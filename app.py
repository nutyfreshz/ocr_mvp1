from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from documents.extractor import extract_document
from export.excel import RECORD_COLUMNS, build_excel
from ocr.engine import retry_thai_id_number, run_auto_ocr
from ocr.preprocess import load_pages, normalize_image
from validation.thai_id import is_valid_thai_citizen_id

st.set_page_config(page_title="Document OCR → Excel", page_icon="📄", layout="wide")

st.title("Document OCR → Excel")
st.caption("Thai Citizen ID + ICAO Passport MVP | PaddleOCR | Local processing in Databricks App")

with st.expander("Processing rules", expanded=False):
    st.markdown(
        """
        - Multiple files: PDF, JPG, JPEG, PNG, TIFF, BMP, WEBP
        - Auto routing: general multilingual OCR + Thai candidate model
        - Thai Citizen ID: validates the 13-digit checksum and retries only the number area when needed
        - Passport: reads ICAO TD3 MRZ and validates MRZ check digits
        - REVIEW means a human should check the flagged field before using the data
        - Uploaded images are processed in memory and are not persisted by this app
        """
    )

col_a, col_b = st.columns([3, 1])
with col_a:
    files = st.file_uploader(
        "Upload documents",
        type=["pdf", "jpg", "jpeg", "png", "tif", "tiff", "bmp", "webp"],
        accept_multiple_files=True,
    )
with col_b:
    max_pages = st.number_input("Max pages / file", min_value=1, max_value=100, value=30, step=1)

run = st.button("Process Documents", type="primary", disabled=not files, use_container_width=True)

if run:
    records = []
    issues = []
    raw_rows = []
    total_files = len(files)
    progress = st.progress(0.0, text="Preparing OCR models...")
    status_box = st.empty()
    start = time.time()

    for file_idx, uploaded in enumerate(files, start=1):
        filename = Path(uploaded.name).name
        try:
            pages = load_pages(uploaded.getvalue(), filename, max_pages=int(max_pages))
        except Exception as exc:
            records.append({
                "source_file": filename,
                "page_number": 1,
                "document_type": "ERROR",
                "detected_language": "",
                "overall_confidence": 0.0,
                "validation_status": "FAIL",
                "review_required": True,
            })
            issues.append({"source_file": filename, "page_number": 1, "field": "file", "value": "", "issue": f"Could not open file: {exc}"})
            continue

        for page_no, page in enumerate(pages, start=1):
            status_box.info(f"OCR: {filename} | page {page_no}/{len(pages)}")
            try:
                image = normalize_image(page)
                ocr_result = run_auto_ocr(image, include_thai_candidate=True)
                record, page_issues = extract_document(ocr_result.texts, ocr_result.mean_confidence)

                # A wrong citizen number is high-risk. Retry only this region when the
                # document is a Thai ID and the first pass does not produce a valid checksum.
                citizen_id = record.get("citizen_id", "")
                if record.get("document_type") == "THAI_ID" and not is_valid_thai_citizen_id(citizen_id):
                    retry_lines = retry_thai_id_number(image, ocr_result.lines)
                    if retry_lines:
                        combined_texts = ocr_result.texts + [line.text for line in retry_lines]
                        retried_record, retried_issues = extract_document(combined_texts, ocr_result.mean_confidence)
                        retried_id = retried_record.get("citizen_id", "")
                        ocr_result.lines.extend(retry_lines)
                        if is_valid_thai_citizen_id(retried_id):
                            record, page_issues = retried_record, retried_issues

                record.update(
                    source_file=filename,
                    page_number=page_no,
                    detected_language=ocr_result.detected_language,
                )
                records.append(record)
                for item in page_issues:
                    issues.append({"source_file": filename, "page_number": page_no, **item})
                for line in ocr_result.lines:
                    raw_rows.append({
                        "source_file": filename,
                        "page_number": page_no,
                        "model": line.model,
                        "text": line.text,
                        "confidence": round(line.score, 5),
                        "box": json.dumps(line.box, ensure_ascii=False),
                    })
            except Exception as exc:
                records.append({
                    "source_file": filename,
                    "page_number": page_no,
                    "document_type": "ERROR",
                    "detected_language": "",
                    "overall_confidence": 0.0,
                    "validation_status": "FAIL",
                    "review_required": True,
                })
                issues.append({"source_file": filename, "page_number": page_no, "field": "ocr", "value": "", "issue": str(exc)})

        progress.progress(file_idx / total_files, text=f"Processed {file_idx}/{total_files} files")

    elapsed = time.time() - start
    status_box.success(f"Completed {len(records)} page(s) in {elapsed:.1f}s")
    st.session_state["records"] = records
    st.session_state["issues"] = issues
    st.session_state["raw_rows"] = raw_rows

if "records" in st.session_state:
    records = st.session_state["records"]
    issues = st.session_state["issues"]
    raw_rows = st.session_state["raw_rows"]

    df = pd.DataFrame(records)
    for col in RECORD_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[RECORD_COLUMNS]

    pass_count = int((df["validation_status"] == "PASS").sum()) if not df.empty else 0
    review_count = int((df["validation_status"] == "REVIEW").sum()) if not df.empty else 0
    fail_count = int((df["validation_status"] == "FAIL").sum()) if not df.empty else 0
    a, b, c, d = st.columns(4)
    a.metric("Pages", len(df))
    b.metric("PASS", pass_count)
    c.metric("REVIEW", review_count)
    d.metric("FAIL", fail_count)

    st.subheader("Results")
    edited = st.data_editor(
        df,
        hide_index=True,
        use_container_width=True,
        disabled=["source_file", "page_number", "document_type", "detected_language", "overall_confidence", "validation_status", "review_required"],
        key="record_editor",
    )

    if issues:
        with st.expander(f"Issues ({len(issues)})", expanded=True):
            st.dataframe(pd.DataFrame(issues), hide_index=True, use_container_width=True)

    excel_bytes = build_excel(edited.to_dict("records"), issues, raw_rows)
    st.download_button(
        "Download Excel",
        data=excel_bytes,
        file_name="ocr_output.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )

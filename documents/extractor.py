from __future__ import annotations

from typing import Dict, List, Tuple

from documents.classifier import detect_document_type
from documents.passport import extract_passport
from documents.thai_id import extract_thai_id


def _has_complete_core_fields(doc_type: str, record: Dict) -> Tuple[bool, List[str]]:
    missing: List[str] = []

    if doc_type == "THAI_ID":
        if not record.get("citizen_id"):
            missing.append("citizen_id")
        full_name = bool(
            (record.get("name_native") and record.get("surname_native"))
            or (record.get("name_english") and record.get("surname_english"))
        )
        if not full_name:
            missing.append("name")
        for field in ("date_of_birth", "issue_date", "expiry_date"):
            if not record.get(field):
                missing.append(field)

    elif doc_type == "PASSPORT":
        for field in (
            "passport_number",
            "name_english",
            "surname_english",
            "date_of_birth",
            "expiry_date",
            "nationality",
            "issuing_country",
        ):
            if not record.get(field):
                missing.append(field)

    return not missing, missing


def extract_document(texts: List[str], mean_confidence: float) -> Tuple[Dict, List[Dict]]:
    doc_type = detect_document_type(texts)
    base = {
        "document_type": doc_type,
        "citizen_id": "",
        "passport_number": "",
        "name_native": "",
        "surname_native": "",
        "name_english": "",
        "surname_english": "",
        "date_of_birth": "",
        "sex": "",
        "nationality": "",
        "issue_date": "",
        "expiry_date": "",
        "issuing_country": "",
        "address": "",
    }
    issues: List[Dict] = []

    if doc_type == "PASSPORT":
        extracted, issues = extract_passport(texts)
        base.update({k: v for k, v in extracted.items() if k in base})
        valid = extracted.get("mrz_valid", False)
    elif doc_type == "THAI_ID":
        extracted, issues = extract_thai_id(texts)
        base.update({k: v for k, v in extracted.items() if k in base})
        valid = extracted.get("thai_id_valid", False)
    else:
        valid = False
        issues.append({"field": "document_type", "value": "UNKNOWN", "issue": "Unsupported or unrecognized document"})

    confidence = max(0.0, min(1.0, mean_confidence))
    if valid:
        confidence = min(1.0, confidence * 0.75 + 0.25)
    elif issues:
        confidence *= 0.8

    complete, missing_fields = _has_complete_core_fields(doc_type, base)
    existing_missing = {i.get("field") for i in issues if "not found" in i.get("issue", "").lower() or "could not be extracted" in i.get("issue", "").lower()}
    for field in missing_fields:
        if field not in existing_missing:
            issues.append({"field": field, "value": base.get(field, ""), "issue": "Required core field missing"})

    checksum_failed = any("checksum failed" in i.get("issue", "").lower() for i in issues)

    if doc_type == "UNKNOWN":
        status = "FAIL"
    elif valid and complete and confidence >= 0.75 and not checksum_failed:
        status = "PASS"
    else:
        status = "REVIEW"

    base.update(
        overall_confidence=round(confidence, 4),
        validation_status=status,
        review_required=status != "PASS",
    )
    return base, issues

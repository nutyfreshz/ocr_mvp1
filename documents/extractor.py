from __future__ import annotations

from typing import Dict, List, Tuple

from documents.classifier import detect_document_type
from documents.passport import extract_passport
from documents.thai_id import extract_thai_id


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

    if doc_type == "UNKNOWN":
        status = "FAIL"
    elif valid and confidence >= 0.75 and not [i for i in issues if "checksum failed" in i["issue"].lower()]:
        status = "PASS"
    else:
        status = "REVIEW"

    base.update(
        overall_confidence=round(confidence, 4),
        validation_status=status,
        review_required=status != "PASS",
    )
    return base, issues

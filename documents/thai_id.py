from __future__ import annotations

import re
from typing import Dict, List, Tuple

from validation.common import first_date_near_keywords
from validation.thai_id import find_thai_citizen_id, is_valid_thai_citizen_id

THAI_TITLES = ("นาย", "นางสาว", "นาง")
EN_TITLES = ("MR.", "MRS.", "MISS", "MS.", "MR", "MRS", "MS")


def _clean_label(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_english_name(texts: List[str]) -> Tuple[str, str]:
    for i, raw in enumerate(texts):
        text = _clean_label(raw)
        m = re.search(r"(?i)\bName\b[:\s]*((?:Mr\.?|Mrs\.?|Miss|Ms\.?)?\s*[A-Z][A-Za-z' -]{2,})", text)
        candidate = m.group(1).strip() if m else ""
        if not candidate and text.lower().strip() in {"name", "name:"} and i + 1 < len(texts):
            candidate = _clean_label(texts[i + 1])
        if candidate:
            words = candidate.split()
            if words and words[0].upper() in EN_TITLES:
                words = words[1:]
            if len(words) >= 2:
                return " ".join(words[:-1]), words[-1]
    return "", ""


def _extract_thai_name(texts: List[str]) -> Tuple[str, str]:
    for raw in texts:
        text = _clean_label(raw)
        for title in THAI_TITLES:
            if title in text:
                candidate = text[text.find(title) + len(title):].strip(" :")
                words = candidate.split()
                if len(words) >= 2:
                    return " ".join(words[:-1]), words[-1]
    return "", ""


def _extract_address(texts: List[str]) -> str:
    for i, raw in enumerate(texts):
        if "ที่อยู่" in raw:
            same = raw.split("ที่อยู่", 1)[1].strip(" :")
            parts = [same] if same else []
            for nxt in texts[i + 1 : i + 3]:
                if any(k in nxt.lower() for k in ["date of", "วันออกบัตร", "วันบัตรหมดอายุ"]):
                    break
                parts.append(nxt.strip())
            return " ".join(x for x in parts if x)
    return ""


def extract_thai_id(texts: List[str]) -> Tuple[Dict, List[Dict]]:
    citizen_id = find_thai_citizen_id(texts) or ""
    name_en, surname_en = _extract_english_name(texts)
    name_th, surname_th = _extract_thai_name(texts)

    record = {
        "citizen_id": citizen_id,
        "name_native": name_th,
        "surname_native": surname_th,
        "name_english": name_en,
        "surname_english": surname_en,
        "date_of_birth": first_date_near_keywords(texts, ["date of birth", "เกิด", "วันเกิด"]) or "",
        "issue_date": first_date_near_keywords(texts, ["date of issue", "วันออกบัตร"]) or "",
        "expiry_date": first_date_near_keywords(texts, ["date of expiry", "expiry", "วันบัตรหมดอายุ"]) or "",
        "address": _extract_address(texts),
        "thai_id_valid": bool(citizen_id and is_valid_thai_citizen_id(citizen_id)),
    }
    issues: List[Dict] = []
    if not citizen_id:
        issues.append({"field": "citizen_id", "value": "", "issue": "13-digit citizen ID not found"})
    elif not record["thai_id_valid"]:
        issues.append({"field": "citizen_id", "value": citizen_id, "issue": "Thai citizen ID checksum failed"})
    if not (name_th or name_en):
        issues.append({"field": "name", "value": "", "issue": "Name could not be extracted reliably"})
    return record, issues

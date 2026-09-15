from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import Iterable

from validation.thai_id import find_thai_citizen_id
from validation.mrz import clean_mrz_line


def _normalize_ocr_phrase(value: str) -> str:
    text = (value or "").upper()
    # Common OCR confusions inside alphabetic document headings.
    text = text.replace("1", "I").replace("|", "I").replace("0", "O")
    return re.sub(r"[^A-Z]+", " ", text).strip()


def _fuzzy_phrase_match(items: list[str], target: str, threshold: float = 0.72) -> bool:
    target_n = _normalize_ocr_phrase(target)
    for raw in items:
        line = _normalize_ocr_phrase(raw)
        if not line:
            continue
        if target_n in line:
            return True
        if SequenceMatcher(None, line, target_n).ratio() >= threshold:
            return True
    return False


def detect_document_type(texts: Iterable[str]) -> str:
    items = list(texts)
    joined = "\n".join(items)
    upper = joined.upper()
    long_lines = [clean_mrz_line(x) for x in items]

    if any(x.startswith("P<") and len(x) >= 35 for x in long_lines):
        return "PASSPORT"
    if "PASSPORT" in upper and any("<<<" in x or len(x) >= 35 for x in long_lines):
        return "PASSPORT"

    thai_anchors = ["บัตรประจำตัวประชาชน", "THAI NATIONAL ID CARD", "IDENTIFICATION NUMBER"]
    if any(anchor in upper if anchor.isascii() else anchor in joined for anchor in thai_anchors):
        return "THAI_ID"

    # Real OCR often turns THAI -> THAL and ID -> 1D. Use tolerant heading matching
    # rather than requiring exact text.
    if _fuzzy_phrase_match(items, "THAI NATIONAL ID CARD", threshold=0.68):
        return "THAI_ID"
    if _fuzzy_phrase_match(items, "IDENTIFICATION NUMBER", threshold=0.72):
        return "THAI_ID"

    normalized_joined = _normalize_ocr_phrase(joined)
    if "NATIONAL" in normalized_joined and "CARD" in normalized_joined and (
        "THAI" in normalized_joined or "THAL" in normalized_joined
    ):
        return "THAI_ID"

    # Some crops omit the card heading entirely but retain a distinctive cluster of
    # Thai-ID labels. Require several signals so a generic document is not classified
    # from one accidental phrase.
    field_targets = ["DATE OF BIRTH", "DATE OF ISSUE", "DATE OF EXPIRY", "LAST NAME"]
    field_hits = sum(_fuzzy_phrase_match(items, target, threshold=0.70) for target in field_targets)
    has_thai_script = bool(re.search(r"[ก-๙]", joined))
    thai_field_hint = any(k in joined for k in ["ที่อยู่", "วันออกบัตร", "วันบัตรหมดอายุ", "เกิดวันที่"])
    if field_hits >= 3 or ((has_thai_script or thai_field_hint) and field_hits >= 2):
        return "THAI_ID"

    if find_thai_citizen_id(items):
        return "THAI_ID"
    return "UNKNOWN"

from __future__ import annotations

from typing import Iterable

from validation.thai_id import find_thai_citizen_id
from validation.mrz import clean_mrz_line


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
    if find_thai_citizen_id(items):
        return "THAI_ID"
    return "UNKNOWN"

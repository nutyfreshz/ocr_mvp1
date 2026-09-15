from __future__ import annotations

from datetime import datetime
import re
from typing import Iterable, Optional

EN_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "SEPT": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}
TH_MONTHS = {
    "ม.ค.": 1, "ก.พ.": 2, "มี.ค.": 3, "เม.ย.": 4, "พ.ค.": 5, "มิ.ย.": 6,
    "ก.ค.": 7, "ส.ค.": 8, "ก.ย.": 9, "ต.ค.": 10, "พ.ย.": 11, "ธ.ค.": 12,
}


def parse_human_date(text: str) -> Optional[str]:
    text = " ".join((text or "").replace(",", " ").split())

    m = re.search(r"\b(\d{1,2})[\s/.-]+([A-Za-z]{3,9})[\s/.-]+(\d{4})\b", text)
    if m:
        day, month_word, year = int(m.group(1)), m.group(2)[:4].upper().rstrip("."), int(m.group(3))
        month = EN_MONTHS.get(month_word) or EN_MONTHS.get(month_word[:3])
        if month:
            try:
                return datetime(year, month, day).date().isoformat()
            except ValueError:
                pass

    m = re.search(r"\b(\d{1,2})[\s/.-]+(\d{1,2})[\s/.-]+(\d{4})\b", text)
    if m:
        day, month, year = map(int, m.groups())
        if year >= 2400:
            year -= 543
        try:
            return datetime(year, month, day).date().isoformat()
        except ValueError:
            pass

    for month_word, month in TH_MONTHS.items():
        m = re.search(rf"(\d{{1,2}})\s*{re.escape(month_word)}\s*(\d{{4}})", text)
        if m:
            day, year = int(m.group(1)), int(m.group(2))
            if year >= 2400:
                year -= 543
            try:
                return datetime(year, month, day).date().isoformat()
            except ValueError:
                pass
    return None


def first_date_near_keywords(texts: Iterable[str], keywords: Iterable[str]) -> Optional[str]:
    keywords_l = [k.lower() for k in keywords]
    items = list(texts)
    for i, text in enumerate(items):
        lower = text.lower()
        if any(k in lower for k in keywords_l):
            for candidate in (text, items[i + 1] if i + 1 < len(items) else ""):
                parsed = parse_human_date(candidate)
                if parsed:
                    return parsed
    return None

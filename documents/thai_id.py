from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import Dict, List, Tuple

from validation.common import first_date_near_keywords, parse_human_date
from validation.thai_id import find_thai_citizen_id, is_valid_thai_citizen_id

THAI_TITLES = ("นางสาว", "เด็กหญิง", "เด็กชาย", "น.ส.", "ด.ญ.", "ด.ช.", "น.ส", "ด.ญ", "ด.ช", "นาย", "นาง")
EN_TITLE_PATTERN = r"(?:Mr\.?|Mrs\.?|Miss|Ms\.?|Master|Mise|Mins)"


def _clean_label(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _clean_english_person_value(value: str) -> str:
    value = _clean_label(value).strip(" :-")
    value = re.sub(rf"(?i)^{EN_TITLE_PATTERN}\s+", "", value).strip()
    if not value:
        return ""
    if re.search(r"\d", value):
        return ""
    if any(k in value.lower() for k in ["date of", "identification", "nationality", "address", "expiry", "issue"]):
        return ""
    if not re.fullmatch(r"[A-Za-z' -]{2,}", value):
        return ""
    return value


def _next_english_value(texts: List[str], index: int, max_ahead: int = 2) -> str:
    for j in range(index + 1, min(len(texts), index + 1 + max_ahead)):
        candidate = _clean_english_person_value(texts[j])
        if candidate:
            return candidate
    return ""


def _fuzzy_surname_label(text: str) -> Tuple[bool, str]:
    cleaned = _clean_label(text)
    tokens = cleaned.split()
    if not tokens:
        return False, ""

    # Exact-ish one-word Surname remains common.
    if SequenceMatcher(None, tokens[0].lower(), "surname").ratio() >= 0.78:
        return True, " ".join(tokens[1:])

    if len(tokens) >= 2:
        head = " ".join(tokens[:2]).lower()
        score = SequenceMatcher(None, head, "last name").ratio()
        # Real samples include OCR forms such as Last nama, Laut Name, Lart Nems,
        # Exst zame and Lest saw. Keep this low threshold scoped only to Thai-ID parsing.
        if score >= 0.57:
            return True, " ".join(tokens[2:])
    return False, ""


def _extract_english_name(texts: List[str]) -> Tuple[str, str]:
    given = ""
    surname = ""

    for i, raw in enumerate(texts):
        text = _clean_label(raw)

        surname_match = re.search(r"(?i)\b(?:Last\s*Name|Surname)\b\s*[:\-]?\s*(.*)$", text)
        fuzzy_surname, fuzzy_tail = _fuzzy_surname_label(text)
        if not surname and (surname_match or fuzzy_surname):
            tail = surname_match.group(1) if surname_match else fuzzy_tail
            surname = _clean_english_person_value(tail)
            if not surname:
                surname = _next_english_value(texts, i)

        if surname_match or fuzzy_surname:
            continue

        name_match = re.search(r"(?i)\bName\b\s*[:\-]?\s*(.*)$", text)
        if name_match and not given:
            candidate = name_match.group(1)
            candidate = re.split(r"(?i)\b(?:Last\s*Name|Surname)\b", candidate, maxsplit=1)[0]
            given = _clean_english_person_value(candidate)
            if not given:
                given = _next_english_value(texts, i)

        # OCR often destroys the word "Name" but preserves the title and actual name.
        if not given:
            title_match = re.search(rf"(?i)\b{EN_TITLE_PATTERN}\s+([A-Za-z][A-Za-z' -]{{1,}})$", text)
            if title_match:
                given = _clean_english_person_value(title_match.group(1))

    if given and not surname:
        words = given.split()
        if len(words) >= 2:
            given, surname = " ".join(words[:-1]), words[-1]

    return given, surname


def _extract_thai_name(texts: List[str]) -> Tuple[str, str]:
    for i, raw in enumerate(texts):
        text = _clean_label(raw)
        for title in THAI_TITLES:
            if title in text:
                candidate = text[text.find(title) + len(title):].strip(" :,.ๆ")
                words = candidate.split()
                if len(words) >= 2:
                    return " ".join(words[:-1]), words[-1]
                if len(words) == 1 and i + 1 < len(texts):
                    nxt = _clean_label(texts[i + 1])
                    if re.fullmatch(r"[ก-๙]+", nxt):
                        return words[0], nxt
    return "", ""


def _extract_address(texts: List[str]) -> str:
    for i, raw in enumerate(texts):
        if "ที่อยู่" in raw:
            same = raw.split("ที่อยู่", 1)[1].strip(" :")
            parts = [same] if same else []
            for nxt in texts[i + 1 : i + 4]:
                if any(k in nxt.lower() for k in ["date of", "วันออกบัตร", "วันบัตรหมดอายุ"]):
                    break
                parts.append(nxt.strip())
            return " ".join(x for x in parts if x)
    return ""


def _collect_unique_dates(texts: List[str]) -> List[str]:
    found: List[str] = []
    for text in texts:
        parsed = parse_human_date(text)
        if parsed and parsed not in found:
            found.append(parsed)
    return found


def _extract_dates(texts: List[str]) -> Tuple[str, str, str]:
    """Return DOB, issue date, expiry date.

    Thai ID OCR frequently emits dates before their labels or in a different visual order.
    When all three unique dates are visible, chronology is more reliable than OCR list order:
    birth < issue < expiry.
    """
    dates = _collect_unique_dates(texts)
    if len(dates) >= 3:
        ordered = sorted(dates)
        return ordered[0], ordered[-2], ordered[-1]

    dob = first_date_near_keywords(texts, ["date of birth", "เกิด", "วันเกิด"]) or ""
    issue = first_date_near_keywords(texts, ["date of issue", "วันออกบัตร"]) or ""
    expiry = first_date_near_keywords(texts, ["date of expiry", "expiry", "วันบัตรหมดอายุ"]) or ""

    if len(dates) == 2 and not dob:
        # If birth is absent, the two complete dates visible near the bottom of an ID
        # are overwhelmingly the issue and expiry dates. Chronology is safer than OCR order.
        ordered = sorted(dates)
        issue, expiry = ordered[0], ordered[1]
    return dob, issue, expiry


def extract_thai_id(texts: List[str]) -> Tuple[Dict, List[Dict]]:
    citizen_id = find_thai_citizen_id(texts) or ""
    name_en, surname_en = _extract_english_name(texts)
    name_th, surname_th = _extract_thai_name(texts)
    dob, issue_date, expiry_date = _extract_dates(texts)

    record = {
        "citizen_id": citizen_id,
        "name_native": name_th,
        "surname_native": surname_th,
        "name_english": name_en,
        "surname_english": surname_en,
        "date_of_birth": dob,
        "issue_date": issue_date,
        "expiry_date": expiry_date,
        "address": _extract_address(texts),
        "thai_id_valid": bool(citizen_id and is_valid_thai_citizen_id(citizen_id)),
    }
    issues: List[Dict] = []
    if not citizen_id:
        issues.append({"field": "citizen_id", "value": "", "issue": "13-digit citizen ID not found"})
    elif not record["thai_id_valid"]:
        issues.append({"field": "citizen_id", "value": citizen_id, "issue": "Thai citizen ID checksum failed"})
    if not ((name_th and surname_th) or (name_en and surname_en)):
        issues.append({"field": "name", "value": "", "issue": "Complete name could not be extracted reliably"})
    if not dob:
        issues.append({"field": "date_of_birth", "value": "", "issue": "Date of birth not found"})
    if not issue_date:
        issues.append({"field": "issue_date", "value": "", "issue": "Issue date not found"})
    if not expiry_date:
        issues.append({"field": "expiry_date", "value": "", "issue": "Expiry date not found"})
    return record, issues

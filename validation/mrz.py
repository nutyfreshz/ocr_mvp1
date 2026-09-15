from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re
from typing import Iterable, Optional

_WEIGHTS = (7, 3, 1)


def _char_value(ch: str) -> int:
    if ch.isdigit():
        return int(ch)
    if "A" <= ch <= "Z":
        return ord(ch) - ord("A") + 10
    if ch == "<":
        return 0
    raise ValueError(f"Unsupported MRZ character: {ch!r}")


def mrz_check_digit(data: str) -> str:
    total = sum(_char_value(ch) * _WEIGHTS[i % 3] for i, ch in enumerate(data))
    return str(total % 10)


def validate_mrz_field(data: str, check_digit: str) -> bool:
    return bool(check_digit and check_digit.isdigit() and mrz_check_digit(data) == check_digit)


def clean_mrz_line(text: str) -> str:
    text = (text or "").upper().replace(" ", "")
    return re.sub(r"[^A-Z0-9<]", "", text)


def _repair_numeric(value: str) -> str:
    return value.translate(str.maketrans({"O": "0", "Q": "0", "I": "1", "L": "1", "Z": "2", "S": "5", "B": "8", "G": "6"}))


def _parse_mrz_date(raw: str, kind: str) -> Optional[str]:
    raw = _repair_numeric(raw)
    if not re.fullmatch(r"\d{6}", raw):
        return None
    yy, mm, dd = int(raw[:2]), int(raw[2:4]), int(raw[4:6])
    today = date.today()
    if kind == "birth":
        year = 2000 + yy
        if year > today.year:
            year -= 100
    else:
        options = [1900 + yy, 2000 + yy, 2100 + yy]
        year = min(options, key=lambda y: abs(y - today.year))
    try:
        return date(year, mm, dd).isoformat()
    except ValueError:
        return None


@dataclass
class MRZPassport:
    passport_number: str
    issuing_country: str
    nationality: str
    surname: str
    given_names: str
    date_of_birth: Optional[str]
    sex: str
    expiry_date: Optional[str]
    passport_number_valid: bool
    birth_date_valid: bool
    expiry_date_valid: bool
    composite_valid: bool
    line1: str
    line2: str

    @property
    def core_valid(self) -> bool:
        return self.passport_number_valid and self.birth_date_valid and self.expiry_date_valid


def _pad44(line: str) -> str:
    line = clean_mrz_line(line)
    return (line + "<" * 44)[:44]


def parse_td3(lines: Iterable[str]) -> Optional[MRZPassport]:
    cleaned = [clean_mrz_line(x) for x in lines]
    candidates = [x for x in cleaned if len(x) >= 35]
    line1 = next((x for x in candidates if x.startswith("P<") or x.startswith("P0") or x.startswith("P1")), None)
    if not line1:
        return None
    idx = cleaned.index(line1)
    following = cleaned[idx + 1 :]
    line2 = next((x for x in following if len(x) >= 35), None)
    if not line2:
        line2 = next((x for x in candidates if x != line1), None)
    if not line2:
        return None

    l1, l2 = _pad44(line1), _pad44(line2)

    names = l1[5:44]
    surname_raw, _, given_raw = names.partition("<<")
    surname = surname_raw.replace("<", " ").strip()
    given_names = given_raw.replace("<", " ").strip()

    passport_raw = l2[0:9]
    passport_number = passport_raw.replace("<", "").strip()
    passport_check = _repair_numeric(l2[9])
    nationality = l2[10:13].replace("<", "").strip()
    birth_raw = _repair_numeric(l2[13:19])
    birth_check = _repair_numeric(l2[19])
    sex = l2[20].replace("<", "X")
    expiry_raw = _repair_numeric(l2[21:27])
    expiry_check = _repair_numeric(l2[27])

    passport_valid = validate_mrz_field(passport_raw, passport_check)
    birth_valid = validate_mrz_field(birth_raw, birth_check)
    expiry_valid = validate_mrz_field(expiry_raw, expiry_check)

    composite_data = l2[0:10] + l2[13:20] + l2[21:43]
    composite_check = _repair_numeric(l2[43])
    composite_valid = validate_mrz_field(composite_data, composite_check)

    return MRZPassport(
        passport_number=passport_number,
        issuing_country=l1[2:5].replace("<", "").strip(),
        nationality=nationality,
        surname=surname,
        given_names=given_names,
        date_of_birth=_parse_mrz_date(birth_raw, "birth"),
        sex=sex,
        expiry_date=_parse_mrz_date(expiry_raw, "expiry"),
        passport_number_valid=passport_valid,
        birth_date_valid=birth_valid,
        expiry_date_valid=expiry_valid,
        composite_valid=composite_valid,
        line1=l1,
        line2=l2,
    )

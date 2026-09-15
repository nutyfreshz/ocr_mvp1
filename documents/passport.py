from __future__ import annotations

from typing import Dict, List, Tuple

from validation.mrz import parse_td3


def extract_passport(texts: List[str]) -> Tuple[Dict, List[Dict]]:
    mrz = parse_td3(texts)
    issues: List[Dict] = []
    record = {
        "passport_number": "",
        "name_english": "",
        "surname_english": "",
        "date_of_birth": "",
        "sex": "",
        "nationality": "",
        "expiry_date": "",
        "issuing_country": "",
        "mrz_valid": False,
    }
    if not mrz:
        issues.append({"field": "mrz", "value": "", "issue": "TD3 MRZ not found or incomplete"})
        return record, issues

    record.update(
        passport_number=mrz.passport_number,
        name_english=mrz.given_names,
        surname_english=mrz.surname,
        date_of_birth=mrz.date_of_birth or "",
        sex=mrz.sex,
        nationality=mrz.nationality,
        expiry_date=mrz.expiry_date or "",
        issuing_country=mrz.issuing_country,
        mrz_valid=mrz.core_valid,
    )
    checks = {
        "passport_number": mrz.passport_number_valid,
        "date_of_birth": mrz.birth_date_valid,
        "expiry_date": mrz.expiry_date_valid,
        "mrz_composite": mrz.composite_valid,
    }
    for field, ok in checks.items():
        if not ok:
            issues.append({"field": field, "value": record.get(field, ""), "issue": "MRZ checksum failed"})
    return record, issues

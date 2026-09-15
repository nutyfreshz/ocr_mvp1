import re
from typing import Iterable, Optional


def normalize_thai_citizen_id(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def is_valid_thai_citizen_id(value: str) -> bool:
    digits = normalize_thai_citizen_id(value)
    if len(digits) != 13 or len(set(digits)) == 1:
        return False
    total = sum(int(digits[i]) * (13 - i) for i in range(12))
    check_digit = (11 - (total % 11)) % 10
    return check_digit == int(digits[-1])


def find_thai_citizen_id(texts: Iterable[str]) -> Optional[str]:
    candidates = []
    for text in texts:
        compact = re.sub(r"[^0-9]", "", text or "")
        if len(compact) == 13:
            candidates.append(compact)
        candidates.extend(re.findall(r"(?<!\d)\d{13}(?!\d)", text or ""))

    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if is_valid_thai_citizen_id(candidate):
            return candidate
    return candidates[0] if candidates else None

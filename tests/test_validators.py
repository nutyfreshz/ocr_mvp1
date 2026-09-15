from validation.mrz import mrz_check_digit, parse_td3
from validation.thai_id import is_valid_thai_citizen_id


def test_mrz_known_td3_example():
    lines = [
        "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<",
        "L898902C36UTO7408122F1204159ZE184226B<<<<<10",
    ]
    result = parse_td3(lines)
    assert result is not None
    assert result.passport_number == "L898902C3"
    assert result.passport_number_valid
    assert result.birth_date_valid
    assert result.expiry_date_valid


def test_mrz_check_digit_example():
    assert mrz_check_digit("L898902C3") == "6"


def test_thai_id_rejects_bad_length_and_repeated():
    assert not is_valid_thai_citizen_id("123")
    assert not is_valid_thai_citizen_id("1111111111111")

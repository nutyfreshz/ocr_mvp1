from documents.classifier import detect_document_type
from documents.extractor import extract_document
from documents.thai_id import extract_thai_id
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


def test_classifier_tolerates_common_ocr_heading_errors():
    texts = ["Thal National 1D Card", "Identification Number"]
    assert detect_document_type(texts) == "THAI_ID"


def test_thai_id_extracts_split_english_name_and_dates_by_chronology():
    texts = [
        "Thai National ID Card",
        "Identification Number 1 2345 67890 12 1",
        "Name Mr. Demo",
        "Last Name",
        "Person",
        "20 Nov. 1990",
        "19 Apr. 2020",
        "20 Apr. 2029",
        "Date of Expiry",
        "Date of Issue",
    ]
    record, issues = extract_thai_id(texts)
    assert record["citizen_id"] == "1234567890121"
    assert record["name_english"] == "Demo"
    assert record["surname_english"] == "Person"
    assert record["date_of_birth"] == "1990-11-20"
    assert record["issue_date"] == "2020-04-19"
    assert record["expiry_date"] == "2029-04-20"
    assert record["thai_id_valid"]
    assert not [i for i in issues if i["field"] in {"citizen_id", "name", "date_of_birth", "issue_date", "expiry_date"}]


def test_thai_id_does_not_pass_when_core_fields_are_missing():
    texts = [
        "Thai National ID Card",
        "Identification Number 1 2345 67890 12 1",
        "Name Mr. Demo",
        "Last Name Person",
    ]
    record, issues = extract_document(texts, 0.98)
    assert record["document_type"] == "THAI_ID"
    assert record["validation_status"] == "REVIEW"
    assert record["review_required"] is True
    missing = {i["field"] for i in issues}
    assert {"date_of_birth", "issue_date", "expiry_date"}.issubset(missing)

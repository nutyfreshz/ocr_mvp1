from documents.classifier import detect_document_type
from documents.extractor import extract_document
from documents.thai_id import extract_thai_id
from validation.common import parse_human_date
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


def test_common_ocr_month_typo_is_parsed():
    assert parse_human_date("21 Feh. 2019") == "2019-02-21"


def test_classifier_tolerates_common_ocr_heading_errors():
    texts = ["Thal National 1D Card", "Identification Number"]
    assert detect_document_type(texts) == "THAI_ID"


def test_classifier_uses_field_cluster_when_heading_is_missing():
    texts = [
        "Name",
        "Master Demo",
        "Last nama",
        "Person",
        "Date of Birth 16 Oct. 2007",
        "Date of Issus",
        "Date of Expiry",
        "ที่อยู่ 1 ถนนตัวอย่าง",
    ]
    assert detect_document_type(texts) == "THAI_ID"


def test_thai_id_extracts_split_english_name_and_consensus_dates():
    texts = [
        "Thai National ID Card",
        "Identification Number 1 2345 67890 12 1",
        "Name Mr. Demo",
        "Last Name",
        "Person",
        "Date of Birth 20 Nov. 1990",
        "19 Apr. 2020",
        "20 Apr. 2029",
        "20 Aug. 2029",  # one-off OCR error
        "19 Apr. 2020",  # bilingual agreement
        "20 Apr. 2029",  # bilingual agreement
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


def test_thai_id_handles_fuzzy_name_labels_and_master_title():
    texts = [
        "Thai National ID Card",
        "Name",
        "Master Theerat",
        "Last nama",
        "Sriprasert",
        "Date of Birth 16 Oct. 2007",
        "30 Jan. 2020",
        "15 Oct. 2028",
    ]
    record, _ = extract_thai_id(texts)
    assert record["name_english"] == "Theerat"
    assert record["surname_english"] == "Sriprasert"
    assert record["date_of_birth"] == "2007-10-16"
    assert record["issue_date"] == "2020-01-30"
    assert record["expiry_date"] == "2028-10-15"


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

# OCR MVP 1

Free/local OCR web app for Databricks Apps. It accepts multiple documents, recognizes Thai ID cards and ICAO passports, validates key identifiers, lets a user review extracted rows, and exports Excel.

## Core stack

- Streamlit on Databricks Apps
- PaddleOCR 3.7.0
- PP-OCRv6 general multilingual OCR
- PP-OCRv5 Thai recognizer (`th_PP-OCRv5_mobile_rec`)
- PyMuPDF for PDF rendering
- OpenCV/Pillow for image cleanup
- pandas/openpyxl for Excel output

No paid OCR API and no LLM are required.

## Supported MVP documents

### Thai Citizen ID

Extracts best-effort fields including citizen ID, Thai/English name, DOB, issue/expiry date, and address. The 13-digit citizen ID is checksum validated.

### Passport

Uses the standardized ICAO TD3 Machine Readable Zone (MRZ) as the source of truth for passport number, Latin name, DOB, sex, nationality, expiry, and issuing country. Key MRZ check digits are validated.

A Chinese, Japanese, Thai, or other passport still exposes its core fields through the Latin MRZ, which avoids needing a country-specific template for each passport.

## Auto language behavior

The app runs the current PaddleOCR general model and a Thai candidate pass. The general PP-OCRv6 model covers Chinese, English, Japanese, and many Latin-script languages. If meaningful Thai script is detected, Thai recognition is merged automatically.

This MVP intentionally does **not** run every script-specific model on every page because that would multiply CPU latency and memory use. Arabic/Cyrillic/Indic native-script extraction can be added later without changing the Excel schema. Passport core fields remain readable from MRZ regardless of the native language printed elsewhere.

## Excel output

- `RECORDS`: one page/document record per row
- `ISSUES`: fields that failed validation or require review
- `RAW_OCR`: OCR text, confidence, model, and bounding box for audit/debugging

Status meanings:

- `PASS`: structural validation succeeded
- `REVIEW`: document was recognized but at least one important field needs human verification
- `FAIL`: unsupported/unrecognized document or OCR processing error

## Databricks Apps deployment

`app.yaml` is already configured for Streamlit.

1. Create a Databricks App.
2. Sync/clone this repository into the app source location.
3. Deploy the source.
4. On first OCR use, PaddleOCR downloads its model weights. The app therefore needs outbound access to the Paddle model host, or the models must be pre-cached in your Databricks environment.

Databricks Apps automatically supplies the Streamlit host/port environment variables, so the app only needs `streamlit run app.py` in `app.yaml`.

## Local Windows test

Double-click:

`run_local.bat`

It creates `.venv`, installs requirements, and starts Streamlit.

> First install is large because PaddlePaddle and OCR models are downloaded.

## Push updates to GitHub

Double-click:

`push_to_github.bat`

The script points to:

`https://github.com/nutyfreshz/ocr_mvp1.git`

It contains no GitHub token. Authentication is handled by your normal Git credential flow.

## Privacy

The current app does not intentionally persist uploaded identity documents. It processes uploads in memory. Do not add names, citizen IDs, passport numbers, DOB, or raw OCR text to application logs.

For production, restrict Databricks App permissions and decide explicitly whether any audit data is allowed to persist.

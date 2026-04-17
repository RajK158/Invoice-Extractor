# data/schema.md — Invoice Data Schema

## Invoice Record Schema

All extracted invoices are stored in SQLite and indexed in Whoosh. Below is the
complete field specification including type, source, and validation rules.

---

### Core Identifier Fields

| Field         | Type    | Description                              | Mandatory |
|---------------|---------|------------------------------------------|-----------|
| `id`          | INTEGER | Auto-increment primary key               | Auto      |
| `filename`    | STRING  | Original uploaded file name              | Yes       |
| `file_hash`   | STRING  | SHA-256 of the file (dedup key)          | Yes       |

---

### Extracted Invoice Fields

| Field             | Type    | Source              | Validation Rule                           |
|-------------------|---------|---------------------|-------------------------------------------|
| `invoice_number`  | STRING  | Regex / NER         | 3–30 alphanumeric chars                   |
| `invoice_date`    | STRING  | Regex / NER / spaCy | ISO 8601 (YYYY-MM-DD); not in future      |
| `due_date`        | STRING  | Regex               | ISO 8601; must be ≥ invoice_date          |
| `vendor_name`     | STRING  | Regex / NER / spaCy | Non-empty; max 200 chars                  |
| `buyer_name`      | STRING  | Regex / NER / spaCy | Non-empty; max 200 chars                  |
| `total_amount`    | FLOAT   | Regex               | > 0; ≈ subtotal + tax (±5% tolerance)     |
| `subtotal`        | FLOAT   | Regex               | ≤ total_amount                            |
| `tax_amount`      | FLOAT   | Regex               | ≥ 0                                       |
| `tax_rate`        | STRING  | Regex               | Percentage string (e.g., "18%")           |
| `discount`        | FLOAT   | Regex               | ≥ 0                                       |
| `currency`        | STRING  | Regex / Symbol map  | 3-letter ISO 4217 code (e.g., USD)        |
| `tax_id`          | STRING  | Regex               | GSTIN / VAT / EIN / TIN format            |
| `po_number`       | STRING  | Regex               | 3–20 alphanumeric chars                   |
| `address`         | TEXT    | Regex / NER         | Max 200 chars                             |
| `payment_terms`   | STRING  | Regex               | e.g., "Net 30", "Due on receipt"          |
| `detected_language` | STRING | langdetect / script | ISO 639-1 code (e.g., en, hi, ar, fr)   |

---

### OCR & Processing Metadata

| Field                  | Type    | Description                               |
|------------------------|---------|-------------------------------------------|
| `ocr_engine`           | STRING  | "tesseract" or "easyocr"                  |
| `ocr_confidence`       | FLOAT   | Mean word-level OCR confidence (0–1)      |
| `avg_field_confidence` | FLOAT   | Mean field extraction confidence (0–1)    |
| `raw_text`             | TEXT    | Full OCR output (up to 50K chars)         |
| `processed_at`         | DATETIME| UTC timestamp of processing               |

---

### Validation & Quality Fields

| Field               | Type    | Values                                     |
|---------------------|---------|--------------------------------------------|
| `validation_status` | STRING  | PASSED / WARNING / FAILED                  |
| `validation_report` | TEXT    | JSON: {status, passed[], warnings[], errors[]} |
| `confidence_scores` | TEXT    | JSON: {field_name: float, ...}             |
| `is_duplicate`      | BOOLEAN | True if same invoice_number found in DB    |

---

### Confidence Score Interpretation

| Score Range | Label     | Meaning                                          |
|-------------|-----------|--------------------------------------------------|
| 0.85 – 1.00 | High      | Strong label-match via regex or NER              |
| 0.60 – 0.84 | Medium    | Extracted via secondary pattern or fallback NER  |
| 0.35 – 0.59 | Low       | Heuristic guess; manual verification recommended |
| 0.00 – 0.34 | Very Low  | Field likely missing or unrecognized             |

---

### Supported File Formats

| Format | Extensions                          | Processing Method        |
|--------|-------------------------------------|--------------------------|
| Image  | .jpg .jpeg .png .tiff .tif .bmp    | Direct OCR               |
| PDF    | .pdf                                | pdf2image / PyMuPDF → OCR|

---

### Supported Languages (OCR + Extraction)

| Code | Language             | OCR Engine Support  |
|------|----------------------|---------------------|
| en   | English              | Tesseract + EasyOCR |
| hi   | Hindi                | Tesseract + EasyOCR |
| ar   | Arabic               | Tesseract + EasyOCR |
| fr   | French               | Tesseract + EasyOCR |
| de   | German               | Tesseract + EasyOCR |
| es   | Spanish              | Tesseract + EasyOCR |
| zh   | Chinese (Simplified) | Tesseract + EasyOCR |
| ja   | Japanese             | Tesseract + EasyOCR |
| pt   | Portuguese           | Tesseract + EasyOCR |
| it   | Italian              | Tesseract            |
| ko   | Korean               | EasyOCR              |
| ru   | Russian              | Tesseract + EasyOCR |
| tr   | Turkish              | Tesseract            |
| nl   | Dutch                | Tesseract            |

---

### JSON Export Sample

```json
[
  {
    "id": 1,
    "filename": "invoice_001.jpg",
    "invoice_number": "INV-2024-0042",
    "invoice_date": "2024-03-15",
    "due_date": "2024-04-14",
    "vendor_name": "Acme Technologies LLC",
    "buyer_name": "Global Imports Inc",
    "total_amount": 1180.00,
    "subtotal": 1000.00,
    "tax_amount": 180.00,
    "tax_rate": "18%",
    "discount": null,
    "currency": "USD",
    "tax_id": "27AAPFU0939F1ZV",
    "po_number": "PO-5521",
    "payment_terms": "Net 30",
    "detected_language": "en",
    "ocr_engine": "tesseract",
    "ocr_confidence": 0.921,
    "avg_field_confidence": 0.873,
    "validation_status": "PASSED",
    "is_duplicate": false,
    "processed_at": "2024-03-15T10:23:44"
  }
]
```

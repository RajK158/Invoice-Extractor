"""
config.py - Central configuration for Multi-Language Invoice Extractor
"""

import os
from pathlib import Path

# ─── Project Paths ───────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SAMPLES_DIR = DATA_DIR / "samples"
INDEX_DIR = DATA_DIR / "index"
DB_PATH = BASE_DIR / "data" / "invoices.db"
LOG_DIR = BASE_DIR / "logs"
EXPORT_DIR = BASE_DIR / "app" / "exports" / "output"

# ─── OCR Settings ────────────────────────────────────────────────────────────
TESSERACT_CMD = os.getenv("TESSERACT_CMD", r"tesseract")  # Override via .env on Windows
TESSERACT_LANGS = ["eng", "hin", "ara", "fra", "deu", "spa", "chi_sim", "jpn"]
EASYOCR_LANGS_MAP = {
    "en": ["en"],
    "hi": ["hi", "en"],
    "ar": ["ar", "en"],
    "fr": ["fr", "en"],
    "de": ["de", "en"],
    "es": ["es", "en"],
    "zh": ["ch_sim", "en"],
    "ja": ["ja", "en"],
    "unknown": ["en"],
}
OCR_DPI = 300
OCR_CONFIDENCE_THRESHOLD = 60  # Tesseract confidence threshold

# ─── Image Preprocessing ─────────────────────────────────────────────────────
PREPROCESS_RESIZE_WIDTH = 1800
PREPROCESS_DENOISE_STRENGTH = 10
PREPROCESS_THRESHOLD_BLOCK = 11
PREPROCESS_THRESHOLD_C = 2

# ─── NLP Settings ────────────────────────────────────────────────────────────
SPACY_MODEL = "en_core_web_sm"
NLP_CONFIDENCE_HIGH = 0.85
NLP_CONFIDENCE_MEDIUM = 0.65
NLP_CONFIDENCE_LOW = 0.40

# ─── Validation Rules ────────────────────────────────────────────────────────
TAX_TOTAL_TOLERANCE = 0.05  # 5% tolerance for subtotal+tax vs total check
MANDATORY_FIELDS = ["invoice_number", "invoice_date", "total_amount", "vendor_name"]
INVOICE_NUMBER_MIN_LEN = 3
INVOICE_NUMBER_MAX_LEN = 30

# ─── Search / Retrieval ──────────────────────────────────────────────────────
WHOOSH_INDEX_DIR = str(INDEX_DIR / "whoosh")
CACHE_MAX_SIZE = 500          # LRU cache max entries
SEARCH_RESULTS_LIMIT = 100

# ─── Supported Currencies ────────────────────────────────────────────────────
CURRENCY_SYMBOLS = {
    "$": "USD", "€": "EUR", "£": "GBP", "₹": "INR", "¥": "JPY",
    "₩": "KRW", "₺": "TRY", "﷼": "SAR", "د.إ": "AED", "R": "ZAR",
    "CHF": "CHF", "CAD": "CAD", "AUD": "AUD", "SGD": "SGD",
}

# ─── Logging ─────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_FILE = LOG_DIR / "invoice_extractor.log"

# ─── Batch Processing ────────────────────────────────────────────────────────
BATCH_MAX_WORKERS = int(os.getenv("BATCH_MAX_WORKERS", 4))
SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp"}
SUPPORTED_PDF_EXT = ".pdf"

# ─── Export ──────────────────────────────────────────────────────────────────
CSV_EXPORT_FILENAME = "invoice_export.csv"
JSON_EXPORT_FILENAME = "invoice_export.json"

# Ensure required dirs exist at import time
for _dir in [RAW_DIR, PROCESSED_DIR, SAMPLES_DIR, INDEX_DIR, LOG_DIR, EXPORT_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)

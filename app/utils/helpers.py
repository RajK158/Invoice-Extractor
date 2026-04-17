"""
app/utils/helpers.py - Shared utility functions
"""

import re
import hashlib
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.utils.logger import get_logger

logger = get_logger(__name__)


# ─── String Helpers ──────────────────────────────────────────────────────────

def normalize_whitespace(text: str) -> str:
    """Collapse multiple whitespace characters into a single space."""
    return re.sub(r"\s+", " ", text).strip()


def clean_text(text: str) -> str:
    """Remove non-printable characters and normalize unicode."""
    text = unicodedata.normalize("NFKC", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cc" or ch in "\n\t")
    return normalize_whitespace(text)


def safe_float(value: str) -> Optional[float]:
    """
    Convert string to float, handling commas, currency symbols, etc.

    Args:
        value: Raw string like '$1,234.56' or '1.234,56'

    Returns:
        float or None
    """
    if not value:
        return None
    cleaned = re.sub(r"[^\d.,\-]", "", str(value))
    # Handle European comma-decimal notation: 1.234,56 → 1234.56
    if re.match(r"^\d{1,3}(\.\d{3})+(,\d+)?$", cleaned):
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def safe_int(value: str) -> Optional[int]:
    """Convert string to int, stripping non-numeric characters."""
    if not value:
        return None
    cleaned = re.sub(r"[^\d]", "", str(value))
    try:
        return int(cleaned) if cleaned else None
    except ValueError:
        return None


# ─── Date Helpers ────────────────────────────────────────────────────────────

DATE_FORMATS = [
    "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d",
    "%d.%m.%Y", "%m.%d.%Y", "%B %d, %Y", "%b %d, %Y",
    "%d %B %Y", "%d %b %Y", "%Y%m%d",
    "%d/%m/%y", "%m/%d/%y", "%y-%m-%d",
]


def parse_date(date_str: str) -> Optional[datetime]:
    """
    Attempt to parse a date string using multiple known formats.

    Args:
        date_str: Raw date string from OCR

    Returns:
        datetime object or None
    """
    if not date_str:
        return None
    cleaned = normalize_whitespace(date_str)
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    logger.debug(f"Could not parse date: {date_str!r}")
    return None


def format_date_iso(date_str: str) -> str:
    """Return ISO 8601 date string or original if parsing fails."""
    dt = parse_date(date_str)
    return dt.strftime("%Y-%m-%d") if dt else date_str


# ─── File Helpers ────────────────────────────────────────────────────────────

def file_hash(filepath: Path, algorithm: str = "sha256") -> str:
    """
    Compute a hex digest hash of a file.

    Args:
        filepath: Path to file
        algorithm: Hash algorithm name

    Returns:
        Hex digest string
    """
    h = hashlib.new(algorithm)
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def is_supported_file(filepath: Path) -> bool:
    """Return True if the file extension is supported for processing."""
    from app.config import SUPPORTED_IMAGE_EXTS, SUPPORTED_PDF_EXT
    ext = filepath.suffix.lower()
    return ext in SUPPORTED_IMAGE_EXTS or ext == SUPPORTED_PDF_EXT


# ─── Confidence Helpers ──────────────────────────────────────────────────────

def confidence_label(score: float) -> str:
    """Map a 0–1 confidence score to a human-readable label."""
    if score >= 0.85:
        return "High"
    elif score >= 0.60:
        return "Medium"
    elif score >= 0.35:
        return "Low"
    else:
        return "Very Low"


def average_confidence(scores: dict) -> float:
    """Compute mean confidence from a field→score mapping."""
    values = [v for v in scores.values() if isinstance(v, (int, float))]
    return round(sum(values) / len(values), 4) if values else 0.0

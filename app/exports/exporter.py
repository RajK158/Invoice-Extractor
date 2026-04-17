"""
app/exports/exporter.py - Export processed invoices to CSV and JSON formats
"""

import csv
import json
from io import StringIO, BytesIO
from pathlib import Path
from typing import List, Dict, Any

from app.config import CSV_EXPORT_FILENAME, JSON_EXPORT_FILENAME, EXPORT_DIR
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Canonical field order for export files
EXPORT_FIELDS = [
    "id", "filename", "invoice_number", "invoice_date", "due_date",
    "vendor_name", "buyer_name", "total_amount", "subtotal", "tax_amount",
    "tax_rate", "discount", "currency", "tax_id", "po_number",
    "address", "payment_terms", "detected_language",
    "ocr_engine", "ocr_confidence", "avg_field_confidence",
    "validation_status", "is_duplicate", "processed_at",
]


def to_csv_bytes(records: List[Dict[str, Any]]) -> bytes:
    """
    Serialize a list of invoice dicts to CSV bytes.

    Args:
        records: List of invoice record dicts

    Returns:
        UTF-8 encoded CSV bytes (including BOM for Excel compatibility)
    """
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=EXPORT_FIELDS,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for record in records:
        writer.writerow({f: record.get(f, "") for f in EXPORT_FIELDS})

    csv_str = output.getvalue()
    return b"\xef\xbb\xbf" + csv_str.encode("utf-8")  # UTF-8 BOM


def to_json_bytes(records: List[Dict[str, Any]]) -> bytes:
    """
    Serialize a list of invoice dicts to pretty-printed JSON bytes.

    Args:
        records: List of invoice record dicts

    Returns:
        UTF-8 JSON bytes
    """
    # Keep only export fields
    filtered = [
        {f: rec.get(f) for f in EXPORT_FIELDS} for rec in records
    ]
    return json.dumps(filtered, indent=2, default=str, ensure_ascii=False).encode("utf-8")


def export_to_disk(records: List[Dict[str, Any]], fmt: str = "both") -> Dict[str, Path]:
    """
    Write exports to the configured output directory.

    Args:
        records: Invoice records to export
        fmt:     'csv', 'json', or 'both'

    Returns:
        Dict mapping format name to output Path
    """
    paths = {}
    if fmt in ("csv", "both"):
        csv_path = EXPORT_DIR / CSV_EXPORT_FILENAME
        csv_path.write_bytes(to_csv_bytes(records))
        paths["csv"] = csv_path
        logger.info(f"Exported {len(records)} records → {csv_path}")

    if fmt in ("json", "both"):
        json_path = EXPORT_DIR / JSON_EXPORT_FILENAME
        json_path.write_bytes(to_json_bytes(records))
        paths["json"] = json_path
        logger.info(f"Exported {len(records)} records → {json_path}")

    return paths

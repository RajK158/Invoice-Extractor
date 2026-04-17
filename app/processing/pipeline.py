"""
app/processing/pipeline.py - End-to-end invoice processing orchestrator.

Connects: PDF/image loading → OCR → NLP extraction → validation → DB persist → indexing
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

from PIL import Image

from app.config import SUPPORTED_IMAGE_EXTS, SUPPORTED_PDF_EXT
from app.ocr.preprocessor import ImagePreprocessor
from app.ocr.engine import OCREngine
from app.ocr.pdf_converter import pdf_to_images
from app.nlp.language_detector import detect_language
from app.nlp.extractor import InvoiceExtractor
from app.validation.validator import InvoiceValidator
from app.db.database import save_invoice, get_session_factory
from app.retrieval.search import index_invoice
from app.utils.helpers import file_hash, average_confidence
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Module-level singletons (initialized once per worker)
_preprocessor = ImagePreprocessor()
_ocr_engine = OCREngine()
_extractor = InvoiceExtractor()
_validator = InvoiceValidator()


class InvoiceProcessingResult:
    """Complete result of processing a single invoice file."""

    def __init__(self):
        self.success: bool = False
        self.filename: str = ""
        self.raw_text: str = ""
        self.lang_code: str = "en"
        self.ocr_engine: str = ""
        self.ocr_confidence: float = 0.0
        self.fields: Dict[str, Any] = {}
        self.confidence: Dict[str, float] = {}
        self.validation: Dict[str, Any] = {}
        self.db_id: Optional[int] = None
        self.error: Optional[str] = None
        self.processing_time_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "filename": self.filename,
            "lang_code": self.lang_code,
            "ocr_engine": self.ocr_engine,
            "ocr_confidence": self.ocr_confidence,
            "fields": self.fields,
            "confidence": self.confidence,
            "validation": self.validation,
            "db_id": self.db_id,
            "error": self.error,
            "processing_time_ms": self.processing_time_ms,
        }


def process_file(filepath: Path) -> InvoiceProcessingResult:
    """
    Full pipeline for a single invoice file (image or PDF).

    Args:
        filepath: Path to the invoice file

    Returns:
        InvoiceProcessingResult with all extracted data
    """
    t0 = time.perf_counter()
    result = InvoiceProcessingResult()
    result.filename = filepath.name

    try:
        ext = filepath.suffix.lower()
        images: list[Image.Image] = []

        # ── Load ─────────────────────────────────────────────────────────────
        if ext == SUPPORTED_PDF_EXT:
            images = pdf_to_images(filepath)
        elif ext in SUPPORTED_IMAGE_EXTS:
            images = [Image.open(filepath).convert("RGB")]
        else:
            raise ValueError(f"Unsupported file type: {ext}")

        if not images:
            raise RuntimeError("No images could be loaded from file")

        # ── Preprocess & OCR (all pages → concatenate) ────────────────────
        all_text_parts = []
        total_conf = 0.0
        engine_used = "tesseract"

        for page_img in images:
            preprocessed = _preprocessor.preprocess(page_img)
            # Quick language hint from first page
            if not all_text_parts:
                raw_sample, _, _ = _ocr_engine.extract_text(preprocessed, "en")
                lang_code = detect_language(raw_sample)
                result.lang_code = lang_code
            else:
                lang_code = result.lang_code

            page_text, page_conf, engine_used = _ocr_engine.extract_text(preprocessed, lang_code)
            all_text_parts.append(page_text)
            total_conf += page_conf

        result.raw_text = "\n".join(all_text_parts)
        result.ocr_confidence = round(total_conf / len(images), 4)
        result.ocr_engine = engine_used

        # ── NLP Extraction ───────────────────────────────────────────────────
        extraction = _extractor.extract(result.raw_text, result.lang_code)
        result.fields = extraction["fields"]
        result.confidence = extraction["confidence"]

        # ── Validation ───────────────────────────────────────────────────────
        val_report = _validator.validate(result.fields)
        result.validation = val_report.to_dict()

        # ── Persist to DB ─────────────────────────────────────────────────────
        fhash = file_hash(filepath)
        avg_conf = average_confidence(result.confidence)

        record_data = {
            "filename": result.filename,
            "file_hash": fhash,
            "ocr_engine": result.ocr_engine,
            "ocr_confidence": result.ocr_confidence,
            "avg_field_confidence": avg_conf,
            "raw_text": result.raw_text[:50000],  # Limit stored text size
            "validation_status": result.validation["status"],
            "validation_report": json.dumps(result.validation),
            "confidence_scores": json.dumps(result.confidence),
            "is_duplicate": result.validation.get("is_duplicate", False),
            **result.fields,
        }

        factory = get_session_factory()
        db = factory()
        try:
            saved = save_invoice(record_data, db)
            result.db_id = saved.id

            # ── Index for fast retrieval ─────────────────────────────────────
            idx_data = saved.to_dict()
            idx_data["raw_text"] = result.raw_text[:20000]
            index_invoice(idx_data)
        finally:
            db.close()

        result.success = True
        logger.info(f"Processed {filepath.name} in {(time.perf_counter()-t0)*1000:.0f}ms | {result.validation['status']}")

    except Exception as e:
        result.error = str(e)
        logger.error(f"Pipeline error for {filepath.name}: {e}", exc_info=True)

    result.processing_time_ms = round((time.perf_counter() - t0) * 1000, 2)
    return result


def process_bytes(file_bytes: bytes, filename: str, suffix: str) -> InvoiceProcessingResult:
    """
    Process an invoice from in-memory bytes (used by Streamlit uploader).

    Args:
        file_bytes: Raw file bytes
        filename:   Original filename (for display/logging)
        suffix:     File extension including dot (e.g., '.pdf', '.jpg')

    Returns:
        InvoiceProcessingResult
    """
    import tempfile, os

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    try:
        result = process_file(tmp_path)
        result.filename = filename  # Use original name
        return result
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def process_batch(folder: Path, max_workers: int = 4) -> list:
    """
    Batch-process all supported files in a folder using a thread pool.

    Args:
        folder:      Directory containing invoice files
        max_workers: Thread pool size

    Returns:
        List of InvoiceProcessingResult objects
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    files = [
        f for f in folder.iterdir()
        if f.is_file() and (f.suffix.lower() in SUPPORTED_IMAGE_EXTS or f.suffix.lower() == SUPPORTED_PDF_EXT)
    ]

    if not files:
        logger.warning(f"No supported files found in {folder}")
        return []

    logger.info(f"Batch processing {len(files)} files with {max_workers} workers")
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_file, f): f for f in files}
        for future in as_completed(futures):
            filepath = futures[future]
            try:
                res = future.result()
                results.append(res)
            except Exception as e:
                logger.error(f"Batch error for {filepath.name}: {e}")

    logger.info(f"Batch complete: {sum(1 for r in results if r.success)}/{len(files)} succeeded")
    return results

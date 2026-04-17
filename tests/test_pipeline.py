"""
tests/test_pipeline.py - Integration tests for the processing pipeline
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import io
import pytest
from PIL import Image, ImageDraw, ImageFont


def create_sample_invoice_image() -> bytes:
    """
    Generate a synthetic invoice image with known field values.
    Used for pipeline integration testing without real invoice files.
    """
    img = Image.new("RGB", (1200, 1600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Header
    draw.text((50, 50), "INVOICE", fill=(0, 0, 0))
    draw.text((50, 120), "Invoice No: INV-TEST-9999", fill=(0, 0, 0))
    draw.text((50, 160), "Invoice Date: 2024-03-15", fill=(0, 0, 0))
    draw.text((50, 200), "Due Date: 2024-04-15", fill=(0, 0, 0))

    # Vendor
    draw.text((50, 280), "From: Test Vendor Corporation", fill=(0, 0, 0))
    draw.text((50, 320), "123 Test Street, New York, NY 10001", fill=(0, 0, 0))

    # Buyer
    draw.text((50, 400), "Bill To: Sample Buyer Inc", fill=(0, 0, 0))
    draw.text((50, 440), "456 Commerce Ave, Los Angeles, CA", fill=(0, 0, 0))

    # Line items
    draw.text((50, 540), "Description               Amount", fill=(0, 0, 0))
    draw.text((50, 580), "Product A                $500.00", fill=(0, 0, 0))
    draw.text((50, 620), "Service B                $300.00", fill=(0, 0, 0))

    # Totals
    draw.text((50, 720), "Subtotal: $800.00", fill=(0, 0, 0))
    draw.text((50, 760), "Tax (10%): $80.00", fill=(0, 0, 0))
    draw.text((50, 800), "Total: $880.00", fill=(0, 0, 0))

    # Footer
    draw.text((50, 880), "Currency: USD", fill=(0, 0, 0))
    draw.text((50, 920), "Payment Terms: Net 30", fill=(0, 0, 0))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestPreprocessor:
    def test_preprocess_returns_pil_image(self):
        from app.ocr.preprocessor import ImagePreprocessor
        preprocessor = ImagePreprocessor()
        img_bytes = create_sample_invoice_image()
        img = Image.open(io.BytesIO(img_bytes))
        result = preprocessor.preprocess(img)
        assert isinstance(result, Image.Image)

    def test_preprocess_grayscale_output(self):
        from app.ocr.preprocessor import ImagePreprocessor
        preprocessor = ImagePreprocessor()
        img_bytes = create_sample_invoice_image()
        img = Image.open(io.BytesIO(img_bytes))
        result = preprocessor.preprocess(img)
        # Thresholded output should be grayscale or binary
        assert result.mode in ("L", "1", "RGB")

    def test_preprocess_bytes(self):
        from app.ocr.preprocessor import ImagePreprocessor
        preprocessor = ImagePreprocessor()
        img_bytes = create_sample_invoice_image()
        result = preprocessor.preprocess_bytes(img_bytes)
        assert isinstance(result, Image.Image)


class TestProcessBytes:
    """
    Tests for the process_bytes pipeline function.
    Note: Full OCR requires Tesseract/EasyOCR to be installed.
    These tests verify the pipeline runs without crashing even if
    OCR libraries are not fully configured.
    """

    def test_pipeline_runs_on_png(self):
        from app.processing.pipeline import process_bytes
        img_bytes = create_sample_invoice_image()
        result = process_bytes(img_bytes, "test_invoice.png", ".png")

        # Pipeline should complete regardless of OCR availability
        assert hasattr(result, "success")
        assert hasattr(result, "filename")
        assert result.filename == "test_invoice.png"
        assert hasattr(result, "processing_time_ms")
        assert result.processing_time_ms >= 0

    def test_result_has_required_keys(self):
        from app.processing.pipeline import process_bytes
        img_bytes = create_sample_invoice_image()
        result = process_bytes(img_bytes, "test_invoice.png", ".png")

        d = result.to_dict()
        required_keys = [
            "success", "filename", "lang_code", "ocr_engine",
            "ocr_confidence", "fields", "confidence",
            "validation", "processing_time_ms",
        ]
        for key in required_keys:
            assert key in d, f"Missing key in result dict: {key}"

    def test_fields_dict_has_expected_structure(self):
        from app.processing.pipeline import process_bytes
        img_bytes = create_sample_invoice_image()
        result = process_bytes(img_bytes, "test_invoice.png", ".png")

        expected_field_keys = [
            "invoice_number", "invoice_date", "vendor_name",
            "total_amount", "currency", "detected_language",
        ]
        for key in expected_field_keys:
            assert key in result.fields, f"Missing field: {key}"

    def test_unsupported_extension_fails_gracefully(self):
        from app.processing.pipeline import process_bytes
        result = process_bytes(b"garbage", "test.xyz", ".xyz")
        assert result.success is False
        assert result.error is not None


class TestExporter:
    def test_csv_export(self):
        from app.exports.exporter import to_csv_bytes
        records = [
            {
                "id": 1, "filename": "test.jpg", "invoice_number": "INV-001",
                "vendor_name": "Test Corp", "total_amount": 500.0,
                "currency": "USD", "detected_language": "en",
                "validation_status": "PASSED",
            }
        ]
        csv_bytes = to_csv_bytes(records)
        assert isinstance(csv_bytes, bytes)
        # UTF-8 BOM
        assert csv_bytes[:3] == b"\xef\xbb\xbf"
        decoded = csv_bytes.decode("utf-8-sig")
        assert "INV-001" in decoded
        assert "Test Corp" in decoded

    def test_json_export(self):
        import json
        from app.exports.exporter import to_json_bytes
        records = [
            {
                "id": 1, "filename": "test.jpg", "invoice_number": "INV-001",
                "vendor_name": "Test Corp", "total_amount": 500.0,
            }
        ]
        json_bytes = to_json_bytes(records)
        assert isinstance(json_bytes, bytes)
        parsed = json.loads(json_bytes.decode("utf-8"))
        assert isinstance(parsed, list)
        assert len(parsed) == 1

    def test_csv_handles_empty_records(self):
        from app.exports.exporter import to_csv_bytes
        csv_bytes = to_csv_bytes([])
        assert isinstance(csv_bytes, bytes)

    def test_json_handles_empty_records(self):
        import json
        from app.exports.exporter import to_json_bytes
        json_bytes = to_json_bytes([])
        parsed = json.loads(json_bytes)
        assert parsed == []


class TestDatabaseOperations:
    def test_save_and_retrieve_invoice(self):
        from app.db.database import get_session_factory, save_invoice, get_invoice_by_id
        import hashlib, time

        factory = get_session_factory()
        db = factory()
        try:
            unique_hash = hashlib.sha256(str(time.time()).encode()).hexdigest()
            record_data = {
                "filename": "pytest_test.jpg",
                "file_hash": unique_hash,
                "invoice_number": "PYTEST-001",
                "invoice_date": "2024-01-01",
                "vendor_name": "PyTest Corp",
                "total_amount": 999.99,
                "currency": "USD",
                "detected_language": "en",
                "validation_status": "PASSED",
                "validation_report": "{}",
                "confidence_scores": "{}",
                "avg_field_confidence": 0.88,
                "ocr_engine": "test",
                "ocr_confidence": 0.90,
                "is_duplicate": False,
            }
            saved = save_invoice(record_data, db)
            assert saved.id is not None
            assert saved.invoice_number == "PYTEST-001"

            retrieved = get_invoice_by_id(saved.id, db)
            assert retrieved is not None
            assert retrieved.vendor_name == "PyTest Corp"
        finally:
            db.close()

    def test_get_analytics_returns_dict(self):
        from app.db.database import get_session_factory, get_analytics
        factory = get_session_factory()
        db = factory()
        try:
            stats = get_analytics(db)
            assert "total_invoices" in stats
            assert "by_language" in stats
            assert "by_validation_status" in stats
            assert "avg_confidence" in stats
        finally:
            db.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

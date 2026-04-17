"""
app/ocr/engine.py - OCR pipeline with Tesseract primary and EasyOCR fallback
"""

import io
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image

from app.config import (
    TESSERACT_CMD, TESSERACT_LANGS, EASYOCR_LANGS_MAP, OCR_CONFIDENCE_THRESHOLD
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Lazy imports to avoid loading heavy models at startup
_tesseract_available = False
_easyocr_available = False
_easyocr_readers: dict = {}


def _init_tesseract() -> bool:
    global _tesseract_available
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
        pytesseract.get_tesseract_version()
        _tesseract_available = True
        logger.info("Tesseract OCR initialized successfully")
    except Exception as e:
        logger.warning(f"Tesseract not available: {e}")
        _tesseract_available = False
    return _tesseract_available


def _init_easyocr(lang_code: str = "unknown") -> Optional[object]:
    """Load or retrieve cached EasyOCR reader for given language."""
    global _easyocr_available
    try:
        import easyocr
        langs = EASYOCR_LANGS_MAP.get(lang_code, EASYOCR_LANGS_MAP["unknown"])
        key = ",".join(langs)
        if key not in _easyocr_readers:
            logger.info(f"Loading EasyOCR reader for langs: {langs}")
            _easyocr_readers[key] = easyocr.Reader(langs, gpu=False, verbose=False)
        _easyocr_available = True
        return _easyocr_readers[key]
    except Exception as e:
        logger.warning(f"EasyOCR not available: {e}")
        _easyocr_available = False
        return None


class OCREngine:
    """
    Dual-engine OCR system using Tesseract as primary and EasyOCR as fallback.

    Strategy:
    1. Run Tesseract with the detected language hint.
    2. If Tesseract confidence < threshold or output too short, fall back to EasyOCR.
    3. Return the higher-quality result with a confidence score.
    """

    def __init__(self):
        _init_tesseract()

    # ─── Public API ──────────────────────────────────────────────────────────

    def extract_text(
        self, image: Image.Image, lang_code: str = "en"
    ) -> Tuple[str, float, str]:
        """
        Run OCR on a preprocessed PIL Image.

        Args:
            image:     Preprocessed PIL Image
            lang_code: ISO 639-1 language code (e.g., 'en', 'hi', 'ar')

        Returns:
            (extracted_text, confidence, engine_used)
        """
        text_tess, conf_tess = self._run_tesseract(image, lang_code)
        engine_used = "tesseract"

        if conf_tess < OCR_CONFIDENCE_THRESHOLD or len(text_tess.strip()) < 20:
            logger.debug(
                f"Tesseract low confidence ({conf_tess:.1f}), trying EasyOCR"
            )
            text_easy, conf_easy = self._run_easyocr(image, lang_code)
            if len(text_easy.strip()) > len(text_tess.strip()):
                return text_easy, conf_easy / 100.0, "easyocr"

        return text_tess, conf_tess / 100.0, engine_used

    # ─── Internal Engines ────────────────────────────────────────────────────

    def _run_tesseract(self, image: Image.Image, lang_code: str) -> Tuple[str, float]:
        """Run Tesseract OCR and return (text, mean_confidence)."""
        if not _tesseract_available:
            return "", 0.0
        try:
            import pytesseract
            tess_lang = self._map_lang_tesseract(lang_code)
            custom_cfg = f"--oem 3 --psm 6 -l {tess_lang}"

            data = pytesseract.image_to_data(
                image, config=custom_cfg, output_type=pytesseract.Output.DICT
            )
            text_parts = []
            confidences = []
            for i, word in enumerate(data["text"]):
                conf = data["conf"][i]
                if word.strip() and conf > 0:
                    text_parts.append(word)
                    confidences.append(conf)

            text = " ".join(text_parts)
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
            logger.debug(f"Tesseract: {len(text)} chars, conf={avg_conf:.1f}")
            return text, avg_conf
        except Exception as e:
            logger.error(f"Tesseract error: {e}")
            return "", 0.0

    def _run_easyocr(self, image: Image.Image, lang_code: str) -> Tuple[str, float]:
        """Run EasyOCR and return (text, mean_confidence*100)."""
        reader = _init_easyocr(lang_code)
        if reader is None:
            return "", 0.0
        try:
            import numpy as np
            img_np = np.array(image)
            results = reader.readtext(img_np, detail=1, paragraph=False)
            text_parts = []
            confidences = []
            for (_, text, conf) in results:
                if text.strip():
                    text_parts.append(text)
                    confidences.append(conf * 100)
            text = " ".join(text_parts)
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
            logger.debug(f"EasyOCR: {len(text)} chars, conf={avg_conf:.1f}")
            return text, avg_conf
        except Exception as e:
            logger.error(f"EasyOCR error: {e}")
            return "", 0.0

    def _map_lang_tesseract(self, lang_code: str) -> str:
        """Map ISO 639-1 code to Tesseract lang string."""
        mapping = {
            "en": "eng", "hi": "hin+eng", "ar": "ara+eng",
            "fr": "fra+eng", "de": "deu+eng", "es": "spa+eng",
            "zh": "chi_sim+eng", "ja": "jpn+eng", "pt": "por+eng",
        }
        return mapping.get(lang_code, "eng")

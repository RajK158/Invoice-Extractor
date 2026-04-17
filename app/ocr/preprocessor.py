"""
app/ocr/preprocessor.py - Image preprocessing for optimal OCR accuracy
"""

import io
import math
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from app.config import (
    PREPROCESS_RESIZE_WIDTH,
    PREPROCESS_DENOISE_STRENGTH,
    PREPROCESS_THRESHOLD_BLOCK,
    PREPROCESS_THRESHOLD_C,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ImagePreprocessor:
    """
    Prepares invoice images for OCR by applying a configurable pipeline of
    enhancement steps: resize, grayscale, denoise, deskew, and threshold.
    """

    def __init__(
        self,
        target_width: int = PREPROCESS_RESIZE_WIDTH,
        denoise_strength: int = PREPROCESS_DENOISE_STRENGTH,
    ):
        self.target_width = target_width
        self.denoise_strength = denoise_strength

    # ─── Public API ──────────────────────────────────────────────────────────

    def preprocess(self, image: Image.Image) -> Image.Image:
        """
        Full preprocessing pipeline.

        Args:
            image: PIL Image (any mode)

        Returns:
            Preprocessed PIL Image ready for OCR
        """
        img_cv = self._pil_to_cv(image)
        img_cv = self._resize(img_cv)
        img_cv = self._to_grayscale(img_cv)
        img_cv = self._denoise(img_cv)
        img_cv = self._deskew(img_cv)
        img_cv = self._threshold(img_cv)
        return self._cv_to_pil(img_cv)

    def preprocess_bytes(self, image_bytes: bytes) -> Image.Image:
        """Preprocess from raw bytes."""
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return self.preprocess(image)

    def preprocess_path(self, filepath: Path) -> Image.Image:
        """Preprocess from file path."""
        image = Image.open(filepath).convert("RGB")
        return self.preprocess(image)

    # ─── Pipeline Steps ──────────────────────────────────────────────────────

    def _pil_to_cv(self, image: Image.Image) -> np.ndarray:
        return cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)

    def _cv_to_pil(self, img: np.ndarray) -> Image.Image:
        if len(img.shape) == 2:  # Grayscale
            return Image.fromarray(img)
        return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

    def _resize(self, img: np.ndarray) -> np.ndarray:
        """Upscale small images to improve OCR accuracy."""
        h, w = img.shape[:2]
        if w < self.target_width:
            scale = self.target_width / w
            new_w = int(w * scale)
            new_h = int(h * scale)
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
            logger.debug(f"Resized image: {w}x{h} → {new_w}x{new_h}")
        return img

    def _to_grayscale(self, img: np.ndarray) -> np.ndarray:
        if len(img.shape) == 3:
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return img

    def _denoise(self, img: np.ndarray) -> np.ndarray:
        """Apply fast non-local means denoising."""
        return cv2.fastNlMeansDenoising(img, h=self.denoise_strength)

    def _threshold(self, img: np.ndarray) -> np.ndarray:
        """
        Adaptive Gaussian thresholding → binarized image.
        Handles uneven illumination common in scanned invoices.
        """
        return cv2.adaptiveThreshold(
            img,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            PREPROCESS_THRESHOLD_BLOCK,
            PREPROCESS_THRESHOLD_C,
        )

    def _deskew(self, img: np.ndarray) -> np.ndarray:
        """
        Correct image skew using Hough line transform approach.
        Skew correction improves OCR word segmentation significantly.
        """
        try:
            angle = self._detect_skew(img)
            if abs(angle) > 0.5:  # Only correct meaningful skew
                img = self._rotate(img, angle)
                logger.debug(f"Deskewed image by {angle:.2f}°")
        except Exception as e:
            logger.warning(f"Deskew failed (non-critical): {e}")
        return img

    def _detect_skew(self, img: np.ndarray) -> float:
        """Detect skew angle via minAreaRect on edge points."""
        edges = cv2.Canny(img, 50, 150, apertureSize=3)
        coords = np.column_stack(np.where(edges > 0))
        if len(coords) < 10:
            return 0.0
        rect = cv2.minAreaRect(coords)
        angle = rect[-1]
        # minAreaRect returns angles in [-90, 0]; normalize
        if angle < -45:
            angle += 90
        return angle

    def _rotate(self, img: np.ndarray, angle: float) -> np.ndarray:
        """Rotate image by given angle, keeping full image in frame."""
        h, w = img.shape[:2]
        cx, cy = w // 2, h // 2
        M = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)

        # Calculate new bounding dimensions
        cos_a = abs(M[0, 0])
        sin_a = abs(M[0, 1])
        new_w = int(h * sin_a + w * cos_a)
        new_h = int(h * cos_a + w * sin_a)

        M[0, 2] += (new_w / 2) - cx
        M[1, 2] += (new_h / 2) - cy
        return cv2.warpAffine(img, M, (new_w, new_h), flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REPLICATE)

"""
app/ocr/pdf_converter.py - Convert PDF pages to PIL Images for OCR
"""

from pathlib import Path
from typing import List, Optional

from PIL import Image

from app.config import OCR_DPI
from app.utils.logger import get_logger

logger = get_logger(__name__)


def pdf_to_images(pdf_path: Path, dpi: int = OCR_DPI) -> List[Image.Image]:
    """
    Convert each page of a PDF to a high-resolution PIL Image.

    Tries pdf2image (poppler) first, falls back to PyMuPDF (fitz).

    Args:
        pdf_path: Path to the PDF file
        dpi:      Resolution for rendering (default 300 DPI for good OCR quality)

    Returns:
        List of PIL Images, one per page
    """
    images = _try_pdf2image(pdf_path, dpi)
    if not images:
        images = _try_pymupdf(pdf_path, dpi)
    if not images:
        logger.error(f"Could not convert PDF to images: {pdf_path}")
    return images


def _try_pdf2image(pdf_path: Path, dpi: int) -> List[Image.Image]:
    """Use pdf2image + poppler to render PDF pages."""
    try:
        from pdf2image import convert_from_path
        images = convert_from_path(str(pdf_path), dpi=dpi)
        logger.info(f"pdf2image: {len(images)} pages from {pdf_path.name}")
        return images
    except ImportError:
        logger.debug("pdf2image not installed, trying PyMuPDF")
        return []
    except Exception as e:
        logger.warning(f"pdf2image failed: {e}")
        return []


def _try_pymupdf(pdf_path: Path, dpi: int) -> List[Image.Image]:
    """Use PyMuPDF (fitz) to render PDF pages."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(pdf_path))
        images = []
        zoom = dpi / 72  # 72 DPI is fitz default
        mat = fitz.Matrix(zoom, zoom)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(matrix=mat)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)
        doc.close()
        logger.info(f"PyMuPDF: {len(images)} pages from {pdf_path.name}")
        return images
    except ImportError:
        logger.warning("Neither pdf2image nor PyMuPDF found. Cannot process PDFs.")
        return []
    except Exception as e:
        logger.error(f"PyMuPDF failed: {e}")
        return []

"""
app/nlp/language_detector.py - Language detection for multilingual invoice support
"""

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Supported language codes and display names
SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "ar": "Arabic",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "zh": "Chinese (Simplified)",
    "ja": "Japanese",
    "pt": "Portuguese",
    "it": "Italian",
    "ko": "Korean",
    "ru": "Russian",
    "tr": "Turkish",
    "nl": "Dutch",
}


def detect_language(text: str) -> str:
    """
    Detect the primary language of invoice text.

    Args:
        text: Raw OCR text

    Returns:
        ISO 639-1 language code (e.g., 'en', 'hi', 'ar')
        Falls back to 'en' if detection fails or language unsupported.
    """
    if not text or len(text.strip()) < 20:
        logger.debug("Text too short for language detection, defaulting to 'en'")
        return "en"

    # Try langdetect
    lang = _detect_langdetect(text)
    if lang:
        return lang

    # Fallback: script-based heuristic
    lang = _detect_by_script(text)
    logger.debug(f"Script-based language detection: {lang}")
    return lang


def _detect_langdetect(text: str) -> str:
    """Use langdetect library for probabilistic language identification."""
    try:
        from langdetect import detect, LangDetectException
        lang = detect(text[:2000])  # Limit for speed
        # Map to supported set
        code = lang.split("-")[0].lower()
        if code in SUPPORTED_LANGUAGES:
            logger.debug(f"langdetect detected: {code} ({SUPPORTED_LANGUAGES[code]})")
            return code
        logger.debug(f"Detected unsupported lang {code}, defaulting to 'en'")
        return "en"
    except ImportError:
        logger.debug("langdetect not installed")
        return ""
    except Exception as e:
        logger.debug(f"langdetect failed: {e}")
        return ""


def _detect_by_script(text: str) -> str:
    """
    Heuristic script-based detection using Unicode ranges.
    Used when langdetect is unavailable or fails.
    """
    import unicodedata

    script_counts: dict = {}
    for ch in text:
        try:
            name = unicodedata.name(ch, "")
        except Exception:
            continue
        if "ARABIC" in name:
            script_counts["ar"] = script_counts.get("ar", 0) + 1
        elif "DEVANAGARI" in name:
            script_counts["hi"] = script_counts.get("hi", 0) + 1
        elif "CJK" in name or "HIRAGANA" in name or "KATAKANA" in name:
            script_counts["zh"] = script_counts.get("zh", 0) + 1
        elif "HANGUL" in name:
            script_counts["ko"] = script_counts.get("ko", 0) + 1
        elif "CYRILLIC" in name:
            script_counts["ru"] = script_counts.get("ru", 0) + 1

    if script_counts:
        dominant = max(script_counts, key=script_counts.get)
        if script_counts[dominant] > 5:
            return dominant

    return "en"


def get_language_name(lang_code: str) -> str:
    """Return human-readable language name for a code."""
    return SUPPORTED_LANGUAGES.get(lang_code, f"Unknown ({lang_code})")

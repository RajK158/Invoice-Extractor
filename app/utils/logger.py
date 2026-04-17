"""
app/utils/logger.py - Centralized logging configuration
"""

import logging
import sys
from pathlib import Path

from app.config import LOG_LEVEL, LOG_FORMAT, LOG_FILE


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger with file + stream handlers.

    Args:
        name: Logger name (typically __name__ of calling module)

    Returns:
        Configured logging.Logger instance
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # Already configured

    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    formatter = logging.Formatter(LOG_FORMAT)

    # Stream handler (stdout)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)
    logger.addHandler(sh)

    # File handler
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except Exception:
        pass  # Non-critical; stream handler is sufficient

    logger.propagate = False
    return logger

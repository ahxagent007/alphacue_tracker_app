# =============================================================================
# utils/logger.py — Centralised logging setup
#
# Usage:
#   from utils.logger import get_logger
#   log = get_logger(__name__)
#   log.info("Something happened")
# =============================================================================

import logging
import logging.handlers
import os
import sys

# Import config lazily to avoid circular imports
from config import LOG_FILE, LOG_LEVEL, LOG_MAX_BYTES, LOG_BACKUP_COUNT

# ── ensure the logs directory exists before creating handlers ───────────────
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# ── map string level to logging constant ────────────────────────────────────
_LEVEL_MAP = {
    "DEBUG":    logging.DEBUG,
    "INFO":     logging.INFO,
    "WARNING":  logging.WARNING,
    "ERROR":    logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

_numeric_level = _LEVEL_MAP.get(LOG_LEVEL.upper(), logging.DEBUG)

# ── shared formatter ─────────────────────────────────────────────────────────
_FORMATTER = logging.Formatter(
    fmt="%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ── root logger — configure once ─────────────────────────────────────────────
def _configure_root_logger() -> None:
    """Attach handlers to the root logger exactly once."""
    root = logging.getLogger()

    # Guard: skip if already configured (e.g. module reloaded in tests)
    if root.handlers:
        return

    root.setLevel(_numeric_level)

    # 1. Rotating file handler — keeps log directory tidy
    file_handler = logging.handlers.RotatingFileHandler(
        filename    = LOG_FILE,
        maxBytes    = LOG_MAX_BYTES,
        backupCount = LOG_BACKUP_COUNT,
        encoding    = "utf-8",
    )
    file_handler.setFormatter(_FORMATTER)
    root.addHandler(file_handler)

    # 2. Console handler — visible when running interactively / debugging
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(_FORMATTER)
    root.addHandler(console_handler)


_configure_root_logger()


# ── public helper ─────────────────────────────────────────────────────────────
def get_logger(name: str) -> logging.Logger:
    """Return a named child logger.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A :class:`logging.Logger` instance that inherits handlers from root.
    """
    return logging.getLogger(name)

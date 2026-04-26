# =============================================================================
# capture/screenshot.py — Full-desktop screenshot capture
#
# Usage:
#   from capture.screenshot import take_screenshot
#   path = take_screenshot()   # returns absolute path to saved file, or None
# =============================================================================

import os
from datetime import datetime

import pyautogui
from PIL import Image

from config import TEMP_IMAGE_DIR, SCREENSHOT_FORMAT
from utils.logger import get_logger

log = get_logger(__name__)


def _build_filename() -> str:
    """Generate a timestamped filename for the screenshot.

    Returns:
        e.g. ``screenshot_20260426_145301.jpg``
    """
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = SCREENSHOT_FORMAT.lower().replace("jpeg", "jpg")
    return f"screenshot_{ts}.{ext}"


def take_screenshot() -> str | None:
    """Capture the full desktop and save it to TEMP_IMAGE_DIR.

    Steps
    -----
    1. Ensure the staging directory exists.
    2. Capture all monitors via pyautogui (returns a PIL Image).
    3. Convert to RGB so JPEG encoding never chokes on alpha channels.
    4. Save to disk.

    Returns:
        Absolute path to the saved file on success, ``None`` on failure.
    """
    os.makedirs(TEMP_IMAGE_DIR, exist_ok=True)

    filepath = os.path.join(TEMP_IMAGE_DIR, _build_filename())

    try:
        log.debug("Capturing screenshot…")

        # pyautogui.screenshot() returns a PIL Image
        img: Image.Image = pyautogui.screenshot()

        # Drop alpha channel — JPEG does not support transparency
        if img.mode != "RGB":
            img = img.convert("RGB")

        img.save(filepath, format=SCREENSHOT_FORMAT)

        size_kb = os.path.getsize(filepath) / 1024
        log.info("Screenshot saved → %s  (%.1f KB)", filepath, size_kb)
        return filepath

    except Exception:
        log.exception("Screenshot capture failed")
        return None

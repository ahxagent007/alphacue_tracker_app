# =============================================================================
# capture/webcam.py — Single-frame webcam capture via OpenCV
#
# Usage:
#   from capture.webcam import take_webcam_photo
#   path = take_webcam_photo()   # returns absolute path, or None on failure
# =============================================================================

import os
from datetime import datetime

import cv2
from PIL import Image

from config import TEMP_IMAGE_DIR, WEBCAM_FORMAT
from utils.logger import get_logger

log = get_logger(__name__)

# Camera index — 0 = default/built-in webcam.
# Change to 1, 2, … if you have multiple cameras and want a different one.
CAMERA_INDEX = 0

# How many frames to discard before saving.
# Most webcams need a few frames to auto-adjust exposure / white-balance.
WARMUP_FRAMES = 3


def _build_filename() -> str:
    """Generate a timestamped filename for the webcam image.

    Returns:
        e.g. ``webcam_20260426_145301.jpg``
    """
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = WEBCAM_FORMAT.lower().replace("jpeg", "jpg")
    return f"webcam_{ts}.{ext}"


def take_webcam_photo() -> str | None:
    """Capture a single frame from the default webcam and save it.

    Steps
    -----
    1. Open the camera with ``cv2.VideoCapture``.
    2. Verify the camera opened successfully.
    3. Discard ``WARMUP_FRAMES`` frames so auto-exposure can settle.
    4. Read the target frame (BGR from OpenCV → RGB for PIL).
    5. Save as JPEG to TEMP_IMAGE_DIR.
    6. Release the camera unconditionally (even on error).

    Returns:
        Absolute path to the saved file on success, ``None`` on failure.
    """
    os.makedirs(TEMP_IMAGE_DIR, exist_ok=True)

    filepath = os.path.join(TEMP_IMAGE_DIR, _build_filename())
    cap      = None  # declared outside try so finally can always release

    try:
        log.debug("Opening webcam (index=%d)…", CAMERA_INDEX)
        cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)  # CAP_DSHOW = faster open on Windows

        if not cap.isOpened():
            log.error("Could not open webcam at index %d", CAMERA_INDEX)
            return None

        # Discard warm-up frames so the image isn't dark / colour-shifted
        for i in range(WARMUP_FRAMES):
            ret, _ = cap.read()
            if not ret:
                log.warning("Warm-up frame %d/%d failed — continuing", i + 1, WARMUP_FRAMES)

        # Capture the actual frame
        ret, frame = cap.read()
        if not ret or frame is None:
            log.error("Failed to read frame from webcam")
            return None

        log.debug("Frame captured: %dx%d px", frame.shape[1], frame.shape[0])

        # OpenCV uses BGR colour order; PIL/JPEG expects RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img       = Image.fromarray(frame_rgb)

        img.save(filepath, format=WEBCAM_FORMAT)

        size_kb = os.path.getsize(filepath) / 1024
        log.info("Webcam photo saved → %s  (%.1f KB)", filepath, size_kb)
        return filepath

    except Exception:
        log.exception("Webcam capture failed")
        return None

    finally:
        # ALWAYS release the camera — even if an exception occurred.
        # Failing to release leaves the camera LED on and blocks other apps.
        if cap is not None and cap.isOpened():
            cap.release()
            log.debug("Webcam released.")

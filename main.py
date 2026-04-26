# =============================================================================
# main.py — Tracker app entry point
#
# Runs an infinite loop that every CAPTURE_INTERVAL_SECONDS:
#   1. Takes a screenshot
#   2. Captures a webcam photo
#   3. Compresses both images
#   4. Uploads both to Google Drive
#   5. Deletes local files after successful upload
#
# Run directly:
#   python main.py
#
# Or as a compiled .exe (see Milestone 7 for PyInstaller instructions).
# =============================================================================

import os
import sys
import time
import signal

# Ensure the app root is always on sys.path regardless of how it's launched
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CAPTURE_INTERVAL_SECONDS, UPLOAD_MAX_RETRIES, UPLOAD_RETRY_DELAY
from capture.screenshot   import take_screenshot
from capture.webcam       import take_webcam_photo
from utils.compressor     import compress_image
from uploader.drive_uploader import upload_file
from utils.logger         import get_logger

log = get_logger("main")

# ---------------------------------------------------------------------------
# Graceful shutdown support
# ---------------------------------------------------------------------------

_shutdown_requested = False

def _handle_signal(signum, _frame) -> None:
    """Mark shutdown on SIGINT / SIGTERM so the loop exits cleanly."""
    global _shutdown_requested
    log.info("Shutdown signal received (%s) — finishing current cycle then exiting.", signum)
    _shutdown_requested = True

signal.signal(signal.SIGINT,  _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


# ---------------------------------------------------------------------------
# Per-file pipeline helpers
# ---------------------------------------------------------------------------

def _compress(filepath: str, label: str) -> str | None:
    """Compress *filepath* in-place.  Returns path on success, None on failure."""
    result = compress_image(filepath, keep_original=False)
    if result is None:
        log.error("[%s] Compression failed — skipping upload.", label)
    return result


def _upload_with_retry(filepath: str, label: str) -> bool:
    """Attempt to upload *filepath*, retrying up to UPLOAD_MAX_RETRIES times.

    Returns True only when the upload succeeds.
    """
    for attempt in range(1, UPLOAD_MAX_RETRIES + 1):
        log.debug("[%s] Upload attempt %d / %d…", label, attempt, UPLOAD_MAX_RETRIES)
        if upload_file(filepath):
            return True
        if attempt < UPLOAD_MAX_RETRIES:
            log.warning(
                "[%s] Upload failed (attempt %d) — retrying in %ds…",
                label, attempt, UPLOAD_RETRY_DELAY,
            )
            time.sleep(UPLOAD_RETRY_DELAY)

    log.error("[%s] All %d upload attempts failed.", label, UPLOAD_MAX_RETRIES)
    return False


def _delete_local(filepath: str, label: str) -> None:
    """Delete *filepath* from disk, logging the outcome."""
    try:
        os.remove(filepath)
        log.debug("[%s] Local file deleted: %s", label, filepath)
    except OSError:
        log.exception("[%s] Could not delete local file: %s", label, filepath)


# ---------------------------------------------------------------------------
# Single capture-compress-upload-delete cycle for one file
# ---------------------------------------------------------------------------

def _process_file(filepath: str | None, label: str) -> None:
    """Run the full pipeline for a single captured image.

    Args:
        filepath: Path returned by a capture function, or None if capture failed.
        label:    Human-readable label used in log messages ("screenshot" / "webcam").
    """
    if filepath is None:
        log.error("[%s] Capture failed — nothing to process.", label)
        return

    # Step 1 — compress
    filepath = _compress(filepath, label)
    if filepath is None:
        return

    # Step 2 — upload (with retry)
    uploaded = _upload_with_retry(filepath, label)

    # Step 3 — delete local file
    #   Always delete, even on upload failure, to prevent temp_images filling up.
    #   Failed uploads are logged; the log is the audit trail.
    _delete_local(filepath, label)

    if uploaded:
        log.info("[%s] ✓ Cycle complete.", label)
    else:
        log.warning("[%s] ✗ Cycle complete with upload failure (file deleted locally).", label)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run() -> None:
    """Start the infinite capture loop.  Exits cleanly on SIGINT / SIGTERM."""
    log.info("=" * 60)
    log.info("Tracker started  (interval = %ds)", CAPTURE_INTERVAL_SECONDS)
    log.info("=" * 60)

    cycle = 0

    while not _shutdown_requested:
        cycle += 1
        log.info("─── Cycle %d ───────────────────────────────────────────", cycle)

        # -- Screenshot pipeline --
        _process_file(take_screenshot(), "screenshot")

        # -- Webcam pipeline --
        _process_file(take_webcam_photo(), "webcam")

        log.info("Cycle %d done — sleeping %ds.", cycle, CAPTURE_INTERVAL_SECONDS)

        # Sleep in 1-second ticks so SIGINT is handled promptly
        for _ in range(CAPTURE_INTERVAL_SECONDS):
            if _shutdown_requested:
                break
            time.sleep(1)

    log.info("Tracker stopped cleanly after %d cycle(s).", cycle)


if __name__ == "__main__":
    run()

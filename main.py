# =============================================================================
# main.py — Tracker app entry point  (Milestone 8: hardened)
#
# Runs an infinite loop that every CAPTURE_INTERVAL_SECONDS:
#   1. Takes a screenshot
#   2. Captures a webcam photo
#   3. Compresses both images
#   4. Uploads both to Google Drive  (with retry on transient failures)
#   5. Deletes local files after each attempt (success or not)
#
# Hardening added in M8:
#   - startup self-check (disk space, credentials, Drive folder ID)
#   - per-cycle guard: an unhandled exception never kills the loop
#   - disk-space guard before capture: skips cycle if < MIN_FREE_MB available
#   - consecutive-failure circuit-breaker: backs off after N failures
#   - stale-file cleanup on startup: removes leftover temp images from a crash
#   - all error paths include context (cycle number, stage, filename)
# =============================================================================

import os
import sys
import time
import signal
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    CAPTURE_INTERVAL_SECONDS,
    UPLOAD_MAX_RETRIES,
    UPLOAD_RETRY_DELAY,
    TEMP_IMAGE_DIR,
    CREDENTIALS_FILE,
    TOKEN_FILE,
    GOOGLE_DRIVE_FOLDER_ID,
)
from capture.screenshot      import take_screenshot
from capture.webcam          import take_webcam_photo
from utils.compressor        import compress_image
from uploader.drive_uploader import upload_file
from utils.logger            import get_logger

log = get_logger("main")

# ---------------------------------------------------------------------------
# Tunable constants
# ---------------------------------------------------------------------------
MIN_FREE_MB          = 200    # skip capture cycle if free disk space falls below this
CIRCUIT_BREAKER_LIMIT = 5    # consecutive full-cycle failures before backing off
BACKOFF_SLEEP        = 300   # seconds to sleep when circuit breaker trips (5 min)

# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------
_shutdown_requested = False

def _handle_signal(signum, _frame) -> None:
    global _shutdown_requested
    log.info("Shutdown signal received (%s) — finishing current cycle then exiting.", signum)
    _shutdown_requested = True

signal.signal(signal.SIGINT,  _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


# ---------------------------------------------------------------------------
# Startup self-check
# ---------------------------------------------------------------------------

def _startup_checks() -> bool:
    """Run pre-flight checks before the first capture cycle.

    Checks
    ------
    - credentials.json exists
    - token.json exists  (reminds user to run setup_drive.py if missing)
    - GOOGLE_DRIVE_FOLDER_ID is not still the placeholder
    - temp_images/ and logs/ directories are writable
    - Sufficient free disk space

    Returns:
        True if all checks pass, False if any critical check fails.
    """
    log.info("Running startup checks…")
    ok = True

    # 1. credentials.json
    if not os.path.exists(CREDENTIALS_FILE):
        log.critical(
            "credentials.json not found at: %s\n"
            "  → Run  python setup_drive.py  to set up Google Drive auth.",
            CREDENTIALS_FILE,
        )
        ok = False
    else:
        log.debug("✓ credentials.json found")

    # 2. token.json
    if not os.path.exists(TOKEN_FILE):
        log.critical(
            "token.json not found at: %s\n"
            "  → Run  python setup_drive.py  to authenticate with Google Drive.",
            TOKEN_FILE,
        )
        ok = False
    else:
        log.debug("✓ token.json found")

    # 3. Drive folder ID placeholder check
    if GOOGLE_DRIVE_FOLDER_ID == "YOUR_FOLDER_ID_HERE":
        log.critical(
            "GOOGLE_DRIVE_FOLDER_ID is still the placeholder value.\n"
            "  → Edit config.py and set your real Drive folder ID."
        )
        ok = False
    else:
        log.debug("✓ GOOGLE_DRIVE_FOLDER_ID = %s", GOOGLE_DRIVE_FOLDER_ID)

    # 4. Writable working directories
    for label, path in [("temp_images", TEMP_IMAGE_DIR)]:
        try:
            os.makedirs(path, exist_ok=True)
            test_file = os.path.join(path, ".write_test")
            with open(test_file, "w") as f:
                f.write("ok")
            os.remove(test_file)
            log.debug("✓ %s/ is writable", label)
        except OSError as exc:
            log.critical("Directory %s is not writable: %s", path, exc)
            ok = False

    # 5. Disk space
    free_mb = _free_disk_mb()
    if free_mb < MIN_FREE_MB:
        log.critical(
            "Insufficient disk space: %.0f MB free (minimum %d MB required).",
            free_mb, MIN_FREE_MB,
        )
        ok = False
    else:
        log.debug("✓ Disk space: %.0f MB free", free_mb)

    if ok:
        log.info("All startup checks passed.")
    else:
        log.critical("One or more startup checks FAILED — fix the issues above and restart.")

    return ok


# ---------------------------------------------------------------------------
# Disk-space guard
# ---------------------------------------------------------------------------

def _free_disk_mb() -> float:
    """Return free disk space in MB for the partition holding TEMP_IMAGE_DIR."""
    try:
        usage = shutil.disk_usage(TEMP_IMAGE_DIR)
        return usage.free / (1024 * 1024)
    except Exception:
        log.warning("Could not determine free disk space — assuming sufficient.")
        return float("inf")


def _check_disk_space() -> bool:
    """Return True if there is enough free space to run a capture cycle."""
    free_mb = _free_disk_mb()
    if free_mb < MIN_FREE_MB:
        log.warning(
            "Low disk space: %.0f MB free (minimum %d MB). Skipping cycle.",
            free_mb, MIN_FREE_MB,
        )
        return False
    return True


# ---------------------------------------------------------------------------
# Stale file cleanup
# ---------------------------------------------------------------------------

def _cleanup_stale_temp_files() -> None:
    """Delete any leftover images in temp_images/ from a previous crash."""
    try:
        stale = [
            f for f in os.listdir(TEMP_IMAGE_DIR)
            if f.endswith(".jpg") or f.endswith(".jpeg")
        ]
        if stale:
            log.warning(
                "Found %d stale temp file(s) from a previous run — deleting.", len(stale)
            )
            for name in stale:
                path = os.path.join(TEMP_IMAGE_DIR, name)
                try:
                    os.remove(path)
                    log.debug("Deleted stale file: %s", name)
                except OSError as exc:
                    log.warning("Could not delete stale file %s: %s", name, exc)
    except FileNotFoundError:
        pass  # temp_images/ doesn't exist yet — nothing to clean


# ---------------------------------------------------------------------------
# Per-file pipeline helpers
# ---------------------------------------------------------------------------

def _compress(filepath: str, label: str, cycle: int) -> str | None:
    """Compress filepath in-place. Returns path on success, None on failure."""
    try:
        result = compress_image(filepath, keep_original=False)
        if result is None:
            log.error("[cycle=%d][%s] Compression failed — skipping upload.", cycle, label)
        return result
    except Exception:
        log.exception("[cycle=%d][%s] Unexpected error during compression.", cycle, label)
        return None


def _upload_with_retry(filepath: str, label: str, cycle: int) -> bool:
    """Attempt upload, retrying up to UPLOAD_MAX_RETRIES times.

    Returns True only on success.
    """
    for attempt in range(1, UPLOAD_MAX_RETRIES + 1):
        try:
            log.debug(
                "[cycle=%d][%s] Upload attempt %d / %d…",
                cycle, label, attempt, UPLOAD_MAX_RETRIES,
            )
            if upload_file(filepath):
                return True
        except Exception:
            log.exception(
                "[cycle=%d][%s] Unhandled exception on upload attempt %d.",
                cycle, label, attempt,
            )

        if attempt < UPLOAD_MAX_RETRIES:
            log.warning(
                "[cycle=%d][%s] Upload failed (attempt %d) — retrying in %ds…",
                cycle, label, attempt, UPLOAD_RETRY_DELAY,
            )
            time.sleep(UPLOAD_RETRY_DELAY)

    log.error(
        "[cycle=%d][%s] All %d upload attempts failed.",
        cycle, label, UPLOAD_MAX_RETRIES,
    )
    return False


def _delete_local(filepath: str, label: str, cycle: int) -> None:
    """Delete filepath from disk, logging the outcome."""
    try:
        os.remove(filepath)
        log.debug("[cycle=%d][%s] Local file deleted: %s", cycle, label, filepath)
    except FileNotFoundError:
        log.debug("[cycle=%d][%s] File already gone: %s", cycle, label, filepath)
    except OSError:
        log.exception(
            "[cycle=%d][%s] Could not delete local file: %s", cycle, label, filepath
        )


# ---------------------------------------------------------------------------
# Single file pipeline: capture → compress → upload → delete
# ---------------------------------------------------------------------------

def _process_file(filepath: str | None, label: str, cycle: int) -> bool:
    """Run the full pipeline for one captured image.

    Args:
        filepath: Path from a capture function, or None if capture failed.
        label:    "screenshot" or "webcam".
        cycle:    Current cycle number (for log context).

    Returns:
        True if the file was successfully uploaded, False otherwise.
    """
    if filepath is None:
        log.error("[cycle=%d][%s] Capture failed — nothing to process.", cycle, label)
        return False

    # Compress
    filepath = _compress(filepath, label, cycle)
    if filepath is None:
        return False

    # Upload with retry
    uploaded = _upload_with_retry(filepath, label, cycle)

    # Always delete locally — prevents temp_images from filling disk
    _delete_local(filepath, label, cycle)

    if uploaded:
        log.info("[cycle=%d][%s] ✓ Pipeline complete.", cycle, label)
    else:
        log.warning(
            "[cycle=%d][%s] ✗ Pipeline complete — upload failed (file removed locally).",
            cycle, label,
        )

    return uploaded


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run() -> None:
    """Start the infinite capture loop. Exits cleanly on SIGINT / SIGTERM."""
    log.info("=" * 60)
    log.info("Tracker starting…")
    log.info("=" * 60)

    # Pre-flight
    if not _startup_checks():
        log.critical("Aborting — fix startup check failures before running.")
        sys.exit(1)

    # Clean up any leftovers from a previous crash
    _cleanup_stale_temp_files()

    log.info("Tracker running  (interval=%ds)", CAPTURE_INTERVAL_SECONDS)

    cycle              = 0
    consecutive_fails  = 0   # circuit-breaker counter

    while not _shutdown_requested:
        cycle += 1
        log.info("─── Cycle %d ────────────────────────────────────────────", cycle)

        # --- Disk-space guard ---
        if not _check_disk_space():
            consecutive_fails += 1
        else:
            cycle_ok = False
            try:
                ss_ok  = _process_file(take_screenshot(),   "screenshot", cycle)
                cam_ok = _process_file(take_webcam_photo(), "webcam",     cycle)
                cycle_ok = ss_ok or cam_ok   # at least one succeeded

            except Exception:
                # Last-resort guard: an unhandled exception must never kill the loop
                log.exception(
                    "[cycle=%d] Unhandled exception in capture cycle — will retry next interval.",
                    cycle,
                )

            if cycle_ok:
                consecutive_fails = 0
            else:
                consecutive_fails += 1
                log.warning(
                    "[cycle=%d] Both pipelines failed (%d consecutive).",
                    cycle, consecutive_fails,
                )

        # --- Circuit breaker ---
        if consecutive_fails >= CIRCUIT_BREAKER_LIMIT:
            log.error(
                "%d consecutive cycle failures — backing off for %ds before retrying.",
                consecutive_fails, BACKOFF_SLEEP,
            )
            consecutive_fails = 0   # reset so we try again after the backoff
            _interruptible_sleep(BACKOFF_SLEEP)
            continue

        log.info("Cycle %d done — sleeping %ds.", cycle, CAPTURE_INTERVAL_SECONDS)
        _interruptible_sleep(CAPTURE_INTERVAL_SECONDS)

    log.info("Tracker stopped cleanly after %d cycle(s).", cycle)


def _interruptible_sleep(seconds: int) -> None:
    """Sleep for *seconds* but wake immediately if shutdown is requested."""
    for _ in range(seconds):
        if _shutdown_requested:
            return
        time.sleep(1)


if __name__ == "__main__":
    run()
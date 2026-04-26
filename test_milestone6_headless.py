"""
Milestone 6 headless integration test — main loop pipeline.

Mocks all I/O (screenshot, webcam, Drive API) so the full
capture → compress → upload → delete cycle can run without
a display, camera, or internet connection.

Run: cd tracker_app && python test_milestone6_headless.py
"""

import sys, os, types, unittest.mock as mock, tempfile, json
sys.path.insert(0, os.path.dirname(__file__))

# ── mock google API stack (same as M5 test) ──────────────────────────────────
for mod_name in [
    "google", "google.auth", "google.auth.transport",
    "google.auth.transport.requests", "google.oauth2",
    "google.oauth2.credentials", "google_auth_oauthlib",
    "google_auth_oauthlib.flow", "googleapiclient",
    "googleapiclient.discovery", "googleapiclient.errors",
    "googleapiclient.http",
]:
    sys.modules.setdefault(mod_name, types.ModuleType(mod_name))

sys.modules["google.auth.transport.requests"].Request = object

class FakeCreds:
    valid = True; expired = False; refresh_token = "x"
    def refresh(self, _): pass
    def to_json(self): return '{}'
    @classmethod
    def from_authorized_user_file(cls, *_): return cls()

sys.modules["google.oauth2.credentials"].Credentials          = FakeCreds
sys.modules["googleapiclient.errors"].HttpError               = Exception

class FakeMediaUpload:
    def __init__(self, *a, **kw): pass

sys.modules["googleapiclient.http"].MediaFileUpload = FakeMediaUpload

class FakeFlow:
    @classmethod
    def from_client_secrets_file(cls, *_): return cls()
    def run_local_server(self, **_): return FakeCreds()

sys.modules["google_auth_oauthlib.flow"].InstalledAppFlow = FakeFlow

_execute_mock = mock.MagicMock(return_value={"id": "drive123", "name": "x.jpg", "size": "100"})
_files_mock   = mock.MagicMock(return_value=mock.MagicMock(
    create=mock.MagicMock(return_value=mock.MagicMock(execute=_execute_mock))
))
_svc_mock = mock.MagicMock(); _svc_mock.files = _files_mock
sys.modules["googleapiclient.discovery"].build = mock.MagicMock(return_value=_svc_mock)

# ── mock pyautogui ────────────────────────────────────────────────────────────
import numpy as np
from PIL import Image

fake_pyautogui = types.ModuleType("pyautogui")
fake_pyautogui.screenshot = lambda: Image.new("RGB", (1280, 720), (30, 100, 200))
sys.modules["pyautogui"] = fake_pyautogui

# ── mock cv2 ─────────────────────────────────────────────────────────────────
fake_cv2 = types.ModuleType("cv2")
fake_cv2.CAP_DSHOW     = 700
fake_cv2.COLOR_BGR2RGB = 4
fake_cv2.cvtColor      = lambda f, _: f

class FakeCap:
    def __init__(self, *a, **kw): self._open = True
    def isOpened(self): return self._open
    def read(self):
        return True, np.full((720, 1280, 3), 80, dtype=np.uint8)
    def release(self): self._open = False

fake_cv2.VideoCapture = FakeCap
sys.modules["cv2"] = fake_cv2

# ── patch token / credentials paths ──────────────────────────────────────────
import config
config.TOKEN_FILE       = "/tmp/fake_token_m6.json"
config.CREDENTIALS_FILE = "/tmp/fake_creds_m6.json"
with open(config.TOKEN_FILE, "w")       as f: json.dump({"token":"x","refresh_token":"x","token_uri":"x","client_id":"x","client_secret":"x","scopes":[]}, f)
with open(config.CREDENTIALS_FILE, "w") as f: json.dump({"installed":{"client_id":"x","client_secret":"x","redirect_uris":["x"]}}, f)

# ── import main AFTER all mocks are in place ──────────────────────────────────
import main as app
from utils.logger import get_logger

log = get_logger("milestone6_headless")


# ---------------------------------------------------------------------------
# Test 1 — Full happy-path cycle: both files captured, compressed, uploaded,
#           then deleted from disk.
# ---------------------------------------------------------------------------
def test_full_cycle_happy_path():
    log.info("── Test 1: full happy-path cycle ──")

    deleted = []
    original_delete = app._delete_local

    def _track_delete(fp, label):
        deleted.append(fp)
        original_delete(fp, label)

    with mock.patch.object(app, "_delete_local", side_effect=_track_delete):
        app._process_file(app.take_screenshot(),   "screenshot")
        app._process_file(app.take_webcam_photo(), "webcam")

    assert len(deleted) == 2, f"Expected 2 deletions, got {len(deleted)}"
    for p in deleted:
        assert not os.path.exists(p), f"File should be deleted: {p}"

    log.info("PASS  2 files processed and deleted from disk")


# ---------------------------------------------------------------------------
# Test 2 — Capture failure: _process_file handles None gracefully.
# ---------------------------------------------------------------------------
def test_capture_failure_handled():
    log.info("── Test 2: capture returns None ──")
    # Should log an error and return — no exception raised
    app._process_file(None, "screenshot")
    log.info("PASS  None capture handled without exception")


# ---------------------------------------------------------------------------
# Test 3 — Upload failure + retry: file still deleted, no exception.
# ---------------------------------------------------------------------------
def test_upload_failure_still_deletes():
    log.info("── Test 3: upload fails → file still deleted ──")

    deleted = []

    with mock.patch("uploader.drive_uploader.upload_file", return_value=False), \
         mock.patch.object(app, "_delete_local",
                           side_effect=lambda fp, lbl: deleted.append(fp) or
                                       (os.remove(fp) if os.path.exists(fp) else None)):

        path = app.take_screenshot()
        assert path is not None
        app._process_file(path, "screenshot")

    assert len(deleted) == 1, f"File must be deleted even on upload failure, got {deleted}"
    log.info("PASS  file deleted despite upload failure")


# ---------------------------------------------------------------------------
# Test 4 — Retry logic: upload_with_retry stops after UPLOAD_MAX_RETRIES
# ---------------------------------------------------------------------------
def test_upload_retry_exhausted():
    log.info("── Test 4: retry exhausted after %d attempts ──", config.UPLOAD_MAX_RETRIES)

    call_count = {"n": 0}

    def _always_fail(_path):
        call_count["n"] += 1
        return False

    with mock.patch("main.upload_file", side_effect=_always_fail), \
         mock.patch("main.time.sleep"):   # skip real sleeps in test
        os.makedirs(config.TEMP_IMAGE_DIR, exist_ok=True)
        tmp = os.path.join(config.TEMP_IMAGE_DIR, "retry_test.jpg")
        Image.new("RGB", (10, 10)).save(tmp, "JPEG")
        result = app._upload_with_retry(tmp, "test")
        if os.path.exists(tmp): os.remove(tmp)

    assert result is False, "Should return False after exhausting retries"
    assert call_count["n"] == config.UPLOAD_MAX_RETRIES, \
        f"Expected {config.UPLOAD_MAX_RETRIES} attempts, got {call_count['n']}"

    log.info("PASS  retried exactly %d times then returned False", call_count["n"])


if __name__ == "__main__":
    log.info("=== Milestone 6 — Main loop integration tests ===")
    test_full_cycle_happy_path()
    test_capture_failure_handled()
    test_upload_failure_still_deletes()
    test_upload_retry_exhausted()
    log.info("=== All 4 tests passed ===")

    for f in [config.TOKEN_FILE, config.CREDENTIALS_FILE]:
        if os.path.exists(f): os.remove(f)

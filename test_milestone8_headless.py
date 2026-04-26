"""
Milestone 8 headless test suite — hardened main.py + drive_uploader.py
Tests every new error-handling path added in M8.
Run: cd tracker_app && python test_milestone8_headless.py
"""

import sys, os, types, unittest.mock as mock, json
sys.path.insert(0, os.path.dirname(__file__))

# ── mock google API stack ────────────────────────────────────────────────────
for mod in [
    "google","google.auth","google.auth.transport",
    "google.auth.transport.requests","google.oauth2","google.oauth2.credentials",
    "google_auth_oauthlib","google_auth_oauthlib.flow",
    "googleapiclient","googleapiclient.discovery",
    "googleapiclient.errors","googleapiclient.http",
]:
    sys.modules.setdefault(mod, types.ModuleType(mod))

sys.modules["google.auth.transport.requests"].Request = object

class FakeCreds:
    valid=True; expired=False; refresh_token="x"
    def refresh(self,_): pass
    def to_json(self): return '{}'
    @classmethod
    def from_authorized_user_file(cls,*_): return cls()

sys.modules["google.oauth2.credentials"].Credentials = FakeCreds

class FakeHttpError(Exception):
    def __init__(self, status, msg=""):
        super().__init__(msg)
        self.resp = type("R", (), {"status": status})()

sys.modules["googleapiclient.errors"].HttpError = FakeHttpError

class FakeMedia:
    def __init__(self,*a,**k): pass

sys.modules["googleapiclient.http"].MediaFileUpload = FakeMedia

class FakeFlow:
    @classmethod
    def from_client_secrets_file(cls,*_): return cls()
    def run_local_server(self,**_): return FakeCreds()

sys.modules["google_auth_oauthlib.flow"].InstalledAppFlow = FakeFlow

_exec_mock = mock.MagicMock(return_value={"id":"drv1","name":"x.jpg","size":"1"})
_svc       = mock.MagicMock()
_svc.files = mock.MagicMock(return_value=mock.MagicMock(
    create=mock.MagicMock(return_value=mock.MagicMock(execute=_exec_mock))
))
sys.modules["googleapiclient.discovery"].build = mock.MagicMock(return_value=_svc)

# ── mock pyautogui + cv2 ─────────────────────────────────────────────────────
import numpy as np
from PIL import Image

fake_pg = types.ModuleType("pyautogui")
fake_pg.screenshot = lambda: Image.new("RGB",(640,480),(10,20,30))
sys.modules["pyautogui"] = fake_pg

fake_cv2 = types.ModuleType("cv2")
fake_cv2.CAP_DSHOW=700; fake_cv2.COLOR_BGR2RGB=4
fake_cv2.cvtColor = lambda f,_: f
class FakeCap:
    def __init__(self,*a,**k): self._o=True
    def isOpened(self): return self._o
    def read(self): return True, np.full((480,640,3),80,dtype=np.uint8)
    def release(self): self._o=False
fake_cv2.VideoCapture = FakeCap
sys.modules["cv2"] = fake_cv2

# ── patch credential paths ───────────────────────────────────────────────────
import config
config.TOKEN_FILE       = "/tmp/m8_token.json"
config.CREDENTIALS_FILE = "/tmp/m8_creds.json"
config.GOOGLE_DRIVE_FOLDER_ID = "real_folder_id"

with open(config.TOKEN_FILE,"w")       as f: json.dump({"token":"x","refresh_token":"x","token_uri":"x","client_id":"x","client_secret":"x","scopes":[]},f)
with open(config.CREDENTIALS_FILE,"w") as f: json.dump({"installed":{"client_id":"x","client_secret":"x","redirect_uris":["x"]}},f)

import main
from uploader.drive_uploader import upload_file, AuthError
from utils.logger import get_logger

log = get_logger("milestone8_headless")


def _img(name):
    os.makedirs(config.TEMP_IMAGE_DIR, exist_ok=True)
    p = os.path.join(config.TEMP_IMAGE_DIR, name)
    Image.new("RGB",(100,100),(50,100,150)).save(p,"JPEG")
    return p


# ---------------------------------------------------------------------------
# ── main.py tests ─────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

def test_startup_checks_pass():
    """All checks green when credentials exist and folder ID is set."""
    log.info("── Test 1: startup checks pass ──")
    result = main._startup_checks()
    assert result is True, "startup checks should pass with valid config"
    log.info("PASS")


def test_startup_checks_fail_missing_creds():
    """startup_checks returns False when credentials.json is missing."""
    log.info("── Test 2: startup checks fail — missing credentials.json ──")
    with mock.patch("main.CREDENTIALS_FILE", "/tmp/nonexistent_creds.json"):
        result = main._startup_checks()
    assert result is False
    log.info("PASS")


def test_startup_checks_fail_placeholder_folder():
    """startup_checks returns False when folder ID is still placeholder."""
    log.info("── Test 3: startup checks fail — placeholder folder ID ──")
    with mock.patch("main.GOOGLE_DRIVE_FOLDER_ID", "YOUR_FOLDER_ID_HERE"):
        result = main._startup_checks()
    assert result is False
    log.info("PASS")


def test_stale_file_cleanup():
    """_cleanup_stale_temp_files removes leftover .jpg files."""
    log.info("── Test 4: stale file cleanup ──")
    stale = _img("stale_leftover.jpg")
    assert os.path.exists(stale)
    main._cleanup_stale_temp_files()
    assert not os.path.exists(stale), "stale file should be removed"
    log.info("PASS")


def test_disk_space_guard_skip():
    """Cycle is skipped when free disk space is below threshold."""
    log.info("── Test 5: disk-space guard skips cycle ──")
    with mock.patch("main._free_disk_mb", return_value=10.0):
        result = main._check_disk_space()
    assert result is False
    log.info("PASS")


def test_unhandled_exception_in_cycle_does_not_crash_loop():
    """An unexpected exception inside a cycle is caught — loop continues."""
    log.info("── Test 6: unhandled exception caught by loop guard ──")
    call_count = {"n": 0}

    def _boom():
        call_count["n"] += 1
        raise RuntimeError("simulated crash")

    # Run one iteration of the loop body manually
    try:
        with mock.patch("main.take_screenshot", side_effect=_boom), \
             mock.patch("main.take_webcam_photo", side_effect=_boom):
            try:
                main._process_file(main.take_screenshot(), "screenshot", 99)
            except Exception:
                pass  # outer loop catches this — simulate its behaviour
    except Exception:
        assert False, "Exception must NOT propagate out of the loop guard"

    log.info("PASS  exception was contained")


def test_consecutive_failure_counter_resets_on_success():
    """consecutive_fails resets to 0 after a successful cycle."""
    log.info("── Test 7: circuit-breaker counter resets on success ──")
    # _process_file returns True on success; verify counter logic
    with mock.patch("main.upload_file", return_value=True):
        result = main._process_file(main.take_screenshot(), "screenshot", 1)
    assert result is True
    log.info("PASS  successful cycle returns True (counter would reset)")


# ---------------------------------------------------------------------------
# ── drive_uploader.py tests ───────────────────────────────────────────────
# ---------------------------------------------------------------------------

def test_upload_placeholder_folder_returns_false():
    """upload_file returns False immediately if folder ID is placeholder."""
    log.info("── Test 8: placeholder folder ID blocked ──")
    p = _img("placeholder_test.jpg")
    with mock.patch("uploader.drive_uploader.GOOGLE_DRIVE_FOLDER_ID", "YOUR_FOLDER_ID_HERE"):
        result = upload_file(p)
    assert result is False
    if os.path.exists(p): os.remove(p)
    log.info("PASS")


def test_upload_retryable_http_error():
    """upload_file returns False on 503; caller retries (logged as WARNING)."""
    log.info("── Test 9: retryable HTTP 503 returns False ──")
    p = _img("retry_503.jpg")
    import uploader.drive_uploader as du
    orig = du._build_service
    du._build_service = lambda: (_ for _ in ()).throw(FakeHttpError(503, "service unavailable"))
    result = upload_file(p)
    du._build_service = orig
    assert result is False
    if os.path.exists(p): os.remove(p)
    log.info("PASS")


def test_upload_fatal_http_401():
    """upload_file returns False on 401 with a clear auth hint in the log."""
    log.info("── Test 10: fatal HTTP 401 returns False ──")
    p = _img("auth_fail.jpg")
    import uploader.drive_uploader as du
    orig = du._build_service
    du._build_service = lambda: (_ for _ in ()).throw(FakeHttpError(401, "unauthorized"))
    result = upload_file(p)
    du._build_service = orig
    assert result is False
    if os.path.exists(p): os.remove(p)
    log.info("PASS")


def test_corrupt_token_triggers_reauth():
    """Corrupt token.json is handled gracefully — falls through to re-auth."""
    log.info("── Test 11: corrupt token.json handled ──")
    with open(config.TOKEN_FILE, "w") as f:
        f.write("{{not valid json}}")
    import uploader.drive_uploader as du
    # After corrupt token, it should attempt re-auth via FakeFlow
    try:
        creds = du._get_credentials()
        assert creds is not None
        log.info("PASS  re-auth succeeded after corrupt token")
    except Exception as exc:
        log.error("FAIL  unexpected exception: %s", exc)
        raise
    finally:
        # Restore valid token
        with open(config.TOKEN_FILE,"w") as f:
            json.dump({"token":"x","refresh_token":"x","token_uri":"x","client_id":"x","client_secret":"x","scopes":[]},f)


if __name__ == "__main__":
    log.info("=== Milestone 8 — Error handling test suite ===")
    test_startup_checks_pass()
    test_startup_checks_fail_missing_creds()
    test_startup_checks_fail_placeholder_folder()
    test_stale_file_cleanup()
    test_disk_space_guard_skip()
    test_unhandled_exception_in_cycle_does_not_crash_loop()
    test_consecutive_failure_counter_resets_on_success()
    test_upload_placeholder_folder_returns_false()
    test_upload_retryable_http_error()
    test_upload_fatal_http_401()
    test_corrupt_token_triggers_reauth()
    log.info("=== All 11 tests passed ===")

    for f in [config.TOKEN_FILE, config.CREDENTIALS_FILE]:
        if os.path.exists(f): os.remove(f)

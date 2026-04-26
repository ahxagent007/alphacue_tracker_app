"""
Milestone 5 headless unit-test — Google Drive uploader.
Mocks the entire Google API stack so no credentials or network are needed.
Run: cd tracker_app && python test_milestone5_headless.py
"""

import sys, os, types, unittest.mock as mock
sys.path.insert(0, os.path.dirname(__file__))

# ── mock all google.* packages before importing drive_uploader ───────────────
for mod_name in [
    "google", "google.auth", "google.auth.transport", "google.auth.transport.requests",
    "google.oauth2", "google.oauth2.credentials",
    "google_auth_oauthlib", "google_auth_oauthlib.flow",
    "googleapiclient", "googleapiclient.discovery",
    "googleapiclient.errors", "googleapiclient.http",
]:
    sys.modules.setdefault(mod_name, types.ModuleType(mod_name))

# Stub Request (used for token refresh)
sys.modules["google.auth.transport.requests"].Request = object

# Stub Credentials
class FakeCreds:
    valid        = True
    expired      = False
    refresh_token= "fake"
    def refresh(self, _): pass
    def to_json(self): return '{"token":"fake"}'
    @classmethod
    def from_authorized_user_file(cls, *_): return cls()

sys.modules["google.oauth2.credentials"].Credentials = FakeCreds

# Stub InstalledAppFlow
class FakeFlow:
    @classmethod
    def from_client_secrets_file(cls, *_): return cls()
    def run_local_server(self, **_): return FakeCreds()

sys.modules["google_auth_oauthlib.flow"].InstalledAppFlow = FakeFlow

# Stub HttpError
class FakeHttpError(Exception):
    pass

sys.modules["googleapiclient.errors"].HttpError = FakeHttpError

# Stub MediaFileUpload
class FakeMediaUpload:
    def __init__(self, *_a, **_kw): pass

sys.modules["googleapiclient.http"].MediaFileUpload = FakeMediaUpload

# Stub build() → returns a fake service with a chainable files().create().execute()
def _make_fake_service(return_id="abc123", raise_exc=None):
    execute_mock = mock.MagicMock(return_value={"id": return_id, "name": "test.jpg", "size": "1024"})
    if raise_exc:
        execute_mock.side_effect = raise_exc
    create_mock  = mock.MagicMock(return_value=mock.MagicMock(execute=execute_mock))
    files_mock   = mock.MagicMock(return_value=mock.MagicMock(create=create_mock))
    service_mock = mock.MagicMock()
    service_mock.files = files_mock
    return service_mock

sys.modules["googleapiclient.discovery"].build = mock.MagicMock(
    return_value=_make_fake_service()
)

# ── patch token file so _get_credentials skips the browser flow ──────────────
import config
config.TOKEN_FILE       = "/tmp/fake_token.json"
config.CREDENTIALS_FILE = "/tmp/fake_credentials.json"

# Write fake token + credentials so the code believes they exist
import json
with open(config.TOKEN_FILE, "w") as f:
    json.dump({"token": "fake", "refresh_token": "fake", "token_uri": "x",
               "client_id": "x", "client_secret": "x", "scopes": []}, f)
with open(config.CREDENTIALS_FILE, "w") as f:
    json.dump({"installed": {"client_id": "x", "client_secret": "x",
               "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"]}}, f)

# ── now import module under test ─────────────────────────────────────────────
from uploader.drive_uploader import upload_file
from utils.logger import get_logger
from PIL import Image

log = get_logger("milestone5_headless")


def _make_test_image(name: str) -> str:
    """Write a tiny JPEG to temp_images and return its path."""
    os.makedirs(config.TEMP_IMAGE_DIR, exist_ok=True)
    path = os.path.join(config.TEMP_IMAGE_DIR, name)
    Image.new("RGB", (320, 240), color=(255, 100, 50)).save(path, "JPEG")
    return path


# ---------------------------------------------------------------------------
# Test 1 — Happy path: upload succeeds, returns True
# ---------------------------------------------------------------------------
def test_successful_upload():
    log.info("── Test 1: successful upload ──")
    path = _make_test_image("test_upload.jpg")
    result = upload_file(path)
    assert result is True, f"Expected True, got {result}"
    log.info("PASS  upload_file returned True")
    os.remove(path)


# ---------------------------------------------------------------------------
# Test 2 — Missing file: returns False, no crash
# ---------------------------------------------------------------------------
def test_missing_file():
    log.info("── Test 2: missing file ──")
    result = upload_file("/tmp/does_not_exist_xyz.jpg")
    assert result is False, f"Expected False for missing file, got {result}"
    log.info("PASS  returned False as expected")


# ---------------------------------------------------------------------------
# Test 3 — HttpError from Drive API: returns False, no crash
# ---------------------------------------------------------------------------
def test_http_error():
    log.info("── Test 3: HttpError from Drive API ──")
    path = _make_test_image("test_http_error.jpg")

    # Make the fake service raise HttpError
    bad_service = _make_fake_service(raise_exc=FakeHttpError("403 Forbidden"))
    with mock.patch("googleapiclient.discovery.build", return_value=bad_service):
        # Re-import to pick up patched build
        import importlib
        import uploader.drive_uploader as du
        original_build = du._build_service

        def _patched_build():
            return bad_service
        du._build_service = _patched_build
        result = upload_file(path)
        du._build_service = original_build

    assert result is False, f"Expected False on HttpError, got {result}"
    log.info("PASS  returned False on HTTP error")
    os.remove(path)


# ---------------------------------------------------------------------------
# Test 4 — Unexpected exception: returns False, no crash
# ---------------------------------------------------------------------------
def test_unexpected_exception():
    log.info("── Test 4: unexpected exception ──")
    path = _make_test_image("test_exception.jpg")

    import uploader.drive_uploader as du
    original = du._build_service

    def _boom():
        raise RuntimeError("simulated network failure")
    du._build_service = _boom
    result = upload_file(path)
    du._build_service = original

    assert result is False, f"Expected False on exception, got {result}"
    log.info("PASS  returned False on unexpected exception")
    os.remove(path)


if __name__ == "__main__":
    log.info("=== Milestone 5 — Drive Uploader unit-tests ===")
    test_successful_upload()
    test_missing_file()
    test_http_error()
    test_unexpected_exception()
    log.info("=== All 4 tests passed ===")

    # Cleanup temp files
    for f in [config.TOKEN_FILE, config.CREDENTIALS_FILE]:
        if os.path.exists(f): os.remove(f)

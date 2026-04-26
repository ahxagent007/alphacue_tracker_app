# =============================================================================
# uploader/drive_uploader.py — Google Drive file upload via OAuth 2.0
#
# First-time setup (run once manually, not by the background app):
#   python uploader/drive_uploader.py --auth
#
# This opens a browser, asks you to sign in, then writes token.json.
# After that the background app runs silently — no browser needed.
#
# Usage:
#   from uploader.drive_uploader import upload_file
#   success = upload_file("/path/to/image.jpg")
# =============================================================================

import os
import sys
import mimetypes

from google.auth.transport.requests import Request
from google.oauth2.credentials       import Credentials
from google_auth_oauthlib.flow       import InstalledAppFlow
from googleapiclient.discovery       import build
from googleapiclient.errors          import HttpError
from googleapiclient.http            import MediaFileUpload

from config import (
    GOOGLE_DRIVE_FOLDER_ID,
    CREDENTIALS_FILE,
    TOKEN_FILE,
)
from utils.logger import get_logger

log = get_logger(__name__)

# The only Drive scope we need — upload + list files in shared folders
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _get_credentials() -> Credentials:
    """Load or refresh OAuth 2.0 credentials.

    Flow
    ----
    1. If ``token.json`` exists and is valid → use it directly.
    2. If token is expired but has a refresh token → refresh silently.
    3. If neither condition is met → launch browser OAuth flow and save
       the new token to ``token.json`` for future runs.

    Returns:
        A valid :class:`google.oauth2.credentials.Credentials` object.

    Raises:
        FileNotFoundError: if ``credentials.json`` is missing.
        Exception: if the OAuth flow fails.
    """
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError(
            f"credentials.json not found at: {CREDENTIALS_FILE}\n"
            "Download it from Google Cloud Console → APIs & Services → Credentials."
        )

    creds = None

    # Re-use a previously saved token
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # Refresh expired token silently (no browser needed)
    if creds and creds.expired and creds.refresh_token:
        log.debug("Refreshing expired OAuth token…")
        creds.refresh(Request())

    # First-time: launch browser flow
    elif not creds or not creds.valid:
        log.info("Starting OAuth browser flow — check your browser…")
        flow  = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)

    # Persist for next run
    with open(TOKEN_FILE, "w") as fh:
        fh.write(creds.to_json())
    log.debug("Token saved to %s", TOKEN_FILE)

    return creds


def _build_service():
    """Return an authenticated Google Drive v3 service client."""
    creds = _get_credentials()
    return build("drive", "v3", credentials=creds)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def upload_file(filepath: str) -> bool:
    """Upload a single file to the configured Google Drive folder.

    Args:
        filepath: Absolute path to the local file to upload.

    Returns:
        ``True`` on success, ``False`` on any failure.
    """
    if not os.path.exists(filepath):
        log.error("upload_file: file not found — %s", filepath)
        return False

    filename    = os.path.basename(filepath)
    mime_type   = mimetypes.guess_type(filepath)[0] or "application/octet-stream"
    size_kb     = os.path.getsize(filepath) / 1024

    log.debug("Uploading %s  (%.1f KB, %s)…", filename, size_kb, mime_type)

    try:
        service = _build_service()

        # File metadata — name + parent folder
        file_metadata = {
            "name":    filename,
            "parents": [GOOGLE_DRIVE_FOLDER_ID],
        }

        # resumable=True handles large files and poor connections gracefully
        media = MediaFileUpload(filepath, mimetype=mime_type, resumable=True)

        uploaded = (
            service.files()
            .create(body=file_metadata, media_body=media, fields="id,name,size")
            .execute()
        )

        log.info(
            "Uploaded %-40s → Drive file ID: %s  (%.1f KB)",
            uploaded.get("name"), uploaded.get("id"), size_kb,
        )
        return True

    except HttpError as exc:
        log.error("Drive API HTTP error for %s: %s", filename, exc)
        return False

    except Exception:
        log.exception("Unexpected error uploading %s", filename)
        return False


# ---------------------------------------------------------------------------
# One-time auth helper — run manually from the command line
# ---------------------------------------------------------------------------

def _run_auth_flow() -> None:
    """Interactive helper: authenticate and write token.json, then exit."""
    print("\n=== Google Drive — First-time authentication ===")
    print(f"credentials.json path : {CREDENTIALS_FILE}")
    print(f"token.json will be at : {TOKEN_FILE}\n")
    try:
        creds = _get_credentials()
        if creds and creds.valid:
            print("✓ Authentication successful. token.json saved.")
            print("  You will NOT need to do this again unless you revoke access.")
        else:
            print("✗ Authentication failed — check credentials.json and try again.")
    except FileNotFoundError as exc:
        print(f"✗ {exc}")
    except Exception as exc:
        print(f"✗ Unexpected error: {exc}")


if __name__ == "__main__":
    if "--auth" in sys.argv:
        _run_auth_flow()
    else:
        print("Usage: python uploader/drive_uploader.py --auth")
        print("       Runs the one-time browser OAuth flow and saves token.json.")

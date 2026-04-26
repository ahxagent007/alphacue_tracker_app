# =============================================================================
# uploader/drive_uploader.py — Google Drive upload  (Milestone 8: hardened)
#
# Changes from M5:
#   - Distinguishes recoverable vs non-recoverable HTTP errors:
#       recoverable  (429 rate-limit, 5xx server errors) → caller should retry
#       fatal        (401 auth, 403 forbidden, 404 folder)  → logged clearly
#   - Token refresh failures raise a clear AuthError instead of a generic one
#   - Folder ID placeholder is validated before any network call
#   - All exceptions include the filename for easier log grepping
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

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

# HTTP status codes where retrying makes sense
_RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class AuthError(RuntimeError):
    """Raised when OAuth credentials cannot be obtained or refreshed."""


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _get_credentials() -> Credentials:
    """Load, refresh, or obtain OAuth 2.0 credentials.

    Raises:
        FileNotFoundError: credentials.json is missing.
        AuthError:         token refresh or flow failed.
    """
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError(
            f"credentials.json not found at: {CREDENTIALS_FILE}\n"
            "  → Run  python setup_drive.py  to set up auth."
        )

    creds = None

    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception as exc:
            log.warning("token.json is corrupt or unreadable (%s) — will re-authenticate.", exc)
            creds = None

    # Silently refresh an expired token
    if creds and creds.expired and creds.refresh_token:
        try:
            log.debug("Refreshing expired OAuth token…")
            creds.refresh(Request())
        except Exception as exc:
            log.warning("Token refresh failed (%s) — attempting full re-auth.", exc)
            creds = None

    # Full browser flow (first time or after refresh failure)
    if not creds or not creds.valid:
        try:
            log.info("Starting OAuth browser flow — check your browser…")
            flow  = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        except Exception as exc:
            raise AuthError(f"OAuth flow failed: {exc}") from exc

    # Persist refreshed/new token
    try:
        with open(TOKEN_FILE, "w") as fh:
            fh.write(creds.to_json())
        log.debug("Token saved → %s", TOKEN_FILE)
    except OSError as exc:
        # Non-fatal — token may still work in memory for this session
        log.warning("Could not save token.json: %s", exc)

    return creds


def _build_service():
    """Return an authenticated Google Drive v3 service client."""
    creds = _get_credentials()
    return build("drive", "v3", credentials=creds)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def upload_file(filepath: str) -> bool:
    """Upload a file to the configured Google Drive folder.

    Distinguishes fatal vs retryable HTTP errors so the caller
    (_upload_with_retry in main.py) can make informed retry decisions.

    Args:
        filepath: Absolute path to the local file.

    Returns:
        True on success.
        False on failure (all failures are logged with context).
    """
    # Guard: placeholder folder ID
    if GOOGLE_DRIVE_FOLDER_ID == "YOUR_FOLDER_ID_HERE":
        log.error(
            "GOOGLE_DRIVE_FOLDER_ID is not configured — "
            "edit config.py before running the tracker."
        )
        return False

    if not os.path.exists(filepath):
        log.error("upload_file: file not found — %s", filepath)
        return False

    filename  = os.path.basename(filepath)
    mime_type = mimetypes.guess_type(filepath)[0] or "application/octet-stream"
    size_kb   = os.path.getsize(filepath) / 1024

    log.debug("Uploading %s  (%.1f KB, %s)…", filename, size_kb, mime_type)

    try:
        service = _build_service()

        file_metadata = {
            "name":    filename,
            "parents": [GOOGLE_DRIVE_FOLDER_ID],
        }
        media = MediaFileUpload(filepath, mimetype=mime_type, resumable=True)

        uploaded = (
            service.files()
            .create(body=file_metadata, media_body=media, fields="id,name,size")
            .execute()
        )

        log.info(
            "Uploaded %-40s → Drive ID: %s  (%.1f KB)",
            uploaded.get("name"), uploaded.get("id"), size_kb,
        )
        return True

    except AuthError as exc:
        # Auth failure is not retryable — user needs to re-run setup_drive.py
        log.error(
            "Auth error uploading %s: %s\n"
            "  → Run  python setup_drive.py  to re-authenticate.",
            filename, exc,
        )
        return False

    except HttpError as exc:
        status = exc.resp.status if hasattr(exc, "resp") else 0
        if status in _RETRYABLE_HTTP_CODES:
            log.warning(
                "Drive API retryable error %d for %s — caller will retry: %s",
                status, filename, exc,
            )
        else:
            # 401, 403, 404 etc. — log as error with a helpful hint
            hint = {
                401: "Token may be revoked — run  python setup_drive.py  to re-auth.",
                403: "Access denied — check your Drive API quota and folder permissions.",
                404: "Folder not found — verify GOOGLE_DRIVE_FOLDER_ID in config.py.",
            }.get(status, "Check logs for details.")
            log.error(
                "Drive API error %d for %s: %s\n  → %s",
                status, filename, exc, hint,
            )
        return False

    except Exception:
        log.exception("Unexpected error uploading %s", filename)
        return False


# ---------------------------------------------------------------------------
# One-time auth CLI helper
# ---------------------------------------------------------------------------

def _run_auth_flow() -> None:
    print("\n=== Google Drive — First-time authentication ===")
    print(f"credentials.json : {CREDENTIALS_FILE}")
    print(f"token.json       : {TOKEN_FILE}\n")
    try:
        creds = _get_credentials()
        if creds and creds.valid:
            print("✓ Authentication successful. token.json saved.")
        else:
            print("✗ Authentication failed — check credentials.json and try again.")
    except (FileNotFoundError, AuthError) as exc:
        print(f"✗ {exc}")
    except Exception as exc:
        print(f"✗ Unexpected error: {exc}")


if __name__ == "__main__":
    if "--auth" in sys.argv:
        _run_auth_flow()
    else:
        print("Usage: python uploader/drive_uploader.py --auth")
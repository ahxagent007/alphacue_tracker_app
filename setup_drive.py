# =============================================================================
# setup_drive.py — Guided first-time Google Drive setup
#
# Run once before starting the tracker:
#   python setup_drive.py
#
# This script walks you through:
#   1. Verifying credentials.json exists
#   2. Running the OAuth browser flow → writes token.json
#   3. Doing a test upload of a tiny file to confirm everything works
# =============================================================================

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from utils.logger import get_logger
import config

log = get_logger("setup_drive")


def check_prerequisites() -> bool:
    print("\n" + "=" * 60)
    print("  Google Drive Setup Checker")
    print("=" * 60)

    ok = True

    # 1. credentials.json
    if os.path.exists(config.CREDENTIALS_FILE):
        print(f"  ✓  credentials.json found at:\n     {config.CREDENTIALS_FILE}")
    else:
        print(f"  ✗  credentials.json NOT found at:\n     {config.CREDENTIALS_FILE}")
        print()
        print("  HOW TO GET IT:")
        print("  1. Go to https://console.cloud.google.com/")
        print("  2. Create a project (or select existing)")
        print("  3. Enable the Google Drive API")
        print("  4. Go to APIs & Services → Credentials")
        print("  5. Create OAuth 2.0 Client ID → Desktop App")
        print("  6. Download JSON → rename to credentials.json")
        print(f"  7. Place it at: {config.CREDENTIALS_FILE}")
        ok = False

    # 2. Folder ID placeholder check
    if config.GOOGLE_DRIVE_FOLDER_ID == "YOUR_FOLDER_ID_HERE":
        print()
        print("  ✗  GOOGLE_DRIVE_FOLDER_ID is still the placeholder.")
        print("  HOW TO GET YOUR FOLDER ID:")
        print("  1. Open Google Drive in your browser")
        print("  2. Navigate into the folder you want uploads to go to")
        print("  3. Copy the ID from the URL:")
        print("     https://drive.google.com/drive/folders/<FOLDER_ID_HERE>")
        print(f"  4. Paste it into config.py → GOOGLE_DRIVE_FOLDER_ID")
        ok = False
    else:
        print(f"  ✓  GOOGLE_DRIVE_FOLDER_ID = {config.GOOGLE_DRIVE_FOLDER_ID}")

    # 3. token.json (optional — will be created by auth flow)
    if os.path.exists(config.TOKEN_FILE):
        print(f"  ✓  token.json already exists (auth done previously)")
    else:
        print(f"  ℹ  token.json not found — will be created during auth flow")

    print()
    return ok


def run_auth_and_test():
    """Trigger OAuth flow then do a tiny test upload."""
    from uploader.drive_uploader import _get_credentials, upload_file
    from PIL import Image

    print("Starting OAuth browser flow…")
    print("(A browser window will open — sign in and allow access)\n")

    try:
        creds = _get_credentials()
        if not creds or not creds.valid:
            print("✗ Auth failed.")
            return
        print("✓ Auth successful — token.json saved.\n")
    except Exception as exc:
        print(f"✗ Auth error: {exc}")
        return

    # Create a tiny test image
    test_path = os.path.join(config.TEMP_IMAGE_DIR, "drive_test_upload.jpg")
    os.makedirs(config.TEMP_IMAGE_DIR, exist_ok=True)
    Image.new("RGB", (100, 100), color=(0, 128, 255)).save(test_path, "JPEG")

    print(f"Uploading test file: {test_path}")
    success = upload_file(test_path)

    if success:
        print("✓ Test upload succeeded — check your Drive folder!")
        os.remove(test_path)
    else:
        print("✗ Test upload failed — check logs/tracker.log for details.")


if __name__ == "__main__":
    if not check_prerequisites():
        print("Fix the issues above, then re-run this script.\n")
        sys.exit(1)

    run_auth_and_test()

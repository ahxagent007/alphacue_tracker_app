# =============================================================================
# config.py — Central configuration for tracker_app
# All tunable settings live here. Edit this file to adjust behavior.
# =============================================================================

import os
import sys

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# When running as a PyInstaller .exe, __file__ points inside a temp extraction
# folder (_MEIPASS). We split paths so:
#   _BUNDLE_DIR  — where bundled assets live (credentials.json, token.json)
#   BASE_DIR     — where the .exe itself sits (logs/ and temp_images/ go here)
if getattr(sys, "frozen", False):
    # Running as compiled .exe
    BASE_DIR    = os.path.dirname(sys.executable)   # folder containing the .exe
    _BUNDLE_DIR = sys._MEIPASS                       # temp folder with bundled files
else:
    # Running as plain Python script
    BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
    _BUNDLE_DIR = BASE_DIR

TEMP_IMAGE_DIR  = os.path.join(BASE_DIR, "temp_images")   # staging area for captures
LOG_DIR         = os.path.join(BASE_DIR, "logs")
LOG_FILE        = os.path.join(LOG_DIR, "tracker.log")

# ---------------------------------------------------------------------------
# Capture settings
# ---------------------------------------------------------------------------
CAPTURE_INTERVAL_SECONDS = 60          # how often the main loop fires

# ---------------------------------------------------------------------------
# Image quality / compression
# ---------------------------------------------------------------------------
SCREENSHOT_FORMAT   = "JPEG"
WEBCAM_FORMAT       = "JPEG"
IMAGE_QUALITY       = 60               # JPEG quality 1-95 (lower = smaller file)
MAX_IMAGE_WIDTH     = 1280             # pixels; image is scaled down if wider
MAX_IMAGE_HEIGHT    = 720              # pixels; maintains aspect ratio

# ---------------------------------------------------------------------------
# Google Drive
# ---------------------------------------------------------------------------
GOOGLE_DRIVE_FOLDER_ID  = "YOUR_FOLDER_ID_HERE"   # replace after Drive setup
CREDENTIALS_FILE        = os.path.join(_BUNDLE_DIR, "credentials.json")
TOKEN_FILE              = os.path.join(_BUNDLE_DIR, "token.json")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL           = "DEBUG"          # DEBUG | INFO | WARNING | ERROR
LOG_MAX_BYTES       = 5 * 1024 * 1024  # 5 MB per log file before rotation
LOG_BACKUP_COUNT    = 3                # keep 3 rotated files

# ---------------------------------------------------------------------------
# Upload retry
# ---------------------------------------------------------------------------
UPLOAD_MAX_RETRIES  = 3
UPLOAD_RETRY_DELAY  = 10              # seconds between retries

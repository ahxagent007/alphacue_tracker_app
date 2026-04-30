"""
Gmail uploader headless test suite.
Mocks smtplib so no real email is sent.
Run: cd tracker_app && python test_gmail_uploader.py
"""

import sys, os, types, unittest.mock as mock
sys.path.insert(0, os.path.dirname(__file__))

from PIL import Image
import config

# Patch config values to valid ones for happy-path tests
config.SENDER_EMAIL        = "sender@gmail.com"
config.SENDER_APP_PASSWORD = "abcdefghijklmnop"
config.RECIPIENT_EMAIL     = "recipient@gmail.com"
config.EMAIL_SUBJECT       = "Test — {timestamp}"

from uploader.gmail_uploader import send_captures
from utils.logger import get_logger

log = get_logger("test_gmail")


def _img(name):
    os.makedirs(config.TEMP_IMAGE_DIR, exist_ok=True)
    p = os.path.join(config.TEMP_IMAGE_DIR, name)
    Image.new("RGB", (100, 100), (80, 120, 200)).save(p, "JPEG")
    return p


# ── Test 1 — Happy path: both files sent, returns True ───────────────────────
def test_happy_path():
    log.info("── Test 1: happy path ──")
    ss  = _img("t_screenshot.jpg")
    cam = _img("t_webcam.jpg")

    with mock.patch("smtplib.SMTP_SSL") as mock_smtp:
        instance = mock_smtp.return_value.__enter__.return_value
        result = send_captures([ss, cam])

    assert result is True
    instance.login.assert_called_once_with(config.SENDER_EMAIL, config.SENDER_APP_PASSWORD)
    instance.sendmail.assert_called_once()

    # Confirm both filenames appear in the sent message
    sent_body = instance.sendmail.call_args[0][2]
    assert "t_screenshot.jpg" in sent_body
    assert "t_webcam.jpg"     in sent_body

    log.info("PASS  login called, sendmail called, both filenames in message")
    for p in [ss, cam]:
        if os.path.exists(p): os.remove(p)


# ── Test 2 — Empty file list returns False ───────────────────────────────────
def test_empty_list():
    log.info("── Test 2: empty file list ──")
    result = send_captures([])
    assert result is False
    log.info("PASS")


# ── Test 3 — Placeholder sender email blocked ────────────────────────────────
def test_placeholder_sender():
    log.info("── Test 3: placeholder SENDER_EMAIL ──")
    p = _img("t_placeholder.jpg")
    with mock.patch("uploader.gmail_uploader.SENDER_EMAIL", "your.gmail@gmail.com"):
        result = send_captures([p])
    assert result is False
    if os.path.exists(p): os.remove(p)
    log.info("PASS")


# ── Test 4 — SMTPAuthenticationError returns False with clear log ────────────
def test_auth_error():
    log.info("── Test 4: SMTPAuthenticationError ──")
    import smtplib
    p = _img("t_authfail.jpg")
    with mock.patch("smtplib.SMTP_SSL") as mock_smtp:
        mock_smtp.return_value.__enter__.return_value.login.side_effect = \
            smtplib.SMTPAuthenticationError(535, b"Bad credentials")
        result = send_captures([p])
    assert result is False
    if os.path.exists(p): os.remove(p)
    log.info("PASS")


# ── Test 5 — Network error (OSError) returns False ──────────────────────────
def test_network_error():
    log.info("── Test 5: network OSError ──")
    p = _img("t_network.jpg")
    with mock.patch("smtplib.SMTP_SSL", side_effect=OSError("Network unreachable")):
        result = send_captures([p])
    assert result is False
    if os.path.exists(p): os.remove(p)
    log.info("PASS")


# ── Test 6 — Missing attachment skipped, email still sends ───────────────────
def test_missing_attachment_skipped():
    log.info("── Test 6: missing attachment is skipped gracefully ──")
    real  = _img("t_real.jpg")
    ghost = "/tmp/does_not_exist_xyz.jpg"

    with mock.patch("smtplib.SMTP_SSL") as mock_smtp:
        instance = mock_smtp.return_value.__enter__.return_value
        result = send_captures([real, ghost])

    assert result is True
    sent_body = instance.sendmail.call_args[0][2]
    assert "t_real.jpg" in sent_body     # real file attached
    log.info("PASS  missing file skipped, real file still sent")
    if os.path.exists(real): os.remove(real)


if __name__ == "__main__":
    log.info("=== Gmail uploader test suite ===")
    test_happy_path()
    test_empty_list()
    test_placeholder_sender()
    test_auth_error()
    test_network_error()
    test_missing_attachment_skipped()
    log.info("=== All 6 tests passed ===")

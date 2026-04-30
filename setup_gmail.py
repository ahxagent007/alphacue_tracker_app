# =============================================================================
# setup_gmail.py — Guided Gmail setup checker + connection test
#
# Run once before starting the tracker:
#   python setup_gmail.py
# =============================================================================

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import smtplib, ssl
from utils.logger import get_logger
import config

log = get_logger("setup_gmail")


def check_config() -> bool:
    print("\n" + "=" * 60)
    print("  Gmail Setup Checker")
    print("=" * 60)

    ok = True

    # SENDER_EMAIL
    if "your.gmail" in config.SENDER_EMAIL:
        print("  ✗  SENDER_EMAIL is not set")
        print("     → Edit config.py: SENDER_EMAIL = 'your.actual@gmail.com'")
        ok = False
    else:
        print(f"  ✓  SENDER_EMAIL      = {config.SENDER_EMAIL}")

    # SENDER_APP_PASSWORD
    pw = config.SENDER_APP_PASSWORD.replace(" ", "")
    if "xxxx" in config.SENDER_APP_PASSWORD or len(pw) < 16:
        print("  ✗  SENDER_APP_PASSWORD is not set")
        print()
        print("  HOW TO GET AN APP PASSWORD:")
        print("  1. Go to https://myaccount.google.com/security")
        print("  2. Enable 2-Step Verification (required)")
        print("  3. Go to https://myaccount.google.com/apppasswords")
        print("  4. App: Mail  |  Device: Windows Computer  → Generate")
        print("  5. Copy the 16-character password (e.g. abcd efgh ijkl mnop)")
        print("  6. Paste into config.py → SENDER_APP_PASSWORD")
        ok = False
    else:
        masked = pw[:4] + " **** **** " + pw[-4:]
        print(f"  ✓  SENDER_APP_PASSWORD = {masked}  (16 chars)")

    # RECIPIENT_EMAIL
    if "recipient@example.com" in config.RECIPIENT_EMAIL:
        print("  ✗  RECIPIENT_EMAIL is not set")
        print("     → Edit config.py: RECIPIENT_EMAIL = 'destination@example.com'")
        ok = False
    else:
        print(f"  ✓  RECIPIENT_EMAIL    = {config.RECIPIENT_EMAIL}")

    print()
    return ok


def test_connection() -> bool:
    """Try logging into Gmail SMTP and sending a test email."""
    print("Testing Gmail SMTP connection…")
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(config.SENDER_EMAIL, config.SENDER_APP_PASSWORD)
        print("✓ SMTP login successful.\n")
        return True

    except smtplib.SMTPAuthenticationError:
        print("✗ Authentication failed.")
        print("  → Make sure you are using an App Password, not your Gmail password.")
        print("  → App Passwords: https://myaccount.google.com/apppasswords")
        return False

    except OSError as exc:
        print(f"✗ Network error: {exc}")
        print("  → Check your internet connection.")
        return False


def send_test_email() -> None:
    """Send a real test email so you can confirm delivery end-to-end."""
    from email.mime.multipart import MIMEMultipart
    from email.mime.text      import MIMEText
    import ssl, smtplib

    print(f"Sending test email to {config.RECIPIENT_EMAIL}…")

    msg             = MIMEMultipart()
    msg["From"]     = config.SENDER_EMAIL
    msg["To"]       = config.RECIPIENT_EMAIL
    msg["Subject"]  = "Tracker App — Setup Test Email"
    msg.attach(MIMEText(
        "This is a test email from your tracker_app.\n\n"
        "If you received this, Gmail is configured correctly!\n"
        "The app will send one email per capture cycle with screenshots attached.",
        "plain",
    ))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(config.SENDER_EMAIL, config.SENDER_APP_PASSWORD)
            server.sendmail(config.SENDER_EMAIL, config.RECIPIENT_EMAIL, msg.as_string())
        print(f"✓ Test email sent! Check {config.RECIPIENT_EMAIL}\n")
    except Exception as exc:
        print(f"✗ Failed to send test email: {exc}\n")


if __name__ == "__main__":
    if not check_config():
        print("Fix the issues above in config.py, then re-run this script.\n")
        sys.exit(1)

    if not test_connection():
        sys.exit(1)

    send_test_email()
    print("Setup complete — run  python main.py  to start the tracker.")

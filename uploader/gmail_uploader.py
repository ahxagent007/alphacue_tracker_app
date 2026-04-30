# =============================================================================
# uploader/gmail_uploader.py — Send captured images as email attachments
#
# Uses Python's built-in smtplib + email modules — no Google API, no OAuth,
# no credentials.json.  Authentication is via a Gmail App Password.
#
# Usage:
#   from uploader.gmail_uploader import send_captures
#   success = send_captures(["/path/screenshot.jpg", "/path/webcam.jpg"])
# =============================================================================

import os
import smtplib
import ssl
from datetime    import datetime
from email       import encoders
from email.mime.base        import MIMEBase
from email.mime.multipart   import MIMEMultipart
from email.mime.text        import MIMEText

from config import (
    SENDER_EMAIL,
    SENDER_APP_PASSWORD,
    RECIPIENT_EMAIL,
    EMAIL_SUBJECT,
)
from utils.logger import get_logger

log = get_logger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465          # SSL — no STARTTLS needed


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_message(filepaths: list[str]) -> MIMEMultipart:
    """Construct a MIME email with all files attached.

    Args:
        filepaths: List of absolute paths to attach.

    Returns:
        A ready-to-send :class:`MIMEMultipart` message object.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subject   = EMAIL_SUBJECT.format(timestamp=timestamp)

    msg = MIMEMultipart()
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECIPIENT_EMAIL
    msg["Subject"] = subject

    # Plain-text body
    body_lines = [
        f"Tracker capture — {timestamp}",
        f"Attachments: {len(filepaths)} file(s)",
        "",
    ]
    for fp in filepaths:
        size_kb = os.path.getsize(fp) / 1024 if os.path.exists(fp) else 0
        body_lines.append(f"  • {os.path.basename(fp)}  ({size_kb:.1f} KB)")

    msg.attach(MIMEText("\n".join(body_lines), "plain"))

    # Attach each file
    for filepath in filepaths:
        if not os.path.exists(filepath):
            log.warning("Attachment not found, skipping: %s", filepath)
            continue
        _attach_file(msg, filepath)

    return msg


def _attach_file(msg: MIMEMultipart, filepath: str) -> None:
    """Attach a single file to *msg* as a binary attachment."""
    filename = os.path.basename(filepath)
    try:
        with open(filepath, "rb") as fh:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(fh.read())

        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            "attachment",
            filename=filename,
        )
        msg.attach(part)
        log.debug("Attached: %s  (%.1f KB)", filename, os.path.getsize(filepath) / 1024)

    except OSError:
        log.exception("Failed to attach file: %s", filepath)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def send_captures(filepaths: list[str]) -> bool:
    """Send all files in *filepaths* as email attachments via Gmail SMTP.

    Args:
        filepaths: Absolute paths to the files to attach and send.

    Returns:
        ``True`` on success, ``False`` on any failure.
    """
    if not filepaths:
        log.warning("send_captures called with empty file list — nothing to send.")
        return False

    # Config validation — catch placeholder values before hitting the network
    if "your.gmail" in SENDER_EMAIL or SENDER_EMAIL == "your.gmail@gmail.com":
        log.error(
            "SENDER_EMAIL is not configured — edit config.py with your Gmail address."
        )
        return False

    if "xxxx" in SENDER_APP_PASSWORD or len(SENDER_APP_PASSWORD.replace(" ", "")) < 16:
        log.error(
            "SENDER_APP_PASSWORD is not configured — "
            "edit config.py with your 16-character Gmail App Password."
        )
        return False

    if "recipient@example.com" in RECIPIENT_EMAIL:
        log.error(
            "RECIPIENT_EMAIL is not configured — edit config.py with the destination address."
        )
        return False

    names = [os.path.basename(f) for f in filepaths]
    log.debug("Sending email to %s with attachments: %s", RECIPIENT_EMAIL, names)

    try:
        msg = _build_message(filepaths)

        # SSL context — enforces certificate verification
        context = ssl.create_default_context()

        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())

        log.info(
            "Email sent → %s  |  %d attachment(s): %s",
            RECIPIENT_EMAIL, len(filepaths), ", ".join(names),
        )
        return True

    except smtplib.SMTPAuthenticationError:
        log.error(
            "Gmail authentication failed.\n"
            "  → Check SENDER_EMAIL and SENDER_APP_PASSWORD in config.py.\n"
            "  → Make sure you are using an App Password, not your regular password.\n"
            "  → App Passwords: https://myaccount.google.com/apppasswords"
        )
        return False

    except smtplib.SMTPRecipientsRefused:
        log.error(
            "Recipient address refused: %s\n"
            "  → Check RECIPIENT_EMAIL in config.py.",
            RECIPIENT_EMAIL,
        )
        return False

    except smtplib.SMTPException as exc:
        log.error("SMTP error sending email: %s", exc)
        return False

    except OSError as exc:
        # Network unreachable, DNS failure, connection timeout, etc.
        log.error(
            "Network error sending email: %s\n"
            "  → Check your internet connection.",
            exc,
        )
        return False

    except Exception:
        log.exception("Unexpected error sending email")
        return False

from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)


def _smtp_config():
    """Resolve SMTP host/port/credentials from env.

    Prefer Gmail via the App Password (one credential, no Brevo). Google shows
    App Passwords with spaces; strip them. Falls back to a generic SMTP relay
    (e.g. Brevo) only when Gmail creds are absent. Returns
    (host, port, username, password, from_addr, gmail_user).
    """
    gmail_user = os.getenv("GMAIL_ADDRESS") or None
    gmail_pass = (os.getenv("GMAIL_APP_PASSWORD") or "").replace(" ", "") or None

    if gmail_user and gmail_pass:
        host, port = "smtp.gmail.com", 587
        username, password = gmail_user, gmail_pass
        from_addr = gmail_user  # Gmail requires From to be the authenticated account
    else:
        # `or` fallbacks: CI renders unset secrets as empty strings, not missing vars.
        host = os.getenv("SMTP_HOST") or None
        port = int(os.getenv("SMTP_PORT") or "587")
        username = os.getenv("SMTP_USERNAME") or None
        password = os.getenv("SMTP_PASSWORD") or None
        from_addr = os.getenv("REPORT_FROM_EMAIL") or username

    return host, port, username, password, from_addr, gmail_user


def send_email(to_addr: str, subject: str, body: str) -> bool:
    """Send a single email over SMTP to an arbitrary recipient (stdlib smtplib).

    Env-gated: if SMTP settings are absent this logs a warning and returns
    False so the pipeline (and CI without secrets) still exits 0.
    """
    host, port, username, password, from_addr, _ = _smtp_config()

    if not (host and to_addr and from_addr):
        logger.warning(
            "Email not configured (set GMAIL_ADDRESS + GMAIL_APP_PASSWORD, or "
            "SMTP_HOST + REPORT_FROM_EMAIL); skipping email send."
        )
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.ehlo()
            if smtp.has_extn("starttls"):
                smtp.starttls()
                smtp.ehlo()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        logger.warning("Email send failed: %s", exc)
        return False
    logger.info("Email sent to %s via %s:%s", to_addr, host, port)
    return True


def send_report_email(report_markdown: str, subject: str) -> bool:
    """Send the daily report over SMTP (stdlib smtplib — Decision 1, Option A).

    Env-gated: if SMTP settings are absent this logs a warning and returns
    False so the pipeline (and CI without secrets) still exits 0.
    """
    _, _, _, _, _, gmail_user = _smtp_config()
    to_addr = os.getenv("REPORT_TO_EMAIL") or gmail_user
    return send_email(to_addr, subject, report_markdown)

from __future__ import annotations

"""Read BizBuySell alert emails from Gmail over IMAP.

The alerts land in rainking6693@gmail.com, which the connected Gmail app can't
read (that connector is a different workspace account). IMAP reads the operator's
Gmail directly and works unattended in the cron. Env-gated and stdlib-only:
- GMAIL_ADDRESS       the mailbox to read (rainking6693@gmail.com)
- GMAIL_APP_PASSWORD  a Gmail App Password (needs 2FA enabled on the account)

Returns the best body (HTML preferred) of each matching message. Never raises to
the caller — on any failure it logs and returns []. The same app password can
also send via smtp.gmail.com, replacing the Brevo relay if desired.
"""

import email
import imaplib
import logging
import os
from email.message import Message
from typing import List, Optional

logger = logging.getLogger(__name__)

IMAP_HOST = "imap.gmail.com"


def imap_configured() -> bool:
    return bool(os.getenv("GMAIL_ADDRESS") and os.getenv("GMAIL_APP_PASSWORD"))


def _best_body(msg: Message) -> str:
    html: Optional[str] = None
    plain: Optional[str] = None
    for part in msg.walk():
        ctype = part.get_content_type()
        if part.get_content_disposition() == "attachment":
            continue
        if ctype not in ("text/html", "text/plain"):
            continue
        try:
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        except Exception:
            continue
        if ctype == "text/html":
            html = text
        else:
            plain = text
    return html or plain or ""


def fetch_alert_bodies(
    sender: str = "bizbuysell.com",
    since_days: int = 7,
    limit: int = 100,
) -> List[str]:
    """Return the bodies of recent alert emails from `sender`. [] if unconfigured."""
    address = os.getenv("GMAIL_ADDRESS") or None
    # Google displays App Passwords with spaces ("abcd efgh ..."); login needs them removed.
    password = (os.getenv("GMAIL_APP_PASSWORD") or "").replace(" ", "") or None
    if not (address and password):
        logger.warning(
            "IMAP not configured (need GMAIL_ADDRESS and GMAIL_APP_PASSWORD); "
            "skipping alert fetch."
        )
        return []

    bodies: List[str] = []
    try:
        with imaplib.IMAP4_SSL(IMAP_HOST) as imap:
            imap.login(address, password)
            # Read All Mail (not INBOX): alerts get archived out of the inbox
            # before the nightly run sees them — observed 2026-07-19, when 37
            # alerts existed in All Mail but 0 remained in INBOX. Read-only so
            # fetching never marks messages seen or otherwise mutates the box.
            status, _ = imap.select('"[Gmail]/All Mail"', readonly=True)
            if status != "OK":
                imap.select("INBOX", readonly=True)
            # Gmail IMAP understands the SINCE and FROM search keys.
            from datetime import date, timedelta
            since = (date.today() - timedelta(days=since_days)).strftime("%d-%b-%Y")
            status, data = imap.search(None, "FROM", sender, "SINCE", since)
            if status != "OK":
                logger.warning("IMAP search failed: %s", status)
                return []
            all_ids = data[0].split()
            if len(all_ids) > limit:
                logger.warning("IMAP: %d matching emails exceed limit=%d; "
                               "processing the newest %d.", len(all_ids), limit, limit)
            ids = all_ids[-limit:]
            for msg_id in ids:
                status, msg_data = imap.fetch(msg_id, "(RFC822)")
                if status != "OK" or not msg_data or not msg_data[0]:
                    continue
                msg = email.message_from_bytes(msg_data[0][1])
                body = _best_body(msg)
                if body:
                    bodies.append(body)
    except Exception as exc:  # auth / network / IMAP disabled — never crash
        logger.warning("IMAP fetch failed: %s", exc)
        return []

    logger.info("Fetched %d alert email(s) from %s.", len(bodies), sender)
    return bodies

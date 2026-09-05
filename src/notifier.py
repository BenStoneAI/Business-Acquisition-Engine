from __future__ import annotations

"""Telegram alert for the daily radar.

When a run finds reportable deals, push a short summary to the operator's
Telegram so they know to pull Claude in for enrichment + outreach. Env-gated
like the rest of the platform: with no bot token / chat id it logs a warning and
returns False (CI without secrets still exits 0). No third-party dependency —
the Bot API is a plain HTTPS POST via stdlib `urllib`.
"""

import json
import logging
import os
import urllib.parse
import urllib.request
from datetime import date
from typing import Callable, List, Tuple

from .financing_filter import financing_status
from .models import Listing, ScoreBreakdown
from .reporting import money

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"
MAX_MESSAGE = 4000  # Telegram hard limit is 4096; leave headroom.

Transport = Callable[[str, bytes], dict]


def _post(url: str, data: bytes) -> dict:
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 (fixed host)
        return json.loads(resp.read().decode("utf-8"))


def telegram_configured() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def build_alert(
    scored: List[Tuple[Listing, ScoreBreakdown]],
    min_score: float = 70,
    limit: int = 10,
) -> str:
    """Summarize the reportable deals; empty string when there is nothing to send."""
    top = sorted(
        [x for x in scored if x[1].total_score >= min_score],
        key=lambda x: x[1].total_score,
        reverse=True,
    )[:limit]
    if not top:
        return ""

    lines = [f"\U0001F3E2 Boring Business Radar — {len(top)} deal(s) to review", ""]
    for listing, score in top:
        lines.append(f"• {listing.business_name} — {listing.location}")
        lines.append(
            f"  {score.total_score}/100 {score.bucket} | ask {money(listing.asking_price)} "
            f"| financing: {financing_status(listing)}"
        )
        if listing.listing_url:
            lines.append(f"  {listing.listing_url}")
    lines.append("")
    lines.append("Tell Claude which one to enrich + package.")
    return "\n".join(lines)


def send_telegram(text: str, transport: Transport = _post) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN") or None
    chat_id = os.getenv("TELEGRAM_CHAT_ID") or None
    if not (token and chat_id):
        logger.warning(
            "Telegram not configured (need TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID); "
            "skipping alert."
        )
        return False

    payload = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text[:MAX_MESSAGE],
        "disable_web_page_preview": "true",
    }).encode("utf-8")
    try:
        resp = transport(f"{TELEGRAM_API}/bot{token}/sendMessage", payload)
    except Exception as exc:  # network / auth — never break the pipeline
        logger.warning("Telegram send error: %s", exc)
        return False
    if not resp.get("ok"):
        logger.warning("Telegram send failed: %s", resp)
        return False
    logger.info("Telegram alert sent.")
    return True


def build_heartbeat(parsed: int, fresh: int, built: int, min_score: float) -> str:
    """One-line liveness ping for runs with nothing to alert.

    Without this, 'no qualifying deals' and 'pipeline dead' look identical to
    the operator — the failure mode that hid 4 days of missed runs in July 2026.
    """
    return (
        f"✅ Radar ran {date.today().isoformat()}: {parsed} listing(s) parsed, "
        f"{fresh} new, {built} packet(s) at or above {min_score:g}."
    )


def notify_daily(
    scored: List[Tuple[Listing, ScoreBreakdown]],
    min_score: float = 70,
    transport: Transport = _post,
) -> bool:
    alert = build_alert(scored, min_score=min_score)
    if not alert:
        logger.info("No reportable deals; skipping Telegram alert.")
        return False
    return send_telegram(alert, transport=transport)

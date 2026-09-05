from __future__ import annotations

"""Cross-run ingest state: which listings have already been alerted/packeted.

The IMAP fetch window (`since_days`) intentionally overlaps between nightly
runs so a missed night never loses alerts — but that means the same alert email
is parsed on consecutive runs. This state file (JSON, {key: {"last_seen":
"YYYY-MM-DD", "asking_price": float|null}}, keyed by listing_url) is what
prevents duplicate Telegram alerts and rebuilt deal packets. Lives in data/
(gitignored, local-only). Entries not seen for PRUNE_DAYS are dropped on save
so the file stays small.

Legacy entries written before price tracking was added are plain
{key: "YYYY-MM-DD"} strings; `load_processed` upgrades them transparently to
{"last_seen": <str>, "asking_price": None} in memory, so no manual migration
of the existing state file is needed.

A listing whose price drops is the strongest seller-motivation signal in this
thesis, so it is NOT silently skipped: `detect_price_drops` re-surfaces any
previously-seen listing whose asking price fell >=5% since it was last
recorded (see src/ingest_bizbuysell.py).
"""

import json
import logging
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .models import Listing

logger = logging.getLogger(__name__)

PRUNE_DAYS = 180
PRICE_DROP_THRESHOLD = 0.05  # >=5% lower re-alerts; guards against parse noise

_QUERY_ID = re.compile(r"[?&]q=(\d{4,})")
_NUMERIC_ID = re.compile(r"/(\d{5,})(?:[/?#]|$)")


def listing_key(listing: Listing) -> str:
    """Canonical dedup key: numeric listing id when the URL carries one
    (live alerts: ?q=2398358; listing pages: /2101010/), else the URL
    stripped of query params/trailing slash, else the name. Raw URL strings
    vary per email (utm tracking params) and must never be trusted as identity."""
    url = listing.listing_url
    if not url:
        return listing.business_name
    m = _QUERY_ID.search(url) or _NUMERIC_ID.search(url)
    if m:
        return m.group(1)
    return url.split("?")[0].rstrip("/").lower()


_key = listing_key


def _normalize_entry(value) -> Dict[str, Optional[float]]:
    """Upgrade a legacy plain-string entry to the {last_seen, asking_price} shape."""
    if isinstance(value, str):
        return {"last_seen": value, "asking_price": None}
    if isinstance(value, dict):
        return {"last_seen": value.get("last_seen"), "asking_price": value.get("asking_price")}
    return {"last_seen": None, "asking_price": None}


def _last_seen(value) -> str:
    if isinstance(value, dict):
        return value.get("last_seen") or ""
    return value or ""


def _stored_price(value) -> Optional[float]:
    if isinstance(value, dict):
        return value.get("asking_price")
    return None


def load_processed(path: str | Path) -> Dict[str, dict]:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        return {k: _normalize_entry(v) for k, v in data.items()}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read ingest state %s (%s); starting fresh.", path, exc)
        return {}


def filter_unprocessed(listings: List[Listing], processed: Dict[str, dict]) -> List[Listing]:
    return [l for l in listings if _key(l) not in processed]


def detect_price_drops(
    listings: List[Listing], processed: Dict[str, dict]
) -> List[Tuple[Listing, float]]:
    """Previously-seen listings whose asking price fell >=PRICE_DROP_THRESHOLD.

    Only fires when the stored price is a real number and the new price is a
    real number lower than it by the threshold — protects against parse noise
    (missing prices, OCR jitter) generating false alerts.
    """
    drops = []
    for listing in listings:
        entry = processed.get(_key(listing))
        if entry is None:
            continue
        old_price = _stored_price(entry)
        new_price = listing.asking_price
        if not isinstance(old_price, (int, float)) or not isinstance(new_price, (int, float)):
            continue
        if old_price <= 0 or new_price >= old_price:
            continue
        if (old_price - new_price) / old_price >= PRICE_DROP_THRESHOLD:
            drops.append((listing, old_price))
    return drops


def mark_processed(processed: Dict[str, dict], listings: List[Listing],
                   day: Optional[date] = None) -> None:
    stamp = (day or date.today()).isoformat()
    for listing in listings:
        processed[_key(listing)] = {"last_seen": stamp, "asking_price": listing.asking_price}


def save_processed(processed: Dict[str, dict], path: str | Path,
                   day: Optional[date] = None) -> None:
    cutoff = ((day or date.today()) - timedelta(days=PRUNE_DAYS)).isoformat()
    pruned = {k: v for k, v in processed.items() if _last_seen(v) >= cutoff}
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(pruned, indent=0, sort_keys=True), encoding="utf-8")

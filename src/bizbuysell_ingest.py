from __future__ import annotations

"""Parse BizBuySell 'Listings by Email' alerts into Listing objects.

The operator runs a saved search on BizBuySell's *owner-financed* section
(filtered to the target industries + Mountain West). BizBuySell emails new
matches daily. This module turns one of those alert emails into structured
`Listing` rows for the existing scoring pipeline. Because the source is the
owner-financed feed, `seller_financing` defaults to True; the downstream
`financing_filter` then narrows to the 100%/possible-100% subset.

Parsing is intentionally resilient: it strips HTML to text, splits the body into
per-listing blocks around BizBuySell listing URLs, and extracts labeled fields
by regex. The exact field labels in a live alert may need a one-line tweak — see
CALIBRATION note in tests once a real alert is available.
"""

import logging
import re
from html import unescape
from typing import List, Optional

from .financing_filter import MAJORITY_FLOOR, stated_cap_pct
from .models import Listing

logger = logging.getLogger(__name__)

_LISTING_URL = re.compile(r"https?://(?:www\.)?bizbuysell\.com/[^\s\"'<>)]+", re.I)
# Amounts appear as "$850,000", "$1.2M", "1.5 million", "155K".
_AMOUNT = r"([\d,]+(?:\.\d+)?)\s*(million|thousand|[MmKk])?\b"
_PRICE = re.compile(r"Asking Price[:\s]*\$?\s*" + _AMOUNT, re.I)
_CASHFLOW = re.compile(r"Cash Flow[:\s]*\$?\s*" + _AMOUNT, re.I)
_REVENUE = re.compile(r"(?:Gross Revenue|Gross Sales|Revenue|Sales)[:\s]*\$?\s*" + _AMOUNT, re.I)
# A URL block with no parseable price can still be a real listing ("Inquire for
# price") — recognize it by other listing-field labels before discarding.
_LISTING_SIGNAL = re.compile(
    r"Cash Flow|Gross Revenue|Gross Sales|Seller Financing|Inquire", re.I)
_LOCATION = re.compile(r"\b([A-Z][A-Za-z.\-]+(?:[ ][A-Z][A-Za-z.\-]+){0,3},[ ]*[A-Z]{2})\b")

# Broker contact extraction (best-effort — only set keys that are actually
# found in a listing block; see CALIBRATION note above).
_EMAIL = re.compile(r"(?:mailto:)?([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", re.I)
_GENERIC_EMAIL_PREFIX = re.compile(
    r"^(?:noreply|no-reply|donotreply|do-not-reply|unsubscribe)@", re.I)
# Require explicit separators between digit groups to avoid matching stray
# 10-digit runs inside prices/ids.
_PHONE = re.compile(r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}(?!\d)")
_BROKER_LABEL = r"(?:Contact|Broker|Listed by|Listing Agent|Agent)"
# Words that mark the start of the *next* labeled field — stop the name capture
# before swallowing into "... Jane Roberts Contact: jane@..." style runs.
_FIELD_LABEL_WORDS = (
    r"(?:Contact|Broker|Phone|Email|Cash|Gross|Asking|Seller|Owner|Listed|"
    r"Listing|Agent|Revenue|Sales)"
)
_BROKER_NAME = re.compile(
    r"(?i:" + _BROKER_LABEL + r")\s*[:\-]\s*"
    r"([A-Z][A-Za-z.'-]+(?:\s(?!" + _FIELD_LABEL_WORDS + r"\b)[A-Z][A-Za-z.'-]+){0,2})"
)

_INDUSTRY_KEYWORDS = [
    ("hvac", ("hvac", "heating", "air conditioning", "heating & cooling")),
    ("plumbing", ("plumbing", "plumber")),
    ("electrical", ("electrical", "electrician")),
    ("laundromat", ("laundromat", "laundry", "coin laundry")),
    ("pest_control", ("pest control", "exterminat")),
    ("commercial_cleaning", ("commercial cleaning", "janitorial", "cleaning service")),
    ("pool_service", ("pool service", "pool route", "pool cleaning")),
    ("self_storage", ("self storage", "self-storage", "storage facility")),
    ("car_wash", ("car wash", "carwash")),
    ("roofing", ("roofing", "roofer")),
    # Off-thesis industries the owner-financed feed actually sends (pizzerias,
    # auto shops, retail). Naming them routes them to honest low base scores in
    # industry_formulas.yaml instead of the 75-point "other" default.
    ("restaurant", ("pizzeria", "pizza", "restaurant", "cafe", "bakery", "deli",
                    "food truck", "sandwich", "catering")),
    ("auto_repair", ("auto repair", "auto shop", "mechanic", "tire", "oil change",
                     "body shop", "car repair", "transmission")),
    ("retail", ("retail", "boutique", "frame shop", "gift shop", "liquor store",
                "convenience store", "smoke shop", "clothing store")),
]

# Sub-100% cap detection is shared with the financing filter
# (financing_filter.stated_cap_below_100) so the two layers can't disagree.


def html_to_text(body: str) -> str:
    body = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", body)
    # keep listing URLs that live in href attributes
    body = re.sub(r'(?is)<a\b[^>]*?href\s*=\s*["\']([^"\']+)["\'][^>]*>', r" \1 ", body)
    body = re.sub(r"(?s)<[^>]+>", " ", body)
    return unescape(re.sub(r"[ \t ]+", " ", body))


def _infer_industry(text: str) -> str:
    low = text.lower()
    for key, words in _INDUSTRY_KEYWORDS:
        if any(w in low for w in words):
            return key
    return "other"


_SUFFIX_MULTIPLIER = {"m": 1e6, "million": 1e6, "k": 1e3, "thousand": 1e3}


def _num(match: Optional[re.Match]) -> Optional[float]:
    if not match:
        return None
    value = float(match.group(1).replace(",", ""))
    suffix = (match.group(2) or "").lower()
    return value * _SUFFIX_MULTIPLIER.get(suffix, 1)


def _listing_id(url: str) -> str:
    # Live alert URLs carry the id as a query param (/listings/Profile/?q=2398358);
    # older/canonical listing pages carry it in the path (/x/2101010/).
    m = re.search(r"[?&]q=(\d{4,})", url) or re.search(r"/(\d{5,})/?", url)
    return m.group(1) if m else url


def _canonical_url(url: str) -> str:
    """One stable URL per listing: keep the identifying q param, drop the
    per-send utm_* tracking params that defeat every dedup layer."""
    url = url.rstrip(".,);")
    m = re.search(r"[?&]q=(\d{4,})", url)
    if m:
        return f"{url.split('?')[0]}?q={m.group(1)}"
    return url.split("?")[0]


def _extract_broker_email(block: str) -> Optional[str]:
    for m in _EMAIL.finditer(block):
        email = m.group(1)
        if _GENERIC_EMAIL_PREFIX.match(email):
            continue
        return email
    return None


def _extract_broker_phone(block: str) -> Optional[str]:
    m = _PHONE.search(block)
    return m.group(0).strip() if m else None


def _extract_broker_name(block: str) -> Optional[str]:
    m = _BROKER_NAME.search(block)
    return m.group(1).strip() if m else None


def _title_from(block: str, location: Optional[str]) -> str:
    # In alert HTML the href precedes the visible title; strip URLs, then take the
    # text before the first labeled field (that's the title, maybe + location).
    head = re.split(r"(?:Asking Price|Cash Flow|Gross Revenue|Revenue|Sales)", block, 1, re.I)[0]
    head = _LISTING_URL.sub(" ", head)
    if location:
        head = head.replace(location, " ")
    head = re.sub(r"\s{2,}", " ", head).strip(" -|·\t")
    return (head or "Unknown Business")[:120]


def parse_alert(body: str) -> List[Listing]:
    """Parse one BizBuySell alert email (HTML or plaintext) into Listings.

    Each listing block runs from its URL to the next URL. Blocks without a price
    are secondary links (image/broker) within a listing and are skipped; blocks
    are de-duplicated by BizBuySell listing id.
    """
    text = html_to_text(body)
    matches = list(_LISTING_URL.finditer(text))
    listings: List[Listing] = []
    seen_ids: set[str] = set()

    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[m.start():end]
        price = _PRICE.search(block)
        if not price and not _LISTING_SIGNAL.search(block):
            continue  # image/broker link within a listing, or a nav link
        url = _canonical_url(m.group(0))
        lid = _listing_id(url)
        if lid in seen_ids:
            continue
        seen_ids.add(lid)

        loc_match = _LOCATION.search(block)
        location = loc_match.group(1) if loc_match else None
        # Financing is "on the table" unless the blurb caps the carry below the
        # majority floor — a 60% stated carry is still seller financing.
        cap = stated_cap_pct(block.lower())
        capped = cap is not None and cap < MAJORITY_FLOOR

        raw: dict = {}
        broker_email = _extract_broker_email(block)
        if broker_email:
            raw["broker_email"] = broker_email
        broker_phone = _extract_broker_phone(block)
        if broker_phone:
            raw["broker_phone"] = broker_phone
        broker_name = _extract_broker_name(block)
        if broker_name:
            raw["broker_name"] = broker_name

        listings.append(Listing(
            business_name=_title_from(block, location),
            industry=_infer_industry(block),
            location=location or "Unknown",
            asking_price=_num(price),
            revenue=_num(_REVENUE.search(block)),
            sde=_num(_CASHFLOW.search(block)),
            # Source is the owner-financed feed: financing is on the table unless
            # the blurb explicitly states a sub-100% cap.
            seller_financing=not capped,
            seller_financing_terms=(block.strip()[-300:] if capped else None),
            reason_for_sale=None,
            source="BizBuySell (email alert)",
            listing_url=url,
            notes=block.strip()[:600],
            raw=raw,
        ))

    logger.info("Parsed %d listing(s) from BizBuySell alert.", len(listings))
    return listings

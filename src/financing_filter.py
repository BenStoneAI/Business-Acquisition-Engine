from __future__ import annotations

"""100% seller-financing screen.

The radar only surfaces deals that are either explicitly 100% seller financed
or leave the door open to it ("possibility of 100%"). This is a screening
filter applied BEFORE scoring — it never touches `score_listing()` (Hard
Constraint 1). Detection is deterministic keyword/regex logic over the free-text
fields, so the decision is reproducible and testable.

Status meanings:
- "full"           — explicit evidence of 100% / full seller carry
- "possible"       — seller financing offered with no stated cap below 100%
- "majority_carry" — stated cap between 50% and 99% (qualifies; negotiate up)
- "partial_capped" — seller financing explicitly capped below 50%
- "none"           — no seller financing, or third-party/bank/cash only
"""

import re
from typing import List, Optional, Tuple

from .models import Listing

FULL = "full"
POSSIBLE = "possible"
MAJORITY = "majority_carry"
PARTIAL_CAPPED = "partial_capped"
NONE = "none"

# Screen on quality, negotiate on structure (2026-07-19 strategy change, per
# the ETA best-practices research): a stated majority carry (>=50%) qualifies —
# a motivated solo buyer can negotiate the rest. Only sub-50% caps and explicit
# no-financing listings are dropped.
MAJORITY_FLOOR = 50

QUALIFYING = {FULL, POSSIBLE, MAJORITY}

# Explicit 100% / full-carry evidence. Attribution to the seller/owner is
# required — "SBA 100% financing" is not seller carry (it still qualifies as
# POSSIBLE downstream when the seller_financing flag or a mention is present).
_FULL_PATTERNS = [
    r"100\s*%?\s*(?:seller|owner)\s*financ",
    r"(?:seller|owner)\s*financ\w*\s*(?:up to\s*)?100",
    r"100\s*%?\s*(?:seller|owner)\s*carr",
    r"full\s+seller\s+carry",
    r"full\s+owner\s+carry",
    r"fully\s+(?:seller|owner)[\s-]?financ",
    r"(?:seller|owner)\s+will\s+carry\s+(?:the\s+)?(?:full|100)",
    r"100\s*%?\s*owner\s+carry",
]

# Any seller/owner-financing mention (signals "possibility").
_FINANCING_MENTION = [
    r"seller\s+financ",
    r"owner\s+financ",
    r"seller\s+will\s+finance",
    r"owner\s+will\s+finance",
    r"seller\s+carr",
    r"owner\s+carr",
    r"seller\s+note",
    r"owner\s+note",
    r"owner\s+carry",
]

# Explicit exclusions — financing is off the table.
_NONE_PATTERNS = [
    r"no\s+seller\s+financ",
    r"no\s+owner\s+financ",
    r"seller\s+financing\s*[:\-]?\s*no\b",
    r"without\s+seller\s+financ",
    r"third[\s-]?party\s+financing\s+only",
    r"bank\s+financing\s+only",
    r"sba\s+(?:financing\s+)?only",
    r"cash\s+(?:buyers?\s+)?only",
]

# A stated seller contribution capped below 100%, e.g. "finance 25 percent",
# "will carry 20%", "seller note of 30%". Down-payment percentages are excluded
# from this test on purpose (a small down payment can still leave a large carry):
# any match whose surrounding text mentions "down" is a down payment, not a cap.
_PARTIAL_CAP = re.compile(
    r"(?:finance|carry|seller\s+note|owner\s+note)\D{0,20}?(\d{1,3})\s*(?:%|percent)"
    r"|(\d{1,3})\s*(?:%|percent)\D{0,20}?(?:seller|owner)\s*(?:financ|carr|note)",
    re.IGNORECASE,
)


def stated_cap_pct(text: str) -> Optional[int]:
    """The smallest stated seller-financing cap under 100%, or None.

    Down-payment percentages ("with 10% down", "10% down payment, owner
    carries the balance") are not caps — they describe the buyer's equity,
    and often accompany a 90%+ carry.
    """
    caps = []
    for match in _PARTIAL_CAP.finditer(text):
        window = text[max(0, match.start() - 25):match.end() + 25]
        if "down" in window:
            continue
        pct = next((int(g) for g in match.groups() if g is not None), None)
        if pct is not None and pct < 100:
            caps.append(pct)
    return min(caps) if caps else None


def stated_cap_below_100(text: str) -> bool:
    return stated_cap_pct(text) is not None


def _text(listing: Listing) -> str:
    parts = [
        listing.reason_for_sale or "",
        listing.seller_financing_terms or "",
        listing.notes or "",
    ]
    return " ".join(parts).lower()


def financing_status(listing: Listing) -> str:
    text = _text(listing)

    if any(re.search(p, text) for p in _FULL_PATTERNS):
        return FULL

    cap = stated_cap_pct(text)
    if cap is not None:
        return MAJORITY if cap >= MAJORITY_FLOOR else PARTIAL_CAPPED

    if any(re.search(p, text) for p in _NONE_PATTERNS):
        return NONE

    if listing.seller_financing or any(re.search(p, text) for p in _FINANCING_MENTION):
        return POSSIBLE

    return NONE


def qualifies(listing: Listing) -> bool:
    """True when the listing offers, or could offer, a majority (>=50%) or
    full seller-financed structure."""
    return financing_status(listing) in QUALIFYING


def filter_full_seller_financing(
    listings: List[Listing],
) -> Tuple[List[Listing], List[Listing]]:
    """Split listings into (kept, dropped) by the 100%-seller-financing screen."""
    kept: List[Listing] = []
    dropped: List[Listing] = []
    for listing in listings:
        (kept if qualifies(listing) else dropped).append(listing)
    return kept, dropped

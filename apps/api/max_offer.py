"""Four max-offer constraints from the same formulas as src.scoring.estimate_values.

Does not change score_listing(). Used only to label which bound won (RD-05).
"""

from __future__ import annotations

from typing import Any

from src.models import Listing
from src.scoring import estimate_values


def max_offer_constraints(listing: Listing, industry_config: dict[str, Any]) -> dict[str, Any]:
    low, high, max_offer = estimate_values(listing, industry_config)
    if not listing.sde:
        return {
            "estimated_value_low": low,
            "estimated_value_high": high,
            "estimated_max_offer": max_offer,
            "sde_multiple": None,
            "dscr_1_75": None,
            "cash_on_cash_25": None,
            "payback_4yr": None,
            "binding": None,
        }
    sde = float(listing.sde)
    sde_multiple = sde * float(industry_config.get("target_multiple_high", 3.0))
    annual_debt_service_capacity = sde / 1.75
    dscr = annual_debt_service_capacity / 0.1627
    coc = sde / 0.30
    payback = sde * 4.0
    named = {
        "sde_multiple": sde_multiple,
        "dscr_1_75": dscr,
        "cash_on_cash_25": coc,
        "payback_4yr": payback,
    }
    binding = min(named, key=lambda k: named[k])
    return {
        "estimated_value_low": low,
        "estimated_value_high": high,
        "estimated_max_offer": max_offer,
        "sde_multiple": sde_multiple,
        "dscr_1_75": dscr,
        "cash_on_cash_25": coc,
        "payback_4yr": payback,
        "binding": binding,
    }

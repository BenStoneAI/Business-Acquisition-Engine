from __future__ import annotations

import logging
import math
import re
from typing import Dict, Any, Optional, List

from .models import Listing, ScoreBreakdown

logger = logging.getLogger(__name__)


MASTER_WEIGHTS = {
    "financial": 0.30,
    "industry": 0.15,
    "recurring_revenue": 0.15,
    "seller_motivation": 0.10,
    "owner_independence": 0.10,
    "financing_fit": 0.10,
    "growth_upside": 0.05,
    "risk": 0.05,
}

DEFAULT_INDUSTRY = {
    "display_name": "Other Essential Service",
    "base_score": 75,
    "target_multiple_low": 2.0,
    "target_multiple_high": 3.0,
}


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def _term_present(text: str, term: str) -> bool:
    # Whole-word match (plural tolerated). Bare `term in text` fabricated flags:
    # "lien" is a substring of "clients", "environmental" of "environmentally".
    return re.search(r"\b" + re.escape(term) + r"s?\b", text) is not None


def normalized_industry_key(industry: str) -> str:
    return industry.strip().lower().replace(" ", "_").replace("-", "_")


def cash_flow_yield(listing: Listing) -> Optional[float]:
    if not listing.asking_price or not listing.sde or listing.asking_price <= 0:
        return None
    return listing.sde / listing.asking_price


def financial_score(listing: Listing) -> float:
    cfy = cash_flow_yield(listing)
    if cfy is None:
        return 35
    if cfy >= 0.40:
        return 100
    if cfy >= 0.30:
        return 90
    if cfy >= 0.25:
        return 80
    if cfy >= 0.20:
        return 65
    if cfy >= 0.15:
        return 45
    return 20


def recurring_revenue_score(listing: Listing) -> float:
    pct = listing.recurring_revenue_pct
    industry = normalized_industry_key(listing.industry)
    if pct is None:
        # Default assumptions by industry if listing does not disclose recurring revenue.
        defaults = {
            "pest_control": 85,
            "commercial_cleaning": 80,
            "hvac": 65,
            "pool_service": 80,
            "self_storage": 75,
            "laundromat": 60,
            "plumbing": 45,
            "electrical": 45,
            "roofing": 30,
            "car_wash": 55,
        }
        return defaults.get(industry, 45)
    if pct >= 0.70:
        return 100
    if pct >= 0.50:
        return 85
    if pct >= 0.30:
        return 70
    if pct >= 0.15:
        return 50
    return 25


def seller_motivation_score(listing: Listing) -> float:
    text = f"{listing.reason_for_sale or ''} {listing.notes or ''}".lower()
    score = 40
    if any(term in text for term in ["retire", "retiring", "retirement"]):
        score += 40
    if any(term in text for term in ["health", "burnout", "relocat", "estate", "divorce"]):
        score += 25
    if listing.seller_financing:
        score += 20
    if "owner will train" in text or "training" in text:
        score += 10
    return clamp(score)


def owner_independence_score(listing: Listing) -> float:
    score = 50
    if listing.owner_hours_per_week is not None:
        if listing.owner_hours_per_week <= 10:
            score += 35
        elif listing.owner_hours_per_week <= 25:
            score += 20
        elif listing.owner_hours_per_week <= 40:
            score += 5
        else:
            score -= 25
    if listing.employees and listing.employees >= 5:
        score += 10
    if "manager" in (listing.notes or "").lower():
        score += 15
    if "absentee" in (listing.notes or "").lower():
        score += 25
    return clamp(score)


def financing_fit_score(listing: Listing) -> float:
    score = 35
    if listing.seller_financing:
        score += 35
    if listing.sba_prequalified:
        score += 20
    if listing.real_estate_included:
        score += 10
    if listing.asking_price and listing.sde:
        cfy = listing.sde / listing.asking_price
        if cfy >= 0.30:
            score += 15
        elif cfy < 0.20:
            score -= 20
    return clamp(score)


def growth_upside_score(listing: Listing) -> float:
    text = (listing.notes or "").lower()
    score = 50
    upside_terms = [
        "no website", "poor website", "no seo", "no crm", "paper", "manual", "no ads",
        "under-marketed", "below market", "expansion", "growth", "route density", "membership",
        "maintenance agreement", "google reviews", "automation"
    ]
    score += min(40, sum(8 for term in upside_terms if term in text))
    return clamp(score)


def risk_score(listing: Listing) -> float:
    score = 80
    if listing.customer_concentration_pct is not None:
        if listing.customer_concentration_pct > 0.50:
            score -= 60
        elif listing.customer_concentration_pct > 0.30:
            score -= 35
        elif listing.customer_concentration_pct > 0.20:
            score -= 15
    if listing.lease_years_remaining is not None and listing.lease_years_remaining < 2:
        score -= 35
    text = (listing.notes or "").lower()
    risk_terms = ["lawsuit", "lien", "declining revenue", "tax issue", "environmental", "key employee leaving", "old equipment"]
    score -= min(50, sum(15 for term in risk_terms if _term_present(text, term)))
    return clamp(score)


def deal_killers(listing: Listing) -> List[str]:
    flags: List[str] = []
    text = (listing.notes or "").lower()
    if listing.customer_concentration_pct is not None and listing.customer_concentration_pct > 0.30:
        flags.append("Customer concentration above 30%")
    if listing.owner_hours_per_week is not None and listing.owner_hours_per_week > 50:
        flags.append("Owner appears too operationally critical")
    if listing.lease_years_remaining is not None and listing.lease_years_remaining < 2:
        flags.append("Lease expires within 24 months")
    for term, label in [
        ("no tax returns", "No tax returns"),
        ("refuses financials", "Seller refuses financials"),
        ("lawsuit", "Potential lawsuit"),
        ("lien", "Potential lien"),
        ("environmental", "Environmental risk"),
        ("unverifiable cash flow", "Unverifiable cash flow"),
        ("declining revenue", "Declining revenue"),
        ("key employee leaving", "Key employee leaving"),
    ]:
        if _term_present(text, term):
            flags.append(label)
    return flags


def estimate_values(listing: Listing, industry_config: Dict[str, Any]) -> tuple[Optional[float], Optional[float], Optional[float]]:
    if not listing.sde:
        return None, None, None
    low = listing.sde * float(industry_config.get("target_multiple_low", 2.0))
    high = listing.sde * float(industry_config.get("target_multiple_high", 3.0))

    # Max price supported by a 1.75x DSCR assuming 10-year amortization at 10% blended debt cost.
    # This is intentionally conservative and approximate for screening only.
    annual_debt_service_capacity = listing.sde / 1.75
    debt_constant = 0.1627  # annual payment per $1 borrowed; rough 10yr @ 10%
    debt_supported_price = annual_debt_service_capacity / debt_constant

    # Price allowing 25% cash-on-cash assuming 20% down and post-debt cash flow.
    price_for_coc = listing.sde / 0.30 if listing.sde else high

    # Price allowing approximate payback under 4 years on equity.
    price_for_payback = listing.sde * 4.0

    max_offer = min(high, debt_supported_price, price_for_coc, price_for_payback)
    return low, high, max_offer


def bucket_for_score(score: float) -> str:
    if score >= 90:
        return "PURSUE NOW"
    if score >= 80:
        return "STRONG CANDIDATE"
    if score >= 70:
        return "REQUEST INFO / WATCHLIST"
    if score >= 60:
        return "PRICE TOO HIGH / WATCH"
    return "PASS"


def next_action_for(score: float, listing: Listing, flags: List[str]) -> str:
    if flags and score < 80:
        return "Pass unless seller provides clean financials and risk mitigation."
    if score >= 90:
        return "Contact broker/seller today; request CIM, tax returns, SDE add-back schedule, customer concentration, employee roster, and seller-financing terms."
    if score >= 80:
        return "Request financial package and confirm owner hours, seller financing, recurring revenue, lease, and employee retention."
    if score >= 70:
        return "Add to watchlist; ask for missing SDE, revenue, reason for sale, and financing details."
    if listing.asking_price and listing.sde:
        return "Only revisit after price reduction or improved seller-financing terms."
    return "Insufficient data; request basic financials before spending more time."


def score_listing(listing: Listing, industry_configs: Dict[str, Any]) -> ScoreBreakdown:
    key = normalized_industry_key(listing.industry)
    cfg = industry_configs.get(key)
    if cfg is None:
        logger.warning(
            "Unknown industry '%s' on listing '%s'; scoring with default config",
            listing.industry, listing.business_name,
        )
        cfg = DEFAULT_INDUSTRY

    fin = financial_score(listing)
    ind = float(cfg.get("base_score", 75))
    rec = recurring_revenue_score(listing)
    mot = seller_motivation_score(listing)
    own = owner_independence_score(listing)
    fit = financing_fit_score(listing)
    grow = growth_upside_score(listing)
    risk = risk_score(listing)

    bonus = 0
    if listing.seller_financing:
        bonus += 5
    if listing.real_estate_included:
        bonus += 3
    if listing.sba_prequalified:
        bonus += 2
    if listing.years_in_business and listing.years_in_business >= 20:
        bonus += 3

    flags = deal_killers(listing)
    penalty = 0
    if flags:
        penalty = min(35, len(flags) * 10)

    total = (
        MASTER_WEIGHTS["financial"] * fin
        + MASTER_WEIGHTS["industry"] * ind
        + MASTER_WEIGHTS["recurring_revenue"] * rec
        + MASTER_WEIGHTS["seller_motivation"] * mot
        + MASTER_WEIGHTS["owner_independence"] * own
        + MASTER_WEIGHTS["financing_fit"] * fit
        + MASTER_WEIGHTS["growth_upside"] * grow
        + MASTER_WEIGHTS["risk"] * risk
        + bonus
        - penalty
    )
    total = clamp(total)
    cfy = cash_flow_yield(listing)
    low, high, max_offer = estimate_values(listing, cfg)
    payback = None
    if listing.sde and listing.asking_price:
        assumed_down_payment = listing.asking_price * 0.20
        assumed_after_debt_cash_flow = listing.sde * 0.45
        if assumed_after_debt_cash_flow > 0:
            payback = assumed_down_payment / assumed_after_debt_cash_flow

    return ScoreBreakdown(
        financial_score=fin,
        industry_score=ind,
        recurring_revenue_score=rec,
        seller_motivation_score=mot,
        owner_independence_score=own,
        financing_fit_score=fit,
        growth_upside_score=grow,
        risk_score=risk,
        bonus_points=bonus,
        deal_killer_penalty=penalty,
        total_score=round(total, 1),
        bucket=bucket_for_score(total),
        cash_flow_yield=cfy,
        payback_years=payback,
        estimated_value_low=low,
        estimated_value_high=high,
        estimated_max_offer=max_offer,
        red_flags=flags,
        next_action=next_action_for(total, listing, flags),
    )

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class Listing:
    business_name: str
    industry: str
    location: str
    asking_price: Optional[float] = None
    revenue: Optional[float] = None
    sde: Optional[float] = None
    ebitda: Optional[float] = None
    real_estate_included: bool = False
    seller_financing: bool = False
    seller_financing_terms: Optional[str] = None
    sba_prequalified: bool = False
    reason_for_sale: Optional[str] = None
    years_in_business: Optional[int] = None
    employees: Optional[int] = None
    owner_hours_per_week: Optional[float] = None
    recurring_revenue_pct: Optional[float] = None
    customer_concentration_pct: Optional[float] = None
    equipment_condition: Optional[str] = None
    lease_years_remaining: Optional[float] = None
    source: Optional[str] = None
    listing_url: Optional[str] = None
    notes: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScoreBreakdown:
    financial_score: float
    industry_score: float
    recurring_revenue_score: float
    seller_motivation_score: float
    owner_independence_score: float
    financing_fit_score: float
    growth_upside_score: float
    risk_score: float
    bonus_points: float
    deal_killer_penalty: float
    total_score: float
    bucket: str
    cash_flow_yield: Optional[float]
    payback_years: Optional[float]
    estimated_value_low: Optional[float]
    estimated_value_high: Optional[float]
    estimated_max_offer: Optional[float]
    red_flags: List[str]
    next_action: str

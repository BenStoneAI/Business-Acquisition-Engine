import pytest

from src.models import Listing
from src.scoring import score_listing

INDUSTRIES = {
    "hvac": {"base_score": 95, "target_multiple_low": 2.5, "target_multiple_high": 4.0},
    "pest_control": {"base_score": 93, "target_multiple_low": 3.0, "target_multiple_high": 5.0},
}


def test_strong_hvac_scores_high():
    listing = Listing(
        business_name="Test HVAC",
        industry="hvac",
        location="Utah",
        asking_price=800000,
        sde=300000,
        seller_financing=True,
        sba_prequalified=True,
        reason_for_sale="Retirement",
        owner_hours_per_week=20,
        recurring_revenue_pct=0.35,
        customer_concentration_pct=0.10,
        years_in_business=25,
        notes="Owner will train. Maintenance agreements. Poor website."
    )
    score = score_listing(listing, INDUSTRIES)
    assert score.total_score >= 80
    assert score.bucket in {"STRONG CANDIDATE", "PURSUE NOW"}


def test_customer_concentration_penalty():
    listing = Listing(
        business_name="Risky Pest",
        industry="pest_control",
        location="Utah",
        asking_price=1000000,
        sde=200000,
        customer_concentration_pct=0.55,
        owner_hours_per_week=60,
        notes="Key employee leaving."
    )
    score = score_listing(listing, INDUSTRIES)
    assert "Customer concentration above 30%" in score.red_flags
    assert score.total_score < 70


def test_unknown_industry_uses_default_config():
    listing = Listing(
        business_name="Mystery Co", industry="underwater_basket_weaving",
        location="Utah", asking_price=500000, sde=150000,
    )
    score = score_listing(listing, INDUSTRIES)
    assert score.industry_score == 75  # DEFAULT_INDUSTRY base_score
    assert 0 <= score.total_score <= 100


def test_missing_financials_penalized_not_crashing():
    listing = Listing(business_name="Opaque LLC", industry="hvac", location="Utah")
    score = score_listing(listing, INDUSTRIES)
    assert score.financial_score == 35  # missing-data penalty tier
    assert score.cash_flow_yield is None
    assert score.payback_years is None
    assert score.estimated_max_offer is None


def test_short_lease_is_deal_killer():
    listing = Listing(
        business_name="Short Lease Wash", industry="pest_control", location="Utah",
        asking_price=900000, sde=280000, lease_years_remaining=1.5,
    )
    score = score_listing(listing, INDUSTRIES)
    assert "Lease expires within 24 months" in score.red_flags
    assert score.deal_killer_penalty >= 10


def test_max_offer_capped_by_cash_on_cash_constraint():
    listing = Listing(
        business_name="Cap Check HVAC", industry="hvac", location="Utah",
        asking_price=1000000, sde=100000,
    )
    score = score_listing(listing, INDUSTRIES)
    # min(4.0x SDE = 400000, DSCR cap = 100000/1.75/0.1627 ~= 351258,
    #     25% cash-on-cash cap = 100000/0.30 ~= 333333, 4yr payback = 400000)
    assert score.estimated_max_offer == pytest.approx(333333.33, rel=1e-3)
    assert score.estimated_value_low == 250000
    assert score.estimated_value_high == 400000


def test_word_boundary_terms_do_not_false_flag():
    # Bug A1: "lien" in "clients" / "environmental" in "environmentally".
    from src.models import Listing
    from src.scoring import deal_killers, risk_score
    clean = Listing(business_name="B", industry="hvac", location="UT",
                    notes="Loyal clients and environmentally friendly products.")
    assert deal_killers(clean) == []
    assert risk_score(clean) == 80
    dirty = Listing(business_name="B", industry="hvac", location="UT",
                    notes="There is a tax lien and a pending lawsuit.")
    flags = deal_killers(dirty)
    assert "Potential lien" in flags
    assert "Potential lawsuit" in flags

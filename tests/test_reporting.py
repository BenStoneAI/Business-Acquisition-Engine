from src.models import Listing
from src.reporting import build_daily_report, render_deal
from src.scoring import score_listing

INDUSTRIES = {
    "hvac": {"base_score": 95, "target_multiple_low": 2.5, "target_multiple_high": 4.0},
}


def _scored(listing):
    return listing, score_listing(listing, INDUSTRIES)


def test_payback_renders_numeric_years():
    listing = Listing(
        business_name="Payback Co", industry="hvac", location="Utah",
        asking_price=850000, sde=310000, listing_url="https://x.test/1",
    )
    listing, score = _scored(listing)
    out = render_deal(listing, score, 1)
    # 20% down / 45% after-debt cash flow => 170000 / 139500 = 1.2 years
    assert "| Payback Estimate | 1.2 years |" in out
    # Regression guard for the Phase 1 bug that leaked Python source into the report
    assert "if score.payback_years" not in out


def test_payback_unknown_when_financials_missing():
    listing = Listing(business_name="No Financials LLC", industry="hvac", location="Utah")
    listing, score = _scored(listing)
    out = render_deal(listing, score, 1)  # crashed with TypeError before the fix
    assert "| Payback Estimate | Unknown |" in out


def test_report_sections_respect_min_score():
    strong = Listing(
        business_name="Strong Deal", industry="hvac", location="Utah",
        asking_price=800000, sde=300000, seller_financing=True, sba_prequalified=True,
        reason_for_sale="Retirement", owner_hours_per_week=15,
        recurring_revenue_pct=0.6, years_in_business=25,
        notes="Owner will train. Maintenance agreements.",
    )
    weak = Listing(
        business_name="Weak Deal", industry="hvac", location="Utah",
        asking_price=5000000, sde=200000, owner_hours_per_week=70,
        customer_concentration_pct=0.6, notes="Declining revenue. Lawsuit.",
    )
    report = build_daily_report([_scored(strong), _scored(weak)], min_score=70)
    assert "- Total deals reviewed: 2" in report
    top_section = report.split("## Top Deals")[1].split("## Rejected / Pass")[0]
    rejected_section = report.split("## Rejected / Pass")[1]
    assert "Strong Deal" in top_section
    assert "Weak Deal" not in top_section
    assert "Weak Deal" in rejected_section

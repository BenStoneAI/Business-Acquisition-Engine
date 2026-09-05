from src.models import Listing
from src.scoring import score_listing
from src.response_engine import (
    build_response_package,
    create_deal_folder,
    render_package_markdown,
    document_requests,
    financing_options,
    decision_for,
    BUYER_NAME,
)

CONFIGS = {
    "hvac": {"display_name": "HVAC", "base_score": 80, "target_multiple_low": 2.0, "target_multiple_high": 3.0},
    "laundromat": {"display_name": "Laundromat", "base_score": 78, "target_multiple_low": 2.5, "target_multiple_high": 3.5},
}


def hvac_listing(**kw) -> Listing:
    base = dict(
        business_name="Wasatch HVAC Services", industry="hvac", location="Utah County UT",
        asking_price=850000, revenue=1800000, sde=310000, seller_financing=True,
        reason_for_sale="Retirement", years_in_business=24, employees=11,
        owner_hours_per_week=25, recurring_revenue_pct=0.32,
        notes="Owner will train for 12 months. Maintenance agreements in place.",
        listing_url="https://example.com/wasatch-hvac",
    )
    base.update(kw)
    return Listing(**base)


def test_package_has_all_required_sections():
    l = hvac_listing()
    pkg = build_response_package(l, score_listing(l, CONFIGS))
    md = render_package_markdown(pkg)
    for section in [
        "Deal Summary", "Decision", "Deal Thesis", "Outreach Email",
        "Buyer Credibility", "Top 10 Questions", "Document Request List",
        "Proposed Financing Structures", "Preliminary Valuation", "Risk Notes",
        "NDA Request", "LOI Skeleton", "Follow-up Email 1", "Follow-up Email 2",
        "Deal Folder", "CRM Status", "Calendar Reminder",
    ]:
        assert section in md, f"missing section: {section}"


def test_email_is_addressed_and_signed():
    l = hvac_listing()
    pkg = build_response_package(l, score_listing(l, CONFIGS))
    assert l.business_name in pkg.email_subject
    assert l.location in pkg.email_subject
    assert BUYER_NAME in pkg.email_body
    assert "seller-financed" in pkg.email_body.lower() or "seller financ" in pkg.email_body.lower()


def test_document_requests_are_industry_tailored():
    hvac_docs = document_requests(hvac_listing())
    assert "Technician roster" in hvac_docs  # HVAC extra
    laundry_docs = document_requests(hvac_listing(industry="laundromat"))
    assert "Machine list and age" in laundry_docs  # laundromat extra
    assert "Technician roster" not in laundry_docs


def test_three_financing_options_use_price_math():
    l = hvac_listing(asking_price=180000, sde=45000)
    opts = financing_options(l, score_listing(l, CONFIGS))
    assert len(opts) == 3
    assert opts[0].name.startswith("Option A")
    # Option B down payment is 10% of the anchored price (<= asking).
    assert "$" in opts[1].down_payment


def test_decision_reflects_score():
    assert "Pursue now" in decision_for(_fake_score(92, []))
    assert "Watchlist" in decision_for(_fake_score(72, []))
    assert "accountant" in decision_for(_fake_score(74, ["Customer concentration above 30%"]))


def test_create_deal_folder_builds_tree(tmp_path):
    l = hvac_listing()
    pkg = build_response_package(l, score_listing(l, CONFIGS))
    root = create_deal_folder(pkg, base_dir=tmp_path)
    for sub in ["01 Listing", "02 Financials", "05 Financing", "08 Notes"]:
        assert (root / sub).is_dir()
    assert (root / "01 Listing" / "hit_send_package.md").is_file()


def _fake_score(total, flags):
    from src.models import ScoreBreakdown
    return ScoreBreakdown(
        financial_score=0, industry_score=0, recurring_revenue_score=0,
        seller_motivation_score=0, owner_independence_score=0, financing_fit_score=0,
        growth_upside_score=0, risk_score=0, bonus_points=0, deal_killer_penalty=0,
        total_score=total, bucket="", cash_flow_yield=None, payback_years=None,
        estimated_value_low=None, estimated_value_high=None, estimated_max_offer=None,
        red_flags=flags, next_action="",
    )


def test_safe_folder_name_strips_windows_invalid_chars():
    from src.response_engine import safe_folder_name
    assert safe_folder_name("Frame Shop w/ Growing Sales") == "Frame Shop w Growing Sales"
    assert safe_folder_name('Auto: "Tire" & <Repair>?') == "Auto Tire & Repair"
    assert safe_folder_name("Trailing dot.") == "Trailing dot"
    assert safe_folder_name("") == "Unnamed Deal"
    assert len(safe_folder_name("x" * 200)) <= 80


def test_create_deal_folder_sanitizes_business_name(tmp_path):
    l = hvac_listing(business_name="Shop w/ Slash: Bad*Name?")
    pkg = build_response_package(l, score_listing(l, CONFIGS))
    root = create_deal_folder(pkg, base_dir=tmp_path)
    assert root.parent == tmp_path
    assert root.name == "Shop w Slash Bad Name"
    assert (root / "01 Listing" / "hit_send_package.md").exists()

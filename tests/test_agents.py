import logging

from src.agents import SourcingAgent

HEADER = (
    "business_name,industry,location,asking_price,revenue,sde,ebitda,"
    "real_estate_included,seller_financing,sba_prequalified,reason_for_sale,"
    "years_in_business,employees,owner_hours_per_week,recurring_revenue_pct,"
    "customer_concentration_pct,equipment_condition,lease_years_remaining,"
    "source,listing_url,notes\n"
)


def test_bad_asking_price_becomes_none_with_warning(tmp_path, caplog):
    # A single unparseable number must not cost the whole listing — the row
    # survives with that field blank and a warning logged.
    csv_path = tmp_path / "listings.csv"
    csv_path.write_text(
        HEADER
        + "Good Biz,hvac,Utah,850000,1800000,310000,,No,Yes,Yes,Retirement,24,11,25,32,12,Good,5,Test,https://x.test/good,ok\n"
        + "Broken Biz,hvac,Utah,NOT_A_PRICE,,,,,No,No,,,,,,,,,,https://x.test/broken,bad\n"
        + "Second Good,laundromat,Boise ID,600000,420000,145000,,No,Yes,No,Retiring,18,3,12,55,5,Fair,11,Test,https://x.test/good2,ok\n",
        encoding="utf-8",
    )
    with caplog.at_level(logging.WARNING, logger="src.agents"):
        listings = SourcingAgent().from_csv(csv_path)
    assert [l.business_name for l in listings] == ["Good Biz", "Broken Biz", "Second Good"]
    assert listings[1].asking_price is None
    assert any("Unparseable" in r.message for r in caplog.records)


def test_currency_and_percentage_normalization(tmp_path):
    csv_path = tmp_path / "listings.csv"
    csv_path.write_text(
        HEADER
        + '"Fancy Format Co",hvac,Utah,"$850,000",,"$310,000",,Yes,yes,TRUE,Retirement,24,11,25,32,12,Good,5,Test,https://x.test/f,ok\n',
        encoding="utf-8",
    )
    (listing,) = SourcingAgent().from_csv(csv_path)
    assert listing.asking_price == 850000.0
    assert listing.sde == 310000.0
    assert listing.recurring_revenue_pct == 0.32  # 32 -> 0.32
    assert listing.real_estate_included is True
    assert listing.seller_financing is True
    assert listing.sba_prequalified is True

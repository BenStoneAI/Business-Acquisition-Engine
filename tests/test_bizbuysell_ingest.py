from src.bizbuysell_ingest import parse_alert
from src.financing_filter import filter_full_seller_financing, financing_status, FULL, PARTIAL_CAPPED

# Representative BizBuySell "Listings by Email" alert. NOTE: calibrate the field
# regexes in bizbuysell_ingest.py against a real alert once one arrives — this
# fixture encodes the structure we expect (href before visible title + fields).
ALERT_HTML = """
<html><body>
<h2>New listings matching "Owner Financed - Mountain West"</h2>
<table>
 <tr><td>
   <a href="https://www.bizbuysell.com/Business-Opportunity/established-hvac-company/2101010/">
     Established HVAC Company - Owner Retiring</a><br>
   Salt Lake City, UT<br>
   Asking Price: $850,000<br>
   Cash Flow: $310,000<br>
   Gross Revenue: $1,800,000<br>
   Well-run HVAC business with maintenance agreements. Owner will consider
   seller financing for a qualified buyer.
 </td></tr>
 <tr><td>
   <a href="https://www.bizbuysell.com/Business-Opportunity/turnkey-coin-laundromat/2102020/">
     Turnkey Coin Laundromat</a><br>
   Boise, ID<br>
   Asking Price: $600,000<br>
   Cash Flow: $145,000<br>
   Long lease. Seller will finance 20% for the right buyer.
 </td></tr>
 <tr><td>
   <a href="https://www.bizbuysell.com/Business-Opportunity/pest-control-route/2103030/">
     Recurring Pest Control Route</a><br>
   Phoenix, AZ<br>
   Asking Price: $950,000<br>
   Cash Flow: $285,000<br>
   High recurring revenue. 100% seller financing available to a qualified buyer.
 </td></tr>
</table>
</body></html>
"""


def test_parses_all_three_listings():
    listings = parse_alert(ALERT_HTML)
    assert len(listings) == 3
    by_url = {l.listing_url.split("/")[-2]: l for l in listings}
    assert set(by_url) == {"2101010", "2102020", "2103030"}


def test_extracts_fields_and_industry():
    hvac = next(l for l in parse_alert(ALERT_HTML) if "2101010" in l.listing_url)
    assert hvac.industry == "hvac"
    assert hvac.asking_price == 850000
    assert hvac.sde == 310000            # Cash Flow -> SDE
    assert hvac.revenue == 1800000
    assert hvac.location == "Salt Lake City, UT"
    assert "HVAC" in hvac.business_name


def test_financing_screen_keeps_full_and_possible_drops_capped():
    listings = parse_alert(ALERT_HTML)
    statuses = {l.industry: financing_status(l) for l in listings}
    assert statuses["pest_control"] == FULL          # "100% seller financing"
    assert statuses["laundromat"] == PARTIAL_CAPPED   # "finance 20%"

    kept, dropped = filter_full_seller_financing(listings)
    kept_industries = {l.industry for l in kept}
    assert "hvac" in kept_industries          # possible (no stated cap)
    assert "pest_control" in kept_industries  # explicit 100%
    assert "laundromat" not in kept_industries  # capped at 20%


def test_skips_links_without_price():
    html = (
        '<a href="https://www.bizbuysell.com/logo/999/">logo</a> '
        '<a href="https://www.bizbuysell.com/Business-Opportunity/x/2200000/">A Biz</a> '
        'Ogden, UT Asking Price: $400,000 Cash Flow: $120,000'
    )
    listings = parse_alert(html)
    assert len(listings) == 1
    assert "2200000" in listings[0].listing_url


def test_off_thesis_industries_are_named_not_other():
    from src.bizbuysell_ingest import _infer_industry
    assert _infer_industry("Profitable Ocean County Pizzeria") == "restaurant"
    assert _infer_industry("Auto Repair, Tire & Inspection Shop") == "auto_repair"
    assert _infer_industry("Heritage Custom Frame Shop") == "retail"
    assert _infer_industry("Established HVAC Contractor") == "hvac"
    assert _infer_industry("Holiday Lights & Decor Business") == "other"


def test_price_suffixes_and_undisclosed_price():
    # Bug A3: "$1.2M"/"155K" must scale; "Inquire for price" listings must survive.
    html = (
        '<a href="https://www.bizbuysell.com/Business-Opportunity/a/2300000/?utm_source=email">Alpha Biz</a> '
        'Provo, UT Asking Price: $1.2M Cash Flow: 155K '
        '<a href="https://www.bizbuysell.com/Business-Opportunity/b/2300001/">Beta Biz</a> '
        'Ogden, UT Inquire for price. Cash Flow: $200,000 Seller Financing available.'
    )
    listings = parse_alert(html)
    assert len(listings) == 2
    a = next(l for l in listings if "2300000" in l.listing_url)
    assert a.asking_price == 1200000
    assert a.sde == 155000
    assert "?" not in a.listing_url  # tracking params stripped (bug A4)
    b = next(l for l in listings if "2300001" in l.listing_url)
    assert b.asking_price is None
    assert b.sde == 200000


def test_live_profile_url_shape_dedups_and_canonicalizes():
    # Real 2026 alert URLs: /listings/Profile/?q=<id>&utm_...  One listing emits
    # several sub-links (photo/button/headline) differing only in utm_content.
    html = (
        '<a href="https://www.bizbuysell.com/listings/Profile/?q=2398358&utm_content=bizphoto">photo</a> '
        '<a href="https://www.bizbuysell.com/listings/Profile/?q=2398358&utm_content=headline">Route Biz</a> '
        'Manitowoc, WI Asking Price: $250,000 Cash Flow: $95,000 Seller financing available.'
    )
    listings = parse_alert(html)
    assert len(listings) == 1
    assert listings[0].listing_url == "https://www.bizbuysell.com/listings/Profile/?q=2398358"


def test_broker_email_phone_and_name_extracted_from_block():
    html = """
    <a href="https://www.bizbuysell.com/Business-Opportunity/broker-hvac-co/2400000/">
      Broker HVAC Co</a><br>
    Ogden, UT<br>
    Asking Price: $500,000<br>
    Cash Flow: $150,000<br>
    Listed by: Jane Roberts<br>
    Contact: jane.roberts@brokerfirm.com<br>
    Phone: (801) 555-0142<br>
    Seller financing available.
    """
    listing = parse_alert(html)[0]
    assert listing.raw["broker_name"] == "Jane Roberts"
    assert listing.raw["broker_email"] == "jane.roberts@brokerfirm.com"
    assert listing.raw["broker_phone"] == "(801) 555-0142"


def test_broker_email_extracted_from_mailto_link():
    html = """
    <a href="https://www.bizbuysell.com/Business-Opportunity/mailto-biz/2400001/">Mailto Biz</a>
    Provo, UT Asking Price: $300,000 Cash Flow: $90,000 Seller financing available.
    <a href="mailto:broker@examplebrokerage.com">Email the broker</a>
    """
    listing = parse_alert(html)[0]
    assert listing.raw["broker_email"] == "broker@examplebrokerage.com"


def test_generic_relay_email_is_excluded():
    html = """
    <a href="https://www.bizbuysell.com/Business-Opportunity/noreply-biz/2400002/">Noreply Biz</a>
    Reno, NV Asking Price: $400,000 Cash Flow: $100,000 Seller financing available.
    <a href="mailto:noreply@bizbuysell.com">reply notice</a>
    """
    listing = parse_alert(html)[0]
    assert "broker_email" not in listing.raw


def test_absent_broker_fields_are_not_set():
    # The base fixture (ALERT_HTML) has no broker contact info at all.
    hvac = next(l for l in parse_alert(ALERT_HTML) if "2101010" in l.listing_url)
    assert "broker_email" not in hvac.raw
    assert "broker_phone" not in hvac.raw
    assert "broker_name" not in hvac.raw

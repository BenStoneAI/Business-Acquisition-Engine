from src.interested import resolve_broker_recipient
from src.models import Listing


def _listing(**raw_kw) -> Listing:
    return Listing(
        business_name="Wasatch HVAC Services", industry="hvac", location="Utah County UT",
        listing_url="https://example.com/wasatch-hvac", raw=raw_kw,
    )


def test_resolve_prefers_explicit_send_to_over_captured_broker_email():
    listing = _listing(broker_email="captured@brokerfirm.com")
    assert resolve_broker_recipient("explicit@brokerfirm.com", listing) == "explicit@brokerfirm.com"


def test_resolve_falls_back_to_captured_broker_email():
    listing = _listing(broker_email="captured@brokerfirm.com")
    assert resolve_broker_recipient(None, listing) == "captured@brokerfirm.com"


def test_resolve_returns_none_without_send_to_or_captured_email():
    listing = _listing()
    assert resolve_broker_recipient(None, listing) is None


def test_resolve_never_falls_back_to_buyer_own_address():
    # Safety contract: no captured broker email and no --send-to must resolve to
    # None, never BUYER_EMAIL — outreach must never silently redirect to self.
    from src.response_engine import BUYER_EMAIL
    listing = _listing()
    result = resolve_broker_recipient(None, listing)
    assert result is None
    assert result != BUYER_EMAIL


def test_main_send_with_no_recipient_exits_2(capsys, tmp_path):
    import sys
    from src.interested import main

    argv = [
        "prog", "--input", "examples/sample_listings.csv",
        "--name", "Wasatch", "--send", "--deals-dir", str(tmp_path),
    ]
    old_argv = sys.argv
    sys.argv = argv
    try:
        rc = main()
    finally:
        sys.argv = old_argv

    assert rc == 2
    captured = capsys.readouterr()
    assert "ERROR" in captured.err
    assert "sending outreach email" not in captured.err

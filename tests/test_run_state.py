from datetime import date

from src.models import Listing
from src.run_state import (
    detect_price_drops,
    filter_unprocessed,
    listing_key,
    load_processed,
    mark_processed,
    save_processed,
)


def _listing(url: str, name: str = "Biz", asking_price=None) -> Listing:
    return Listing(
        business_name=name, industry="hvac", location="Utah",
        listing_url=url, asking_price=asking_price,
    )


def test_round_trip_and_filter(tmp_path):
    state_file = tmp_path / "data" / "ingest_state.json"
    a, b = _listing("https://x.test/a"), _listing("https://x.test/b")

    processed = load_processed(state_file)
    assert processed == {}
    assert filter_unprocessed([a, b], processed) == [a, b]

    mark_processed(processed, [a], day=date(2026, 7, 18))
    save_processed(processed, state_file, day=date(2026, 7, 18))

    reloaded = load_processed(state_file)
    assert filter_unprocessed([a, b], reloaded) == [b]


def test_prune_drops_stale_entries(tmp_path):
    state_file = tmp_path / "state.json"
    processed = {"https://x.test/old": "2025-01-01", "https://x.test/new": "2026-07-17"}
    save_processed(processed, state_file, day=date(2026, 7, 18))
    reloaded = load_processed(state_file)
    assert "https://x.test/old" not in reloaded
    assert "https://x.test/new" in reloaded


def test_corrupt_state_file_starts_fresh(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text("{not json", encoding="utf-8")
    assert load_processed(state_file) == {}


def test_listing_without_url_keys_on_name(tmp_path):
    no_url = Listing(business_name="No URL Biz", industry="hvac", location="Utah")
    processed = {}
    mark_processed(processed, [no_url])
    assert filter_unprocessed([no_url], processed) == []


def test_listing_key_normalizes_url_variants():
    # Bug A4: tracking params / www / slashes must not defeat dedup.
    from src.run_state import listing_key
    a = _listing("https://www.bizbuysell.com/Business-Opportunity/x/2101010/")
    b = _listing("https://bizbuysell.com/Business-Opportunity/x/2101010/?utm=tracking")
    assert listing_key(a) == listing_key(b) == "2101010"
    c = _listing("https://example.com/deal/?utm=1")
    assert listing_key(c) == "https://example.com/deal"


def test_listing_key_extracts_query_param_id():
    a = _listing("https://www.bizbuysell.com/listings/Profile/?q=2398358&utm_content=button")
    b = _listing("https://www.bizbuysell.com/listings/Profile/?q=2398358&utm_content=summary")
    assert listing_key(a) == listing_key(b) == "2398358"


# --- Price-drop detection (b4) ---------------------------------------------

def test_legacy_string_values_load_transparently(tmp_path):
    """The live state file has 55 entries in the pre-price-tracking {key: 'YYYY-MM-DD'}
    format. Loading must upgrade them in memory without raising or requiring a
    manual migration, and detect_price_drops must work against the result."""
    state_file = tmp_path / "state.json"
    state_file.write_text(
        '{"https://x.test/a": "2026-07-01", "2101010": "2026-07-10"}', encoding="utf-8"
    )
    processed = load_processed(state_file)
    assert processed == {
        "https://x.test/a": {"last_seen": "2026-07-01", "asking_price": None},
        "2101010": {"last_seen": "2026-07-10", "asking_price": None},
    }
    # A legacy entry has no stored price, so it can never produce a false drop.
    listing = _listing("https://x.test/a", asking_price=100000)
    assert detect_price_drops([listing], processed) == []
    # filter_unprocessed still treats it as seen.
    assert filter_unprocessed([listing], processed) == []


def test_detect_price_drop_at_5pct_or_more(tmp_path):
    processed = {}
    original = _listing("https://x.test/a", asking_price=200000)
    mark_processed(processed, [original], day=date(2026, 7, 1))

    dropped = _listing("https://x.test/a", asking_price=190000)  # exactly -5%
    drops = detect_price_drops([dropped], processed)
    assert len(drops) == 1
    listing, old_price = drops[0]
    assert listing is dropped
    assert old_price == 200000

    steeper = _listing("https://x.test/a", asking_price=150000)  # -25%
    drops = detect_price_drops([steeper], processed)
    assert len(drops) == 1 and drops[0][1] == 200000


def test_no_false_drop_under_5pct_or_equal_or_higher(tmp_path):
    processed = {}
    original = _listing("https://x.test/a", asking_price=200000)
    mark_processed(processed, [original], day=date(2026, 7, 1))

    barely = _listing("https://x.test/a", asking_price=192000)  # -4%, under threshold
    assert detect_price_drops([barely], processed) == []

    same = _listing("https://x.test/a", asking_price=200000)
    assert detect_price_drops([same], processed) == []

    higher = _listing("https://x.test/a", asking_price=250000)
    assert detect_price_drops([higher], processed) == []

    # Never-before-seen listing (key not in state) is not a "drop".
    new_listing = _listing("https://x.test/never-seen", asking_price=1000)
    assert detect_price_drops([new_listing], processed) == []


def test_mark_processed_records_new_price(tmp_path):
    processed = {}
    a = _listing("https://x.test/a", asking_price=200000)
    mark_processed(processed, [a], day=date(2026, 7, 1))
    assert processed[listing_key(a)] == {"last_seen": "2026-07-01", "asking_price": 200000}

    # Re-running with a new price overwrites the stored price (state prices
    # stay current every run, independent of whether it was a "drop").
    b = _listing("https://x.test/a", asking_price=190000)
    mark_processed(processed, [b], day=date(2026, 7, 2))
    assert processed[listing_key(a)] == {"last_seen": "2026-07-02", "asking_price": 190000}

    # Round-trips through save/load without losing the price.
    state_file = tmp_path / "state.json"
    save_processed(processed, state_file, day=date(2026, 7, 2))
    reloaded = load_processed(state_file)
    assert reloaded[listing_key(a)]["asking_price"] == 190000

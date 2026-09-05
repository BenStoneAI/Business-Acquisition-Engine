from __future__ import annotations

"""Synthetic-listing simulation harness (t6).

Exercises the REAL pipeline pieces end to end — never reimplements their
logic:
  - src.bizbuysell_ingest.parse_alert()         (synthetic alert-email HTML)
  - src.financing_filter.financing_status()/
    filter_full_seller_financing()              (100% seller-financing screen)
  - src.scoring.score_listing()                 (real config/industry_formulas.yaml)
  - src.run_state                                (cross-run dedup)
  - src.agents.SourcingAgent.from_csv()          (CSV ingest path)

Per CLAUDE.md Hard Constraint 1/2, this file NEVER edits scoring logic or
Listing field names — it only asserts against real output. Any mismatch is
reported as a finding (category, listing, expected vs actual), not silently
patched.
"""

import time
from pathlib import Path

import pytest

import sim_factory as sf
from src.agents import SourcingAgent
from src.bizbuysell_ingest import parse_alert
from src.financing_filter import (
    FULL, POSSIBLE, PARTIAL_CAPPED, NONE,
    financing_status, filter_full_seller_financing,
)
from src.main import load_industry_configs
from src.models import Listing
from src.run_state import filter_unprocessed, mark_processed
from src.scoring import score_listing

REPO_ROOT = Path(__file__).resolve().parents[1]
INDUSTRY_CONFIGS = load_industry_configs(REPO_ROOT / "config" / "industry_formulas.yaml")


def _classify_population(alert_html: str, meta: dict):
    """Run the real pipeline over one synthetic alert and check every listing
    against its known-expected classification.

    Returns (mismatches: list[str], per_category: dict[str, {n, correct}]).
    """
    listings = parse_alert(alert_html)
    assert len(listings) == len(meta), (
        f"parse_alert() returned {len(listings)} listings; expected {len(meta)} "
        f"(a dropped/duplicated block indicates a parser regression, not part "
        f"of this harness's scope to fix)."
    )
    by_url = {l.listing_url: l for l in listings}

    kept, dropped = filter_full_seller_financing(listings)
    kept_urls = {l.listing_url for l in kept}

    mismatches = []
    per_category: dict = {}

    for url, info in meta.items():
        cat = info["category"]
        stats = per_category.setdefault(cat, {"n": 0, "correct": 0})
        stats["n"] += 1

        listing = by_url[url]
        actual_status = financing_status(listing)
        actual_qualifies = url in kept_urls
        ok = True

        if actual_status != info["expected_status"]:
            mismatches.append(
                f"[{cat}] {listing.business_name} ({url}): financing_status "
                f"expected={info['expected_status']!r} actual={actual_status!r}"
            )
            ok = False

        if actual_qualifies != info["expected_qualifies"]:
            mismatches.append(
                f"[{cat}] {listing.business_name} ({url}): qualifies "
                f"expected={info['expected_qualifies']!r} actual={actual_qualifies!r}"
            )
            ok = False

        if info["expected_qualifies"]:
            # Score every qualifying listing to prove score_listing() never
            # raises and, where the category makes a claim, matches it.
            try:
                score = score_listing(listing, INDUSTRY_CONFIGS)
            except Exception as exc:  # pragma: no cover - reported, not hidden
                mismatches.append(
                    f"[{cat}] {listing.business_name} ({url}): score_listing "
                    f"raised {exc!r}"
                )
                ok = False
            else:
                if not (0 <= score.total_score <= 100):
                    mismatches.append(
                        f"[{cat}] {listing.business_name} ({url}): total_score "
                        f"{score.total_score} out of [0,100]"
                    )
                    ok = False
                if "expected_min_total_score" in info and \
                        score.total_score < info["expected_min_total_score"]:
                    mismatches.append(
                        f"[{cat}] {listing.business_name} ({url}): total_score "
                        f"{score.total_score} below expected minimum "
                        f"{info['expected_min_total_score']}"
                    )
                    ok = False
                if "expected_industry_score" in info and \
                        score.industry_score != info["expected_industry_score"]:
                    mismatches.append(
                        f"[{cat}] {listing.business_name} ({url}): industry_score "
                        f"expected={info['expected_industry_score']} "
                        f"actual={score.industry_score}"
                    )
                    ok = False

        if ok:
            stats["correct"] += 1

    return mismatches, per_category


def _print_summary_table(per_category: dict, title: str) -> None:
    print(f"\n=== {title} ===")
    print(f"{'category':<24}{'N generated':<14}{'correct':<10}{'mismatches'}")
    for cat, stats in sorted(per_category.items()):
        n, correct = stats["n"], stats["correct"]
        print(f"{cat:<24}{n:<14}{correct:<10}{n - correct}")


# ---------------------------------------------------------------------------
# 1. Per-category correctness (small N, every category individually named)
# ---------------------------------------------------------------------------

def test_category_classification_accuracy():
    alert_html, meta = sf.generate_population(n=60, seed=sf.SEED)  # 10 per category
    mismatches, per_category = _classify_population(alert_html, meta)
    _print_summary_table(per_category, "Category accuracy (N=60, 10/category)")
    assert not mismatches, "Classification mismatches found:\n" + "\n".join(mismatches)
    assert set(per_category) == set(sf.CATEGORY_GENERATORS)


# ---------------------------------------------------------------------------
# 2. Scale test: 100 / 500 / 1000 through the real parse+filter+score pipeline
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n", [100, 500, 1000])
def test_scale_no_exceptions_and_accuracy(n):
    start = time.perf_counter()
    alert_html, meta = sf.generate_population(n=n, seed=sf.SEED)
    mismatches, per_category = _classify_population(alert_html, meta)
    elapsed = time.perf_counter() - start

    _print_summary_table(per_category, f"Scale run N={n} (elapsed {elapsed:.2f}s)")
    assert elapsed < 60, f"Scale run N={n} took {elapsed:.2f}s, exceeding the 60s budget"
    assert not mismatches, (
        f"Scale run N={n} found {len(mismatches)} classification mismatch(es):\n"
        + "\n".join(mismatches[:25])
    )


# ---------------------------------------------------------------------------
# 3. Dedup: same URL repeated inside a single alert (parse_alert's own dedup)
# ---------------------------------------------------------------------------

def test_duplicate_same_url_within_single_alert_is_deduped():
    import random
    rng = random.Random(sf.SEED)
    block, info = sf.gen_full_100(rng, idx=0)
    alert_html = sf.build_alert([block, block, block])  # same URL 3x
    listings = parse_alert(alert_html)
    assert len(listings) == 1, (
        f"parse_alert() should dedup repeated listing URLs within one alert; "
        f"got {len(listings)} listings for url={info['url']}"
    )
    assert listings[0].listing_url == info["url"]


# ---------------------------------------------------------------------------
# 4. Dedup: same URL across two ingest runs (src.run_state)
# ---------------------------------------------------------------------------

def test_duplicate_url_deduped_across_runs():
    listing = Listing(business_name="Repeat HVAC", industry="hvac",
                       location="Utah", listing_url="https://x.test/sim/repeat-1")
    processed: dict = {}

    run1_new = filter_unprocessed([listing], processed)
    assert run1_new == [listing]
    mark_processed(processed, run1_new)

    # Same listing arrives again (overlapping IMAP window re-parses the alert).
    run2_new = filter_unprocessed([listing], processed)
    assert run2_new == [], "Second run should see the URL as already processed"


# ---------------------------------------------------------------------------
# 5. Dedup: same business name, no URL, across two ingest runs
# ---------------------------------------------------------------------------

def test_duplicate_name_no_url_deduped_across_runs():
    a = Listing(business_name="No URL Laundromat", industry="laundromat", location="Idaho")
    b = Listing(business_name="No URL Laundromat", industry="laundromat", location="Idaho")
    processed: dict = {}

    run1_new = filter_unprocessed([a], processed)
    assert run1_new == [a]
    mark_processed(processed, run1_new)

    run2_new = filter_unprocessed([b], processed)
    assert run2_new == [], (
        "run_state keys on business_name when listing_url is None; a second "
        "listing with the same name should be treated as the same duplicate."
    )


# ---------------------------------------------------------------------------
# 6. Bad/thin listings via the CSV ingest path (missing SDE and/or price)
# ---------------------------------------------------------------------------

def test_thin_bad_listings_score_low_without_crashing(tmp_path):
    rows = sf.gen_thin_bad_rows()
    csv_path = tmp_path / "thin_bad.csv"
    sf.write_csv(csv_path, rows)

    listings = SourcingAgent().from_csv(csv_path)
    assert len(listings) == len(rows), "malformed cells should not drop whole rows"

    for listing in listings:
        score = score_listing(listing, INDUSTRY_CONFIGS)
        assert score.financial_score == 35, (
            f"{listing.business_name}: expected the missing-data financial "
            f"penalty tier (35), got {score.financial_score}"
        )
        assert score.cash_flow_yield is None
        assert 0 <= score.total_score <= 100


# ---------------------------------------------------------------------------
# 7. Absurd values via the CSV ingest path (0 / negative / 1e12 price)
# ---------------------------------------------------------------------------

def test_absurd_values_do_not_crash_and_stay_clamped(tmp_path):
    rows = sf.gen_absurd_value_rows()
    csv_path = tmp_path / "absurd.csv"
    sf.write_csv(csv_path, rows)

    listings = SourcingAgent().from_csv(csv_path)
    assert len(listings) == len(rows)

    by_name = {l.business_name: l for l in listings}

    zero = by_name["Zero Price Roofing"]
    assert zero.asking_price == 0
    score = score_listing(zero, INDUSTRY_CONFIGS)
    assert score.cash_flow_yield is None  # asking_price falsy -> guarded, no ZeroDivisionError
    assert 0 <= score.total_score <= 100

    negative = by_name["Negative Price Car Wash"]
    assert negative.asking_price == -500000
    score = score_listing(negative, INDUSTRY_CONFIGS)
    assert score.cash_flow_yield is None  # asking_price <= 0 -> guarded
    assert 0 <= score.total_score <= 100

    huge = by_name["Absurd Trillion Dollar Storage"]
    assert huge.asking_price == 1_000_000_000_000
    score = score_listing(huge, INDUSTRY_CONFIGS)
    assert score.cash_flow_yield is not None and score.cash_flow_yield < 0.01
    assert 0 <= score.total_score <= 100


# ---------------------------------------------------------------------------
# 8. Off-thesis industry inference + honest low base score
# ---------------------------------------------------------------------------

def test_off_thesis_pizzeria_gets_low_industry_base_score():
    import random
    rng = random.Random(sf.SEED + 1)
    block, info = sf.gen_off_thesis_pizzeria(rng, idx=0)
    alert_html = sf.build_alert([block])
    listings = parse_alert(alert_html)
    assert len(listings) == 1
    pizzeria = listings[0]
    assert pizzeria.industry == "restaurant"
    score = score_listing(pizzeria, INDUSTRY_CONFIGS)
    assert score.industry_score == 30, (
        f"expected restaurant base_score=30 from config/industry_formulas.yaml, "
        f"got {score.industry_score}"
    )


# ---------------------------------------------------------------------------
# 9. Retiring owner + strong financials clears the STRONG CANDIDATE threshold
# ---------------------------------------------------------------------------

def test_retiring_owner_strong_deal_scores_high():
    import random
    rng = random.Random(sf.SEED + 2)
    mismatches_found = []
    for idx in range(10):
        block, info = sf.gen_retiring_strong(rng, idx)
        alert_html = sf.build_alert([block])
        listings = parse_alert(alert_html)
        assert len(listings) == 1
        listing = listings[0]
        assert financing_status(listing) == FULL
        score = score_listing(listing, INDUSTRY_CONFIGS)
        if score.total_score < info["expected_min_total_score"]:
            mismatches_found.append(
                f"{listing.business_name}: total_score={score.total_score} "
                f"< expected minimum {info['expected_min_total_score']}"
            )
    assert not mismatches_found, "\n".join(mismatches_found)

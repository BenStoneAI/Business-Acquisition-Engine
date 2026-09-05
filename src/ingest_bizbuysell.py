from __future__ import annotations

"""End-to-end BizBuySell alert -> deal packets.

Fetches BizBuySell alert emails (IMAP, or a saved --file), parses them into
listings, drops listings already processed on a previous run (data/
ingest_state.json), keeps only the 100%/possible-100% seller-financing deals,
scores them, persists listings + scores to Postgres (env-gated), pushes a
Telegram alert — or a one-line heartbeat when there is nothing to alert, so
silence always means failure — and builds a first-contact packet + deal folder
for each qualifying deal that clears the reporting threshold. Any crash sends a
Telegram failure alert before exiting nonzero.

    python -m src.ingest_bizbuysell                    # fetch via IMAP
    python -m src.ingest_bizbuysell --file alert.html  # parse a saved alert
    python -m src.ingest_bizbuysell --no-state         # reprocess seen listings
"""

import argparse
import logging
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from .bizbuysell_ingest import parse_alert
from .db import persist_scored_listings
from .financing_filter import filter_full_seller_financing
from .imap_fetch import fetch_alert_bodies
from .notifier import build_alert, build_heartbeat, send_telegram, telegram_configured
from .reporting import money
from .response_engine import build_response_package, create_deal_folder
from .run_state import (
    detect_price_drops,
    filter_unprocessed,
    listing_key,
    load_processed,
    mark_processed,
    save_processed,
)
from .scoring import score_listing
from .tls import use_system_certs

logger = logging.getLogger(__name__)


def _build_price_drop_alert(drops) -> str:
    lines = []
    for listing, old_price in drops:
        lines.append(f"\U0001F4C9 PRICE DROP: {listing.business_name} — {listing.location}")
        lines.append(f"  {money(old_price)} → {money(listing.asking_price)}")
        if listing.listing_url:
            lines.append(f"  {listing.listing_url}")
    return "\n".join(lines)


def _dedupe(listings):
    seen, out = set(), []
    for l in listings:
        key = listing_key(l)
        if key not in seen:
            seen.add(key)
            out.append(l)
    return out


def _run(args, min_score: float) -> int:
    if args.file:
        bodies = [Path(args.file).read_text(encoding="utf-8", errors="replace")]
    else:
        bodies = fetch_alert_bodies()

    listings = _dedupe([l for body in bodies for l in parse_alert(body)]) if bodies else []
    print(f"Parsed {len(listings)} listing(s) from {len(bodies)} alert(s).")

    processed = {} if args.no_state else load_processed(args.state_file)
    fresh = filter_unprocessed(listings, processed)
    if len(fresh) < len(listings):
        print(f"Skipped {len(listings) - len(fresh)} listing(s) already processed on a prior run.")

    # Price drops are the strongest seller-motivation signal in this thesis and
    # must not stay buried by filter_unprocessed just because the URL was seen
    # before. Detected against the FULL parsed set so a re-priced listing that
    # dropped out of the current alert email on a later run is still caught.
    price_drops = detect_price_drops(listings, processed)
    if price_drops:
        print(f"Detected {len(price_drops)} price drop(s).")
        send_telegram(_build_price_drop_alert(price_drops))

    to_process = fresh + [listing for listing, _ in price_drops]
    kept, dropped = filter_full_seller_financing(to_process)
    print(f"Kept {len(kept)} with 100% seller financing possible; dropped {len(dropped)}.")

    industry_configs = yaml.safe_load(Path(args.industry_config).read_text(encoding="utf-8"))["industries"]
    scored = [(l, score_listing(l, industry_configs)) for l in kept]

    persisted = persist_scored_listings(scored)
    if persisted is None and os.getenv("DATABASE_URL"):
        # DATABASE_URL is set but persistence failed — that's an outage, not an
        # unconfigured skip. Score history silently stopping is how data rots.
        send_telegram("⚠️ Radar: database persistence FAILED this run — "
                      "score history not saved. Check logs/radar.log.")

    alert_text = build_alert(scored, min_score=min_score)
    alerted = send_telegram(alert_text) if alert_text else False
    # If a deal alert was due but Telegram failed, do NOT mark these listings
    # processed — the next run must re-alert them instead of burying them.
    alert_failed = bool(alert_text) and telegram_configured() and not alerted

    built = 0
    for listing, score in sorted(scored, key=lambda x: x[1].total_score, reverse=True):
        if score.total_score < min_score:
            continue
        try:
            pkg = build_response_package(listing, score)
            folder = create_deal_folder(pkg, base_dir=args.deals_dir)
        except OSError as exc:
            logger.error("Packet build failed for %r: %s", listing.business_name, exc)
            continue
        built += 1
        print(f"  packet: {listing.business_name} ({score.total_score}/100) -> {folder}")

    if alert_failed:
        logger.warning("Deal alert could not be delivered; ingest state NOT saved "
                       "so these listings re-alert on the next run.")
    elif not args.no_state and listings:
        mark_processed(processed, listings)
        save_processed(processed, args.state_file)

    if not alert_text:
        send_telegram(build_heartbeat(len(listings), len(fresh), built, min_score))

    print(f"Built {built} deal packet(s) at or above score {min_score}.")
    return 0


def main() -> int:
    use_system_certs()
    load_dotenv()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="Ingest BizBuySell alerts and build deal packets")
    parser.add_argument("--file", help="Parse a saved alert email (HTML/text) instead of IMAP")
    parser.add_argument("--industry-config", default="config/industry_formulas.yaml")
    parser.add_argument("--deals-dir", default="Deals")
    parser.add_argument("--state-file", default="data/ingest_state.json")
    parser.add_argument("--no-state", action="store_true",
                        help="Ignore the cross-run state file and reprocess every listing")
    parser.add_argument("--min-score", type=float, default=None,
                        help="Score threshold to build a packet; default MIN_SCORE_TO_REPORT or 70")
    args = parser.parse_args()
    min_score = args.min_score if args.min_score is not None else float(os.getenv("MIN_SCORE_TO_REPORT", "70"))

    try:
        return _run(args, min_score)
    except Exception as exc:
        logger.exception("Radar ingest failed")
        send_telegram(f"⚠️ Radar ingest FAILED: {exc!r}. Check logs/radar.log.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

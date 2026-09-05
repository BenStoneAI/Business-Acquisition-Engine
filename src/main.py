from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

from datetime import date

from .agents import SourcingAgent
from .daily_runs import write_daily_run
from .db import persist_scored_listings
from .emailer import send_report_email
from .financing_filter import filter_full_seller_financing
from .notifier import notify_daily
from .scoring import score_listing
from .reporting import build_daily_report
from .tls import use_system_certs


def load_industry_configs(path: str | Path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)["industries"]


def main():
    use_system_certs()
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Run Boring Business Acquisition Radar")
    parser.add_argument("--input", required=True, help="CSV of listings to score")
    parser.add_argument("--output", default="daily_report.md", help="Markdown report output path")
    parser.add_argument("--industry-config", default="config/industry_formulas.yaml")
    parser.add_argument("--min-score", type=float, default=None,
                        help="Reporting threshold; defaults to MIN_SCORE_TO_REPORT env var or 70")
    parser.add_argument("--all-financing", action="store_true",
                        help="Disable the 100%% seller-financing screen and score every listing")
    args = parser.parse_args()
    if args.min_score is None:
        args.min_score = float(os.getenv("MIN_SCORE_TO_REPORT", "70"))

    industry_configs = load_industry_configs(args.industry_config)
    listings = SourcingAgent().from_csv(args.input)
    print(f"Loaded {len(listings)} listings.")

    if not args.all_financing:
        listings, dropped = filter_full_seller_financing(listings)
        print(f"Kept {len(listings)} with 100% seller financing possible; "
              f"dropped {len(dropped)} without it.")

    scored = [(listing, score_listing(listing, industry_configs)) for listing in listings]
    print(f"Scored {len(scored)} listings.")

    report = build_daily_report(scored, min_score=args.min_score)
    Path(args.output).write_text(report, encoding="utf-8")
    print(f"Report written to {args.output}")

    reportable = sum(1 for _, s in scored if s.total_score >= args.min_score)
    archived = write_daily_run(report, found_count=reportable)
    if archived:
        print(f"Daily run archived to {archived}")

    persist_scored_listings(scored)
    notify_daily(scored, min_score=args.min_score)
    send_report_email(report, subject=f"Daily Boring Business Acquisition Radar — {date.today().isoformat()}")


if __name__ == "__main__":
    main()

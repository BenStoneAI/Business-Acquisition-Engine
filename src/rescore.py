from __future__ import annotations

"""Re-underwrite a deal once verified financials arrive.

Loads `Deals/<Business>/01 Listing/listing.json`, applies verified-number
overrides from flags, re-runs the untouched score_listing(), prints a
before → after comparison, archives it to `02 Financials/rescore_<date>.md`,
updates listing.json with the verified values, and appends a deal_scores
history row via db.persist_scored_listings (env-gated, log-and-skip).

Usage:
    python -m src.rescore --deal Wasatch --sde 250000
"""

import argparse
import json
import sys
from dataclasses import asdict, fields, replace
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from dotenv import load_dotenv

from . import db
from .deal import find_deal_folder
from .models import Listing, ScoreBreakdown
from .reporting import money
from .scoring import score_listing

# CLI flag dest -> Listing field name
OVERRIDE_FIELDS = {
    "sde": "sde",
    "revenue": "revenue",
    "asking_price": "asking_price",
    "recurring_pct": "recurring_revenue_pct",
    "customer_concentration_pct": "customer_concentration_pct",
    "owner_hours": "owner_hours_per_week",
}

_FACTOR_FIELDS = [
    "financial_score", "industry_score", "recurring_revenue_score",
    "seller_motivation_score", "owner_independence_score",
    "financing_fit_score", "growth_upside_score", "risk_score",
    "bonus_points", "deal_killer_penalty",
]


def listing_from_json(data: dict) -> Listing:
    names = {f.name for f in fields(Listing)}
    return Listing(**{k: v for k, v in data.items() if k in names})


def comparison_markdown(business_name: str, before: ScoreBreakdown,
                        after: ScoreBreakdown, overrides: Dict[str, float]) -> str:
    def m(value: Optional[float]) -> str:
        return money(value, none_label="TBD")

    lines = [
        f"# Rescore — {business_name} ({date.today().isoformat()})",
        "",
        "**VERIFIED NUMBERS — supersedes listing-ad screening score**",
        "",
        "## Verified overrides applied",
    ]
    lines += [f"- {field_name}: {value}" for field_name, value in overrides.items()] or ["- (none)"]
    lines += [
        "",
        "## Score",
        f"- Total: {before.total_score} → {after.total_score}",
        f"- Bucket: {before.bucket} → {after.bucket}",
        "",
        "## Factors that moved",
    ]
    moved = [
        f"- {name}: {getattr(before, name)} → {getattr(after, name)}"
        for name in _FACTOR_FIELDS
        if getattr(before, name) != getattr(after, name)
    ]
    lines += moved or ["- (no individual factor changed)"]
    lines += [
        "",
        "## Valuation",
        f"- Screening value range: {m(after.estimated_value_low)}–{m(after.estimated_value_high)}"
        f" (was {m(before.estimated_value_low)}–{m(before.estimated_value_high)})",
        f"- Disciplined max offer: {m(after.estimated_max_offer)}"
        f" (was {m(before.estimated_max_offer)})",
        "",
    ]
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    load_dotenv()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Re-score a deal with verified numbers")
    parser.add_argument("--deal", required=True, help="substring of the deal folder name")
    parser.add_argument("--deals-dir", default="Deals")
    parser.add_argument("--industry-config", default="config/industry_formulas.yaml")
    parser.add_argument("--sde", type=float)
    parser.add_argument("--revenue", type=float)
    parser.add_argument("--asking-price", type=float)
    parser.add_argument("--recurring-pct", type=float)
    parser.add_argument("--customer-concentration-pct", type=float)
    parser.add_argument("--owner-hours", type=float)
    args = parser.parse_args(argv)

    try:
        folder = find_deal_folder(args.deals_dir, args.deal)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    listing_path = folder / "01 Listing" / "listing.json"
    if not listing_path.is_file():
        print(f"{listing_path} not found — build the packet first "
              f"(python -m src.interested).", file=sys.stderr)
        return 1

    data = json.loads(listing_path.read_text(encoding="utf-8"))
    before_listing = listing_from_json(data)

    overrides = {
        field_name: getattr(args, flag)
        for flag, field_name in OVERRIDE_FIELDS.items()
        if getattr(args, flag) is not None
    }

    configs = yaml.safe_load(
        Path(args.industry_config).read_text(encoding="utf-8")
    )["industries"]
    before = score_listing(before_listing, configs)
    after_listing = replace(before_listing, **overrides)
    after = score_listing(after_listing, configs)

    report = comparison_markdown(before_listing.business_name, before, after, overrides)
    print(report)

    out_path = folder / "02 Financials" / f"rescore_{date.today().isoformat()}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"[rescore written to: {out_path}]", file=sys.stderr)

    data.update(asdict(after_listing))
    data["total_score"] = after.total_score
    data["bucket"] = after.bucket
    listing_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    db.persist_scored_listings([(after_listing, after)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

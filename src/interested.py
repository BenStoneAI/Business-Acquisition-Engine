from __future__ import annotations

"""`Interested` trigger — the second-layer entry point.

Given a listing (by URL or name) from a CSV, this scores it, builds the full
first-contact package, creates the deal-room folder, and writes the package to
disk. Delivery to the operator's inbox is handled separately (Gmail).

Usage:
    python -m src.interested --input examples/sample_listings.csv \
        --url https://example.com/wasatch-hvac
    python -m src.interested --input examples/sample_listings.csv --name "Wasatch"
"""

import argparse
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from .agents import SourcingAgent
from .emailer import send_email, send_report_email
from .models import Listing
from .response_engine import build_response_package, create_deal_folder, render_package_markdown
from .scoring import score_listing
from .tls import use_system_certs


def _find(listings: list[Listing], url: str | None, name: str | None) -> Listing | None:
    for l in listings:
        if url and l.listing_url == url:
            return l
        if name and name.lower() in l.business_name.lower():
            return l
    return None


def resolve_broker_recipient(send_to: str | None, listing: Listing) -> str | None:
    """Resolve who the outreach email goes to: --send-to wins, else the broker
    email captured during ingest. Never falls back to the buyer's own address —
    that would silently redirect outreach meant for a third party."""
    if send_to:
        return send_to
    return (listing.raw or {}).get("broker_email")


def main() -> int:
    use_system_certs()
    load_dotenv()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Mark a listing Interested and build its package")
    parser.add_argument("--input", required=True, help="CSV of listings")
    parser.add_argument("--url", help="listing_url of the interested deal")
    parser.add_argument("--name", help="substring of the business name")
    parser.add_argument("--industry-config", default="config/industry_formulas.yaml")
    parser.add_argument("--deals-dir", default="Deals")
    parser.add_argument("--email", action="store_true",
                        help="Email the package to REPORT_TO_EMAIL via the SMTP relay")
    parser.add_argument("--send-to", help="explicit recipient for the broker outreach email")
    parser.add_argument("--send", action="store_true",
                        help="Send the broker outreach email (subject+body) to --send-to, "
                             "or the broker email captured during ingest if not given")
    args = parser.parse_args()
    if not (args.url or args.name):
        parser.error("provide --url or --name")

    industry_configs = yaml.safe_load(Path(args.industry_config).read_text(encoding="utf-8"))["industries"]
    listings = SourcingAgent().from_csv(args.input)
    listing = _find(listings, args.url, args.name)
    if listing is None:
        print(f"No listing matched url={args.url!r} name={args.name!r}", file=sys.stderr)
        return 1

    score = score_listing(listing, industry_configs)
    pkg = build_response_package(listing, score)
    folder = create_deal_folder(pkg, base_dir=args.deals_dir)
    markdown = render_package_markdown(pkg)

    print(markdown)
    print(f"\n[deal folder created at: {folder}]", file=sys.stderr)

    if args.email:
        subject = f"[Radar — INTERESTED] {listing.business_name} — {listing.location}"
        sent = send_report_email(markdown, subject=subject)
        print(f"[email {'sent' if sent else 'skipped — SMTP not configured'}]",
              file=sys.stderr)

    if args.send:
        recipient = resolve_broker_recipient(args.send_to, listing)
        if not recipient:
            print(
                "ERROR: --send requires --send-to or a broker email captured "
                "during ingest; none was found for this listing. Nothing was sent.",
                file=sys.stderr,
            )
            return 2
        print(f"[sending outreach email] to={recipient} subject={pkg.email_subject!r}",
              file=sys.stderr)
        sent = send_email(recipient, pkg.email_subject, pkg.email_body)
        print(f"[broker email {'sent' if sent else 'skipped — SMTP not configured'}]",
              file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

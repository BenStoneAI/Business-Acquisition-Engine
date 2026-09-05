from __future__ import annotations

"""Deal lifecycle stage tracker (post-first-contact).

Writes/updates `status.json` in the deal folder root and mirrors the stage to
business_listings.status in Postgres (env-gated, log-and-skip without
DATABASE_URL — same contract as db.persist_scored_listings).

Usage:
    python -m src.deal --deal Wasatch --stage contacted
    python -m src.deal --deal Wasatch          # print current status
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

from . import db

STAGES = ["new", "contacted", "nda", "cim", "loi", "dd", "closing", "closed", "dead"]


def find_deal_folder(deals_dir: str | Path, needle: str) -> Path:
    """Locate exactly one deal folder whose name contains `needle` (case-insensitive)."""
    base = Path(deals_dir)
    matches = (
        sorted(
            (p for p in base.iterdir() if p.is_dir() and needle.lower() in p.name.lower()),
            key=lambda p: p.name,
        )
        if base.is_dir()
        else []
    )
    if not matches:
        raise FileNotFoundError(f"No deal folder under {base} matches {needle!r}")
    if len(matches) > 1:
        names = ", ".join(p.name for p in matches)
        raise FileNotFoundError(f"Ambiguous deal {needle!r}: matches {names}")
    return matches[0]


def load_listing_json(folder: Path) -> Optional[dict]:
    path = folder / "01 Listing" / "listing.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def set_stage(folder: Path, stage: str, when: Optional[date] = None) -> dict:
    day = (when or date.today()).isoformat()
    status_path = folder / "status.json"
    history: List[dict] = []
    if status_path.is_file():
        history = json.loads(status_path.read_text(encoding="utf-8")).get("history", [])
    status = {
        "stage": stage,
        "updated": day,
        "history": history + [{"stage": stage, "date": day}],
    }
    status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status


def main(argv: Optional[List[str]] = None) -> int:
    load_dotenv()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Track a deal's lifecycle stage")
    parser.add_argument("--deal", required=True, help="substring of the deal folder name")
    parser.add_argument("--stage", choices=STAGES,
                        help="new stage; omit to print the current status")
    parser.add_argument("--deals-dir", default="Deals")
    args = parser.parse_args(argv)

    try:
        folder = find_deal_folder(args.deals_dir, args.deal)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    status_path = folder / "status.json"
    if not args.stage:
        if status_path.is_file():
            print(status_path.read_text(encoding="utf-8"))
        else:
            print(f"No status recorded yet for {folder.name} (stage defaults to 'new').")
        return 0

    status = set_stage(folder, args.stage)
    print(f"{folder.name}: stage → {status['stage']} ({status['updated']})")

    listing_url = (load_listing_json(folder) or {}).get("listing_url")
    if listing_url:
        db.update_listing_status(listing_url, args.stage)
    else:
        print("No listing.json/listing_url in this deal folder; "
              "database status not updated.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Apply customer-plane SQL. Usage: python scripts/apply_customer_plane.py"""
from __future__ import annotations

import os
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "sql" / "migrations" / "phase3_customer_plane.sql").read_text(encoding="utf-8")


def main() -> None:
    url = os.environ["CUSTOMER_DATABASE_URL"]
    conn = psycopg2.connect(url)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(SQL)
        cur.execute("GRANT USAGE ON SCHEMA public TO radar_pool_readonly")
        cur.execute(
            "GRANT SELECT ON business_listings, deal_scores, pool_runs TO radar_pool_readonly"
        )
        cur.execute(
            "INSERT INTO pool_runs (listing_count, notes) VALUES (0, 'customer plane initialized')"
        )
    print("customer plane applied")


if __name__ == "__main__":
    main()

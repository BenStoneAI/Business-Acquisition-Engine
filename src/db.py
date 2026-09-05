from __future__ import annotations

import logging
import os
from typing import List, Optional, Tuple

from .models import Listing, ScoreBreakdown

logger = logging.getLogger(__name__)

LISTING_UPSERT_SQL = """
INSERT INTO business_listings (
    business_name, industry, location, asking_price, revenue, sde, ebitda,
    real_estate_included, seller_financing, sba_prequalified, reason_for_sale,
    years_in_business, employees, owner_hours_per_week, recurring_revenue_pct,
    customer_concentration_pct, equipment_condition, lease_years_remaining,
    source, listing_url, notes, raw_json
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (listing_url) DO UPDATE SET
    asking_price = EXCLUDED.asking_price,
    revenue = EXCLUDED.revenue,
    sde = EXCLUDED.sde,
    notes = EXCLUDED.notes,
    last_seen_at = now()
RETURNING id
"""

_UPSERT_CLAUSE = (
    "ON CONFLICT (listing_url) DO UPDATE SET\n"
    "    asking_price = EXCLUDED.asking_price,\n"
    "    revenue = EXCLUDED.revenue,\n"
    "    sde = EXCLUDED.sde,\n"
    "    notes = EXCLUDED.notes,\n"
    "    last_seen_at = now()"
)

SCORE_INSERT_SQL = """
INSERT INTO deal_scores (
    listing_id, total_score, bucket, financial_score, industry_score,
    recurring_revenue_score, seller_motivation_score, owner_independence_score,
    financing_fit_score, growth_upside_score, risk_score, bonus_points,
    deal_killer_penalty, cash_flow_yield, payback_years, estimated_value_low,
    estimated_value_high, estimated_max_offer, red_flags, next_action
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def _listing_values(listing: Listing, raw_json) -> tuple:
    return (
        listing.business_name, listing.industry, listing.location,
        listing.asking_price, listing.revenue, listing.sde, listing.ebitda,
        listing.real_estate_included, listing.seller_financing,
        listing.sba_prequalified, listing.reason_for_sale,
        listing.years_in_business, listing.employees, listing.owner_hours_per_week,
        listing.recurring_revenue_pct, listing.customer_concentration_pct,
        listing.equipment_condition, listing.lease_years_remaining,
        listing.source, listing.listing_url, listing.notes, raw_json,
    )


def _upsert_listing(cur, listing: Listing, json_adapter) -> int:
    if listing.listing_url:
        cur.execute(LISTING_UPSERT_SQL, _listing_values(listing, json_adapter(listing.raw)))
        return cur.fetchone()[0]
    # No URL to dedup on: match by name + location instead of inserting blindly.
    cur.execute(
        "SELECT id FROM business_listings"
        " WHERE business_name = %s AND location = %s AND listing_url IS NULL",
        (listing.business_name, listing.location),
    )
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE business_listings SET last_seen_at = now() WHERE id = %s", (row[0],))
        return row[0]
    cur.execute(
        LISTING_UPSERT_SQL.replace(_UPSERT_CLAUSE, ""),
        _listing_values(listing, json_adapter(listing.raw)),
    )
    return cur.fetchone()[0]


def persist_scored_listings(scored: List[Tuple[Listing, ScoreBreakdown]]) -> Optional[int]:
    """Upsert listings (dedup by listing_url) and append one deal_scores row each.

    Env-gated: without DATABASE_URL this logs a warning and returns None so the
    pipeline (and CI without secrets) still succeeds. Returns rows persisted.
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.warning("DATABASE_URL not set; skipping database persistence.")
        return None

    import psycopg2
    from psycopg2.extras import Json

    schema = os.getenv("DATABASE_SCHEMA") or "public"
    try:
        conn = psycopg2.connect(database_url)
    except psycopg2.Error as exc:
        logger.warning("Database connection failed; skipping persistence: %s", exc)
        return None
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SET search_path TO %s", (schema,))
                for listing, score in scored:
                    listing_id = _upsert_listing(cur, listing, Json)
                    cur.execute(SCORE_INSERT_SQL, (
                        listing_id, score.total_score, score.bucket,
                        score.financial_score, score.industry_score,
                        score.recurring_revenue_score, score.seller_motivation_score,
                        score.owner_independence_score, score.financing_fit_score,
                        score.growth_upside_score, score.risk_score,
                        score.bonus_points, score.deal_killer_penalty,
                        score.cash_flow_yield, score.payback_years,
                        score.estimated_value_low, score.estimated_value_high,
                        score.estimated_max_offer, score.red_flags, score.next_action,
                    ))
    except psycopg2.Error as exc:
        logger.warning("Database write failed; persistence rolled back: %s", exc)
        return None
    finally:
        conn.close()
    logger.info("Persisted %d listings + scores to database (schema=%s).", len(scored), schema)
    return len(scored)


def update_listing_status(listing_url: str, status: str) -> Optional[int]:
    """Set business_listings.status for one listing (matched by listing_url).

    Env-gated exactly like persist_scored_listings: without DATABASE_URL this
    logs a warning and returns None. Returns the number of rows updated.
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.warning("DATABASE_URL not set; skipping status update.")
        return None

    import psycopg2

    schema = os.getenv("DATABASE_SCHEMA") or "public"
    try:
        conn = psycopg2.connect(database_url)
    except psycopg2.Error as exc:
        logger.warning("Database connection failed; skipping status update: %s", exc)
        return None
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SET search_path TO %s", (schema,))
                cur.execute(
                    "UPDATE business_listings SET status = %s WHERE listing_url = %s",
                    (status, listing_url),
                )
                updated = cur.rowcount
    except psycopg2.Error as exc:
        logger.warning("Database status update failed; skipped: %s", exc)
        return None
    finally:
        conn.close()
    logger.info("Updated status=%s for %s (%d row(s), schema=%s).",
                status, listing_url, updated, schema)
    return updated

"""Nightly match job: filter the shared pool; do not rescore (RD-10)."""

from __future__ import annotations

from apps.api.db import get_customer_connection, get_pool_connection
from src.scoring import normalized_industry_key

FINANCING_RANK = {"majority_carry": 1, "possible": 2, "full": 3}


def match_tenant(tenant_id: str) -> int:
    with get_customer_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT states, metros, industries, asking_min, asking_max,
                       sde_min, sde_max, financing_floor, score_threshold
                FROM tenant_criteria WHERE tenant_id = %s
                """,
                (tenant_id,),
            )
            row = cur.fetchone()
            if row is None:
                return 0
            (
                states,
                metros,
                industries,
                asking_min,
                asking_max,
                sde_min,
                sde_max,
                financing_floor,
                score_threshold,
            ) = row
            floor_rank = FINANCING_RANK.get((financing_floor or "full").lower(), 3)

            with get_pool_connection() as pool:
                with pool.cursor() as pcur:
                    pcur.execute(
                        """
                        SELECT l.id, l.industry, l.location, l.asking_price, l.sde,
                               COALESCE(l.financing_status, CASE WHEN l.seller_financing THEN 'full' ELSE 'possible' END),
                               ds.total_score
                        FROM business_listings l
                        JOIN LATERAL (
                            SELECT total_score FROM deal_scores
                            WHERE listing_id = l.id
                            ORDER BY scored_at DESC LIMIT 1
                        ) ds ON true
                        """
                    )
                    listings = pcur.fetchall()

            upserted = 0
            for (
                listing_id,
                industry,
                location,
                asking,
                sde,
                financing_status,
                total_score,
            ) in listings:
                key = normalized_industry_key(industry or "")
                wanted = {normalized_industry_key(i) for i in (industries or [])}
                if wanted and key not in wanted:
                    continue
                loc = (location or "").upper()
                geo_ok = True
                if states:
                    geo_ok = any(str(s).upper() in loc for s in states)
                if metros:
                    geo_ok = geo_ok and any(str(m).upper() in loc for m in metros)
                if not geo_ok:
                    continue
                if asking_min is not None and asking is not None and float(asking) < float(asking_min):
                    continue
                if asking_max is not None and asking is not None and float(asking) > float(asking_max):
                    continue
                if sde_min is not None and sde is not None and float(sde) < float(sde_min):
                    continue
                if sde_max is not None and sde is not None and float(sde) > float(sde_max):
                    continue
                rank = FINANCING_RANK.get(str(financing_status).lower(), 0)
                if rank < floor_rank:
                    continue
                if float(total_score) < float(score_threshold):
                    continue
                cur.execute(
                    """
                    INSERT INTO tenant_matches (tenant_id, listing_id, first_seen_score, last_score)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (tenant_id, listing_id) DO UPDATE SET last_score = EXCLUDED.last_score
                    """,
                    (tenant_id, listing_id, total_score, total_score),
                )
                upserted += 1
        conn.commit()
    return upserted


def match_all_tenants() -> dict[str, int]:
    with get_customer_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT tenant_id::text FROM tenant_criteria")
            ids = [r[0] for r in cur.fetchall()]
    return {tid: match_tenant(tid) for tid in ids}

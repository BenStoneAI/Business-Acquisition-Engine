"""Customer dashboard HTTP surfaces. All require tenant context."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from apps.api.db import get_customer_connection, get_pool_connection
from apps.api.match import match_tenant
from apps.api.max_offer import max_offer_constraints
from apps.api.tenant import (
    criteria_saved,
    ensure_tenant_exists,
    get_tenant,
    parse_tenant_id,
)
from src.financing_filter import financing_status
from src.models import Listing, ScoreBreakdown
from src.response_engine import build_response_package, render_package_markdown
from src import response_engine as response_engine_mod
from src.scoring import normalized_industry_key, score_listing

router = APIRouter(prefix="/customer", tags=["customer"])

REPO_ROOT = Path(__file__).resolve().parents[3]
INDUSTRY_YAML = REPO_ROOT / "config" / "industry_formulas.yaml"


def _industries() -> dict:
    with INDUSTRY_YAML.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)["industries"]


def _score_to_breakdown(row: dict) -> ScoreBreakdown:
    return ScoreBreakdown(
        financial_score=float(row.get("financial_score") or 0),
        industry_score=float(row.get("industry_score") or 0),
        recurring_revenue_score=float(row.get("recurring_revenue_score") or 0),
        seller_motivation_score=float(row.get("seller_motivation_score") or 0),
        owner_independence_score=float(row.get("owner_independence_score") or 0),
        financing_fit_score=float(row.get("financing_fit_score") or 0),
        growth_upside_score=float(row.get("growth_upside_score") or 0),
        risk_score=float(row.get("risk_score") or 0),
        bonus_points=float(row.get("bonus_points") or 0),
        deal_killer_penalty=float(row.get("deal_killer_penalty") or 0),
        total_score=float(row["total_score"]),
        bucket=row["bucket"],
        cash_flow_yield=float(row["cash_flow_yield"]) if row.get("cash_flow_yield") is not None else None,
        payback_years=float(row["payback_years"]) if row.get("payback_years") is not None else None,
        estimated_value_low=float(row["estimated_value_low"]) if row.get("estimated_value_low") is not None else None,
        estimated_value_high=float(row["estimated_value_high"]) if row.get("estimated_value_high") is not None else None,
        estimated_max_offer=float(row["estimated_max_offer"]) if row.get("estimated_max_offer") is not None else None,
        red_flags=list(row.get("red_flags") or []),
        next_action=row.get("next_action") or "",
    )


def _num(row: dict, key: str):
    val = row.get(key)
    return float(val) if val is not None else None


def _int(row: dict, key: str):
    val = row.get(key)
    return int(val) if val is not None else None


def _listing_from_row(row: dict) -> Listing:
    return Listing(
        business_name=row["business_name"],
        industry=row["industry"],
        location=row.get("location") or "",
        asking_price=_num(row, "asking_price"),
        revenue=_num(row, "revenue"),
        sde=_num(row, "sde"),
        ebitda=_num(row, "ebitda"),
        real_estate_included=bool(row.get("real_estate_included")),
        seller_financing=bool(row.get("seller_financing")),
        sba_prequalified=bool(row.get("sba_prequalified")),
        reason_for_sale=row.get("reason_for_sale"),
        years_in_business=_int(row, "years_in_business"),
        employees=_int(row, "employees"),
        owner_hours_per_week=_num(row, "owner_hours_per_week"),
        recurring_revenue_pct=_num(row, "recurring_revenue_pct"),
        customer_concentration_pct=_num(row, "customer_concentration_pct"),
        equipment_condition=row.get("equipment_condition"),
        lease_years_remaining=_num(row, "lease_years_remaining"),
        source=row.get("source"),
        listing_url=row.get("listing_url"),
        notes=row.get("notes") or "",
    )


class SettingsBody(BaseModel):
    states: list[str] = Field(default_factory=list)
    metros: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    asking_min: float | None = None
    asking_max: float | None = None
    sde_min: float | None = None
    sde_max: float | None = None
    financing_floor: str = "full"
    score_threshold: float = 80
    buyer_name: str | None = None
    buyer_entity: str | None = None
    credibility_blurb: str | None = None
    target_close_timeline: str | None = None


class StageBody(BaseModel):
    stage: str


class RescoreBody(BaseModel):
    verified_sde: float | None = None
    verified_revenue: float | None = None
    verified_asking: float | None = None


@router.get("/settings")
def get_settings(tenant_id: str = Depends(parse_tenant_id)) -> dict:
    ensure_tenant_exists(tenant_id)
    profile = get_tenant(tenant_id)
    with get_customer_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM tenant_criteria WHERE tenant_id = %s", (tenant_id,))
            crit = cur.fetchone()
            crit_cols = [d[0] for d in cur.description] if cur.description else []
    criteria = dict(zip(crit_cols, crit)) if crit else None
    if criteria:
        criteria["tenant_id"] = str(criteria["tenant_id"])
        if criteria.get("updated_at"):
            criteria["updated_at"] = criteria["updated_at"].isoformat()
    industries = _industries()
    return {
        "tenant": profile,
        "criteria": criteria,
        "wizard_required": criteria is None,
        "industries": [
            {"id": k, "display_name": v["display_name"], "on_thesis": k not in {"restaurant", "auto_repair"}}
            for k, v in industries.items()
        ],
        "forbidden_fields": [
            "DATABASE_URL",
            "CUSTOMER_DATABASE_URL",
            "IMAP",
            "SMTP",
            "TELEGRAM_BOT_TOKEN",
            "mailbox",
        ],
    }


@router.put("/settings")
def put_settings(body: SettingsBody, tenant_id: str = Depends(parse_tenant_id)) -> dict:
    ensure_tenant_exists(tenant_id)
    with get_customer_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenant_criteria (
                  tenant_id, states, metros, industries, asking_min, asking_max,
                  sde_min, sde_max, financing_floor, score_threshold
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (tenant_id) DO UPDATE SET
                  states = EXCLUDED.states,
                  metros = EXCLUDED.metros,
                  industries = EXCLUDED.industries,
                  asking_min = EXCLUDED.asking_min,
                  asking_max = EXCLUDED.asking_max,
                  sde_min = EXCLUDED.sde_min,
                  sde_max = EXCLUDED.sde_max,
                  financing_floor = EXCLUDED.financing_floor,
                  score_threshold = EXCLUDED.score_threshold,
                  updated_at = now()
                """,
                (
                    tenant_id,
                    body.states,
                    body.metros,
                    body.industries,
                    body.asking_min,
                    body.asking_max,
                    body.sde_min,
                    body.sde_max,
                    body.financing_floor,
                    body.score_threshold,
                ),
            )
            cur.execute(
                """
                UPDATE tenant_settings SET
                  buyer_name = COALESCE(%s, buyer_name),
                  buyer_entity = COALESCE(%s, buyer_entity),
                  credibility_blurb = COALESCE(%s, credibility_blurb),
                  target_close_timeline = COALESCE(%s, target_close_timeline)
                WHERE tenant_id = %s
                """,
                (
                    body.buyer_name,
                    body.buyer_entity,
                    body.credibility_blurb,
                    body.target_close_timeline,
                    tenant_id,
                ),
            )
            cur.execute(
                "UPDATE tenants SET setup_completed_at = now() WHERE tenant_id = %s AND setup_completed_at IS NULL",
                (tenant_id,),
            )
        conn.commit()
    match_tenant(tenant_id)
    return get_settings(tenant_id)


@router.post("/settings/test-match")
def test_match(tenant_id: str = Depends(parse_tenant_id)) -> dict:
    ensure_tenant_exists(tenant_id)
    if not criteria_saved(tenant_id):
        raise HTTPException(status_code=400, detail="Save criteria first.")
    count = match_tenant(tenant_id)
    opps = list_opportunities(tenant_id)
    return {"match_count": count, "top": opps["opportunities"][:5]}


@router.get("/runs/latest")
def latest_run(tenant_id: str = Depends(parse_tenant_id)) -> dict:
    ensure_tenant_exists(tenant_id)
    with get_pool_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT ran_at, listing_count FROM pool_runs ORDER BY ran_at DESC LIMIT 1")
            row = cur.fetchone()
    if not row:
        return {"ran_at": None, "listing_count": 0}
    return {"ran_at": row[0].isoformat(), "listing_count": row[1]}


@router.get("/radar/summary")
def radar_summary(tenant_id: str = Depends(parse_tenant_id)) -> dict:
    ensure_tenant_exists(tenant_id)
    wizard = not criteria_saved(tenant_id)
    run = latest_run(tenant_id)
    with get_customer_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT count(*) FILTER (WHERE hidden = false),
                       count(*) FILTER (WHERE hidden = false AND last_score >= 90)
                FROM tenant_matches WHERE tenant_id = %s
                """,
                (tenant_id,),
            )
            matches, strong = cur.fetchone()
    return {
        "wizard_required": wizard,
        "new_matches": int(matches or 0),
        "strong_scores": int(strong or 0),
        "price_drops": 0,
        "full_carry": 0,
        "last_run_at": run.get("ran_at"),
        "empty_message": None
        if wizard or matches
        else f"No matches yet. Radar last ran at {run.get('ran_at') or 'unknown'}. Widen your criteria?",
    }


def list_opportunities(tenant_id: str) -> dict:
    with get_customer_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT l.id, l.business_name, l.industry, l.location, l.asking_price, l.sde,
                       l.financing_status, l.source, m.last_score, ds.bucket, ds.estimated_max_offer
                FROM tenant_matches m
                JOIN business_listings l ON l.id = m.listing_id
                JOIN LATERAL (
                    SELECT bucket, estimated_max_offer FROM deal_scores
                    WHERE listing_id = l.id ORDER BY scored_at DESC LIMIT 1
                ) ds ON true
                WHERE m.tenant_id = %s AND m.hidden = false
                ORDER BY m.last_score DESC
                """,
                (tenant_id,),
            )
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
    items = []
    for row in rows:
        item = dict(zip(cols, row))
        for k in ("asking_price", "sde", "last_score", "estimated_max_offer"):
            if item.get(k) is not None:
                item[k] = float(item[k])
        items.append(item)
    return {"opportunities": items}


@router.get("/opportunities")
def get_opportunities(tenant_id: str = Depends(parse_tenant_id)) -> dict:
    ensure_tenant_exists(tenant_id)
    if not criteria_saved(tenant_id):
        return {"wizard_required": True, "opportunities": []}
    payload = list_opportunities(tenant_id)
    payload["wizard_required"] = False
    if not payload["opportunities"]:
        run = latest_run(tenant_id)
        payload["empty_message"] = (
            f"No matches yet. Radar last ran at {run.get('ran_at') or 'unknown'}. Widen your criteria?"
        )
    return payload


@router.get("/opportunities/{listing_id}")
def get_opportunity(listing_id: int, tenant_id: str = Depends(parse_tenant_id)) -> dict:
    ensure_tenant_exists(tenant_id)
    with get_customer_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM tenant_matches WHERE tenant_id = %s AND listing_id = %s AND hidden = false",
                (tenant_id, listing_id),
            )
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="Listing not found.")
            cur.execute("SELECT * FROM business_listings WHERE id = %s", (listing_id,))
            listing_row = dict(zip([d[0] for d in cur.description], cur.fetchone()))
            cur.execute(
                "SELECT * FROM deal_scores WHERE listing_id = %s ORDER BY scored_at DESC LIMIT 1",
                (listing_id,),
            )
            score_row = dict(zip([d[0] for d in cur.description], cur.fetchone()))
    listing = _listing_from_row(listing_row)
    live = score_listing(listing, _industries())
    cfg = _industries().get(normalized_industry_key(listing.industry), {})
    constraints = max_offer_constraints(listing, cfg)
    return {
        "listing": listing_row,
        "score": score_row,
        "live_score": live.total_score,
        "max_offer": constraints,
        "financing_status": financing_status(listing),
    }


@router.post("/opportunities/{listing_id}/watch")
def watch(listing_id: int, tenant_id: str = Depends(parse_tenant_id)) -> dict:
    ensure_tenant_exists(tenant_id)
    with get_customer_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM tenant_matches WHERE tenant_id = %s AND listing_id = %s",
                (tenant_id, listing_id),
            )
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="Listing not found.")
            cur.execute(
                """
                INSERT INTO tenant_watchlist (tenant_id, listing_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (tenant_id, listing_id),
            )
        conn.commit()
    return {"ok": True}


@router.delete("/opportunities/{listing_id}/watch")
def unwatch(listing_id: int, tenant_id: str = Depends(parse_tenant_id)) -> dict:
    ensure_tenant_exists(tenant_id)
    with get_customer_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM tenant_watchlist WHERE tenant_id = %s AND listing_id = %s",
                (tenant_id, listing_id),
            )
        conn.commit()
    return {"ok": True}


@router.post("/opportunities/{listing_id}/hide")
def hide(listing_id: int, tenant_id: str = Depends(parse_tenant_id)) -> dict:
    ensure_tenant_exists(tenant_id)
    with get_customer_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tenant_matches SET hidden = true WHERE tenant_id = %s AND listing_id = %s",
                (tenant_id, listing_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Listing not found.")
        conn.commit()
    return {"ok": True}


@router.post("/opportunities/{listing_id}/interested")
def interested(listing_id: int, tenant_id: str = Depends(parse_tenant_id)) -> dict:
    ensure_tenant_exists(tenant_id)
    profile = get_tenant(tenant_id) or {}
    with get_customer_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM tenant_matches WHERE tenant_id = %s AND listing_id = %s",
                (tenant_id, listing_id),
            )
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="Listing not found.")
            cur.execute("SELECT * FROM business_listings WHERE id = %s", (listing_id,))
            listing_row = dict(zip([d[0] for d in cur.description], cur.fetchone()))
            cur.execute(
                "SELECT * FROM deal_scores WHERE listing_id = %s ORDER BY scored_at DESC LIMIT 1",
                (listing_id,),
            )
            score_row = dict(zip([d[0] for d in cur.description], cur.fetchone()))
            listing = _listing_from_row(listing_row)
            score = _score_to_breakdown(score_row)
            previous = (
                response_engine_mod.BUYER_NAME,
                response_engine_mod.BUYER_EMAIL,
                response_engine_mod.BUYER_CREDIBILITY,
            )
            response_engine_mod.BUYER_NAME = profile.get("buyer_name") or previous[0]
            response_engine_mod.BUYER_EMAIL = profile.get("buyer_entity") or previous[1]
            response_engine_mod.BUYER_CREDIBILITY = profile.get("credibility_blurb") or previous[2]
            try:
                pkg = build_response_package(listing, score)
                md = render_package_markdown(pkg)
            finally:
                (
                    response_engine_mod.BUYER_NAME,
                    response_engine_mod.BUYER_EMAIL,
                    response_engine_mod.BUYER_CREDIBILITY,
                ) = previous
            deal_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO tenant_deals (id, tenant_id, listing_id, stage)
                VALUES (%s, %s, %s, 'contacted')
                ON CONFLICT (tenant_id, listing_id) DO UPDATE SET updated_at = now()
                RETURNING id
                """,
                (deal_id, tenant_id, listing_id),
            )
            deal_id = str(cur.fetchone()[0])
            cur.execute(
                """
                INSERT INTO tenant_packets (deal_id, tenant_id, markdown)
                VALUES (%s, %s, %s)
                ON CONFLICT (deal_id) DO UPDATE SET markdown = EXCLUDED.markdown
                """,
                (deal_id, tenant_id, md),
            )
            cur.execute(
                "INSERT INTO tenant_deal_stage_history (deal_id, tenant_id, stage) VALUES (%s, %s, 'contacted')",
                (deal_id, tenant_id),
            )
        conn.commit()
    return {"deal_id": deal_id}


@router.get("/deals")
def list_deals(tenant_id: str = Depends(parse_tenant_id)) -> dict:
    ensure_tenant_exists(tenant_id)
    with get_customer_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.id::text, d.stage, d.updated_at, l.business_name, l.asking_price
                FROM tenant_deals d
                JOIN business_listings l ON l.id = d.listing_id
                WHERE d.tenant_id = %s
                ORDER BY d.updated_at DESC
                """,
                (tenant_id,),
            )
            rows = [
                {
                    "id": r[0],
                    "stage": r[1],
                    "updated_at": r[2].isoformat(),
                    "business_name": r[3],
                    "asking_price": float(r[4]) if r[4] is not None else None,
                    "next_follow_up": (date.today() + timedelta(days=3)).isoformat(),
                }
                for r in cur.fetchall()
            ]
    return {"deals": rows}


@router.get("/deals/{deal_id}")
def get_deal(deal_id: str, tenant_id: str = Depends(parse_tenant_id)) -> dict:
    ensure_tenant_exists(tenant_id)
    with get_customer_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id::text, stage, listing_id FROM tenant_deals WHERE id = %s AND tenant_id = %s",
                (deal_id, tenant_id),
            )
            row = cur.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Deal not found.")
            cur.execute(
                "SELECT markdown FROM tenant_packets WHERE deal_id = %s AND tenant_id = %s",
                (deal_id, tenant_id),
            )
            pkt = cur.fetchone()
    return {"id": row[0], "stage": row[1], "listing_id": row[2], "packet_markdown": pkt[0] if pkt else ""}


@router.post("/deals/{deal_id}/stage")
def set_stage(deal_id: str, body: StageBody, tenant_id: str = Depends(parse_tenant_id)) -> dict:
    ensure_tenant_exists(tenant_id)
    with get_customer_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tenant_deals SET stage = %s, updated_at = now() WHERE id = %s AND tenant_id = %s",
                (body.stage, deal_id, tenant_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Deal not found.")
            cur.execute(
                "INSERT INTO tenant_deal_stage_history (deal_id, tenant_id, stage) VALUES (%s, %s, %s)",
                (deal_id, tenant_id, body.stage),
            )
        conn.commit()
    return {"ok": True, "stage": body.stage}


@router.post("/deals/{deal_id}/rescore")
def rescore(deal_id: str, body: RescoreBody, tenant_id: str = Depends(parse_tenant_id)) -> dict:
    ensure_tenant_exists(tenant_id)
    with get_customer_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT l.* FROM tenant_deals d
                JOIN business_listings l ON l.id = d.listing_id
                WHERE d.id = %s AND d.tenant_id = %s
                """,
                (deal_id, tenant_id),
            )
            row = cur.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Deal not found.")
            listing_row = dict(zip([d[0] for d in cur.description], row))
            listing = _listing_from_row(listing_row)
            if body.verified_sde is not None:
                listing.sde = body.verified_sde
            if body.verified_revenue is not None:
                listing.revenue = body.verified_revenue
            if body.verified_asking is not None:
                listing.asking_price = body.verified_asking
            scored = score_listing(listing, _industries())
            cur.execute(
                """
                INSERT INTO tenant_rescores (
                  deal_id, tenant_id, verified_sde, verified_revenue, verified_asking,
                  total_score, estimated_max_offer
                ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    deal_id,
                    tenant_id,
                    body.verified_sde,
                    body.verified_revenue,
                    body.verified_asking,
                    scored.total_score,
                    scored.estimated_max_offer,
                ),
            )
        conn.commit()
    return {
        "total_score": scored.total_score,
        "estimated_max_offer": scored.estimated_max_offer,
        "shared_deal_scores_mutated": False,
    }


@router.get("/deals/{deal_id}/packet.md")
def packet_md(deal_id: str, tenant_id: str = Depends(parse_tenant_id)):
    from fastapi.responses import PlainTextResponse

    data = get_deal(deal_id, tenant_id)
    return PlainTextResponse(data["packet_markdown"] or "", media_type="text/markdown")


@router.get("/watchlist")
def watchlist(tenant_id: str = Depends(parse_tenant_id)) -> dict:
    ensure_tenant_exists(tenant_id)
    with get_customer_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT l.id, l.business_name, w.notes, w.priority
                FROM tenant_watchlist w
                JOIN business_listings l ON l.id = w.listing_id
                WHERE w.tenant_id = %s
                """,
                (tenant_id,),
            )
            items = [
                {"listing_id": r[0], "business_name": r[1], "notes": r[2], "priority": r[3]}
                for r in cur.fetchall()
            ]
    return {"watchlist": items}


@router.get("/alerts")
def get_alerts(tenant_id: str = Depends(parse_tenant_id)) -> dict:
    ensure_tenant_exists(tenant_id)
    with get_customer_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT email_enabled, telegram_chat_id, digest, threshold, price_drop_alerts FROM tenant_alert_prefs WHERE tenant_id = %s", (tenant_id,))
            row = cur.fetchone()
            cur.execute(
                "SELECT channel, body, created_at FROM tenant_alert_log WHERE tenant_id = %s ORDER BY created_at DESC LIMIT 50",
                (tenant_id,),
            )
            log = [
                {"channel": r[0], "body": r[1], "created_at": r[2].isoformat()}
                for r in cur.fetchall()
            ]
    prefs = None
    if row:
        prefs = {
            "email_enabled": row[0],
            "telegram_chat_id": row[1],
            "digest": row[2],
            "threshold": float(row[3]),
            "price_drop_alerts": row[4],
        }
    return {"prefs": prefs, "log": log}

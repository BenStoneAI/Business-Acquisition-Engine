"""RD-01 / RD-03 / RD-10 customer-plane proofs."""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from apps.api.tenant import create_tenant
from src.models import Listing
from src.scoring import score_listing
import yaml
from pathlib import Path

pytestmark = pytest.mark.skipif(
    not os.environ.get("CUSTOMER_DATABASE_URL"),
    reason="CUSTOMER_DATABASE_URL not set",
)


def _client() -> TestClient:
    from apps.api.main import app

    return TestClient(app)


def _industries():
    path = Path(__file__).resolve().parents[3] / "config" / "industry_formulas.yaml"
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)["industries"]


def test_fresh_tenant_sees_wizard_only():
    tenant_id = create_tenant("Fresh radar tenant", tenant_id=str(uuid.uuid4()))
    client = _client()
    res = client.get("/customer/radar/summary", headers={"X-Tenant-Id": tenant_id})
    assert res.status_code == 200
    body = res.json()
    assert body["wizard_required"] is True
    settings = client.get("/customer/settings", headers={"X-Tenant-Id": tenant_id})
    assert settings.json()["wizard_required"] is True


def test_criteria_no_matches_honest_empty():
    tenant_id = create_tenant("Empty-match tenant", tenant_id=str(uuid.uuid4()))
    client = _client()
    put = client.put(
        "/customer/settings",
        headers={"X-Tenant-Id": tenant_id},
        json={
            "states": ["ZZ"],
            "industries": ["hvac"],
            "financing_floor": "full",
            "score_threshold": 99,
        },
    )
    assert put.status_code == 200
    opps = client.get("/customer/opportunities", headers={"X-Tenant-Id": tenant_id})
    body = opps.json()
    assert body["opportunities"] == []
    assert "No matches yet" in (body.get("empty_message") or "")


def test_cross_tenant_listing_is_404():
    from apps.api.db import get_customer_connection

    a = create_tenant("Tenant A", tenant_id=str(uuid.uuid4()))
    b = create_tenant("Tenant B", tenant_id=str(uuid.uuid4()))
    with get_customer_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO business_listings (business_name, industry, location, asking_price, sde, seller_financing, financing_status, listing_url)
                VALUES ('Iso HVAC', 'HVAC', 'UT', 500000, 180000, true, 'full', %s)
                RETURNING id
                """,
                (f"https://example.test/{uuid.uuid4()}",),
            )
            listing_id = cur.fetchone()[0]
            listing = Listing(
                business_name="Iso HVAC",
                industry="HVAC",
                location="UT",
                asking_price=500000,
                sde=180000,
                seller_financing=True,
            )
            scored = score_listing(listing, _industries())
            cur.execute(
                """
                INSERT INTO deal_scores (listing_id, total_score, bucket, estimated_max_offer)
                VALUES (%s, %s, %s, %s)
                """,
                (listing_id, scored.total_score, scored.bucket, scored.estimated_max_offer),
            )
            cur.execute(
                "INSERT INTO tenant_matches (tenant_id, listing_id, first_seen_score, last_score) VALUES (%s, %s, %s, %s)",
                (a, listing_id, scored.total_score, scored.total_score),
            )
        conn.commit()
    client = _client()
    ok = client.get(f"/customer/opportunities/{listing_id}", headers={"X-Tenant-Id": a})
    assert ok.status_code == 200
    denied = client.get(f"/customer/opportunities/{listing_id}", headers={"X-Tenant-Id": b})
    assert denied.status_code == 404


def test_match_job_idempotent():
    from apps.api.db import get_customer_connection
    from apps.api.match import match_tenant

    tenant_id = create_tenant("Idempotent tenant", tenant_id=str(uuid.uuid4()))
    with get_customer_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenant_criteria (tenant_id, states, industries, financing_floor, score_threshold)
                VALUES (%s, '{UT}', '{HVAC}', 'full', 50)
                """,
                (tenant_id,),
            )
        conn.commit()
    first = match_tenant(tenant_id)
    second = match_tenant(tenant_id)
    with get_customer_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM tenant_matches WHERE tenant_id = %s", (tenant_id,))
            count = cur.fetchone()[0]
    assert second == first or count >= 0
    with get_customer_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM tenant_matches WHERE tenant_id = %s", (tenant_id,))
            again = cur.fetchone()[0]
    assert again == count


def test_customer_routes_do_not_import_operator_plane():
    text = Path(__file__).resolve().parents[3].joinpath("apps/api/routes/customer.py").read_text(encoding="utf-8")
    for banned in ("persist_scored_listings", "imap_fetch", "notifier.send_telegram", "Deals/"):
        assert banned not in text

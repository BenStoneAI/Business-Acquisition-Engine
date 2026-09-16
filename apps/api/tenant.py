"""Tenant helpers on the customer plane. Cross-tenant IDs return 404."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import Header, HTTPException

from apps.api.db import get_customer_connection


def parse_tenant_id(x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-Id")) -> str:
    if not x_tenant_id or not x_tenant_id.strip():
        raise HTTPException(status_code=401, detail="X-Tenant-Id header is required.")
    try:
        return str(uuid.UUID(x_tenant_id.strip()))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid X-Tenant-Id.") from exc


def create_tenant(name: str, *, tenant_id: str | None = None) -> str:
    tenant_id = str(tenant_id or uuid.uuid4())
    uuid.UUID(tenant_id)
    with get_customer_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenants (tenant_id, name)
                VALUES (%s, %s)
                ON CONFLICT (tenant_id) DO UPDATE SET name = EXCLUDED.name
                """,
                (tenant_id, name),
            )
            cur.execute(
                """
                INSERT INTO tenant_alert_prefs (tenant_id)
                VALUES (%s)
                ON CONFLICT (tenant_id) DO NOTHING
                """,
                (tenant_id,),
            )
            cur.execute(
                """
                INSERT INTO tenant_settings (tenant_id)
                VALUES (%s)
                ON CONFLICT (tenant_id) DO NOTHING
                """,
                (tenant_id,),
            )
        conn.commit()
    return tenant_id


def ensure_tenant_exists(tenant_id: str) -> None:
    with get_customer_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM tenants WHERE tenant_id = %s", (tenant_id,))
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail="Tenant not found.")


def get_tenant(tenant_id: str) -> dict | None:
    with get_customer_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.tenant_id::text, t.name, t.setup_completed_at, t.created_at,
                       s.buyer_name, s.buyer_entity, s.credibility_blurb, s.target_close_timeline
                FROM tenants t
                LEFT JOIN tenant_settings s ON s.tenant_id = t.tenant_id
                WHERE t.tenant_id = %s
                """,
                (tenant_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            cols = [d[0] for d in cur.description]
            data = dict(zip(cols, row))
    for key in ("setup_completed_at", "created_at"):
        if data.get(key) is not None:
            data[key] = data[key].isoformat()
    return data


def criteria_saved(tenant_id: str) -> bool:
    with get_customer_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM tenant_criteria WHERE tenant_id = %s", (tenant_id,))
            return cur.fetchone() is not None

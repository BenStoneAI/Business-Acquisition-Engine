"""Tenant helpers on the customer plane. Cross-tenant IDs return 404."""

from __future__ import annotations

import hmac
import hashlib
import os
import uuid
from typing import Optional

from fastapi import Cookie, Header, HTTPException

from apps.api.db import get_customer_connection

SESSION_COOKIE = "radar_session"


def _session_secret() -> str:
    return os.environ.get("RADAR_PORTAL_HANDOFF_SECRET") or os.environ.get("ARTIFACT_SIGNING_KEY") or ""


def sign_tenant_session(tenant_id: str) -> str:
    secret = _session_secret()
    if not secret:
        raise RuntimeError("handoff secret missing")
    sig = hmac.new(secret.encode(), tenant_id.encode(), hashlib.sha256).hexdigest()
    return f"{tenant_id}.{sig}"


def parse_tenant_session(value: str | None) -> str | None:
    if not value or "." not in value:
        return None
    tenant_id, sig = value.split(".", 1)
    try:
        uuid.UUID(tenant_id)
    except ValueError:
        return None
    expected = sign_tenant_session(tenant_id)
    if not hmac.compare_digest(expected, value):
        return None
    return tenant_id


def parse_tenant_id(
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-Id"),
    radar_session: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
) -> str:
    from_cookie = parse_tenant_session(radar_session)
    if from_cookie:
        if x_tenant_id and x_tenant_id.strip() and str(uuid.UUID(x_tenant_id.strip())) != from_cookie:
            raise HTTPException(status_code=404, detail="Tenant not found.")
        return from_cookie
    allow_header = os.environ.get("RADAR_ALLOW_HEADER_TENANT") == "1"
    if allow_header and x_tenant_id and x_tenant_id.strip():
        try:
            return str(uuid.UUID(x_tenant_id.strip()))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid X-Tenant-Id.") from exc
    raise HTTPException(status_code=401, detail="Sign in from the Aptria Customer Portal.")


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

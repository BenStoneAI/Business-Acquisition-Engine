"""Service-to-service tenant provisioning for Aptria portal."""

from __future__ import annotations

import hmac
import os
import uuid

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from apps.api.tenant import create_tenant, get_tenant

router = APIRouter(prefix="/internal/portal", tags=["portal-internal"])


class ProvisionTenantRequest(BaseModel):
    tenant_id: str = Field(min_length=36, max_length=36)
    name: str = Field(min_length=1, max_length=200)


def _require_service_key(key: str | None) -> None:
    expected = os.environ.get("RADAR_PORTAL_SERVICE_KEY")
    if not expected or not key or not hmac.compare_digest(expected.encode(), key.encode()):
        raise HTTPException(status_code=401, detail="Unauthorized.")


@router.post("/tenants")
def provision_tenant(
    body: ProvisionTenantRequest,
    x_aptria_portal_service_key: str | None = Header(default=None, alias="X-Aptria-Portal-Service-Key"),
) -> dict:
    _require_service_key(x_aptria_portal_service_key)
    try:
        uuid.UUID(body.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid tenant_id.") from exc
    existing = get_tenant(body.tenant_id)
    if existing:
        return {"tenant_id": body.tenant_id, "name": existing["name"], "already_exists": True}
    tenant_id = create_tenant(body.name, tenant_id=body.tenant_id)
    return {"tenant_id": tenant_id, "name": body.name, "already_exists": False}

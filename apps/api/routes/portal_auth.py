"""Portal SSO handoff (H-P08 pattern)."""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from apps.api.aptria_handoff import verify_portal_handoff_token
from apps.api.tenant import ensure_tenant_exists

router = APIRouter(tags=["portal-auth"])


class PortalHandoffRequest(BaseModel):
    token: str = Field(min_length=10)


@router.post("/auth/portal-handoff")
def post_portal_handoff(body: PortalHandoffRequest) -> dict:
    secret = os.environ.get("RADAR_PORTAL_HANDOFF_SECRET") or os.environ.get("ARTIFACT_SIGNING_KEY")
    if not secret:
        raise HTTPException(status_code=503, detail="Portal handoff is not configured.")
    payload = verify_portal_handoff_token(body.token, secret)
    if payload is None:
        raise HTTPException(status_code=403, detail="Invalid or expired handoff token.")
    tenant_id = str(payload["tenantId"])
    ensure_tenant_exists(tenant_id)
    return {
        "tenant_id": tenant_id,
        "email": payload["email"],
        "organization_id": payload["organizationId"],
    }

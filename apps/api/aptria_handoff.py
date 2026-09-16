"""HMAC handoff tokens from Aptria Customer Portal. Mirrors omst-handoff.ts."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def verify_portal_handoff_token(token: str, secret: str) -> dict[str, Any] | None:
    if not token or "." not in token:
        return None
    data_part, sig_part = token.split(".", 1)
    expected = hmac.new(secret.encode("utf-8"), data_part.encode("utf-8"), hashlib.sha256).digest()
    expected_sig = base64.urlsafe_b64encode(expected).decode("ascii").rstrip("=")
    if not hmac.compare_digest(sig_part, expected_sig):
        return None
    try:
        payload = json.loads(_b64url_decode(data_part).decode("utf-8"))
    except Exception:
        return None
    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(time.time()):
        return None
    for key in ("tenantId", "userId", "email", "organizationId"):
        if not payload.get(key):
            return None
    return payload

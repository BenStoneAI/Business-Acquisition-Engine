"""Customer-plane connections. Operator DATABASE_URL is never used here."""

from __future__ import annotations

import os
from urllib.parse import urlparse

import psycopg2


class DataPlaneError(RuntimeError):
    """Raised when a data-plane URL is missing or would cross the operator boundary."""


def _normalize_url(url: str) -> str:
    return url.strip()


def _url_fingerprint(url: str) -> tuple[str, str, str]:
    parsed = urlparse(url)
    return (
        (parsed.hostname or "").lower(),
        (parsed.path or "").lstrip("/").lower(),
        (parsed.username or "").lower(),
    )


def get_customer_database_url() -> str:
    url = os.environ.get("CUSTOMER_DATABASE_URL")
    if not url:
        raise DataPlaneError("CUSTOMER_DATABASE_URL is not set — customer plane is not configured")
    url = _normalize_url(url)
    operator = os.environ.get("DATABASE_URL")
    if operator and _url_fingerprint(url) == _url_fingerprint(operator):
        raise DataPlaneError("CUSTOMER_DATABASE_URL must not point at the operator database")
    return url


def get_pool_readonly_url() -> str:
    url = os.environ.get("RADAR_POOL_READONLY_URL")
    if not url:
        raise DataPlaneError("RADAR_POOL_READONLY_URL is not set — pool role is not configured")
    return _normalize_url(url)


def get_customer_connection():
    return psycopg2.connect(get_customer_database_url())


def get_pool_connection():
    return psycopg2.connect(get_pool_readonly_url())

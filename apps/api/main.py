"""Acquisition Radar customer API. Bind 0.0.0.0:$PORT on Render."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.db import DataPlaneError, get_customer_database_url, get_pool_readonly_url
from apps.api.routes import customer, health, portal_auth, portal_internal


def create_app() -> FastAPI:
    try:
        get_customer_database_url()
        get_pool_readonly_url()
    except DataPlaneError as exc:
        # Fail fast in production; tests set the env before importing.
        if os.environ.get("RADAR_ALLOW_UNCONFIGURED") != "1":
            raise
        _ = exc
    app = FastAPI(title="Acquisition Radar by Aptria")
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=(
            r"http://(localhost|127\.0\.0\.1):\d+|"
            r"https://([a-z0-9-]+\.)?vercel\.app|"
            r"https://portal\.aptria\.net"
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(customer.router)
    app.include_router(portal_auth.router)
    app.include_router(portal_internal.router)
    return app


app = create_app()

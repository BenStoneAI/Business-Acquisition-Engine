"""RD-02 data-plane guard."""

import os

import pytest

from apps.api.db import DataPlaneError, get_customer_database_url


def test_customer_url_refuses_operator_fingerprint(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://op@operator.example/radar")
    monkeypatch.setenv("CUSTOMER_DATABASE_URL", "postgresql://op@operator.example/radar")
    with pytest.raises(DataPlaneError):
        get_customer_database_url()


def test_customer_url_requires_env(monkeypatch):
    monkeypatch.delenv("CUSTOMER_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(DataPlaneError):
        get_customer_database_url()

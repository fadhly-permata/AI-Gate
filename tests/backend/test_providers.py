"""Provider CRUD + auto-discovery tests (task B2.2) — hermetic, no on-disk DB.

Mirrors ``test_gateway.py``: an in-memory SQLite engine (StaticPool) replaces
every ``SessionLocal`` binding the router and logger use, so all connections
share one DB. ``respx`` mocks ``httpx`` for the auto-discovery network calls.
"""

from __future__ import annotations

import pytest
import respx
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.config.db as db_mod
import backend.providers_router as providers_router
from backend.config.db import Base
from backend.models import (
    Combo,
    ComboMember,
    Endpoint,
    EndpointBinding,
    LogEntry,
    Provider,
    ProviderModel,
)
from fastapi.testclient import TestClient

from backend.server import app


def _make_sessionmaker() -> sessionmaker:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _patch_db(monkeypatch, sf: sessionmaker) -> None:
    monkeypatch.setattr(db_mod, "SessionLocal", sf)
    monkeypatch.setattr(providers_router, "SessionLocal", sf)


def _client(monkeypatch) -> TestClient:
    sf = _make_sessionmaker()
    _patch_db(monkeypatch, sf)
    return TestClient(app)


OPENAI_MODELS = {
    "object": "list",
    "data": [
        {"id": "gpt-4o", "object": "model", "capabilities": "chat"},
        {"id": "gpt-4o-mini", "object": "model"},
    ],
}


# --- 1. POST creates provider, plaintext api_key, custom_headers echoed ------


def test_post_creates_provider_plaintext_key_and_headers(monkeypatch) -> None:
    client = _client(monkeypatch)
    resp = client.post(
        "/api/providers",
        json={
            "name": "acme",
            "type": "openai-compatible",
            "base_url": "https://acme.test/v1",
            "api_key": "sk-plaintext-secret",
            "enabled": True,
            "custom_headers": {"X-Org": "42"},
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["api_key"] == "sk-plaintext-secret"  # ADR-007 plaintext
    assert body["custom_headers"] == {"X-Org": "42"}
    assert body["name"] == "acme"
    assert body["models"] == []  # discovery mocked below; not here


# --- 2. GET list + GET by id ------------------------------------------------


def test_get_list_and_by_id(monkeypatch) -> None:
    client = _client(monkeypatch)
    created = client.post(
        "/api/providers",
        json={
            "name": "acme",
            "type": "openai-compatible",
            "base_url": "https://acme.test/v1",
            "api_key": "sk-x",
        },
    ).json()

    listing = client.get("/api/providers")
    assert listing.status_code == 200
    assert listing.json()["object"] == "list"
    ids = {p["id"] for p in listing.json()["data"]}
    assert created["id"] in ids

    by_id = client.get(f"/api/providers/{created['id']}")
    assert by_id.status_code == 200
    assert by_id.json()["name"] == "acme"

    missing = client.get("/api/providers/999999")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "provider_not_found"


# --- 3. PUT updates fields incl. api_key (plaintext preserved) --------------


def test_put_updates_fields(monkeypatch) -> None:
    client = _client(monkeypatch)
    created = client.post(
        "/api/providers",
        json={
            "name": "acme",
            "type": "openai-compatible",
            "base_url": "https://acme.test/v1",
            "api_key": "sk-old",
        },
    ).json()

    resp = client.put(
        f"/api/providers/{created['id']}",
        json={"api_key": "sk-new", "enabled": False, "custom_headers": {"A": "B"}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["api_key"] == "sk-new"  # plaintext preserved
    assert body["enabled"] is False
    assert body["custom_headers"] == {"A": "B"}


# --- 4. Auto-discovery on POST (success + failure) --------------------------


@respx.mock
def test_post_auto_discovers_models(monkeypatch) -> None:
    client = _client(monkeypatch)
    respx.get("https://acme.test/v1/models").mock(
        return_value=httpx.Response(200, json=OPENAI_MODELS)
    )
    resp = client.post(
        "/api/providers",
        json={
            "name": "acme",
            "type": "openai-compatible",
            "base_url": "https://acme.test/v1",
            "api_key": "sk-x",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    model_ids = {m["model_id"] for m in body["models"]}
    assert model_ids == {"gpt-4o", "gpt-4o-mini"}


@respx.mock
def test_post_discovery_failure_still_201_and_logs_warning(monkeypatch) -> None:
    sf = _make_sessionmaker()
    _patch_db(monkeypatch, sf)
    client = TestClient(app)
    respx.get("https://acme.test/v1/models").mock(
        side_effect=httpx.ConnectError("boom")
    )
    resp = client.post(
        "/api/providers",
        json={
            "name": "acme",
            "type": "openai-compatible",
            "base_url": "https://acme.test/v1",
            "api_key": "sk-x",
        },
    )
    # Provider created, discovery failed -> still 201 with empty models.
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] is not None
    assert body["models"] == []

    # A warning LogEntry must exist (ADR-011).
    with sf() as session:
        warns = (
            session.query(LogEntry)
            .filter_by(severity="warning", source="backend.providers.router")
            .all()
        )
    assert len(warns) >= 1
    assert "discovery" in warns[0].message.lower()


# --- 5. POST /discover success replaces; failure ok:false -------------------


@respx.mock
def test_discover_endpoint_success_replaces(monkeypatch) -> None:
    client = _client(monkeypatch)
    created = client.post(
        "/api/providers",
        json={
            "name": "acme",
            "type": "openai-compatible",
            "base_url": "https://acme.test/v1",
            "api_key": "sk-x",
        },
    ).json()

    respx.get("https://acme.test/v1/models").mock(
        return_value=httpx.Response(200, json=OPENAI_MODELS)
    )
    resp = client.post(f"/api/providers/{created['id']}/discover")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert {m["model_id"] for m in body["models"]} == {"gpt-4o", "gpt-4o-mini"}


@respx.mock
def test_discover_endpoint_failure_returns_ok_false(monkeypatch) -> None:
    client = _client(monkeypatch)
    created = client.post(
        "/api/providers",
        json={
            "name": "acme",
            "type": "openai-compatible",
            "base_url": "https://acme.test/v1",
            "api_key": "sk-x",
        },
    ).json()

    respx.get("https://acme.test/v1/models").mock(
        return_value=httpx.Response(500, text="server error")
    )
    resp = client.post(f"/api/providers/{created['id']}/discover")
    assert resp.status_code == 200  # never 500
    body = resp.json()
    assert body["ok"] is False
    assert "error" in body


# --- 6. DELETE cascades ComboMember + EndpointBinding -----------------------


def test_delete_cascades(monkeypatch) -> None:
    sf = _make_sessionmaker()
    _patch_db(monkeypatch, sf)
    with sf() as session:
        provider = Provider(
            name="acme",
            type="openai-compatible",
            base_url="https://acme.test/v1",
            api_key="sk-x",
        )
        session.add(provider)
        session.flush()
        pid = provider.id
        session.add(
            ProviderModel(
                provider_id=pid,
                model_id="gpt-4o",
                model_name="gpt-4o",
                capabilities="chat",
            )
        )
        combo = Combo(name="c", strategy="fallback", enabled=True)
        session.add(combo)
        session.flush()
        session.add(
            ComboMember(combo_id=combo.id, provider_id=pid, priority=0, weight=1.0)
        )
        endpoint = Endpoint(name="e", listen_host="127.0.0.1", listen_port=8000)
        session.add(endpoint)
        session.flush()
        session.add(
            EndpointBinding(
                endpoint_id=endpoint.id, bind_type="provider", bind_id=pid
            )
        )
        # a non-matching binding must survive
        session.add(
            EndpointBinding(
                endpoint_id=endpoint.id, bind_type="combo", bind_id=combo.id
            )
        )
        session.commit()

    client = TestClient(app)
    resp = client.delete(f"/api/providers/{pid}")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    with sf() as session:
        assert (
            session.query(ProviderModel).filter_by(provider_id=pid).count() == 0
        )
        assert (
            session.query(ComboMember).filter_by(provider_id=pid).count() == 0
        )
        assert (
            session.query(EndpointBinding)
            .filter_by(bind_type="provider", bind_id=pid)
            .count()
            == 0
        )
        # unrelated binding remains
        assert session.query(EndpointBinding).count() == 1
        assert session.get(Provider, pid) is None


def test_delete_missing_returns_404(monkeypatch) -> None:
    client = _client(monkeypatch)
    resp = client.delete("/api/providers/999999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "provider_not_found"

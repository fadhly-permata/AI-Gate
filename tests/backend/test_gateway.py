"""Gateway + /api/logs endpoint tests — hermetic, no on-disk DB.

The gateway's ``SessionLocal`` (and every module-level binding the gateway
imports, plus ``backend.config.db.SessionLocal`` used by ``backend.log``) is
redirected to a fresh in-memory SQLite engine built with ``StaticPool`` so all
connections share one DB and tables persist. A ``Provider`` + ``ProviderModel``
(+ ``Combo``/``ComboMember``) are seeded for the model-resolution tests.

Upstream calls use **respx** to mock ``httpx`` (no network).
"""

from __future__ import annotations

import json

import respx
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.combo_routing as combo_routing
import backend.combos_router as combos_router
import backend.config.db as db_mod
import backend.config.logs_router as logs_router
import backend.gateway.provider_adapter as provider_adapter
import backend.gateway.resolver as resolver
import backend.gateway.router as router
from backend.config.db import Base
from backend.models import (
    Combo,
    ComboMember,
    LogEntry,
    Provider,
    ProviderModel,
)
from fastapi.testclient import TestClient

from backend.server import app

CANNED_RESPONSE = {
    "id": "chatcmpl-test",
    "object": "chat.completion",
    "model": "provider:test",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "hi there"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
}


def _make_sessionmaker() -> sessionmaker:
    """In-memory SQLite engine shared across all connections (StaticPool)."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _seed(sf: sessionmaker) -> None:
    with sf() as session:
        provider = Provider(
            name="test",
            type="openai-compatible",
            base_url="http://provider.test/v1",
            api_key="sk-plain",
            enabled=True,
        )
        session.add(provider)
        session.flush()
        session.add(
            ProviderModel(
                provider_id=provider.id,
                model_id="gpt-4o",
                model_name="GPT-4o",
                capabilities="chat",
            )
        )
        combo = Combo(name="default", strategy="fallback", enabled=True)
        session.add(combo)
        session.flush()
        session.add(
            ComboMember(
                combo_id=combo.id,
                provider_id=provider.id,
                provider_model="gpt-4o",
                priority=0,
                weight=1.0,
            )
        )
        session.commit()


def _patch_db(monkeypatch, sf: sessionmaker) -> None:
    """Rebind every SessionLocal binding the gateway / logger touch."""
    monkeypatch.setattr(db_mod, "SessionLocal", sf)
    monkeypatch.setattr(resolver, "SessionLocal", sf)
    monkeypatch.setattr(router, "SessionLocal", sf)
    monkeypatch.setattr(logs_router, "SessionLocal", sf)
    monkeypatch.setattr(combo_routing, "SessionLocal", sf)
    monkeypatch.setattr(combos_router, "SessionLocal", sf)


def _client_with_db(monkeypatch, patch_adapter: bool = True) -> TestClient:
    sf = _make_sessionmaker()
    _seed(sf)
    _patch_db(monkeypatch, sf)
    if patch_adapter:
        async def _fake(_target, _payload: dict) -> dict:
            return CANNED_RESPONSE

        monkeypatch.setattr(provider_adapter, "chat_completion", _fake)
    return TestClient(app)


# --- chat/completions error paths -----------------------------------------


def test_missing_model_returns_400_envelope(monkeypatch) -> None:
    client = _client_with_db(monkeypatch)
    resp = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "halo"}]},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert "error" in body
    assert body["error"]["type"] == "invalid_request_error"
    assert body["error"]["code"] == "missing_model"


def test_streaming_rejected_with_envelope(monkeypatch) -> None:
    client = _client_with_db(monkeypatch)
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "provider:test",
            "messages": [{"role": "user", "content": "halo"}],
            "stream": True,
        },
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "streaming_not_supported"


def test_unknown_model_returns_model_not_found(monkeypatch) -> None:
    client = _client_with_db(monkeypatch)
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "provider:ghost",
            "messages": [{"role": "user", "content": "halo"}],
        },
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["type"] == "invalid_request_error"
    assert body["error"]["code"] == "model_not_found"


# --- chat/completions success path (respx upstream mock) ------------------


@respx.mock
def test_chat_completions_provider_respx_returns_upstream(monkeypatch) -> None:
    client = _client_with_db(monkeypatch, patch_adapter=False)
    route = respx.post("http://provider.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=CANNED_RESPONSE)
    )
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "provider:test:gpt-4o",
            "messages": [{"role": "user", "content": "halo"}],
            # arbitrary extra OpenAI fields must pass through untouched
            "temperature": 0.7,
            "n": 1,
        },
    )
    assert resp.status_code == 200
    assert route.called
    body = resp.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["content"] == "hi there"
    assert body["usage"]["total_tokens"] == 3

    # The provider:-prefixed reference must NOT reach upstream; the real id must.
    sent = json.loads(route.calls.last.request.content)
    assert sent["model"] == "gpt-4o"
    assert sent["temperature"] == 0.7
    assert sent["n"] == 1


@respx.mock
def test_chat_completions_combo_respx(monkeypatch) -> None:
    client = _client_with_db(monkeypatch, patch_adapter=False)
    route = respx.post("http://provider.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=CANNED_RESPONSE)
    )
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "combo:default",
            "messages": [{"role": "user", "content": "halo"}],
        },
    )
    assert resp.status_code == 200
    assert route.called
    body = resp.json()
    assert body["choices"][0]["message"]["content"] == "hi there"
    # combo's member.provider_model must be the real upstream id sent upstream.
    sent = json.loads(route.calls.last.request.content)
    assert sent["model"] == "gpt-4o"


def test_success_creates_info_log_entry(monkeypatch) -> None:
    client = _client_with_db(monkeypatch, patch_adapter=False)
    with respx.mock:
        respx.post("http://provider.test/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=CANNED_RESPONSE)
        )
        resp = client.post(
            "/v1/chat/completions",
            json={
                "model": "provider:test:gpt-4o",
                "messages": [{"role": "user", "content": "halo"}],
            },
        )
    assert resp.status_code == 200
    # The success path of chat_completions must write an INFO LogEntry (ADR-011).
    with router.SessionLocal() as session:
        entries = (
            session.query(LogEntry)
            .filter_by(severity="info", source="backend.gateway.router")
            .all()
        )
    assert len(entries) >= 1
    assert "model" in entries[0].message


# --- models ---------------------------------------------------------------


def test_list_models_contains_provider_and_combo(monkeypatch) -> None:
    client = _client_with_db(monkeypatch)
    resp = client.get("/v1/models")
    assert resp.status_code == 200
    body = resp.json()
    assert body["object"] == "list"
    ids = {entry["id"] for entry in body["data"]}
    assert "provider:test:gpt-4o" in ids
    assert "combo:default" in ids


# --- /api/logs ------------------------------------------------------------


def test_get_logs_returns_seeded_entries(monkeypatch) -> None:
    sf = _make_sessionmaker()
    _seed(sf)
    _patch_db(monkeypatch, sf)
    with sf() as session:
        session.add(
            LogEntry(
                severity="error",
                source="test.seed",
                message="boom",
                stacktrace="trace",
            )
        )
        session.commit()

    client = TestClient(app)
    resp = client.get("/api/logs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["object"] == "list"
    assert any(e["message"] == "boom" for e in body["data"])
    sample = next(e for e in body["data"] if e["message"] == "boom")
    assert sample["severity"] == "error"
    assert sample["stacktrace"] == "trace"
    assert "timestamp" in sample and "id" in sample


def test_post_logs_creates_entry(monkeypatch) -> None:
    sf = _make_sessionmaker()
    _seed(sf)
    _patch_db(monkeypatch, sf)
    client = TestClient(app)
    resp = client.post(
        "/api/logs",
        json={
            "severity": "warning",
            "source": "frontend:app",
            "message": "ui glitch",
            "stacktrace": "st",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["severity"] == "warning"
    assert body["message"] == "ui glitch"
    assert body["id"] is not None

    with sf() as session:
        rows = session.query(LogEntry).filter_by(message="ui glitch").all()
        assert len(rows) == 1
        assert rows[0].source == "frontend:app"

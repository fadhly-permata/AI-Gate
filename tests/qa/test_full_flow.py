"""Standalone QA integration test — full API flow (task B4.3, tests/qa/).

This file lives OUTSIDE the be-dev/fe-dev owned dirs (tests/backend,
tests/frontend). It exercises a complete server-side flow through the real
FastAPI routers exposed by ``backend.server.app``:

  1. POST /api/providers       (with respx-mocked model auto-discovery)
  2. POST /api/combos          (bind the discovered provider model as a member)
  3. POST /v1/chat/completions with model="combo:<name>"
       -> upstream (respx) must receive the REAL model id + the plaintext
          Bearer api_key (no provider:-prefixed leakage).

Plus a second case that proves the ADR-008 Endpoint->ProxyPool egress binding
is actually threaded into the provider adapter: we patch
``backend.combo_routing.execute_combo`` and assert it is called with the
correct ``proxy_url`` built from the selected ProxyNode.

Hermetic: an in-memory SQLite engine (StaticPool) replaces every
``SessionLocal`` binding the flow touches, so nothing touches the on-disk
~/.aigate DB. Pydantic v1 backend — no v2 assumptions.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.cli_tools_router as cli_tools_router
import backend.combo_routing as combo_routing
import backend.combos_router as combos_router
import backend.config.db as db_mod
import backend.config.logs_router as logs_router
import backend.endpoints_router as endpoints_router
import backend.gateway.resolver as resolver
import backend.gateway.router as gateway_router
import backend.providers_router as providers_router
import backend.proxies_router as proxies_router
import backend.selfheal as selfheal
import backend.terminal.router as terminal_router
from backend.config.db import Base
from backend.models import (
    Endpoint,
    EndpointBinding,
    ProxyNode,
    ProxyPool,
)
from backend.server import app


CANNED_RESPONSE = {
    "id": "chatcmpl-qa",
    "object": "chat.completion",
    "model": "provider:test",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "hello from upstream"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
}

OPENAI_MODELS = {
    "object": "list",
    "data": [
        {"id": "gpt-4o", "object": "model"},
        {"id": "gpt-4o-mini", "object": "model"},
    ],
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


def _patch_db(monkeypatch, sf: sessionmaker) -> None:
    """Rebind every SessionLocal the full flow touches to the in-memory DB."""
    # backend.log references SessionLocal via backend.config.db (db_mod), so
    # patching db_mod keeps every log path hermetic too.
    monkeypatch.setattr(db_mod, "SessionLocal", sf)
    monkeypatch.setattr(providers_router, "SessionLocal", sf)
    monkeypatch.setattr(combos_router, "SessionLocal", sf)
    monkeypatch.setattr(resolver, "SessionLocal", sf)
    monkeypatch.setattr(gateway_router, "SessionLocal", sf)
    monkeypatch.setattr(logs_router, "SessionLocal", sf)
    monkeypatch.setattr(combo_routing, "SessionLocal", sf)


def _client(monkeypatch) -> TestClient:
    sf = _make_sessionmaker()
    _patch_db(monkeypatch, sf)
    # Stash the session factory so tests can insert rows directly.
    client = TestClient(app)
    client._qa_sf = sf  # type: ignore[attr-defined]
    return client


# --- Case 1: full create->discover->combo->chat flow --------------------------
@respx.mock
def test_full_flow_provider_discover_combo_chat(monkeypatch) -> None:
    client = _client(monkeypatch)

    # 1) create provider; auto-discovery mocked -> 2 models stored.
    respx.get("https://acme.test/v1/models").mock(
        return_value=httpx.Response(200, json=OPENAI_MODELS)
    )
    created = client.post(
        "/api/providers",
        json={
            "name": "acme",
            "type": "openai-compatible",
            "base_url": "https://acme.test/v1",
            "api_key": "sk-plaintext-secret",
            "enabled": True,
        },
    )
    assert created.status_code == 201, created.text
    provider = created.json()
    assert {m["model_id"] for m in provider["models"]} == {"gpt-4o", "gpt-4o-mini"}

    # 2) create combo bound to the discovered model gpt-4o.
    combo = client.post(
        "/api/combos",
        json={
            "name": "default",
            "strategy": "fallback",
            "enabled": True,
            "members": [
                {
                    "provider_id": provider["id"],
                    "provider_model": "gpt-4o",
                    "priority": 0,
                    "weight": 1.0,
                }
            ],
        },
    )
    assert combo.status_code == 201, combo.text
    assert combo.json()["name"] == "default"

    # 3) chat via combo: ref; upstream mocked.
    route = respx.post("https://acme.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=CANNED_RESPONSE)
    )
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "combo:default",
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0.5,
        },
    )
    assert resp.status_code == 200, resp.text
    assert route.called
    body = resp.json()
    assert body["choices"][0]["message"]["content"] == "hello from upstream"

    sent = json.loads(route.calls.last.request.content)
    # ADR-007/009: the provider:-prefixed ref must NOT reach upstream; the
    # real member model id must.
    assert sent["model"] == "gpt-4o"
    assert sent["temperature"] == 0.5
    # Plaintext Bearer api_key forwarded verbatim (ADR-007).
    assert route.calls.last.request.headers["Authorization"] == (
        "Bearer sk-plaintext-secret"
    )


# --- Case 2: Endpoint->ProxyPool egress binding is threaded to adapter --------
@respx.mock
def test_endpoint_proxy_binding_threads_proxy_url(monkeypatch) -> None:
    client = _client(monkeypatch)

    # create provider + combo (real API flow, discovery mocked).
    respx.get("https://acme.test/v1/models").mock(
        return_value=httpx.Response(200, json=OPENAI_MODELS)
    )
    provider = client.post(
        "/api/providers",
        json={
            "name": "acme",
            "type": "openai-compatible",
            "base_url": "https://acme.test/v1",
            "api_key": "sk-plaintext-secret",
        },
    ).json()
    combo = client.post(
        "/api/combos",
        json={
            "name": "default",
            "strategy": "fallback",
            "members": [
                {"provider_id": provider["id"], "provider_model": "gpt-4o"}
            ],
        },
    ).json()

    # Insert proxy pool + healthy node + endpoint bound to the combo, with the
    # proxy pool attached. Done directly against the same in-memory DB.
    sf: sessionmaker = client._qa_sf  # type: ignore[attr-defined]
    with sf() as session:
        pool = ProxyPool(name="px", rotation_strategy="failover")
        session.add(pool)
        session.flush()
        node = ProxyNode(
            pool_id=pool.id,
            host="px.host",
            port=3128,
            protocol="http",
            username="u",
            password="p",
            status="healthy",
        )
        session.add(node)
        session.flush()
        endpoint = Endpoint(name="e1", proxy_pool_id=pool.id)
        session.add(endpoint)
        session.flush()
        session.add(
            EndpointBinding(
                endpoint_id=endpoint.id, bind_type="combo", bind_id=combo["id"]
            )
        )
        session.commit()

    expected_proxy_url = "http://u:p@px.host:3128"

    # Capture the proxy_url actually passed into the combo router.
    captured = {}

    async def _fake_execute_combo(combo_ref, payload, proxy_url=None):
        captured["proxy_url"] = proxy_url
        captured["called"] = True
        return CANNED_RESPONSE

    monkeypatch.setattr(combo_routing, "execute_combo", _fake_execute_combo)
    # The gateway router imported execute_combo into its own namespace, so the
    # call site must be patched there for the override to take effect.
    monkeypatch.setattr(gateway_router, "execute_combo", _fake_execute_combo)

    resp = client.post(
        "/v1/chat/completions",
        headers={"X-Aigate-Endpoint": "e1"},
        json={"model": "anything", "messages": [{"role": "user", "content": "x"}]},
    )
    assert resp.status_code == 200, resp.text
    assert captured.get("called") is True
    # ADR-008: the egress proxy URL built from the selected node reaches the
    # provider adapter.
    assert captured.get("proxy_url") == expected_proxy_url

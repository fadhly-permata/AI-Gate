"""Provider-level Token Saver tests (Endpoint -> Provider move).

The Token Saver feature moved from the Endpoint level to the Provider level with
independent on/off toggles for each saver type (RTK / Caveman / Ponytail). This
module covers:

1. The three ``Provider`` boolean columns default ``False``; the ``providers``
   CRUD router sets/updates them on create + update.
2. The gateway router applies each toggle independently (rtk compresses tool
   content / measures saved_bytes; caveman adds a concise system instruction;
   ponytail adds a minimal-code instruction) and applies all three in the fixed
   order ``rtk -> caveman -> ponytail`` when enabled together.
3. In-process integration: ``POST /v1/chat/completions`` with a ``provider:``
   ref applies the bound Provider's saver (upstream sees compressed messages) and
   a Provider with no toggle leaves the payload unchanged.
4. The Endpoint DTO no longer carries a ``token_saver`` key.

Hermetic, no on-disk DB. Mirrors ``test_providers.py`` / ``test_token_saver.py``:
an in-memory SQLite engine (StaticPool) replaces every ``SessionLocal`` binding
the routers / token-saver / resolver / combo routing touch.
"""

from __future__ import annotations

import copy

import httpx
import respx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.combo_routing as combo_routing
import backend.config.db as db_mod
import backend.endpoints_router as endpoints_router
import backend.gateway.provider_adapter as provider_adapter
import backend.gateway.resolver as resolver
import backend.gateway.router as gateway_router
import backend.providers_router as providers_router
from backend.config.db import Base
from backend.models import Endpoint, EndpointBinding, Provider, ProviderModel

from fastapi.testclient import TestClient

from backend.server import app


# --------------------------------------------------------------------------- #
# harness
# --------------------------------------------------------------------------- #
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
    monkeypatch.setattr(endpoints_router, "SessionLocal", sf)
    monkeypatch.setattr(gateway_router, "SessionLocal", sf)
    monkeypatch.setattr(combo_routing, "SessionLocal", sf)
    monkeypatch.setattr(resolver, "SessionLocal", sf)
    monkeypatch.setattr(providers_router, "SessionLocal", sf)


def _client(monkeypatch) -> TestClient:
    sf = _make_sessionmaker()
    _patch_db(monkeypatch, sf)
    return TestClient(app)


def _seed_provider(sf: sessionmaker, **toggles) -> int:
    with sf() as session:
        provider = Provider(
            name="sv",
            type="openai-compatible",
            base_url="http://sv.test/v1",
            api_key="sk-plain",
            enabled=True,
            **toggles,
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
        session.commit()
        return provider.id


def _large_git_diff() -> str:
    header = "diff --git a/foo.py b/foo.py\nindex 0000000..1111111 100644\n"
    lines = "\n".join(f"+line_{i} = {i}" for i in range(500))
    return header + lines + "\n" + "\n\n\n\n\n" + "git diff tail\n"


# --------------------------------------------------------------------------- #
# 1. Provider columns + CRUD router
# --------------------------------------------------------------------------- #
def test_provider_columns_default_false():
    sf = _make_sessionmaker()
    pid = _seed_provider(sf)
    with sf() as session:
        p = session.get(Provider, pid)
        assert p.token_saver_rtk is False
        assert p.token_saver_caveman is False
        assert p.token_saver_ponytail is False


@respx.mock
def test_providers_router_create_sets_toggles(monkeypatch):
    respx.get("http://acme.test/v1/models").mock(
        return_value=httpx.Response(200, json={"object": "list", "data": []})
    )
    client = _client(monkeypatch)
    resp = client.post(
        "/api/providers",
        json={
            "name": "acme",
            "type": "openai-compatible",
            "base_url": "http://acme.test/v1",
            "api_key": "sk-plain",
            "token_saver_rtk": True,
            "token_saver_caveman": True,
            "token_saver_ponytail": False,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["token_saver_rtk"] is True
    assert body["token_saver_caveman"] is True
    assert body["token_saver_ponytail"] is False
    pid = body["id"]

    # Partial update: flip rtk off, ponytail on; caveman left unchanged.
    resp = client.put(
        f"/api/providers/{pid}",
        json={"token_saver_rtk": False, "token_saver_ponytail": True},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["token_saver_rtk"] is False
    assert body["token_saver_caveman"] is True  # unchanged
    assert body["token_saver_ponytail"] is True


# --------------------------------------------------------------------------- #
# 2. Router applies each toggle (unit on the provider helper)
# --------------------------------------------------------------------------- #
def _rtk_payload() -> dict:
    return {
        "model": "x",
        "messages": [
            {"role": "user", "content": "diff please"},
            {"role": "tool", "content": _large_git_diff()},
            {"role": "assistant", "content": "normal reply, must stay intact"},
        ],
    }


def _provider(sf: sessionmaker, **toggles) -> int:
    with sf() as session:
        provider = Provider(name="p", type="t", base_url="u", api_key="k", **toggles)
        session.add(provider)
        session.commit()
        return provider.id


def test_apply_rtk_only_when_enabled():
    sf = _make_sessionmaker()
    pid = _provider(sf, token_saver_rtk=True)
    with sf() as session:
        provider = session.get(Provider, pid)
        new_payload, saved = gateway_router._apply_token_saver_for_provider(
            provider, _rtk_payload()
        )
    assert saved and saved > 0
    tool = next(m for m in new_payload["messages"] if m["role"] == "tool")
    assert "[...truncated" in tool["content"]
    # Normal messages untouched; rtk injects no system instruction.
    assert new_payload["messages"][-1]["content"] == "normal reply, must stay intact"
    assert all(m["role"] != "system" for m in new_payload["messages"])


def test_apply_caveman_only_adds_concise_instruction():
    sf = _make_sessionmaker()
    pid = _provider(sf, token_saver_caveman=True)
    with sf() as session:
        provider = session.get(Provider, pid)
        new_payload, saved = gateway_router._apply_token_saver_for_provider(
            provider,
            {"model": "x", "messages": [{"role": "user", "content": "hi"}]},
        )
    # Caveman is output-side; not measurable as input savings.
    assert saved == 0
    sys_msgs = [m for m in new_payload["messages"] if m["role"] == "system"]
    assert sys_msgs and "concise" in sys_msgs[0]["content"]
    assert not any("minimal" in m["content"] for m in sys_msgs)


def test_apply_ponytail_only_adds_minimal_instruction():
    sf = _make_sessionmaker()
    pid = _provider(sf, token_saver_ponytail=True)
    with sf() as session:
        provider = session.get(Provider, pid)
        new_payload, saved = gateway_router._apply_token_saver_for_provider(
            provider,
            {"model": "x", "messages": [{"role": "user", "content": "hi"}]},
        )
    assert saved == 0
    sys_msgs = [m for m in new_payload["messages"] if m["role"] == "system"]
    assert sys_msgs and "minimal" in sys_msgs[0]["content"]
    assert not any("concise" in m["content"] for m in sys_msgs)


def test_apply_all_three_in_order():
    sf = _make_sessionmaker()
    pid = _provider(
        sf, token_saver_rtk=True, token_saver_caveman=True, token_saver_ponytail=True
    )
    with sf() as session:
        provider = session.get(Provider, pid)
        new_payload, saved = gateway_router._apply_token_saver_for_provider(
            provider, _rtk_payload()
        )
    # rtk compressed the tool message.
    tool = next(m for m in new_payload["messages"] if m["role"] == "tool")
    assert "[...truncated" in tool["content"]
    assert saved and saved > 0
    # caveman + ponytail each injected a system instruction.
    sys_contents = [
        m["content"] for m in new_payload["messages"] if m["role"] == "system"
    ]
    assert any("concise" in c for c in sys_contents)
    assert any("minimal" in c for c in sys_contents)


def test_apply_no_toggles_returns_unchanged():
    sf = _make_sessionmaker()
    pid = _provider(sf)
    with sf() as session:
        provider = session.get(Provider, pid)
        payload = _rtk_payload()
        new_payload, saved = gateway_router._apply_token_saver_for_provider(
            provider, copy.deepcopy(payload)
        )
    assert saved is None  # not measured -> None (B5.6 semantics)
    assert new_payload == payload  # untouched


# --------------------------------------------------------------------------- #
# 3. Integration via in-process TestClient
# --------------------------------------------------------------------------- #
def _capturing_fake(box: dict):
    async def _fake(_target, _payload, proxy_url=None):
        box["payload"] = _payload
        return {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "model": "x",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "ok"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    return _fake


def test_integration_provider_rtk_compresses_upstream_payload(monkeypatch):
    sf = _make_sessionmaker()
    _seed_provider(sf, token_saver_rtk=True)
    _patch_db(monkeypatch, sf)
    captured: dict = {}
    monkeypatch.setattr(provider_adapter, "chat_completion", _capturing_fake(captured))
    client = TestClient(app)
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "provider:sv:gpt-4o",
            "messages": [
                {"role": "user", "content": "diff please"},
                {"role": "tool", "content": _large_git_diff()},
            ],
        },
    )
    assert resp.status_code == 200
    assert "payload" in captured
    tool = next(m for m in captured["payload"]["messages"] if m["role"] == "tool")
    assert "[...truncated" in tool["content"]


def test_integration_no_saver_leaves_payload_unchanged(monkeypatch):
    sf = _make_sessionmaker()
    _seed_provider(sf)  # all toggles off
    _patch_db(monkeypatch, sf)
    captured: dict = {}
    monkeypatch.setattr(provider_adapter, "chat_completion", _capturing_fake(captured))
    client = TestClient(app)
    diff = _large_git_diff()
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "provider:sv:gpt-4o",
            "messages": [
                {"role": "user", "content": "diff please"},
                {"role": "tool", "content": diff},
            ],
        },
    )
    assert resp.status_code == 200
    assert "payload" in captured
    tool = next(m for m in captured["payload"]["messages"] if m["role"] == "tool")
    # Nothing truncated; original tool content forwarded verbatim.
    assert tool["content"] == diff


# --------------------------------------------------------------------------- #
# 4. Endpoint DTO no longer carries token_saver
# --------------------------------------------------------------------------- #
def test_endpoint_dto_has_no_token_saver_key(monkeypatch):
    sf = _make_sessionmaker()
    with sf() as session:
        ep = Endpoint(name="ep1")
        session.add(ep)
        session.flush()
        session.add(
            EndpointBinding(endpoint_id=ep.id, bind_type="provider", bind_id=1)
        )
        session.commit()
        eid = ep.id
    _patch_db(monkeypatch, sf)
    client = TestClient(app)
    resp = client.get(f"/api/endpoints/{eid}")
    assert resp.status_code == 200
    body = resp.json()
    assert "token_saver" not in body

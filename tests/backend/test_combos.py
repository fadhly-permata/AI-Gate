"""Combo CRUD + strategy routing tests (task B2.4) — hermetic, no on-disk DB.

Mirrors the DB-patching pattern in ``test_gateway.py``: every module-level
``SessionLocal`` the combo path touches (``backend.config.db``,
``backend.combo_routing``, ``backend.combos_router``, ``backend.gateway.resolver``,
``backend.gateway.router``, ``backend.config.logs_router``) is rebound to a
shared in-memory SQLite engine.

Upstream calls use **respx** to mock ``httpx`` (no network).
"""

from __future__ import annotations

import respx
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.combo_routing as combo_routing
import backend.combos_router as combos_router
import backend.config.db as db_mod
import backend.config.logs_router as logs_router
import backend.gateway.resolver as resolver
import backend.gateway.router as router
from backend.config.db import Base
from backend.models import Combo, ComboMember, Provider, ProviderModel
from fastapi.testclient import TestClient

from backend.server import app

CANNED_RESPONSE = {
    "id": "chatcmpl-test",
    "object": "chat.completion",
    "model": "gpt-4o",
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
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _seed_combo(sf: sessionmaker) -> dict:
    """Seed two providers + a 2-member fallback combo, return their ids."""
    with sf() as session:
        p1 = Provider(
            name="p1",
            type="openai-compatible",
            base_url="http://p1.test/v1",
            api_key="sk-p1",
            enabled=True,
        )
        p2 = Provider(
            name="p2",
            type="openai-compatible",
            base_url="http://p2.test/v1",
            api_key="sk-p2",
            enabled=True,
        )
        session.add_all([p1, p2])
        session.flush()
        session.add_all(
            [
                ProviderModel(
                    provider_id=p1.id, model_id="gpt-4o", model_name="GPT-4o"
                ),
                ProviderModel(
                    provider_id=p2.id, model_id="gpt-4o", model_name="GPT-4o"
                ),
            ]
        )
        combo = Combo(name="default", strategy="fallback", enabled=True)
        session.add(combo)
        session.flush()
        session.add_all(
            [
                ComboMember(
                    combo_id=combo.id,
                    provider_id=p1.id,
                    provider_model="gpt-4o",
                    priority=0,
                    weight=1.0,
                ),
                ComboMember(
                    combo_id=combo.id,
                    provider_id=p2.id,
                    provider_model="gpt-4o",
                    priority=1,
                    weight=2.0,
                ),
            ]
        )
        session.commit()
        return {
            "p1_id": p1.id,
            "p2_id": p2.id,
            "combo_id": combo.id,
        }


def _patch_db(monkeypatch, sf: sessionmaker) -> None:
    monkeypatch.setattr(db_mod, "SessionLocal", sf)
    monkeypatch.setattr(resolver, "SessionLocal", sf)
    monkeypatch.setattr(router, "SessionLocal", sf)
    monkeypatch.setattr(combo_routing, "SessionLocal", sf)
    monkeypatch.setattr(combos_router, "SessionLocal", sf)
    monkeypatch.setattr(logs_router, "SessionLocal", sf)


def _client(monkeypatch, sf: sessionmaker) -> TestClient:
    _patch_db(monkeypatch, sf)
    return TestClient(app)


# --- Combo CRUD --------------------------------------------------------------


def test_combo_crud_post_get_put_delete(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed_combo(sf)
    client = _client(monkeypatch, sf)

    # POST /api/combos with nested members.
    resp = client.post(
        "/api/combos",
        json={
            "name": "mycombo",
            "strategy": "fallback",
            "enabled": True,
            "members": [
                {"provider_id": ids["p1_id"], "provider_model": "gpt-4o", "priority": 0},
                {"provider_id": ids["p2_id"], "provider_model": "gpt-4o", "priority": 1},
            ],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "mycombo"
    assert body["strategy"] == "fallback"
    assert len(body["members"]) == 2
    new_id = body["id"]

    # GET list contains it.
    resp = client.get("/api/combos")
    assert resp.status_code == 200
    names = {c["name"] for c in resp.json()["data"]}
    assert "mycombo" in names

    # GET detail.
    resp = client.get(f"/api/combos/{new_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "mycombo"

    # PUT updates strategy only.
    resp = client.put(f"/api/combos/{new_id}", json={"strategy": "load_balance"})
    assert resp.status_code == 200
    assert resp.json()["strategy"] == "load_balance"

    # DELETE cascades members.
    resp = client.delete(f"/api/combos/{new_id}")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    resp = client.get(f"/api/combos/{new_id}")
    assert resp.status_code == 404


def test_combo_get_404_envelope(monkeypatch) -> None:
    sf = _make_sessionmaker()
    _seed_combo(sf)
    client = _client(monkeypatch, sf)
    resp = client.get("/api/combos/9999")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["type"] == "not_found"


def test_combo_member_subroutes(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed_combo(sf)
    client = _client(monkeypatch, sf)

    # Add a member.
    resp = client.post(
        f"/api/combos/{ids['combo_id']}/members",
        json={"provider_id": ids["p1_id"], "provider_model": "gpt-4o", "priority": 5},
    )
    assert resp.status_code == 201
    mid = resp.json()["id"]

    # Update it.
    resp = client.put(
        f"/api/combos/{ids['combo_id']}/members/{mid}",
        json={"priority": 7, "weight": 3.0},
    )
    assert resp.status_code == 200
    assert resp.json()["priority"] == 7
    assert resp.json()["weight"] == 3.0

    # Delete it.
    resp = client.delete(f"/api/combos/{ids['combo_id']}/members/{mid}")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


# --- Strategy routing via gateway (respx) ------------------------------------


@respx.mock
def test_fallback_success_on_second_member(monkeypatch) -> None:
    sf = _make_sessionmaker()
    _seed_combo(sf)
    client = _client(monkeypatch, sf)

    route1 = respx.post("http://p1.test/v1/chat/completions").mock(
        return_value=httpx.Response(502, json={"error": "boom"})
    )
    route2 = respx.post("http://p2.test/v1/chat/completions").mock(
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
    assert resp.json() == CANNED_RESPONSE
    # First member was attempted (and failed); second succeeded.
    assert route1.called
    assert route2.called


@respx.mock
def test_fallback_all_fail_returns_upstream_envelope(monkeypatch) -> None:
    sf = _make_sessionmaker()
    _seed_combo(sf)
    client = _client(monkeypatch, sf)

    respx.post("http://p1.test/v1/chat/completions").mock(
        return_value=httpx.Response(502, json={"error": "boom1"})
    )
    respx.post("http://p2.test/v1/chat/completions").mock(
        return_value=httpx.Response(503, json={"error": "boom2"})
    )

    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "combo:default",
            "messages": [{"role": "user", "content": "halo"}],
        },
    )
    # UpstreamError surfaces as its HTTP status + OpenAI envelope.
    assert resp.status_code in (502, 503)
    assert "error" in resp.json()
    assert resp.json()["error"]["type"] == "upstream_error"


@respx.mock
def test_load_balance_single_member_200(monkeypatch) -> None:
    sf = _make_sessionmaker()
    with sf() as session:
        p = Provider(
            name="lb",
            type="openai-compatible",
            base_url="http://lb.test/v1",
            api_key="sk-lb",
            enabled=True,
        )
        session.add(p)
        session.flush()
        session.add(
            ProviderModel(provider_id=p.id, model_id="gpt-4o", model_name="GPT-4o")
        )
        combo = Combo(name="lb", strategy="load_balance", enabled=True)
        session.add(combo)
        session.flush()
        session.add(
            ComboMember(
                combo_id=combo.id,
                provider_id=p.id,
                provider_model="gpt-4o",
                priority=0,
                weight=1.0,
            )
        )
        session.commit()

    client = _client(monkeypatch, sf)
    route = respx.post("http://lb.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=CANNED_RESPONSE)
    )
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "combo:lb",
            "messages": [{"role": "user", "content": "halo"}],
        },
    )
    assert resp.status_code == 200
    assert route.called
    assert resp.json() == CANNED_RESPONSE


@respx.mock
def test_latency_cost_single_member_200(monkeypatch) -> None:
    sf = _make_sessionmaker()
    with sf() as session:
        p = Provider(
            name="lc",
            type="openai-compatible",
            base_url="http://lc.test/v1",
            api_key="sk-lc",
            enabled=True,
        )
        session.add(p)
        session.flush()
        session.add(
            ProviderModel(provider_id=p.id, model_id="gpt-4o", model_name="GPT-4o")
        )
        combo = Combo(name="lc", strategy="latency_cost", enabled=True)
        session.add(combo)
        session.flush()
        session.add(
            ComboMember(
                combo_id=combo.id,
                provider_id=p.id,
                provider_model="gpt-4o",
                priority=0,
                weight=0.5,
            )
        )
        session.commit()

    client = _client(monkeypatch, sf)
    route = respx.post("http://lc.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=CANNED_RESPONSE)
    )
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "combo:lc",
            "messages": [{"role": "user", "content": "halo"}],
        },
    )
    assert resp.status_code == 200
    assert route.called
    assert resp.json() == CANNED_RESPONSE


# --- select_member unit checks -----------------------------------------------


def test_select_member_load_balance_weighted(monkeypatch) -> None:
    from backend.gateway.resolver import ResolvedTarget

    a = ResolvedTarget("", "", "", "a", combo_used=True, priority=0, weight=1.0)
    b = ResolvedTarget("", "", "", "b", combo_used=True, priority=1, weight=99.0)
    chosen = combo_routing.select_member("load_balance", [a, b])
    assert chosen in (a, b)


def test_select_member_latency_cost_lowest_weight(monkeypatch) -> None:
    from backend.gateway.resolver import ResolvedTarget

    a = ResolvedTarget("", "", "", "a", combo_used=True, priority=0, weight=5.0)
    b = ResolvedTarget("", "", "", "b", combo_used=True, priority=1, weight=1.0)
    chosen = combo_routing.select_member("latency_cost", [a, b])
    assert chosen is b

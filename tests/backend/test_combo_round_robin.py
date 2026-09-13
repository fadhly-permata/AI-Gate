"""Combo ``round_robin`` strategy tests (task 2026-09-13).

Hermetic, no on-disk DB. Mirrors ``test_combos.py`` DB-patching (every
``SessionLocal`` the combo path touches is rebound to a shared in-memory engine)
and uses **respx** to mock ``httpx`` (no network).

Covers the handover §B contract:
* distribution rotates evenly by ``priority`` order (wrap-around);
* the cursor is persisted and advances on every request;
* ``weight`` is ignored (positional selection only);
* single attempt, no intra-request retry, cursor still advances on failure;
* an unknown strategy falls back to the first (priority-asc) member.
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
from backend.gateway.resolver import ResolvedTarget
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


def _seed_round_robin(sf: sessionmaker, n: int, weights=None) -> dict:
    """Seed ``n`` providers + an ``n``-member ``round_robin`` combo.

    Members get ``priority`` 0..n-1 (so the priority-asc candidate order is
    provider p0, p1, ... pn-1). Returns provider id / base-url maps + combo id.
    """
    if weights is None:
        weights = [1.0] * n
    out: dict = {}
    with sf() as session:
        prov_ids = []
        for i in range(n):
            p = Provider(
                name=f"p{i}",
                type="openai-compatible",
                base_url=f"http://p{i}.test/v1",
                api_key=f"sk-p{i}",
                enabled=True,
            )
            session.add(p)
            session.flush()
            session.add(
                ProviderModel(provider_id=p.id, model_id="gpt-4o", model_name="GPT-4o")
            )
            prov_ids.append(p.id)
            out[f"p{i}_id"] = p.id
            out[f"p{i}_url"] = f"http://p{i}.test/v1/chat/completions"
        combo = Combo(name="rr", strategy="round_robin", enabled=True, last_used_index=0)
        session.add(combo)
        session.flush()
        for i in range(n):
            session.add(
                ComboMember(
                    combo_id=combo.id,
                    provider_id=prov_ids[i],
                    provider_model="gpt-4o",
                    priority=i,
                    weight=weights[i],
                )
            )
        session.commit()
        out["combo_id"] = combo.id
    return out


def _seed_unknown(sf: sessionmaker) -> dict:
    """Seed a combo with an UNKNOWN strategy + 2 members (priority 0, 1)."""
    out: dict = {}
    with sf() as session:
        prov_ids = []
        for i in range(2):
            p = Provider(
                name=f"u{i}",
                type="openai-compatible",
                base_url=f"http://u{i}.test/v1",
                api_key=f"sk-u{i}",
                enabled=True,
            )
            session.add(p)
            session.flush()
            session.add(
                ProviderModel(provider_id=p.id, model_id="gpt-4o", model_name="GPT-4o")
            )
            prov_ids.append(p.id)
            out[f"u{i}_url"] = f"http://u{i}.test/v1/chat/completions"
        combo = Combo(name="unknown", strategy="bogus_strategy", enabled=True)
        session.add(combo)
        session.flush()
        for i in range(2):
            session.add(
                ComboMember(
                    combo_id=combo.id,
                    provider_id=prov_ids[i],
                    provider_model="gpt-4o",
                    priority=i,
                    weight=1.0,
                )
            )
        session.commit()
        out["combo_id"] = combo.id
    return out


def _cursor(sf: sessionmaker, combo_id: int) -> int:
    with sf() as session:
        return session.get(Combo, combo_id).last_used_index


# --- Distribution: rotates by priority, weight ignored, cursor wraps ---------- #


@respx.mock
def test_round_robin_rotates_by_priority_ignoring_weight(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed_round_robin(sf, 3, weights=[99.0, 0.1, 5.0])
    client = _client(monkeypatch, sf)

    for i in range(3):
        respx.post(ids[f"p{i}_url"]).mock(
            return_value=httpx.Response(200, json=CANNED_RESPONSE)
        )

    for _ in range(4):
        resp = client.post(
            "/v1/chat/completions",
            json={
                "model": "combo:rr",
                "messages": [{"role": "user", "content": "halo"}],
            },
        )
        assert resp.status_code == 200

    # Call order proves rotation by priority index, NOT by weight.
    urls = [str(c.request.url) for c in respx.calls]
    assert urls == [
        ids["p0_url"],
        ids["p1_url"],
        ids["p2_url"],
        ids["p0_url"],
    ]
    # 4 picks over 3 members: 0,1,2,0 -> next cursor is 1.
    assert _cursor(sf, ids["combo_id"]) == 1


@respx.mock
def test_round_robin_cursor_persists_and_advances(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed_round_robin(sf, 2)
    client = _client(monkeypatch, sf)

    respx.post(ids["p0_url"]).mock(
        return_value=httpx.Response(200, json=CANNED_RESPONSE)
    )
    respx.post(ids["p1_url"]).mock(
        return_value=httpx.Response(200, json=CANNED_RESPONSE)
    )

    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "combo:rr",
            "messages": [{"role": "user", "content": "halo"}],
        },
    )
    assert resp.status_code == 200
    # Single request: cursor 0 -> picked p0, advanced to 1 (persisted).
    assert _cursor(sf, ids["combo_id"]) == 1


@respx.mock
def test_round_robin_single_attempt_no_retry_cursor_advances_on_failure(
    monkeypatch,
) -> None:
    sf = _make_sessionmaker()
    ids = _seed_round_robin(sf, 2)
    client = _client(monkeypatch, sf)

    r0 = respx.post(ids["p0_url"]).mock(
        return_value=httpx.Response(502, json={"error": "boom"})
    )
    r1 = respx.post(ids["p1_url"]).mock(
        return_value=httpx.Response(200, json=CANNED_RESPONSE)
    )

    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "combo:rr",
            "messages": [{"role": "user", "content": "halo"}],
        },
    )
    # Single attempt: the selected member (p0, cursor 0) failed -> 502, no retry.
    assert resp.status_code == 502
    assert r0.call_count == 1
    assert r1.call_count == 0
    # Cursor still advanced past the failed member.
    assert _cursor(sf, ids["combo_id"]) == 1


@respx.mock
def test_unknown_strategy_falls_back_to_first_member(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed_unknown(sf)
    client = _client(monkeypatch, sf)

    r0 = respx.post(ids["u0_url"]).mock(
        return_value=httpx.Response(200, json=CANNED_RESPONSE)
    )
    r1 = respx.post(ids["u1_url"]).mock(
        return_value=httpx.Response(200, json=CANNED_RESPONSE)
    )

    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "combo:unknown",
            "messages": [{"role": "user", "content": "halo"}],
        },
    )
    # Unknown strategy -> safe single select of the first (priority-asc) member.
    assert resp.status_code == 200
    assert r0.called
    assert not r1.called


# --- select_member unit checks ------------------------------------------------ #


def test_select_member_round_robin_advances_cursor() -> None:
    # Stub combo (ORM-shaped: just needs `id` + `last_used_index`).
    class _Combo:
        id = 1
        last_used_index = 0

    c = _Combo()
    a = ResolvedTarget("", "", "", "a", combo_used=True, priority=0)
    b = ResolvedTarget("", "", "", "b", combo_used=True, priority=1)
    chosen = combo_routing.select_member(
        "round_robin", [a, b], session=None, combo=c
    )
    assert chosen is a
    assert c.last_used_index == 1


def test_select_member_round_robin_wraps_around() -> None:
    class _Combo:
        id = 1
        last_used_index = 2  # would index out of range without modulo

    c = _Combo()
    members = [
        ResolvedTarget("", "", "", f"m{i}", combo_used=True, priority=i)
        for i in range(3)
    ]
    chosen = combo_routing.select_member(
        "round_robin", members, session=None, combo=c
    )
    assert chosen is members[2]  # cursor 2 % 3 -> index 2
    assert c.last_used_index == 0  # (2 + 1) % 3 == 0


def test_select_member_unknown_returns_first_member() -> None:
    a = ResolvedTarget("", "", "", "a", combo_used=True, priority=0)
    b = ResolvedTarget("", "", "", "b", combo_used=True, priority=1)
    chosen = combo_routing.select_member("bogus_strategy", [a, b])
    assert chosen is a

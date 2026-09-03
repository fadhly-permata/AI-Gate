"""B5.2 backend tests: 3-tier fallback, cadangan antar-akun, quota scaffold.

Hermetic, in-memory DB (mirrors test_combos.py). Upstream calls use respx.
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
from backend.models import (
    Combo,
    ComboMember,
    LogEntry,
    Provider,
    ProviderAccount,
    ProviderModel,
)
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


# --------------------------------------------------------------------------- #
# Seed helpers
# --------------------------------------------------------------------------- #
def _seed_three_tier(sf: sessionmaker) -> dict:
    """Two 'subscription' providers, one 'cheap', one 'free'.

    Members ordered by tier on three_tier; within subscription, priority decides.
    """
    with sf() as session:
        psub = Provider(
            name="psub", type="openai", base_url="http://psub.test/v1",
            api_key="sk-sub", tier="subscription", enabled=True,
        )
        psub2 = Provider(
            name="psub2", type="openai", base_url="http://psub2.test/v1",
            api_key="sk-sub2", tier="subscription", enabled=True,
        )
        pcheap = Provider(
            name="pcheap", type="openrouter", base_url="http://pcheap.test/v1",
            api_key="sk-cheap", tier="cheap", enabled=True,
        )
        pfree = Provider(
            name="pfree", type="ollama", base_url="http://pfree.test/v1",
            api_key="sk-free", tier="free", enabled=True,
        )
        session.add_all([psub, psub2, pcheap, pfree])
        session.flush()
        for p in (psub, psub2, pcheap, pfree):
            session.add(
                ProviderModel(
                    provider_id=p.id, model_id=f"{p.name}-m", model_name=f"{p.name}-m"
                )
            )
        combo = Combo(name="tiered", strategy="three_tier", enabled=True)
        session.add(combo)
        session.flush()
        # Intentionally scrambled priorities to prove tier dominates.
        members = [
            ComboMember(combo_id=combo.id, provider_id=pfree.id, provider_model="free", priority=0, weight=1.0),
            ComboMember(combo_id=combo.id, provider_id=pcheap.id, provider_model="cheap", priority=0, weight=1.0),
            ComboMember(combo_id=combo.id, provider_id=psub.id, provider_model="sub5", priority=5, weight=1.0),
            ComboMember(combo_id=combo.id, provider_id=psub2.id, provider_model="sub1", priority=1, weight=1.0),
        ]
        session.add_all(members)
        session.commit()
        return {"combo_id": combo.id}


def _seed_provider_with_accounts(sf: sessionmaker, n_accounts: int = 2) -> dict:
    """Single provider with ``n_accounts`` enabled api_key accounts + 1 combo."""
    with sf() as session:
        p = Provider(
            name="p", type="openai", base_url="http://p.test/v1",
            api_key="sk-prov", tier="subscription", enabled=True,
        )
        session.add(p)
        session.flush()
        session.add(
            ProviderModel(provider_id=p.id, model_id="gpt-4o", model_name="GPT-4o")
        )
        for i in range(1, n_accounts + 1):
            session.add(
                ProviderAccount(
                    provider_id=p.id,
                    label=f"acct{i}",
                    auth_type="api_key",
                    api_key=f"key{i}",
                    enabled=True,
                )
            )
        combo = Combo(name="default", strategy="fallback", enabled=True)
        session.add(combo)
        session.flush()
        session.add(
            ComboMember(
                combo_id=combo.id, provider_id=p.id,
                provider_model="gpt-4o", priority=0, weight=1.0,
            )
        )
        session.commit()
        return {"provider_id": p.id, "combo_id": combo.id}


# --------------------------------------------------------------------------- #
# provider_tier classification
# --------------------------------------------------------------------------- #
def test_provider_tier_classification_by_type():
    assert combo_routing.provider_tier(Provider(type="ollama")) == "free"
    assert combo_routing.provider_tier(Provider(type="openrouter")) == "cheap"
    assert combo_routing.provider_tier(Provider(type="litellm")) == "cheap"
    assert combo_routing.provider_tier(Provider(type="openai")) == "subscription"
    # explicit tier wins.
    assert combo_routing.provider_tier(Provider(type="openai", tier="free")) == "free"
    assert combo_routing.provider_tier(Provider(type="ollama", tier="cheap")) == "cheap"
    # unknown tier falls back to type classification.
    assert combo_routing.provider_tier(Provider(type="ollama", tier="???")) == "free"


# --------------------------------------------------------------------------- #
# three_tier ordering
# --------------------------------------------------------------------------- #
def test_three_tier_orders_subscription_cheap_free(monkeypatch):
    sf = _make_sessionmaker()
    _seed_three_tier(sf)
    with sf() as session:
        combo = session.query(Combo).filter_by(name="tiered").first()
        candidates = combo_routing.build_candidates(combo, session)
    models = [c.upstream_model for c in candidates]
    assert models == ["sub1", "sub5", "cheap", "free"], models


# --------------------------------------------------------------------------- #
# quota-aware scaffold (no-op)
# --------------------------------------------------------------------------- #
def test_quota_aware_order_is_noop_and_logs(monkeypatch):
    sf = _make_sessionmaker()
    # Logging writes via the global SessionLocal; rebind so LogEntry lands in sf.
    monkeypatch.setattr(db_mod, "SessionLocal", sf)
    _seed_three_tier(sf)
    with sf() as session:
        combo = session.query(Combo).filter_by(name="tiered").first()
        before = [c.upstream_model for c in combo_routing.build_candidates(combo, session)]
    # Re-run and capture ordering + log.
    with sf() as session:
        combo = session.query(Combo).filter_by(name="tiered").first()
        after = combo_routing.build_candidates(combo, session)
        after_models = [c.upstream_model for c in after]
    assert after_models == before, after_models

    # The scaffold must log the B5.5 placeholder (writes to LogEntry).
    with sf() as session:
        rows = session.query(LogEntry).all()
    msgs = " ".join(r.message for r in rows)
    assert "quota tracking not yet available (B5.5)" in msgs


# --------------------------------------------------------------------------- #
# three_tier advances on failure (respx)
# --------------------------------------------------------------------------- #
@respx.mock
def test_three_tier_advances_on_failure(monkeypatch):
    sf = _make_sessionmaker()
    _seed_three_tier(sf)
    client = _client(monkeypatch, sf)

    # subscription (sub1) fails with 5xx; three_tier should advance to the rest
    # and eventually succeed on the free tier (last member). All but the last
    # return 500; last returns 200.
    respx.post("http://psub2.test/v1/chat/completions").mock(
        return_value=httpx.Response(500, json={"error": "boom"})
    )
    respx.post("http://psub.test/v1/chat/completions").mock(
        return_value=httpx.Response(500, json={"error": "boom"})
    )
    respx.post("http://pcheap.test/v1/chat/completions").mock(
        return_value=httpx.Response(500, json={"error": "boom"})
    )
    route_free = respx.post("http://pfree.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=CANNED_RESPONSE)
    )

    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "combo:tiered",
            "messages": [{"role": "user", "content": "halo"}],
        },
    )
    assert resp.status_code == 200
    assert resp.json() == CANNED_RESPONSE
    # The free tier (last in tier order) was the one that succeeded.
    assert route_free.called


# --------------------------------------------------------------------------- #
# fallback still advances on UpstreamError (regression guard for B2.4 behavior)
# --------------------------------------------------------------------------- #
@respx.mock
def test_fallback_advances_on_upstream_error(monkeypatch):
    sf = _make_sessionmaker()
    with sf() as session:
        p1 = Provider(name="p1", type="openai", base_url="http://p1.test/v1",
                      api_key="sk-p1", tier="subscription", enabled=True)
        p2 = Provider(name="p2", type="openai", base_url="http://p2.test/v1",
                      api_key="sk-p2", tier="subscription", enabled=True)
        session.add_all([p1, p2])
        session.flush()
        session.add_all([
            ProviderModel(provider_id=p1.id, model_id="gpt-4o", model_name="GPT-4o"),
            ProviderModel(provider_id=p2.id, model_id="gpt-4o", model_name="GPT-4o"),
        ])
        combo = Combo(name="default", strategy="fallback", enabled=True)
        session.add(combo)
        session.flush()
        session.add_all([
            ComboMember(combo_id=combo.id, provider_id=p1.id,
                        provider_model="gpt-4o", priority=0, weight=1.0),
            ComboMember(combo_id=combo.id, provider_id=p2.id,
                        provider_model="gpt-4o", priority=1, weight=1.0),
        ])
        session.commit()
    client = _client(monkeypatch, sf)

    r1 = respx.post("http://p1.test/v1/chat/completions").mock(
        return_value=httpx.Response(502, json={"error": "boom"})
    )
    r2 = respx.post("http://p2.test/v1/chat/completions").mock(
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
    assert r1.called and r2.called


# --------------------------------------------------------------------------- #
# Cadangan Antar-Akun: 429 on first account -> retry second account
# --------------------------------------------------------------------------- #
@respx.mock
def test_cadangan_antar_akun_retries_next_account_on_429(monkeypatch):
    sf = _make_sessionmaker()
    _seed_provider_with_accounts(sf, n_accounts=2)
    # Force the FIRST attempt to use account #1's credential deterministically.
    monkeypatch.setattr(
        combo_routing, "select_provider_credential", lambda p, s: "key1"
    )
    client = _client(monkeypatch, sf)

    auths: list = []

    def _side(request):
        auths.append(request.headers.get("Authorization"))
        if len(auths) == 1:
            return httpx.Response(
                429,
                json={"error": {"message": "rate limit", "type": "upstream_error",
                                "code": "upstream_429"}},
            )
        return httpx.Response(200, json=CANNED_RESPONSE)

    respx.post("http://p.test/v1/chat/completions").mock(side_effect=_side)

    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "combo:default",
            "messages": [{"role": "user", "content": "halo"}],
        },
    )
    assert resp.status_code == 200
    assert "Bearer key1" in auths, auths
    assert "Bearer key2" in auths, auths
    # Exactly two upstream attempts: first account (429) then second account (200).
    assert len(auths) == 2


# --------------------------------------------------------------------------- #
# 5xx must NOT spin on accounts — advance to next member instead
# --------------------------------------------------------------------------- #
@respx.mock
def test_5xx_does_not_spin_on_accounts(monkeypatch):
    sf = _make_sessionmaker()
    # Two providers: p1 has 2 accounts and always 5xx; p2 is plain and 200.
    with sf() as session:
        p1 = Provider(name="p1", type="openai", base_url="http://p1.test/v1",
                      api_key="sk-p1", tier="subscription", enabled=True)
        p2 = Provider(name="p2", type="openai", base_url="http://p2.test/v1",
                      api_key="sk-p2", tier="subscription", enabled=True)
        session.add_all([p1, p2])
        session.flush()
        session.add_all([
            ProviderModel(provider_id=p1.id, model_id="gpt-4o", model_name="GPT-4o"),
            ProviderModel(provider_id=p2.id, model_id="gpt-4o", model_name="GPT-4o"),
        ])
        for i in (1, 2):
            session.add(ProviderAccount(provider_id=p1.id, label=f"a{i}",
                                        auth_type="api_key", api_key=f"k{i}", enabled=True))
        combo = Combo(name="fb", strategy="fallback", enabled=True)
        session.add(combo)
        session.flush()
        session.add_all([
            ComboMember(combo_id=combo.id, provider_id=p1.id,
                        provider_model="gpt-4o", priority=0, weight=1.0),
            ComboMember(combo_id=combo.id, provider_id=p2.id,
                        provider_model="gpt-4o", priority=1, weight=1.0),
        ])
        session.commit()

    monkeypatch.setattr(combo_routing, "select_provider_credential", lambda p, s: "k1")
    client = _client(monkeypatch, sf)

    r1 = respx.post("http://p1.test/v1/chat/completions").mock(
        return_value=httpx.Response(500, json={"error": "boom"})
    )
    r2 = respx.post("http://p2.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=CANNED_RESPONSE)
    )
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "combo:fb", "messages": [{"role": "user", "content": "x"}]},
    )
    assert resp.status_code == 200
    # p1 must be attempted exactly ONCE (no account spin); then p2 succeeds.
    assert r1.call_count == 1, r1.call_count
    assert r2.called


# --------------------------------------------------------------------------- #
# CRUD accepts the new 'three_tier' strategy
# --------------------------------------------------------------------------- #
def test_combo_create_accepts_three_tier_strategy(monkeypatch):
    sf = _make_sessionmaker()
    _seed_provider_with_accounts(sf, n_accounts=1)
    client = _client(monkeypatch, sf)
    with sf() as session:
        pid = session.query(Provider).first().id
    resp = client.post(
        "/api/combos",
        json={"name": "t", "strategy": "three_tier", "members": [
            {"provider_id": pid, "provider_model": "gpt-4o", "priority": 0},
        ]},
    )
    assert resp.status_code == 201
    assert resp.json()["strategy"] == "three_tier"

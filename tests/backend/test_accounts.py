"""Tests for multi-account + OAuth (Backlog B5.1).

Hermetic in-memory SQLite via StaticPool, mirroring ``test_gateway.py``. Every
module that binds ``SessionLocal`` is rebound to the in-memory factory so the
accounts router, resolver, and combo routing all talk to the same DB.

Upstream OAuth token exchanges are mocked with ``respx`` (no network).
"""

from __future__ import annotations

import respx
import httpx
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

import backend.accounts_router as accounts_router
import backend.combo_routing as combo_routing
import backend.combos_router as combos_router
import backend.config.db as db_mod
import backend.config.logs_router as logs_router
import backend.gateway.router as gateway_router
import backend.gateway.resolver as resolver
import backend.oauth as oauth

from backend.config.db import Base
from backend.models import (
    Combo,
    ComboMember,
    Provider,
    ProviderAccount,
    ProviderModel,
)
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


def _seed(sf: sessionmaker) -> dict:
    with sf() as session:
        provider = Provider(
            name="test",
            type="anthropic",
            base_url="http://provider.test/v1",
            api_key="sk-legacy",
            enabled=True,
        )
        session.add(provider)
        session.flush()
        session.add(
            ProviderModel(
                provider_id=provider.id,
                model_id="claude-3",
                model_name="Claude 3",
                capabilities="chat",
            )
        )
        # Enabled api_key account -> must be selected over provider.api_key.
        acc = ProviderAccount(
            provider_id=provider.id,
            label="acc-1",
            auth_type="api_key",
            api_key="acc-key",
            enabled=True,
        )
        session.add(acc)
        session.flush()
        pid = provider.id
        aid = acc.id
        session.commit()
    return {"provider_id": pid, "account_id": aid}


def _patch_db(monkeypatch, sf: sessionmaker) -> None:
    monkeypatch.setattr(db_mod, "SessionLocal", sf)
    monkeypatch.setattr(resolver, "SessionLocal", sf)
    monkeypatch.setattr(gateway_router, "SessionLocal", sf)
    monkeypatch.setattr(logs_router, "SessionLocal", sf)
    monkeypatch.setattr(combo_routing, "SessionLocal", sf)
    monkeypatch.setattr(combos_router, "SessionLocal", sf)
    monkeypatch.setattr(accounts_router, "SessionLocal", sf)


def _client_with_db(monkeypatch) -> tuple[TestClient, dict]:
    """Build one in-memory DB, seed it, patch every SessionLocal binding, and
    return ``(client, seeded_ids)`` so CRUD tests hit the SAME database."""
    sf = _make_sessionmaker()
    ids = _seed(sf)
    _patch_db(monkeypatch, sf)
    return TestClient(app), ids


# --- Account CRUD -----------------------------------------------------------


def test_list_accounts_requires_provider_id(monkeypatch) -> None:
    client, _ = _client_with_db(monkeypatch)
    resp = client.get("/api/accounts")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "missing_provider_id"


def test_list_accounts_invalid_provider_id(monkeypatch) -> None:
    client, _ = _client_with_db(monkeypatch)
    resp = client.get("/api/accounts?provider_id=abc")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_provider_id"


def test_list_accounts_filters_by_provider(monkeypatch) -> None:
    client, ids = _client_with_db(monkeypatch)
    resp = client.get(f"/api/accounts?provider_id={ids['provider_id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["object"] == "list"
    assert len(body["data"]) == 1
    acc = body["data"][0]
    assert acc["api_key"] == "acc-key"  # ADR-007 plaintext
    assert acc["has_oauth_token"] is False
    assert acc["auth_type"] == "api_key"


def test_create_account_returns_201_plaintext(monkeypatch) -> None:
    client, ids = _client_with_db(monkeypatch)
    resp = client.post(
        "/api/accounts",
        json={
            "provider_id": ids["provider_id"],
            "label": "acc-2",
            "auth_type": "api_key",
            "api_key": "sk-account-2",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["api_key"] == "sk-account-2"  # ADR-007 plaintext in/out
    assert body["id"] > 0
    # exists in DB
    resp2 = client.get(f"/api/accounts?provider_id={ids['provider_id']}")
    assert len(resp2.json()["data"]) == 2


def test_create_account_invalid_auth_type(monkeypatch) -> None:
    client, ids = _client_with_db(monkeypatch)
    resp = client.post(
        "/api/accounts",
        json={"provider_id": ids["provider_id"], "label": "x", "auth_type": "bogus"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_auth_type"


def test_create_account_unknown_provider(monkeypatch) -> None:
    client, _ = _client_with_db(monkeypatch)
    resp = client.post(
        "/api/accounts",
        json={"provider_id": 99999, "label": "x", "auth_type": "api_key"},
    )
    assert resp.status_code == 404


def test_delete_account_ok_and_404(monkeypatch) -> None:
    client, ids = _client_with_db(monkeypatch)
    resp = client.delete(f"/api/accounts/{ids['account_id']}")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    # already gone
    resp2 = client.delete(f"/api/accounts/{ids['account_id']}")
    assert resp2.status_code == 404


# --- OAuth start / callback -------------------------------------------------


def test_oauth_start_known_provider(monkeypatch) -> None:
    client, ids = _client_with_db(monkeypatch)
    resp = client.post(f"/api/oauth/{ids['provider_id']}/start")
    assert resp.status_code == 200
    body = resp.json()
    assert "authorize_url" in body and "state" in body
    assert "claude.ai/oauth/authorize" in body["authorize_url"]
    assert "state=" in body["authorize_url"]
    # state stored in memory keyed by provider id
    assert body["state"] in oauth.OAUTH_STATES
    assert oauth.OAUTH_STATES[body["state"]]["provider_id"] == ids["provider_id"]


def test_oauth_start_by_name(monkeypatch) -> None:
    client, _ = _client_with_db(monkeypatch)
    resp = client.post("/api/oauth/test/start")
    assert resp.status_code == 200
    assert "authorize_url" in resp.json()


def test_oauth_start_unknown_type(monkeypatch) -> None:
    client, _ = _client_with_db(monkeypatch)
    with db_mod.SessionLocal() as session:
        p = Provider(
            name="unknownprov",
            type="does-not-exist",
            base_url="http://x",
            api_key="k",
        )
        session.add(p)
        session.commit()
        pid = p.id
    resp = client.post(f"/api/oauth/{pid}/start")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "oauth_not_configured"


@respx.mock
def test_oauth_callback_exchanges_and_stores(monkeypatch) -> None:
    client, ids = _client_with_db(monkeypatch)
    # start to get a valid state
    start = client.post(f"/api/oauth/{ids['provider_id']}/start").json()
    state = start["state"]

    token_url = oauth.OAUTH_REGISTRY["anthropic"]["token_url"]
    route = respx.post(token_url).mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "at-123",
                "refresh_token": "rt-123",
                "expires_in": 3600,
            },
        )
    )
    resp = client.get(
        f"/api/oauth/{ids['provider_id']}/callback",
        params={"code": "the-code", "state": state},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "account_id" in body

    # account created in DB with tokens + expires_at
    with db_mod.SessionLocal() as session:
        acc = session.get(ProviderAccount, body["account_id"])
        assert acc is not None
        assert acc.auth_type == "oauth"
        assert acc.oauth_token == "at-123"
        assert acc.refresh_token == "rt-123"
        assert acc.expires_at is not None
    assert route.called


# --- get_valid_token auto-refresh -------------------------------------------


@respx.mock
def test_get_valid_token_auto_refresh(monkeypatch) -> None:
    sf = _make_sessionmaker()
    with sf() as session:
        provider = Provider(name="gh", type="github", base_url="http://gh", api_key="")
        session.add(provider)
        session.flush()
        # expired oauth account with refresh token
        account = ProviderAccount(
            provider_id=provider.id,
            label="gh-oauth",
            auth_type="oauth",
            oauth_token="old-token",
            refresh_token="rt-old",
            expires_at=datetime.utcnow() - timedelta(seconds=10),
            enabled=True,
        )
        session.add(account)
        session.flush()
        aid = account.id
        session.commit()

    token_url = oauth.OAUTH_REGISTRY["github"]["token_url"]
    respx.post(token_url).mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "new-token",
                "refresh_token": "rt-new",
                "expires_in": 7200,
            },
        )
    )

    with sf() as session:
        account = session.get(ProviderAccount, aid)
        token = oauth.get_valid_token(account, session)
        assert token == "new-token"
        # DB updated
        assert account.oauth_token == "new-token"
        assert account.refresh_token == "rt-new"
        assert account.expires_at is not None
        assert account.expires_at > datetime.utcnow()


def test_get_valid_token_api_key(monkeypatch) -> None:
    sf = _make_sessionmaker()
    with sf() as session:
        provider = Provider(name="p", type="openai", base_url="b", api_key="")
        session.add(provider)
        session.flush()
        account = ProviderAccount(
            provider_id=provider.id,
            label="k",
            auth_type="api_key",
            api_key="plain-key",
            enabled=True,
        )
        session.add(account)
        session.flush()
        aid = account.id
        session.commit()
    with sf() as session:
        account = session.get(ProviderAccount, aid)
        assert oauth.get_valid_token(account, session) == "plain-key"


# --- resolver wiring --------------------------------------------------------


def test_resolver_uses_account_credential(monkeypatch) -> None:
    _client_with_db(monkeypatch)  # seeds provider + enabled account
    target = resolver.resolve_target("provider:test")
    assert target.api_key == "acc-key"  # account token, not provider.api_key
    assert target.api_key != "sk-legacy"


def test_resolver_falls_back_when_no_accounts(monkeypatch) -> None:
    sf = _make_sessionmaker()
    with sf() as session:
        provider = Provider(
            name="noacc", type="openai", base_url="http://p/v1", api_key="sk-only"
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
    monkeypatch.setattr(db_mod, "SessionLocal", sf)
    monkeypatch.setattr(resolver, "SessionLocal", sf)
    target = resolver.resolve_target("provider:noacc")
    assert target.api_key == "sk-only"  # identical to pre-B5.1 behavior


def test_combo_build_candidates_uses_account(monkeypatch) -> None:
    sf = _make_sessionmaker()
    with sf() as session:
        provider = Provider(
            name="cp", type="anthropic", base_url="http://cp/v1", api_key="sk-legacy"
        )
        session.add(provider)
        session.flush()
        session.add(
            ProviderModel(
                provider_id=provider.id,
                model_id="claude-3",
                model_name="Claude 3",
                capabilities="chat",
            )
        )
        session.add(
            ProviderAccount(
                provider_id=provider.id,
                label="cp-acc",
                auth_type="api_key",
                api_key="cp-account-key",
                enabled=True,
            )
        )
        combo = Combo(name="c1", strategy="fallback", enabled=True)
        session.add(combo)
        session.flush()
        session.add(
            ComboMember(
                combo_id=combo.id,
                provider_id=provider.id,
                provider_model="claude-3",
                priority=0,
                weight=1.0,
            )
        )
        session.commit()
    monkeypatch.setattr(db_mod, "SessionLocal", sf)
    monkeypatch.setattr(combo_routing, "SessionLocal", sf)
    monkeypatch.setattr(resolver, "SessionLocal", sf)

    with sf() as session:
        combo = session.query(Combo).filter_by(name="c1").first()
        candidates = combo_routing.build_candidates(combo, session)
    assert len(candidates) == 1
    assert candidates[0].api_key == "cp-account-key"

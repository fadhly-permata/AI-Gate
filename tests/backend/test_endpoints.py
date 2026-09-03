"""Endpoint CRUD + X-Aigate-Endpoint header routing / proxy binding (B2.5).

Hermetic, no on-disk DB. Mirrors ``test_proxies.py``: an in-memory SQLite
engine (StaticPool) replaces every ``SessionLocal`` binding the routers, logger,
gateway router, combo routing, and proxy selector touch. The upstream
``provider_adapter.chat_completion`` / ``combo_routing.execute_combo`` are
monkeypatched so no real HTTP happens; we only assert the proxy URL that would
be used.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.combo_routing as combo_routing
import backend.config.db as db_mod
import backend.endpoints_router as endpoints_router
import backend.gateway.resolver as resolver
import backend.gateway.router as gateway_router
import backend.proxy_selector as proxy_selector
from backend.config.db import Base
from backend.models import (
    Combo,
    Endpoint,
    EndpointBinding,
    Provider,
    ProviderModel,
    ProxyNode,
    ProxyPool,
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


def _patch_all(monkeypatch, sf: sessionmaker) -> None:
    """Rebind every ``SessionLocal`` binding touched by the endpoints/gateway."""
    monkeypatch.setattr(db_mod, "SessionLocal", sf)
    monkeypatch.setattr(endpoints_router, "SessionLocal", sf)
    monkeypatch.setattr(gateway_router, "SessionLocal", sf)
    monkeypatch.setattr(combo_routing, "SessionLocal", sf)
    monkeypatch.setattr(resolver, "SessionLocal", sf)


def _client(monkeypatch, sf: sessionmaker) -> TestClient:
    _patch_all(monkeypatch, sf)
    return TestClient(app)


# --- helpers to seed via the same in-memory session ------------------------ #


def _seed_endpoint_binding(
    sf: sessionmaker,
    *,
    name="ep1",
    access_control_enabled=False,
    internal_api_key="",
    proxy_pool_id=None,
    bind_type="provider",
    bind_id=1,
) -> int:
    with sf() as s:
        ep = Endpoint(
            name=name,
            access_control_enabled=access_control_enabled,
            internal_api_key=internal_api_key,
            proxy_pool_id=proxy_pool_id,
        )
        s.add(ep)
        s.commit()
        s.refresh(ep)
        eid = ep.id
        s.add(
            EndpointBinding(
                endpoint_id=eid, bind_type=bind_type, bind_id=bind_id
            )
        )
        s.commit()
    return eid


def _seed_provider(sf: sessionmaker, base_url="https://p.example/v1", api_key="k") -> int:
    with sf() as s:
        p = Provider(name="prov", type="openai", base_url=base_url, api_key=api_key)
        s.add(p)
        s.commit()
        s.refresh(p)
        return p.id


def _seed_combo(sf: sessionmaker) -> int:
    with sf() as s:
        c = Combo(name="c1", strategy="fallback", enabled=True)
        s.add(c)
        s.commit()
        s.refresh(c)
        return c.id


def _seed_pool_with_healthy_node(sf: sessionmaker) -> int:
    with sf() as s:
        pool = ProxyPool(name="pool", rotation_strategy="round_robin", enabled=True)
        s.add(pool)
        s.commit()
        s.refresh(pool)
        node = ProxyNode(
            pool_id=pool.id,
            host="10.0.0.5",
            port=3128,
            protocol="http",
            status="healthy",
        )
        s.add(node)
        s.commit()
        s.refresh(node)
        return pool.id


def _expected_proxy_for_pool(sf: sessionmaker, pool_id: int) -> str:
    with sf() as s:
        node = s.query(ProxyNode).filter_by(pool_id=pool_id).first()
        return proxy_selector.build_proxy_url(node)


# =========================================================================== #
# 1. Endpoint CRUD (POST with binding + proxy_pool_id; GET; PUT; DELETE)
# =========================================================================== #


def test_endpoint_crud(monkeypatch) -> None:
    sf = _make_sessionmaker()
    client = _client(monkeypatch, sf)

    # Need a provider + pool id to reference in binding/proxy_pool_id.
    pid = _seed_provider(sf)
    pool_id = _seed_pool_with_healthy_node(sf)

    created = client.post(
        "/api/endpoints",
        json={
            "name": "ep-main",
            "listen_host": "0.0.0.0",
            "listen_port": 9000,
            "access_control_enabled": True,
            "internal_api_key": "topsecret",
            "proxy_pool_id": pool_id,
            "binding": {"bind_type": "provider", "bind_id": pid},
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "ep-main"
    assert body["listen_host"] == "0.0.0.0"
    assert body["listen_port"] == 9000
    assert body["access_control_enabled"] is True
    assert body["proxy_pool_id"] == pool_id
    assert body["binding"] == {"bind_type": "provider", "bind_id": pid}
    eid = body["id"]

    listing = client.get("/api/endpoints")
    assert listing.status_code == 200
    assert listing.json()["object"] == "list"
    assert any(e["id"] == eid for e in listing.json()["data"])

    detail = client.get(f"/api/endpoints/{eid}")
    assert detail.status_code == 200
    assert detail.json()["name"] == "ep-main"

    # PUT updates + replace binding to a combo.
    updated = client.put(
        f"/api/endpoints/{eid}",
        json={"name": "ep-renamed", "binding": {"bind_type": "combo", "bind_id": 7}},
    )
    assert updated.status_code == 200
    ub = updated.json()
    assert ub["name"] == "ep-renamed"
    assert ub["binding"] == {"bind_type": "combo", "bind_id": 7}

    # DELETE cascades its EndpointBinding.
    deleted = client.delete(f"/api/endpoints/{eid}")
    assert deleted.status_code == 200
    assert deleted.json() == {"ok": True}
    assert client.get(f"/api/endpoints/{eid}").status_code == 404


def test_endpoint_missing_404(monkeypatch) -> None:
    sf = _make_sessionmaker()
    client = _client(monkeypatch, sf)
    r = client.get("/api/endpoints/999999")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "endpoint_not_found"
    d = client.delete("/api/endpoints/999999")
    assert d.status_code == 404


# =========================================================================== #
# 2. internal_api_key plaintext echoed (ADR-007)
# =========================================================================== #


def test_internal_api_key_plaintext(monkeypatch) -> None:
    sf = _make_sessionmaker()
    client = _client(monkeypatch, sf)
    r = client.post(
        "/api/endpoints",
        json={"name": "ep-key", "internal_api_key": "plain-key-123"},
    )
    assert r.status_code == 201
    assert r.json()["internal_api_key"] == "plain-key-123"


# =========================================================================== #
# 3. Header routing uses proxy (provider binding + ProxyPool)
# =========================================================================== #


def test_header_routing_uses_proxy(monkeypatch) -> None:
    sf = _make_sessionmaker()
    client = _client(monkeypatch, sf)

    pid = _seed_provider(sf)
    pool_id = _seed_pool_with_healthy_node(sf)
    expected_proxy = _expected_proxy_for_pool(sf, pool_id)
    _seed_endpoint_binding(
        sf, name="ep-proxy", proxy_pool_id=pool_id, bind_type="provider", bind_id=pid
    )

    captured = {}

    async def fake_chat_completion(target, payload, proxy_url=None):
        captured["proxy_url"] = proxy_url
        captured["target"] = target
        return {"ok": True}

    monkeypatch.setattr(
        "backend.gateway.provider_adapter.chat_completion", fake_chat_completion
    )

    resp = client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        headers={"X-Aigate-Endpoint": "ep-proxy"},
    )
    assert resp.status_code == 200
    assert captured["proxy_url"] == expected_proxy
    # Prefix stripped for the upstream model when provider-bound.
    assert captured["target"].upstream_model == "gpt-4"


def test_header_routing_no_proxy_when_unbound(monkeypatch) -> None:
    sf = _make_sessionmaker()
    client = _client(monkeypatch, sf)
    pid = _seed_provider(sf)
    _seed_endpoint_binding(
        sf, name="ep-noprox", proxy_pool_id=None, bind_type="provider", bind_id=pid
    )
    captured = {}

    async def fake_chat_completion(target, payload, proxy_url=None):
        captured["proxy_url"] = proxy_url
        captured["target"] = target
        return {"ok": True}

    monkeypatch.setattr(
        "backend.gateway.provider_adapter.chat_completion", fake_chat_completion
    )
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "provider:gpt-4", "messages": []},
        headers={"X-Aigate-Endpoint": "ep-noprox"},
    )
    assert resp.status_code == 200
    assert captured["proxy_url"] is None
    # "provider:" prefix stripped for the upstream model.
    assert captured["target"].upstream_model == "gpt-4"


def test_header_routing_endpoint_not_found(monkeypatch) -> None:
    sf = _make_sessionmaker()
    client = _client(monkeypatch, sf)
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4", "messages": []},
        headers={"X-Aigate-Endpoint": "does-not-exist"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "endpoint_not_found"


# =========================================================================== #
# 4. Access control (401 when key required and missing/wrong)
# =========================================================================== #


def test_access_control_unauthorized(monkeypatch) -> None:
    sf = _make_sessionmaker()
    client = _client(monkeypatch, sf)
    pid = _seed_provider(sf)
    _seed_endpoint_binding(
        sf,
        name="ep-acl",
        access_control_enabled=True,
        internal_api_key="right-key",
        bind_type="provider",
        bind_id=pid,
    )

    # No key -> 401.
    r = client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4", "messages": []},
        headers={"X-Aigate-Endpoint": "ep-acl"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"

    # Wrong key -> 401.
    r2 = client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4", "messages": []},
        headers={"X-Aigate-Endpoint": "ep-acl", "x-api-key": "wrong-key"},
    )
    assert r2.status_code == 401


def test_access_control_authorized(monkeypatch) -> None:
    sf = _make_sessionmaker()
    client = _client(monkeypatch, sf)
    pid = _seed_provider(sf)
    _seed_endpoint_binding(
        sf,
        name="ep-acl2",
        access_control_enabled=True,
        internal_api_key="right-key",
        bind_type="provider",
        bind_id=pid,
    )
    called = {}

    async def fake_chat_completion(target, payload, proxy_url=None):
        called["yes"] = True
        return {"ok": True}

    monkeypatch.setattr(
        "backend.gateway.provider_adapter.chat_completion", fake_chat_completion
    )

    # x-api-key header path.
    r = client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4", "messages": []},
        headers={"X-Aigate-Endpoint": "ep-acl2", "x-api-key": "right-key"},
    )
    assert r.status_code == 200
    assert called.get("yes") is True

    # Authorization: Bearer path.
    called.clear()
    r2 = client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4", "messages": []},
        headers={
            "X-Aigate-Endpoint": "ep-acl2",
            "Authorization": "Bearer right-key",
        },
    )
    assert r2.status_code == 200
    assert called.get("yes") is True


# =========================================================================== #
# 5. No-header path unchanged (existing model-based routing still wired)
# =========================================================================== #


def test_no_header_path_still_routes(monkeypatch) -> None:
    sf = _make_sessionmaker()
    client = _client(monkeypatch, sf)
    # Provider with a ProviderModel so model-based resolution works.
    with sf() as s:
        p = Provider(
            name="openai", type="openai", base_url="https://api.openai.com/v1", api_key="k"
        )
        s.add(p)
        s.commit()
        s.refresh(p)
        s.add(ProviderModel(provider_id=p.id, model_id="gpt-4", model_name="GPT-4"))
        s.commit()

    captured = {}

    async def fake_chat_completion(target, payload, proxy_url=None):
        captured["model_ref"] = target.model_ref
        captured["proxy_url"] = proxy_url
        return {"ok": True}

    monkeypatch.setattr(
        "backend.gateway.provider_adapter.chat_completion", fake_chat_completion
    )

    resp = client.post(
        "/v1/chat/completions",
        json={"model": "provider:openai:gpt-4", "messages": []},
    )
    assert resp.status_code == 200
    # No endpoint header => old path; proxy None (not endpoint-bound).
    assert captured["model_ref"] == "provider:openai:gpt-4"
    assert captured["proxy_url"] is None


# =========================================================================== #
# 6. Combo-bound endpoint forwards proxy_url to execute_combo
# =========================================================================== #


def test_combo_bound_endpoint_forwards_proxy(monkeypatch) -> None:
    sf = _make_sessionmaker()
    client = _client(monkeypatch, sf)
    cid = _seed_combo(sf)
    pool_id = _seed_pool_with_healthy_node(sf)
    expected_proxy = _expected_proxy_for_pool(sf, pool_id)
    ep_id = _seed_endpoint_binding(
        sf, name="ep-combo", proxy_pool_id=pool_id, bind_type="combo", bind_id=cid
    )

    captured = {}

    async def fake_execute_combo(
        combo_ref, payload, proxy_url=None, endpoint_id=None, saved_tokens_est=None
    ):
        captured["combo_ref"] = combo_ref
        captured["proxy_url"] = proxy_url
        captured["endpoint_id"] = endpoint_id
        return {"ok": True}

    monkeypatch.setattr(
        "backend.gateway.router.execute_combo", fake_execute_combo
    )

    resp = client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4", "messages": []},
        headers={"X-Aigate-Endpoint": "ep-combo"},
    )
    assert resp.status_code == 200
    assert captured["combo_ref"] == cid  # bound by id
    assert captured["proxy_url"] == expected_proxy
    # B5.5: the endpoint id is threaded through for UsageRecord attribution.
    assert captured["endpoint_id"] == ep_id

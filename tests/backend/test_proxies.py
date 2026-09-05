"""Proxy Pools CRUD + nodes + health-check + selection tests (task B2.3).

Hermetic, no on-disk DB. Mirrors ``test_providers.py``: an in-memory SQLite
engine (StaticPool) replaces every ``SessionLocal`` binding the router and
logger use. ``socket.create_connection`` is monkeypatched to simulate healthy
and dead proxies for the health-check tests.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.config.db as db_mod
import backend.proxies_router as proxies_router
import backend.proxy_selector as proxy_selector
from backend.config.db import Base
from backend.models import ProxyNode, ProxyPool
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
    """Rebind every SessionLocal binding the router + logger touch."""
    monkeypatch.setattr(db_mod, "SessionLocal", sf)
    monkeypatch.setattr(proxies_router, "SessionLocal", sf)


def _client(monkeypatch) -> TestClient:
    sf = _make_sessionmaker()
    _patch_db(monkeypatch, sf)
    return TestClient(app)


# --- 1. Pool CRUD (POST/GET list/GET id/PUT/DELETE cascade) -----------------


def test_pool_crud(monkeypatch) -> None:
    client = _client(monkeypatch)

    created = client.post(
        "/api/proxy-pools",
        json={"name": "mypool", "rotation_strategy": "random", "enabled": True},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "mypool"
    assert body["rotation_strategy"] == "random"
    assert body["enabled"] is True
    assert body["last_used_index"] == 0
    assert body["nodes"] == []
    pid = body["id"]

    listing = client.get("/api/proxy-pools")
    assert listing.status_code == 200
    assert listing.json()["object"] == "list"
    assert any(p["id"] == pid for p in listing.json()["data"])

    by_id = client.get(f"/api/proxy-pools/{pid}")
    assert by_id.status_code == 200
    assert by_id.json()["name"] == "mypool"

    updated = client.put(
        f"/api/proxy-pools/{pid}", json={"name": "renamed", "enabled": False}
    )
    assert updated.status_code == 200
    ub = updated.json()
    assert ub["name"] == "renamed"
    assert ub["enabled"] is False

    missing = client.get("/api/proxy-pools/999999")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "proxy_pool_not_found"

    deleted = client.delete(f"/api/proxy-pools/{pid}")
    assert deleted.status_code == 200
    assert deleted.json() == {"ok": True}

    gone = client.get(f"/api/proxy-pools/{pid}")
    assert gone.status_code == 404

    missing_delete = client.delete("/api/proxy-pools/999999")
    assert missing_delete.status_code == 404


def test_delete_pool_cascades_nodes(monkeypatch) -> None:
    sf = _make_sessionmaker()
    _patch_db(monkeypatch, sf)
    with sf() as session:
        pool = ProxyPool(name="p", rotation_strategy="round_robin", enabled=True)
        session.add(pool)
        session.commit()
        pid = pool.id
        session.add(ProxyNode(pool_id=pid, host="h1", port=1, protocol="http"))
        session.add(ProxyNode(pool_id=pid, host="h2", port=2, protocol="socks5"))
        session.commit()

    client = TestClient(app)
    resp = client.delete(f"/api/proxy-pools/{pid}")
    assert resp.status_code == 200
    with sf() as session:
        assert (
            session.query(ProxyNode).filter_by(pool_id=pid).count() == 0
        )
        assert session.get(ProxyPool, pid) is None


# --- 2. Node CRUD under a pool ----------------------------------------------


def test_node_crud(monkeypatch) -> None:
    client = _client(monkeypatch)
    pid = _seed_via_client(client)

    created = client.post(
        f"/api/proxy-pools/{pid}/nodes",
        json={
            "host": "10.0.0.1",
            "port": 8080,
            "protocol": "https",
            "username": "u",
            "password": "p",
        },
    )
    assert created.status_code == 201
    node = created.json()
    assert node["host"] == "10.0.0.1"
    assert node["port"] == 8080
    assert node["protocol"] == "https"
    assert node["username"] == "u"
    assert node["password"] == "p"
    nid = node["id"]

    listing = client.get(f"/api/proxy-pools/{pid}/nodes")
    assert listing.status_code == 200
    assert any(n["id"] == nid for n in listing.json()["data"])

    updated = client.put(
        f"/api/proxy-pools/{pid}/nodes/{nid}",
        json={"port": 9090, "status": "healthy"},
    )
    assert updated.status_code == 200
    ub = updated.json()
    assert ub["port"] == 9090
    assert ub["status"] == "healthy"

    deleted = client.delete(f"/api/proxy-pools/{pid}/nodes/{nid}")
    assert deleted.status_code == 200
    assert deleted.json() == {"ok": True}

    # No GET single-node route; re-DELETE must 404 (already gone).
    gone = client.delete(f"/api/proxy-pools/{pid}/nodes/{nid}")
    assert gone.status_code == 404


def _seed_via_client(client: TestClient) -> int:
    resp = client.post(
        "/api/proxy-pools", json={"name": "p", "rotation_strategy": "round_robin"}
    )
    return resp.json()["id"]


def test_node_ops_missing_pool_404(monkeypatch) -> None:
    client = _client(monkeypatch)
    r = client.post(
        "/api/proxy-pools/999999/nodes",
        json={"host": "h", "port": 1},
    )
    assert r.status_code == 404
    r2 = client.get("/api/proxy-pools/999999/nodes")
    assert r2.status_code == 404


# --- 3. Health-check updates status + latency -------------------------------


def test_health_check_healthy_and_dead(monkeypatch) -> None:
    sf = _make_sessionmaker()
    _patch_db(monkeypatch, sf)
    with sf() as session:
        pool = ProxyPool(name="p", rotation_strategy="round_robin", enabled=True)
        session.add(pool)
        session.commit()
        pid = pool.id
        n_ok = ProxyNode(pool_id=pid, host="good", port=1111, protocol="http")
        n_bad = ProxyNode(pool_id=pid, host="bad", port=2222, protocol="socks5")
        session.add(n_ok)
        session.add(n_bad)
        session.commit()
        ok_id, bad_id = n_ok.id, n_bad.id

    def fake_connect(addr, timeout=None):
        host, port = addr
        if port == 1111:
            return _FakeSock()
        raise OSError("unreachable")

    monkeypatch.setattr(proxies_router.socket, "create_connection", fake_connect)

    client = TestClient(app)
    resp = client.post(f"/api/proxy-pools/{pid}/health-check")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    by_id = {r["node_id"]: r for r in body["results"]}
    assert by_id[ok_id]["status"] == "healthy"
    assert by_id[ok_id]["latency_ms"] > 0
    assert by_id[bad_id]["status"] == "dead"
    assert by_id[bad_id]["latency_ms"] == 0.0

    with sf() as session:
        ok = session.get(ProxyNode, ok_id)
        bad = session.get(ProxyNode, bad_id)
        assert ok.status == "healthy"
        assert ok.uptime_pct == 100.0
        assert ok.last_latency_ms > 0
        assert ok.last_checked is not None
        assert bad.status == "dead"
        assert bad.uptime_pct == 0.0
        assert bad.last_latency_ms == 0.0


class _FakeSock:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


# --- 4. select_node per strategy --------------------------------------------


def test_select_node_strategies(monkeypatch) -> None:
    sf = _make_sessionmaker()
    _patch_db(monkeypatch, sf)
    with sf() as session:
        pool = ProxyPool(name="p", rotation_strategy="round_robin", enabled=True)
        session.add(pool)
        session.commit()
        pid = pool.id
        a = ProxyNode(pool_id=pid, host="a", port=1, protocol="http", status="healthy")
        b = ProxyNode(pool_id=pid, host="b", port=2, protocol="http", status="healthy")
        session.add(a)
        session.add(b)
        session.commit()
        aid, bid = a.id, b.id

    # Re-fetch pool with its nodes attached.
    with sf() as session:
        pool = session.get(ProxyPool, pid)

        # failover -> first by id asc
        pool.rotation_strategy = "failover"
        chosen = proxy_selector.select_node(pool, session)
        assert chosen is not None and chosen.id == min(aid, bid)

        # random -> one of them
        pool.rotation_strategy = "random"
        for _ in range(10):
            c = proxy_selector.select_node(pool, session)
            assert c.id in (aid, bid)

        # round_robin -> cycles; call twice, expect different nodes
        pool.rotation_strategy = "round_robin"
        pool.last_used_index = 0
        first = proxy_selector.select_node(pool, session)
        second = proxy_selector.select_node(pool, session)
        assert first is not None and second is not None
        assert first.id != second.id

    # healthy-only: mark all dead -> None
    with sf() as session:
        session.query(ProxyNode).filter_by(pool_id=pid).update(
            {"status": "dead"}, synchronize_session=False
        )
        session.commit()
        pool = session.get(ProxyPool, pid)
        assert proxy_selector.select_node(pool, session) is None


def test_build_proxy_url() -> None:
    mk = lambda proto, u, pw: type(
        "N", (), {"protocol": proto, "username": u, "password": pw, "host": "h", "port": 9}
    )()
    assert proxy_selector.build_proxy_url(mk("http", "", "")) == "http://h:9"
    assert proxy_selector.build_proxy_url(mk("https", "u", "p")) == "https://u:p@h:9"
    assert proxy_selector.build_proxy_url(mk("socks5", "u", "p")) == "socks5://u:p@h:9"
    assert proxy_selector.build_proxy_url(mk("socks5", "u", "")) == "socks5://h:9"


# --- 5. Plaintext username/password echoed (ADR-007) ------------------------


def test_plaintext_creds_echoed(monkeypatch) -> None:
    client = _client(monkeypatch)
    pid = _seed_via_client(client)
    resp = client.post(
        f"/api/proxy-pools/{pid}/nodes",
        json={"host": "h", "port": 1, "username": "user", "password": "secret"},
    ).json()
    assert resp["username"] == "user"
    assert resp["password"] == "secret"

    detail = client.get(f"/api/proxy-pools/{pid}").json()
    node = detail["nodes"][0]
    assert node["username"] == "user"
    assert node["password"] == "secret"

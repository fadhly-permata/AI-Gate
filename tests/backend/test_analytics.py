"""B5.6 tests: token_saver savings metrics, saved_tokens_est persistence,
GET /api/request-logs and GET /api/analytics aggregation, and the
usage_records.saved_tokens_est self-heal migration.

Hermetic in-memory DB (StaticPool) mirroring test_usage.py; respx upstream.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.analytics_router as analytics_router
import backend.combo_routing as combo_routing
import backend.config.db as db_mod
import backend.config.logs_router as logs_router
import backend.gateway.resolver as resolver
import backend.gateway.router as gateway_router
import backend.gateway.token_saver as token_saver
import backend.usage as usage
import backend.usage_router as usage_router
from backend.config.db import Base, _ensure_usage_record_saved_tokens_column
from backend.models import (
    Endpoint,
    EndpointBinding,
    LogEntry,
    Provider,
    ProviderModel,
    RequestLog,
    Setting,
    UsageRecord,
)
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
    monkeypatch.setattr(gateway_router, "SessionLocal", sf)
    monkeypatch.setattr(combo_routing, "SessionLocal", sf)
    monkeypatch.setattr(logs_router, "SessionLocal", sf)
    monkeypatch.setattr(usage_router, "SessionLocal", sf)
    monkeypatch.setattr(analytics_router, "SessionLocal", sf)


@pytest.fixture
def sf(monkeypatch):
    factory = _make_sessionmaker()
    _patch_db(monkeypatch, factory)
    return factory


def _seed_provider(sf, name="p", base_url=None) -> int:
    with sf() as session:
        p = Provider(
            name=name,
            type="openai",
            base_url=base_url or f"http://{name}.test/v1",
            api_key="sk-x",
            enabled=True,
        )
        session.add(p)
        session.flush()  # assign p.id before referencing it
        session.add(ProviderModel(provider_id=p.id, model_id="gpt-4o", model_name="GPT-4o"))
        session.commit()
        return p.id


def _seed_endpoint(sf, name, token_saver_mode, provider_id) -> int:
    with sf() as session:
        ep = Endpoint(name=name, token_saver=token_saver_mode)
        session.add(ep)
        session.flush()
        session.add(
            EndpointBinding(endpoint_id=ep.id, bind_type="provider", bind_id=provider_id)
        )
        session.commit()
        return ep.id


def _large_git_diff() -> str:
    header = "diff --git a/foo.py b/foo.py\nindex 0000000..1111111 100644\n"
    lines = "\n".join(f"+line_{i} = {i}" for i in range(500))
    return header + lines + "\n" + "\n\n\n\n\n" + "git diff tail\n"


# --------------------------------------------------------------------------- #
# token_saver metrics (unit)
# --------------------------------------------------------------------------- #
def test_apply_token_saver_with_metrics_rtk_positive():
    payload = {
        "model": "x",
        "messages": [
            {"role": "user", "content": "diff please"},
            {"role": "tool", "content": _large_git_diff()},
        ],
    }
    new_payload, saved = token_saver.apply_token_saver_with_metrics("rtk", payload)
    assert saved > 0
    tool_msg = next(m for m in new_payload["messages"] if m["role"] == "tool")
    assert "[...truncated" in tool_msg["content"]


def test_apply_token_saver_with_metrics_caveman_zero():
    payload = {"model": "x", "messages": [{"role": "user", "content": "hi"}]}
    new_payload, saved = token_saver.apply_token_saver_with_metrics("caveman", payload)
    assert saved == 0  # output-side savings not measurable (documented)
    assert new_payload["messages"][0]["role"] == "system"


def test_apply_token_saver_with_metrics_off_identity_zero():
    payload = {"model": "x", "messages": []}
    new_payload, saved = token_saver.apply_token_saver_with_metrics("off", payload)
    assert new_payload is payload
    assert saved == 0


def test_apply_token_saver_backward_compatible():
    payload = {"model": "x", "messages": [{"role": "user", "content": "hello"}]}
    assert token_saver.apply_token_saver("off", payload) is payload


def test_saved_tokens_from_bytes_heuristic():
    assert usage.saved_tokens_from_bytes(100) == 25
    assert usage.saved_tokens_from_bytes(3) == 0
    assert usage.saved_tokens_from_bytes(-50) == 0
    assert usage.saved_tokens_from_bytes(None) == 0


# --------------------------------------------------------------------------- #
# Gateway persists saved_tokens_est (savings tracking)
# --------------------------------------------------------------------------- #
@respx.mock
def test_gateway_rtk_records_positive_saved_tokens_est(sf):
    pid = _seed_provider(sf, "sv", base_url="http://sv1.test/v1")
    _seed_endpoint(sf, "ep-rtk", "rtk", pid)
    respx.post("http://sv1.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=CANNED_RESPONSE)
    )
    client = TestClient(app)
    resp = client.post(
        "/v1/chat/completions",
        headers={"X-Aigate-Endpoint": "ep-rtk"},
        json={
            "model": "gpt-4o",
            "messages": [
                {"role": "user", "content": "diff please"},
                {"role": "tool", "content": _large_git_diff()},
            ],
        },
    )
    assert resp.status_code == 200
    with sf() as session:
        row = session.query(UsageRecord).one()
    assert row.saved_tokens_est is not None and row.saved_tokens_est > 0


@respx.mock
def test_gateway_caveman_records_zero_saved_tokens_est(sf):
    pid = _seed_provider(sf, "sv", base_url="http://sv2.test/v1")
    _seed_endpoint(sf, "ep-cav", "caveman", pid)
    respx.post("http://sv2.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=CANNED_RESPONSE)
    )
    client = TestClient(app)
    resp = client.post(
        "/v1/chat/completions",
        headers={"X-Aigate-Endpoint": "ep-cav"},
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 200
    with sf() as session:
        row = session.query(UsageRecord).one()
    # Saver applied but output-side -> 0 (NOT NULL: distinguishable from "off").
    assert row.saved_tokens_est == 0


@respx.mock
def test_gateway_no_saver_records_null(sf):
    pid = _seed_provider(sf, "sv", base_url="http://sv3.test/v1")
    respx.post("http://sv3.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=CANNED_RESPONSE)
    )
    client = TestClient(app)
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "provider:sv:gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 200
    with sf() as session:
        row = session.query(UsageRecord).one()
    assert row.saved_tokens_est is None  # no saver -> not measured


def test_record_usage_saved_tokens_default_null(sf):
    pid = _seed_provider(sf, "sv")
    row = usage.record_usage(None, pid, None, "gpt-4o", 10, 10)
    assert row is not None
    assert row.saved_tokens_est is None
    row2 = usage.record_usage(None, pid, None, "gpt-4o", 10, 10, saved_tokens_est=7)
    assert row2.saved_tokens_est == 7


# --------------------------------------------------------------------------- #
# GET /api/request-logs
# --------------------------------------------------------------------------- #
def _seed_request_logs(sf) -> dict:
    with sf() as session:
        a = RequestLog(
            endpoint_id=1, model="gpt-4o", ts=datetime(2026, 9, 1, 10, 0),
            duration_ms=100, request="ra", response="sa",
        )
        b = RequestLog(
            endpoint_id=1, model="gpt-4o-mini", ts=datetime(2026, 9, 2, 10, 0),
            duration_ms=200, request="rb", response="sb",
        )
        c = RequestLog(
            endpoint_id=2, model="claude", ts=datetime(2026, 9, 3, 10, 0),
            duration_ms=300, request="rc", response="sc",
        )
        session.add_all([a, b, c])
        session.commit()
        return {"a": a.id, "b": b.id, "c": c.id}


def test_api_request_logs_shape_newest_first(sf):
    ids = _seed_request_logs(sf)
    client = TestClient(app)
    resp = client.get("/api/request-logs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["object"] == "list"
    assert [r["id"] for r in body["data"]] == [ids["c"], ids["b"], ids["a"]]
    row = body["data"][0]
    assert set(row.keys()) == {
        "id", "endpoint_id", "model", "ts", "duration_ms", "request", "response",
    }
    assert row["duration_ms"] == 300
    assert row["ts"].startswith("2026-09-03")


def test_api_request_logs_limit_and_endpoint_filter(sf):
    ids = _seed_request_logs(sf)
    client = TestClient(app)
    resp = client.get("/api/request-logs?limit=2")
    assert [r["id"] for r in resp.json()["data"]] == [ids["c"], ids["b"]]
    resp = client.get("/api/request-logs?endpoint_id=1")
    assert [r["id"] for r in resp.json()["data"]] == [ids["b"], ids["a"]]


def test_api_request_logs_limit_capped(sf):
    _seed_request_logs(sf)
    client = TestClient(app)
    resp = client.get("/api/request-logs?limit=99999")
    assert resp.status_code == 200  # capped at MAX_LIMIT, not an error
    assert analytics_router.MAX_LIMIT == 500


def test_api_request_logs_bad_params_400(sf):
    client = TestClient(app)
    resp = client.get("/api/request-logs?endpoint_id=abc")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_endpoint_id"
    resp = client.get("/api/request-logs?limit=abc")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_limit"
    resp = client.get("/api/request-logs?limit=0")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_limit"


# --------------------------------------------------------------------------- #
# GET /api/analytics — buckets + totals + by_group
# --------------------------------------------------------------------------- #
def _seed_analytics_rows(sf) -> dict:
    p1 = _seed_provider(sf, "alpha")
    p2 = _seed_provider(sf, "beta")
    now = datetime.utcnow()
    with sf() as session:
        session.add_all(
            [
                # Today (current bucket): 2 rows.
                UsageRecord(provider_id=p1, model="gpt-4o", tokens_in=100,
                            tokens_out=50, cost_est=0.1, saved_tokens_est=8, ts=now),
                UsageRecord(provider_id=p1, model="gpt-4o", tokens_in=10,
                            tokens_out=10, cost_est=0.01, saved_tokens_est=None,
                            ts=now),
                # 2 days back.
                UsageRecord(provider_id=p2, model="claude-3-5-sonnet", tokens_in=20,
                            tokens_out=20, cost_est=0.02, saved_tokens_est=4,
                            ts=now - timedelta(days=2)),
                # 29 days back: first bucket of the 30-day window.
                UsageRecord(provider_id=p1, model="gpt-4o", tokens_in=1,
                            tokens_out=1, cost_est=0.001, saved_tokens_est=0,
                            ts=now - timedelta(days=29)),
                # 31 days back: OUTSIDE the month window.
                UsageRecord(provider_id=p1, model="gpt-4o", tokens_in=999,
                            tokens_out=999, cost_est=9.99, saved_tokens_est=999,
                            ts=now - timedelta(days=31)),
            ]
        )
        session.commit()
    return {"p1": p1, "p2": p2, "now": now}


def test_api_analytics_month_shape_and_totals(sf):
    _seed_analytics_rows(sf)
    client = TestClient(app)
    resp = client.get("/api/analytics?range=month&group_by=model")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {
        "object", "range", "group_by", "buckets", "totals", "by_group",
    }
    assert body["object"] == "analytics"
    assert body["range"] == "month"
    assert body["group_by"] == "model"
    assert len(body["buckets"]) == 30
    assert set(body["buckets"][0].keys()) == {
        "label", "requests", "tokens_in", "tokens_out", "cost_est", "saved_tokens_est",
    }
    assert body["totals"] == {
        "requests": 4,
        "tokens_in": 131,
        "tokens_out": 81,
        "cost_est": pytest.approx(0.131),
        "saved_tokens_est": 12,  # 8 + 4 + 0 + (None -> 0)
    }
    # First bucket = 29 days back (daily label), last bucket = today.
    assert body["buckets"][0]["label"] == (
        datetime.utcnow() - timedelta(days=29)
    ).strftime("%Y-%m-%d")
    assert body["buckets"][0]["requests"] == 1
    assert body["buckets"][-1]["label"] == datetime.utcnow().strftime("%Y-%m-%d")
    assert body["buckets"][-1]["requests"] == 2
    assert body["buckets"][-1]["saved_tokens_est"] == 8
    # Empty middle buckets included as zeros for a continuous trend.
    assert body["buckets"][5] == {
        "label": body["buckets"][5]["label"],
        "requests": 0, "tokens_in": 0, "tokens_out": 0,
        "cost_est": 0.0, "saved_tokens_est": 0,
    }
    by_model = {g["key"]: g for g in body["by_group"]}
    assert set(by_model) == {"gpt-4o", "claude-3-5-sonnet"}
    assert by_model["gpt-4o"]["requests"] == 3
    assert by_model["gpt-4o"]["tokens_in"] == 111
    assert by_model["gpt-4o"]["saved_tokens_est"] == 8
    assert by_model["claude-3-5-sonnet"]["requests"] == 1
    # Sorted by requests desc.
    assert [g["key"] for g in body["by_group"]] == ["gpt-4o", "claude-3-5-sonnet"]


def test_api_analytics_day_uses_hourly_buckets(sf):
    _seed_analytics_rows(sf)
    client = TestClient(app)
    resp = client.get("/api/analytics?range=day")
    body = resp.json()
    assert body["range"] == "day"
    assert body["group_by"] == "model"  # default
    assert len(body["buckets"]) == 24
    assert body["buckets"][-1]["label"] == datetime.utcnow().strftime(
        "%Y-%m-%d %H:00"
    )
    # Only the two "now" rows fall inside the last 24h of hourly buckets.
    assert body["totals"]["requests"] == 2
    assert body["totals"]["saved_tokens_est"] == 8


def test_api_analytics_week_buckets(sf):
    _seed_analytics_rows(sf)
    client = TestClient(app)
    resp = client.get("/api/analytics?range=week")
    body = resp.json()
    assert len(body["buckets"]) == 7
    assert body["totals"]["requests"] == 3  # month-old row excluded


def test_api_analytics_group_by_provider(sf):
    _seed_analytics_rows(sf)
    with sf() as session:
        session.add(
            UsageRecord(provider_id=9999, model="ghost", tokens_in=5, tokens_out=5,
                        cost_est=0.0, ts=datetime.utcnow())
        )
        session.commit()
    client = TestClient(app)
    resp = client.get("/api/analytics?range=month&group_by=provider")
    body = resp.json()
    keys = {g["key"] for g in body["by_group"]}
    # provider NAMEs; missing provider falls back to "provider#<id>".
    assert keys == {"alpha", "beta", "provider#9999"}


def test_api_analytics_bad_params_400(sf):
    client = TestClient(app)
    resp = client.get("/api/analytics?range=year")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_range"
    resp = client.get("/api/analytics?group_by=endpoint")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_group_by"


def test_api_analytics_empty_db(sf):
    client = TestClient(app)
    resp = client.get("/api/analytics?range=month")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["buckets"]) == 30
    assert body["totals"]["requests"] == 0
    assert body["by_group"] == []


def test_analytics_calls_are_logged(sf):
    client = TestClient(app)
    client.get("/api/request-logs")
    client.get("/api/analytics")
    with sf() as session:
        msgs = [
            r.message
            for r in session.query(LogEntry).filter_by(source="backend.analytics.router").all()
        ]
    assert any(m.startswith("GET /api/request-logs") for m in msgs)
    assert any(m.startswith("GET /api/analytics") for m in msgs)


# --------------------------------------------------------------------------- #
# Migration: usage_records.saved_tokens_est self-heal
# --------------------------------------------------------------------------- #
def _build_old_usage_records_table(engine) -> None:
    with engine.connect() as conn:
        conn.execute(
            text(
                "CREATE TABLE usage_records ("
                "id INTEGER PRIMARY KEY, endpoint_id INTEGER, provider_id INTEGER, "
                "account_id INTEGER, model TEXT, tokens_in INTEGER, "
                "tokens_out INTEGER, cost_est FLOAT, ts DATETIME)"
            )
        )
        conn.commit()


def _usage_columns(engine) -> set:
    with engine.connect() as conn:
        return {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(usage_records)")).fetchall()
        }


def test_ensure_saved_tokens_column_adds_and_is_idempotent():
    engine = create_engine("sqlite:///:memory:", future=True)
    _build_old_usage_records_table(engine)
    assert "saved_tokens_est" not in _usage_columns(engine)
    _ensure_usage_record_saved_tokens_column(engine)
    assert "saved_tokens_est" in _usage_columns(engine)
    # Second run must not raise (no duplicate-column error).
    _ensure_usage_record_saved_tokens_column(engine)
    assert "saved_tokens_est" in _usage_columns(engine)
    engine.dispose()


def test_ensure_saved_tokens_column_noop_when_present():
    from backend import models  # noqa: F401  (register mappers)

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    assert "saved_tokens_est" in _usage_columns(engine)
    _ensure_usage_record_saved_tokens_column(engine)  # silent no-op
    engine.dispose()


def test_ensure_saved_tokens_column_survives_missing_table():
    """Bare engine (no usage_records table) -> logged warning, never crash (R12)."""
    engine = create_engine("sqlite:///:memory:", future=True)
    _ensure_usage_record_saved_tokens_column(engine)  # must not raise
    engine.dispose()

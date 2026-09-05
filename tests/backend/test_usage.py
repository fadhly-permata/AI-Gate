"""B5.5 backend tests: UsageRecord, cost estimation, summarize, quota_status,
/api/usage + /api/usage/summary + /api/quota, gateway recording, quota-aware
combo ordering, and the provider quota-column self-heal migration.

Hermetic, in-memory DB (StaticPool) mirroring test_gateway.py; upstream calls
use respx (no network).
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

import backend.combo_routing as combo_routing
import backend.config.db as db_mod
import backend.config.logs_router as logs_router
import backend.gateway.resolver as resolver
import backend.gateway.router as gateway_router
import backend.usage as usage
import backend.usage_router as usage_router
from backend.config.db import Base
from backend.models import (
    Combo,
    ComboMember,
    Endpoint,
    EndpointBinding,
    LogEntry,
    Provider,
    ProviderModel,
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
    """Rebind every SessionLocal binding usage / gateway / logging touch."""
    monkeypatch.setattr(db_mod, "SessionLocal", sf)
    monkeypatch.setattr(resolver, "SessionLocal", sf)
    monkeypatch.setattr(gateway_router, "SessionLocal", sf)
    monkeypatch.setattr(combo_routing, "SessionLocal", sf)
    monkeypatch.setattr(logs_router, "SessionLocal", sf)
    monkeypatch.setattr(usage_router, "SessionLocal", sf)


@pytest.fixture
def sf(monkeypatch):
    """In-memory session factory patched into every module binding."""
    factory = _make_sessionmaker()
    _patch_db(monkeypatch, factory)
    return factory


def _seed_provider(sf, name="p", **kw) -> int:
    with sf() as session:
        p = Provider(
            name=name,
            type=kw.get("type", "openai"),
            base_url=kw.get("base_url", f"http://{name}.test/v1"),
            api_key="sk-x",
            enabled=True,
            tier=kw.get("tier", "subscription"),
            quota_limit=kw.get("quota_limit"),
            quota_window=kw.get("quota_window"),
        )
        session.add(p)
        session.commit()
        return p.id


# --------------------------------------------------------------------------- #
# estimate_cost
# --------------------------------------------------------------------------- #
def test_estimate_cost_known_model(sf):
    # gpt-4o built-in: (0.0025 in, 0.01 out) per 1k.
    assert usage.estimate_cost("gpt-4o", 1000, 0) == pytest.approx(0.0025)
    assert usage.estimate_cost("gpt-4o", 0, 1000) == pytest.approx(0.01)
    assert usage.estimate_cost("GPT-4O", 1000, 1000) == pytest.approx(0.0125)


def test_estimate_cost_prefix_match(sf):
    # Dated model ids resolve to their family prefix.
    assert usage.estimate_cost("gpt-4o-2024-11-20", 1000, 0) == pytest.approx(0.0025)


def test_estimate_cost_unknown_model_is_zero(sf):
    assert usage.estimate_cost("totally-unknown-model-xyz", 1000, 1000) == 0.0


def test_estimate_cost_setting_override(sf):
    with sf() as session:
        session.add(
            Setting(key="cost_rates", value='{"zzz-model": [1.0, 2.0], "gpt-4o": [0.5, 0.5]}')
        )
        session.commit()
    assert usage.estimate_cost("zzz-model", 1000, 1000) == pytest.approx(3.0)
    # Overrides win over built-ins.
    assert usage.estimate_cost("gpt-4o", 1000, 0) == pytest.approx(0.5)


def test_estimate_cost_malformed_override_falls_back(sf):
    with sf() as session:
        session.add(Setting(key="cost_rates", value="not-json{{"))
        session.commit()
    # Fail-open to built-ins + a warning lands in LogEntry (R12).
    assert usage.estimate_cost("gpt-4o", 1000, 0) == pytest.approx(0.0025)
    with sf() as session:
        rows = (
            session.query(LogEntry)
            .filter(LogEntry.source == "backend.usage", LogEntry.severity == "warning")
            .all()
        )
    assert any("cost_rates" in r.message for r in rows)


# --------------------------------------------------------------------------- #
# record_usage
# --------------------------------------------------------------------------- #
def test_record_usage_inserts_row_with_cost_est(sf):
    pid = _seed_provider(sf, "rec")
    row = usage.record_usage(
        endpoint_id=None,
        provider_id=pid,
        account_id=None,
        model="gpt-4o",
        tokens_in=1000,
        tokens_out=500,
    )
    assert row is not None and row.id is not None
    with sf() as session:
        stored = session.query(UsageRecord).one()
    assert stored.provider_id == pid
    assert stored.tokens_in == 1000
    assert stored.tokens_out == 500
    assert stored.cost_est == pytest.approx(usage.estimate_cost("gpt-4o", 1000, 500))
    assert stored.cost_est > 0
    assert stored.ts is not None


def test_record_usage_fail_open_without_provider(sf):
    row = usage.record_usage(
        endpoint_id=None,
        provider_id=None,
        account_id=None,
        model="gpt-4o",
        tokens_in=1,
        tokens_out=1,
    )
    assert row is None  # never raises
    with sf() as session:
        assert session.query(UsageRecord).count() == 0
        warns = (
            session.query(LogEntry)
            .filter_by(severity="warning", source="backend.usage")
            .all()
        )
    assert any("no provider_id" in r.message for r in warns)


def test_record_usage_from_result_extracts_tokens(sf):
    pid = _seed_provider(sf, "fr")
    row = usage.record_usage_from_result(
        CANNED_RESPONSE, provider_id=pid, account_id=None, model="gpt-4o"
    )
    assert row is not None
    assert row.tokens_in == 1 and row.tokens_out == 2
    # Missing usage block -> 0/0 recorded, still no raise.
    row2 = usage.record_usage_from_result(
        {"choices": []}, provider_id=pid, account_id=None, model="gpt-4o"
    )
    assert row2 is not None and row2.tokens_in == 0 and row2.tokens_out == 0


# --------------------------------------------------------------------------- #
# summarize
# --------------------------------------------------------------------------- #
def _seed_usage_rows(sf) -> dict:
    p1 = _seed_provider(sf, "alpha")
    p2 = _seed_provider(sf, "beta")
    with sf() as session:
        session.add_all(
            [
                UsageRecord(provider_id=p1, model="gpt-4o", tokens_in=100,
                            tokens_out=50, cost_est=0.01, ts=datetime.utcnow()),
                UsageRecord(provider_id=p1, model="gpt-4o", tokens_in=200,
                            tokens_out=100, cost_est=0.02, ts=datetime.utcnow()),
                UsageRecord(provider_id=p2, model="claude-3-5-sonnet", tokens_in=10,
                            tokens_out=10, cost_est=0.003, ts=datetime.utcnow()),
                # Outside the 'day' window (inside 'week').
                UsageRecord(provider_id=p1, model="gpt-4o", tokens_in=999,
                            tokens_out=999, cost_est=9.99,
                            ts=datetime.utcnow() - timedelta(days=3)),
            ]
        )
        session.commit()
    return {"p1": p1, "p2": p2}


def test_summarize_aggregates_totals_and_groups(sf):
    ids = _seed_usage_rows(sf)
    with sf() as session:
        out = usage.summarize(session, range="day")
    assert out["object"] == "usage_summary"
    assert out["range"] == "day"
    assert out["totals"] == {
        "requests": 3,
        "tokens_in": 310,
        "tokens_out": 160,
        "cost_est": pytest.approx(0.033),
    }
    prov_ids = [e["provider_id"] for e in out["by_provider"]]
    assert prov_ids == [ids["p1"], ids["p2"]]
    names = {e["provider_name"] for e in out["by_provider"]}
    assert names == {"alpha", "beta"}
    models = {e["model"]: e["requests"] for e in out["by_model"]}
    assert models == {"gpt-4o": 2, "claude-3-5-sonnet": 1}


def test_summarize_week_window_and_provider_filter(sf):
    ids = _seed_usage_rows(sf)
    with sf() as session:
        week = usage.summarize(session, range="week")
        assert week["totals"]["requests"] == 4
        only_p2 = usage.summarize(session, provider_id=ids["p2"], range="day")
        assert only_p2["totals"]["requests"] == 1
        assert only_p2["by_provider"][0]["provider_id"] == ids["p2"]


# --------------------------------------------------------------------------- #
# quota_status
# --------------------------------------------------------------------------- #
def test_quota_status_limited_provider(sf):
    pid = _seed_provider(sf, "lim", quota_limit=1000, quota_window="day")
    usage.record_usage(None, pid, None, "gpt-4o", 100, 200)  # today: used=300
    with sf() as session:
        # Yesterday's usage must NOT count in the current day window.
        session.add(
            UsageRecord(provider_id=pid, model="gpt-4o", tokens_in=5000,
                        tokens_out=5000, cost_est=1.0,
                        ts=datetime.utcnow() - timedelta(days=1))
        )
        session.commit()
    with sf() as session:
        rows = usage.quota_status(session)
    assert len(rows) == 1
    st = rows[0]
    assert st["provider_id"] == pid
    assert st["quota_limit"] == 1000
    assert st["quota_window"] == "day"
    assert st["used"] == 300
    assert st["remaining"] == 700
    assert st["unlimited"] is False
    assert st["tier"] == "subscription"
    now = datetime.utcnow()
    expected_reset = (
        now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    )
    assert st["reset_at"] == expected_reset.isoformat()
    assert 0 < st["seconds_to_reset"] <= 86400
    assert st["cost_est"] > 0


def test_quota_status_unlimited_provider_included(sf):
    pid = _seed_provider(sf, "unl")  # no quota_limit
    usage.record_usage(None, pid, None, "gpt-4o", 5, 5)
    with sf() as session:
        rows = usage.quota_status(session)
    assert len(rows) == 1
    st = rows[0]
    # Documented decision: unlimited providers are INCLUDED, remaining=None.
    assert st["unlimited"] is True
    assert st["remaining"] is None
    assert st["quota_limit"] is None
    assert st["used"] == 10  # still reported over the default day window


def test_quota_status_hour_and_week_windows(sf):
    ph = _seed_provider(sf, "h", quota_limit=100, quota_window="hour")
    pw = _seed_provider(sf, "w", quota_limit=100, quota_window="week")
    with sf() as session:
        rows = {r["provider_id"]: r for r in usage.quota_status(session)}
    now = datetime.utcnow()
    hour = rows[ph]
    assert hour["window_start"] == now.replace(
        minute=0, second=0, microsecond=0
    ).isoformat()
    assert hour["reset_at"] == (
        now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    ).isoformat()
    week = rows[pw]
    ws = datetime.fromisoformat(week["window_start"])
    assert ws.weekday() == 0 and ws.hour == 0  # Monday 00:00
    assert week["reset_at"] == (ws + timedelta(days=7)).isoformat()


def test_quota_status_provider_id_filter(sf):
    p1 = _seed_provider(sf, "one", quota_limit=10, quota_window="day")
    _seed_provider(sf, "two")
    with sf() as session:
        rows = usage.quota_status(session, provider_id=p1)
    assert [r["provider_id"] for r in rows] == [p1]


# --------------------------------------------------------------------------- #
# API: GET /api/usage, /api/usage/summary, /api/quota
# --------------------------------------------------------------------------- #
def test_api_usage_list_shape(sf):
    pid = _seed_provider(sf, "api")
    usage.record_usage(None, pid, None, "gpt-4o", 10, 20)
    client = TestClient(app)
    resp = client.get("/api/usage")
    assert resp.status_code == 200
    body = resp.json()
    assert body["object"] == "list"
    assert body["range"] == "day"
    assert len(body["data"]) == 1
    row = body["data"][0]
    assert set(row.keys()) == {
        "id", "endpoint_id", "provider_id", "account_id", "model",
        "tokens_in", "tokens_out", "cost_est", "ts",
    }
    assert row["provider_id"] == pid
    assert row["tokens_in"] == 10 and row["tokens_out"] == 20
    assert isinstance(row["ts"], str)


def test_api_usage_invalid_range_400(sf):
    client = TestClient(app)
    resp = client.get("/api/usage?range=bogus")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_range"


def test_api_usage_invalid_provider_id_400(sf):
    client = TestClient(app)
    resp = client.get("/api/usage?provider_id=abc")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_provider_id"


def test_api_usage_summary_shape(sf):
    _seed_usage_rows(sf)
    client = TestClient(app)
    resp = client.get("/api/usage/summary?range=week")
    assert resp.status_code == 200
    body = resp.json()
    assert body["object"] == "usage_summary"
    assert body["range"] == "week"
    assert body["totals"]["requests"] == 4
    assert "by_provider" in body and "by_model" in body
    resp_bad = client.get("/api/usage/summary?range=year")
    assert resp_bad.status_code == 400


def test_api_quota_shape(sf):
    pid = _seed_provider(sf, "q", quota_limit=500, quota_window="day")
    usage.record_usage(None, pid, None, "gpt-4o", 100, 50)
    client = TestClient(app)
    resp = client.get("/api/quota")
    assert resp.status_code == 200
    body = resp.json()
    assert body["object"] == "list"
    st = next(r for r in body["data"] if r["provider_id"] == pid)
    assert st["used"] == 150
    assert st["remaining"] == 350
    assert st["reset_at"]
    resp_filtered = client.get(f"/api/quota?provider_id={pid}")
    assert len(resp_filtered.json()["data"]) == 1
    resp_bad = client.get("/api/quota?provider_id=x")
    assert resp_bad.status_code == 400


def test_api_usage_calls_are_logged(sf):
    client = TestClient(app)
    client.get("/api/usage")
    client.get("/api/usage/summary")
    client.get("/api/quota")
    with sf() as session:
        msgs = [
            r.message
            for r in session.query(LogEntry)
            .filter_by(source="backend.usage.router")
            .all()
        ]
    assert any(m.startswith("GET /api/usage ") for m in msgs)
    assert any(m.startswith("GET /api/usage/summary") for m in msgs)
    assert any(m.startswith("GET /api/quota") for m in msgs)


# --------------------------------------------------------------------------- #
# Gateway records a UsageRecord after a successful chat completion
# --------------------------------------------------------------------------- #
@respx.mock
def test_gateway_records_usage_on_success(sf):
    pid = _seed_provider(sf, "gw", base_url="http://gw.test/v1")
    with sf() as session:
        session.add(ProviderModel(provider_id=pid, model_id="gpt-4o", model_name="GPT-4o"))
        session.commit()
    respx.post("http://gw.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=CANNED_RESPONSE)
    )
    client = TestClient(app)
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "provider:gw:gpt-4o", "messages": [{"role": "user", "content": "x"}]},
    )
    assert resp.status_code == 200
    with sf() as session:
        row = session.query(UsageRecord).one()
    assert row.provider_id == pid
    assert row.model == "gpt-4o"
    assert row.tokens_in == 1 and row.tokens_out == 2
    assert row.endpoint_id is None  # model-based path: no endpoint attribution
    assert row.cost_est > 0  # gpt-4o is a known model


@respx.mock
def test_gateway_records_usage_with_endpoint(sf):
    pid = _seed_provider(sf, "gwe", base_url="http://gwe.test/v1")
    with sf() as session:
        session.add(ProviderModel(provider_id=pid, model_id="gpt-4o", model_name="GPT-4o"))
        ep = Endpoint(name="ep1", listen_host="127.0.0.1", listen_port=9999)
        session.add(ep)
        session.flush()
        session.add(EndpointBinding(endpoint_id=ep.id, bind_type="provider", bind_id=pid))
        session.commit()
        ep_id = ep.id
    respx.post("http://gwe.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=CANNED_RESPONSE)
    )
    client = TestClient(app)
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "x"}]},
        headers={"X-Aigate-Endpoint": "ep1"},
    )
    assert resp.status_code == 200
    with sf() as session:
        row = session.query(UsageRecord).one()
    assert row.endpoint_id == ep_id
    assert row.provider_id == pid


@respx.mock
def test_gateway_combo_records_usage(sf):
    pid = _seed_provider(sf, "gwc", base_url="http://gwc.test/v1")
    with sf() as session:
        session.add(ProviderModel(provider_id=pid, model_id="gpt-4o", model_name="GPT-4o"))
        combo = Combo(name="c1", strategy="fallback", enabled=True)
        session.add(combo)
        session.flush()
        session.add(ComboMember(combo_id=combo.id, provider_id=pid,
                                provider_model="gpt-4o", priority=0, weight=1.0))
        session.commit()
    respx.post("http://gwc.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=CANNED_RESPONSE)
    )
    client = TestClient(app)
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "combo:c1", "messages": [{"role": "user", "content": "x"}]},
    )
    assert resp.status_code == 200
    with sf() as session:
        row = session.query(UsageRecord).one()
    assert row.provider_id == pid and row.tokens_in == 1 and row.tokens_out == 2


@respx.mock
def test_gateway_records_nothing_on_failure(sf):
    pid = _seed_provider(sf, "gwf", base_url="http://gwf.test/v1")
    with sf() as session:
        session.add(ProviderModel(provider_id=pid, model_id="gpt-4o", model_name="GPT-4o"))
        session.commit()
    respx.post("http://gwf.test/v1/chat/completions").mock(
        return_value=httpx.Response(500, json={"error": "boom"})
    )
    client = TestClient(app)
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "provider:gwf:gpt-4o", "messages": [{"role": "user", "content": "x"}]},
    )
    assert resp.status_code == 502  # upstream 5xx envelope
    with sf() as session:
        assert session.query(UsageRecord).count() == 0


# --------------------------------------------------------------------------- #
# quota_aware_order (combo routing integration)
# --------------------------------------------------------------------------- #
def test_quota_aware_order_prefers_remaining_quota(sf):
    p_bad = _seed_provider(sf, "bad", quota_limit=500, quota_window="day")
    p_ok = _seed_provider(sf, "ok", quota_limit=10000, quota_window="day")
    usage.record_usage(None, p_bad, None, "gpt-4o", 300, 300)  # 600 > 500 -> exhausted
    usage.record_usage(None, p_ok, None, "gpt-4o", 100, 100)   # 200 < 10000 -> ok
    t_bad = combo_routing.ResolvedTarget(
        base_url="", api_key="", model_ref="m", upstream_model="m-bad", provider_id=p_bad
    )
    t_ok = combo_routing.ResolvedTarget(
        base_url="", api_key="", model_ref="m", upstream_model="m-ok", provider_id=p_ok
    )
    with sf() as session:
        out = combo_routing.quota_aware_order([t_bad, t_ok], session)
    assert [c.upstream_model for c in out] == ["m-ok", "m-bad"]
    # Deprioritized, never dropped (fallback last-resort preserved).
    assert len(out) == 2


def test_quota_aware_order_no_quota_data_unchanged(sf):
    p1 = _seed_provider(sf, "n1")
    p2 = _seed_provider(sf, "n2")
    t1 = combo_routing.ResolvedTarget(
        base_url="", api_key="", model_ref="m", upstream_model="a", provider_id=p1
    )
    t2 = combo_routing.ResolvedTarget(
        base_url="", api_key="", model_ref="m", upstream_model="b", provider_id=p2
    )
    with sf() as session:
        out = combo_routing.quota_aware_order([t1, t2], session)
    assert [c.upstream_model for c in out] == ["a", "b"]


def test_build_candidates_reorders_exhausted_member(sf):
    """End-to-end: a fallback combo puts the exhausted provider's member last."""
    p_bad = _seed_provider(sf, "cbad", quota_limit=100, quota_window="day")
    p_ok = _seed_provider(sf, "cok", quota_limit=100, quota_window="day")
    usage.record_usage(None, p_bad, None, "gpt-4o", 60, 60)  # 120 > 100 exhausted
    usage.record_usage(None, p_ok, None, "gpt-4o", 10, 10)
    with sf() as session:
        session.add_all(
            [
                ProviderModel(provider_id=p_bad, model_id="m-bad", model_name="m-bad"),
                ProviderModel(provider_id=p_ok, model_id="m-ok", model_name="m-ok"),
            ]
        )
        combo = Combo(name="qa", strategy="fallback", enabled=True)
        session.add(combo)
        session.flush()
        session.add_all(
            [
                ComboMember(combo_id=combo.id, provider_id=p_bad,
                            provider_model="m-bad", priority=0, weight=1.0),
                ComboMember(combo_id=combo.id, provider_id=p_ok,
                            provider_model="m-ok", priority=1, weight=1.0),
            ]
        )
        session.commit()
        combo_id = combo.id
    with sf() as session:
        combo = session.get(Combo, combo_id)
        candidates = combo_routing.build_candidates(combo, session)
    assert [c.upstream_model for c in candidates] == ["m-ok", "m-bad"]


# --------------------------------------------------------------------------- #
# Migration: providers.quota_limit / quota_window self-heal
# --------------------------------------------------------------------------- #
def _build_old_providers_table(engine) -> None:
    with engine.connect() as conn:
        conn.execute(
            text(
                "CREATE TABLE providers ("
                "id INTEGER PRIMARY KEY, name TEXT, type TEXT, base_url TEXT, "
                "api_key TEXT, enabled BOOLEAN, custom_headers TEXT, "
                "created_at DATETIME)"
            )
        )
        conn.commit()


def _provider_columns(engine) -> set:
    with engine.connect() as conn:
        return {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(providers)")).fetchall()
        }


def test_ensure_provider_quota_columns_adds_and_is_idempotent():
    from backend.config.db import _ensure_provider_quota_columns

    engine = create_engine("sqlite:///:memory:", future=True)
    _build_old_providers_table(engine)
    assert "quota_limit" not in _provider_columns(engine)
    _ensure_provider_quota_columns(engine)
    cols = _provider_columns(engine)
    assert {"quota_limit", "quota_window"} <= cols
    # Second run must not raise (no duplicate-column error).
    _ensure_provider_quota_columns(engine)
    assert {"quota_limit", "quota_window"} <= _provider_columns(engine)
    engine.dispose()


def test_ensure_provider_quota_columns_noop_when_present():
    from backend import models  # noqa: F401  (register mappers)
    from backend.config.db import Base, _ensure_provider_quota_columns

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    assert {"quota_limit", "quota_window"} <= _provider_columns(engine)
    _ensure_provider_quota_columns(engine)  # must be a silent no-op
    engine.dispose()


def test_ensure_provider_quota_columns_survives_missing_table():
    """Bare engine (no providers table) -> logged warning, never crash (R12)."""
    from backend.config.db import _ensure_provider_quota_columns

    engine = create_engine("sqlite:///:memory:", future=True)
    _ensure_provider_quota_columns(engine)  # must not raise
    engine.dispose()

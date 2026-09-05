"""B5.6 tests: RequestLog debug model + gateway request-logging behavior.

Covers: the debug gate (Setting ``request_log_enabled`` on/off), duration_ms
measurement, endpoint attribution, secret-header redaction, truncation, the
error path, fail-open, and RequestLog + UsageRecord written together on a
successful request. Hermetic in-memory DB (StaticPool) mirroring
test_usage.py; upstream calls use respx (no network).
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

import backend.analytics_router as analytics_router
import backend.combo_routing as combo_routing
import backend.config.db as db_mod
import backend.config.logs_router as logs_router
import backend.gateway.resolver as resolver
import backend.gateway.router as gateway_router
from backend.config.db import Base
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
    """Rebind every SessionLocal binding the gateway / analytics / logging touch."""
    monkeypatch.setattr(db_mod, "SessionLocal", sf)
    monkeypatch.setattr(resolver, "SessionLocal", sf)
    monkeypatch.setattr(gateway_router, "SessionLocal", sf)
    monkeypatch.setattr(combo_routing, "SessionLocal", sf)
    monkeypatch.setattr(logs_router, "SessionLocal", sf)
    monkeypatch.setattr(analytics_router, "SessionLocal", sf)


@pytest.fixture
def sf(monkeypatch):
    factory = _make_sessionmaker()
    _patch_db(monkeypatch, factory)
    return factory


def _enable_request_log(sf, value: str = "true") -> None:
    with sf() as session:
        session.add(Setting(key="request_log_enabled", value=value))
        session.commit()


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


def _post_completion(client: TestClient, model="provider:p:gpt-4o", **kw):
    return client.post(
        "/v1/chat/completions",
        json={"model": model, "messages": [{"role": "user", "content": "halo"}]},
        **kw,
    )


# --------------------------------------------------------------------------- #
# Debug gate
# --------------------------------------------------------------------------- #
@respx.mock
def test_request_log_written_when_enabled(sf):
    _seed_provider(sf, "p", base_url="http://rl1.test/v1")
    _enable_request_log(sf)
    respx.post("http://rl1.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=CANNED_RESPONSE)
    )
    client = TestClient(app)
    resp = _post_completion(client, model="provider:p:gpt-4o")
    assert resp.status_code == 200
    with sf() as session:
        row = session.query(RequestLog).one()
    assert row.model == "gpt-4o"  # upstream model, not the provider: ref
    assert row.endpoint_id is None  # model-based path: no endpoint attribution
    assert row.duration_ms >= 0
    assert row.ts is not None
    doc = json.loads(row.request)
    assert "headers" in doc and "body" in doc
    assert doc["body"]["model"] == "provider:p:gpt-4o"
    assert '"status": "ok"' in row.response
    assert "hi there" in row.response  # content preview present


@respx.mock
def test_request_log_not_written_when_disabled(sf):
    _seed_provider(sf, "p", base_url="http://rl2.test/v1")
    # No Setting row at all -> default OFF.
    respx.post("http://rl2.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=CANNED_RESPONSE)
    )
    client = TestClient(app)
    resp = _post_completion(client, model="provider:p:gpt-4o")
    assert resp.status_code == 200
    with sf() as session:
        assert session.query(RequestLog).count() == 0
        # B5.5 UsageRecord still records regardless of the debug gate.
        assert session.query(UsageRecord).count() == 1


@respx.mock
def test_request_log_explicit_false_not_written(sf):
    _seed_provider(sf, "p", base_url="http://rl3.test/v1")
    _enable_request_log(sf, value="false")
    respx.post("http://rl3.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=CANNED_RESPONSE)
    )
    client = TestClient(app)
    assert _post_completion(client, model="provider:p:gpt-4o").status_code == 200
    with sf() as session:
        assert session.query(RequestLog).count() == 0


@respx.mock
def test_request_log_case_insensitive_true(sf):
    _seed_provider(sf, "p", base_url="http://rl4.test/v1")
    _enable_request_log(sf, value="TRUE")
    respx.post("http://rl4.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=CANNED_RESPONSE)
    )
    client = TestClient(app)
    assert _post_completion(client, model="provider:p:gpt-4o").status_code == 200
    with sf() as session:
        assert session.query(RequestLog).count() == 1


# --------------------------------------------------------------------------- #
# Endpoint attribution + together-with-usage
# --------------------------------------------------------------------------- #
@respx.mock
def test_gateway_records_request_log_and_usage_together(sf):
    """DoD: a successful request writes RequestLog AND UsageRecord."""
    pid = _seed_provider(sf, "p", base_url="http://rl5.test/v1")
    _enable_request_log(sf)
    respx.post("http://rl5.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=CANNED_RESPONSE)
    )
    client = TestClient(app)
    assert _post_completion(client, model="provider:p:gpt-4o").status_code == 200
    with sf() as session:
        log_row = session.query(RequestLog).one()
        usage_row = session.query(UsageRecord).one()
    assert log_row.model == usage_row.model == "gpt-4o"
    assert usage_row.provider_id == pid


@respx.mock
def test_request_log_endpoint_attribution(sf):
    pid = _seed_provider(sf, "p", base_url="http://rl6.test/v1")
    with sf() as session:
        ep = Endpoint(name="ep1", listen_host="127.0.0.1", listen_port=9999)
        session.add(ep)
        session.flush()
        session.add(
            EndpointBinding(endpoint_id=ep.id, bind_type="provider", bind_id=pid)
        )
        session.commit()
        ep_id = ep.id
    _enable_request_log(sf)
    respx.post("http://rl6.test/v1/chat/completions").mock(
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
        row = session.query(RequestLog).one()
    assert row.endpoint_id == ep_id
    assert row.model == "gpt-4o"


# --------------------------------------------------------------------------- #
# Error path + redaction + truncation + duration + fail-open
# --------------------------------------------------------------------------- #
@respx.mock
def test_request_log_error_path_recorded(sf):
    _seed_provider(sf, "p", base_url="http://rl7.test/v1")
    _enable_request_log(sf)
    respx.post("http://rl7.test/v1/chat/completions").mock(
        return_value=httpx.Response(500, json={"error": "boom"})
    )
    client = TestClient(app)
    resp = _post_completion(client, model="provider:p:gpt-4o")
    assert resp.status_code == 502  # upstream 5xx envelope
    with sf() as session:
        row = session.query(RequestLog).one()
        usage_count = session.query(UsageRecord).count()
    assert usage_count == 0  # failures record no usage (B5.5 semantics kept)
    doc = json.loads(row.response)
    assert doc["status"] == "error"
    assert doc["http_status"] == 502


@respx.mock
def test_request_log_redacts_secret_headers(sf):
    _seed_provider(sf, "p", base_url="http://rl8.test/v1")
    _enable_request_log(sf)
    respx.post("http://rl8.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=CANNED_RESPONSE)
    )
    client = TestClient(app)
    resp = _post_completion(
        client,
        model="provider:p:gpt-4o",
        headers={"Authorization": "Bearer sk-supersecret-123"},
    )
    assert resp.status_code == 200
    with sf() as session:
        row = session.query(RequestLog).one()
    assert "sk-supersecret-123" not in row.request
    assert "***REDACTED***" in row.request
    # Non-secret headers still recorded.
    assert "content-type" in json.loads(row.request)["headers"]


@respx.mock
def test_request_log_truncates_large_body(sf):
    _seed_provider(sf, "p", base_url="http://rl9.test/v1")
    _enable_request_log(sf)
    respx.post("http://rl9.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=CANNED_RESPONSE)
    )
    client = TestClient(app)
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "provider:p:gpt-4o",
            "messages": [{"role": "user", "content": "A" * 20000}],
        },
    )
    assert resp.status_code == 200
    with sf() as session:
        row = session.query(RequestLog).one()
    # ~8KB cap + a short marker suffix.
    assert len(row.request) <= gateway_router.REQUEST_LOG_MAX_CHARS + 64
    assert "[truncated" in row.request


class _FakeClock:
    """Stand-in for the ``time`` module inside gateway.router."""

    def __init__(self, values):
        self._values = list(values)
        self._i = 0

    def monotonic(self):
        value = self._values[min(self._i, len(self._values) - 1)]
        self._i += 1
        return value


@respx.mock
def test_request_log_duration_ms_measured(sf, monkeypatch):
    _seed_provider(sf, "p", base_url="http://rl10.test/v1")
    _enable_request_log(sf)
    respx.post("http://rl10.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=CANNED_RESPONSE)
    )
    # t0 = 0.0s, record-time = 0.1234s -> 123 ms (int-truncated).
    monkeypatch.setattr(gateway_router, "time", _FakeClock([0.0, 0.1234]))
    client = TestClient(app)
    assert _post_completion(client, model="provider:p:gpt-4o").status_code == 200
    with sf() as session:
        row = session.query(RequestLog).one()
    assert row.duration_ms == 123


@respx.mock
def test_request_log_fail_open_never_breaks_response(sf, monkeypatch):
    _seed_provider(sf, "p", base_url="http://rl11.test/v1")
    _enable_request_log(sf)
    respx.post("http://rl11.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=CANNED_RESPONSE)
    )

    class _Boom:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("request-log insert exploded")

    monkeypatch.setattr(gateway_router, "RequestLog", _Boom)
    client = TestClient(app)
    resp = _post_completion(client, model="provider:p:gpt-4o")
    assert resp.status_code == 200  # client response unaffected
    with sf() as session:
        assert session.query(RequestLog).count() == 0
        errors = (
            session.query(LogEntry)
            .filter_by(severity="error", source="backend.gateway.router")
            .all()
        )
    # R12: the swallowed failure is logged to LogEntry (no silent except).
    assert any("request-log recording failed" in e.message for e in errors)

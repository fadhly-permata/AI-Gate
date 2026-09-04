"""SSE streaming tests for the OpenAI-compatible gateway (``stream:true``).

Covers the streaming proxy added for agentic CLIs (opencode / aider / claude):

* OpenAI-format provider + ``stream:true`` -> 200 ``text/event-stream`` with the
  upstream SSE frames forwarded verbatim (incl. ``data: [DONE]``);
* translated formats (anthropic / gemini) + ``stream:true`` -> 400
  ``streaming_unsupported_format`` (known limitation);
* combo + ``stream:true`` -> streams from the first OpenAI-format member;
* a UsageRecord is persisted AFTER the stream completes (final usage chunk);
* an upstream connect failure surfaces as a JSON error envelope (NOT a broken
  200 stream) because the router primes the first chunk before committing.

Upstream calls are mocked with **respx** (no network); the router's forwarding /
priming / usage-after-stream logic is additionally exercised with a fake async
generator (multi-chunk verbatim). Hermetic in-memory SQLite (StaticPool), same
pattern as ``test_gateway.py``.
"""

from __future__ import annotations

import json

import httpx
import respx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.combo_routing as combo_routing
import backend.combos_router as combos_router
import backend.config.db as db_mod
import backend.config.logs_router as logs_router
import backend.gateway.provider_adapter as provider_adapter
import backend.gateway.resolver as resolver
import backend.gateway.router as router
from backend.config.db import Base
from backend.models import (
    Combo,
    ComboMember,
    LogEntry,
    Provider,
    ProviderModel,
    UsageRecord,
)
from fastapi.testclient import TestClient

from backend.server import app

# A realistic OpenAI SSE body: two content deltas, a final usage chunk, [DONE].
SSE_BODY = (
    b'data: {"id":"c1","object":"chat.completion.chunk","choices":'
    b'[{"index":0,"delta":{"role":"assistant","content":"Hi"}}]}\n\n'
    b'data: {"id":"c1","object":"chat.completion.chunk","choices":'
    b'[{"index":0,"delta":{"content":" there"}}]}\n\n'
    b'data: {"id":"c1","object":"chat.completion.chunk","choices":[],'
    b'"usage":{"prompt_tokens":10,"completion_tokens":4,"total_tokens":14}}\n\n'
    b'data: [DONE]\n\n'
)


def _make_sessionmaker() -> sessionmaker:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _seed(sf: sessionmaker) -> None:
    """Seed an openai provider (+model), an anthropic provider (+model), and a
    fallback combo whose single member is the OpenAI provider."""
    with sf() as session:
        provider = Provider(
            name="test",
            type="openai-compatible",
            base_url="http://provider.test/v1",
            api_key="sk-plain",
            enabled=True,
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
        claude = Provider(
            name="claude",
            type="anthropic",
            base_url="http://claude.test",
            api_key="sk-x",
            enabled=True,
        )
        session.add(claude)
        session.flush()
        session.add(
            ProviderModel(
                provider_id=claude.id,
                model_id="claude-3-5-sonnet",
                model_name="Claude 3.5 Sonnet",
                capabilities="chat",
            )
        )
        combo = Combo(name="default", strategy="fallback", enabled=True)
        session.add(combo)
        session.flush()
        session.add(
            ComboMember(
                combo_id=combo.id,
                provider_id=provider.id,
                provider_model="gpt-4o",
                priority=0,
                weight=1.0,
            )
        )
        session.commit()


def _patch_db(monkeypatch, sf: sessionmaker) -> None:
    monkeypatch.setattr(db_mod, "SessionLocal", sf)
    monkeypatch.setattr(resolver, "SessionLocal", sf)
    monkeypatch.setattr(router, "SessionLocal", sf)
    monkeypatch.setattr(logs_router, "SessionLocal", sf)
    monkeypatch.setattr(combo_routing, "SessionLocal", sf)
    monkeypatch.setattr(combos_router, "SessionLocal", sf)


def _client(monkeypatch) -> TestClient:
    sf = _make_sessionmaker()
    _seed(sf)
    _patch_db(monkeypatch, sf)
    return TestClient(app)


# --------------------------------------------------------------------------- #
# OpenAI-format streaming via respx (real adapter path)
# --------------------------------------------------------------------------- #


@respx.mock
def test_stream_openai_returns_sse_verbatim(monkeypatch) -> None:
    client = _client(monkeypatch)
    route = respx.post("http://provider.test/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, content=SSE_BODY, headers={"Content-Type": "text/event-stream"}
        )
    )
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "provider:test:gpt-4o",
            "messages": [{"role": "user", "content": "halo"}],
            "stream": True,
        },
    )
    assert resp.status_code == 200
    assert route.called
    assert resp.headers["content-type"].startswith("text/event-stream")
    # SSE frames forwarded verbatim, ending with the upstream's [DONE].
    assert resp.content == SSE_BODY
    assert "data: [DONE]" in resp.text
    assert resp.text.count("data:") >= 3
    # The provider:-prefixed ref must NOT reach upstream; the real id must.
    sent = json.loads(route.calls.last.request.content)
    assert sent["model"] == "gpt-4o"
    assert sent["stream"] is True


@respx.mock
def test_stream_openai_sets_sse_headers(monkeypatch) -> None:
    client = _client(monkeypatch)
    respx.post("http://provider.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, content=SSE_BODY)
    )
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "provider:test:gpt-4o",
            "messages": [{"role": "user", "content": "halo"}],
            "stream": True,
        },
    )
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "no-cache"
    assert resp.headers["x-accel-buffering"] == "no"


@respx.mock
def test_stream_combo_openai(monkeypatch) -> None:
    """A combo streams from its first OpenAI-format member (B.AI-style)."""
    client = _client(monkeypatch)
    route = respx.post("http://provider.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, content=SSE_BODY)
    )
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "combo:default",
            "messages": [{"role": "user", "content": "halo"}],
            "stream": True,
        },
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert resp.content == SSE_BODY
    assert route.called
    sent = json.loads(route.calls.last.request.content)
    assert sent["model"] == "gpt-4o"
    assert sent["stream"] is True


# --------------------------------------------------------------------------- #
# Translated formats + streaming -> 400 (known limitation)
# --------------------------------------------------------------------------- #


def test_stream_anthropic_returns_400(monkeypatch) -> None:
    client = _client(monkeypatch)
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "provider:claude:claude-3-5-sonnet",
            "messages": [{"role": "user", "content": "halo"}],
            "stream": True,
        },
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["type"] == "invalid_request_error"
    assert body["error"]["code"] == "streaming_unsupported_format"
    # R12: the rejection must land in LogEntry (warning).
    with router.SessionLocal() as session:
        warns = (
            session.query(LogEntry)
            .filter_by(severity="warning", source="backend.gateway.router")
            .all()
        )
    assert any("translated format" in w.message for w in warns)


def test_stream_gemini_returns_400(monkeypatch) -> None:
    sf = _make_sessionmaker()
    _seed(sf)
    with sf() as session:
        gem = Provider(
            name="g",
            type="gemini",
            base_url="http://gemini.test",
            api_key="k",
            enabled=True,
        )
        session.add(gem)
        session.flush()
        session.add(
            ProviderModel(
                provider_id=gem.id,
                model_id="gemini-2.0-flash",
                model_name="Gemini",
                capabilities="chat",
            )
        )
        session.commit()
    _patch_db(monkeypatch, sf)
    client = TestClient(app)
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "provider:g:gemini-2.0-flash",
            "messages": [{"role": "user", "content": "halo"}],
            "stream": True,
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "streaming_unsupported_format"


# --------------------------------------------------------------------------- #
# Usage-after-stream + verbatim multi-chunk forwarding (fake adapter generator)
# --------------------------------------------------------------------------- #


def test_stream_forwards_multiple_chunks_verbatim(monkeypatch) -> None:
    """Router forwards every upstream chunk verbatim (not just the first)."""
    client = _client(monkeypatch)
    chunks = [
        b'data: {"choices":[{"delta":{"content":"A"}}]}\n\n',
        b'data: {"choices":[{"delta":{"content":"B"}}]}\n\n',
        b"data: [DONE]\n\n",
    ]

    async def _fake_stream(_target, _payload, _proxy=None):
        for c in chunks:
            yield c

    monkeypatch.setattr(provider_adapter, "chat_completion_stream", _fake_stream)
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "provider:test:gpt-4o",
            "messages": [{"role": "user", "content": "halo"}],
            "stream": True,
        },
    )
    assert resp.status_code == 200
    assert resp.content == b"".join(chunks)


def test_stream_records_usage_after_completion(monkeypatch) -> None:
    """A UsageRecord is persisted after the stream, parsed from the usage chunk."""
    client = _client(monkeypatch)

    async def _fake_stream(_target, _payload, _proxy=None):
        yield b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n'
        yield (
            b'data: {"choices":[],"usage":{"prompt_tokens":10,'
            b'"completion_tokens":4,"total_tokens":14}}\n\n'
        )
        yield b"data: [DONE]\n\n"

    monkeypatch.setattr(provider_adapter, "chat_completion_stream", _fake_stream)
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "provider:test:gpt-4o",
            "messages": [{"role": "user", "content": "halo"}],
            "stream": True,
        },
    )
    assert resp.status_code == 200
    assert resp.content.endswith(b"data: [DONE]\n\n")
    with router.SessionLocal() as session:
        rows = session.query(UsageRecord).all()
    assert len(rows) == 1
    assert rows[0].tokens_in == 10
    assert rows[0].tokens_out == 4
    assert rows[0].model == "gpt-4o"


def test_stream_no_usage_chunk_records_zero(monkeypatch) -> None:
    """A completed stream without a usage chunk still records 0/0 (fail-open)."""
    client = _client(monkeypatch)

    async def _fake_stream(_target, _payload, _proxy=None):
        yield b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n'
        yield b"data: [DONE]\n\n"

    monkeypatch.setattr(provider_adapter, "chat_completion_stream", _fake_stream)
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "provider:test:gpt-4o",
            "messages": [{"role": "user", "content": "halo"}],
            "stream": True,
        },
    )
    assert resp.status_code == 200
    with router.SessionLocal() as session:
        rows = session.query(UsageRecord).all()
    assert len(rows) == 1
    assert rows[0].tokens_in == 0
    assert rows[0].tokens_out == 0


# --------------------------------------------------------------------------- #
# Error mapping: upstream failure during priming -> JSON envelope (not 200 SSE)
# --------------------------------------------------------------------------- #


@respx.mock
def test_stream_connect_error_maps_to_json_envelope(monkeypatch) -> None:
    client = _client(monkeypatch)
    respx.post("http://provider.test/v1/chat/completions").mock(
        side_effect=httpx.ConnectError("no route")
    )
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "provider:test:gpt-4o",
            "messages": [{"role": "user", "content": "halo"}],
            "stream": True,
        },
    )
    # Priming raised before the 200 SSE was committed -> OpenAI error envelope.
    assert resp.status_code == 503
    assert "text/event-stream" not in resp.headers.get("content-type", "")
    body = resp.json()
    assert body["error"]["type"] == "upstream_error"
    assert body["error"]["code"] == "proxy_503"


@respx.mock
def test_stream_upstream_5xx_maps_to_envelope(monkeypatch) -> None:
    client = _client(monkeypatch)
    respx.post("http://provider.test/v1/chat/completions").mock(
        return_value=httpx.Response(502, content=b"bad gateway")
    )
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "provider:test:gpt-4o",
            "messages": [{"role": "user", "content": "halo"}],
            "stream": True,
        },
    )
    assert resp.status_code == 502
    body = resp.json()
    assert body["error"]["code"] == "upstream_5xx"


# --------------------------------------------------------------------------- #
# Non-streaming path unchanged (stream absent / false) — sanity guard
# --------------------------------------------------------------------------- #


@respx.mock
def test_nonstream_still_returns_json(monkeypatch) -> None:
    client = _client(monkeypatch)
    canned = {
        "id": "x",
        "object": "chat.completion",
        "model": "gpt-4o",
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
    respx.post("http://provider.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=canned)
    )
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "provider:test:gpt-4o",
            "messages": [{"role": "user", "content": "halo"}],
        },
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json()["choices"][0]["message"]["content"] == "hi"

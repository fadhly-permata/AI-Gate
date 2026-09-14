"""Inbound Anthropic ``POST /v1/messages`` SSE streaming (Tahap 2 / B7).

Two layers of coverage:

* **Unit** — the pure OpenAI-chunk -> Anthropic-SSE encoder
  :func:`backend.gateway.translator.openai_chunk_stream_to_anthropic_events`
  (text + tool_use ``input_json_delta`` sequences, stop_reason + usage mapping),
  the ``allow_stream`` switch on
  :func:`backend.gateway.translator.anthropic_messages_request_to_openai_chat`
  (refuse when False / set ``stream``+``stream_options`` when True), and the
  Anthropic error-envelope rendering for an :class:`UpstreamError`.
* **G3 isolated integration** — an in-process ``TestClient`` (NO port bound) over
  a hermetic in-memory ``StaticPool`` SQLite DB (``AIGATE_DB_PATH`` redirected by
  ``conftest``) with **respx** mocking the OpenAI upstream. Asserts the full
  Anthropic SSE event sequence, ``content-type: text/event-stream``, ``stop_reason``
  + ``usage`` in ``message_delta``, the rewritten upstream request (``stream:true``
  + real model id), the translated-format 400, the pre-first-byte JSON error
  (priming), the mid-stream ``event: error`` frame, and the UsageRecord written
  after the stream.

``:8080`` (the live user app) is never touched.
"""

from __future__ import annotations

import json

import httpx
import pytest
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
import backend.gateway.translator as translator
from backend.config.db import Base
from backend.gateway.errors import GatewayError, UpstreamError
from backend.models import Combo, ComboMember, Provider, ProviderModel, UsageRecord
from fastapi.testclient import TestClient

from backend.server import app


# --------------------------------------------------------------------------- #
# Hermetic harness (same pattern as tests/backend/test_gateway_stream.py)
# --------------------------------------------------------------------------- #


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
    """Seed an openai provider (+gpt-4o), an anthropic provider (+model) and a
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


def _parse_events(text: str):
    """Parse an Anthropic SSE body into ``[(event_type, data_dict), ...]``."""
    events = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        etype = None
        data = None
        for line in block.splitlines():
            if line.startswith("event:"):
                etype = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data = json.loads(line[len("data:"):].strip())
        if etype is not None:
            events.append((etype, data))
    return events


# --------------------------------------------------------------------------- #
# Unit: openai_chunk_stream_to_anthropic_events (text sequence)
# --------------------------------------------------------------------------- #


def test_encoder_text_event_sequence():
    chunks = [
        {"id": "c1", "object": "chat.completion.chunk", "choices": [
            {"index": 0, "delta": {"role": "assistant", "content": ""},
             "finish_reason": None}]},
        {"id": "c1", "object": "chat.completion.chunk", "choices": [
            {"index": 0, "delta": {"content": "Hi"}, "finish_reason": None}]},
        {"id": "c1", "object": "chat.completion.chunk", "choices": [
            {"index": 0, "delta": {"content": " there"}, "finish_reason": None}]},
        {"id": "c1", "object": "chat.completion.chunk", "choices": [
            {"index": 0, "delta": {}, "finish_reason": "stop"}]},
        {"id": "c1", "object": "chat.completion.chunk", "choices": [],
         "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15}},
    ]
    body = "".join(
        translator.openai_chunk_stream_to_anthropic_events(chunks, "claude-sonnet-4-5")
    )
    events = _parse_events(body)
    types = [e[0] for e in events]
    assert types == [
        "message_start",
        "content_block_start",
        "content_block_delta",
        "content_block_delta",
        "content_block_stop",
        "message_delta",
        "message_stop",
    ]
    msg_start = events[0][1]["message"]
    assert msg_start["type"] == "message"
    assert msg_start["role"] == "assistant"
    assert msg_start["model"] == "claude-sonnet-4-5"  # echoes request ref
    assert msg_start["content"] == []
    assert msg_start["usage"] == {"input_tokens": 0, "output_tokens": 0}
    texts = [e[1]["delta"]["text"] for e in events if e[0] == "content_block_delta"]
    assert texts == ["Hi", " there"]
    md = next(d for et, d in events if et == "message_delta")
    assert md["delta"]["stop_reason"] == "end_turn"  # _openai_finish_to_anthropic('stop')
    assert md["usage"] == {"input_tokens": 12, "output_tokens": 3}


def test_encoder_tool_use_input_json_delta():
    chunks = [
        {"id": "c1", "choices": [{"index": 0,
            "delta": {"role": "assistant", "content": ""}, "finish_reason": None}]},
        {"id": "c1", "choices": [{"index": 0, "delta": {"tool_calls": [
            {"index": 0, "id": "call_1",
             "function": {"name": "bash", "arguments": ""}}]},
            "finish_reason": None}]},
        {"id": "c1", "choices": [{"index": 0, "delta": {"tool_calls": [
            {"index": 0, "function": {"arguments": '{"cmd":'}}]}},
        ]},
        {"id": "c1", "choices": [{"index": 0, "delta": {"tool_calls": [
            {"index": 0, "function": {"arguments": '"ls"'}}]}},
        ]},
        {"id": "c1", "choices": [{"index": 0, "delta": {"tool_calls": [
            {"index": 0, "function": {"arguments": '}'}}]}},
        ]},
        {"id": "c1", "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]},
        {"id": "c1", "choices": [],
         "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7}},
    ]
    body = "".join(
        translator.openai_chunk_stream_to_anthropic_events(chunks, "claude-sonnet-4-5")
    )
    events = _parse_events(body)
    start = next(d for et, d in events if et == "content_block_start")
    assert start["content_block"]["type"] == "tool_use"
    assert start["content_block"]["id"] == "call_1"
    assert start["content_block"]["name"] == "bash"
    assert start["content_block"]["input"] == {}
    # No phantom text block for a tools-only stream.
    assert "content_block_delta" in [et for et, _ in events]
    partials = [
        d["delta"]["partial_json"]
        for et, d in events
        if et == "content_block_delta" and d["delta"]["type"] == "input_json_delta"
    ]
    # OpenAI streams compact partial JSON; concatenation must remain valid JSON.
    assert json.loads("".join(partials)) == {"cmd": "ls"}
    md = next(d for et, d in events if et == "message_delta")
    assert md["delta"]["stop_reason"] == "tool_use"  # finish tool_calls -> tool_use
    assert md["usage"] == {"input_tokens": 5, "output_tokens": 2}
    assert events[-1][0] == "message_stop"


def test_encoder_no_usage_chunk_yields_zero_usage():
    chunks = [
        {"id": "c1", "choices": [
            {"index": 0, "delta": {"content": "hi"}, "finish_reason": "stop"}]},
    ]
    body = "".join(translator.openai_chunk_stream_to_anthropic_events(chunks, "m"))
    events = _parse_events(body)
    md = next(d for et, d in events if et == "message_delta")
    assert md["usage"] == {"input_tokens": 0, "output_tokens": 0}
    assert md["delta"]["stop_reason"] == "end_turn"
    assert events[-1][0] == "message_stop"


def test_encoder_finish_reason_maps_via_openai_finish_to_anthropic():
    for finish, expected in [
        ("stop", "end_turn"),
        ("tool_calls", "tool_use"),
        ("length", "max_tokens"),
        ("content_filter", "stop"),
    ]:
        chunks = [
            {"id": "c", "choices": [
                {"index": 0, "delta": {"content": "x"}, "finish_reason": finish}]},
        ]
        body = "".join(translator.openai_chunk_stream_to_anthropic_events(chunks, "m"))
        md = next(d for et, d in _parse_events(body) if et == "message_delta")
        assert md["delta"]["stop_reason"] == expected


# --------------------------------------------------------------------------- #
# Unit: allow_stream switch on the request translator
# --------------------------------------------------------------------------- #


def test_allow_stream_false_refuses_stream():
    payload = {
        "model": "claude-sonnet-4-5",
        "messages": [{"role": "user", "content": "hi"}],
        "stream": True,
    }
    with pytest.raises(GatewayError) as exc:
        translator.anthropic_messages_request_to_openai_chat(payload)  # default False
    assert exc.value.status_code == 400
    assert exc.value.envelope["error"]["code"] == (
        translator.ANTHROPIC_STREAMING_UNSUPPORTED_CODE
    )


def test_allow_stream_true_sets_stream_and_include_usage():
    payload = {
        "model": "claude-sonnet-4-5",
        "max_tokens": 32,
        "messages": [{"role": "user", "content": "hi"}],
        "stream": True,
    }
    chat = translator.anthropic_messages_request_to_openai_chat(
        payload, allow_stream=True
    )
    assert chat["stream"] is True
    assert chat["stream_options"] == {"include_usage": True}


def test_allow_stream_true_without_stream_keeps_stage1_shape():
    payload = {
        "model": "claude-sonnet-4-5",
        "max_tokens": 32,
        "messages": [{"role": "user", "content": "hi"}],
    }
    chat = translator.anthropic_messages_request_to_openai_chat(
        payload, allow_stream=True
    )
    assert "stream" not in chat
    assert "stream_options" not in chat


def test_allow_stream_true_still_refuses_thinking():
    payload = {
        "model": "claude-sonnet-4-5",
        "messages": [{"role": "user", "content": "hi"}],
        "stream": True,
        "thinking": {"type": "enabled", "enabled": True},
    }
    with pytest.raises(GatewayError) as exc:
        translator.anthropic_messages_request_to_openai_chat(
            payload, allow_stream=True
        )
    assert exc.value.envelope["error"]["code"] == (
        translator.ANTHROPIC_UNSUPPORTED_FIELD_CODE
    )


# --------------------------------------------------------------------------- #
# Unit: UpstreamError -> Anthropic error envelope
# --------------------------------------------------------------------------- #


def test_upstream_error_maps_to_anthropic_envelope():
    envelope = {
        "error": {
            "message": "rate limited",
            "type": "upstream_error",
            "code": "upstream_429",
        }
    }
    exc = UpstreamError(429, envelope)
    resp = router._anthropic_error_response(exc)
    body = json.loads(resp.body)
    assert resp.status_code == 429
    assert body == {
        "type": "error",
        "error": {
            "message": "rate limited",
            "type": "upstream_error",
            "code": "upstream_429",
        },
    }


# --------------------------------------------------------------------------- #
# G3 isolated integration (in-process TestClient, respx, no port bound)
# --------------------------------------------------------------------------- #

ANTHROPIC_UPSTREAM_SSE = (
    b'data: {"id":"c1","object":"chat.completion.chunk","choices":'
    b'[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":null}]}\n\n'
    b'data: {"id":"c1","object":"chat.completion.chunk","choices":'
    b'[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}\n\n'
    b'data: {"id":"c1","object":"chat.completion.chunk","choices":'
    b'[{"index":0,"delta":{"content":" world"},"finish_reason":null}]}\n\n'
    b'data: {"id":"c1","object":"chat.completion.chunk","choices":'
    b'[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n'
    b'data: {"id":"c1","object":"chat.completion.chunk","choices":[],'
    b'"usage":{"prompt_tokens":12,"completion_tokens":3,"total_tokens":15}}\n\n'
    b'data: [DONE]\n\n'
)

STREAM_BODY = {
    "model": "provider:test:gpt-4o",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "hi"}],
    "stream": True,
}


@respx.mock
def test_messages_stream_openai_returns_full_anthropic_sse(monkeypatch) -> None:
    client = _client(monkeypatch)
    route = respx.post("http://provider.test/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            content=ANTHROPIC_UPSTREAM_SSE,
            headers={"Content-Type": "text/event-stream"},
        )
    )
    resp = client.post("/v1/messages", json=STREAM_BODY)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert resp.headers["cache-control"] == "no-cache"
    assert resp.headers["x-accel-buffering"] == "no"

    events = _parse_events(resp.text)
    types = [e[0] for e in events]
    assert types == [
        "message_start",
        "content_block_start",
        "content_block_delta",
        "content_block_delta",
        "content_block_stop",
        "message_delta",
        "message_stop",
    ]
    assert events[0][1]["message"]["model"] == "provider:test:gpt-4o"
    md = next(d for et, d in events if et == "message_delta")
    assert md["delta"]["stop_reason"] == "end_turn"
    assert md["usage"] == {"input_tokens": 12, "output_tokens": 3}
    # [DONE] never reaches the Anthropic client.
    assert "[DONE]" not in resp.text

    # The upstream was asked for an OpenAI stream with the REAL model id.
    assert route.called
    sent = json.loads(route.calls.last.request.content)
    assert sent["model"] == "gpt-4o"
    assert sent["stream"] is True
    assert sent["stream_options"] == {"include_usage": True}


@respx.mock
def test_messages_stream_records_usage_after_completion(monkeypatch) -> None:
    client = _client(monkeypatch)
    respx.post("http://provider.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, content=ANTHROPIC_UPSTREAM_SSE)
    )
    resp = client.post("/v1/messages", json=STREAM_BODY)
    assert resp.status_code == 200
    with router.SessionLocal() as session:
        rows = session.query(UsageRecord).all()
    assert len(rows) == 1
    assert rows[0].tokens_in == 12
    assert rows[0].tokens_out == 3
    assert rows[0].model == "gpt-4o"


def test_messages_stream_combo_openai_member(monkeypatch) -> None:
    """A combo streams from its first OpenAI-format member (Anthropic-encoded)."""
    client = _client(monkeypatch)

    async def _fake(_target, _payload, _proxy=None):
        yield ANTHROPIC_UPSTREAM_SSE

    monkeypatch.setattr(provider_adapter, "chat_completion_stream", _fake)
    resp = client.post(
        "/v1/messages",
        json={**STREAM_BODY, "model": "combo:default"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = _parse_events(resp.text)
    assert events[0][0] == "message_start"
    assert events[-1][0] == "message_stop"


@respx.mock
def test_messages_stream_translated_upstream_returns_400(monkeypatch) -> None:
    """Tahap 2: an anthropic (translated) upstream still rejects stream:true."""
    client = _client(monkeypatch)
    resp = client.post(
        "/v1/messages",
        json={
            **STREAM_BODY,
            "model": "provider:claude:claude-3-5-sonnet",
        },
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["type"] == "error"
    assert body["error"]["code"] == "streaming_unsupported_format"


@respx.mock
def test_messages_stream_connect_error_is_json_envelope(monkeypatch) -> None:
    """Priming surfaces a pre-first-byte failure as Anthropic JSON, not broken SSE."""
    client = _client(monkeypatch)
    respx.post("http://provider.test/v1/chat/completions").mock(
        side_effect=httpx.ConnectError("no route")
    )
    resp = client.post("/v1/messages", json=STREAM_BODY)
    assert resp.status_code == 503
    assert "text/event-stream" not in resp.headers.get("content-type", "")
    body = resp.json()
    assert body["type"] == "error"
    assert body["error"]["type"] == "upstream_error"
    assert body["error"]["code"] == "proxy_503"


@respx.mock
def test_messages_stream_upstream_5xx_is_json_envelope(monkeypatch) -> None:
    client = _client(monkeypatch)
    respx.post("http://provider.test/v1/chat/completions").mock(
        return_value=httpx.Response(502, content=b"bad gateway")
    )
    resp = client.post("/v1/messages", json=STREAM_BODY)
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "upstream_5xx"


def test_messages_stream_midstream_failure_emits_error_frame(monkeypatch) -> None:
    """A transport failure AFTER the stream starts emits ONE Anthropic error frame."""
    client = _client(monkeypatch)

    async def _fake(_target, _payload, _proxy=None):
        yield (
            b'data: {"id":"c1","choices":[{"index":0,'
            b'"delta":{"content":"hi"},"finish_reason":null}]}\n\n'
        )
        yield (
            b'data: {"id":"c1","choices":[{"index":0,'
            b'"delta":{"content":"!"},"finish_reason":null}]}\n\n'
        )
        raise UpstreamError(
            502,
            {
                "error": {
                    "message": "upstream stream interrupted",
                    "type": "upstream_error",
                    "code": "upstream_stream_interrupted",
                }
            },
        )

    monkeypatch.setattr(provider_adapter, "chat_completion_stream", _fake)
    resp = client.post("/v1/messages", json=STREAM_BODY)
    assert resp.status_code == 200
    events = _parse_events(resp.text)
    # Content delivered up to the failure, then exactly one error frame, no stop.
    types = [e[0] for e in events]
    assert "content_block_delta" in types
    assert types.count("error") == 1
    assert types[-1] == "error"
    assert events[-1][1] == {
        "type": "error",
        "error": {
            "message": "upstream stream interrupted",
            "type": "upstream_error",
            "code": "upstream_stream_interrupted",
        },
    }
    assert "message_stop" not in types  # truncated by the error, not silently closed


# --------------------------------------------------------------------------- #
# Regression guard: Stage-1 non-streaming path untouched (no stream flag)
# --------------------------------------------------------------------------- #


def test_messages_non_stream_still_json(monkeypatch) -> None:
    client = _client(monkeypatch)
    canned = {
        "id": "chatcmpl-t",
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

    async def _fake(_target, _payload, _proxy=None) -> dict:
        return dict(canned)

    monkeypatch.setattr(provider_adapter, "chat_completion", _fake)
    resp = client.post(
        "/v1/messages",
        json={
            "model": "provider:test:gpt-4o",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    body = resp.json()
    assert body["type"] == "message"
    assert body["content"][0]["text"] == "hi there"
    assert body["stop_reason"] == "end_turn"

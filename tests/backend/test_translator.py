"""Tests for the Format Translation Engine (ADR-012, B5.3).

Pure-function tests for :mod:`backend.gateway.translator` plus one integration
test of :func:`backend.gateway.provider_adapter.chat_completion` against a
mocked Anthropic endpoint (via ``respx``).

DB-free except where logging is exercised: an in-memory ``SessionLocal`` is
patched so ``backend.log`` writes stay hermetic (ADR-011).
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.config.db as db_mod
import backend.gateway.provider_adapter as provider_adapter
import backend.gateway.translator as translator
from backend.config.db import Base
from backend.gateway.errors import UpstreamError
from backend.gateway.resolver import ResolvedTarget


@pytest.fixture(autouse=True)
def _in_memory_db(monkeypatch):
    """Route LogEntry writes to an in-memory SQLite so warnings stay hermetic."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    sf = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    monkeypatch.setattr(db_mod, "SessionLocal", sf)
    yield


# --- format_for_provider_type -----------------------------------------------


def test_format_alias_claude_to_anthropic():
    assert translator.format_for_provider_type("claude") == "anthropic"


def test_format_alias_ollama_to_openai():
    assert translator.format_for_provider_type("ollama") == "openai"


def test_format_unknown_defaults_openai():
    assert translator.format_for_provider_type("some-new-provider") == "openai"
    assert translator.format_for_provider_type("") == "openai"


def test_format_direct_mappings():
    assert translator.format_for_provider_type("gemini") == "gemini"
    assert translator.format_for_provider_type("anthropic") == "anthropic"
    assert translator.format_for_provider_type("vertex") == "openai"
    assert translator.format_for_provider_type("cursor") == "openai"
    assert translator.format_for_provider_type("kiro") == "openai"
    assert translator.format_for_provider_type("antigravity") == "openai"
    assert translator.format_for_provider_type("openrouter") == "openai"
    assert translator.format_for_provider_type("litellm") == "openai"
    assert translator.format_for_provider_type("openai-compatible") == "openai"


# --- OpenAI pass-through -----------------------------------------------------


def test_openai_request_passthrough_unchanged():
    payload = {"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]}
    req = translator.translate_request("openai", payload)
    assert req["url_path"] == "/chat/completions"
    assert req["headers_extra"] == {}
    assert req["body"] is payload  # verbatim


def test_openai_response_passthrough():
    raw = {"choices": [{"message": {"content": "x"}}]}
    assert translator.translate_response("openai", raw) is raw


# --- Anthropic request -------------------------------------------------------


def test_anthropic_request_extracts_system_and_path():
    payload = {
        "model": "claude-3-opus",
        "max_tokens": 1024,
        "messages": [
            {"role": "system", "content": "be brief"},
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
            {"role": "user", "content": "again"},
        ],
    }
    req = translator.translate_request("anthropic", payload)
    assert req["url_path"] == "/v1/messages"
    assert req["headers_extra"] == {"anthropic-version": "2023-06-01"}
    body = req["body"]
    assert body["model"] == "claude-3-opus"
    assert body["system"] == "be brief"
    assert body["max_tokens"] == 1024
    # system message must NOT appear in the messages array
    roles = [m["role"] for m in body["messages"]]
    assert "system" not in roles
    assert roles == ["user", "assistant", "user"]


def test_anthropic_request_injects_default_max_tokens_and_warns(caplog):
    payload = {
        "model": "claude-3-opus",
        "messages": [{"role": "user", "content": "hi"}],
    }
    req = translator.translate_request("anthropic", payload)
    # default injected
    assert req["body"]["max_tokens"] == translator._DEFAULT_MAX_TOKENS
    # a warning was logged to LogEntry (via backend.log) AND stdlib logger
    assert any("max_tokens" in rec.message for rec in caplog.records)


def test_anthropic_request_maps_tool_calls():
    payload = {
        "model": "claude-3-opus",
        "max_tokens": 100,
        "messages": [
            {
                "role": "assistant",
                "content": "let me call it",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": '{"city": "Paris"}',
                        },
                    }
                ],
            }
        ],
    }
    req = translator.translate_request("anthropic", payload)
    msg = req["body"]["messages"][0]
    assert msg["role"] == "assistant"
    blocks = msg["content"]
    assert any(b["type"] == "text" for b in blocks)
    tool_use = next(b for b in blocks if b["type"] == "tool_use")
    assert tool_use["id"] == "call_1"
    assert tool_use["name"] == "get_weather"
    assert tool_use["input"] == {"city": "Paris"}


# --- Anthropic response ------------------------------------------------------


def test_anthropic_response_translation():
    raw = {
        "id": "msg_1",
        "type": "message",
        "model": "claude-3-opus",
        "role": "assistant",
        "content": [
            {"type": "text", "text": "hello "},
            {"type": "text", "text": "world"},
        ],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }
    out = translator.translate_response("anthropic", raw)
    assert out["object"] == "chat.completion"
    assert out["model"] == "claude-3-opus"
    assert out["choices"][0]["message"]["role"] == "assistant"
    assert out["choices"][0]["message"]["content"] == "hello world"
    assert out["choices"][0]["finish_reason"] == "stop"
    assert out["usage"]["prompt_tokens"] == 10
    assert out["usage"]["completion_tokens"] == 5
    assert out["usage"]["total_tokens"] == 15


def test_anthropic_response_maps_tool_use_to_tool_calls():
    raw = {
        "id": "msg_2",
        "model": "claude-3-opus",
        "role": "assistant",
        "content": [
            {
                "type": "tool_use",
                "id": "tu_1",
                "name": "search",
                "input": {"q": "x"},
            }
        ],
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }
    out = translator.translate_response("anthropic", raw)
    msg = out["choices"][0]["message"]
    assert "tool_calls" in msg
    tc = msg["tool_calls"][0]
    assert tc["id"] == "tu_1"
    assert tc["function"]["name"] == "search"
    assert tc["function"]["arguments"] == '{"q": "x"}'
    assert out["choices"][0]["finish_reason"] == "tool_calls"


# --- Gemini request + response -----------------------------------------------


def test_gemini_request_translation():
    payload = {
        "model": "gemini-1.5-pro",
        "max_tokens": 256,
        "messages": [
            {"role": "system", "content": "sys prompt"},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ],
    }
    req = translator.translate_request("gemini", payload)
    assert req["url_path"] == "/v1beta/models/gemini-1.5-pro:generateContent"
    body = req["body"]
    assert body["systemInstruction"]["parts"][0]["text"] == "sys prompt"
    # system must not leak into contents
    assert all(c["role"] != "system" for c in body["contents"])
    assert body["contents"][0]["role"] == "user"
    assert body["contents"][0]["parts"][0]["text"] == "hi"
    assert body["contents"][1]["role"] == "model"
    assert body["generationConfig"]["maxOutputTokens"] == 256


def test_gemini_response_translation():
    raw = {
        "candidates": [
            {
                "content": {"parts": [{"text": "answer"}], "role": "model"},
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 7,
            "candidatesTokenCount": 3,
            "totalTokenCount": 10,
        },
        "model": "gemini-1.5-pro",
    }
    out = translator.translate_response("gemini", raw)
    assert out["choices"][0]["message"]["content"] == "answer"
    assert out["choices"][0]["finish_reason"] == "stop"
    assert out["usage"]["prompt_tokens"] == 7
    assert out["usage"]["completion_tokens"] == 3
    assert out["usage"]["total_tokens"] == 10


# --- translate_error ---------------------------------------------------------


def test_translate_error_openai_envelope_shape():
    env = translator.translate_error("anthropic", 400, {"error": {"message": "bad"}})
    assert "error" in env
    assert env["error"]["message"] == "bad"
    assert env["error"]["type"] == "upstream_error"
    assert env["error"]["code"] == "upstream_400"


def test_translate_error_anthropic_preserves_type():
    env = translator.translate_error(
        "anthropic",
        429,
        {"error": {"message": "rate", "type": "rate_limit_error"}},
    )
    assert env["error"]["message"] == "rate"
    assert env["error"]["type"] == "rate_limit_error"


# --- Integration: adapter with mocked Anthropic endpoint ---------------------


@respx.mock
@pytest.mark.asyncio
async def test_adapter_translates_anthropic_upstream():
    base_url = "https://api.anthropic.test"
    target = ResolvedTarget(
        base_url=base_url,
        api_key="sk-ant-plain",
        model_ref="provider:claude",
        upstream_model="claude-3-opus",
        format="anthropic",
    )
    anthropic_body = {
        "id": "msg_x",
        "type": "message",
        "model": "claude-3-opus",
        "role": "assistant",
        "content": [{"type": "text", "text": "translated reply"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 4, "output_tokens": 2},
    }
    route = respx.post(base_url + "/v1/messages").mock(
        return_value=httpx.Response(200, json=anthropic_body)
    )

    result = await provider_adapter.chat_completion(
        target,
        {"model": "provider:claude", "messages": [{"role": "user", "content": "hi"}]},
    )

    assert route.called
    sent = route.calls.last.request
    # Anthropic auth header path (x-api-key, no Authorization Bearer)
    assert sent.headers.get("x-api-key") == "sk-ant-plain"
    assert "Authorization" not in sent.headers
    assert sent.headers.get("anthropic-version") == "2023-06-01"
    sent_body = json.loads(sent.content)
    assert sent_body["model"] == "claude-3-opus"
    assert "system" not in sent_body  # no system message in request

    # Response is OpenAI-shaped
    assert result["object"] == "chat.completion"
    assert result["choices"][0]["message"]["content"] == "translated reply"
    assert result["usage"]["total_tokens"] == 6


@respx.mock
@pytest.mark.asyncio
async def test_adapter_anthropic_error_returns_openai_envelope():
    base_url = "https://api.anthropic.test"
    target = ResolvedTarget(
        base_url=base_url,
        api_key="sk-ant-plain",
        model_ref="provider:claude",
        upstream_model="claude-3-opus",
        format="anthropic",
    )
    respx.post(base_url + "/v1/messages").mock(
        return_value=httpx.Response(
            400,
            json={
                "error": {
                    "message": "invalid request",
                    "type": "invalid_request_error",
                }
            },
        )
    )

    with pytest.raises(UpstreamError) as excinfo:
        await provider_adapter.chat_completion(
            target,
            {"model": "provider:claude", "messages": [{"role": "user", "content": "hi"}]},
        )
    env = excinfo.value.envelope
    assert env["error"]["message"] == "invalid request"
    assert env["error"]["code"] == "upstream_400"

"""Targeted tests for the inbound Anthropic ``/v1/messages`` surface (Stage 1).

Pure-function tests for the translation shims in
:mod:`backend.gateway.translator` plus route-level tests of
``POST /v1/messages`` (non-streaming success, ``model_not_found``, streaming 400,
Anthropic-native ``x-api-key`` auth, tool passthrough) and the sibling routes
(``/v1/messages/count_tokens``, ``/api/event_logging/batch``).

DB-free except where logging/usage are exercised: an in-memory ``SessionLocal``
is patched so ``backend.log`` / usage writes stay hermetic (ADR-011).
"""

from __future__ import annotations

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
from backend.gateway.errors import GatewayError
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


# --------------------------------------------------------------------------- #
# Pure translator unit tests
# --------------------------------------------------------------------------- #


def test_anthropic_request_to_openai_basic():
    payload = {
        "model": "claude-sonnet-4-5",
        "max_tokens": 1024,
        "messages": [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ],
    }
    chat = translator.anthropic_messages_request_to_openai_chat(payload)
    assert chat["model"] == "claude-sonnet-4-5"
    assert chat["max_tokens"] == 1024
    # no system -> no leading system message
    assert chat["messages"][0]["role"] == "user"
    assert chat["messages"][1]["role"] == "assistant"


def test_anthropic_request_to_openai_system_string_and_blocks():
    payload = {
        "model": "claude-sonnet-4-5",
        "system": [{"type": "text", "text": "You are "}, {"type": "text", "text": "brief."}],
        "messages": [{"role": "user", "content": "hi"}],
    }
    chat = translator.anthropic_messages_request_to_openai_chat(payload)
    assert chat["messages"][0] == {"role": "system", "content": "You are brief."}
    assert chat["messages"][1]["role"] == "user"


def test_anthropic_request_to_openai_tool_use_blocks():
    payload = {
        "model": "claude-sonnet-4-5",
        "messages": [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "running"},
                    {
                        "type": "tool_use",
                        "id": "t1",
                        "name": "bash",
                        "input": {"cmd": "ls"},
                    },
                ],
            }
        ],
    }
    chat = translator.anthropic_messages_request_to_openai_chat(payload)
    msg = chat["messages"][0]
    assert msg["role"] == "assistant"
    assert msg["content"] == "running"
    tc = msg["tool_calls"][0]
    assert tc["id"] == "t1"
    assert tc["function"]["name"] == "bash"
    assert tc["function"]["arguments"] == '{"cmd": "ls"}'


def test_anthropic_request_to_openai_tool_result_blocks():
    payload = {
        "model": "claude-sonnet-4-5",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "t1", "content": "file1\nfile2"},
                ],
            }
        ],
    }
    chat = translator.anthropic_messages_request_to_openai_chat(payload)
    tool_msg = chat["messages"][0]
    assert tool_msg["role"] == "tool"
    assert tool_msg["tool_call_id"] == "t1"
    assert tool_msg["content"] == "file1\nfile2"


def test_anthropic_request_to_openai_forwards_tools_and_tool_choice():
    payload = {
        "model": "claude-sonnet-4-5",
        "messages": [{"role": "user", "content": "hi"}],
        "tools": [
            {
                "name": "bash",
                "description": "run a command",
                "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}},
            }
        ],
        "tool_choice": {"type": "tool", "name": "bash"},
    }
    chat = translator.anthropic_messages_request_to_openai_chat(payload)
    assert chat["tools"][0]["type"] == "function"
    assert chat["tools"][0]["function"]["name"] == "bash"
    assert chat["tools"][0]["function"]["parameters"] == {
        "type": "object",
        "properties": {"cmd": {"type": "string"}},
    }
    assert chat["tool_choice"] == {"type": "function", "function": {"name": "bash"}}


def test_anthropic_request_to_openai_stream_refused():
    payload = {
        "model": "claude-sonnet-4-5",
        "messages": [{"role": "user", "content": "hi"}],
        "stream": True,
    }
    with pytest.raises(GatewayError) as exc:
        translator.anthropic_messages_request_to_openai_chat(payload)
    assert exc.value.status_code == 400
    assert exc.value.envelope["error"]["code"] == translator.ANTHROPIC_STREAMING_UNSUPPORTED_CODE


def test_anthropic_request_to_openai_thinking_refused():
    payload = {
        "model": "claude-sonnet-4-5",
        "messages": [{"role": "user", "content": "hi"}],
        "thinking": {"enabled": True, "type": "enabled"},
    }
    with pytest.raises(GatewayError) as exc:
        translator.anthropic_messages_request_to_openai_chat(payload)
    assert exc.value.status_code == 400
    assert exc.value.envelope["error"]["code"] == translator.ANTHROPIC_UNSUPPORTED_FIELD_CODE


def test_anthropic_request_to_openai_injects_default_max_tokens():
    payload = {
        "model": "claude-sonnet-4-5",
        "messages": [{"role": "user", "content": "hi"}],
    }
    chat = translator.anthropic_messages_request_to_openai_chat(payload)
    assert chat["max_tokens"] == translator._DEFAULT_MAX_TOKENS


def test_openai_response_to_anthropic_messages_basic():
    chat = {
        "id": "chatcmpl-xyz",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "hello world"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    out = translator.openai_chat_response_to_anthropic_messages(chat, "claude-sonnet-4-5")
    assert out["type"] == "message"
    assert out["role"] == "assistant"
    assert out["model"] == "claude-sonnet-4-5"  # echoes request ref
    assert out["content"][0] == {"type": "text", "text": "hello world"}
    assert out["stop_reason"] == "end_turn"
    assert out["usage"] == {"input_tokens": 10, "output_tokens": 5}


def test_openai_response_to_anthropic_messages_tool_use():
    chat = {
        "id": "chatcmpl-tu",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "t2",
                            "type": "function",
                            "function": {"name": "bash", "arguments": '{"cmd": "pwd"}'},
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
    out = translator.openai_chat_response_to_anthropic_messages(chat, "claude-sonnet-4-5")
    block = out["content"][0]
    assert block["type"] == "tool_use"
    assert block["id"] == "t2"
    assert block["name"] == "bash"
    assert block["input"] == {"cmd": "pwd"}
    assert out["stop_reason"] == "tool_use"


def test_outbound_anthropic_forwards_tools_and_tool_choice():
    """``_translate_request_anthropic`` (outbound) must now pass OpenAI
    tools/tool_choice through to an anthropic upstream so the double-translation
    round-trip survives (design §3)."""
    openai_payload = {
        "model": "claude-sonnet-4-5",
        "messages": [{"role": "user", "content": "hi"}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "bash",
                    "description": "run",
                    "parameters": {"type": "object"},
                },
            }
        ],
        "tool_choice": {"type": "function", "function": {"name": "bash"}},
    }
    req = translator.translate_request("anthropic", openai_payload)
    body = req["body"]
    assert body["tools"][0]["name"] == "bash"
    assert body["tool_choice"] == {"type": "tool", "name": "bash"}


# --------------------------------------------------------------------------- #
# Route-level tests (in-memory DB + faked adapter)
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
    with sf() as session:
        provider = Provider(
            name="anthropic-fake",
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
                model_id="claude-sonnet-4-5",
                model_name="Claude Sonnet 4.5",
                capabilities="chat",
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


CANNED_RESPONSE = {
    "id": "chatcmpl-test",
    "object": "chat.completion",
    "model": "claude-sonnet-4-5",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "hi there"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
}


def _client_with_db(monkeypatch) -> TestClient:
    sf = _make_sessionmaker()
    _seed(sf)
    _patch_db(monkeypatch, sf)

    captured: dict = {}

    async def _fake(_target, _payload: dict, proxy_url=None) -> dict:
        captured["payload"] = _payload
        return dict(CANNED_RESPONSE)

    monkeypatch.setattr(provider_adapter, "chat_completion", _fake)
    client = TestClient(app)
    client._captured = captured  # type: ignore[attr-defined]
    return client


VALID_BODY = {
    "model": "claude-sonnet-4-5",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "hello"}],
}


def test_messages_non_streaming_success(monkeypatch) -> None:
    client = _client_with_db(monkeypatch)
    resp = client.post(
        "/v1/messages",
        json=VALID_BODY,
        headers={"x-api-key": "sk-aigate"},  # Anthropic-native header
    )
    assert resp.status_code == 200
    body = resp.json()
    # Anthropic Messages envelope
    assert body["type"] == "message"
    assert body["role"] == "assistant"
    assert body["content"][0] == {"type": "text", "text": "hi there"}
    assert body["stop_reason"] == "end_turn"
    assert body["usage"] == {"input_tokens": 1, "output_tokens": 2}
    # model echoes the REQUEST ref (not the upstream id)
    assert body["model"] == "claude-sonnet-4-5"


def test_messages_authorization_bearer_also_accepted(monkeypatch) -> None:
    client = _client_with_db(monkeypatch)
    resp = client.post(
        "/v1/messages",
        json=VALID_BODY,
        headers={"Authorization": "Bearer sk-aigate"},
    )
    assert resp.status_code == 200
    assert resp.json()["type"] == "message"


def test_messages_model_not_found(monkeypatch) -> None:
    client = _client_with_db(monkeypatch)
    resp = client.post(
        "/v1/messages",
        json={
            "model": "ghost-model",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )
    assert resp.status_code == 400
    body = resp.json()
    # Anthropic-shaped error envelope
    assert body["type"] == "error"
    assert body["error"]["code"] == "model_not_found"
    assert body["error"]["type"] == "invalid_request_error"


def test_messages_streaming_refused(monkeypatch) -> None:
    client = _client_with_db(monkeypatch)
    resp = client.post(
        "/v1/messages",
        json={**VALID_BODY, "stream": True},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["type"] == "error"
    assert body["error"]["code"] == translator.ANTHROPIC_STREAMING_UNSUPPORTED_CODE


def test_messages_missing_model(monkeypatch) -> None:
    client = _client_with_db(monkeypatch)
    resp = client.post(
        "/v1/messages",
        json={"messages": [{"role": "user", "content": "hello"}]},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["type"] == "error"
    assert body["error"]["code"] == translator.ANTHROPIC_MISSING_MODEL_CODE


def test_messages_tool_passthrough(monkeypatch) -> None:
    client = _client_with_db(monkeypatch)
    resp = client.post(
        "/v1/messages",
        json={
            **VALID_BODY,
            "tools": [
                {
                    "name": "bash",
                    "description": "run a command",
                    "input_schema": {"type": "object"},
                }
            ],
            "tool_choice": {"type": "auto"},
        },
    )
    assert resp.status_code == 200
    sent = client._captured["payload"]
    assert sent["tools"][0]["type"] == "function"
    assert sent["tools"][0]["function"]["name"] == "bash"
    assert sent["tool_choice"] == {"type": "auto"}


def test_messages_count_tokens_heuristic(monkeypatch) -> None:
    client = _client_with_db(monkeypatch)
    resp = client.post(
        "/v1/messages/count_tokens",
        json={
            "model": "claude-sonnet-4-5",
            "messages": [{"role": "user", "content": "hello world"}],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["output_tokens"] == 0
    # "hello world" -> 11 bytes -> 11 // 4 == 2
    assert body["input_tokens"] == 2


def test_event_logging_batch_stub(monkeypatch) -> None:
    client = _client_with_db(monkeypatch)
    resp = client.post("/api/event_logging/batch", json={"events": []})
    assert resp.status_code == 202
    assert resp.json() == {}


@respx.mock
def test_messages_real_adapter_anthropic_upstream(monkeypatch) -> None:
    """End-to-end (no faked adapter): a bare anthropic-flavoured model is resolved
    to an anthropic-type provider and the adapter double-translates (OpenAI ->
    Anthropic -> OpenAI). Verifies the full pipeline + envelope."""
    sf = _make_sessionmaker()
    with sf() as session:
        provider = Provider(
            name="claude",
            type="anthropic",
            base_url="http://claude.upstream",
            api_key="sk-ant-plain",
            enabled=True,
        )
        session.add(provider)
        session.flush()
        session.add(
            ProviderModel(
                provider_id=provider.id,
                model_id="claude-sonnet-4-5",
                model_name="Claude Sonnet 4.5",
                capabilities="chat",
            )
        )
        session.commit()
    _patch_db(monkeypatch, sf)
    client = TestClient(app)

    anthropic_body = {
        "id": "msg_up",
        "type": "message",
        "model": "claude-sonnet-4-5",
        "role": "assistant",
        "content": [{"type": "text", "text": "upstream reply"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 4, "output_tokens": 2},
    }
    route = respx.post("http://claude.upstream/v1/messages").mock(
        return_value=httpx.Response(200, json=anthropic_body)
    )

    resp = client.post("/v1/messages", json=VALID_BODY)
    assert resp.status_code == 200
    body = resp.json()
    assert body["content"][0]["text"] == "upstream reply"
    assert body["usage"] == {"input_tokens": 4, "output_tokens": 2}
    # The upstream must have been hit with the Anthropic wire format.
    assert route.called

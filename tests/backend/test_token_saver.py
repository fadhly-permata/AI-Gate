"""Tests for the Token Saver hooks (B5.4 / ADR-013).

Covers ``backend.gateway.token_saver`` directly (off / rtk / caveman /
ponytail / fail-open) plus wiring in the gateway router via the
``X-Aigate-Endpoint`` header. Hermetic, no on-disk DB.
"""

from __future__ import annotations

import copy

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.combo_routing as combo_routing
import backend.config.db as db_mod
import backend.gateway.provider_adapter as provider_adapter
import backend.gateway.resolver as resolver
import backend.gateway.router as gateway_router
import backend.gateway.token_saver as token_saver
from backend.config.db import Base
from backend.models import (
    Endpoint,
    EndpointBinding,
    Provider,
    ProviderModel,
)

from fastapi.testclient import TestClient

from backend.server import app


# --------------------------------------------------------------------------- #
# token_saver unit tests
# --------------------------------------------------------------------------- #
def _large_git_diff() -> str:
    # A big git diff body (well over the 200+100 truncation window).
    header = "diff --git a/foo.py b/foo.py\nindex 0000000..1111111 100644\n"
    lines = "\n".join(f"+line_{i} = {i}" for i in range(500))
    return header + lines + "\n" + "\n\n\n\n\n" + "git diff tail\n"


def test_off_returns_unchanged():
    payload = {"model": "x", "messages": [{"role": "user", "content": "hello"}]}
    result = token_saver.apply_token_saver("off", payload)
    assert result is payload  # exact same object returned


def test_rtk_compresses_tool_message():
    payload = {
        "model": "x",
        "messages": [
            {"role": "user", "content": "run the diff"},
            {"role": "tool", "content": _large_git_diff()},
            {"role": "assistant", "content": "normal reply, must stay intact"},
        ],
    }
    result = token_saver.apply_token_saver("rtk", payload)
    assert result is not payload  # a new payload object is produced
    msgs = result["messages"]
    # The tool message shrank and carries a truncation marker.
    tool_msg = next(m for m in msgs if m["role"] == "tool")
    assert "[...truncated" in tool_msg["content"]
    assert len(tool_msg["content"]) < len(_large_git_diff())
    # Normal / user conversation messages are untouched in text.
    assert msgs[0]["content"] == "run the diff"
    assert msgs[2]["content"] == "normal reply, must stay intact"
    # blank-run collapse happened (the 5 blank lines are now a single blank).
    assert "\n\n\n\n\n" not in tool_msg["content"]


def test_rtk_does_not_alter_normal_conversation():
    payload = {
        "model": "x",
        "messages": [{"role": "user", "content": "How are you today?"}],
    }
    result = token_saver.apply_token_saver("rtk", copy.deepcopy(payload))
    assert result["messages"][0]["content"] == "How are you today?"


def test_caveman_injects_system_message_and_preserves_existing():
    payload = {
        "model": "x",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "hi"},
        ],
    }
    result = token_saver.apply_token_saver("caveman", copy.deepcopy(payload))
    sys_msgs = [m for m in result["messages"] if m["role"] == "system"]
    assert len(sys_msgs) == 1
    assert "concise" in sys_msgs[0]["content"]
    assert "helpful assistant" in sys_msgs[0]["content"]  # preserved


def test_caveman_prepends_system_when_absent():
    payload = {
        "model": "x",
        "messages": [{"role": "user", "content": "hi"}],
    }
    result = token_saver.apply_token_saver("caveman", copy.deepcopy(payload))
    assert result["messages"][0]["role"] == "system"
    assert "concise" in result["messages"][0]["content"]


def test_ponytail_injects_system_message():
    payload = {
        "model": "x",
        "messages": [{"role": "user", "content": "hi"}],
    }
    result = token_saver.apply_token_saver("ponytail", copy.deepcopy(payload))
    sys_msgs = [m for m in result["messages"] if m["role"] == "system"]
    assert len(sys_msgs) == 1
    assert "minimal" in sys_msgs[0]["content"]


def test_fail_open_returns_original_on_exception(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise RuntimeError("transform exploded")

    monkeypatch.setattr(token_saver, "_transform_text", _boom)
    payload = {
        "model": "x",
        "messages": [{"role": "tool", "content": _large_git_diff()}],
    }
    result = token_saver.apply_token_saver("rtk", payload)
    # No exception propagates; original payload returned unchanged.
    assert result is payload


# --------------------------------------------------------------------------- #
# gateway router wiring test
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
        session.commit()


def _patch_db(monkeypatch, sf: sessionmaker) -> None:
    monkeypatch.setattr(db_mod, "SessionLocal", sf)
    monkeypatch.setattr(gateway_router, "SessionLocal", sf)
    monkeypatch.setattr(combo_routing, "SessionLocal", sf)
    monkeypatch.setattr(resolver, "SessionLocal", sf)


def test_endpoint_header_applies_caveman_hook(monkeypatch):
    sf = _make_sessionmaker()
    _seed(sf)
    with sf() as session:
        ep = Endpoint(name="ep1", token_saver="caveman")
        session.add(ep)
        session.flush()
        session.add(
            EndpointBinding(endpoint_id=ep.id, bind_type="provider", bind_id=1)
        )
        session.commit()

    _patch_db(monkeypatch, sf)
    captured: dict = {}

    async def _fake(_target, _payload, proxy_url=None):
        captured["payload"] = _payload
        return {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "model": "x",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "ok"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    monkeypatch.setattr(provider_adapter, "chat_completion", _fake)
    client = TestClient(app)
    resp = client.post(
        "/v1/chat/completions",
        headers={"X-Aigate-Endpoint": "ep1"},
        json={
            "model": "provider:test:gpt-4o",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )
    assert resp.status_code == 200
    assert "payload" in captured
    sys_msgs = [m for m in captured["payload"]["messages"] if m["role"] == "system"]
    assert len(sys_msgs) == 1
    assert "concise" in sys_msgs[0]["content"]


def test_endpoint_header_rtk_compresses_forwarded_payload(monkeypatch):
    sf = _make_sessionmaker()
    _seed(sf)
    with sf() as session:
        ep = Endpoint(name="ep2", token_saver="rtk")
        session.add(ep)
        session.flush()
        session.add(
            EndpointBinding(endpoint_id=ep.id, bind_type="provider", bind_id=1)
        )
        session.commit()

    _patch_db(monkeypatch, sf)
    captured: dict = {}

    async def _fake(_target, _payload, proxy_url=None):
        captured["payload"] = _payload
        return {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "model": "x",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "ok"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    monkeypatch.setattr(provider_adapter, "chat_completion", _fake)
    client = TestClient(app)
    resp = client.post(
        "/v1/chat/completions",
        headers={"X-Aigate-Endpoint": "ep2"},
        json={
            "model": "provider:test:gpt-4o",
            "messages": [
                {"role": "user", "content": "diff please"},
                {"role": "tool", "content": _large_git_diff()},
            ],
        },
    )
    assert resp.status_code == 200
    assert "payload" in captured
    tool_msg = next(
        m for m in captured["payload"]["messages"] if m["role"] == "tool"
    )
    assert "[...truncated" in tool_msg["content"]


def test_missing_endpoint_header_is_no_hook(monkeypatch):
    sf = _make_sessionmaker()
    _seed(sf)
    _patch_db(monkeypatch, sf)
    captured: dict = {}

    async def _fake(_target, _payload, proxy_url=None):
        captured["payload"] = _payload
        return {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "model": "x",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "ok"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    monkeypatch.setattr(provider_adapter, "chat_completion", _fake)
    client = TestClient(app)
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "provider:test:gpt-4o",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )
    assert resp.status_code == 200
    # No system injection when header absent.
    sys_msgs = [
        m for m in captured["payload"]["messages"] if m["role"] == "system"
    ]
    assert sys_msgs == []

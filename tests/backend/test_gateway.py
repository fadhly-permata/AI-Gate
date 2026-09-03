"""Gateway endpoint tests — no network.

The provider adapter is monkeypatched to a canned OpenAI-style response, and
the gateway's ``SessionLocal`` is redirected to an in-memory SQLite database
(reusing the in-memory pattern from ``test_models.py``) seeded with a
``Provider``, ``ProviderModel``, ``Combo`` and ``ComboMember``.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.gateway.provider_adapter as provider_adapter
import backend.gateway.resolver as resolver
import backend.gateway.router as router
from backend.config.db import Base
from backend.models import Combo, ComboMember, Provider, ProviderModel
from fastapi.testclient import TestClient

from backend.server import app

CANNED_RESPONSE = {
    "id": "chatcmpl-test",
    "object": "chat.completion",
    "model": "provider:test",
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
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _seed(session_factory: sessionmaker) -> None:
    with session_factory() as session:
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


async def _fake_chat_completion(_target, _payload: dict) -> dict:
    return CANNED_RESPONSE


def _client_with_db(monkeypatch) -> TestClient:
    sf = _make_sessionmaker()
    _seed(sf)
    monkeypatch.setattr(resolver, "SessionLocal", sf)
    monkeypatch.setattr(router, "SessionLocal", sf)
    monkeypatch.setattr(provider_adapter, "chat_completion", _fake_chat_completion)
    return TestClient(app)


def test_chat_completions_provider_ok(monkeypatch) -> None:
    client = _client_with_db(monkeypatch)
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "provider:test",
            "messages": [{"role": "user", "content": "halo"}],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["content"] == "hi there"
    assert body["usage"]["total_tokens"] == 3


def test_chat_completions_unknown_model_returns_envelope(monkeypatch) -> None:
    client = _client_with_db(monkeypatch)
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "provider:ghost",
            "messages": [{"role": "user", "content": "halo"}],
        },
    )
    assert resp.status_code == 400
    body = resp.json()
    assert "error" in body
    assert body["error"]["type"] == "invalid_request_error"
    assert body["error"]["code"] == "model_not_found"


def test_list_models_contains_provider_and_combo(monkeypatch) -> None:
    client = _client_with_db(monkeypatch)
    resp = client.get("/v1/models")
    assert resp.status_code == 200
    body = resp.json()
    assert body["object"] == "list"
    ids = {entry["id"] for entry in body["data"]}
    assert "provider:test:gpt-4o" in ids
    assert "combo:default" in ids


def test_streaming_rejected_with_envelope(monkeypatch) -> None:
    client = _client_with_db(monkeypatch)
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "provider:test",
            "messages": [{"role": "user", "content": "halo"}],
            "stream": True,
        },
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "streaming_not_supported"

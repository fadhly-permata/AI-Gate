"""Chat Playground backend tests (B8.B6.1 / PRD §2.9 / ERD §ChatSession,ChatMessage).

Exercises the ``/api/chat/sessions`` CRUD + the SSE ``/complete`` endpoint.

DB isolation: the conftest session fixture has already redirected ``AIGATE_DB_PATH``
to a throwaway temp file and run ``init_db()`` (which ``create_all``-s the new
``chat_sessions`` / ``chat_messages`` tables). We seed a provider there and mock
only the upstream stream adapter — the gateway resolver / token-saver / combo
routing / usage-logging pipeline is exercised for real (DRY: we REUSE
``run_chat_completion``, never a second LLM engine).

Client: the repo's ``TestClient`` fixture is broken in THIS environment by an
incompatible ``starlette 0.27 + httpx 0.28`` pair (``TypeError: Client.__init__()
got an unexpected keyword argument 'app'`` — see baseline run: 235 failed / 42
errors that are NOT our regression). ``httpx.ASGITransport`` is the supported
in-process ASGI driver for httpx 0.28 and is the faithful equivalent (same app,
no socket, no loopback to a live server). So we drive ``backend.server.app`` with
``httpx.AsyncClient(transport=ASGITransport(app=app))``.
"""

from __future__ import annotations

import httpx
import pytest  # noqa: F401  (fixtures use @pytest.fixture)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.config.db as db_mod
import backend.gateway.provider_adapter as provider_adapter
from backend.config.db import Base
from backend.models import ChatMessage, ChatSession, Provider, ProviderModel
from backend.server import app

MODEL_REF = "provider:pgw:gpt-4o"

# A realistic OpenAI SSE body: two content deltas, a final usage chunk, [DONE].
SSE_WITH_USAGE = (
    b'data: {"id":"c1","object":"chat.completion.chunk","choices":'
    b'[{"index":0,"delta":{"role":"assistant","content":"Hai"}}]}\n\n'
    b'data: {"id":"c1","object":"chat.completion.chunk","choices":'
    b'[{"index":0,"delta":{"content":" dunia"}}]}\n\n'
    b'data: {"id":"c1","object":"chat.completion.chunk","choices":[],'
    b'"usage":{"prompt_tokens":7,"completion_tokens":3,"total_tokens":10}}\n\n'
    b"data: [DONE]\n\n"
)

# Same but WITHOUT a usage frame -> assistant tokens must be persisted as None.
SSE_NO_USAGE = (
    b'data: {"id":"c2","object":"chat.completion.chunk","choices":'
    b'[{"index":0,"delta":{"role":"assistant","content":"Oke"}}]}\n\n'
    b'data: {"id":"c2","object":"chat.completion.chunk","choices":'
    b'[{"index":0,"delta":{"content":" siap"}}]}\n\n'
    b"data: [DONE]\n\n"
)


def _seed_provider() -> int:
    """Seed an OpenAI-format provider + model into the (temp) config DB."""
    with db_mod.SessionLocal() as session:
        provider = Provider(
            name="pgw",
            type="openai-compatible",
            base_url="http://pgw.test/v1",
            api_key="sk-plain",
            enabled=True,
        )
        session.add(provider)
        session.flush()
        session.add(
            ProviderModel(
                provider_id=provider.id, model_id="gpt-4o", model_name="GPT-4o"
            )
        )
        session.commit()
        return provider.id


@pytest.fixture
def client():
    """In-process ASGI client (no socket, no server loopback)."""
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


@pytest.fixture(autouse=True)
def _seed(monkeypatch):
    """Provide a seeded provider + mocked upstream SSE stream per test."""
    _seed_provider()

    async def _fake_stream(_target, _payload, _proxy=None):
        yield SSE_WITH_USAGE

    monkeypatch.setattr(provider_adapter, "chat_completion_stream", _fake_stream)
    yield
    # monkeypatch auto-undoes the patch; nothing else to clean (temp DB resets per session)


# --------------------------------------------------------------------------- #
# init_db idempotency for the two new tables
# --------------------------------------------------------------------------- #
def test_init_db_creates_chat_tables_idempotently():
    """``init_db()`` builds chat_sessions + chat_messages and is safe to re-run."""
    # Already run by conftest; run twice more to prove idempotency.
    db_mod.init_db()
    db_mod.init_db()
    from sqlalchemy import inspect

    tables = set(inspect(db_mod.get_engine()).get_table_names())
    assert "chat_sessions" in tables
    assert "chat_messages" in tables


# --------------------------------------------------------------------------- #
# Session CRUD
# --------------------------------------------------------------------------- #
async def test_create_and_list_sessions(client):
    r = await client.post(
        "/api/chat/sessions",
        json={"title": "Satu", "model": MODEL_REF, "system_prompt": "be brief", "temperature": 0.3},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["title"] == "Satu"
    assert body["model"] == MODEL_REF
    assert body["system_prompt"] == "be brief"
    assert body["temperature"] == 0.3
    sid = body["id"]
    assert isinstance(sid, int)

    # second session, then list newest-first
    await client.post("/api/chat/sessions", json={"title": "Dua", "model": MODEL_REF})
    r = await client.get("/api/chat/sessions")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) >= 2
    # updated_at desc -> "Dua" (created last) first
    assert data[0]["title"] == "Dua"
    assert {k for k in data[0]} == {
        "id", "title", "model", "provider_id", "combo_id", "updated_at"
    }


async def test_get_session_with_messages_chronological(client):
    sid = (await client.post("/api/chat/sessions", json={"title": "T", "model": MODEL_REF})).json()["id"]
    # add two turns directly via DB to verify ordering + shape in GET
    with db_mod.SessionLocal() as session:
        session.add(ChatMessage(session_id=sid, role="user", content="hi"))
        session.add(ChatMessage(session_id=sid, role="assistant", content="hello"))
        session.commit()
    r = await client.get(f"/api/chat/sessions/{sid}")
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "T"
    msgs = body["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[0]["content"] == "hi" and msgs[1]["content"] == "hello"
    assert {k for k in msgs[0]} == {"id", "role", "content", "tokens_in", "tokens_out", "created_at"}


async def test_update_session_patches_title_and_params(client):
    sid = (await client.post("/api/chat/sessions", json={"title": "old", "model": MODEL_REF})).json()["id"]
    r = await client.put(f"/api/chat/sessions/{sid}", json={"title": "new", "temperature": 0.9})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["title"] == "new"
    assert body["temperature"] == 0.9
    # model untouched
    assert body["model"] == MODEL_REF


async def test_delete_session_cascades_messages(client):
    sid = (await client.post("/api/chat/sessions", json={"title": "X", "model": MODEL_REF})).json()["id"]
    with db_mod.SessionLocal() as session:
        session.add(ChatMessage(session_id=sid, role="user", content="u"))
        session.commit()
    r = await client.delete(f"/api/chat/sessions/{sid}")
    assert r.status_code == 200
    assert r.json()["deleted"] is True
    # session gone
    r = await client.get(f"/api/chat/sessions/{sid}")
    assert r.status_code == 404
    # messages cascaded
    with db_mod.SessionLocal() as session:
        assert session.query(ChatMessage).filter_by(session_id=sid).count() == 0


async def test_get_missing_session_returns_404(client):
    r = await client.get("/api/chat/sessions/999999")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


# --------------------------------------------------------------------------- #
# SSE completion: reuse gateway pipeline, persist both turns
# --------------------------------------------------------------------------- #
async def test_complete_streams_sse_and_persists_assistant_with_usage(client):
    sid = (await client.post("/api/chat/sessions", json={"title": "C", "model": MODEL_REF})).json()["id"]

    r = await client.post(f"/api/chat/sessions/{sid}/complete", json={"content": "halo"})
    await r.aread()
    assert r.status_code == 200, r.text
    assert "text/event-stream" in r.headers.get("content-type", "")
    assert "Hai" in r.text and "dunia" in r.text and "data: [DONE]" in r.text

    with db_mod.SessionLocal() as session:
        msgs = (
            session.query(ChatMessage)
            .filter_by(session_id=sid)
            .order_by(ChatMessage.id.asc())
            .all()
        )
    roles = [m.role for m in msgs]
    assert roles == ["user", "assistant"], roles
    assert msgs[0].content == "halo"           # user turn persisted
    assert msgs[1].content == "Hai dunia"      # assistant content concatenated from deltas
    assert msgs[1].tokens_in == 7              # usage frame captured
    assert msgs[1].tokens_out == 3


async def test_complete_without_usage_records_none_tokens(client, monkeypatch):
    sid = (await client.post("/api/chat/sessions", json={"title": "N", "model": MODEL_REF})).json()["id"]

    # swap the stream to a no-usage body for this test only
    async def _fake_no_usage(_target, _payload, _proxy=None):
        yield SSE_NO_USAGE

    monkeypatch.setattr(provider_adapter, "chat_completion_stream", _fake_no_usage)

    r = await client.post(f"/api/chat/sessions/{sid}/complete", json={"content": "yo"})
    await r.aread()
    assert r.status_code == 200, r.text
    assert "Oke" in r.text and "siap" in r.text

    with db_mod.SessionLocal() as session:
        msgs = (
            session.query(ChatMessage)
            .filter_by(session_id=sid)
            .order_by(ChatMessage.id.asc())
            .all()
        )
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert msgs[1].content == "Oke siap"
    assert msgs[1].tokens_in is None          # no usage frame -> None, never fabricated
    assert msgs[1].tokens_out is None


async def test_complete_with_system_prompt_included(client):
    sid = (await client.post(
        "/api/chat/sessions",
        json={"title": "S", "model": MODEL_REF, "system_prompt": "Jawab singkat."},
    )).json()["id"]
    r = await client.post(f"/api/chat/sessions/{sid}/complete", json={"content": "hi"})
    await r.aread()
    assert r.status_code == 200, r.text
    with db_mod.SessionLocal() as session:
        msgs = (
            session.query(ChatMessage)
            .filter_by(session_id=sid)
            .order_by(ChatMessage.id.asc())
            .all()
        )
    # user + assistant persisted; system prompt lives on the session, not as a turn
    assert [m.role for m in msgs] == ["user", "assistant"]


async def test_complete_missing_model_returns_400(client):
    sid = (await client.post("/api/chat/sessions", json={"title": "M", "model": None})).json()["id"]
    r = await client.post(f"/api/chat/sessions/{sid}/complete", json={"content": "hi"})
    await r.aread()
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "no_model"
    # no assistant turn persisted (and no accidental provider call)
    with db_mod.SessionLocal() as session:
        assert session.query(ChatMessage).filter_by(session_id=sid).count() == 1


async def test_complete_bad_model_ref_propagates_gateway_error(client):
    """Unknown model ref -> pipeline refuses; honest 400, no assistant saved."""
    sid = (await client.post(
        "/api/chat/sessions", json={"title": "B", "model": "provider:ghost:gpt-4o"}
    )).json()["id"]
    r = await client.post(f"/api/chat/sessions/{sid}/complete", json={"content": "hi"})
    await r.aread()
    # The gateway's TargetNotFound -> GatewayError 400 (OpenAI envelope). The user
    # turn was saved (it is a real message), but NO empty assistant turn exists.
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "model_not_found"
    with db_mod.SessionLocal() as session:
        msgs = session.query(ChatMessage).filter_by(session_id=sid).all()
        assert [m.role for m in msgs] == ["user"]


# --------------------------------------------------------------------------- #
# In-memory engine smoke test (decoupled from the conftest temp DB)
# --------------------------------------------------------------------------- #
def test_chat_models_roundtrip_in_memory():
    """Models map cleanly on a fresh in-memory engine (no production DB)."""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False},
        poolclass=StaticPool, future=True,
    )
    from backend.config.db import Base

    Base.metadata.create_all(engine)
    sf = sessionmaker(bind=engine, autoflush=False, future=True)
    with sf() as session:
        chat = ChatSession(title="rt", model=MODEL_REF, temperature=0.5)
        session.add(chat)
        session.flush()
        session.add(ChatMessage(session_id=chat.id, role="user", content="hi"))
        session.add(ChatMessage(session_id=chat.id, role="assistant", content="yo"))
        session.commit()
        got = session.query(ChatSession).filter_by(id=chat.id).one()
        assert len(got.messages) == 2
        assert got.messages[0].role == "user"
        assert got.messages[1].tokens_in is None


__all__ = ["client"]

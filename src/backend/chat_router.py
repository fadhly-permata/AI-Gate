"""Chat Playground backend API (B8.B6.1 / PRD §2.9 / ERD §ChatSession,ChatMessage).

Entity + CRUD for chat sessions and a **streaming (SSE)** completion endpoint that
reuses the EXISTING gateway pipeline (format translator + Token Saver + quota +
usage logging all run transparently), exactly as PRD §2.9 requires — aigate's
chat is NOT a new LLM engine; it is a thin conversation store on top of the same
``/v1/chat/completions`` machinery that CLIs use.

Routes (full paths on the decorator, matching the repo router style):

* ``GET    /api/chat/sessions``            -> list sessions (updated_at desc)
* ``POST   /api/chat/sessions``            -> create a session
* ``GET    /api/chat/sessions/{id}``       -> session + chronological messages
* ``PUT    /api/chat/sessions/{id}``       -> rename + parameters (title/system/temperature/model)
* ``DELETE /api/chat/sessions/{id}``       -> delete a session (cascades its messages)
* ``POST   /api/chat/sessions/{id}/complete`` -> SSE chat completion, persists both turns

Gateway reuse (the "cara WAJIB pakai gateway" from the handover): the completion
endpoint calls :func:`backend.gateway.router.run_chat_completion` — the pipeline
core extracted from the HTTP surface — directly IN-PROCESS. It never makes an
HTTP loopback to a running server (J6), yet inherits resolver/adapter/combo
routing, the Token Saver hook, usage recording and SSE streaming verbatim. The
returned SSE byte stream is *teed*: forwarded to the client untouched while a
side buffer accumulates the assistant deltas + the final usage frame, which are
then persisted as a ``ChatMessage(role="assistant")``.

Errors use the same OpenAI-style envelope as the rest of the management API
(:func:`backend.usage_router._error` pattern): ``{"error":{message,type,code}}``.

Layering (skill): the router validates + serializes; SSE reassembly and payload
assembly are small pure helpers below it. Pydantic **v1** only (R10). R12/ADR-011:
every handler logs to ``LogEntry``; failure paths log warning/error (no empty
catch — every swallow records the exception).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel

from backend.config.db import SessionLocal
from backend.gateway.errors import GatewayError
from backend.gateway.router import (
    _extract_usage_from_sse,
    _parse_sse_data_frame,
    run_chat_completion,
)
from backend.log import log_info, log_warning, log_warning_exc
from backend.models import ChatMessage, ChatSession

LOG_SOURCE = "backend.chat_router"

router = APIRouter()


# --------------------------------------------------------------------------- #
# Pydantic v1 request DTOs (R10)
# --------------------------------------------------------------------------- #
class SessionCreate(BaseModel):
    """Body for ``POST /api/chat/sessions``. All fields optional (FE may auto-
    title later; the backend just accepts + persists what it is given)."""

    title: Optional[str] = None
    provider_id: Optional[int] = None
    combo_id: Optional[int] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    temperature: Optional[float] = None


class SessionUpdate(BaseModel):
    """Body for ``PUT /api/chat/sessions/{id}`` (rename + parameters). Only the
    provided keys are patched; ``None``/absent leaves the stored value.

    Adds ``model`` so the in-chat model switcher can persist its selection:
    ``body.dict(exclude_unset=True)`` in :func:`update_session` means an absent
    ``model`` is NOT sent, so an existing value is preserved (exclude_unset
    semantics), while an explicitly provided ``model`` overwrites it.
    """

    title: Optional[str] = None
    system_prompt: Optional[str] = None
    temperature: Optional[float] = None
    model: Optional[str] = None


class CompleteRequest(BaseModel):
    """Body for ``POST /api/chat/sessions/{id}/complete`` — one new user turn."""

    content: str


# --------------------------------------------------------------------------- #
# Helpers (pure / serialization)
# --------------------------------------------------------------------------- #
def _error(status: int, message: str, code: str, etype: str = "invalid_request_error"):
    """OpenAI-style error envelope, shared with the management-API convention."""
    return JSONResponse(
        status_code=status,
        content={"error": {"message": message, "type": etype, "code": code}},
    )


def _iso(value: Optional[datetime]) -> Optional[str]:
    """Naive-UTC ISO-8601, or None (JSON-safe serialization of a datetime col)."""
    return value.isoformat() if value is not None else None


def _session_dto(session: ChatSession) -> dict:
    """Full session shape (GET/PUT/create). ``messages`` is added separately."""
    return {
        "id": session.id,
        "title": session.title,
        "provider_id": session.provider_id,
        "combo_id": session.combo_id,
        "model": session.model,
        "system_prompt": session.system_prompt,
        "temperature": session.temperature,
        "created_at": _iso(session.created_at),
        "updated_at": _iso(session.updated_at),
    }


def _session_item_dto(session: ChatSession) -> dict:
    """Compact list item for ``GET /api/chat/sessions`` (sidebar)."""
    return {
        "id": session.id,
        "title": session.title,
        "model": session.model,
        "provider_id": session.provider_id,
        "combo_id": session.combo_id,
        "updated_at": _iso(session.updated_at),
    }


def _message_dto(message: ChatMessage) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "tokens_in": message.tokens_in,
        "tokens_out": message.tokens_out,
        "created_at": _iso(message.created_at),
    }


def _build_history(session: ChatSession, messages: List[ChatMessage]) -> List[dict]:
    """Assemble the OpenAI ``messages`` array for a completion.

    System prompt first (session-level, not persisted as a turn), then every
    stored turn in chronological order. The just-saved user turn is already in
    ``messages`` (it is queried AFTER the insert), so it is NOT appended twice.
    """
    history: List[dict] = []
    if session.system_prompt:
        history.append({"role": "system", "content": session.system_prompt})
    for message in messages:
        if message.role == "system":
            # Session-level system prompt is the single source; never double it.
            continue
        history.append({"role": message.role, "content": message.content})
    return history


def _assistant_text_from_sse(raw: bytes) -> str:
    """Concatenate every assistant ``delta.content`` from an OpenAI SSE stream.

    Frames split across chunk boundaries are reassembled (split on the ``\\n\\n``
    event delimiter); ``[DONE]`` and malformed/blank frames are skipped by the
    shared :func:`backend.gateway.router._parse_sse_data_frame`. Non-string
    content parts (e.g. tool-call deltas) are ignored.
    """
    parts: List[str] = []
    for frame in raw.split(b"\n\n"):
        obj = _parse_sse_data_frame(frame)
        if not obj:
            continue
        for choice in obj.get("choices") or []:
            if not isinstance(choice, dict):
                continue
            delta = choice.get("delta")
            if isinstance(delta, dict):
                content = delta.get("content")
                if isinstance(content, str):
                    parts.append(content)
    return "".join(parts)


# --------------------------------------------------------------------------- #
# Session CRUD
# --------------------------------------------------------------------------- #
@router.get("/api/chat/sessions")
def list_sessions() -> Any:
    """List chat sessions, newest activity first."""
    with SessionLocal() as session:
        rows = (
            session.query(ChatSession)
            .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
            .all()
        )
        data = [_session_item_dto(row) for row in rows]
    log_info(
        f"GET /api/chat/sessions -> {len(data)} session(s)", source=LOG_SOURCE
    )
    return {"object": "list", "data": data}


@router.post("/api/chat/sessions")
def create_session(body: SessionCreate) -> Any:
    """Create a chat session; returns the full session."""
    with SessionLocal() as session:
        chat = ChatSession(
            title=body.title or "",
            provider_id=body.provider_id,
            combo_id=body.combo_id,
            model=body.model,
            system_prompt=body.system_prompt,
            temperature=body.temperature,
        )
        session.add(chat)
        session.commit()
        session.refresh(chat)
        dto = _session_dto(chat)
    log_info(f"POST /api/chat/sessions -> id={dto['id']}", source=LOG_SOURCE)
    return dto


@router.get("/api/chat/sessions/{session_id}")
def get_session(session_id: int) -> Any:
    """One session + its full message history (chronological asc)."""
    with SessionLocal() as session:
        chat = session.get(ChatSession, session_id)
        if chat is None:
            log_warning(
                f"GET /api/chat/sessions/{session_id} -> not found",
                source=LOG_SOURCE,
            )
            return _error(404, f"chat session {session_id} not found", "not_found")
        messages = (
            session.query(ChatMessage)
            .filter_by(session_id=session_id)
            .order_by(ChatMessage.id.asc())
            .all()
        )
        dto = _session_dto(chat)
        dto["messages"] = [_message_dto(m) for m in messages]
    log_info(
        f"GET /api/chat/sessions/{session_id} -> {len(dto['messages'])} message(s)",
        source=LOG_SOURCE,
    )
    return dto


@router.put("/api/chat/sessions/{session_id}")
def update_session(session_id: int, body: SessionUpdate) -> Any:
    """Rename + set parameters (title / system_prompt / temperature / model)."""
    updates = body.dict(exclude_unset=True)
    with SessionLocal() as session:
        chat = session.get(ChatSession, session_id)
        if chat is None:
            log_warning(
                f"PUT /api/chat/sessions/{session_id} -> not found",
                source=LOG_SOURCE,
            )
            return _error(404, f"chat session {session_id} not found", "not_found")
        for key, value in updates.items():
            setattr(chat, key, value)
        # Bump updated_at explicitly so the sidebar (updated_at desc) reorders on
        # any real edit; ``onupdate`` alone also fires here, but setting it keeps
        # the intent obvious and covers a no-op PUT deterministically.
        chat.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(chat)
        dto = _session_dto(chat)
    log_info(
        f"PUT /api/chat/sessions/{session_id} -> updated {sorted(updates)}",
        source=LOG_SOURCE,
    )
    return dto


@router.delete("/api/chat/sessions/{session_id}")
def delete_session(session_id: int) -> Any:
    """Delete a session + cascade its messages (ORM ``delete-orphan``)."""
    with SessionLocal() as session:
        chat = session.get(ChatSession, session_id)
        if chat is None:
            log_warning(
                f"DELETE /api/chat/sessions/{session_id} -> not found",
                source=LOG_SOURCE,
            )
            return _error(404, f"chat session {session_id} not found", "not_found")
        session.delete(chat)  # relationship cascades the ChatMessage rows
        session.commit()
    log_info(
        f"DELETE /api/chat/sessions/{session_id} -> deleted (messages cascaded)",
        source=LOG_SOURCE,
    )
    return {"object": "chat.session.deleted", "id": session_id, "deleted": True}


# --------------------------------------------------------------------------- #
# Streaming completion (the core feature)
# --------------------------------------------------------------------------- #
def _persist_assistant(session_id: int, raw_sse: bytes, model: str) -> None:
    """Persist the assistant turn from a completed SSE stream (fail-open).

    Content = the concatenated ``delta.content`` fragments; token counts come
    from the final usage frame when the upstream emitted one (``include_usage``),
    else ``None`` — never a fabricated number (handover). An empty assistant turn
    (error / no content) is NOT persisted. A DB failure is logged and swallowed
    so it can never corrupt an already-delivered stream (R12 — no empty catch).
    """
    content = _assistant_text_from_sse(raw_sse)
    if not content:
        log_warning(
            f"assistant stream produced no content for session {session_id}; "
            "message not persisted",
            source=LOG_SOURCE,
        )
        return
    usage = _extract_usage_from_sse(raw_sse)
    tokens_in = usage.get("prompt_tokens") if usage else None
    tokens_out = usage.get("completion_tokens") if usage else None
    try:
        with SessionLocal() as session:
            session.add(
                ChatMessage(
                    session_id=session_id,
                    role="assistant",
                    content=content,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                )
            )
            chat = session.get(ChatSession, session_id)
            if chat is not None:
                chat.updated_at = datetime.utcnow()
            session.commit()
        log_info(
            f"assistant turn persisted for session {session_id} "
            f"({len(content)} chars, model={model!r})",
            source=LOG_SOURCE,
        )
    except Exception as exc:  # noqa: BLE001 - fail-open: stream already delivered
        log_warning_exc(
            f"assistant persistence failed for session {session_id}",
            source=LOG_SOURCE,
            exc=exc,
        )


@router.post("/api/chat/sessions/{session_id}/complete")
async def complete_session(session_id: int, body: CompleteRequest) -> Response:
    """Stream one chat turn through the gateway pipeline and persist both turns.

    Persists the user turn, assembles the OpenAI payload from the session's
    history + parameters, runs it through the reused gateway pipeline (SSE), and
    — after the stream — persists the assembled assistant turn. On any pipeline
    error the client gets the honest OpenAI envelope and NO assistant turn is
    saved (the user message stays, so a retry reuses it deliberately: it is a
    real message the user sent).
    """
    # --- assemble payload (short-lived session; do NOT hold it across stream) -- #
    with SessionLocal() as session:
        chat = session.get(ChatSession, session_id)
        if chat is None:
            log_warning(
                f"POST /api/chat/sessions/{session_id}/complete -> session not found",
                source=LOG_SOURCE,
            )
            return _error(404, f"chat session {session_id} not found", "not_found")
        # Persist the user turn FIRST (handover sequence: save user -> build -> run
        # pipeline); a session without a target cannot complete, but the message the
        # user actually sent stays in history for a later retry.
        session.add(
            ChatMessage(session_id=session_id, role="user", content=body.content)
        )
        chat.updated_at = datetime.utcnow()
        session.commit()

        if not chat.model:
            log_warning(
                f"session {session_id} has no model/target configured",
                source=LOG_SOURCE,
            )
            return _error(
                400,
                "session has no model/target set; set one before chatting",
                "no_model",
            )

        messages = (
            session.query(ChatMessage)
            .filter_by(session_id=session_id)
            .order_by(ChatMessage.id.asc())
            .all()
        )
        history = _build_history(chat, messages)
        model = chat.model
        temperature = chat.temperature

    payload: dict = {"model": model, "messages": history, "stream": True}
    if temperature is not None:
        payload["temperature"] = temperature

    ctx: dict = {
        "endpoint_id": None,
        "model": None,
        "payload": None,
        "saved_bytes": None,
    }

    # --- run the REUSED gateway pipeline (in-process, no HTTP loopback) ------- #
    try:
        result = await run_chat_completion(payload, ctx)
    except GatewayError as exc:
        # Honest propagation: the pipeline refuses (bad ref / translated format /
        # upstream error). Do NOT save an empty assistant turn. The user turn was
        # already persisted (a real message the user sent).
        log_warning(
            f"completion pipeline error for session {session_id}: "
            f"{exc.envelope.get('error', {}).get('message', exc)}",
            source=LOG_SOURCE,
            context={"code": exc.envelope.get("error", {}).get("code")},
        )
        return JSONResponse(status_code=exc.status_code, content=exc.envelope)

    # --- non-streaming fallback (translated formats can only answer as JSON) -- #
    if not isinstance(result, StreamingResponse):
        if isinstance(result, dict) and "error" in result:
            return JSONResponse(status_code=502, content=result)
        assistant_msg = _assistant_from_nonstream(result)
        if assistant_msg is not None:
            _persist_assistant_text(session_id, assistant_msg, result, model)
        return result if isinstance(result, Response) else JSONResponse(result)

    # --- tee the SSE: forward verbatim + accumulate to persist the assistant --- #
    return _tee_sse_and_persist(result, session_id, model)


# --------------------------------------------------------------------------- #
# SSE tee wrapper
# --------------------------------------------------------------------------- #
def _tee_sse_and_persist(
    response: StreamingResponse, session_id: int, model: str
) -> StreamingResponse:
    """Wrap a gateway ``StreamingResponse`` so its bytes are forwarded untouched
    while a side buffer accumulates them for post-stream assistant persistence.

    ``completed`` guards persistence to a clean end-of-stream: a client
    disconnect / mid-stream error (``GeneratorExit`` / exception) leaves the
    partial stream unpersisted rather than storing a truncated assistant turn.
    """
    source_iter = response.body_iterator

    async def tee():
        buffer = bytearray()
        completed = False
        try:
            async for chunk in source_iter:
                if isinstance(chunk, str):
                    buffer.extend(chunk.encode("utf-8"))
                else:
                    buffer.extend(chunk)
                yield chunk
            completed = True
        finally:
            if completed:
                _persist_assistant(session_id, bytes(buffer), model)

    return StreamingResponse(
        tee(),
        media_type=getattr(response, "media_type", "text/event-stream"),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _assistant_from_nonstream(result: object) -> Optional[str]:
    """Extract assistant text from a non-stream OpenAI completion dict (or None)."""
    if not isinstance(result, dict):
        return None
    try:
        content = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    return content if isinstance(content, str) and content else None


def _persist_assistant_text(
    session_id: int, content: str, result: object, model: str
) -> None:
    """Persist an assistant turn from a non-stream completion dict (fail-open)."""
    usage = result.get("usage") if isinstance(result, dict) else None
    tokens_in = usage.get("prompt_tokens") if isinstance(usage, dict) else None
    tokens_out = usage.get("completion_tokens") if isinstance(usage, dict) else None
    try:
        with SessionLocal() as session:
            session.add(
                ChatMessage(
                    session_id=session_id,
                    role="assistant",
                    content=content,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                )
            )
            chat = session.get(ChatSession, session_id)
            if chat is not None:
                chat.updated_at = datetime.utcnow()
            session.commit()
        log_info(
            f"assistant turn (non-stream) persisted for session {session_id}",
            source=LOG_SOURCE,
        )
    except Exception as exc:  # noqa: BLE001 - fail-open: response already built
        log_warning_exc(
            f"assistant (non-stream) persistence failed for session {session_id}",
            source=LOG_SOURCE,
            exc=exc,
        )


__all__ = ["router"]

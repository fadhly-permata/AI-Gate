"""Format Translation Engine (ADR-012) — B5.3 backend scope.

Translates chat-completion requests/responses between the OpenAI format the
client always speaks and the native format each upstream provider expects.

Design constraints (HARD RULES):
- FastAPI <0.100 / Pydantic v1 only — this module is ORM/pure-function, no pydantic.
- No ``except: pass`` / empty except: every failure path logs to ``LogEntry``
  via ``backend.log`` and raises or returns a safe fallback.
- Streaming is NOT translated here (the adapter currently returns ``resp.json()``
  non-streaming). Per-chunk translation is a future task — see ``# TODO streaming``
  markers in ``provider_adapter``.
- Client-facing contract (OpenAI shape) is never changed: translation is internal
  and transparent (OPENAI_COMPATIBLE_CONTRACT.md §2.4).

Supported canonical formats:
- ``openai``      — pass-through (verbatim request/response).
- ``anthropic``   — Anthropic Messages API (``/v1/messages``).
- ``gemini``      — Google Gemini ``generateContent``.

Everything else (cursor, kiro, vertex, antigravity, ollama, openrouter,
litellm, openai-compatible) maps to ``openai`` pass-through (they are
OpenAI-compatible). See :data:`FORMAT_ALIASES`.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Iterator, List, Optional

from backend.gateway.errors import GatewayError
from backend.log import log_warning

logger = logging.getLogger(__name__)

# Default max_tokens injected when an upstream requires it but the client (OpenAI
# format) did not supply one. 4096 is a sane non-streaming default.
_DEFAULT_MAX_TOKENS = 4096

# Stable machine codes (contract) for the inbound Anthropic `/v1/messages`
# surface. Mirrors the Responses surface codes in ``responses.py`` so every
# refusal a client can hit has a stable, grep-able identifier (R47 fact-based).
ANTHROPIC_STREAMING_UNSUPPORTED_CODE = "anthropic_streaming_unsupported"
ANTHROPIC_UNSUPPORTED_FIELD_CODE = "anthropic_unsupported_field"
ANTHROPIC_MISSING_MODEL_CODE = "anthropic_missing_model"
ANTHROPIC_INVALID_REQUEST_CODE = "anthropic_invalid_request"

# Log source for the inbound Anthropic surface (kept distinct from the
# OUTBOING translator source so LogEntry rows are attributable).
ANTHROPIC_LOG_SOURCE = "backend.gateway.translator.anthropic"

# Provider.type -> canonical translation format. Anything not listed resolves to
# ``openai`` (safe pass-through) so unrecognized providers never break.
FORMAT_ALIASES: Dict[str, str] = {
    "claude": "anthropic",
    "openai-compatible": "openai",
    "openrouter": "openai",
    "litellm": "openai",
    "ollama": "openai",
    "cursor": "openai",
    "kiro": "openai",
    "vertex": "openai",
    "antigravity": "openai",
    "gemini": "gemini",
    "anthropic": "anthropic",
}


def format_for_provider_type(provider_type: str) -> str:
    """Map a :class:`~backend.models.Provider.type` to a canonical format.

    Unrecognized types fall back to ``"openai"`` (safe pass-through).
    """
    if not provider_type:
        return "openai"
    return FORMAT_ALIASES.get(provider_type.strip().lower(), "openai")


def _error(message: str, error_type: str, code: str) -> dict:
    """OpenAI-shaped error envelope (matches provider_adapter._error)."""
    return {"error": {"message": message, "type": error_type, "code": code}}


def _extract_text(content: Any) -> str:
    """Best-effort extraction of plain text from an OpenAI message ``content``.

    Handles ``str`` and the ``[{"type": "text", "text": ...}, ...]`` list form.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text" and "text" in block:
                    parts.append(str(block["text"]))
                elif "text" in block:
                    parts.append(str(block["text"]))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


def _build_system(messages: List[dict]) -> str:
    """Concatenate all ``role == 'system'`` messages into one system string."""
    chunks: List[str] = []
    for m in messages:
        if m.get("role") == "system":
            text = _extract_text(m.get("content"))
            if text:
                chunks.append(text)
    return "\n".join(chunks)


def _openai_to_anthropic_messages(messages: List[dict]) -> List[dict]:
    """Map OpenAI messages -> Anthropic ``messages`` (user/assistant only)."""
    out: List[dict] = []
    for m in messages:
        role = m.get("role")
        if role == "system":
            continue  # handled as top-level `system`
        if role == "assistant":
            content: Any = []
            text = _extract_text(m.get("content"))
            if text:
                content.append({"type": "text", "text": text})
            for tc in m.get("tool_calls", []) or []:
                func = tc.get("function", {}) or {}
                raw_args = func.get("arguments", "{}")
                try:
                    tool_input = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except (json.JSONDecodeError, TypeError):
                    tool_input = {}
                content.append(
                    {
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": func.get("name", ""),
                        "input": tool_input,
                    }
                )
            out.append({"role": "assistant", "content": content})
        elif role == "tool":
            # OpenAI tool result -> Anthropic user message with tool_result block.
            out.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m.get("tool_call_id", ""),
                            "content": _extract_text(m.get("content")),
                        }
                    ],
                }
            )
        else:  # user
            out.append({"role": "user", "content": _extract_text(m.get("content"))})
    return out


def translate_request(format: str, payload: dict) -> dict:
    """Translate an OUTGOING OpenAI request into the upstream native format.

    :param format: canonical format from :func:`format_for_provider_type`.
    :param payload: the OpenAI-style request body (``model`` already rewritten
      to the REAL upstream model id by the adapter).
    :returns: ``{"url_path": str, "headers_extra": dict, "body": dict}``.
    """
    if format == "anthropic":
        return _translate_request_anthropic(payload)
    if format == "gemini":
        return _translate_request_gemini(payload)
    # openai (and everything else) -> verbatim pass-through.
    return {"url_path": "/chat/completions", "headers_extra": {}, "body": payload}


def _translate_request_anthropic(payload: dict) -> dict:
    messages = payload.get("messages", []) or []
    system = _build_system(messages)
    anthropic_messages = _openai_to_anthropic_messages(messages)

    body: dict = {
        "model": payload.get("model"),
        "messages": anthropic_messages,
    }
    if system:
        body["system"] = system

    # Anthropic REQUIRES max_tokens; OpenAI does not. Inject a sane default and
    # warn when the client did not supply one.
    if "max_tokens" in payload and payload["max_tokens"] is not None:
        body["max_tokens"] = payload["max_tokens"]
    else:
        body["max_tokens"] = _DEFAULT_MAX_TOKENS
        log_warning(
            "translate_request(anthropic): client did not supply max_tokens; "
            f"injected default {_DEFAULT_MAX_TOKENS}",
            source="backend.gateway.translator",
            context={"upstream_model": payload.get("model")},
        )

    # Pass through common sampling params (drop OpenAI-only fields like stream/n).
    for key in ("temperature", "top_p", "top_k", "stop"):
        if key in payload and payload[key] is not None:
            body[key] = payload[key]

    # Forward OpenAI tools / tool_choice to the anthropic upstream so an
    # OpenAI-format payload (produced by ``anthropic_messages_request_to_openai_chat``)
    # survives the double-translation round-trip (desgin: §3). Additive only — the
    # fields are included iff present; existing outbound behaviour is unchanged.
    if "tools" in payload and payload["tools"] is not None:
        anthropic_tools = _openai_tools_to_anthropic(payload["tools"])
        if anthropic_tools:
            body["tools"] = anthropic_tools
    if "tool_choice" in payload and payload["tool_choice"] is not None:
        tc = _openai_tool_choice_to_anthropic(payload["tool_choice"])
        if tc is not None:
            body["tool_choice"] = tc

    return {
        "url_path": "/v1/messages",
        "headers_extra": {"anthropic-version": "2023-06-01"},
        "body": body,
    }


def _openai_tools_to_anthropic(tools: Any) -> list:
    """OpenAI ``tools`` (``[{type:"function",function:{...}}]``) → Anthropic
    ``tools`` (``[{name,description,input_schema}]``)."""
    out: list = []
    if not isinstance(tools, list):
        return out
    for t in tools:
        if not isinstance(t, dict):
            continue
        func = t.get("function", {}) or {}
        out.append(
            {
                "name": func.get("name", ""),
                "description": func.get("description", ""),
                "input_schema": func.get("parameters", {}),
            }
        )
    return out


def _openai_tool_choice_to_anthropic(choice: Any) -> Optional[dict]:
    """OpenAI ``tool_choice`` → Anthropic ``tool_choice``.

    auto→auto · none→none · required→any · function→{type:"tool",name}.
    """
    if not isinstance(choice, dict):
        return None
    ctype = choice.get("type")
    if ctype == "auto":
        return {"type": "auto"}
    if ctype == "none":
        return {"type": "none"}
    if ctype == "required":
        return {"type": "any"}
    if ctype == "function":
        name = (choice.get("function") or {}).get("name", "")
        return {"type": "tool", "name": name}
    return None


def _translate_request_gemini(payload: dict) -> dict:
    messages = payload.get("messages", []) or []
    system = _build_system(messages)
    contents: List[dict] = []
    for m in messages:
        role = m.get("role")
        if role in ("system", "tool"):
            continue  # system -> systemInstruction; tool results best-effort skipped
        grole = "user" if role == "user" else "model"
        text = _extract_text(m.get("content"))
        contents.append({"role": grole, "parts": [{"text": text}]})

    model = payload.get("model")
    body: dict = {"contents": contents}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}

    gen_cfg: dict = {}
    if "temperature" in payload and payload["temperature"] is not None:
        gen_cfg["temperature"] = payload["temperature"]
    gen_cfg["maxOutputTokens"] = payload.get("max_tokens", _DEFAULT_MAX_TOKENS)
    body["generationConfig"] = gen_cfg

    return {
        "url_path": "/v1beta/models/" + str(model) + ":generateContent",
        "headers_extra": {},
        "body": body,
    }


def translate_response(format: str, raw_json: dict) -> dict:
    """Translate an INCOMING upstream response into OpenAI chat-completion shape.

    :param format: canonical upstream format.
    :param raw_json: parsed upstream JSON.
    :returns: OpenAI-shaped chat completion dict.
    """
    if format == "anthropic":
        return _translate_response_anthropic(raw_json)
    if format == "gemini":
        return _translate_response_gemini(raw_json)
    # openai -> already OpenAI-shaped; return verbatim.
    return raw_json


def _translate_response_anthropic(raw: dict) -> dict:
    raw = raw or {}
    content_blocks = raw.get("content", []) or []
    text_parts: List[str] = []
    tool_calls: List[dict] = []
    for block in content_blocks:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            text_parts.append(block.get("text", ""))
        elif btype == "tool_use":
            tool_calls.append(
                {
                    "id": block.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": block.get("name", ""),
                        "arguments": json.dumps(
                            block.get("input", {}), ensure_ascii=False
                        ),
                    },
                }
            )

    finish = _anthropic_stop_reason(raw.get("stop_reason"))
    message = {
        "role": "assistant",
        "content": "".join(text_parts) if not tool_calls else "".join(text_parts),
    }
    if tool_calls:
        message["tool_calls"] = tool_calls

    usage = raw.get("usage", {}) or {}
    prompt_tokens = usage.get("input_tokens", 0) or 0
    completion_tokens = usage.get("output_tokens", 0) or 0

    return {
        "id": raw.get("id", "anthropic-" + str(int(time.time()))),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": raw.get("model", ""),
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": finish,
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def _anthropic_stop_reason(stop_reason: Optional[str]) -> str:
    mapping = {
        "end_turn": "stop",
        "stop_sequence": "stop",
        "tool_use": "tool_calls",
        "max_tokens": "length",
    }
    return mapping.get(stop_reason, "stop") if stop_reason else "stop"


def _translate_response_gemini(raw: dict) -> dict:
    raw = raw or {}
    candidates = raw.get("candidates", []) or []
    text_parts: List[str] = []
    finish = "stop"
    if candidates:
        c0 = candidates[0] or {}
        parts = (c0.get("content", {}) or {}).get("parts", []) or []
        for p in parts:
            if isinstance(p, dict) and "text" in p:
                text_parts.append(str(p["text"]))
        finish = _gemini_finish_reason(c0.get("finishReason"))

    usage_meta = raw.get("usageMetadata", {}) or {}
    prompt_tokens = usage_meta.get("promptTokenCount", 0) or 0
    completion_tokens = usage_meta.get("candidatesTokenCount", 0) or 0
    total_tokens = usage_meta.get("totalTokenCount", 0) or (
        prompt_tokens + completion_tokens
    )

    return {
        "id": "gemini-" + str(int(time.time())),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": raw.get("model", ""),
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "".join(text_parts),
                },
                "finish_reason": finish,
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        },
    }


def _gemini_finish_reason(reason: Optional[str]) -> str:
    mapping = {
        "STOP": "stop",
        "MAX_TOKENS": "length",
        "SAFETY": "content_filter",
        "RECITATION": "content_filter",
    }
    return mapping.get(reason, "stop") if reason else "stop"


# --------------------------------------------------------------------------- #
# Inbound Anthropic Messages API (POST /v1/messages) translation
# --------------------------------------------------------------------------- #
# aigate speaks OpenAI chat-completions internally; ``claude-code`` speaks the
# Anthropic Messages API and points ``ANTHROPIC_BASE_URL`` here. The two functions
# below are the INBOUND inverse of the OUTBOUND pair above: they translate an
# incoming Anthropic request into the OpenAI chat payload the rest of the pipeline
# already consumes, and translate the OpenAI chat response back into an Anthropic
# Messages envelope. Everything else (resolver / adapter / combo / usage / logging)
# is reused verbatim from ``/v1/chat/completions`` and ``/v1/responses`` (DRY).
import uuid as _uuid  # noqa: E402  (kept local to the inbound block; see __all__)

LOG_SOURCE_ANTHROPIC = ANTHROPIC_LOG_SOURCE


def _derive_anthropic_id(chat_id: Any, prefix: str) -> str:
    """Derive a ``msg_``/``chatcmpl-``-style id from a chat id (fallback random).

    Mirrors :func:`backend.gateway.responses._derive_id` (strips ``chatcmpl-`` so
    the correlation suffix stays visible).
    """
    if isinstance(chat_id, str) and chat_id:
        base = (
            chat_id[len("chatcmpl-"):]
            if chat_id.startswith("chatcmpl-")
            else chat_id
        )
        return f"{prefix}{base}"
    return f"{prefix}{_uuid.uuid4().hex[:24]}"


def _anthropic_to_openai_messages(messages: Any) -> List[dict]:
    """Map Anthropic ``messages`` (user/assistant, content blocks) → OpenAI.

    Inverse of :func:`_openai_to_anthropic_messages`. Handles:
    * ``content`` as ``str`` or a list of blocks;
    * ``tool_use`` blocks → assistant ``tool_calls`` (input JSON-dumped to args);
    * ``tool_result`` blocks → ``{"role":"tool","tool_call_id","content"}``.
    """
    out: List[dict] = []
    if not isinstance(messages, list):
        return out
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = m.get("content")

        if role == "assistant":
            text_parts: List[str] = []
            tool_calls: List[dict] = []
            if isinstance(content, str):
                text_parts.append(content)
            elif isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type")
                    if btype == "text":
                        text_parts.append(block.get("text", ""))
                    elif btype == "tool_use":
                        inp = block.get("input", {})
                        if not isinstance(inp, (dict, list)):
                            inp = {"value": inp}
                        tool_calls.append(
                            {
                                "id": block.get("id", ""),
                                "type": "function",
                                "function": {
                                    "name": block.get("name", ""),
                                    "arguments": json.dumps(
                                        inp, ensure_ascii=False
                                    ),
                                },
                            }
                        )
            msg: dict = {
                "role": "assistant",
                "content": "".join(text_parts),
            }
            if tool_calls:
                msg["tool_calls"] = tool_calls
            out.append(msg)

        elif role == "user":
            if isinstance(content, str):
                out.append({"role": "user", "content": content})
            elif isinstance(content, list):
                text_parts = []
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type")
                    if btype == "text":
                        text_parts.append(block.get("text", ""))
                    elif btype == "tool_result":
                        result_content = block.get("content", "")
                        if isinstance(result_content, list):
                            result_content = _extract_text(result_content)
                        out.append(
                            {
                                "role": "tool",
                                "tool_call_id": block.get("tool_use_id", ""),
                                "content": (
                                    result_content
                                    if isinstance(result_content, str)
                                    else str(result_content)
                                ),
                            }
                        )
                if text_parts:
                    out.append({"role": "user", "content": "".join(text_parts)})
            else:
                out.append(
                    {
                        "role": "user",
                        "content": "" if content is None else str(content),
                    }
                )
        # Non-standard roles are skipped (claude-code only sends user/assistant).
    return out


def _anthropic_system_to_text(system: Any) -> str:
    """Anthropic ``system`` (``str`` or ``[{type:"text",text}]``) → plain string."""
    if system is None:
        return ""
    if isinstance(system, str):
        return system
    if isinstance(system, list):
        parts = []
        for block in system:
            if isinstance(block, dict) and "text" in block:
                parts.append(str(block["text"]))
        return "".join(parts)
    return str(system)


def _anthropic_tools_to_openai_tools(tools: Any) -> List[dict]:
    """Anthropic ``tools`` (``[{name,description,input_schema}]``) → OpenAI."""
    out: List[dict] = []
    if not isinstance(tools, list):
        return out
    for t in tools:
        if not isinstance(t, dict):
            continue
        out.append(
            {
                "type": "function",
                "function": {
                    "name": t.get("name", ""),
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {}),
                },
            }
        )
    return out


def _anthropic_tool_choice_to_openai(choice: Any) -> Optional[dict]:
    """Anthropic ``tool_choice`` → OpenAI ``tool_choice``.

    auto→auto · none→none · any→required · {type:"tool",name}→{type:function,...}.
    """
    if not isinstance(choice, dict):
        return None
    ctype = choice.get("type")
    if ctype == "auto":
        return {"type": "auto"}
    if ctype == "none":
        return {"type": "none"}
    if ctype == "any":
        return {"type": "required"}
    if ctype == "tool":
        return {
            "type": "function",
            "function": {"name": choice.get("name", "")},
        }
    return None


def _openai_finish_to_anthropic(finish: Optional[str]) -> str:
    """OpenAI ``finish_reason`` → Anthropic ``stop_reason`` (inverse map)."""
    mapping = {
        "stop": "end_turn",
        "tool_calls": "tool_use",
        "length": "max_tokens",
        "content_filter": "stop",
    }
    return mapping.get(finish, "end_turn") if finish else "end_turn"


def anthropic_messages_request_to_openai_chat(
    payload: dict, allow_stream: bool = False
) -> dict:
    """Translate an INBOUND Anthropic Messages request → OpenAI chat payload.

    Pure function (raises :class:`GatewayError`). Reuses the SAME pipeline as
    ``/v1/chat/completions`` and ``/v1/responses`` downstream.

    :param allow_stream: when ``True`` (Tahap 2 inbound Anthropic SSE), a
      ``stream:true`` request is accepted and the returned payload is forced to
      ``stream:true`` + ``stream_options={"include_usage": true}`` so the gateway
      can translate the upstream OpenAI SSE into the Anthropic SSE envelope. When
      ``False`` (default — Stage 1 non-streaming), ``stream:true`` is refused
      exactly as before (no behaviour change).
    :raises GatewayError: 400 ``anthropic_streaming_unsupported`` for
      ``stream:true`` when ``allow_stream`` is ``False``; 400
      ``anthropic_unsupported_field`` for ``thinking`` with ``enabled`` (extended
      thinking is not representable in the OpenAI chat payload). Harmless keys
      (``metadata``) are dropped silently (a stateless gateway never forwards them).
    """
    payload = payload or {}

    # Stage 1 (allow_stream=False): refuse stream:true (clear seam). Tahap 2
    # (allow_stream=True, the streaming /v1/messages route): accept it and mark the
    # chat payload to stream — the final `stream`/`stream_options` are set below
    # after the sampling params are copied.
    wants_stream = payload.get("stream") is True
    if wants_stream and not allow_stream:
        log_warning(
            "anthropic /v1/messages asked for stream:true; Stage 1 is "
            "non-streaming only",
            source=LOG_SOURCE_ANTHROPIC,
        )
        raise GatewayError(
            400,
            "streaming is not yet supported on /v1/messages (use stream:false)",
            "invalid_request_error",
            ANTHROPIC_STREAMING_UNSUPPORTED_CODE,
        )

    # Extended thinking is NOT representable in an OpenAI chat payload (Stage 1).
    # Refuse loudly rather than silently dropping an instruction that would
    # corrupt an agent loop.
    thinking = payload.get("thinking")
    if isinstance(thinking, dict) and thinking.get("enabled") is True:
        log_warning(
            "anthropic /v1/messages requested extended 'thinking'; not "
            "supported in Stage 1",
            source=LOG_SOURCE_ANTHROPIC,
        )
        raise GatewayError(
            400,
            "field 'thinking' (extended thinking) is not supported on "
            "/v1/messages in this build",
            "invalid_request_error",
            ANTHROPIC_UNSUPPORTED_FIELD_CODE,
        )

    model = payload.get("model")

    messages: List[dict] = _anthropic_to_openai_messages(payload.get("messages"))

    # system (string OR blocks) → leading system message.
    system_text = _anthropic_system_to_text(payload.get("system"))
    if system_text:
        messages.insert(0, {"role": "system", "content": system_text})

    chat: dict = {"model": model, "messages": messages}

    # Anthropic REQUIRES max_tokens; inject the shared default if absent.
    max_tokens = payload.get("max_tokens")
    if max_tokens is not None:
        chat["max_tokens"] = max_tokens
    else:
        chat["max_tokens"] = _DEFAULT_MAX_TOKENS
        log_warning(
            "anthropic /v1/messages: client did not supply max_tokens; "
            f"injected default {_DEFAULT_MAX_TOKENS}",
            source=LOG_SOURCE_ANTHROPIC,
            context={"upstream_model": model},
        )

    # Pass through common sampling params.
    for key in ("temperature", "top_p", "top_k", "stop_sequences"):
        if key in payload and payload[key] is not None:
            chat["stop" if key == "stop_sequences" else key] = payload[key]

    # Tools + tool_choice passthrough (Decision 3 — Stage 1 supported).
    tools = _anthropic_tools_to_openai_tools(payload.get("tools"))
    if tools:
        chat["tools"] = tools
    tool_choice = _anthropic_tool_choice_to_openai(payload.get("tool_choice"))
    if tool_choice is not None:
        chat["tool_choice"] = tool_choice

    # Harmless OpenAI/Anthropic metadata keys are dropped (whitelist decides what
    # reaches upstream; nothing is blindly forwarded).

    # Tahap 2: a streaming inbound request must become an OpenAI stream that also
    # carries the final usage chunk (so message_delta can report token counts).
    if allow_stream and wants_stream:
        chat["stream"] = True
        chat["stream_options"] = {"include_usage": True}

    return chat


def openai_chat_response_to_anthropic_messages(
    chat_result: dict, request_model: str
) -> dict:
    """Translate an OpenAI chat-completion response → Anthropic Messages envelope.

    ``model`` echoes the REQUEST model ref (claude-code matches on what it sent).
    Inverse of :func:`_translate_response_anthropic`.
    """
    chat_result = chat_result or {}
    choices = chat_result.get("choices")
    first: dict = choices[0] if isinstance(choices, list) and choices else {}
    if not isinstance(first, dict):
        first = {}
    message = first.get("message")
    if not isinstance(message, dict):
        message = {}

    text = message.get("content")
    if not isinstance(text, str):
        text = "" if text is None else str(text)

    blocks: List[dict] = []
    if text:
        blocks.append({"type": "text", "text": text})

    tool_calls = message.get("tool_calls")
    if isinstance(tool_calls, list):
        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue
            func = tc.get("function", {}) or {}
            raw_args = func.get("arguments", "{}")
            try:
                tool_input = (
                    json.loads(raw_args)
                    if isinstance(raw_args, str)
                    else raw_args
                )
            except (json.JSONDecodeError, TypeError):
                tool_input = {}
            blocks.append(
                {
                    "type": "tool_use",
                    "id": tc.get("id", ""),
                    "name": func.get("name", ""),
                    "input": tool_input if isinstance(tool_input, dict) else {},
                }
            )

    stop_reason = _openai_finish_to_anthropic(first.get("finish_reason"))

    usage = chat_result.get("usage")
    if not isinstance(usage, dict):
        usage = {}
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)

    return {
        "id": _derive_anthropic_id(chat_result.get("id"), "msg_"),
        "type": "message",
        "role": "assistant",
        "model": request_model,
        "content": blocks if blocks else [{"type": "text", "text": ""}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
        },
    }


class _AnthropicSseEncoder:
    """Stateful OpenAI-chunk -> Anthropic-SSE encoder (Tahap 2 inbound stream).

    A single encoder instance walks the WHOLE OpenAI chunk sequence so it can
    emit a correct Anthropic Messages SSE event stream in order:
    ``message_start`` -> ``content_block_start`` -> ``content_block_delta``*
    (+ optional ``tool_use`` blocks via ``input_json_delta``) -> ``content_block_stop``
    -> ``message_delta`` (stop_reason + usage) -> ``message_stop``.

    Exposed through :func:`openai_chunk_stream_to_anthropic_events` (pure, list-in
    / events-out); the streaming router drives :meth:`feed` per upstream byte frame
    so it can flush low-latency while keeping one continuous state machine.

    Internal representation = OpenAI chat-completion chunk dicts (the SAME shape
    ``_streaming_response`` forwards today) — no new stream engine (DRY/KISS).
    """

    def __init__(self, request_model: str) -> None:
        self.request_model = request_model
        self.msg_id: Optional[str] = None
        self.started = False
        # Anthropic content-block indices are assigned in first-appearance order
        # (text first if any, then each tool_call) so a tools-only stream never
        # leaves a phantom empty text block at index 0.
        self._next_index = 0
        self.text_index: Optional[int] = None
        self.text_open = False
        self.tool_index: Dict[int, int] = {}  # openai tool_call index -> block idx
        self.tool_open: Dict[int, bool] = {}  # block idx -> open?
        self.finish_reason: Optional[str] = None
        self.usage: Optional[dict] = None
        self.finalized = False

    @staticmethod
    def _event(event_type: str, data: dict) -> str:
        """Format one Anthropic SSE event (``event:`` + ``data:`` + blank line)."""
        return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    def _ensure_start(self, chat_id: Any) -> List[str]:
        """Emit ``message_start`` exactly once, on the first chunk seen."""
        if self.started:
            return []
        self.started = True
        self.msg_id = _derive_anthropic_id(chat_id, "msg_")
        return [
            self._event(
                "message_start",
                {
                    "type": "message_start",
                    "message": {
                        "id": self.msg_id,
                        "type": "message",
                        "role": "assistant",
                        "model": self.request_model,
                        "content": [],
                        "stop_reason": None,
                        "stop_sequence": None,
                        # OpenAI sends no prompt usage up-front; the final value is
                        # reported in message_delta (design §4.1 / R1).
                        "usage": {"input_tokens": 0, "output_tokens": 0},
                    },
                },
            )
        ]

    def _open_text_block(self) -> List[str]:
        if self.text_index is not None:
            return []
        self.text_index = self._next_index
        self._next_index += 1
        self.text_open = True
        return [
            self._event(
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": self.text_index,
                    "content_block": {"type": "text", "text": ""},
                },
            )
        ]

    def feed(self, chunks: Any) -> List[str]:
        """Translate one or more OpenAI chunk dicts into Anthropic SSE events."""
        events: List[str] = []
        for chunk in chunks:
            events.extend(self._process(chunk))
        return events

    def _process(self, chunk: Any) -> List[str]:
        if not isinstance(chunk, dict):
            return []
        events: List[str] = self._ensure_start(chunk.get("id"))

        choices = chunk.get("choices")
        if isinstance(choices, list):
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                delta = choice.get("delta")
                if isinstance(delta, dict):
                    content = delta.get("content")
                    if isinstance(content, str) and content:
                        events.extend(self._open_text_block())
                        events.append(
                            self._event(
                                "content_block_delta",
                                {
                                    "type": "content_block_delta",
                                    "index": self.text_index,
                                    "delta": {"type": "text_delta", "text": content},
                                },
                            )
                        )
                    events.extend(self._process_tool_calls(delta.get("tool_calls")))
                if choice.get("finish_reason") is not None:
                    # Save it; message_delta + message_stop wait for usage / end.
                    self.finish_reason = choice["finish_reason"]

        usage = chunk.get("usage")
        if isinstance(usage, dict) and usage:
            self.usage = usage
            events.extend(self._finalize())
        return events

    def _process_tool_calls(self, tool_calls: Any) -> List[str]:
        """Map OpenAI ``delta.tool_calls`` -> Anthropic ``tool_use`` blocks.

        The FIRST fragment for a given tool_call index opens the block (``id`` +
        ``name`` are known there); each subsequent ``function.arguments`` fragment
        is streamed as an ``input_json_delta`` (OpenAI already emits partial JSON,
        so the fragments concatenate into a valid ``input`` — design §4.1 / R2).
        """
        events: List[str] = []
        if not isinstance(tool_calls, list):
            return events
        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue
            openai_index = tc.get("index", 0)
            if not isinstance(openai_index, int):
                openai_index = 0
            func = tc.get("function") if isinstance(tc.get("function"), dict) else {}
            if openai_index not in self.tool_index:
                block_index = self._next_index
                self._next_index += 1
                self.tool_index[openai_index] = block_index
                self.tool_open[block_index] = True
                events.append(
                    self._event(
                        "content_block_start",
                        {
                            "type": "content_block_start",
                            "index": block_index,
                            "content_block": {
                                "type": "tool_use",
                                "id": tc.get("id", "") or "",
                                "name": func.get("name", "") or "",
                                "input": {},
                            },
                        },
                    )
                )
            block_index = self.tool_index[openai_index]
            part = func.get("arguments")
            if isinstance(part, str) and part:
                events.append(
                    self._event(
                        "content_block_delta",
                        {
                            "type": "content_block_delta",
                            "index": block_index,
                            "delta": {
                                "type": "input_json_delta",
                                "partial_json": part,
                            },
                        },
                    )
                )
        return events

    def finish(self) -> List[str]:
        """Flush the terminal events at end-of-stream (idempotent)."""
        events: List[str] = []
        if not self.started:
            # Degenerate/empty upstream: still emit a well-formed envelope.
            events.extend(self._ensure_start(None))
        events.extend(self._finalize())
        return events

    def _finalize(self) -> List[str]:
        if self.finalized:
            return []
        self.finalized = True
        events: List[str] = []
        if self.text_open:
            events.append(
                self._event(
                    "content_block_stop",
                    {"type": "content_block_stop", "index": self.text_index},
                )
            )
            self.text_open = False
        for block_index in sorted(self.tool_open):
            if self.tool_open[block_index]:
                events.append(
                    self._event(
                        "content_block_stop",
                        {"type": "content_block_stop", "index": block_index},
                    )
                )
                self.tool_open[block_index] = False
        usage = self.usage if isinstance(self.usage, dict) else {}
        events.append(
            self._event(
                "message_delta",
                {
                    "type": "message_delta",
                    "delta": {
                        "stop_reason": _openai_finish_to_anthropic(self.finish_reason),
                        "stop_sequence": None,
                    },
                    "usage": {
                        "input_tokens": int(usage.get("prompt_tokens") or 0),
                        "output_tokens": int(usage.get("completion_tokens") or 0),
                    },
                },
            )
        )
        events.append(self._event("message_stop", {"type": "message_stop"}))
        return events


def openai_chunk_stream_to_anthropic_events(
    chunks: Any, request_model: str
) -> Iterator[str]:
    """Translate an iterable of OpenAI chat-completion CHUNK DICTS into the
    Anthropic Messages SSE event sequence (Tahap 2 inbound stream).

    Pure (no I/O, no DB). ``[DONE]`` / malformed frames must be stripped by the
    caller (:func:`backend.gateway.router._iter_openai_sse_chunks`) — only decoded
    chunk dicts are fed here. ``data: [DONE]`` is ignored because Anthropic closes
    a stream with ``message_stop`` instead.

    :param chunks: iterable of OpenAI chunk dicts.
    :param request_model: the client-requested model ref (echoed in
      ``message_start.message.model``, same as the non-streaming envelope).
    :yields: SSE event strings (``event: X\\ndata: {json}\\n\\n``).
    """
    encoder = _AnthropicSseEncoder(request_model)
    for event in encoder.feed(chunks):
        yield event
    for event in encoder.finish():
        yield event


def anthropic_error_sse_frame(error: dict) -> str:
    """One Anthropic-shaped ``event: error`` SSE frame (mid-stream failure, §5.2).

    ``error`` is the inner ``{"type","message","code"}`` dict only (never a secret
    dump — the caller passes the already-safe UpstreamError envelope).
    """
    return (
        "event: error\n"
        + f"data: {json.dumps({'type': 'error', 'error': error}, ensure_ascii=False)}"
        + "\n\n"
    )


def translate_error(format: str, status_code: int, raw_body: Any) -> dict:
    """Map an upstream error body to an OpenAI error envelope.

    :param format: canonical upstream format (used for provider-specific parsing).
    :param status_code: upstream HTTP status code.
    :param raw_body: parsed JSON error body (or string / None).
    :returns: ``{"error": {"message", "type", "code"}}``.
    """
    if format == "anthropic" and isinstance(raw_body, dict):
        err = raw_body.get("error", {}) or {}
        msg = err.get("message") or f"anthropic upstream error (HTTP {status_code})"
        etype = err.get("type") or "upstream_error"
        return _error(msg, etype, f"upstream_{status_code}")

    msg: str
    if isinstance(raw_body, dict):
        err = raw_body.get("error")
        if isinstance(err, dict) and err.get("message"):
            msg = str(err["message"])
        elif isinstance(err, str):
            msg = err
        else:
            msg = str(raw_body)
    elif isinstance(raw_body, str) and raw_body:
        msg = raw_body
    else:
        msg = f"upstream error (HTTP {status_code})"
    return _error(msg, "upstream_error", f"upstream_{status_code}")


# Pydantic **v1** shape validation for the inbound Anthropic ``/v1/messages``
# surface (mirrors ``responses.ResponsesRequest`` / ``router.ChatCompletionRequest``).
# Only the documented envelope fields are declared; ``extra="allow"`` keeps the
# raw dict intact for :func:`anthropic_messages_request_to_openai_chat`, which
# performs the semantic (refuse-or-map) validation.
from pydantic import BaseModel as _BaseModel  # noqa: E402


class AnthropicMessagesRequest(_BaseModel):
    """Anthropic Messages API request shape (Pydantic **v1**)."""

    model: str
    messages: Optional[list] = None
    max_tokens: Optional[int] = None
    stream: Optional[bool] = None

    class Config:
        extra = "allow"


__all__ = [
    "FORMAT_ALIASES",
    "format_for_provider_type",
    "translate_request",
    "translate_response",
    "translate_error",
    "AnthropicMessagesRequest",
    "anthropic_messages_request_to_openai_chat",
    "openai_chat_response_to_anthropic_messages",
    "openai_chunk_stream_to_anthropic_events",
    "anthropic_error_sse_frame",
    "ANTHROPIC_STREAMING_UNSUPPORTED_CODE",
    "ANTHROPIC_UNSUPPORTED_FIELD_CODE",
    "ANTHROPIC_MISSING_MODEL_CODE",
    "ANTHROPIC_INVALID_REQUEST_CODE",
]

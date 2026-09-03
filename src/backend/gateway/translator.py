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
from typing import Any, Dict, List, Optional

from backend.log import log_warning

logger = logging.getLogger(__name__)

# Default max_tokens injected when an upstream requires it but the client (OpenAI
# format) did not supply one. 4096 is a sane non-streaming default.
_DEFAULT_MAX_TOKENS = 4096

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

    return {
        "url_path": "/v1/messages",
        "headers_extra": {"anthropic-version": "2023-06-01"},
        "body": body,
    }


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


__all__ = [
    "FORMAT_ALIASES",
    "format_for_provider_type",
    "translate_request",
    "translate_response",
    "translate_error",
]

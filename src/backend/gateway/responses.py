"""OpenAI **Responses API** ⇄ chat-completions translation (pure helpers).

aigate's pipeline speaks chat-completions; codex ≥ 0.122 and the Rust
open-interpreter only speak the Responses API (``POST /v1/responses``,
``wire_api = "chat"`` was removed — openai/codex discussion #7782). This module
bridges the two shapes with PURE functions so they are unit-testable without
HTTP:

* :func:`responses_request_to_chat` — Responses request body → chat payload
  (fed straight into the existing resolve → adapter/combo → usage pipeline).
* :func:`chat_response_to_responses` — chat response → Responses envelope.

Shape references (read 2026-09-05):
- https://platform.openai.com/docs/api-reference/responses/create
- https://platform.openai.com/docs/api-reference/responses/object
- https://platform.openai.com/docs/guides/response-streaming (event names for
  the NEXT round; see ``RESPONSES_STREAMING_TODO`` below).

Hard rules (mirrors translator.py style):
- Pydantic **v1** only; pure Python (Termux-safe, no new deps).
- Anything that cannot be represented FAITHFULLY raises
  :class:`~backend.gateway.errors.GatewayError` 400 with a stable machine code
  (``responses_unsupported_field`` / ``responses_streaming_unsupported``).
  A silently-dropped tool/function item would corrupt an agent loop instead of
  failing loudly — refusal is the contract.
- Errors keep the EXISTING OpenAI error envelope ``{"error":{message,type,code}}``
  (decision: codex and other Responses clients parse the same envelope on both
  APIs; a Responses-shaped error body would be a second, divergent contract).
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from backend.gateway.errors import GatewayError
from backend.log import log_warning

LOG_SOURCE = "backend.gateway.responses"

# Machine code (stable, contract) for any field/item we refuse to translate.
UNSUPPORTED_FIELD_CODE = "responses_unsupported_field"
# Machine code for stream:true — non-streaming round only.
STREAMING_UNSUPPORTED_CODE = "responses_streaming_unsupported"

# NEXT ROUND (streaming) seam: when ``stream:true`` is implemented, the route
# must emit the Responses SSE event sequence over the existing chat SSE from
# provider_adapter.chat_completion_stream:
#   response.created → response.output_item.added (message) →
#   response.content_part.added → response.output_text.delta (per chunk) →
#   response.output_text.done → response.completed
# (https://platform.openai.com/docs/guides/response-streaming).
RESPONSES_STREAMING_TODO = (
    "Responses API streaming is not implemented yet; use stream:false "
    "(non-streaming /v1/responses is supported)"
)

# Top-level Responses fields that change semantics if dropped silently (tools,
# server-side state, structured outputs, background runs) → REFUSE loudly.
# WHY: a silently-dropped tool_choice/function_call makes an agent loop corrupt
# instead of failing; previous_response_id/conversation imply server state the
# stateless gateway does not have.
_UNSUPPORTED_TOP_LEVEL = (
    "tools",
    "tool_choice",
    "functions",  # legacy alias of tools
    "function_call",  # legacy alias of a function_call item
    "parallel_tool_calls",
    "reasoning",
    "background",
    "text",  # structured outputs / output configuration
    "previous_response_id",  # server-side conversation state
    "conversation",  # conversation object/param
    "max_tool_calls",  # only meaningful with tools
)

# Top-level Responses fields that are harmless to drop for a stateless
# pass-through gateway (telemetry / storage hints / client-side extras the
# upstream chat call never sees). Dropped, NOT forwarded blindly.
_DROPPED_HARMLESS_KEYS = (
    "store",  # gateway is stateless regardless
    "metadata",
    "user",
    "service_tier",
    "safety_identifier",
    "prompt_cache_key",
    "prompt",  # OpenAI prompt-template refs are not resolvable here; input is
    "truncation",  # no server-side state to truncate
    "include",  # asks for extra output data we never synthesize
    "top_logprobs",
    "seed",
    "modalities",
    "audio",
    "video",
    "web_search_options",
)

# Chat params passed through verbatim when present (explicit whitelist —
# everything unknown-but-harmless is dropped, not forwarded).
_PASS_THROUGH_PARAMS = ("temperature", "top_p", "stop")

# Responses input item types that are messages (translatable).
_MESSAGE_ITEM_TYPES = frozenset({"message"})
# Responses content part types inside a message we can map to chat parts.
_TEXT_PART_TYPES = frozenset({"input_text", "output_text", "text"})


class ResponsesRequest(BaseModel):
    """Pydantic **v1** shape validation for ``POST /v1/responses``.

    Only the documented envelope fields are declared; ``extra="allow"`` keeps
    the raw dict intact for :func:`responses_request_to_chat`, which performs
    the semantic (refuse-or-map) validation.
    """

    model: str
    input: Optional[Any] = None
    instructions: Optional[str] = None
    max_output_tokens: Optional[int] = None
    stream: Optional[bool] = None

    class Config:
        extra = "allow"


def _error(message: str, code: str) -> GatewayError:
    """400 GatewayError with a stable machine code (OpenAI envelope)."""
    return GatewayError(400, message, "invalid_request_error", code)


def _refuse(field: str, why: str = "cannot be translated to chat-completions") -> GatewayError:
    """Build the standard refusal for an unsupported Responses field/item."""
    return _error(
        f"field '{field}' {why}; /v1/responses only supports the non-streaming "
        f"message subset in this build",
        UNSUPPORTED_FIELD_CODE,
    )


def _map_role(role: Any) -> str:
    """Responses message role → chat role.

    ``developer`` maps to ``system``: the chat pipeline (incl. the anthropic/
    gemini translators) treats only ``system`` as instruction-level, so mapping
    developer→system keeps the instruction hierarchy faithful.
    """
    if not isinstance(role, str) or not role:
        raise _refuse("input[].role", "must be a non-empty string")
    lowered = role.lower()
    if lowered == "developer":
        return "system"
    if lowered in ("system", "user", "assistant", "tool"):
        return lowered
    raise _refuse(f"input[].role '{role}'", "is not a supported chat role")


def _content_part_to_chat(part: Any) -> Dict[str, Any]:
    """One Responses content part → one chat content part (or refuse).

    Supported: ``input_text``/``output_text``/``text`` → ``{"type":"text"}``;
    ``input_image`` with an ``image_url`` → chat ``image_url`` form (trivially
    supported). ``input_image.file_id`` and ``input_file`` need OpenAI file
    storage the gateway cannot resolve → refuse.
    """
    if isinstance(part, str):
        return {"type": "text", "text": part}
    if not isinstance(part, dict):
        raise _refuse("input[].content[] part", "must be an object or string")
    ptype = part.get("type")
    if ptype in _TEXT_PART_TYPES:
        text = part.get("text")
        if not isinstance(text, str):
            raise _refuse("input[].content[].text", "must be a string")
        return {"type": "text", "text": text}
    if ptype == "input_image":
        image_url = part.get("image_url")
        if isinstance(image_url, str) and image_url:
            # WHY: chat format nests url/detail in an object
            # (https://platform.openai.com/docs/api-reference/chat/create).
            return {"type": "image_url", "image_url": {"url": image_url}}
        # file_id-only images need OpenAI file storage → not representable.
        raise _refuse("input_image without 'image_url'", "requires a URL or data URL")
    raise _refuse(f"input[].content[] type '{ptype}'", "is not translatable")


def _message_item_to_chat(item: Dict[str, Any]) -> Dict[str, Any]:
    """A Responses ``message`` item → a chat message dict.

    Text parts are joined into a plain string when no images are present
    (maximizes upstream compatibility); mixed text+image keeps the chat
    content-part array form.
    """
    role = _map_role(item.get("role"))
    content = item.get("content")
    if content is None:
        raise _refuse("input[].content", "is required for message items")
    if isinstance(content, str):
        return {"role": role, "content": content}
    if not isinstance(content, list):
        raise _refuse("input[].content", "must be a string or an array")
    parts = [_content_part_to_chat(p) for p in content]
    has_image = any(p.get("type") == "image_url" for p in parts)
    if not has_image:
        # WHY joined with "": Responses text parts are contiguous fragments
        # of one message (no implicit separators in the API shape).
        return {"role": role, "content": "".join(p.get("text", "") for p in parts)}
    return {"role": role, "content": parts}


def responses_request_to_chat(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Responses request body → chat-completions payload (pure, raises GatewayError).

    Mapping (https://platform.openai.com/docs/api-reference/responses/create):
    ``model`` unchanged (aigate refs resolve downstream) · ``instructions`` →
    leading ``system`` message · ``input`` string → one ``user`` message ·
    ``input`` items → ``messages`` · ``max_output_tokens`` → ``max_tokens`` ·
    ``temperature``/``top_p``/``stop`` pass through · harmless keys dropped.

    :raises GatewayError: 400 ``responses_streaming_unsupported`` for
      ``stream:true`` (non-streaming round); 400 ``responses_unsupported_field``
      for tools/functions/reasoning/state/structured-output fields and items.
    """
    # stream:true — refuse BEFORE anything else (clear seam for next round).
    if payload.get("stream") is True:
        log_warning(
            "responses request asked for stream:true; streaming is not "
            "implemented yet",
            source=LOG_SOURCE,
        )
        raise _error(RESPONSES_STREAMING_TODO, STREAMING_UNSUPPORTED_CODE)

    # Refuse fields whose silent drop would corrupt an agent loop.
    for field in _UNSUPPORTED_TOP_LEVEL:
        if payload.get(field) is not None:
            log_warning(
                f"responses request carries unsupported field '{field}'; "
                f"refusing explicitly",
                source=LOG_SOURCE,
            )
            raise _refuse(field)

    messages: List[Dict[str, Any]] = []

    instructions = payload.get("instructions")
    if isinstance(instructions, str) and instructions:
        messages.append({"role": "system", "content": instructions})
    elif instructions is not None and not isinstance(instructions, str):
        raise _refuse("instructions", "must be a string when present")

    item_input = payload.get("input")
    if isinstance(item_input, str):
        if item_input:
            messages.append({"role": "user", "content": item_input})
    elif isinstance(item_input, list):
        for item in item_input:
            if not isinstance(item, dict):
                raise _refuse("input[] item", "must be an object")
            itype = item.get("type", "message")  # EasyInputMessage omits type
            if itype not in _MESSAGE_ITEM_TYPES:
                # function_call / function_call_output / reasoning / tool
                # calls / item_reference / ... — never silently dropped.
                raise _refuse(f"input item type '{itype}'")
            messages.append(_message_item_to_chat(item))
    elif item_input is None:
        pass  # instructions-only requests are legal
    else:
        raise _refuse("input", "must be a string or an array of items")

    if not messages:
        raise _error(
            "either 'input' or 'instructions' must provide at least one message",
            "missing_input",
        )

    chat: Dict[str, Any] = {
        "model": payload.get("model"),
        "messages": messages,
    }
    # max_output_tokens → max_tokens (Responses name for the same limit).
    max_tokens = payload.get("max_output_tokens")
    if max_tokens is not None:
        if not isinstance(max_tokens, int) or isinstance(max_tokens, bool):
            raise _refuse("max_output_tokens", "must be an integer")
        chat["max_tokens"] = max_tokens
    for key in _PASS_THROUGH_PARAMS:
        if payload.get(key) is not None:
            chat[key] = payload[key]
    # Unknown-but-harmless keys (incl. _DROPPED_HARMLESS_KEYS) are simply not
    # copied — the whitelist above decides what reaches upstream.
    return chat


def _derive_id(chat_id: Any, prefix: str) -> str:
    """Derive a ``resp_``/``msg_`` id from the chat id (fallback: random hex).

    WHY strip ``chatcmpl-``: keeps the correlation suffix visible
    (chatcmpl-abc → resp_abc) without a double prefix.
    """
    if isinstance(chat_id, str) and chat_id:
        base = chat_id[len("chatcmpl-"):] if chat_id.startswith("chatcmpl-") else chat_id
        return f"{prefix}{base}"
    return f"{prefix}{uuid.uuid4().hex[:24]}"


def _finish_to_status(finish_reason: Optional[str]) -> tuple[str, Optional[dict]]:
    """chat ``finish_reason`` → (response status, incomplete_details).

    ``length``/``content_filter`` map to the documented incomplete reasons
    (https://platform.openai.com/docs/api-reference/responses/object —
    ``incomplete_details.reason``).
    """
    if finish_reason == "length":
        return "incomplete", {"reason": "max_output_tokens"}
    if finish_reason == "content_filter":
        return "incomplete", {"reason": "content_filter"}
    return "completed", None


def chat_response_to_responses(
    chat: Dict[str, Any], request_model: str
) -> Dict[str, Any]:
    """Chat response dict → Responses envelope (pure).

    ``model`` echoes the REQUEST ref (``provider:...``/``combo:...``/bare id),
    not the upstream id — clients match on the ref they sent. Usage maps
    prompt/completion/total → input/output/total tokens.
    """
    chat_id = chat.get("id")
    resp_id = _derive_id(chat_id, "resp_")
    created = chat.get("created")
    if not isinstance(created, int):
        created = int(time.time())

    choices = chat.get("choices")
    first: Dict[str, Any] = choices[0] if isinstance(choices, list) and choices else {}
    if not isinstance(first, dict):
        first = {}
    message = first.get("message")
    if not isinstance(message, dict):
        message = {}
    text = message.get("content")
    if not isinstance(text, str):
        text = "" if text is None else str(text)

    status, incomplete_details = _finish_to_status(first.get("finish_reason"))
    item_status = "completed" if status == "completed" else "incomplete"

    output: List[Dict[str, Any]] = [
        {
            "type": "message",
            "id": _derive_id(chat_id, "msg_"),
            "role": "assistant",
            "status": item_status,
            "content": [{"type": "output_text", "text": text, "annotations": []}],
        }
    ]

    usage = chat.get("usage")
    if not isinstance(usage, dict):
        usage = {}
    return {
        "id": resp_id,
        "object": "response",
        "created": created,
        "status": status,
        "incomplete_details": incomplete_details,
        "model": request_model,
        "output": output,
        "usage": {
            "input_tokens": int(usage.get("prompt_tokens") or 0),
            "output_tokens": int(usage.get("completion_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
        },
    }


__all__ = [
    "UNSUPPORTED_FIELD_CODE",
    "STREAMING_UNSUPPORTED_CODE",
    "RESPONSES_STREAMING_TODO",
    "ResponsesRequest",
    "responses_request_to_chat",
    "chat_response_to_responses",
]

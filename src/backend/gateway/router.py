"""OpenAI-compatible gateway router (FastAPI ``APIRouter``).

Exposes:

* ``POST /v1/chat/completions`` — validate the body via a Pydantic **v1**
  :class:`ChatCompletionRequest`, then forward the RAW received dict (not the
  validated model) to :mod:`backend.gateway.provider_adapter` so upstream gets
  the exact payload (pass-through of arbitrary OpenAI fields). The request
  model uses ``extra="allow"`` so unknown OpenAI fields are preserved.
  ``stream:true`` is proxied as an SSE ``text/event-stream`` for OpenAI-format
  (pass-through) upstreams incl. combos; translated formats (anthropic/gemini)
  return a ``streaming_unsupported_format`` 400 (per-chunk SSE translation is a
  known, documented limitation).
* ``POST /v1/responses`` — OpenAI **Responses API** surface (codex ≥ 0.122
  dropped ``wire_api = "chat"``). The body is translated to a chat-completions
  payload by :mod:`backend.gateway.responses` and run through the SAME
  resolution/adapter/usage/logging pipeline as ``/v1/chat/completions``; the
  chat response is translated back into the Responses envelope. NON-STREAMING
  ONLY: ``stream:true`` returns a ``responses_streaming_unsupported`` 400, and
  non-representable fields (tools, function calls, reasoning, server-side
  state, structured outputs) return ``responses_unsupported_field`` 400s.
* ``GET /v1/models`` — list available models derived from ``ProviderModel``
  rows (id ``provider:<provider>:<model_id>``) plus ENABLED ``Combo`` rows
  (id ``combo:<name>``), in OpenAI ``{"object":"list","data":[...]}`` shape.
  Listing combos makes them discoverable/selectable by OpenAI-compatible CLIs.

Hard rule R12 / ADR-011: every failure path logs to ``LogEntry`` via
``backend.log`` before raising. The adapter re-raises its own ``UpstreamError``
(which is already logged) as-is.

B5.6 / PRD §2.4.3 (Log Permintaan debug): the endpoint additionally measures
the request duration and — when request logging is ENABLED via the ``Setting``
key ``request_log_enabled`` (default ``'false'``) — persists a ``RequestLog``
row (endpoint id, model, ts, duration_ms, truncated header/body dump with
secret headers redacted, response summary) on both success and failure.
Recording is fail-open: a logging failure never alters the client response.
UsageRecord (B5.5) is recorded regardless of the debug gate.

All errors surface as the OpenAI error envelope via
:class:`backend.gateway.errors.GatewayError` + the handler registered in
``backend.server``.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import List, Optional, Tuple, Union

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

from backend.config import settings as _settings
from backend.config.db import SessionLocal
from backend.combo_routing import (
    build_candidates,
    execute_combo,
    resolve_combo_stream_target,
)
from backend.gateway import provider_adapter
from backend.gateway.errors import GatewayError, UpstreamError
from backend.gateway import responses as _responses
from backend.gateway.resolver import ResolvedTarget, TargetNotFound, resolve_target
from backend.gateway.translator import (
    ANTHROPIC_INVALID_REQUEST_CODE,
    ANTHROPIC_MISSING_MODEL_CODE,
    AnthropicMessagesRequest,
    _AnthropicSseEncoder,
    _extract_text,
    anthropic_error_sse_frame,
    anthropic_messages_request_to_openai_chat,
    format_for_provider_type,
    openai_chat_response_to_anthropic_messages,
)
from backend.log import log_error_exc, log_info, log_warning, log_warning_exc
from backend.models import (
    Combo,
    Endpoint,
    EndpointBinding,
    Provider,
    ProviderModel,
    ProxyPool,
    RequestLog,
)
from backend.gateway import token_saver as _token_saver
from backend import proxy_selector
from backend import usage as _usage
from backend.oauth import (
    CONNECTION_ID_HEADER,
    select_provider_credential_with_account,
)


class ChatCompletionRequest(BaseModel):
    """Pydantic **v1** validation for ``POST /v1/chat/completions``.

    Only the documented fields are declared; everything else passes through
    ``extra="allow"`` so an arbitrary OpenAI payload reaches the upstream
    verbatim.
    """

    model: str
    messages: Optional[List[dict]] = None
    stream: Optional[bool] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

    class Config:
        extra = "allow"


router = APIRouter()

# --------------------------------------------------------------------------- #
# B5.6 request-logging (debug) constants — decisions documented in receipt
# --------------------------------------------------------------------------- #
# Gate: dedicated Setting key (NOT dev_mode) so debug logging is independently
# switchable; default 'false' (seeded in backend.config.settings).
REQUEST_LOG_SETTING_KEY = "request_log_enabled"
# Hard cap for the RequestLog.request / .response text columns (~8KB) so a
# chatty debug session cannot grow the DB unboundedly; a marker notes the
# omitted size when truncation happens.
REQUEST_LOG_MAX_CHARS = 8192
# Preview length for the assistant answer inside the response summary.
RESPONSE_PREVIEW_CHARS = 500
# Header names whose values must NEVER land in the debug dump (skill rule:
# never log secrets/keys — ADR-007 plaintext covers the config DB, not logs).
_SECRET_HEADERS = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "x-api-key",
        "api-key",
        "openai-api-key",
        "x-goog-api-key",
    }
)
_REDACTED = "***REDACTED***"


@router.post("/v1/chat/completions")
async def chat_completions(request: Request) -> Response:
    """OpenAI-compatible chat completion proxy (non-streaming OR SSE stream).

    Returns a JSON dict for a normal request, or a ``StreamingResponse``
    (``text/event-stream``) when the client asked for ``stream:true`` against an
    OpenAI-format upstream/combo. FastAPI passes a ``Response`` instance through
    untouched, so the streaming case bypasses JSON serialization.

    B5.6 wrapper: times the request and persists a ``RequestLog`` debug row
    (success OR error path) when ``request_log_enabled`` is 'true'. The
    recording itself is fail-open — see :func:`_record_request_log_safe`.
    """
    ctx: dict = {
        "endpoint_id": None,  # resolved Endpoint id (nullable)
        "model": None,  # request model ref, upgraded to upstream_model
        "payload": None,  # parsed body (for the debug dump)
        "saved_bytes": None,  # token_saver input savings (None = not applied)
    }
    t0 = time.monotonic()
    try:
        result = await _handle_chat_completion(request, ctx)
    except GatewayError as exc:
        _record_request_log_safe(
            ctx, request, t0, error_envelope=exc.envelope, http_status=exc.status_code
        )
        raise
    except Exception as exc:  # noqa: BLE001 - record debug row, then re-raise
        _record_request_log_safe(
            ctx, request, t0, error_envelope=None, http_status=500, exc=exc
        )
        raise
    _record_request_log_safe(ctx, request, t0, result=result, http_status=200)
    return result


async def _parse_object_body(request: Request) -> dict:
    """Parse + basic-shape-validate a JSON object request body.

    Shared by ``/v1/chat/completions`` and ``/v1/responses`` so both surfaces
    answer malformed bodies with the SAME OpenAI envelope (invalid_json /
    invalid_body). Raises GatewayError(400).
    """
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001 - malformed body
        log_warning(
            "received malformed JSON request body",
            source="backend.gateway.router",
        )
        raise GatewayError(
            400, "invalid JSON request body", "invalid_request_error", "invalid_json"
        )

    if not isinstance(payload, dict):
        log_warning(
            "request body must be a JSON object",
            source="backend.gateway.router",
        )
        raise GatewayError(
            400,
            "request body must be a JSON object",
            "invalid_request_error",
            "invalid_body",
        )
    return payload


def _preferred_account_id(request: Request) -> Optional[int]:
    """Read the optional ``x-connection-id`` account-pin header (9router parity).

    Returns the account id, or ``None`` when the header is absent / blank / not
    an integer — an unusable pin must NEVER error the request; the provider's
    routing strategy simply applies. Whether the id belongs to the resolved
    provider is enforced by the selection engine (also fail-safe).
    """
    raw = request.headers.get(CONNECTION_ID_HEADER)
    if raw is None or not raw.strip():
        return None
    try:
        return int(raw.strip())
    except ValueError:
        log_warning(
            f"ignoring non-integer '{CONNECTION_ID_HEADER}' header",
            source="backend.gateway.router",
            context={"header": CONNECTION_ID_HEADER, "value": raw[:32]},
        )
        return None


async def _handle_chat_completion(request: Request, ctx: dict) -> Union[dict, Response]:
    """Validate + route + forward one chat completion (raises GatewayError).

    Thin HTTP-surface wrapper: parses the body + reads the request headers, then
    delegates to :func:`run_chat_completion` (the shared pipeline core). Kept as
    a separate function so the ``/v1/chat/completions`` contract is byte-for-byte
    unchanged while the Chat Playground router (B8.B6.1) drives the SAME pipeline
    in-process (no HTTP loopback to a running server).
    """
    payload = await _parse_object_body(request)
    return await run_chat_completion(
        payload,
        ctx,
        request=request,
        endpoint_name=request.headers.get("x-aigate-endpoint"),
        preferred_account_id=_preferred_account_id(request),
    )


async def run_chat_completion(
    payload: dict,
    ctx: dict,
    *,
    request: Optional[Request] = None,
    endpoint_name: Optional[str] = None,
    preferred_account_id: Optional[int] = None,
) -> Union[dict, Response]:
    """Shared chat-completion pipeline core (validate -> resolve -> adapter/stream).

    Extracted verbatim from the former ``_handle_chat_completion`` body so an
    in-process caller (the Chat Playground router) can reuse the exact gateway
    machinery — Token Saver hook, resolver/``combo:`` routing, provider adapter,
    usage recording (B5.5) and SSE streaming — WITHOUT re-implementing an LLM
    engine and WITHOUT an HTTP loopback to a live server (J6). The HTTP surface
    passes ``request`` + ``endpoint_name`` + ``preferred_account_id`` parsed from
    its headers; an internal caller passes only a built ``payload`` + ``ctx`` (and
    ``endpoint_name=None``), so the endpoint-binding/access-control branch is
    never reached.

    Returns a JSON dict (non-streaming) or a ``StreamingResponse`` (SSE) when the
    payload requests ``stream:true`` against an OpenAI-format target/combo.
    Raises :class:`GatewayError` on any validation / resolution failure.
    """
    # `model` must be a non-empty string in the RAW payload (the validated
    # model coerces types, but we forward the raw dict, so enforce str here).
    model = payload.get("model")
    if not isinstance(model, str) or not model:
        log_warning(
            "field 'model' is required and must be a string",
            source="backend.gateway.router",
        )
        raise GatewayError(
            400, "field 'model' is required", "invalid_request_error", "missing_model"
        )

    # B5.6: stash what the RequestLog debug row needs (raw body + model ref).
    ctx["payload"] = payload
    ctx["model"] = model

    # Full Pydantic-v1 validation (pass-through of extra fields is allowed).
    try:
        ChatCompletionRequest.parse_obj(payload)
    except ValidationError as exc:
        log_warning(
            f"invalid chat completion request: {exc}",
            source="backend.gateway.router",
        )
        raise GatewayError(
            400, "field 'model' is required", "invalid_request_error", "missing_model"
        )

    # NOTE: ``stream:true`` is NOT rejected here any more. Streaming is decided
    # AFTER the target is resolved (we need its ``format``): OpenAI-format
    # upstreams/combos are proxied as SSE; translated formats get a
    # ``streaming_unsupported_format`` 400. See ``_streaming_response``.

    # ADR-008 / task B2.5: named Endpoint selected at request time via the
    # X-Aigate-Endpoint header. When present, routing + proxy binding are
    # driven by the Endpoint's EndpointBinding instead of the model reference.
    # An in-process caller (Chat Playground) never sets this -> the branch below
    # is HTTP-surface only and ``request`` is guaranteed non-None when taken.
    if endpoint_name:
        # ADR-013: apply the bound Provider's Token Saver hook to the payload
        # BEFORE forwarding (endpoint -> provider binding; combos use their first
        # candidate member). Fail-open: never raises; original payload returned
        # on any error / no provider / all toggles off. B5.6: also capture the
        # input-side savings estimate for the UsageRecord.
        payload, saved_bytes = _apply_token_saver_for_provider(
            _resolve_saver_provider(endpoint_name=endpoint_name), payload
        )
        # NOTE: ctx["payload"] keeps the ORIGINAL received body (ERD RequestLog
        # "header/isi" = what the client sent); the saver effect is captured by
        # saved_bytes -> UsageRecord.saved_tokens_est, not by re-dumping.
        ctx["saved_bytes"] = saved_bytes
        result = await _route_via_endpoint(endpoint_name, model, payload, request, ctx)
        log_info(
            f"chat completion success via endpoint '{endpoint_name}' "
            f"for model '{model}'",
            source="backend.gateway.router",
            context={"endpoint": endpoint_name, "model": model},
        )
        return result

    try:
        target = resolve_target(
            model, preferred_account_id=preferred_account_id
        )
    except TargetNotFound as exc:
        log_warning(
            f"model reference not found: {model}",
            source="backend.gateway.router",
        )
        raise GatewayError(
            400, str(exc), "invalid_request_error", "model_not_found"
        )

    # B5.6: prefer the real upstream model id in the debug row. A ``combo:``
    # marker resolves upstream_model="" (members are decided inside
    # execute_combo) — the requested combo ref stays; the result upgrades it.
    _upgrade_ctx_model(ctx, target.upstream_model)

    # ADR-013: model-based path — apply the resolved Provider's Token Saver hook
    # to the payload BEFORE forwarding (provider ref / combo first member).
    # Fail-open: original payload returned on any error / no provider / all
    # toggles off. B5.6: capture the input-side savings estimate for the
    # UsageRecord / RequestLog.
    payload, saved_bytes = _apply_token_saver_for_provider(
        _resolve_saver_provider(target=target), payload
    )
    ctx["saved_bytes"] = saved_bytes

    # --- SSE streaming (stream:true) ----------------------------------------
    # Decided AFTER resolution so we know the target's format. A ``combo:``
    # reference streams from its first usable OpenAI-format member; a plain
    # provider streams from itself. Translated formats raise the 400 inside
    # ``_streaming_response``.
    if payload.get("stream") is True:
        if target.combo_used:
            combo_name = model[len("combo:"):]
            try:
                member = resolve_combo_stream_target(combo_name)
            except TargetNotFound as exc:
                log_warning(
                    f"combo model reference not found for streaming: {model}",
                    source="backend.gateway.router",
                )
                raise GatewayError(
                    400, str(exc), "invalid_request_error", "model_not_found"
                )
            if member is None:
                log_warning(
                    "streaming requested for a combo with no OpenAI-compatible "
                    "member",
                    source="backend.gateway.router",
                    context={"combo": combo_name},
                )
                raise _streaming_unsupported_error()
            # B5.6: the debug row carries the streaming member's real model.
            _upgrade_ctx_model(ctx, member.upstream_model)
            return await _streaming_response(
                member, payload, None, ctx, endpoint_id=None
            )
        return await _streaming_response(target, payload, None, ctx, endpoint_id=None)

    # Combo strategy routing (B2.4): a ``combo:`` reference is resolved per its
    # strategy by backend.combo_routing.execute_combo (which itself calls the
    # provider adapter). A plain provider reference goes straight to the adapter.
    if target.combo_used:
        combo_name = model[len("combo:"):]
        # B5.5: ``execute_combo`` records the UsageRecord itself (it knows which
        # member/account actually succeeded). No endpoint on this path.
        # B5.6: thread the token_saver savings estimate (from ctx) through.
        result = await execute_combo(
            combo_name, payload, saved_tokens_est=_saved_tokens_est(ctx)
        )
        # B5.6: prefer the model that actually served (upstream envelope), else
        # keep the requested combo ref.
        _upgrade_ctx_model(ctx, result.get("model"))
    else:
        result = await provider_adapter.chat_completion(target, payload)
        # B5.5: persist usage telemetry (fail-open — never breaks the client).
        # B5.6: + token_saver savings when a saver was applied (None = no saver).
        _record_usage_safe(
            result, target, endpoint_id=None, saved_bytes=ctx.get("saved_bytes")
        )

    # ADR-011 / R12: success path must still land in LogEntry.
    log_info(
        f"chat completion success for model '{model}'",
        source="backend.gateway.router",
        context={"model": model},
    )
    return result


@router.post("/v1/responses")
async def responses_completions(request: Request) -> Response:
    """OpenAI **Responses API** proxy (non-streaming) → chat pipeline.

    codex ≥ 0.122 removed ``wire_api = "chat"`` (openai/codex discussion
    #7782) and only speaks ``POST /v1/responses``
    (https://platform.openai.com/docs/api-reference/responses/create). This
    route translates the request via :mod:`backend.gateway.responses` and then
    runs the EXACT same pipeline as ``/v1/chat/completions`` — token saver,
    Endpoint header routing, resolver, combos, adapter, usage recording — so
    quota/savings/logging keep working. The chat response is translated back
    into the Responses envelope (request ``model`` ref echoed).

    B5.6 wrapper: same timing + ``RequestLog`` behavior as ``chat_completions``.
    """
    ctx: dict = {
        "endpoint_id": None,
        "model": None,
        "payload": None,
        "saved_bytes": None,
    }
    t0 = time.monotonic()
    try:
        result = await _handle_responses(request, ctx)
    except GatewayError as exc:
        _record_request_log_safe(
            ctx, request, t0, error_envelope=exc.envelope, http_status=exc.status_code
        )
        raise
    except Exception as exc:  # noqa: BLE001 - record debug row, then re-raise
        _record_request_log_safe(
            ctx, request, t0, error_envelope=None, http_status=500, exc=exc
        )
        raise
    _record_request_log_safe(ctx, request, t0, result=result, http_status=200)
    return result


async def _handle_responses(request: Request, ctx: dict) -> dict:
    """Validate + translate + route one Responses request (raises GatewayError).

    ``stream:true`` and every non-representable field (tools, function calls,
    reasoning, server-side state, structured outputs) are refused with a
    STABLE machine code by :func:`backend.gateway.responses.responses_request_to_chat`
    — a silently-dropped tool item would corrupt an agent loop instead of
    failing loudly.
    """
    payload = await _parse_object_body(request)

    # `model` must be a non-empty string in the RAW payload (same rule as the
    # chat path: the resolver + adapter consume the raw dict, not coerced types).
    model = payload.get("model")
    if not isinstance(model, str) or not model:
        log_warning(
            "field 'model' is required and must be a string",
            source=_responses.LOG_SOURCE,
        )
        raise GatewayError(
            400, "field 'model' is required", "invalid_request_error", "missing_model"
        )

    ctx["payload"] = payload
    ctx["model"] = model

    # Pydantic v1 shape check (semantic validation happens in the mapper).
    try:
        _responses.ResponsesRequest.parse_obj(payload)
    except ValidationError as exc:
        log_warning(
            f"invalid responses request: {exc}",
            source=_responses.LOG_SOURCE,
        )
        raise GatewayError(
            400,
            "invalid responses request: 'model' must be a string",
            "invalid_request_error",
            "invalid_responses_request",
        )

    # Responses → chat translation; refuses stream:true / unsupported fields.
    chat_payload = _responses.responses_request_to_chat(payload)

    # ADR-008: named Endpoint via X-Aigate-Endpoint header (same path as chat;
    # chat_payload never carries stream, so the endpoint path cannot return an
    # SSE Response here).
    endpoint_name = request.headers.get("x-aigate-endpoint")
    if endpoint_name:
        # ADR-013: apply the bound Provider's Token Saver hook (endpoint ->
        # provider binding; combos use their first candidate member).
        chat_payload, saved_bytes = _apply_token_saver_for_provider(
            _resolve_saver_provider(endpoint_name=endpoint_name), chat_payload
        )
        ctx["saved_bytes"] = saved_bytes
        chat_result = await _route_via_endpoint(
            endpoint_name, model, chat_payload, request, ctx
        )
        if not isinstance(chat_result, dict):
            # Defensive: unreachable while stream is refused; fail loudly (R12)
            # rather than translate a stream we cannot represent.
            raise GatewayError(
                500,
                "endpoint path returned a stream for a non-streaming request",
                "server_error",
                "responses_internal_error",
            )
        log_info(
            f"responses completion success via endpoint '{endpoint_name}' "
            f"for model '{model}'",
            source=_responses.LOG_SOURCE,
            context={"endpoint": endpoint_name, "model": model},
        )
        return _responses.chat_response_to_responses(chat_result, model)

    try:
        target = resolve_target(
            model, preferred_account_id=_preferred_account_id(request)
        )
    except TargetNotFound as exc:
        log_warning(
            f"model reference not found: {model}",
            source=_responses.LOG_SOURCE,
        )
        raise GatewayError(
            400, str(exc), "invalid_request_error", "model_not_found"
        )

    _upgrade_ctx_model(ctx, target.upstream_model)

    # ADR-013: model-based path — apply the resolved Provider's Token Saver hook.
    chat_payload, saved_bytes = _apply_token_saver_for_provider(
        _resolve_saver_provider(target=target), chat_payload
    )
    ctx["saved_bytes"] = saved_bytes

    # Combo strategy routing / plain provider — identical to the chat path so
    # usage recording (B5.5) and savings attribution stay shared.
    if target.combo_used:
        combo_name = model[len("combo:"):]
        chat_result = await execute_combo(
            combo_name, chat_payload, saved_tokens_est=_saved_tokens_est(ctx)
        )
        # B5.6: prefer the model that actually served (upstream envelope), else
        # keep the requested combo ref.
        _upgrade_ctx_model(ctx, chat_result.get("model"))
    else:
        chat_result = await provider_adapter.chat_completion(target, chat_payload)
        _record_usage_safe(
            chat_result, target, endpoint_id=None, saved_bytes=ctx.get("saved_bytes")
        )

    log_info(
        f"responses completion success for model '{model}'",
        source=_responses.LOG_SOURCE,
        context={"model": model},
    )
    return _responses.chat_response_to_responses(chat_result, model)


# --------------------------------------------------------------------------- #
# Anthropic Messages API (POST /v1/messages) — inbound surface for claude-code
# --------------------------------------------------------------------------- #
# Stage 1 = NON-STREAMING. This is the SAME pipeline as ``/v1/responses`` (resolve
# → adapter/combo → usage/logging) with two pure translation shims from
# :mod:`backend.gateway.translator` (Anthropic request↔OpenAI chat). The ONLY
# per-surface deviation: errors render as the **Anthropic** envelope
# ``{"type":"error","error":{...}}`` (claude-code parses that shape) instead of the
# OpenAI envelope — the internal :class:`GatewayError` is unchanged (DRY), only the
# rendering differs. HTTP status mirrors the OpenAI contract (400/401/502..504).
ANTHROPIC_LOG_SOURCE = "backend.gateway.router.anthropic"


@router.post("/v1/messages")
async def messages_completions(request: Request) -> Response:
    """Anthropic Messages API proxy (Stage 1: non-streaming) → chat pipeline.

    ``claude-code`` points ``ANTHROPIC_BASE_URL=<aigate>/v1/messages`` (no litellm
    middleman). The request is translated to OpenAI chat by
    :func:`backend.gateway.translator.anthropic_messages_request_to_openai_chat`
    and run through the EXACT same resolver/adapter/combo/usage/logging pipeline as
    ``/v1/chat/completions`` and ``/v1/responses``; the chat response is translated
    back into the Anthropic Messages envelope.

    B5.6 wrapper: same timing + ``RequestLog`` behavior as
    ``chat_completions``/``responses_completions``. Per-surface deviation: a
    :class:`GatewayError` is caught and rendered as the **Anthropic** error body
    (the global OpenAI handler is deliberately NOT used here) so claude-code parses
    the failure.
    """
    ctx: dict = {
        "endpoint_id": None,
        "model": None,
        "payload": None,
        "saved_bytes": None,
    }
    t0 = time.monotonic()
    try:
        result = await _handle_anthropic_messages(request, ctx)
    except GatewayError as exc:
        # Render Anthropic-shaped, but log the same internal envelope (R12).
        _record_request_log_safe(
            ctx, request, t0, error_envelope=exc.envelope, http_status=exc.status_code
        )
        return _anthropic_error_response(exc)
    except Exception as exc:  # noqa: BLE001 - record debug row, then render Anthropic 500
        _record_request_log_safe(
            ctx, request, t0, error_envelope=None, http_status=500, exc=exc
        )
        return JSONResponse(
            status_code=500,
            content=_anthropic_error_body(
                {
                    "type": "api_error",
                    "message": "internal server error",
                    "code": "internal_error",
                }
            ),
        )
    if isinstance(result, StreamingResponse):
        # Streaming: the SSE body is already committed to the client; usage is
        # recorded after the stream completes (inside _anthropic_stream_response).
        # The debug row records result=None (a Response is not a dict) — mirror chat.
        _record_request_log_safe(ctx, request, t0, result=None, http_status=200)
        return result
    _record_request_log_safe(ctx, request, t0, result=result, http_status=200)
    return JSONResponse(content=result)


async def _handle_anthropic_messages(
    request: Request, ctx: dict
) -> Union[dict, StreamingResponse]:
    """Validate + translate + route one Anthropic Messages request (raises).

    Returns a JSON dict (non-streaming, Stage 1) or a ``StreamingResponse``
    (Anthropic SSE) when the client asked for ``stream:true`` (Tahap 2). Errors on
    the streaming path surface as a ``GatewayError`` before the 200 SSE is
    committed (the generator is primed in :func:`_anthropic_stream_response`).
    """
    payload = await _parse_object_body(request)

    # `model` must be a non-empty string (resolved verbatim downstream, like chat).
    model = payload.get("model")
    if not isinstance(model, str) or not model:
        log_warning(
            "field 'model' is required and must be a string",
            source=ANTHROPIC_LOG_SOURCE,
        )
        raise GatewayError(
            400, "field 'model' is required", "invalid_request_error",
            ANTHROPIC_MISSING_MODEL_CODE,
        )

    ctx["payload"] = payload
    ctx["model"] = model

    # Pydantic v1 shape check (semantic validation in the mapper).
    try:
        AnthropicMessagesRequest.parse_obj(payload)
    except ValidationError as exc:
        log_warning(
            f"invalid anthropic messages request: {exc}",
            source=ANTHROPIC_LOG_SOURCE,
        )
        raise GatewayError(
            400,
            "invalid anthropic messages request",
            "invalid_request_error",
            ANTHROPIC_INVALID_REQUEST_CODE,
        )

    # Anthropic → OpenAI chat translation; refuses thinking. ``stream:true`` is
    # accepted ONLY on the streaming surface (allow_stream) — a stream:false/absent
    # request keeps the exact Stage-1 behavior.
    wants_stream = payload.get("stream") is True
    chat_payload = anthropic_messages_request_to_openai_chat(
        payload, allow_stream=wants_stream
    )

    # ADR-008: named Endpoint via X-Aigate-Endpoint header (same path as chat/responses).
    endpoint_name = request.headers.get("x-aigate-endpoint")

    if wants_stream:
        # Tahap 2 inbound Anthropic SSE: translate the upstream OpenAI stream into
        # the Anthropic SSE envelope (openai-format upstreams only — decision D-A).
        return await _handle_anthropic_messages_stream(
            request, ctx, model, chat_payload, endpoint_name
        )

    if endpoint_name:
        # ADR-013: apply the bound Provider's Token Saver hook (endpoint ->
        # provider binding; combos use their first candidate member).
        chat_payload, saved_bytes = _apply_token_saver_for_provider(
            _resolve_saver_provider(endpoint_name=endpoint_name), chat_payload
        )
        ctx["saved_bytes"] = saved_bytes
        chat_result = await _route_via_endpoint(
            endpoint_name, model, chat_payload, request, ctx
        )
        if not isinstance(chat_result, dict):
            raise GatewayError(
                500,
                "endpoint path returned a stream for a non-streaming request",
                "server_error",
                "anthropic_internal_error",
            )
        log_info(
            f"anthropic completion success via endpoint '{endpoint_name}' "
            f"for model '{model}'",
            source=ANTHROPIC_LOG_SOURCE,
            context={"endpoint": endpoint_name, "model": model},
        )
        return openai_chat_response_to_anthropic_messages(chat_result, model)

    try:
        target = resolve_target(
            model, preferred_account_id=_preferred_account_id(request)
        )
    except TargetNotFound as exc:
        log_warning(
            f"model reference not found: {model}",
            source=ANTHROPIC_LOG_SOURCE,
        )
        raise GatewayError(
            400, str(exc), "invalid_request_error", "model_not_found"
        )

    _upgrade_ctx_model(ctx, target.upstream_model)

    # ADR-013: model-based path — apply the resolved Provider's Token Saver hook.
    chat_payload, saved_bytes = _apply_token_saver_for_provider(
        _resolve_saver_provider(target=target), chat_payload
    )
    ctx["saved_bytes"] = saved_bytes

    # Combo strategy routing / plain provider — identical to the responses path so
    # usage recording (B5.5) and savings attribution stay shared.
    if target.combo_used:
        combo_name = model[len("combo:"):]
        chat_result = await execute_combo(
            combo_name, chat_payload, saved_tokens_est=_saved_tokens_est(ctx)
        )
        _upgrade_ctx_model(ctx, chat_result.get("model"))
    else:
        chat_result = await provider_adapter.chat_completion(target, chat_payload)
        _record_usage_safe(
            chat_result, target, endpoint_id=None, saved_bytes=ctx.get("saved_bytes")
        )

    log_info(
        f"anthropic completion success for model '{model}'",
        source=ANTHROPIC_LOG_SOURCE,
        context={"model": model},
    )
    return openai_chat_response_to_anthropic_messages(chat_result, model)


# --------------------------------------------------------------------------- #
# Inbound Anthropic SSE streaming (Tahap 2 / B7) — OpenAI-format upstream only
# --------------------------------------------------------------------------- #


async def _handle_anthropic_messages_stream(
    request: Request,
    ctx: dict,
    model: str,
    chat_payload: dict,
    endpoint_name: Optional[str],
) -> StreamingResponse:
    """Route an inbound Anthropic ``stream:true`` request to an OpenAI-format
    upstream and translate its SSE into the Anthropic Messages SSE envelope.

    Tahap 2 scope (decision D-A): only OpenAI-format upstreams stream — provider
    openai, combo member openai, or endpoint-bound openai. An anthropic/gemini
    upstream (or a combo with no openai member) raises
    :func:`_streaming_unsupported_error` (400 ``streaming_unsupported_format``),
    reusing the chat-surface rejection. No secrets are forwarded: the client
    ``x-api-key``/``Authorization`` never reaches the upstream; provider keys are
    attached only at egress by :mod:`backend.gateway.provider_adapter`.
    """

    async def _stream_for(target, proxy_url, endpoint_id) -> StreamingResponse:
        fmt = (target.format or "openai").lower()
        if fmt != "openai":
            log_warning(
                "anthropic streaming requested for translated format "
                f"'{fmt}' (not supported yet)",
                source=ANTHROPIC_LOG_SOURCE,
                context={"model": target.model_ref, "format": fmt},
            )
            raise _streaming_unsupported_error()
        return await _anthropic_stream_response(
            target,
            chat_payload,
            ctx,
            endpoint_id,
            request_model=model,
            proxy_url=proxy_url,
        )

    # Endpoint-bound path (mirror _route_via_endpoint, but Anthropic-encoded).
    if endpoint_name:
        # ADR-013: apply the bound Provider's Token Saver hook (endpoint ->
        # provider binding; combos use their first candidate member).
        chat_payload, saved_bytes = _apply_token_saver_for_provider(
            _resolve_saver_provider(endpoint_name=endpoint_name), chat_payload
        )
        ctx["saved_bytes"] = saved_bytes
        with SessionLocal() as session:
            endpoint = (
                session.query(Endpoint).filter_by(name=endpoint_name).first()
            )
            if endpoint is None:
                log_warning(
                    f"_handle_anthropic_messages_stream: endpoint '{endpoint_name}' "
                    "not found",
                    source=ANTHROPIC_LOG_SOURCE,
                )
                raise GatewayError(
                    400, f"endpoint '{endpoint_name}' not found",
                    "invalid_request_error", "endpoint_not_found",
                )
            ctx["endpoint_id"] = endpoint.id
            if endpoint.access_control_enabled and not _endpoint_authorized(
                request, endpoint
            ):
                log_warning(
                    f"_handle_anthropic_messages_stream: unauthorized request to "
                    f"endpoint '{endpoint_name}'",
                    source=ANTHROPIC_LOG_SOURCE,
                )
                raise GatewayError(
                    401,
                    "unauthorized: missing or invalid API key for endpoint",
                    "authentication_error", "unauthorized",
                )
            binding = (
                session.query(EndpointBinding)
                .filter_by(endpoint_id=endpoint.id).first()
            )
            if binding is None:
                raise GatewayError(
                    400, f"endpoint '{endpoint_name}' has no upstream binding",
                    "invalid_request_error", "endpoint_no_binding",
                )
            proxy_url = None
            if endpoint.proxy_pool_id is not None:
                pool = session.get(ProxyPool, endpoint.proxy_pool_id)
                if pool is not None:
                    node = proxy_selector.select_node(pool, session)
                    if node is not None:
                        proxy_url = proxy_selector.build_proxy_url(node)
            if binding.bind_type == "provider":
                provider = session.get(Provider, binding.bind_id)
                if provider is None:
                    raise GatewayError(
                        400, f"endpoint '{endpoint_name}' binds a missing provider",
                        "invalid_request_error", "provider_not_found",
                    )
                api_key, account_id = select_provider_credential_with_account(
                    provider, session,
                    preferred_account_id=_preferred_account_id(request),
                )
                target = ResolvedTarget(
                    base_url=provider.base_url,
                    api_key=api_key,
                    model_ref=model,
                    upstream_model=_strip_binding_prefix(model),
                    combo_used=False,
                    provider_id=provider.id,
                    account_id=account_id,
                    format=format_for_provider_type(provider.type),
                )
                _upgrade_ctx_model(ctx, target.upstream_model)
                return await _stream_for(target, proxy_url, endpoint.id)
            if binding.bind_type == "combo":
                member = resolve_combo_stream_target(binding.bind_id)
                if member is None or (member.format or "openai").lower() != "openai":
                    raise _streaming_unsupported_error()
                _upgrade_ctx_model(ctx, member.upstream_model)
                return await _stream_for(member, proxy_url, endpoint.id)
            raise GatewayError(
                400,
                f"endpoint '{endpoint_name}' has unsupported bind_type "
                f"'{binding.bind_type}'",
                "invalid_request_error", "endpoint_no_binding",
            )

    # Model-based resolution (verbatim mirror of _handle_anthropic_messages).
    try:
        target = resolve_target(
            model, preferred_account_id=_preferred_account_id(request)
        )
    except TargetNotFound as exc:
        log_warning(
            f"model reference not found: {model}", source=ANTHROPIC_LOG_SOURCE,
        )
        raise GatewayError(400, str(exc), "invalid_request_error", "model_not_found")

    _upgrade_ctx_model(ctx, target.upstream_model)

    if target.combo_used:
        combo_name = model[len("combo:"):]
        member = resolve_combo_stream_target(combo_name)
        if member is None or (member.format or "openai").lower() != "openai":
            log_warning(
                "anthropic streaming requested for a combo with no OpenAI-compatible "
                f"member (model '{model}')",
                source=ANTHROPIC_LOG_SOURCE,
            )
            raise _streaming_unsupported_error()
        _upgrade_ctx_model(ctx, member.upstream_model)
        # ADR-013: streaming model-based combo — apply the selected member's
        # Provider Token Saver hook before the SSE is committed (fail-open).
        chat_payload, saved_bytes = _apply_token_saver_for_provider(
            _resolve_saver_provider(target=member), chat_payload
        )
        ctx["saved_bytes"] = saved_bytes
        return await _stream_for(member, None, None)

    # ADR-013: streaming model-based provider — apply the resolved Provider's
    # Token Saver hook before the SSE is committed (fail-open).
    chat_payload, saved_bytes = _apply_token_saver_for_provider(
        _resolve_saver_provider(target=target), chat_payload
    )
    ctx["saved_bytes"] = saved_bytes
    return await _stream_for(target, None, None)


async def _anthropic_stream_response(
    target: ResolvedTarget,
    payload: dict,
    ctx: dict,
    endpoint_id: Optional[int],
    request_model: str,
    proxy_url: Optional[str] = None,
) -> StreamingResponse:
    """Build an SSE ``StreamingResponse`` that translates an upstream OpenAI-format
    stream into the Anthropic Messages SSE envelope.

    Mirrors :func:`_streaming_response` (prime before commit; usage-after-stream)
    but the body generator decodes the upstream OpenAI SSE bytes -> chunk dicts and
    encodes them through :class:`_AnthropicSseEncoder`, flushing per chunk for low
    latency. A mid-stream transport failure (status already 200) emits ONE
    Anthropic-shaped ``event: error`` frame (design §5.2 / R6) — never a silent
    truncation.
    """
    fmt = (target.format or "openai").lower()
    if fmt != "openai":
        raise _streaming_unsupported_error()

    # Force the upstream stream + final usage chunk (the encoder needs usage for
    # message_delta). The adapter also rewrites the model and sets stream=True.
    out = dict(payload)
    out["stream"] = True
    out.setdefault("stream_options", {"include_usage": True})

    agen = provider_adapter.chat_completion_stream(target, out, proxy_url)
    # Prime: pull the first bytes so upstream connect/HTTP/timeout errors raise HERE
    # (mapped to the Anthropic JSON envelope) instead of after the 200 SSE commit.
    try:
        first = await agen.__anext__()
    except StopAsyncIteration:
        first = None
    except Exception:
        await agen.aclose()
        raise

    encoder = _AnthropicSseEncoder(request_model)

    async def body():
        buf = bytearray()
        completed = False
        try:
            async for chunk in _iter_openai_sse_chunks(_chain_first(first, agen), buf):
                for event in encoder.feed([chunk]):
                    yield event.encode("utf-8")
            for event in encoder.finish():
                yield event.encode("utf-8")
            completed = True
        except UpstreamError as exc:
            # Mid-stream transport failure (status already 200): emit ONE
            # Anthropic-shaped error frame, then stop (design §5.2 / R6).
            err = exc.envelope.get("error", {}) if isinstance(exc.envelope, dict) else {}
            yield anthropic_error_sse_frame(err).encode("utf-8")
        except Exception as exc:  # noqa: BLE001 - honest termination, not truncation
            logger.error(
                "anthropic inbound stream failed mid-stream: %s", exc, exc_info=True
            )
            log_error_exc(
                "anthropic inbound stream failed mid-stream",
                source="backend.gateway.router",
                exc=exc,
                context={"model_ref": ctx.get("model")},
            )
            yield anthropic_error_sse_frame(
                {
                    "type": "api_error",
                    "message": "upstream stream interrupted",
                    "code": "upstream_stream_interrupted",
                }
            ).encode("utf-8")
        finally:
            await agen.aclose()
            if completed:
                _record_stream_usage_safe(
                    buf, target, endpoint_id=endpoint_id,
                    saved_bytes=ctx.get("saved_bytes"),
                )

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _chain_first(first, agen):
    """Yield the (already-primed) first bytes, then the remainder of the byte stream."""
    if first is not None:
        yield first
    async for raw in agen:
        yield raw


async def _iter_openai_sse_chunks(byte_stream, buf: bytearray):
    """Decode an OpenAI SSE *byte* async-iterable into OpenAI chunk dicts.

    Buffers every raw byte into ``buf`` (reused for usage-after-stream) and yields
    one chunk dict per ``data:`` frame, skipping ``[DONE]`` and non-JSON frames.
    Frames spanning byte boundaries are reassembled across ``\\n\\n`` events.
    """
    pending = bytearray()
    async for raw in byte_stream:
        buf.extend(raw)
        pending.extend(raw)
        while True:
            idx = pending.find(b"\n\n")
            if idx == -1:
                break
            frame = bytes(pending[:idx])
            del pending[: idx + 2]
            chunk = _parse_sse_data_frame(frame)
            if chunk is not None:
                yield chunk
    if pending:
        chunk = _parse_sse_data_frame(bytes(pending))
        if chunk is not None:
            yield chunk


def _parse_sse_data_frame(frame: bytes) -> Optional[dict]:
    """Parse one raw SSE ``data:`` frame into an OpenAI chunk dict (or None)."""
    try:
        text = frame.decode("utf-8", "replace")
    except Exception:  # noqa: BLE001 - defensive only
        return None
    data_blobs = []
    for line in text.splitlines():
        line = line.rstrip("\r")
        if line.startswith("data:"):
            data_blobs.append(line[len("data:"):].strip())
    joined = "\n".join(data_blobs).strip()
    if not joined or joined == "[DONE]":
        return None
    try:
        obj = json.loads(joined)
    except (ValueError, TypeError):
        return None
    return obj if isinstance(obj, dict) else None


def _anthropic_error_body(error: dict) -> dict:
    """Wrap an OpenAI-style error object into the Anthropic ``{"type":"error"}`` body."""
    return {"type": "error", "error": error}


def _anthropic_error_response(exc: GatewayError) -> JSONResponse:
    """Render a :class:`GatewayError` as an Anthropic-shaped JSON error response."""
    err = exc.envelope.get("error", {})
    return JSONResponse(
        status_code=exc.status_code,
        content=_anthropic_error_body(err),
    )


@router.post("/v1/messages/count_tokens")
async def messages_count_tokens(request: Request) -> Response:
    """Heuristic token estimate for an Anthropic ``/v1/messages`` request.

    litellm parity: claude-code calls this so its UI shows a token count. Stage 1
    uses a cheap heuristic (UTF-8 bytes ÷ 4, rounded; output_tokens:0) — no
    upstream call, no universal tokenizer required (KISS/YAGNI). A real
    tokenizer / upstream count is a future phase (design doc §8).
    """
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001 - malformed body
        raise GatewayError(
            400, "invalid JSON request body", "invalid_request_error", "invalid_json"
        )
    if not isinstance(payload, dict):
        raise GatewayError(
            400,
            "request body must be a JSON object",
            "invalid_request_error",
            "invalid_body",
        )

    text_parts: List[str] = []
    messages = payload.get("messages")
    if isinstance(messages, list):
        for m in messages:
            if isinstance(m, dict):
                text_parts.append(_extract_text(m.get("content")))
    system = payload.get("system")
    if system is not None:
        text_parts.append(_extract_text(system))

    joined = "".join(text_parts)
    input_tokens = len(joined.encode("utf-8")) // 4
    return JSONResponse(content={"input_tokens": input_tokens, "output_tokens": 0})


@router.post("/api/event_logging/batch")
async def event_logging_batch(request: Request) -> Response:
    """Stub for claude-code telemetry batch (litellm parity).

    claude-code POSTs event batches here; returning 202 keeps its telemetry from
    emitting 404 noise. No body is persisted (the gateway is stateless w.r.t.
    client-side telemetry).
    """
    return JSONResponse(status_code=202, content={})


@router.get("/v1/models")
async def list_models() -> dict:
    """OpenAI-compatible model list built from providers + combos."""
    log_info("GET /v1/models", source="backend.gateway.router")
    data: list[dict] = []
    with SessionLocal() as session:
        for pm in session.query(ProviderModel).all():
            provider = pm.provider
            owner = provider.name if provider is not None else "aigate"
            provider_name = provider.name if provider is not None else "unknown"
            data.append(
                {
                    "id": f"provider:{provider_name}:{pm.model_id}",
                    "object": "model",
                    "owned_by": owner,
                }
            )

        # Combos are exposed as selectable models so any OpenAI-compatible
        # client (e.g. opencode's /models) can DISCOVER them; the gateway
        # resolver already accepts ``combo:<name>`` as a model reference. Only
        # ENABLED combos are listed (a disabled combo must not be selectable).
        # A combo with no members is still listed (it may be configured later).
        for combo in session.query(Combo).filter(Combo.enabled.is_(True)).all():
            data.append(
                {
                    "id": f"combo:{combo.name}",
                    "object": "model",
                    "owned_by": "aigate",
                }
            )

    return {"object": "list", "data": data}


# --------------------------------------------------------------------------- #
# Usage recording (B5.5 / PRD §2.4.2) + savings (B5.6 / PRD §2.4.3)
# --------------------------------------------------------------------------- #
def _saved_tokens_est(ctx: dict) -> Optional[int]:
    """Convert ctx ``saved_bytes`` to the token estimate, or None if no saver.

    None (saver not applied) keeps ``UsageRecord.saved_tokens_est`` NULL —
    "not measured" stays distinguishable from "measured as 0" (caveman /
    ponytail are output-side and always measure 0 input-side).
    """
    saved_bytes = ctx.get("saved_bytes")
    if saved_bytes is None:
        return None
    return _usage.saved_tokens_from_bytes(saved_bytes)


def _record_usage_safe(
    result: dict,
    target: ResolvedTarget,
    endpoint_id=None,
    saved_bytes: Optional[int] = None,
) -> None:
    """Persist a UsageRecord for a successful completion (fail-open).

    ``backend.usage.record_usage_from_result`` already swallows+logs its own
    errors; this outer guard additionally protects the extraction call itself
    so a telemetry failure can NEVER alter or break the client response.
    ``saved_bytes`` (B5.6) is the token_saver input-savings figure when a
    saver was applied; it is converted to ``saved_tokens_est`` (~bytes/4).
    """
    try:
        saved_tokens_est = (
            _usage.saved_tokens_from_bytes(saved_bytes)
            if saved_bytes is not None
            else None
        )
        _usage.record_usage_from_result(
            result,
            provider_id=target.provider_id,
            account_id=target.account_id,
            model=target.upstream_model,
            endpoint_id=endpoint_id,
            saved_tokens_est=saved_tokens_est,
        )
    except Exception as exc:  # noqa: BLE001 - fail-open mandated (B5.5)
        log_error_exc(
            "usage recording failed (fail-open; client response unaffected)",
            source="backend.gateway.router",
            exc=exc,
            context={"model_ref": target.model_ref},
        )


# --------------------------------------------------------------------------- #
# SSE streaming (stream:true) — OpenAI-format pass-through proxy
# --------------------------------------------------------------------------- #
# Known limitation: per-chunk SSE translation for anthropic/gemini is NOT
# implemented. Those formats keep working non-streaming; a stream:true request
# against them returns this clear 400 envelope instead of silently mis-proxying.
STREAMING_UNSUPPORTED_MSG = (
    "streaming is not yet supported for translated providers (anthropic/gemini); "
    "use a non-stream request or an OpenAI-compatible provider"
)


def _streaming_unsupported_error() -> GatewayError:
    """The 400 envelope for a stream:true request on a translated format."""
    return GatewayError(
        400, STREAMING_UNSUPPORTED_MSG, "invalid_request_error",
        "streaming_unsupported_format",
    )


def _extract_usage_from_sse(raw: bytes) -> Optional[dict]:
    """Best-effort pull of the final ``usage`` object from an SSE byte stream.

    OpenAI emits usage only when the client asked for it
    (``stream_options.include_usage``); the last ``data:`` frame carrying a
    non-empty ``usage`` wins. Malformed / absent frames are skipped (never
    raise) — this is telemetry best-effort, fail-open.
    """
    try:
        text = raw.decode("utf-8", "replace")
    except Exception:  # noqa: BLE001 - decode is defensive only
        return None
    usage: Optional[dict] = None
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data = line[len("data:"):].strip()
        if not data or data == "[DONE]":
            continue
        try:
            obj = json.loads(data)
        except (ValueError, TypeError):
            continue
        if isinstance(obj, dict) and isinstance(obj.get("usage"), dict):
            usage = obj["usage"]
    return usage


def _record_stream_usage_safe(
    buf: bytearray,
    target: ResolvedTarget,
    endpoint_id: Optional[int],
    saved_bytes: Optional[int],
) -> None:
    """Record a UsageRecord after a stream completes (fail-open, best-effort).

    Parses the final usage chunk from the buffered SSE bytes when present; a
    stream that never carried usage records 0/0 (same as a usage-less non-stream
    response). Any failure is logged (R12) and swallowed — the client already
    received the stream.
    """
    try:
        usage = _extract_usage_from_sse(bytes(buf))
        result = {"usage": usage} if usage else {}
        _record_usage_safe(
            result, target, endpoint_id=endpoint_id, saved_bytes=saved_bytes
        )
    except Exception as exc:  # noqa: BLE001 - fail-open mandated (B5.5)
        log_error_exc(
            "stream usage recording failed (fail-open; stream already delivered)",
            source="backend.gateway.router",
            exc=exc,
            context={"model_ref": target.model_ref},
        )


async def _streaming_response(
    target: ResolvedTarget,
    payload: dict,
    proxy_url: Optional[str],
    ctx: dict,
    endpoint_id: Optional[int] = None,
) -> StreamingResponse:
    """Build an SSE ``StreamingResponse`` proxying an OpenAI-format upstream.

    The upstream generator is PRIMED (first chunk pulled) before the response is
    returned, so a connect / timeout / HTTP-status failure surfaces as a normal
    :class:`GatewayError` (rendered as the OpenAI JSON envelope by the handler)
    rather than a committed-200 broken stream. Once primed, the first chunk plus
    the remainder are forwarded verbatim; the upstream's own ``data: [DONE]`` is
    passed through untouched. Usage is recorded after the stream completes
    normally (not on client disconnect / mid-stream error).

    :raises GatewayError: 400 ``streaming_unsupported_format`` for a translated
      format; or the adapter's :class:`UpstreamError` during priming.
    """
    fmt = (target.format or "openai").lower()
    if fmt != "openai":
        log_warning(
            f"streaming requested for translated format '{fmt}' (not supported "
            f"yet); use a non-stream request or an OpenAI-compatible provider",
            source="backend.gateway.router",
            context={"model": target.model_ref, "format": fmt},
        )
        raise _streaming_unsupported_error()

    agen = provider_adapter.chat_completion_stream(target, payload, proxy_url)
    # Prime: pull the first chunk so upstream connect/HTTP errors raise HERE
    # (mapped to a JSON envelope) instead of after the 200 SSE is committed.
    try:
        first = await agen.__anext__()
    except StopAsyncIteration:
        first = None  # upstream produced an empty stream
    except Exception:
        # UpstreamError (a GatewayError) or unexpected failure — the generator
        # has already unwound its own httpx context; aclose() is a safe no-op.
        await agen.aclose()
        raise

    async def body():
        buf = bytearray()
        completed = False
        try:
            if first is not None:
                buf.extend(first)
                yield first
            async for chunk in agen:
                buf.extend(chunk)
                yield chunk
            completed = True
        finally:
            # Always release the upstream client (covers normal end, mid-stream
            # error, and early client disconnect / GeneratorExit).
            await agen.aclose()
            if completed:
                _record_stream_usage_safe(
                    buf,
                    target,
                    endpoint_id=endpoint_id,
                    saved_bytes=ctx.get("saved_bytes"),
                )

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --------------------------------------------------------------------------- #
# Request logging (B5.6 / PRD §2.4.3 — debug mode, gated + fail-open)
# --------------------------------------------------------------------------- #
def _upgrade_ctx_model(ctx: dict, upstream_model: Optional[str]) -> None:
    """Upgrade the RequestLog debug model to a concrete upstream id (never empty).

    ``ctx["model"]`` starts as the client-requested model reference (set by
    ``_handle_chat_completion`` / ``_handle_responses``). As soon as a real
    upstream model becomes known — resolver target, combo member, endpoint
    binding, or the upstream response envelope — it is upgraded IN PLACE.
    An empty/None value (the ``combo:`` resolver marker, an envelope without
    ``model``) is ignored so the debug row NEVER degrades to ``''``: error
    paths and combo fallbacks keep the requested model ref.
    """
    if upstream_model:
        ctx["model"] = upstream_model


def _request_log_enabled() -> bool:
    """Debug gate: ``Setting`` key ``request_log_enabled`` == 'true'.

    Documented decision: a DEDICATED Setting key, not ``dev_mode`` — request
    logging must be independently switchable and defaults OFF (DB bloat).
    A settings-store failure is logged and treated as DISABLED (fail-safe).
    """
    try:
        value = _settings.get(REQUEST_LOG_SETTING_KEY)
    except Exception as exc:  # noqa: BLE001 - fail-safe to disabled
        log_warning_exc(
            "request_log_enabled lookup failed; treating as disabled",
            source="backend.gateway.router",
            exc=exc,
        )
        return False
    return (value or "").strip().lower() == "true"


def _truncate_debug(text: str) -> str:
    """Bound a debug blob to REQUEST_LOG_MAX_CHARS with an omitted-size marker."""
    if len(text) <= REQUEST_LOG_MAX_CHARS:
        return text
    omitted = len(text) - REQUEST_LOG_MAX_CHARS
    return text[:REQUEST_LOG_MAX_CHARS] + f"...[truncated {omitted} chars]"


def _dump_request_debug(request: Request, ctx: dict) -> str:
    """JSON dump of headers (secrets redacted) + the original parsed body."""
    headers = {
        key: (_REDACTED if key.lower() in _SECRET_HEADERS else value)
        for key, value in request.headers.items()
    }
    body = ctx.get("payload")
    doc = {
        "headers": headers,
        "body": body if body is not None else "<missing or unparseable body>",
    }
    return json.dumps(doc, default=str, ensure_ascii=False)


def _dump_response_debug(
    result: Optional[dict],
    error_envelope: Optional[dict],
    http_status: Optional[int],
    exc: Optional[BaseException] = None,
) -> str:
    """Short response summary: status + answer preview / error + usage block."""
    if result is None:
        err = (error_envelope or {}).get("error", {}) or {}
        doc: dict = {
            "status": "error",
            "http_status": http_status,
            "error": {
                "message": str(err.get("message", ""))[:RESPONSE_PREVIEW_CHARS],
                "type": err.get("type"),
                "code": err.get("code"),
            },
        }
        if exc is not None:
            doc["exception"] = type(exc).__name__
        return json.dumps(doc, default=str, ensure_ascii=False)
    doc = {"status": "ok", "http_status": http_status or 200}
    if isinstance(result, dict):
        doc["model"] = result.get("model")
        doc["usage"] = result.get("usage")
        content: object = None
        try:
            content = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            content = None
        if isinstance(content, str):
            doc["content_preview"] = content[:RESPONSE_PREVIEW_CHARS]
    return json.dumps(doc, default=str, ensure_ascii=False)


def _record_request_log_safe(
    ctx: dict,
    request: Request,
    t0: float,
    result: Optional[dict] = None,
    error_envelope: Optional[dict] = None,
    http_status: Optional[int] = None,
    exc: Optional[BaseException] = None,
) -> None:
    """Persist a ``RequestLog`` debug row when logging is enabled (fail-open).

    Never raises: any error lands in ``LogEntry`` (R12) and the client
    response proceeds untouched. When the gate is off, this is a cheap no-op
    (one Setting lookup, no RequestLog write — avoids DB bloat).
    """
    try:
        if not _request_log_enabled():
            return
        duration_ms = max(0, int((time.monotonic() - t0) * 1000))
        row = RequestLog(
            endpoint_id=ctx.get("endpoint_id"),
            model=str(ctx.get("model") or ""),
            ts=datetime.utcnow(),
            duration_ms=duration_ms,
            request=_truncate_debug(_dump_request_debug(request, ctx)),
            response=_truncate_debug(
                _dump_response_debug(result, error_envelope, http_status, exc)
            ),
        )
        with SessionLocal() as session:
            session.add(row)
            session.commit()
    except Exception as log_exc:  # noqa: BLE001 - fail-open mandated (B5.6)
        log_error_exc(
            "request-log recording failed (fail-open; client response unaffected)",
            source="backend.gateway.router",
            exc=log_exc,
            context={"model_ref": ctx.get("model")},
        )


# --------------------------------------------------------------------------- #
# Endpoint-level routing (ADR-008 / task B2.5)
# --------------------------------------------------------------------------- #
def _lookup_endpoint(session, ref: str) -> Optional[Endpoint]:
    """Resolve an ``Endpoint`` by integer id (header value parsed) or by name.

    The ``X-Aigate-Endpoint`` header may carry either the numeric endpoint id
    or its name; try id first, then fall back to name lookup.
    """
    # Try integer id first (no risky parse exception; names are non-numeric).
    if ref.isdigit():
        endpoint = session.get(Endpoint, int(ref))
        if endpoint is not None:
            return endpoint
    return session.query(Endpoint).filter_by(name=ref).first()


def _first_member_provider(session, combo: "Combo") -> Optional[Provider]:
    """Return the combo's first candidate member Provider (read-only, fail-open).

    Used to attribute a Token Saver hook to a combo target before the concrete
    member is executed: ``build_candidates`` resolves members in the combo's
    strategy order WITHOUT advancing any cursor or mutating state, so this is a
    side-effect-free pick of the member that will (for fallback/three_tier)
    serve first. ``None`` when the combo has no usable member/provider.
    """
    candidates = build_candidates(combo, session)
    if candidates and candidates[0].provider_id:
        return session.get(Provider, candidates[0].provider_id)
    return None


def _resolve_saver_provider(
    endpoint_name: Optional[str] = None,
    target: Optional[ResolvedTarget] = None,
) -> Optional[Provider]:
    """Resolve the ``Provider`` whose Token Saver toggles apply to a request.

    Priority:
    * ``endpoint_name`` given -> follow the Endpoint's single ``EndpointBinding``
      (``provider`` -> that Provider; ``combo`` -> its first candidate member
      Provider via :func:`_first_member_provider`);
    * else a resolved ``target`` -> its ``provider_id`` (a plain provider ref);
      a combo marker (``combo_used`` + ``combo:<name>`` model_ref) resolves via
      its first candidate member.

    Returns ``None`` (no saver applied) when nothing resolves. Fail-open: any
    lookup error is logged and yields ``None`` — the request is never broken.
    """
    try:
        with SessionLocal() as session:
            if endpoint_name:
                endpoint = _lookup_endpoint(session, endpoint_name)
                if endpoint is None:
                    return None
                binding = (
                    session.query(EndpointBinding)
                    .filter_by(endpoint_id=endpoint.id)
                    .first()
                )
                if binding is None:
                    return None
                if binding.bind_type == "provider":
                    return session.get(Provider, binding.bind_id)
                if binding.bind_type == "combo":
                    combo = session.get(Combo, binding.bind_id)
                    if combo is None:
                        return None
                    return _first_member_provider(session, combo)
                return None
            if target is not None:
                if getattr(target, "provider_id", 0):
                    return session.get(Provider, target.provider_id)
                if getattr(target, "combo_used", False):
                    ref = getattr(target, "model_ref", "") or ""
                    if ref.startswith("combo:"):
                        combo = (
                            session.query(Combo)
                            .filter_by(name=ref[len("combo:"):])
                            .first()
                        )
                        if combo is not None:
                            return _first_member_provider(session, combo)
            return None
    except Exception as exc:  # noqa: BLE001 - fail-open mandated by ADR-013
        log_warning_exc(
            "token_saver provider resolution failed; no saver applied",
            source="backend.gateway.router",
            exc=exc,
        )
        return None


def _apply_token_saver_for_provider(
    provider: Optional[Provider], payload: dict
) -> Tuple[dict, Optional[int]]:
    """Apply a resolved ``Provider``'s Token Saver toggles to the payload.

    The Provider carries three independent on/off toggles; the enabled modes
    are applied in the fixed order ``rtk -> caveman -> ponytail`` via
    :func:`backend.gateway.token_saver.apply_token_savers` (so later savers see
    the earlier ones' output). Returns ``(payload, saved_bytes)``:
    ``saved_bytes`` is ``None`` when NO saver ran (no provider / all toggles
    off / lookup failure — "not measured", per B5.6) and an ``int >= 0`` when
    one ran. Any failure returns the original payload unchanged (ADR-013
    fail-open).
    """
    if provider is None:
        return payload, None
    modes = [
        mode
        for mode, on in (
            ("rtk", provider.token_saver_rtk),
            ("caveman", provider.token_saver_caveman),
            ("ponytail", provider.token_saver_ponytail),
        )
        if on
    ]
    if not modes:
        return payload, None
    try:
        log_info(
            f"applying token_saver modes {modes} for provider "
            f"'{getattr(provider, 'name', '?')}'",
            source="backend.gateway.router",
            context={"provider": getattr(provider, "name", None), "modes": modes},
        )
        new_payload, saved_bytes = _token_saver.apply_token_savers(modes, payload)
        return new_payload, saved_bytes
    except Exception as exc:  # noqa: BLE001 - fail-open mandated by ADR-013
        log_warning_exc(
            "token_saver provider application failed; passing through original payload",
            source="backend.gateway.router",
            exc=exc,
        )
        return payload, None


def _strip_binding_prefix(model: str) -> str:
    """Strip a leading ``provider:``/``combo:`` reference prefix for an
    Endpoint-bound provider call so the REAL model id reaches the upstream.

    If the request model carries no such prefix it is returned as-is.
    """
    for prefix in ("provider:", "combo:"):
        if model.startswith(prefix):
            return model[len(prefix):]
    return model


def _endpoint_authorized(request: Request, endpoint: Endpoint) -> bool:
    """Check access control for an Endpoint with ``access_control_enabled``.

    Accepts either ``Authorization: Bearer <key>`` or an ``x-api-key`` header
    equal to ``endpoint.internal_api_key`` (ADR-007 plaintext comparison).
    """
    expected = endpoint.internal_api_key
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        if auth[len("bearer "):].strip() == expected:
            return True
    xkey = request.headers.get("x-api-key")
    if xkey is not None and xkey == expected:
        return True
    return False


async def _route_via_endpoint(
    name: str, model: str, payload: dict, request: Request, ctx: dict
) -> Union[dict, Response]:
    """Resolve + forward a request through a named Endpoint's binding.

    Loads the ``Endpoint`` by name, enforces access control when enabled,
    resolves the upstream via its single ``EndpointBinding`` (provider or
    combo), and routes egress through the Endpoint's bound ``ProxyPool``
    (selected via ``proxy_selector.select_node``). The no-header model-based
    path is untouched. ``ctx`` (B5.6) receives the endpoint attribution +
    upstream model for the RequestLog debug row.
    """
    with SessionLocal() as session:
        endpoint = (
            session.query(Endpoint).filter_by(name=name).first()
        )
        if endpoint is None:
            log_warning(
                f"_route_via_endpoint: endpoint '{name}' not found",
                source="backend.gateway.router",
            )
            raise GatewayError(
                400,
                f"endpoint '{name}' not found",
                "invalid_request_error",
                "endpoint_not_found",
            )

        # B5.6: attribute the debug row to this endpoint.
        ctx["endpoint_id"] = endpoint.id

        if endpoint.access_control_enabled:
            if not _endpoint_authorized(request, endpoint):
                log_warning(
                    f"_route_via_endpoint: unauthorized request to endpoint "
                    f"'{name}'",
                    source="backend.gateway.router",
                )
                raise GatewayError(
                    401,
                    "unauthorized: missing or invalid API key for endpoint",
                    "authentication_error",
                    "unauthorized",
                )

        binding = (
            session.query(EndpointBinding)
            .filter_by(endpoint_id=endpoint.id)
            .first()
        )
        if binding is None:
            log_warning(
                f"_route_via_endpoint: endpoint '{name}' has no binding",
                source="backend.gateway.router",
            )
            raise GatewayError(
                400,
                f"endpoint '{name}' has no upstream binding",
                "invalid_request_error",
                "endpoint_no_binding",
            )

        proxy_url: Optional[str] = None
        if endpoint.proxy_pool_id is not None:
            pool = session.get(ProxyPool, endpoint.proxy_pool_id)
            if pool is not None:
                node = proxy_selector.select_node(pool, session)
                if node is not None:
                    proxy_url = proxy_selector.build_proxy_url(node)
                    log_info(
                        f"_route_via_endpoint: endpoint '{name}' using proxy "
                        f"{proxy_url}",
                        source="backend.gateway.router",
                        context={"endpoint": name, "pool_id": pool.id},
                    )

        if binding.bind_type == "provider":
            provider = session.get(Provider, binding.bind_id)
            if provider is None:
                log_warning(
                    f"_route_via_endpoint: endpoint '{name}' binds missing "
                    f"provider {binding.bind_id}",
                    source="backend.gateway.router",
                )
                raise GatewayError(
                    400,
                    f"endpoint '{name}' binds a missing provider",
                    "invalid_request_error",
                    "provider_not_found",
                )
            api_key, account_id = select_provider_credential_with_account(
                provider, session, preferred_account_id=_preferred_account_id(request)
            )
            target = ResolvedTarget(
                base_url=provider.base_url,
                api_key=api_key,
                model_ref=model,
                upstream_model=_strip_binding_prefix(model),
                combo_used=False,
                # B5.5: provider + account so the UsageRecord can be attributed.
                provider_id=provider.id,
                account_id=account_id,
            )
            # B5.6: the debug row should carry the real upstream model id.
            _upgrade_ctx_model(ctx, target.upstream_model)
            # SSE streaming: an endpoint-bound provider is treated as OpenAI
            # format (matching the non-stream path, which never translates on
            # this binding), so stream:true is proxied straight through.
            if payload.get("stream") is True:
                return await _streaming_response(
                    target, payload, proxy_url, ctx, endpoint_id=endpoint.id
                )
            result = await provider_adapter.chat_completion(
                target, payload, proxy_url
            )
            # B5.5: record usage telemetry for the endpoint-bound provider call
            # (B5.6: + token_saver savings when a saver was applied).
            _record_usage_safe(
                result,
                target,
                endpoint_id=endpoint.id,
                saved_bytes=ctx.get("saved_bytes"),
            )
            return result

        if binding.bind_type == "combo":
            # SSE streaming: resolve the combo's first usable OpenAI-format
            # member and stream from it (translated-only combos -> 400).
            if payload.get("stream") is True:
                try:
                    member = resolve_combo_stream_target(binding.bind_id)
                except TargetNotFound as exc:
                    log_warning(
                        f"_route_via_endpoint: combo '{binding.bind_id}' not "
                        f"found for streaming",
                        source="backend.gateway.router",
                    )
                    raise GatewayError(
                        400, str(exc), "invalid_request_error", "combo_not_found"
                    )
                if member is None:
                    log_warning(
                        "streaming requested for an endpoint combo with no "
                        "OpenAI-compatible member",
                        source="backend.gateway.router",
                        context={"endpoint": name},
                    )
                    raise _streaming_unsupported_error()
                # B5.6: the debug row carries the streaming member's real model.
                _upgrade_ctx_model(ctx, member.upstream_model)
                return await _streaming_response(
                    member, payload, proxy_url, ctx, endpoint_id=endpoint.id
                )
            # B5.5: execute_combo records the UsageRecord (it knows the winning
            # member/account); the endpoint id is threaded through here.
            # B5.6: so is the token_saver savings estimate (None = no saver).
            result = await execute_combo(
                binding.bind_id,
                payload,
                proxy_url,
                endpoint_id=endpoint.id,
                saved_tokens_est=_saved_tokens_est(ctx),
            )
            # B5.6: prefer the model that actually served (upstream envelope),
            # else keep the requested model ref.
            _upgrade_ctx_model(ctx, result.get("model"))
            return result

        log_warning(
            f"_route_via_endpoint: endpoint '{name}' has unsupported bind_type "
            f"'{binding.bind_type}'",
            source="backend.gateway.router",
        )
        raise GatewayError(
            400,
            f"endpoint '{name}' has unsupported binding type "
            f"'{binding.bind_type}'",
            "invalid_request_error",
            "invalid_binding",
        )


__all__ = [
    "router",
    "ChatCompletionRequest",
    "run_chat_completion",
    "REQUEST_LOG_SETTING_KEY",
    "REQUEST_LOG_MAX_CHARS",
    "RESPONSE_PREVIEW_CHARS",
]

"""OpenAI-compatible gateway router (FastAPI ``APIRouter``).

Exposes:

* ``POST /v1/chat/completions`` — validate the body via a Pydantic **v1**
  :class:`ChatCompletionRequest`, then forward the RAW received dict (not the
  validated model) to :mod:`backend.gateway.provider_adapter` so upstream gets
  the exact payload (pass-through of arbitrary OpenAI fields). The request
  model uses ``extra="allow"`` so unknown OpenAI fields are preserved.
  Streaming is rejected with a 400 envelope (streaming SSE is a later task).
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
from typing import List, Optional, Tuple

from fastapi import APIRouter, Request
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

from backend.config import settings as _settings
from backend.config.db import SessionLocal
from backend.combo_routing import execute_combo
from backend.gateway import provider_adapter
from backend.gateway.errors import GatewayError
from backend.gateway.resolver import ResolvedTarget, TargetNotFound, resolve_target
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
from backend.oauth import select_provider_credential_with_account


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
async def chat_completions(request: Request) -> dict:
    """OpenAI-compatible chat completion proxy (non-streaming).

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


async def _handle_chat_completion(request: Request, ctx: dict) -> dict:
    """Validate + route + forward one chat completion (raises GatewayError)."""
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

    if payload.get("stream") is True:
        log_warning(
            "streaming requested but not supported",
            source="backend.gateway.router",
        )
        raise GatewayError(
            400,
            "streaming not implemented yet (planned)",
            "invalid_request_error",
            "streaming_not_supported",
        )

    # ADR-008 / task B2.5: named Endpoint selected at request time via the
    # X-Aigate-Endpoint header. When present, routing + proxy binding are
    # driven by the Endpoint's EndpointBinding instead of the model reference.
    endpoint_name = request.headers.get("x-aigate-endpoint")
    if endpoint_name:
        # ADR-013 / B5.4: apply the Endpoint's Token Saver hook to the payload
        # BEFORE forwarding. Fail-open: never raises; original payload returned
        # on any error / missing endpoint / mode 'off'. B5.6: also capture the
        # input-side savings estimate for the UsageRecord.
        payload, saved_bytes = _apply_token_saver_for_endpoint(endpoint_name, payload)
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
        target = resolve_target(model)
    except TargetNotFound as exc:
        log_warning(
            f"model reference not found: {model}",
            source="backend.gateway.router",
        )
        raise GatewayError(
            400, str(exc), "invalid_request_error", "model_not_found"
        )

    # B5.6: prefer the real upstream model id in the debug row.
    ctx["model"] = target.upstream_model

    # Combo strategy routing (B2.4): a ``combo:`` reference is resolved per its
    # strategy by backend.combo_routing.execute_combo (which itself calls the
    # provider adapter). A plain provider reference goes straight to the adapter.
    if target.combo_used:
        combo_name = model[len("combo:"):]
        # B5.5: ``execute_combo`` records the UsageRecord itself (it knows which
        # member/account actually succeeded). No endpoint on this path.
        result = await execute_combo(combo_name, payload)
    else:
        result = await provider_adapter.chat_completion(target, payload)
        # B5.5: persist usage telemetry (fail-open — never breaks the client).
        _record_usage_safe(result, target, endpoint_id=None)

    # ADR-011 / R12: success path must still land in LogEntry.
    log_info(
        f"chat completion success for model '{model}'",
        source="backend.gateway.router",
        context={"model": model},
    )
    return result


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
# Request logging (B5.6 / PRD §2.4.3 — debug mode, gated + fail-open)
# --------------------------------------------------------------------------- #
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


def _apply_token_saver_for_endpoint(
    name: str, payload: dict
) -> Tuple[dict, Optional[int]]:
    """Apply the Token Saver hook for the named/identified Endpoint (fail-open).

    Looks up the ``Endpoint`` by id-or-name; if found and its ``token_saver``
    mode is not ``off``/None, runs ``apply_token_saver_with_metrics`` on the
    payload. Returns ``(payload, saved_bytes)``: ``saved_bytes`` is None when
    NO saver was applied (unknown endpoint / mode off / lookup failure —
    "not measured"), and an int >= 0 when one ran (B5.6 savings tracking).
    Any failure results in the original ``payload`` being returned unchanged
    (ADR-013 fail-open).
    """
    try:
        with SessionLocal() as session:
            endpoint = _lookup_endpoint(session, name)
            if endpoint is None:
                # header present but endpoint unknown -> no hook
                return payload, None
            mode = endpoint.token_saver
            if not mode or mode == "off":
                return payload, None
            log_info(
                f"applying token_saver mode '{mode}' for endpoint "
                f"'{endpoint.name}'",
                source="backend.gateway.router",
                context={"endpoint": endpoint.name, "mode": mode},
            )
            new_payload, saved_bytes = _token_saver.apply_token_saver_with_metrics(
                mode, payload
            )
            return new_payload, saved_bytes
    except Exception as exc:  # noqa: BLE001 - fail-open mandated by ADR-013
        log_warning_exc(
            "token_saver endpoint lookup failed; passing through original payload",
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
) -> dict:
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
                provider, session
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
            ctx["model"] = target.upstream_model
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
    "REQUEST_LOG_SETTING_KEY",
    "REQUEST_LOG_MAX_CHARS",
    "RESPONSE_PREVIEW_CHARS",
]

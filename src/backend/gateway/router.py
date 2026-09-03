"""OpenAI-compatible gateway router (FastAPI ``APIRouter``).

Exposes:

* ``POST /v1/chat/completions`` — validate the body via a Pydantic **v1**
  :class:`ChatCompletionRequest`, then forward the RAW received dict (not the
  validated model) to :mod:`backend.gateway.provider_adapter` so upstream gets
  the exact payload (pass-through of arbitrary OpenAI fields). The request
  model uses ``extra="allow"`` so unknown OpenAI fields are preserved.
  Streaming is rejected with a 400 envelope (streaming SSE is a later task).
* ``GET /v1/models`` — list available models derived from ``ProviderModel``
  rows (id ``provider:<provider>:<model_id>``) plus ``Combo`` rows
  (id ``combo:<name>``), in OpenAI ``{"object":"list","data":[...]}`` shape.

Hard rule R12 / ADR-011: every failure path logs to ``LogEntry`` via
``backend.log`` before raising. The adapter re-raises its own ``UpstreamError``
(which is already logged) as-is.

All errors surface as the OpenAI error envelope via
:class:`backend.gateway.errors.GatewayError` + the handler registered in
``backend.server``.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

from backend.config.db import SessionLocal
from backend.combo_routing import execute_combo
from backend.gateway import provider_adapter
from backend.gateway.errors import GatewayError
from backend.gateway.resolver import ResolvedTarget, TargetNotFound, resolve_target
from backend.log import log_info, log_warning, log_warning_exc
from backend.models import (
    Combo,
    Endpoint,
    EndpointBinding,
    Provider,
    ProviderModel,
    ProxyPool,
)
from backend.gateway import token_saver as _token_saver
from backend import proxy_selector
from backend.oauth import select_provider_credential


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


@router.post("/v1/chat/completions")
async def chat_completions(request: Request) -> dict:
    """OpenAI-compatible chat completion proxy (non-streaming)."""
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
        # on any error / missing endpoint / mode 'off'.
        payload = _apply_token_saver_for_endpoint(endpoint_name, payload)
        result = await _route_via_endpoint(endpoint_name, model, payload, request)
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

    # Combo strategy routing (B2.4): a ``combo:`` reference is resolved per its
    # strategy by backend.combo_routing.execute_combo (which itself calls the
    # provider adapter). A plain provider reference goes straight to the adapter.
    if target.combo_used:
        combo_name = model[len("combo:"):]
        result = await execute_combo(combo_name, payload)
    else:
        result = await provider_adapter.chat_completion(target, payload)

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

        for combo in session.query(Combo).all():
            data.append(
                {
                    "id": f"combo:{combo.name}",
                    "object": "model",
                    "owned_by": "aigate",
                }
            )

    return {"object": "list", "data": data}


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


def _apply_token_saver_for_endpoint(name: str, payload: dict) -> dict:
    """Apply the Token Saver hook for the named/identified Endpoint (fail-open).

    Looks up the ``Endpoint`` by id-or-name; if found and its ``token_saver``
    mode is not ``off``/None, runs ``apply_token_saver`` on the payload. Any
    failure (lookup error, missing endpoint, transform exception) results in the
    original ``payload`` being returned unchanged (ADR-013 fail-open).
    """
    try:
        with SessionLocal() as session:
            endpoint = _lookup_endpoint(session, name)
            if endpoint is None:
                return payload  # header present but endpoint unknown -> no hook
            mode = endpoint.token_saver
            if not mode or mode == "off":
                return payload
            log_info(
                f"applying token_saver mode '{mode}' for endpoint "
                f"'{endpoint.name}'",
                source="backend.gateway.router",
                context={"endpoint": endpoint.name, "mode": mode},
            )
            return _token_saver.apply_token_saver(mode, payload)
    except Exception as exc:  # noqa: BLE001 - fail-open mandated by ADR-013
        log_warning_exc(
            "token_saver endpoint lookup failed; passing through original payload",
            source="backend.gateway.router",
            exc=exc,
        )
        return payload


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
    name: str, model: str, payload: dict, request: Request
) -> dict:
    """Resolve + forward a request through a named Endpoint's binding.

    Loads the ``Endpoint`` by name, enforces access control when enabled,
    resolves the upstream via its single ``EndpointBinding`` (provider or
    combo), and routes egress through the Endpoint's bound ``ProxyPool``
    (selected via ``proxy_selector.select_node``). The no-header model-based
    path is untouched.
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
            target = ResolvedTarget(
                base_url=provider.base_url,
                api_key=select_provider_credential(provider, session),
                model_ref=model,
                upstream_model=_strip_binding_prefix(model),
                combo_used=False,
            )
            result = await provider_adapter.chat_completion(
                target, payload, proxy_url
            )
            return result

        if binding.bind_type == "combo":
            result = await execute_combo(binding.bind_id, payload, proxy_url)
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


__all__ = ["router", "ChatCompletionRequest"]

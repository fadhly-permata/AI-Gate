"""OpenAI-compatible gateway router (FastAPI ``APIRouter``).

Exposes:

* ``POST /v1/chat/completions`` — resolve ``model`` (``provider:`` / ``combo:``)
  via :func:`backend.gateway.resolver.resolve_target`, forward to the upstream
  via :mod:`backend.gateway.provider_adapter`, and return the upstream JSON
  as-is. Streaming is accepted by the body but rejected with a 400 envelope
  (streaming SSE is a later task).
* ``GET /v1/models`` — list available models derived from ``ProviderModel``
  rows (id ``provider:<provider>:<model_id>``) plus ``Combo`` rows
  (id ``combo:<name>``), in OpenAI ``{"object":"list","data":[...]}`` shape.

All errors surface as the OpenAI error envelope via
:class:`backend.gateway.errors.GatewayError` + the handler registered in
``backend.server``.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.config.db import SessionLocal
from backend.gateway import provider_adapter
from backend.gateway.errors import GatewayError
from backend.gateway.resolver import TargetNotFound, resolve_target
from backend.models import Combo, ProviderModel

router = APIRouter()


@router.post("/v1/chat/completions")
async def chat_completions(request: Request) -> dict:
    """OpenAI-compatible chat completion proxy (non-streaming)."""
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

    model = payload.get("model")
    if not isinstance(model, str) or not model:
        raise GatewayError(
            400, "field 'model' is required", "invalid_request_error", "missing_model"
        )

    if payload.get("stream") is True:
        raise GatewayError(
            400,
            "streaming not implemented yet (planned)",
            "invalid_request_error",
            "streaming_not_supported",
        )

    try:
        target = resolve_target(model)
    except TargetNotFound as exc:
        raise GatewayError(
            400, str(exc), "invalid_request_error", "model_not_found"
        )

    # Adapter raises UpstreamError (a GatewayError) on failure; re-raised as-is.
    return await provider_adapter.chat_completion(target, payload)


@router.get("/v1/models")
async def list_models() -> dict:
    """OpenAI-compatible model list built from providers + combos."""
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


__all__ = ["router"]

"""Shared error types for the OpenAI-compatible gateway.

All gateway failures are raised as :class:`GatewayError` (or its subclass
:class:`UpstreamError`) carrying an OpenAI-shaped error envelope
``{"error": {"message", "type", "code"}}`` plus an HTTP status code. A single
exception handler (registered in ``backend.server``) converts these into a
:class:`fastapi.responses.JSONResponse` so every error matches the contract in
``documents/api/OPENAI_COMPATIBLE_CONTRACT.md``.
"""

from __future__ import annotations

from fastapi.responses import JSONResponse


class GatewayError(Exception):
    """Base gateway error carrying an OpenAI error envelope + HTTP status."""

    def __init__(self, status_code: int, message: str, error_type: str, code: str) -> None:
        self.status_code = status_code
        self.envelope = {"error": {"message": message, "type": error_type, "code": code}}


class UpstreamError(GatewayError):
    """Error originating from (or while reaching) an upstream provider.

    Constructed directly from a pre-built OpenAI envelope so the adapter can
    map arbitrary upstream failures without losing the upstream ``type``/``code``.
    """

    def __init__(self, status_code: int, envelope: dict) -> None:
        self.status_code = status_code
        self.envelope = envelope


def gateway_error_handler(_request, exc: GatewayError) -> JSONResponse:
    """Render a :class:`GatewayError` as a JSON OpenAI error envelope."""
    return JSONResponse(status_code=exc.status_code, content=exc.envelope)


__all__ = ["GatewayError", "UpstreamError", "gateway_error_handler"]

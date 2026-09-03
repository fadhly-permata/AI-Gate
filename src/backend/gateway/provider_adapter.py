"""Provider adapter — forwards requests to an upstream OpenAI-compatible API.

Uses :mod:`httpx` (async). Per **ADR-007** the provider ``api_key`` is sent
plaintext as a ``Bearer`` token (no encryption, no transformation). Upstream
failures are mapped to OpenAI error envelopes and raised as
:class:`~backend.gateway.errors.UpstreamError`.

NOTE: Combo strategy (B1.3) is delegated to ``backend.combo_routing``; this
adapter only performs the raw upstream HTTP call for a resolved target and now
honors an optional egress ``proxy_url`` (ADR-008 / task B2.5).
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

from backend.gateway.errors import UpstreamError
from backend.gateway.resolver import ResolvedTarget
from backend.log import log_error_exc, log_warning_exc

# Outbound timeout (seconds). Streaming SSE will revisit this in a later task.
_DEFAULT_TIMEOUT = 60.0


async def chat_completion(
    target: ResolvedTarget, payload: dict, proxy_url: str | None = None
) -> dict:
    """POST ``{base_url}/chat/completions`` and return the upstream JSON.

    :param target: a resolved upstream (base_url + api_key).
    :param payload: the raw OpenAI-style request body (forwarded as-is).
    :param proxy_url: optional egress proxy URL (ADR-008). When set, httpx
      routes the upstream call through it. Never logged (ADR-011 secret-safe).
    :raises UpstreamError: on any network or upstream HTTP failure.
    """
    url = target.base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {target.api_key}",
        "Content-Type": "application/json",
    }

    # ADR-007: api_key sent plaintext as Bearer (no encryption / masking).
    # Rewrite the request `model` to the REAL upstream model id; the
    # `provider:`-prefixed reference must never reach the upstream provider.
    # All other fields (messages, temperature, n, ...) pass through verbatim.
    out = dict(payload)
    out["model"] = target.upstream_model

    try:
        client_kwargs: dict = {"timeout": _DEFAULT_TIMEOUT}
        # ADR-008: egress proxy binding (Endpoint -> ProxyPool). httpx applies
        # a string proxy to all schemes (http/https). No proxy creds leak to the
        # upstream — they live only in this hop.
        if proxy_url:
            client_kwargs["proxies"] = proxy_url
        async with httpx.AsyncClient(**client_kwargs) as client:
            resp = await client.post(url, headers=headers, json=out)
    except httpx.ConnectError as exc:
        logger.error("upstream unreachable: %s", exc, exc_info=True)
        log_error_exc(
            f"upstream unreachable: {exc}", source="backend.gateway.provider_adapter", exc=exc
        )
        raise UpstreamError(
            503,
            _error(f"upstream unreachable: {exc}", "upstream_error", "proxy_503"),
        )
    except httpx.TimeoutException as exc:
        logger.error("upstream timeout: %s", exc, exc_info=True)
        log_error_exc(
            f"upstream timeout: {exc}", source="backend.gateway.provider_adapter", exc=exc
        )
        raise UpstreamError(
            504,
            _error(f"upstream timeout: {exc}", "upstream_error", "upstream_timeout"),
        )
    except httpx.HTTPError as exc:
        logger.error("upstream request failed: %s", exc, exc_info=True)
        log_error_exc(
            f"upstream request failed: {exc}", source="backend.gateway.provider_adapter", exc=exc
        )
        raise UpstreamError(
            503,
            _error(f"upstream request failed: {exc}", "upstream_error", "proxy_503"),
        )

    # Map upstream HTTP statuses to OpenAI envelopes.
    if resp.status_code == 401:
        raise UpstreamError(
            502,
            _error("upstream authentication failed", "upstream_error", "upstream_401"),
        )
    if 500 <= resp.status_code < 600:
        raise UpstreamError(
            502,
            _error(
                f"upstream error (HTTP {resp.status_code})",
                "upstream_error",
                "upstream_5xx",
            ),
        )
    if 400 <= resp.status_code < 500:
        try:
            body = resp.json()
            message = str(body.get("error", body))
        except Exception:  # noqa: BLE001 - fall back to raw text
            logger.warning(
                "could not parse upstream error body (HTTP %s)",
                resp.status_code,
                exc_info=True,
            )
            log_warning_exc(
                f"could not parse upstream error body (HTTP {resp.status_code})",
                source="backend.gateway.provider_adapter",
            )
            message = resp.text or f"upstream error (HTTP {resp.status_code})"
        raise UpstreamError(
            resp.status_code,
            _error(message, "upstream_error", f"upstream_{resp.status_code}"),
        )

    try:
        return resp.json()
    except Exception as exc:  # noqa: BLE001 - bad upstream payload
        logger.error("invalid upstream JSON response: %s", exc, exc_info=True)
        log_error_exc(
            f"invalid upstream JSON response: {exc}",
            source="backend.gateway.provider_adapter",
            exc=exc,
        )
        raise UpstreamError(
            502,
            _error(f"invalid upstream JSON: {exc}", "upstream_error", "upstream_bad_response"),
        )


def _error(message: str, error_type: str, code: str) -> dict:
    return {"error": {"message": message, "type": error_type, "code": code}}


__all__ = ["chat_completion"]

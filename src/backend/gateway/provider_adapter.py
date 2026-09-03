"""Provider adapter — forwards requests to an upstream OpenAI-compatible API.

Uses :mod:`httpx` (async). Per **ADR-007** the provider ``api_key`` is sent
plaintext as a ``Bearer`` token (no encryption, no transformation). Upstream
failures are mapped to OpenAI error envelopes and raised as
:class:`~backend.gateway.errors.UpstreamError`.

NOTE: proxy pools (B1.2) and Combo strategy (B1.3) are out of scope here; this
adapter only performs the raw upstream HTTP call for a resolved target.
"""

from __future__ import annotations

import httpx

from backend.gateway.errors import UpstreamError
from backend.gateway.resolver import ResolvedTarget

# Outbound timeout (seconds). Streaming SSE will revisit this in a later task.
_DEFAULT_TIMEOUT = 60.0


async def chat_completion(target: ResolvedTarget, payload: dict) -> dict:
    """POST ``{base_url}/chat/completions`` and return the upstream JSON.

    :param target: a resolved upstream (base_url + api_key).
    :param payload: the raw OpenAI-style request body (forwarded as-is).
    :raises UpstreamError: on any network or upstream HTTP failure.
    """
    url = target.base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {target.api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, json=payload)
    except httpx.ConnectError as exc:
        raise UpstreamError(
            503,
            _error(f"upstream unreachable: {exc}", "upstream_error", "proxy_503"),
        )
    except httpx.TimeoutException as exc:
        raise UpstreamError(
            504,
            _error(f"upstream timeout: {exc}", "upstream_error", "upstream_timeout"),
        )
    except httpx.HTTPError as exc:
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
            message = resp.text or f"upstream error (HTTP {resp.status_code})"
        raise UpstreamError(
            resp.status_code,
            _error(message, "upstream_error", f"upstream_{resp.status_code}"),
        )

    try:
        return resp.json()
    except Exception as exc:  # noqa: BLE001 - bad upstream payload
        raise UpstreamError(
            502,
            _error(f"invalid upstream JSON: {exc}", "upstream_error", "upstream_bad_response"),
        )


def _error(message: str, error_type: str, code: str) -> dict:
    return {"error": {"message": message, "type": error_type, "code": code}}


__all__ = ["chat_completion"]

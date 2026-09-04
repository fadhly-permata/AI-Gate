"""Provider adapter — forwards requests to an upstream OpenAI-compatible API.

Uses :mod:`httpx` (async). Per **ADR-007** the provider ``api_key`` is sent
plaintext as a ``Bearer`` token (no encryption, no transformation). Upstream
failures are mapped to OpenAI error envelopes and raised as
:class:`~backend.gateway.errors.UpstreamError`.

NOTE: Combo strategy (B1.3) is delegated to ``backend.combo_routing``; this
adapter only performs the raw upstream HTTP call for a resolved target and now
honors an optional egress ``proxy_url`` (ADR-008 / task B2.5).

Streaming (SSE): :func:`chat_completion_stream` proxies an upstream
``stream:true`` response back as raw OpenAI-format SSE bytes (pass-through).
Per-chunk translation for non-OpenAI formats (anthropic/gemini) is NOT
implemented — the router rejects those with a ``streaming_unsupported_format``
envelope (known limitation, documented in the router + receipt).
"""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

import httpx

logger = logging.getLogger(__name__)

from backend.gateway.errors import UpstreamError
from backend.gateway.resolver import ResolvedTarget
from backend.gateway.translator import (
    translate_error,
    translate_request,
    translate_response,
)
from backend.log import log_error_exc, log_warning_exc

# Outbound timeout (seconds) for the NON-streaming call.
_DEFAULT_TIMEOUT = 60.0
# Streaming timeout: a generous READ budget (time between SSE chunks can be
# long while the model "thinks") but a tight CONNECT budget so an unreachable
# upstream fails fast (surfaced as a 503 before any bytes reach the client).
_STREAM_TIMEOUT = httpx.Timeout(30.0, connect=10.0, read=300.0, write=30.0, pool=10.0)


async def chat_completion(
    target: ResolvedTarget, payload: dict, proxy_url: str | None = None
) -> dict:
    """POST to the upstream and return an OpenAI-shaped JSON response.

    When ``target.format != 'openai'`` the request/response are transparently
    translated by the Format Translation Engine (ADR-012). The OpenAI path is
    kept 100% unchanged so existing behaviour is preserved.

    :param target: a resolved upstream (base_url + api_key + format).
    :param payload: the raw OpenAI-style request body.
    :param proxy_url: optional egress proxy URL (ADR-008).
    :raises UpstreamError: on any network or upstream HTTP failure.
    """
    # ADR-007: api_key sent plaintext (no encryption / masking).
    # Rewrite the request `model` to the REAL upstream model id; the
    # `provider:`-prefixed reference must never reach the upstream provider.
    out = dict(payload)
    out["model"] = target.upstream_model

    fmt = (target.format or "openai").lower()

    if fmt == "openai":
        # --- unchanged OpenAI pass-through path -----------------------------
        url = target.base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {target.api_key}",
            "Content-Type": "application/json",
        }
        body = out
    else:
        # --- ADR-012 format translation -------------------------------------
        req = translate_request(fmt, out)
        url = target.base_url.rstrip("/") + req["url_path"]
        if fmt == "anthropic":
            # Anthropic authenticates with x-api-key (NOT Authorization Bearer)
            # and requires the anthropic-version header.
            headers = {
                "x-api-key": target.api_key,
                "anthropic-version": req["headers_extra"].get(
                    "anthropic-version", "2023-06-01"
                ),
                "Content-Type": "application/json",
            }
        else:
            headers = {
                "Authorization": f"Bearer {target.api_key}",
                "Content-Type": "application/json",
            }
            headers.update(req["headers_extra"])
        body = req["body"]

    try:
        client_kwargs: dict = {"timeout": _DEFAULT_TIMEOUT}
        # ADR-008: egress proxy binding (Endpoint -> ProxyPool). httpx applies
        # a string proxy to all schemes (http/https). No proxy creds leak to the
        # upstream — they live only in this hop.
        if proxy_url:
            client_kwargs["proxies"] = proxy_url
        async with httpx.AsyncClient(**client_kwargs) as client:
            resp = await client.post(url, headers=headers, json=body)
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
    if fmt == "openai":
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
    else:
        # Translated formats: surface the native error through translate_error so
        # the client still receives an OpenAI-shaped envelope (ADR-012).
        if not 200 <= resp.status_code < 300:
            try:
                err_body = resp.json()
            except Exception:  # noqa: BLE001 - fall back to raw text
                logger.warning(
                    "could not parse %s upstream error body (HTTP %s)",
                    fmt,
                    resp.status_code,
                    exc_info=True,
                )
                log_warning_exc(
                    f"could not parse {fmt} upstream error body "
                    f"(HTTP {resp.status_code})",
                    source="backend.gateway.provider_adapter",
                )
                err_body = resp.text or None
            raise UpstreamError(
                resp.status_code,
                translate_error(fmt, resp.status_code, err_body),
            )

    try:
        data = resp.json()
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

    # Translate non-OpenAI responses back into the OpenAI contract shape.
    if fmt != "openai":
        data = translate_response(fmt, data)
    return data


async def chat_completion_stream(
    target: ResolvedTarget, payload: dict, proxy_url: str | None = None
) -> AsyncIterator[bytes]:
    """Proxy an upstream ``stream:true`` SSE response back as raw bytes.

    OpenAI-format PASS-THROUGH only: the upstream's SSE bytes (``data: {json}\\n\\n``
    frames ending with ``data: [DONE]``) are yielded verbatim so any
    OpenAI-compatible streaming client (opencode / aider / claude-code / ...)
    receives exactly what the upstream produced. The request ``model`` is
    rewritten to the real upstream id and ``stream`` is forced true (ADR-007:
    ``api_key`` sent plaintext as a Bearer token).

    Errors mirror the non-streaming path so the router can render the same OpenAI
    envelope:

    * connect / timeout / transport failure BEFORE the first byte ->
      :class:`UpstreamError` (503/504) raised on the first ``__anext__``;
    * upstream HTTP 401 / 5xx / 4xx -> :class:`UpstreamError` with the mapped
      envelope, raised before any body chunk is yielded;
    * a transport failure MID-STREAM (after bytes already reached the client) ->
      logged (R12) then re-raised as :class:`UpstreamError` (the client sees a
      truncated stream; the HTTP status was already committed as 200).

    The ``httpx.AsyncClient`` is owned by an ``async with`` so it is ALWAYS
    closed — on normal completion, on error, and on early consumer disconnect
    (``GeneratorExit`` propagates through the context managers).

    :param target: a resolved upstream (base_url + api_key + format).
    :param payload: the raw OpenAI-style request body.
    :param proxy_url: optional egress proxy URL (ADR-008).
    :raises UpstreamError: on any network or upstream HTTP failure.
    """
    fmt = (target.format or "openai").lower()
    if fmt != "openai":
        # Defensive: the router gates translated formats with a 400 before ever
        # calling this. Per-chunk SSE translation is a known unimplemented case.
        raise UpstreamError(
            400,
            _error(
                "streaming is not yet supported for translated providers "
                "(anthropic/gemini); use a non-stream request or an "
                "OpenAI-compatible provider",
                "invalid_request_error",
                "streaming_unsupported_format",
            ),
        )

    # Rewrite model -> real upstream id; force stream. Copy so the caller's
    # payload dict is never mutated.
    out = dict(payload)
    out["model"] = target.upstream_model
    out["stream"] = True

    url = target.base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {target.api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    client_kwargs: dict = {"timeout": _STREAM_TIMEOUT}
    # ADR-008: egress proxy binding. httpx applies a string proxy to all schemes;
    # proxy creds live only in this hop (never leak to the upstream).
    if proxy_url:
        client_kwargs["proxies"] = proxy_url

    try:
        async with httpx.AsyncClient(**client_kwargs) as client:
            async with client.stream("POST", url, headers=headers, json=out) as resp:
                # --- status -> envelope mapping (same codes as non-stream) -----
                if resp.status_code == 401:
                    raise UpstreamError(
                        502,
                        _error(
                            "upstream authentication failed",
                            "upstream_error",
                            "upstream_401",
                        ),
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
                    raw = await resp.aread()
                    try:
                        parsed = json.loads(raw)
                        message = str(parsed.get("error", parsed))
                    except Exception:  # noqa: BLE001 - fall back to raw text
                        logger.warning(
                            "could not parse upstream streaming error body "
                            "(HTTP %s)",
                            resp.status_code,
                            exc_info=True,
                        )
                        log_warning_exc(
                            f"could not parse upstream streaming error body "
                            f"(HTTP {resp.status_code})",
                            source="backend.gateway.provider_adapter",
                        )
                        message = (
                            raw.decode("utf-8", "replace")
                            or f"upstream error (HTTP {resp.status_code})"
                        )
                    raise UpstreamError(
                        resp.status_code,
                        _error(
                            message,
                            "upstream_error",
                            f"upstream_{resp.status_code}",
                        ),
                    )

                # --- 2xx: forward the SSE byte stream verbatim ------------------
                try:
                    async for chunk in resp.aiter_bytes():
                        yield chunk
                except httpx.RequestError as exc:
                    # Mid-stream transport failure (ReadError / RemoteProtocolError
                    # / ReadTimeout / ...): bytes already reached the client (status
                    # committed 200). Log (R12) + surface as an UpstreamError so the
                    # stream terminates honestly, never a silent truncation.
                    logger.error("upstream stream interrupted: %s", exc, exc_info=True)
                    log_error_exc(
                        f"upstream stream interrupted: {exc}",
                        source="backend.gateway.provider_adapter",
                        exc=exc,
                    )
                    raise UpstreamError(
                        502,
                        _error(
                            f"upstream stream interrupted: {exc}",
                            "upstream_error",
                            "upstream_stream_interrupted",
                        ),
                    )
    except httpx.TimeoutException as exc:
        logger.error("upstream stream timeout: %s", exc, exc_info=True)
        log_error_exc(
            f"upstream stream timeout: {exc}",
            source="backend.gateway.provider_adapter",
            exc=exc,
        )
        raise UpstreamError(
            504,
            _error(
                f"upstream timeout: {exc}", "upstream_error", "upstream_timeout"
            ),
        )
    except httpx.ConnectError as exc:
        logger.error("upstream unreachable (stream): %s", exc, exc_info=True)
        log_error_exc(
            f"upstream unreachable: {exc}",
            source="backend.gateway.provider_adapter",
            exc=exc,
        )
        raise UpstreamError(
            503,
            _error(
                f"upstream unreachable: {exc}", "upstream_error", "proxy_503"
            ),
        )
    except httpx.RequestError as exc:
        # Broad transport fallback (ReadError/WriteError/PoolTimeout/...).
        # NOTE: httpx's root is HTTPError; RequestError covers all request-side
        # failures (ConnectError/TimeoutException are subclasses, caught above
        # first). UpstreamError raised inside the body is NOT a RequestError, so
        # it propagates untouched (already the final mapped error).
        logger.error("upstream stream request failed: %s", exc, exc_info=True)
        log_error_exc(
            f"upstream request failed: {exc}",
            source="backend.gateway.provider_adapter",
            exc=exc,
        )
        raise UpstreamError(
            503,
            _error(
                f"upstream request failed: {exc}", "upstream_error", "proxy_503"
            ),
        )


def _error(message: str, error_type: str, code: str) -> dict:
    return {"error": {"message": message, "type": error_type, "code": code}}


__all__ = ["chat_completion", "chat_completion_stream"]

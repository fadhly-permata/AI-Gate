"""Self-contained demo of the ``respx`` HTTP-mocking pattern.

This module is pure pattern documentation + a runnable example. It does NOT
import the aigate app. It shows how B1.1 gateway tests will mock upstream
provider calls: an ``httpx.AsyncClient`` POST intercepted by ``respx.mock``
returns canned JSON, so no real network call is made.
"""

from __future__ import annotations

import httpx
import pytest
import respx


async def post_json(url: str, payload: dict) -> dict:
    """POST ``payload`` as JSON to ``url`` and return the parsed JSON body."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()


@pytest.mark.asyncio
async def test_respx_intercepts_post() -> None:
    url = "https://api.provider.test/v1/chat/completions"
    with respx.mock:
        respx.post(url).mock(
            return_value=httpx.Response(
                200, json={"status": "ok", "id": "demo", "model": "provider:test"}
            )
        )
        result = await post_json(url, {"model": "provider:test", "messages": []})
    assert result == {
        "status": "ok",
        "id": "demo",
        "model": "provider:test",
    }

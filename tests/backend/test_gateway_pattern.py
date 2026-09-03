"""Placeholder for B1.1 gateway tests (respx + httpx against /v1/chat/completions).

Intended pattern (implemented in B1.1):
- Build a TestClient over ``backend.server.app`` (reuse the ``client`` fixture).
- Seed an in-memory SQLite ``db_session`` with a Provider + Combo + members.
- Use ``respx.mock`` to intercept the upstream provider POST to
  ``/v1/chat/completions`` and return a canned OpenAI-style response.
- Assert the gateway proxies/forwards the response envelope unchanged.

Skipped until B1.1 lands.
"""

from __future__ import annotations

import pytest


def test_b11_gateway_pattern() -> None:
    pytest.skip(reason="B1.1 not implemented yet")

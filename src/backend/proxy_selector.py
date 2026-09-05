"""Reusable proxy-selection + URL-building helpers (task B2.3).

Pure functions operating on ORM models so they can be imported by the gateway
later (B2.5 endpoint-proxy-binding) without any request/router dependency.

ADR-007: ``username``/``password`` are returned in plaintext — no masking.
Pydantic **v1** only (rule R10): this module is ORM-only, no pydantic.
ADR-011 / R12: selection failures are logged, never swallowed.
"""

from __future__ import annotations

import random
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.log import log_warning
from backend.models import ProxyNode, ProxyPool

LOG_SOURCE = "backend.proxies.selector"

# Nodes whose liveness check passed are eligible for selection.
_HEALTHY = "healthy"


def build_proxy_url(node: ProxyNode) -> str:
    """Build the proxy URL for an httpx ``proxies=`` value.

    Scheme mapping:
      - ``https``  -> ``https://``
      - ``socks5`` -> ``socks5://``
      - (default)  -> ``http://``
    Only include ``user:pass@`` when BOTH username and password are non-empty.
    """
    scheme = (node.protocol or "http").lower()
    if scheme == "https":
        base = "https://"
    elif scheme == "socks5":
        base = "socks5://"
    else:
        base = "http://"

    creds = ""
    if node.username and node.password:
        creds = f"{node.username}:{node.password}@"

    return f"{base}{creds}{node.host}:{node.port}"


def select_node(
    pool: ProxyPool, session: Optional[Session] = None
) -> Optional[ProxyNode]:
    """Select a proxy node from ``pool`` per its rotation strategy.

    Only nodes with ``status == "healthy"`` are eligible. If none are healthy,
    returns ``None`` (caller must handle "no usable proxy").

    - ``failover``     -> first healthy node by ``id`` asc.
    - ``random``       -> a uniformly random healthy node.
    - ``round_robin``  -> healthy node at ``pool.last_used_index`` (wrapped),
                          then advances the cursor (and commits if ``session``
                          was supplied).

    The passed ``session`` is committed only for round_robin cursor advance and
    left otherwise untouched on failure.
    """
    candidates: List[ProxyNode] = [n for n in pool.nodes if n.status == _HEALTHY]
    if not candidates:
        log_warning(
            f"select_node: pool {pool.id} ({pool.name}) has no healthy nodes",
            source=LOG_SOURCE,
        )
        return None

    strategy = (pool.rotation_strategy or "round_robin").lower()

    if strategy == "failover":
        return sorted(candidates, key=lambda n: n.id)[0]

    if strategy == "random":
        return random.choice(candidates)

    # default: round_robin
    idx = pool.last_used_index % len(candidates)
    chosen = candidates[idx]
    pool.last_used_index = pool.last_used_index + 1
    if session is not None:
        try:
            session.commit()
        except Exception as exc:  # noqa: BLE001 - cursor persist must not crash
            log_warning(
                f"select_node: failed to persist last_used_index for pool "
                f"{pool.id}: {exc}",
                source=LOG_SOURCE,
            )
            session.rollback()
    return chosen


__all__ = ["build_proxy_url", "select_node"]

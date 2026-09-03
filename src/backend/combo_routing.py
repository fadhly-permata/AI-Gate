"""Combo strategy routing engine (task B2.4).

Implements the three Combo strategies from FSD.md §2.3 / TSD §4.3:

* ``fallback``      — try members in ``priority`` asc order; on ``UpstreamError``
  log a warning and advance to the next; re-raise the LAST error if all fail.
* ``load_balance``  — weighted random selection across members.
* ``latency_cost``  — pick the lowest-``weight`` member (weight models relative
  cost), tie-break by ``priority`` asc. Single attempt, no retry.

ADR-011 / R12: every method logs to ``LogEntry`` via ``backend.log``; no
swallowed exceptions.

Pydantic **v1** only is irrelevant here (ORM-only module, no pydantic).
"""

from __future__ import annotations

import random
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config.db import SessionLocal
from backend.gateway import provider_adapter
from backend.gateway.errors import UpstreamError
from backend.gateway.resolver import ResolvedTarget, TargetNotFound
from backend.log import log_info, log_warning
from backend.models import Combo, ComboMember, Provider, ProviderModel

LOG_SOURCE = "backend.combo.routing"


def build_candidates(combo: Combo, session: Session) -> List[ResolvedTarget]:
    """Resolve one :class:`ResolvedTarget` per :class:`ComboMember`.

    Members are ordered by ``priority`` asc. For each member:

    * resolve its :class:`Provider` by ``provider_id``;
    * ``upstream_model`` = member ``provider_model`` if non-empty, else the
      provider's first :class:`ProviderModel.model_id` (by id asc);
    * skip (and warn) members whose provider is missing or which end up with no
      usable upstream model.

    :param combo: the loaded :class:`Combo`.
    :param session: an active SQLAlchemy session.
    :returns: ordered candidate targets (may be empty).
    """
    members = (
        session.query(ComboMember)
        .filter_by(combo_id=combo.id)
        .order_by(ComboMember.priority.asc())
        .all()
    )
    candidates: List[ResolvedTarget] = []
    for member in members:
        provider = session.get(Provider, member.provider_id)
        if provider is None:
            log_warning(
                f"build_candidates: combo '{combo.name}' member {member.id} "
                f"references missing provider {member.provider_id}",
                source=LOG_SOURCE,
            )
            continue

        if member.provider_model:
            upstream_model = member.provider_model
        else:
            first_model = session.scalars(
                select(ProviderModel)
                .where(ProviderModel.provider_id == provider.id)
                .order_by(ProviderModel.id.asc())
            ).first()
            upstream_model = first_model.model_id if first_model is not None else ""

        if not upstream_model:
            log_warning(
                f"build_candidates: combo '{combo.name}' member {member.id} "
                f"has no upstream model (provider {provider.id} has none)",
                source=LOG_SOURCE,
            )
            continue

        candidates.append(
            ResolvedTarget(
                base_url=provider.base_url,
                api_key=provider.api_key,
                model_ref=f"combo:{combo.name}",
                upstream_model=upstream_model,
                combo_used=True,
                priority=member.priority,
                weight=member.weight,
            )
        )

    log_info(
        f"build_candidates: combo '{combo.name}' -> {len(candidates)} candidate(s)",
        source=LOG_SOURCE,
        context={"combo": combo.name, "members": len(members)},
    )
    return candidates


def select_member(
    strategy: str,
    candidates: List[ResolvedTarget],
    session: Optional[Session] = None,
) -> ResolvedTarget:
    """Pick a single member for ``load_balance`` / ``latency_cost``.

    ``fallback`` is NOT used here (it is handled by :func:`execute_combo`).

    * ``load_balance`` -> ``random.choices(candidates, weights=...)`` with a
      floor of ``0.0001`` so zero-weight members are still reachable.
    * ``latency_cost`` -> lowest ``weight``, tie-break by ``priority`` asc
      (candidates are already ordered by priority). Single attempt, no retry.

    :param strategy: combo strategy string.
    :param candidates: non-empty ordered candidate list.
    :param session: reserved for B2.5 (per-node latency lookups); unused now.
    :raises UpstreamError: if ``candidates`` is empty (nothing to select).
    """
    _ = session  # reserved for future latency data (B2.5)
    if not candidates:
        raise UpstreamError(
            502,
            {
                "error": {
                    "message": "combo has no usable members to select from",
                    "type": "upstream_error",
                    "code": "combo_no_members",
                }
            },
        )

    strat = (strategy or "fallback").lower()

    if strat == "load_balance":
        weights = [max(float(c.weight), 0.0001) for c in candidates]
        return random.choices(candidates, weights=weights)[0]

    if strat == "latency_cost":
        # SIMPLIFICATION (B2.4): true latency_cost requires per-proxy-node
        # latency from the B2.5 health checks, which are not in scope here.
        # `weight` therefore models RELATIVE COST: choose the lowest-weight
        # candidate, tie-break by priority asc. Single attempt, no retry.
        return min(candidates, key=lambda c: (c.weight, c.priority))

    # fallback / unknown -> single select is not used by execute_combo; default
    # to the first (priority asc) candidate for safety.
    return candidates[0]


async def execute_combo(
    combo_ref: str | int, payload: dict, proxy_url: Optional[str] = None
) -> dict:
    """Route a chat-completion request through a Combo's strategy.

    :param combo_ref: the combo's ``name`` OR its integer ``id`` (task B2.5:
      an Endpoint may bind a combo by id). A string is matched against
      ``Combo.name``; an int is matched against ``Combo.id``.
    :param payload: the raw OpenAI-style request body (forwarded verbatim).
    :param proxy_url: optional egress proxy URL (ADR-008) threaded to the
      provider adapter for each attempt.
    :raises TargetNotFound: if no matching combo exists.
    :raises UpstreamError: if every attempt fails (fallback) or the single
      selected attempt fails (load_balance / latency_cost), or there are no
      usable members.
    :returns: the upstream JSON response dict.
    """
    combo_name = combo_ref if isinstance(combo_ref, str) else str(combo_ref)
    log_info(
        f"execute_combo: start for combo ref '{combo_ref}'"
        + (f" via proxy {proxy_url}" if proxy_url else ""),
        source=LOG_SOURCE,
        context={"combo": combo_name, "has_proxy": proxy_url is not None},
    )

    with SessionLocal() as session:
        if isinstance(combo_ref, int):
            combo = session.get(Combo, combo_ref)
        else:
            combo = session.scalars(
                select(Combo).where(Combo.name == combo_ref)
            ).first()
        if combo is None:
            raise TargetNotFound(f"combo '{combo_ref}' not found")
        candidates = build_candidates(combo, session)
        strategy = (combo.strategy or "fallback").lower()

    if strategy == "fallback":
        last_err: Optional[UpstreamError] = None
        for target in candidates:
            try:
                result = await provider_adapter.chat_completion(
                    target, payload, proxy_url
                )
                log_info(
                    f"execute_combo: fallback success via member "
                    f"(model={target.upstream_model})",
                    source=LOG_SOURCE,
                    context={"combo": combo_name, "model": target.upstream_model},
                )
                return result
            except UpstreamError as exc:
                log_warning(
                    f"execute_combo: fallback member failed "
                    f"(model={target.upstream_model}): {exc.envelope}",
                    source=LOG_SOURCE,
                    context={"combo": combo_name, "model": target.upstream_model},
                )
                last_err = exc
        if last_err is not None:
            log_warning(
                f"execute_combo: all {len(candidates)} fallback member(s) "
                f"failed for combo '{combo_name}'",
                source=LOG_SOURCE,
                context={"combo": combo_name},
            )
            raise last_err
        # No candidates at all.
        raise UpstreamError(
            502,
            {
                "error": {
                    "message": f"combo '{combo_name}' has no usable members",
                    "type": "upstream_error",
                    "code": "combo_no_members",
                }
            },
        )

    # load_balance / latency_cost: select one member, single attempt.
    target = select_member(strategy, candidates, None)
    result = await provider_adapter.chat_completion(target, payload, proxy_url)
    log_info(
        f"execute_combo: {strategy} success via member "
        f"(model={target.upstream_model})",
        source=LOG_SOURCE,
        context={"combo": combo_name, "model": target.upstream_model},
    )
    return result


__all__ = ["build_candidates", "select_member", "execute_combo"]

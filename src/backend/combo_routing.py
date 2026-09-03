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
from backend.gateway.translator import format_for_provider_type
from backend.log import log_error_exc, log_info, log_warning
from backend.models import Combo, ComboMember, Provider, ProviderAccount, ProviderModel
from backend.oauth import get_valid_token, select_provider_credential

LOG_SOURCE = "backend.combo.routing"

# B5.2: 3-Tier Fallback ordering. Lower rank = tried first.
TIER_RANK = {"subscription": 0, "cheap": 1, "free": 2}

# Account-switchable error signature (cadangan antar-akun). A limit/quota/auth
# failure on a member should trigger a retry against the NEXT enabled
# ProviderAccount of the SAME provider before advancing to the next member.
_ACCOUNT_SWITCH_TOKENS = ("quota", "rate", "unauthorized", "401")


def provider_tier(provider: Provider) -> str:
    """Classify a :class:`Provider` into one of the 3 tiers.

    * explicit ``provider.tier`` wins if it is one of the allowed values;
    * else classify by ``provider.type``:
      ``ollama`` -> ``'free'``; ``openrouter``/``litellm`` -> ``'cheap'``;
      everything else -> ``'subscription'``.
    """
    t = (getattr(provider, "tier", None) or "").lower()
    if t in TIER_RANK:
        return t
    ptype = (getattr(provider, "type", None) or "").lower()
    if ptype == "ollama":
        return "free"
    if ptype in ("openrouter", "litellm"):
        return "cheap"
    return "subscription"


def _is_account_switchable(exc: UpstreamError) -> bool:
    """True if ``exc`` is a limit/quota/auth error worth retrying on another account."""
    if exc.status_code == 429:
        return True
    err = (exc.envelope or {}).get("error", {}) or {}
    hay = f"{err.get('code', '')} {err.get('message', '')}".lower()
    return any(tok in hay for tok in _ACCOUNT_SWITCH_TOKENS)


def quota_aware_order(candidates, session) -> List[ResolvedTarget]:
    """B5.2 (scaffold): prefer members with remaining quota when data exists.

    # TODO B5.5: once quota tracking (UsageRecord) lands, reorder ``candidates``
    # to prefer members with remaining quota. For now this is a NO-OP
    # pass-through so routing is never blocked when no quota data is present.
    """
    # TODO B5.5: implement real quota-aware reordering here.
    if candidates:
        log_info(
            "quota tracking not yet available (B5.5) — skipping quota-aware "
            "ordering",
            source=LOG_SOURCE,
            context={"candidates": len(candidates)},
        )
    return candidates


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
        .all()
    )

    strategy = (combo.strategy or "fallback").lower()
    if strategy == "three_tier":
        # B5.2: order by tier rank (subscription->cheap->free) then priority asc.
        def _member_key(m: ComboMember):
            prov = session.get(Provider, m.provider_id)
            tier = provider_tier(prov) if prov is not None else "subscription"
            return (TIER_RANK.get(tier, 0), m.priority)

        members.sort(key=_member_key)
    else:
        members.sort(key=lambda m: m.priority)

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
                api_key=select_provider_credential(provider, session),
                model_ref=f"combo:{combo.name}",
                upstream_model=upstream_model,
                combo_used=True,
                priority=member.priority,
                weight=member.weight,
                provider_id=provider.id,
                format=format_for_provider_type(provider.type),
            )
        )

    # B5.2 (scaffold): quota-aware ordering is a no-op until B5.5 lands, but we
    # still call it for fallback / three_tier so it can later reorder in place.
    if strategy in ("fallback", "three_tier"):
        candidates = quota_aware_order(candidates, session)

    log_info(
        f"build_candidates: combo '{combo.name}' -> {len(candidates)} candidate(s)",
        source=LOG_SOURCE,
        context={"combo": combo.name, "members": len(members), "strategy": strategy},
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

        # B5.2 (Cadangan Antar-Akun): precompute the credential list for every
        # enabled ProviderAccount of each candidate's provider so a limit/quota
        # error can retry on the NEXT account within the same request. Credentials
        # are resolved up-front (OAuth auto-refresh applied) so the async retry
        # loop needs no live session.
        account_creds: dict[int, list] = {}
        for target in candidates:
            if not target.provider_id:
                continue
            accounts = (
                session.query(ProviderAccount)
                .filter_by(provider_id=target.provider_id, enabled=True)
                .order_by(ProviderAccount.id.asc())
                .all()
            )
            creds = []
            for acc in accounts:
                try:
                    creds.append(get_valid_token(acc, session))
                except Exception as exc:  # noqa: BLE001 - log + skip unusable account
                    log_error_exc(
                        "execute_combo: account credential unavailable; skipping",
                        source=LOG_SOURCE,
                        exc=exc,
                        context={"provider_id": target.provider_id, "account_id": acc.id},
                    )
            account_creds[target.provider_id] = creds

    # three_tier reuses the sequential fallback semantics (advance on error);
    # the only difference (tier ordering) is already applied in build_candidates.
    if strategy in ("fallback", "three_tier"):
        last_err: Optional[UpstreamError] = None
        for target in candidates:
            creds = account_creds.get(target.provider_id) or []
            acct_cursor = 0  # index of the credential currently in target.api_key
            while True:
                try:
                    result = await provider_adapter.chat_completion(
                        target, payload, proxy_url
                    )
                    log_info(
                        f"execute_combo: {strategy} success via member "
                        f"(model={target.upstream_model})",
                        source=LOG_SOURCE,
                        context={"combo": combo_name, "model": target.upstream_model},
                    )
                    return result
                except UpstreamError as exc:
                    # B5.2 (Cadangan Antar-Akun): on a limit/quota/auth error,
                    # retry with the NEXT enabled account of the SAME provider
                    # before advancing to the next combo member. Bounded by the
                    # account count; normal (5xx) errors do NOT spin on accounts.
                    if _is_account_switchable(exc) and acct_cursor + 1 < len(creds):
                        acct_cursor += 1
                        target.api_key = creds[acct_cursor]
                        log_info(
                            "execute_combo: limit/quota error on "
                            f"provider {target.provider_id} — switching to "
                            f"account #{acct_cursor + 1} (cadangan antar-akun)",
                            source=LOG_SOURCE,
                            context={
                                "combo": combo_name,
                                "provider_id": target.provider_id,
                                "account_index": acct_cursor,
                            },
                        )
                        continue
                    log_warning(
                        f"execute_combo: {strategy} member failed "
                        f"(model={target.upstream_model}): {exc.envelope}",
                        source=LOG_SOURCE,
                        context={"combo": combo_name, "model": target.upstream_model},
                    )
                    last_err = exc
                    break  # advance to next member
        if last_err is not None:
            log_warning(
                f"execute_combo: all {len(candidates)} {strategy} member(s) "
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

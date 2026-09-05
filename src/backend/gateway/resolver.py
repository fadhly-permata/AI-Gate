"""Target resolution for the OpenAI-compatible gateway.

A request ``model`` reference is one of:

* ``provider:<name>`` — a single :class:`Provider` (by ``name``).
* ``combo:<name>``   — a :class:`Combo`; for now we pick the first
  :class:`ComboMember` by ``priority`` asc and use its :class:`Provider`.
* a **bare model id** (no prefix) — what OpenAI-compatible CLIs such as
  ``aider`` send. It is resolved against the enabled :class:`Provider`s that
  advertise a matching :class:`ProviderModel.model_id` (see
  :func:`_resolve_bare_model`).

The full Combo routing strategy (fallback / load_balance / latency_cost) is
deferred to **B1.3** — see the ``# TODO B1.3`` marker below. The API here is a
clean extension point: swap the member-selection logic without touching the
router or adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import select

from backend.config.db import SessionLocal
from backend.config.settings import get as get_setting
from backend.gateway.translator import format_for_provider_type
from backend.log import log_info
from backend.models import Combo, Provider, ProviderModel
from backend.oauth import select_provider_credential_with_account

LOG_SOURCE = "backend.gateway.resolver"


class TargetNotFound(Exception):
    """Raised when a model reference cannot be resolved to a provider.

    The router maps this to an OpenAI ``400`` error envelope
    (``invalid_request_error`` / ``model_not_found``).
    """


@dataclass
class ResolvedTarget:
    """A concrete upstream to forward a request to.

    ``model_ref`` is the original request ``model`` string (kept for reference
    and logging). ``upstream_model`` is the REAL model id that must be sent to
    the upstream provider (the ``provider:``-prefixed string is never valid
    upstream).

    ``priority`` / ``weight`` are carried for Combo strategy routing
    (``backend.combo_routing``): ``weight`` drives ``load_balance`` selection,
    ``priority`` is the tie-break for ``latency_cost``.
    """

    base_url: str
    api_key: str
    model_ref: str
    upstream_model: str
    combo_used: bool = False
    priority: int = 0
    weight: float = 1.0
    # B5.2: the originating Provider id, carried so combo routing can perform
    # account-level retry (cadangan antar-akun). Optional; defaults to 0.
    provider_id: int = 0
    # B5.5: the selected ProviderAccount id (None = legacy provider.api_key
    # path). Carried so the gateway can attribute a UsageRecord per account.
    account_id: Optional[int] = None
    # B5.3 (ADR-012): canonical upstream format (openai/anthropic/gemini). Drives
    # the Format Translation Engine. Defaults to "openai" (pass-through).
    format: str = "openai"


def resolve_target(model: str) -> ResolvedTarget:
    """Resolve a ``provider:`` / ``combo:`` model reference to an upstream.

    Accepted forms (canonical scheme, R9):

    * ``provider:<name>`` (2 segments) — resolve Provider by ``name``;
      upstream model = that provider's first ``ProviderModel.model_id``
      (by id asc). ``TargetNotFound`` if the provider has no models.
    * ``provider:<name>:<model_id>`` (3 segments) — resolve Provider by
      ``name``; upstream model = ``<model_id>`` (validated to exist among the
      provider's models).
    * ``combo:<name>`` — first ``ComboMember`` by ``priority`` asc (current
      placeholder; full strategy deferred to B1.3); upstream model =
      that member's ``provider_model``.
    * ``<bare-model-id>`` (no prefix) — resolved against enabled providers that
      advertise a matching ``ProviderModel.model_id`` (see
      :func:`_resolve_bare_model`).

    :param model: the request ``model`` string.
    :raises TargetNotFound: if nothing matches the reference.
    """
    with SessionLocal() as session:
        if model.startswith("provider:"):
            rest = model[len("provider:"):]
            if ":" in rest:
                # 3 segments: provider:<name>:<model_id>
                name, model_id = rest.split(":", 1)
                provider = session.scalars(
                    select(Provider).where(Provider.name == name)
                ).first()
                if provider is None:
                    raise TargetNotFound(f"provider '{name}' not found")
                exists = session.scalars(
                    select(ProviderModel)
                    .where(ProviderModel.provider_id == provider.id)
                    .where(ProviderModel.model_id == model_id)
                ).first()
                if exists is None:
                    raise TargetNotFound(
                        f"model '{model_id}' not found for provider '{name}'"
                    )
                api_key, account_id = select_provider_credential_with_account(
                    provider, session
                )
                return ResolvedTarget(
                    base_url=provider.base_url,
                    api_key=api_key,
                    model_ref=model,
                    upstream_model=model_id,
                    combo_used=False,
                    provider_id=provider.id,
                    account_id=account_id,
                    format=format_for_provider_type(provider.type),
                )
            else:
                # 2 segments: provider:<name> -> first provider model by id asc
                name = rest
                provider = session.scalars(
                    select(Provider).where(Provider.name == name)
                ).first()
                if provider is None:
                    raise TargetNotFound(f"provider '{name}' not found")
                first_model = session.scalars(
                    select(ProviderModel)
                    .where(ProviderModel.provider_id == provider.id)
                    .order_by(ProviderModel.id.asc())
                ).first()
                if first_model is None:
                    raise TargetNotFound(f"provider '{name}' has no models")
                api_key, account_id = select_provider_credential_with_account(
                    provider, session
                )
                return ResolvedTarget(
                    base_url=provider.base_url,
                    api_key=api_key,
                    model_ref=model,
                    upstream_model=first_model.model_id,
                    combo_used=False,
                    provider_id=provider.id,
                    account_id=account_id,
                    format=format_for_provider_type(provider.type),
                )

        if model.startswith("combo:"):
            name = model[len("combo:"):]
            combo = session.scalars(
                select(Combo).where(Combo.name == name)
            ).first()
            if combo is None:
                raise TargetNotFound(f"combo '{name}' not found")

            # B2.4: full strategy routing is delegated to
            # ``backend.combo_routing.execute_combo``. Return a combo marker with
            # ``combo_used=True``; the concrete upstream(s) are resolved per the
            # combo's strategy there. ``base_url``/``api_key`` are left empty
            # because they are strategy-dependent.
            return ResolvedTarget(
                base_url="",
                api_key="",
                model_ref=model,
                upstream_model="",
                combo_used=True,
            )

        # Bare model id (no ``provider:``/``combo:`` prefix). OpenAI-compatible
        # CLIs (aider, etc.) send a plain model name; resolve it against the
        # enabled providers that advertise it.
        return _resolve_bare_model(model, session)


def _pick_default_provider(
    providers: List[Provider], session
) -> Provider:
    """Deterministically choose one provider from an ambiguous bare-model match.

    Preference order (documented, stable):
    1. the provider named in the ``default_provider`` :class:`Setting`, if that
       name is among ``providers``;
    2. otherwise the lowest ``provider.id`` (``providers`` is already ordered by
       ``Provider.id`` asc).

    A config-read failure never breaks resolution — it falls through to the
    lowest-id pick (the underlying error is already logged by
    ``backend.config.settings``).
    """
    try:
        default_name = get_setting("default_provider", session=session)
    except Exception:  # noqa: BLE001 - config read must never break resolution
        default_name = None
    if default_name:
        for provider in providers:
            if provider.name == default_name:
                return provider
    return providers[0]


def _resolve_bare_model(model: str, session) -> ResolvedTarget:
    """Resolve a bare (unprefixed) model id to an enabled provider's upstream.

    ``model`` is matched against ``ProviderModel.model_id`` joined to ENABLED
    :class:`Provider`s:

    * exactly one provider advertises it -> route there (``upstream_model`` =
      ``model``);
    * more than one -> deterministic pick via :func:`_pick_default_provider`
      (``default_provider`` Setting, else lowest id); the ambiguity + choice are
      logged via ``log_info`` (R12);
    * none -> :class:`TargetNotFound` with a hint to use the ``provider:`` form.

    Credential selection reuses B5.1 (:func:`select_provider_credential_with_account`)
    so account round-robin / OAuth apply exactly as on the ``provider:`` path.
    """
    rows = session.scalars(
        select(Provider)
        .join(ProviderModel, ProviderModel.provider_id == Provider.id)
        .where(ProviderModel.model_id == model)
        .where(Provider.enabled.is_(True))
        .order_by(Provider.id.asc())
    ).all()

    # De-duplicate by provider id (a provider may list the same model twice)
    # while preserving the id-asc ordering that makes the pick deterministic.
    providers: List[Provider] = []
    seen: set[int] = set()
    for provider in rows:
        if provider.id not in seen:
            seen.add(provider.id)
            providers.append(provider)

    if not providers:
        raise TargetNotFound(
            f"model '{model}' not found on any enabled provider "
            f"(use 'provider:<name>:{model}' to target a specific provider)"
        )

    if len(providers) == 1:
        provider = providers[0]
    else:
        provider = _pick_default_provider(providers, session)
        log_info(
            f"bare model '{model}' matched {len(providers)} enabled providers; "
            f"resolved ambiguously to provider '{provider.name}' "
            f"(id={provider.id})",
            source=LOG_SOURCE,
            context={
                "model": model,
                "candidates": [p.name for p in providers],
                "chosen": provider.name,
                "ambiguous": True,
            },
        )

    api_key, account_id = select_provider_credential_with_account(provider, session)
    return ResolvedTarget(
        base_url=provider.base_url,
        api_key=api_key,
        model_ref=model,
        upstream_model=model,
        combo_used=False,
        provider_id=provider.id,
        account_id=account_id,
        format=format_for_provider_type(provider.type),
    )


__all__ = ["TargetNotFound", "ResolvedTarget", "resolve_target"]

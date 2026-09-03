"""Target resolution for the OpenAI-compatible gateway.

A request ``model`` reference is one of:

* ``provider:<name>`` — a single :class:`Provider` (by ``name``).
* ``combo:<name>``   — a :class:`Combo`; for now we pick the first
  :class:`ComboMember` by ``priority`` asc and use its :class:`Provider`.

The full Combo routing strategy (fallback / load_balance / latency_cost) is
deferred to **B1.3** — see the ``# TODO B1.3`` marker below. The API here is a
clean extension point: swap the member-selection logic without touching the
router or adapter.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from backend.config.db import SessionLocal
from backend.gateway.translator import format_for_provider_type
from backend.models import Combo, Provider, ProviderModel
from backend.oauth import select_provider_credential


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
                return ResolvedTarget(
                    base_url=provider.base_url,
                    api_key=select_provider_credential(provider, session),
                    model_ref=model,
                    upstream_model=model_id,
                    combo_used=False,
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
                return ResolvedTarget(
                    base_url=provider.base_url,
                    api_key=select_provider_credential(provider, session),
                    model_ref=model,
                    upstream_model=first_model.model_id,
                    combo_used=False,
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

        raise TargetNotFound(
            f"unsupported model reference '{model}' (expected 'provider:' or 'combo:')"
        )


__all__ = ["TargetNotFound", "ResolvedTarget", "resolve_target"]

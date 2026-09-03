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
from backend.models import Combo, ComboMember, Provider


class TargetNotFound(Exception):
    """Raised when a model reference cannot be resolved to a provider.

    The router maps this to an OpenAI ``400`` error envelope
    (``invalid_request_error`` / ``model_not_found``).
    """


@dataclass
class ResolvedTarget:
    """A concrete upstream to forward a request to."""

    base_url: str
    api_key: str
    model_ref: str
    combo_used: bool = False


def resolve_target(model: str) -> ResolvedTarget:
    """Resolve a ``provider:`` / ``combo:`` model reference to an upstream.

    :param model: the request ``model`` string.
    :raises TargetNotFound: if nothing matches the reference.
    """
    with SessionLocal() as session:
        if model.startswith("provider:"):
            name = model[len("provider:"):]
            provider = session.scalars(
                select(Provider).where(Provider.name == name)
            ).first()
            if provider is None:
                raise TargetNotFound(f"provider '{name}' not found")
            return ResolvedTarget(
                base_url=provider.base_url,
                api_key=provider.api_key,
                model_ref=model,
                combo_used=False,
            )

        if model.startswith("combo:"):
            name = model[len("combo:"):]
            combo = session.scalars(
                select(Combo).where(Combo.name == name)
            ).first()
            if combo is None:
                raise TargetNotFound(f"combo '{name}' not found")

            # TODO B1.3: apply strategy (fallback / load_balance / latency_cost).
            # For now: take the first member by priority asc as a placeholder.
            member = session.scalars(
                select(ComboMember)
                .where(ComboMember.combo_id == combo.id)
                .order_by(ComboMember.priority.asc())
            ).first()
            if member is None:
                raise TargetNotFound(f"combo '{name}' has no members")

            provider = member.provider
            if provider is None:
                raise TargetNotFound(f"combo '{name}' member has no provider")

            return ResolvedTarget(
                base_url=provider.base_url,
                api_key=provider.api_key,
                model_ref=model,
                combo_used=True,
            )

        raise TargetNotFound(
            f"unsupported model reference '{model}' (expected 'provider:' or 'combo:')"
        )


__all__ = ["TargetNotFound", "ResolvedTarget", "resolve_target"]

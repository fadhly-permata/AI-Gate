"""Bare-model resolution tests for ``backend.gateway.resolver``.

OpenAI-compatible CLIs (aider, etc.) send a plain model name with no
``provider:``/``combo:`` prefix. ``resolve_target`` must now resolve such a bare
id against the ENABLED providers that advertise a matching
``ProviderModel.model_id``:

* exactly one match -> route there (upstream_model == the bare id);
* multiple matches  -> deterministic pick (``default_provider`` Setting, else
  lowest provider id) + an ambiguity log entry;
* no match          -> ``TargetNotFound`` with a helpful hint.

Hermetic, no on-disk DB: an in-memory SQLite engine (StaticPool) replaces every
``SessionLocal`` the resolver + ``backend.log`` touch (mirrors test_gateway.py).
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.config.db as db_mod
import backend.gateway.resolver as resolver
from backend.config.db import Base
from backend.gateway.resolver import TargetNotFound, resolve_target
from backend.models import (
    Combo,
    LogEntry,
    Provider,
    ProviderAccount,
    ProviderModel,
    Setting,
)


def _make_sf() -> sessionmaker:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _patch(monkeypatch, sf: sessionmaker) -> None:
    """Rebind every ``SessionLocal`` the resolver + logger touch."""
    monkeypatch.setattr(db_mod, "SessionLocal", sf)
    monkeypatch.setattr(resolver, "SessionLocal", sf)


def _add_provider(
    session,
    name: str,
    *,
    base_url: str,
    api_key: str = "sk-plain",
    enabled: bool = True,
    model_ids: tuple[str, ...] = (),
    account_key: str | None = None,
) -> Provider:
    provider = Provider(
        name=name,
        type="openai-compatible",
        base_url=base_url,
        api_key=api_key,
        enabled=enabled,
    )
    session.add(provider)
    session.flush()
    for mid in model_ids:
        session.add(
            ProviderModel(
                provider_id=provider.id, model_id=mid, model_name=mid
            )
        )
    if account_key is not None:
        session.add(
            ProviderAccount(
                provider_id=provider.id,
                label="acct",
                auth_type="api_key",
                api_key=account_key,
                enabled=True,
            )
        )
    return provider


# --------------------------------------------------------------------------- #
# 1. Single enabled provider advertises the bare model -> route there.
# --------------------------------------------------------------------------- #
def test_bare_model_single_provider(monkeypatch) -> None:
    sf = _make_sf()
    _patch(monkeypatch, sf)
    with sf() as s:
        _add_provider(
            s,
            "B.AI",
            base_url="http://b.ai/v1",
            api_key="sk-bai",
            model_ids=("gpt-5.5",),
        )
        s.commit()
        pid = s.query(Provider).filter_by(name="B.AI").first().id

    target = resolve_target("gpt-5.5")
    assert target.upstream_model == "gpt-5.5"
    assert target.model_ref == "gpt-5.5"
    assert target.base_url == "http://b.ai/v1"
    assert target.api_key == "sk-bai"  # legacy provider.api_key (no accounts)
    assert target.account_id is None
    assert target.provider_id == pid
    assert target.combo_used is False
    assert target.format == "openai"


def test_bare_model_uses_account_credential(monkeypatch) -> None:
    """B5.1 credential selection applies on the bare path too (account wins)."""
    sf = _make_sf()
    _patch(monkeypatch, sf)
    with sf() as s:
        _add_provider(
            s,
            "B.AI",
            base_url="http://b.ai/v1",
            api_key="sk-bai",
            model_ids=("gpt-5.5",),
            account_key="acct-key",
        )
        s.commit()
        acct_id = s.query(ProviderAccount).first().id

    target = resolve_target("gpt-5.5")
    assert target.api_key == "acct-key"
    assert target.account_id == acct_id


# --------------------------------------------------------------------------- #
# 2. Ambiguous: two enabled providers both advertise the model.
# --------------------------------------------------------------------------- #
def test_bare_model_ambiguous_lowest_id(monkeypatch) -> None:
    """No default_provider Setting -> deterministic lowest provider.id wins."""
    sf = _make_sf()
    _patch(monkeypatch, sf)
    with sf() as s:
        _add_provider(
            s, "Alpha", base_url="http://alpha/v1", model_ids=("dup-model",)
        )
        _add_provider(
            s, "Beta", base_url="http://beta/v1", model_ids=("dup-model",)
        )
        s.commit()
        alpha_id = s.query(Provider).filter_by(name="Alpha").first().id

    target = resolve_target("dup-model")
    assert target.base_url == "http://alpha/v1"  # Alpha seeded first -> lowest id
    assert target.provider_id == alpha_id
    assert target.upstream_model == "dup-model"

    # Ambiguity + the chosen provider must be logged (R12).
    with sf() as s:
        logs = (
            s.query(LogEntry)
            .filter_by(source="backend.gateway.resolver")
            .all()
        )
    assert any("ambiguously" in (e.message or "") for e in logs)
    assert any("Alpha" in (e.message or "") for e in logs)


def test_bare_model_ambiguous_default_provider_honored(monkeypatch) -> None:
    """default_provider Setting overrides the lowest-id pick."""
    sf = _make_sf()
    _patch(monkeypatch, sf)
    with sf() as s:
        _add_provider(
            s, "Alpha", base_url="http://alpha/v1", model_ids=("dup-model",)
        )
        _add_provider(
            s, "Beta", base_url="http://beta/v1", model_ids=("dup-model",)
        )
        s.add(Setting(key="default_provider", value="Beta"))
        s.commit()
        beta_id = s.query(Provider).filter_by(name="Beta").first().id

    target = resolve_target("dup-model")
    assert target.base_url == "http://beta/v1"  # default_provider honored
    assert target.provider_id == beta_id


def test_bare_model_default_provider_without_model_falls_back(monkeypatch) -> None:
    """default_provider naming a provider that lacks the model -> lowest id."""
    sf = _make_sf()
    _patch(monkeypatch, sf)
    with sf() as s:
        _add_provider(
            s, "Alpha", base_url="http://alpha/v1", model_ids=("dup-model",)
        )
        _add_provider(
            s, "Beta", base_url="http://beta/v1", model_ids=("dup-model",)
        )
        # default points at a provider that does NOT carry dup-model.
        s.add(Setting(key="default_provider", value="Gamma"))
        s.commit()

    target = resolve_target("dup-model")
    assert target.base_url == "http://alpha/v1"  # falls back to lowest id


# --------------------------------------------------------------------------- #
# 3. No enabled provider advertises the bare model -> TargetNotFound.
# --------------------------------------------------------------------------- #
def test_bare_model_unknown_raises(monkeypatch) -> None:
    sf = _make_sf()
    _patch(monkeypatch, sf)
    with sf() as s:
        _add_provider(
            s, "B.AI", base_url="http://b.ai/v1", model_ids=("gpt-5.5",)
        )
        s.commit()

    with pytest.raises(TargetNotFound) as exc:
        resolve_target("nope")
    # Helpful message must suggest the provider: form.
    assert "provider:" in str(exc.value)


def test_bare_model_disabled_provider_ignored(monkeypatch) -> None:
    """A model only on a DISABLED provider must not resolve (enabled join)."""
    sf = _make_sf()
    _patch(monkeypatch, sf)
    with sf() as s:
        _add_provider(
            s,
            "Off",
            base_url="http://off/v1",
            enabled=False,
            model_ids=("off-model",),
        )
        s.commit()

    with pytest.raises(TargetNotFound):
        resolve_target("off-model")


# --------------------------------------------------------------------------- #
# 4. Existing provider:/combo: behavior unchanged (regression guard).
# --------------------------------------------------------------------------- #
def test_prefixed_paths_still_work(monkeypatch) -> None:
    sf = _make_sf()
    _patch(monkeypatch, sf)
    with sf() as s:
        _add_provider(
            s, "B.AI", base_url="http://b.ai/v1", model_ids=("gpt-5.5",)
        )
        s.add(Combo(name="whatever", strategy="fallback", enabled=True))
        s.commit()
    t = resolve_target("provider:B.AI:gpt-5.5")
    assert t.upstream_model == "gpt-5.5"
    assert t.base_url == "http://b.ai/v1"

    # provider:<name> (2-seg) resolves to first model.
    t2 = resolve_target("provider:B.AI")
    assert t2.upstream_model == "gpt-5.5"

    # combo: still returns a combo marker (combo_used=True, empty upstream).
    t3 = resolve_target("combo:whatever")
    assert t3.combo_used is True
    assert t3.upstream_model == ""

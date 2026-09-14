"""Per-member ``ComboMember.enabled`` switch tests (task 2026-09-13 §B).

Hermetic, no on-disk DB. Mirrors ``test_combos.py``: the combo path's
``SessionLocal`` bindings are rebound to a shared in-memory SQLite engine.

Covers:
* a disabled member is excluded from candidates for EVERY strategy
  (fallback, load_balance, latency_cost, three_tier, round_robin);
* new/existing members default ``enabled=True`` (model default + migration);
* ``PUT /api/combos/{id}/members/{mid}`` persists ``enabled`` and it shows in
  the DTO;
* the migration is idempotent (safe to run more than once).
"""

from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.combo_routing as combo_routing
import backend.combos_router as combos_router
import backend.config.db as db_mod
import backend.config.logs_router as logs_router
import backend.gateway.resolver as resolver
import backend.gateway.router as router
from backend.config.db import Base
from backend.models import Combo, ComboMember, Provider, ProviderModel
from fastapi.testclient import TestClient

from backend.server import app

STRATEGIES = ("fallback", "load_balance", "latency_cost", "three_tier", "round_robin")


def _make_sessionmaker() -> sessionmaker:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _seed_with_disabled_member(sf: sessionmaker, strategy: str = "fallback") -> dict:
    """Seed two providers + a 2-member combo where member B is disabled."""
    with sf() as session:
        p1 = Provider(
            name="p1", type="openai-compatible",
            base_url="http://p1.test/v1", api_key="sk-p1", enabled=True,
        )
        p2 = Provider(
            name="p2", type="openai-compatible",
            base_url="http://p2.test/v1", api_key="sk-p2", enabled=True,
        )
        session.add_all([p1, p2])
        session.flush()
        session.add_all(
            [
                ProviderModel(provider_id=p1.id, model_id="gpt-4o", model_name="GPT-4o"),
                ProviderModel(provider_id=p2.id, model_id="gpt-4o", model_name="GPT-4o"),
            ]
        )
        combo = Combo(name="c", strategy=strategy, enabled=True)
        session.add(combo)
        session.flush()
        m_enabled = ComboMember(
            combo_id=combo.id, provider_id=p1.id,
            provider_model="gpt-4o", priority=0, weight=1.0, enabled=True,
        )
        m_disabled = ComboMember(
            combo_id=combo.id, provider_id=p2.id,
            provider_model="gpt-4o", priority=1, weight=2.0, enabled=False,
        )
        session.add_all([m_enabled, m_disabled])
        session.commit()
        return {
            "combo_id": combo.id,
            "enabled_member_id": m_enabled.id,
            "disabled_member_id": m_disabled.id,
        }


def _patch_db(monkeypatch, sf: sessionmaker) -> None:
    monkeypatch.setattr(db_mod, "SessionLocal", sf)
    monkeypatch.setattr(resolver, "SessionLocal", sf)
    monkeypatch.setattr(router, "SessionLocal", sf)
    monkeypatch.setattr(combo_routing, "SessionLocal", sf)
    monkeypatch.setattr(combos_router, "SessionLocal", sf)
    monkeypatch.setattr(logs_router, "SessionLocal", sf)


# --- Disabled member excluded from candidates for every strategy --------------


def test_disabled_member_excluded_for_every_strategy(monkeypatch) -> None:
    for strategy in STRATEGIES:
        sf = _make_sessionmaker()
        ids = _seed_with_disabled_member(sf, strategy=strategy)
        _patch_db(monkeypatch, sf)
        with sf() as session:
            combo = session.get(Combo, ids["combo_id"])
            candidates = combo_routing.build_candidates(combo, session)
        # Only the enabled member survives; the disabled one is never a candidate.
        assert len(candidates) == 1
        assert candidates[0].upstream_model == "gpt-4o"
        # Confirm via the stored member that the skipped one is indeed disabled.
        with sf() as session:
            skipped = session.get(ComboMember, ids["disabled_member_id"])
            assert skipped.enabled is False


# --- round_robin selects from the enabled-only candidate set ------------------


def test_round_robin_skips_disabled_member(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed_with_disabled_member(sf, strategy="round_robin")
    _patch_db(monkeypatch, sf)
    with sf() as session:
        combo = session.get(Combo, ids["combo_id"])
        candidates = combo_routing.build_candidates(combo, session)
        assert len(candidates) == 1
        chosen = combo_routing.select_member("round_robin", candidates, session, combo)
        assert chosen.upstream_model == "gpt-4o"


# --- Default enabled=True (model default + create API) ------------------------


def test_member_defaults_enabled_true(monkeypatch) -> None:
    # Model default: a ComboMember created without `enabled` is True.
    sf = _make_sessionmaker()
    with sf() as session:
        p = Provider(
            name="p", type="openai-compatible",
            base_url="http://p.test/v1", api_key="sk", enabled=True,
        )
        session.add(p)
        session.flush()
        m = ComboMember(
            combo_id=1, provider_id=p.id, provider_model="gpt-4o",
            priority=0, weight=1.0,
        )
        session.add(m)
        session.commit()
        assert m.enabled is True

    # Create API: omitting `enabled` defaults to True in the DTO.
    seed = _seed_with_disabled_member(sf)
    client = TestClient(app)
    _patch_db(monkeypatch, sf)
    resp = client.post(
        "/api/combos",
        json={
            "name": "newc",
            "strategy": "fallback",
            "members": [{"provider_id": 1, "provider_model": "gpt-4o", "priority": 0}],
        },
    )
    assert resp.status_code == 201
    member = resp.json()["members"][0]
    assert member["enabled"] is True


# --- Update persists enabled and reflects in DTO ------------------------------


def test_update_member_enabled_persists(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed_with_disabled_member(sf)
    client = TestClient(app)
    _patch_db(monkeypatch, sf)

    mid = ids["enabled_member_id"]
    cid = ids["combo_id"]

    # Disable the enabled member.
    resp = client.put(
        f"/api/combos/{cid}/members/{mid}", json={"enabled": False}
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False

    # Re-enable it; omitting other fields must NOT clobber them.
    resp = client.put(
        f"/api/combos/{cid}/members/{mid}", json={"enabled": True}
    )
    body = resp.json()
    assert body["enabled"] is True
    assert body["provider_model"] == "gpt-4o"

    # Verify at the routing layer the re-enabled member is usable again
    # (member B was seeded disabled and stays disabled -> exactly 1 candidate).
    with sf() as session:
        combo = session.get(Combo, cid)
        candidates = combo_routing.build_candidates(combo, session)
        assert len(candidates) == 1
        assert candidates[0].upstream_model == "gpt-4o"


# --- Migration idempotency ---------------------------------------------------


def test_migration_adds_column_and_is_idempotent() -> None:
    # Simulate a pre-existing DB whose combo_members table lacks `enabled`.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    with engine.connect() as conn:
        conn.execute(
            text(
                "CREATE TABLE combo_members ("
                "id INTEGER PRIMARY KEY, combo_id INTEGER, provider_id INTEGER, "
                "provider_model VARCHAR, priority INTEGER, weight FLOAT)"
            )
        )
        # Pre-existing row: should default to enabled=True after the ALTER.
        conn.execute(
            text(
                "INSERT INTO combo_members "
                "(id, combo_id, provider_id, provider_model, priority, weight) "
                "VALUES (1, 1, 1, 'gpt-4o', 0, 1.0)"
            )
        )
        conn.commit()

    # Run 1: adds the column.
    db_mod._ensure_combo_member_enabled_column(engine)
    with engine.connect() as conn:
        cols = {
            r[1]
            for r in conn.execute(text("PRAGMA table_info(combo_members)")).fetchall()
        }
        assert "enabled" in cols
        row = conn.execute(text("SELECT enabled FROM combo_members WHERE id=1")).fetchone()
        assert row[0] == 1  # default True applied to the pre-existing row

    # Run 2: must be a no-op (PRAGMA guard prevents a duplicate-column error).
    db_mod._ensure_combo_member_enabled_column(engine)
    with engine.connect() as conn:
        cols = {
            r[1]
            for r in conn.execute(text("PRAGMA table_info(combo_members)")).fetchall()
        }
        assert "enabled" in cols


def test_migration_safe_when_table_missing() -> None:
    # An engine with no combo_members table must not raise; the OperationalError
    # is swallowed (R12 — no bare except).
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    db_mod._ensure_combo_member_enabled_column(engine)

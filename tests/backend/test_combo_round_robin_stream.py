"""Streaming-path ``round_robin`` rotation (bug fix 2026-09-13).

Regression test for the bug where ``resolve_combo_stream_target`` ignored the
``round_robin`` cursor and always returned the FIRST OpenAI-format member, so the
UI (which chats over SSE streaming) never rotated past member 0.

Hermetic, no on-disk DB (mirrors ``test_combo_round_robin.py``). The streaming
resolver is now exercised directly (no network needed — it only selects, it does
not call upstreams), with ``SessionLocal`` rebound to a shared in-memory engine so
the ``combo.last_used_index`` cursor persists between calls.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.combo_routing as combo_routing
import backend.config.db as db_mod
import backend.config.logs_router as logs_router
import backend.gateway.resolver as resolver
import backend.gateway.router as router
from backend.config.db import Base
from backend.models import Combo, ComboMember, Provider, ProviderModel

CANNED_MODEL = "gpt-4o"


def _make_sessionmaker() -> sessionmaker:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _patch_db(monkeypatch, sf: sessionmaker) -> None:
    monkeypatch.setattr(db_mod, "SessionLocal", sf)
    monkeypatch.setattr(resolver, "SessionLocal", sf)
    monkeypatch.setattr(router, "SessionLocal", sf)
    monkeypatch.setattr(combo_routing, "SessionLocal", sf)
    monkeypatch.setattr(logs_router, "SessionLocal", sf)


def _seed_two_openai_members(sf: sessionmaker, strategy: str, name: str = "rr") -> dict:
    """Seed a combo (``strategy``) with 2 ENABLED OpenAI-format members.

    Members get ``priority`` 0 and 1 (-> provider p0, then p1). Provider type is
    ``openai-compatible`` so ``build_candidates`` reports ``format == 'openai'``.
    Returns provider id / model maps + combo id.
    """
    out: dict = {}
    with sf() as session:
        prov_ids = []
        for i in range(2):
            p = Provider(
                name=f"{name}-p{i}",
                type="openai-compatible",
                base_url=f"http://{name}-p{i}.test/v1",
                api_key=f"sk-{name}-{i}",
                enabled=True,
            )
            session.add(p)
            session.flush()
            session.add(
                ProviderModel(
                    provider_id=p.id, model_id=CANNED_MODEL, model_name="GPT-4o"
                )
            )
            prov_ids.append(p.id)
            out[f"p{i}_id"] = p.id
        combo = Combo(
            name=name, strategy=strategy, enabled=True, last_used_index=0
        )
        session.add(combo)
        session.flush()
        for i in range(2):
            session.add(
                ComboMember(
                    combo_id=combo.id,
                    provider_id=prov_ids[i],
                    provider_model=CANNED_MODEL,
                    priority=i,
                    enabled=True,
                    weight=1.0,
                )
            )
        session.commit()
        out["combo_id"] = combo.id
    return out


def _cursor(sf: sessionmaker, combo_id: int) -> int:
    with sf() as session:
        return session.get(Combo, combo_id).last_used_index


# --- Streaming round_robin rotates across OpenAI members --------------------- #


def test_stream_round_robin_rotates_and_advances_cursor(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed_two_openai_members(sf, "round_robin", name="rr")
    _patch_db(monkeypatch, sf)

    # Call 1: cursor 0 -> member p0, advances to 1.
    t1 = combo_routing.resolve_combo_stream_target("rr")
    assert t1 is not None
    assert t1.upstream_model == CANNED_MODEL
    assert t1.provider_id == ids["p0_id"]
    assert _cursor(sf, ids["combo_id"]) == 1

    # Call 2: cursor 1 -> member p1, advances (wraps) to 0.
    t2 = combo_routing.resolve_combo_stream_target("rr")
    assert t2 is not None
    assert t2.upstream_model == CANNED_MODEL
    assert t2.provider_id == ids["p1_id"]
    assert _cursor(sf, ids["combo_id"]) == 0

    # Rotation works: the two consecutive calls picked DIFFERENT members.
    assert t1.provider_id != t2.provider_id

    # Call 3 wraps back to p0 (cursor 0 -> 1).
    t3 = combo_routing.resolve_combo_stream_target("rr")
    assert t3 is not None
    assert t3.provider_id == ids["p0_id"]
    assert _cursor(sf, ids["combo_id"]) == 1


def test_stream_round_robin_by_id_rotates(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed_two_openai_members(sf, "round_robin", name="rr")
    _patch_db(monkeypatch, sf)

    combo_id = ids["combo_id"]
    t1 = combo_routing.resolve_combo_stream_target(combo_id)
    t2 = combo_routing.resolve_combo_stream_target(combo_id)
    assert t1.provider_id != t2.provider_id


# --- fallback / three_tier streaming returns first OpenAI member ------------- #


def test_stream_fallback_returns_first_openai_member(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed_two_openai_members(sf, "fallback", name="fb")
    _patch_db(monkeypatch, sf)

    t = combo_routing.resolve_combo_stream_target("fb")
    assert t is not None
    assert t.provider_id == ids["p0_id"]  # no rotation -> priority 0 member
    # fallback must NOT touch the cursor.
    assert _cursor(sf, ids["combo_id"]) == 0


def test_stream_three_tier_returns_first_openai_member(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed_two_openai_members(sf, "three_tier", name="tt")
    _patch_db(monkeypatch, sf)

    t = combo_routing.resolve_combo_stream_target("tt")
    assert t is not None
    assert t.provider_id == ids["p0_id"]
    assert _cursor(sf, ids["combo_id"]) == 0

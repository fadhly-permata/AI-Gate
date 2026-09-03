"""Regression tests for config-in-DB settings (Error 2) and startup CLI tool
seeding (Error 1).

Both bugs were runtime errors in the server logs:

* Error 1 — ``backend.server.lifespan`` did ``with SessionLocal() as seed_session:``
  but never imported ``SessionLocal`` -> ``NameError``. Fixed by importing it.
* Error 2 — ``backend.config.settings.get`` opened its session via a fixed
  ``SessionLocal`` binding, which could point at a non-Session object. Fixed by
  resolving ``SessionLocal`` dynamically from ``backend.config.db`` so a real
  session is always obtained.

Hermetic: every test rebinds ``backend.config.db.SessionLocal`` to an in-memory
SQLite engine, so no on-disk ``~/.aigate/aigate.db`` is touched.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.config.db as db_mod
import backend.cli_presets
import backend.server
from backend.config.db import Base
from backend.models import CLITool, CLIToolGroup
from fastapi.testclient import TestClient


def _memory_session_factory(monkeypatch) -> sessionmaker:
    """Rebind ``SessionLocal`` (everywhere it matters) to one in-memory engine."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    sf: sessionmaker = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, future=True
    )
    # settings.py now reads SessionLocal dynamically from backend.config.db.
    monkeypatch.setattr(db_mod, "SessionLocal", sf)
    # server.py imports SessionLocal directly; rebind so lifespan stays hermetic.
    monkeypatch.setattr(backend.server, "SessionLocal", sf)
    return sf


# =========================================================================== #
# Error 2: settings.get / set / ensure_seeded / list_all
# =========================================================================== #
def test_get_returns_default_after_seed(monkeypatch) -> None:
    from backend.config.settings import (
        ensure_seeded,
        get,
        list_all,
        set as set_setting,
    )

    _memory_session_factory(monkeypatch)
    ensure_seeded()

    assert get("port") == "8080"
    assert get("theme") == "light"
    assert get("missing_key", default="fallback") == "fallback"

    set_setting("port", "9090")
    assert get("port") == "9090"
    assert list_all()["port"] == "9090"


def test_get_with_provided_session(monkeypatch) -> None:
    sf = _memory_session_factory(monkeypatch)
    from backend.config.settings import ensure_seeded, get

    with sf() as s:
        ensure_seeded(session=s)
        assert get("port", session=s) == "8080"


def test_ensure_seeded_is_idempotent(monkeypatch) -> None:
    sf = _memory_session_factory(monkeypatch)
    from backend.config.settings import ensure_seeded, get

    ensure_seeded()
    ensure_seeded()  # second call must not duplicate or error
    assert get("port") == "8080"


# =========================================================================== #
# Seeding: CLI preset groups (Error 1 downstream goal)
# =========================================================================== #
def test_seed_cli_tools_inserts_all_groups(monkeypatch) -> None:
    sf = _memory_session_factory(monkeypatch)

    with sf() as s:
        inserted = backend.cli_presets.seed_cli_tools(s)
        assert inserted == 3
        assert s.query(CLIToolGroup).count() == 3  # A / B / C
        assert s.query(CLITool).count() == 24  # 12 + 6 + 6


def test_seed_cli_tools_is_idempotent(monkeypatch) -> None:
    sf = _memory_session_factory(monkeypatch)

    with sf() as s:
        assert backend.cli_presets.seed_cli_tools(s) == 3
        # Re-seeding a non-empty table must be a no-op (returns 0).
        assert backend.cli_presets.seed_cli_tools(s) == 0


# =========================================================================== #
# Error 1: server lifespan imports SessionLocal and seeds without NameError
# =========================================================================== #
def test_lifespan_seeds_cli_tools(monkeypatch) -> None:
    sf = _memory_session_factory(monkeypatch)

    # Entering the TestClient context triggers the app lifespan (startup).
    client = TestClient(backend.server.app)
    with client:
        pass

    # Lifespan must have seeded the preset groups into the DB it used.
    with sf() as s:
        assert s.query(CLIToolGroup).count() == 3


def test_server_imports_sessionlocal() -> None:
    """Regression guard: ``SessionLocal`` must be a name in ``backend.server``
    so the lifespan no longer raises ``NameError``."""
    assert hasattr(backend.server, "SessionLocal")

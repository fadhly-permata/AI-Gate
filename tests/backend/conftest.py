"""Shared pytest fixtures for aigate backend tests.

Exposes:
- ``client``: a FastAPI ``TestClient`` bound to ``backend.server.app``.
- ``db_session``: an isolated in-memory SQLite session for model tests.

## DB isolation (why this file sets an env var at module top)

Running the suite must NEVER write to the user's live ``~/.aigate/aigate.db``.
Two code paths reach the DB:

1. ``backend.log`` writes ``LogEntry`` rows via ``_db.SessionLocal()`` — a
   module-attribute lookup on ``backend.config.db``.
2. The routers do ``from backend.config.db import SessionLocal`` — a direct
   binding captured at *their* import time.

Both names resolve to the SAME sessionmaker object that ``backend.config.db``
creates at import, bound to whatever ``DB_PATH`` was when that module was first
imported. So the single lever that redirects BOTH paths is to set
``AIGATE_DB_PATH`` *before* ``backend.config.db`` is ever imported.

pytest imports this conftest before collecting any test module, and none of the
imports below touch ``backend`` (the app is imported lazily inside the
fixtures). Setting the env var here therefore runs before the first
``import backend.config.db`` anywhere in the suite, so the module-level engine
and ``SessionLocal`` bind to a throwaway temp file for the whole session.

Tests that build their own in-memory engine and ``monkeypatch`` the
``SessionLocal`` bindings (test_providers, test_accounts, ...) still work: their
patch simply overrides the temp-bound factory for the duration of the test.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# --- DB isolation: MUST precede any ``backend.*`` import --------------------- #
# A unique temp file per session; ``backend.config.db`` binds its engine +
# SessionLocal to it on first import (see module docstring).
_TMP_DIR = tempfile.mkdtemp(prefix="aigate-test-isolation-")
os.environ["AIGATE_DB_PATH"] = os.path.join(_TMP_DIR, "aigate.db")


@pytest.fixture(scope="session", autouse=True)
def _bootstrap_temp_db() -> Iterator[None]:
    """Create the schema in the temp DB once for the whole session.

    ``backend.config.db`` has already bound its engine + ``SessionLocal`` to the
    temp file (env set at module top). ``init_db()`` runs ``create_all`` plus the
    idempotent self-heal migrations so client-based tests — which do NOT build
    their own in-memory engine — have tables to write to.

    We deliberately do NOT call ``ensure_seeded`` here: the suite is hermetic and
    the only tests that assume seeded default Settings seed them themselves
    (``test_settings_api.py`` rebinds to its own in-memory DB and calls
    ``ensure_seeded``). Keeping the shared temp DB unseeded avoids leaking
    defaults into tests that count rows.

    Teardown disposes the engine and removes the temp dir (R8 — no junk left).
    """
    from backend.config import db as db_mod

    db_mod.init_db()
    try:
        yield
    finally:
        engine = db_mod._engine
        if engine is not None:
            engine.dispose()
        shutil.rmtree(_TMP_DIR, ignore_errors=True)


@pytest.fixture
def client() -> TestClient:
    """Return a TestClient for the aigate FastAPI app.

    Imported inside the fixture so the app module (and its heavy imports)
    only load when a test actually needs it. Deliberately NOT used as a
    context manager — this avoids triggering the startup lifespan, which
    would bootstrap the on-disk DB. The DB is already redirected to the
    session temp file (see module top), so any router/logger write made
    through this client lands there, never in ``~/.aigate/aigate.db``.
    """
    from backend.server import app

    return TestClient(app)


@pytest.fixture
def db_session() -> Iterator[Session]:
    """Yield a Session over a fresh in-memory SQLite database.

    Importing ``backend.models`` registers every ORM mapper onto
    ``Base.metadata`` before ``create_all`` runs. The schema is dropped on
    teardown so no state leaks between tests.
    """
    from backend import models  # noqa: F401  (register mappers on Base.metadata)
    from backend.config.db import Base

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory: sessionmaker = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, future=True
    )
    with session_factory() as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()

"""Shared pytest fixtures for aigate backend tests.

Exposes:
- ``client``: a FastAPI ``TestClient`` bound to ``backend.server.app``.
- ``db_session``: an isolated in-memory SQLite session for model tests.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture
def client() -> TestClient:
    """Return a TestClient for the aigate FastAPI app.

    Imported inside the fixture so the app module (and its heavy imports)
    only load when a test actually needs it. Deliberately NOT used as a
    context manager — this avoids triggering the startup lifespan, which
    would bootstrap the on-disk ``~/.aigate/aigate.db`` and break hermeticity.
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

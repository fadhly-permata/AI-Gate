"""aigate config engine — SQLAlchemy engine, session, schema bootstrap.

ADR-004: SQLAlchemy 2.x declarative ORM + single SQLite file at
``~/.aigate/aigate.db``. All access goes through a repository/session layer.
ADR-007: secrets (api_key, internal_api_key, password) are stored in
plaintext — no encryption, matching ERD.md.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    """Declarative base for all aigate ORM models (SQLAlchemy 2.x)."""


DB_PATH: Path = Path.home() / ".aigate" / "aigate.db"

_engine = None


def get_engine():
    """Return a cached SQLAlchemy engine for the aigate SQLite database.

    Lazily creates the ``~/.aigate`` parent directory if missing.
    """
    global _engine
    if _engine is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            f"sqlite:///{DB_PATH}",
            future=True,
            connect_args={"check_same_thread": False},
        )
    return _engine


# Bound to the file engine at import time (the app always talks to the
# on-disk SQLite database). Tests build their own in-memory engine instead.
SessionLocal: sessionmaker = sessionmaker(
    bind=get_engine(),
    autoflush=False,
    autocommit=False,
    future=True,
)


def init_db() -> None:
    """Create all tables declared on ``Base.metadata`` (idempotent).

    Importing ``backend.models`` registers every mapped entity onto
    ``Base.metadata`` before ``create_all`` runs.
    """
    from backend import models  # noqa: F401  (side-effect: register mappers)
    from backend.config.db import Base

    Base.metadata.create_all(get_engine())

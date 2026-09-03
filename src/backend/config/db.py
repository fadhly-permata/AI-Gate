"""aigate config engine — SQLAlchemy engine, session, schema bootstrap.

ADR-004: SQLAlchemy 2.x declarative ORM + single SQLite file at
``~/.aigate/aigate.db``. All access goes through a repository/session layer.
ADR-007: secrets (api_key, internal_api_key, password) are stored in
plaintext — no encryption, matching ERD.md.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

logger = logging.getLogger(__name__)


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


def _ensure_provider_default_model_column(engine) -> None:
    """Self-heal ``providers.default_model`` on pre-existing DBs.

    ``create_all`` never alters existing tables, so a DB created before the
    column existed (e.g. ``~/.aigate/aigate.db``) lacks it and every
    ``/api/providers`` call 500s. Idempotent: a PRAGMA check guards the ALTER,
    and only the specific ``OperationalError`` is swallowed (R12 — no bare
    ``except``).
    """
    try:
        with engine.connect() as conn:
            existing = {
                row[1] for row in conn.execute(text("PRAGMA table_info(providers)")).fetchall()
            }
            if "default_model" not in existing:
                conn.execute(
                    text("ALTER TABLE providers ADD COLUMN default_model TEXT")
                )
                conn.commit()
    except OperationalError as exc:  # e.g. table missing on a bare/empty engine
        logger.warning("skipping provider.default_model migration: %s", exc)


def _ensure_endpoint_token_saver_column(engine) -> None:
    """Self-heal ``endpoints.token_saver`` on pre-existing DBs (B5.4 / ADR-013).

    ``create_all`` never alters existing tables, so a DB created before the
    column existed lacks it. Idempotent: a PRAGMA check guards the ALTER, and
    only the specific ``OperationalError`` is swallowed (R12 — no bare
    ``except``).
    """
    try:
        with engine.connect() as conn:
            existing = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(endpoints)")).fetchall()
            }
            if "token_saver" not in existing:
                conn.execute(
                    text(
                        "ALTER TABLE endpoints ADD COLUMN token_saver TEXT "
                        "NOT NULL DEFAULT 'off'"
                    )
                )
                conn.commit()
    except OperationalError as exc:  # e.g. table missing on a bare/empty engine
        logger.warning("skipping endpoint.token_saver migration: %s", exc)


def _ensure_provider_tier_column(engine) -> None:
    """Self-heal ``providers.tier`` on pre-existing DBs (B5.2).

    ``create_all`` never alters existing tables, so a DB created before the
    column existed lacks it. Idempotent: a PRAGMA check guards the ALTER, and
    only the specific ``OperationalError`` is swallowed (R12 — no bare
    ``except``).
    """
    try:
        with engine.connect() as conn:
            existing = {
                row[1] for row in conn.execute(text("PRAGMA table_info(providers)")).fetchall()
            }
            if "tier" not in existing:
                conn.execute(text("ALTER TABLE providers ADD COLUMN tier TEXT"))
                conn.commit()
    except OperationalError as exc:  # e.g. table missing on a bare/empty engine
        logger.warning("skipping provider.tier migration: %s", exc)


def _ensure_provider_quota_columns(engine) -> None:
    """Self-heal ``providers.quota_limit``/``quota_window`` on old DBs (B5.5).

    ``create_all`` never alters existing tables, so a DB created before the
    quota columns existed lacks them and every ``/api/quota`` call 500s.
    Idempotent: a PRAGMA check guards each ALTER, and only the specific
    ``OperationalError`` is swallowed (R12 — no bare ``except``).
    """
    try:
        with engine.connect() as conn:
            existing = {
                row[1] for row in conn.execute(text("PRAGMA table_info(providers)")).fetchall()
            }
            if "quota_limit" not in existing:
                conn.execute(
                    text("ALTER TABLE providers ADD COLUMN quota_limit INTEGER")
                )
                conn.commit()
            if "quota_window" not in existing:
                conn.execute(
                    text("ALTER TABLE providers ADD COLUMN quota_window TEXT")
                )
                conn.commit()
    except OperationalError as exc:  # e.g. table missing on a bare/empty engine
        logger.warning("skipping provider quota columns migration: %s", exc)


def init_db() -> None:
    """Create all tables declared on ``Base.metadata`` (idempotent).

    Importing ``backend.models`` registers every mapped entity onto
    ``Base.metadata`` before ``create_all`` runs. After bootstrap, self-heal
    any columns added to existing tables after their first creation.
    """
    from backend import models  # noqa: F401  (side-effect: register mappers)
    from backend.config.db import Base

    engine = get_engine()
    Base.metadata.create_all(engine)
    _ensure_provider_default_model_column(engine)
    _ensure_provider_tier_column(engine)
    _ensure_provider_quota_columns(engine)
    _ensure_endpoint_token_saver_column(engine)

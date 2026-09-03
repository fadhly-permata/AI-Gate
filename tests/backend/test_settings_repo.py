"""Tests for the config-in-DB repository ``backend.config.settings``.

Hermetic: builds its own in-memory SQLite engine (no on-disk DB, R12-safe),
using the same pattern as ``tests/backend/conftest.py::db_session``.
"""

from __future__ import annotations

import logging

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models  # noqa: F401  (register mappers on Base.metadata)
from backend.config.db import Base
from backend.config import settings as settings_repo
from backend.config.settings import DEFAULT_SETTINGS


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def session(engine):
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    with factory() as s:
        yield s


def test_ensure_seeded_creates_defaults(session):
    assert settings_repo.list_all(session) == {}
    settings_repo.ensure_seeded(session)
    stored = settings_repo.list_all(session)
    assert stored == DEFAULT_SETTINGS


def test_ensure_seeded_is_idempotent(session):
    settings_repo.ensure_seeded(session)
    settings_repo.ensure_seeded(session)
    # still exactly the default keys, no duplicates
    assert settings_repo.list_all(session) == DEFAULT_SETTINGS
    from sqlalchemy import select, func

    count = session.execute(
        select(func.count()).select_from(models.Setting)
    ).scalar_one()
    assert count == len(DEFAULT_SETTINGS)


def test_get_returns_default_when_missing(session):
    assert settings_repo.get("port", default="9999", session=session) == "9999"


def test_get_set_roundtrip(session):
    settings_repo.set("theme", "dark", session=session)
    assert settings_repo.get("theme", session=session) == "dark"


def test_set_updates_existing_value(session):
    settings_repo.ensure_seeded(session)
    assert settings_repo.get("theme", session=session) == "light"
    settings_repo.set("theme", "dark", session=session)
    assert settings_repo.get("theme", session=session) == "dark"
    # ensure_seeded must NOT clobber the user's change
    settings_repo.ensure_seeded(session)
    assert settings_repo.get("theme", session=session) == "dark"


def test_list_all_reflects_writes(session):
    settings_repo.ensure_seeded(session)
    settings_repo.set("custom_key", "custom_val", session=session)
    all_settings = settings_repo.list_all(session)
    assert all_settings["custom_key"] == "custom_val"
    assert all_settings["locale"] == "en"


def test_no_empty_except_and_logging(caplog):
    """A missing session path still logs on error instead of swallowing it."""
    # Force a failure by pointing at a closed session-like object via bad engine.
    bad_session = object()  # not a real session -> triggers exception
    with caplog.at_level(logging.ERROR, logger=settings_repo.logger.name):
        with pytest.raises(Exception):
            settings_repo.get("port", session=bad_session)
    assert any("config.settings.get failed" in r.message for r in caplog.records)

"""Tests for the aigate ORM models and config engine.

Run against an in-memory SQLite database (no on-disk side effects).
"""

from __future__ import annotations

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from backend.config.db import Base
from backend.models import Endpoint, Provider


def _make_engine():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return engine


def test_provider_roundtrip() -> None:
    engine = _make_engine()
    with Session(engine) as session:
        session.add(
            Provider(
                name="test",
                type="openai-compatible",
                base_url="http://x",
                api_key="sk-plain",
                enabled=True,
            )
        )
        session.commit()
        got = session.query(Provider).filter_by(name="test").one()
        assert got.name == "test"
        assert got.api_key == "sk-plain"


def test_endpoint_internal_api_key_plain() -> None:
    engine = _make_engine()
    columns = [c["name"] for c in inspect(engine).get_columns("endpoints")]
    assert "internal_api_key" in columns

    with Session(engine) as session:
        session.add(Endpoint(name="local", internal_api_key="plain-key"))
        session.commit()
        got = session.query(Endpoint).filter_by(name="local").one()
        assert got.internal_api_key == "plain-key"

"""Self-healing DB migration tests (R12-safe, idempotent).

Covers ``_ensure_provider_default_model_column``: it must add the
``providers.default_model`` column to a pre-existing table that lacks it, and
must be safe to run twice (no error / no duplicate column).
"""

from __future__ import annotations

from sqlalchemy import create_engine, text


def _column_names(engine, table: str) -> set[str]:
    with engine.connect() as conn:
        return {
            row[1]
            for row in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        }


def _build_providers_without_default_model(engine) -> None:
    """Create a ``providers`` table that mimics an old pre-column DB."""
    with engine.connect() as conn:
        conn.execute(
            text(
                "CREATE TABLE providers ("
                "id INTEGER PRIMARY KEY, "
                "name TEXT, "
                "type TEXT, "
                "base_url TEXT, "
                "api_key TEXT, "
                "enabled BOOLEAN, "
                "custom_headers TEXT, "
                "created_at DATETIME)"
            )
        )
        conn.commit()


def test_ensure_provider_default_model_adds_column():
    from backend.config.db import _ensure_provider_default_model_column

    engine = create_engine("sqlite:///:memory:", future=True)
    _build_providers_without_default_model(engine)

    assert "default_model" not in _column_names(engine, "providers")

    _ensure_provider_default_model_column(engine)

    assert "default_model" in _column_names(engine, "providers")
    engine.dispose()


def test_ensure_provider_default_model_is_idempotent():
    from backend.config.db import _ensure_provider_default_model_column

    engine = create_engine("sqlite:///:memory:", future=True)
    _build_providers_without_default_model(engine)

    # Running twice must not raise (no duplicate-column OperationalError).
    _ensure_provider_default_model_column(engine)
    _ensure_provider_default_model_column(engine)

    cols = _column_names(engine, "providers")
    assert "default_model" in cols
    engine.dispose()


def test_ensure_provider_default_model_noop_when_present():
    from backend import models  # noqa: F401  (register mappers)
    from backend.config.db import (
        Base,
        _ensure_provider_default_model_column,
    )

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    # Model already declares the column — migration must be a no-op.
    assert "default_model" in _column_names(engine, "providers")
    _ensure_provider_default_model_column(engine)
    assert "default_model" in _column_names(engine, "providers")
    engine.dispose()

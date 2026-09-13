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


# --- log_entries.resolved (T1) ---------------------------------------------- #


def _build_log_entries_without_resolved(engine) -> None:
    """Create a ``log_entries`` table that mimics a pre-T1 (column-less) DB."""
    with engine.connect() as conn:
        conn.execute(
            text(
                "CREATE TABLE log_entries ("
                "id INTEGER PRIMARY KEY, "
                "timestamp DATETIME, "
                "severity VARCHAR, "
                "source VARCHAR, "
                "message VARCHAR, "
                "stacktrace TEXT)"
            )
        )
        conn.commit()


def _insert_log_rows(engine, rows: list[tuple]) -> None:
    with engine.connect() as conn:
        for ts, severity, message in rows:
            conn.execute(
                text(
                    "INSERT INTO log_entries (timestamp, severity, source, "
                    "message, stacktrace) VALUES (:ts, :sev, 'test', :msg, NULL)"
                ),
                {"ts": ts, "sev": severity, "msg": message},
            )
        conn.commit()


def test_ensure_log_entry_resolved_adds_column_keeps_rows_falsy():
    """The live-DB scenario (~9700 rows): ALTER adds the column additively,
    existing rows survive, and old rows read back with ``resolved`` falsy."""
    from sqlalchemy.orm import sessionmaker

    from backend.config.db import _ensure_log_entry_resolved_column
    from backend.models import LogEntry

    engine = create_engine("sqlite:///:memory:", future=True)
    _build_log_entries_without_resolved(engine)
    _insert_log_rows(
        engine,
        [
            ("2026-01-01 00:00:00.000000", "warning", "old one"),
            ("2026-02-01 00:00:00.000000", "error", "other one"),
        ],
    )

    assert "resolved" not in _column_names(engine, "log_entries")

    _ensure_log_entry_resolved_column(engine)

    assert "resolved" in _column_names(engine, "log_entries")

    # Rows intact + read back through the ORM with resolved falsy.
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    with factory() as s:
        rows = s.query(LogEntry).order_by(LogEntry.id).all()
        assert [r.message for r in rows] == ["old one", "other one"]
        assert all(not r.resolved for r in rows)
    factory.close_all()
    engine.dispose()


def test_ensure_log_entry_resolved_is_idempotent():
    from backend.config.db import _ensure_log_entry_resolved_column

    engine = create_engine("sqlite:///:memory:", future=True)
    _build_log_entries_without_resolved(engine)

    # Running twice must not raise (no duplicate-column OperationalError).
    _ensure_log_entry_resolved_column(engine)
    _ensure_log_entry_resolved_column(engine)

    assert "resolved" in _column_names(engine, "log_entries")
    engine.dispose()


def test_ensure_log_entry_resolved_noop_when_present():
    from backend import models  # noqa: F401  (register mappers)
    from backend.config.db import Base, _ensure_log_entry_resolved_column

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    # Model already declares the column — migration must be a no-op.
    assert "resolved" in _column_names(engine, "log_entries")
    _ensure_log_entry_resolved_column(engine)
    assert "resolved" in _column_names(engine, "log_entries")
    engine.dispose()


# --- combos.last_used_index (Combo round_robin cursor, task 2026-09-13) ------- #


def _build_combos_without_last_used_index(engine) -> None:
    """Create a ``combos`` table that mimics a pre-column DB."""
    with engine.connect() as conn:
        conn.execute(
            text(
                "CREATE TABLE combos ("
                "id INTEGER PRIMARY KEY, "
                "name TEXT, "
                "strategy TEXT, "
                "enabled BOOLEAN)"
            )
        )
        conn.commit()


def test_ensure_combo_last_used_index_adds_column():
    from backend.config.db import _ensure_combo_last_used_index_column

    engine = create_engine("sqlite:///:memory:", future=True)
    _build_combos_without_last_used_index(engine)

    assert "last_used_index" not in _column_names(engine, "combos")

    _ensure_combo_last_used_index_column(engine)

    assert "last_used_index" in _column_names(engine, "combos")
    engine.dispose()


def test_ensure_combo_last_used_index_is_idempotent():
    from backend.config.db import _ensure_combo_last_used_index_column

    engine = create_engine("sqlite:///:memory:", future=True)
    _build_combos_without_last_used_index(engine)

    # Running twice must not raise (no duplicate-column OperationalError).
    _ensure_combo_last_used_index_column(engine)
    _ensure_combo_last_used_index_column(engine)

    assert "last_used_index" in _column_names(engine, "combos")
    engine.dispose()


def test_ensure_combo_last_used_index_noop_when_present():
    from backend import models  # noqa: F401  (register mappers)
    from backend.config.db import Base, _ensure_combo_last_used_index_column

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    # Model already declares the column — migration must be a no-op.
    assert "last_used_index" in _column_names(engine, "combos")
    _ensure_combo_last_used_index_column(engine)
    assert "last_used_index" in _column_names(engine, "combos")
    engine.dispose()

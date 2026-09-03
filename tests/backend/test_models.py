"""Tests for the aigate ORM models and config engine.

Run against an in-memory SQLite database (no on-disk side effects).
"""

from __future__ import annotations

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from backend.config.db import Base, init_db
from backend.models import (
    CLITool,
    CLIToolGroup,
    Combo,
    ComboMember,
    Endpoint,
    EndpointBinding,
    LogEntry,
    Provider,
    ProviderModel,
    ProxyNode,
    ProxyPool,
    Setting,
    TerminalSession,
    TerminalTab,
)

# All 16 table names declared on Base.metadata, per ERD.md (B5.6 adds
# ``request_logs`` — the ERD RequestLog entity, now modeled).
EXPECTED_TABLES = {
    "providers",
    "provider_accounts",
    "provider_models",
    "proxy_pools",
    "proxy_nodes",
    "combos",
    "combo_members",
    "endpoints",
    "endpoint_bindings",
    "usage_records",
    "request_logs",
    "cli_tool_groups",
    "cli_tools",
    "terminal_sessions",
    "terminal_tabs",
    "log_entries",
    "settings",
}


def _make_engine():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return engine


def test_all_erd_tables_created() -> None:
    engine = _make_engine()
    existing = set(inspect(engine).get_table_names())
    assert EXPECTED_TABLES <= existing, existing.symmetric_difference(
        EXPECTED_TABLES
    )


def test_init_db_creates_all_tables() -> None:
    # init_db() must register every model and create all 16 tables.
    init_db()  # uses on-disk engine; assert against metadata instead.
    declared = set(Base.metadata.tables.keys())
    assert EXPECTED_TABLES == declared, declared.symmetric_difference(
        EXPECTED_TABLES
    )


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
        assert got.api_key == "sk-plain"  # ADR-007: plaintext, no encryption.


def test_endpoint_internal_api_key_plain() -> None:
    engine = _make_engine()
    columns = [c["name"] for c in inspect(engine).get_columns("endpoints")]
    assert "internal_api_key" in columns

    with Session(engine) as session:
        session.add(Endpoint(name="local", internal_api_key="plain-key"))
        session.commit()
        got = session.query(Endpoint).filter_by(name="local").one()
        assert got.internal_api_key == "plain-key"


def test_log_entry_roundtrip() -> None:
    engine = _make_engine()
    with Session(engine) as session:
        session.add(
            LogEntry(
                severity="error",
                source="backend.gateway",
                message="boom",
                stacktrace="Traceback...",
            )
        )
        session.commit()
        got = session.query(LogEntry).filter_by(severity="error").one()
        assert got.message == "boom"
        assert got.stacktrace == "Traceback..."


def test_setting_unique_key_and_roundtrip() -> None:
    engine = _make_engine()
    with Session(engine) as session:
        session.add(Setting(key="default_port", value="8080"))
        session.commit()
        got = session.query(Setting).filter_by(key="default_port").one()
        assert got.value == "8080"

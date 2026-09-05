"""Tests for the mandatory DB logging helper (B1.2 / ADR-011 / R12).

Hermetic: every test builds its own in-memory SQLite engine and rebinds
``backend.config.db.SessionLocal`` so the logger writes there instead of the
on-disk ``~/.aigate/aigate.db``. No file is touched.
"""

from __future__ import annotations

import ast
import pathlib

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.config.db as db_mod
from backend import models  # noqa: F401  (register mappers on Base.metadata)
from backend.config.db import Base
from backend.log import (
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    log_error,
    log_event,
    log_exception,
    log_info,
    log_warning,
)


@pytest.fixture
def log_session():
    """Provide an isolated in-memory engine bound to ``SessionLocal``.

    Rebinds the module-level ``SessionLocal`` (referenced by ``backend.log`` via
    the ``backend.config.db`` module object) so log writes land in-memory.
    """
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    original = db_mod.SessionLocal
    db_mod.SessionLocal = factory
    try:
        with factory() as session:
            yield session
    finally:
        db_mod.SessionLocal = original
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_log_error_persists_to_db(log_session) -> None:
    """log_error writes a LogEntry with ERROR severity and the message."""
    entry = log_error("boom", source="test")

    rows = log_session.query(models.LogEntry).all()
    assert len(rows) == 1
    assert rows[0].severity == SEVERITY_ERROR
    assert rows[0].message == "boom"
    assert rows[0].source == "test"
    # stacktrace is nullable and omitted here.
    assert rows[0].stacktrace is None
    # returned object is the same persisted row.
    assert entry.id == rows[0].id


def test_log_warning_persists_to_db(log_session) -> None:
    entry = log_warning("careful", source="test.warn")
    rows = log_session.query(models.LogEntry).all()
    assert len(rows) == 1
    assert rows[0].severity == SEVERITY_WARNING
    assert rows[0].message == "careful"


def test_log_info_persists_to_db(log_session) -> None:
    entry = log_info("starting up", source="test.info")
    rows = log_session.query(models.LogEntry).all()
    assert len(rows) == 1
    assert rows[0].severity == SEVERITY_INFO
    assert rows[0].message == "starting up"


def test_log_event_uses_external_session(log_session) -> None:
    """A caller-supplied session is used (not committed/closed by helper)."""
    entry = log_event(
        SEVERITY_ERROR, "via external session", source="test", session=log_session
    )
    # Not yet committed by the helper; flush happened, so the row is visible
    # within the same session.
    assert (
        log_session.query(models.LogEntry)
        .filter_by(message="via external session")
        .first()
        is not None
    )
    assert entry.id is not None


def test_log_exception_captures_traceback(log_session) -> None:
    """log_exception stores a formatted traceback from a real exception."""
    try:
        raise ValueError("kaboom-value")
    except ValueError as exc:
        entry = log_exception(
            SEVERITY_ERROR, "caught a value error", source="test.exc", exc=exc
        )

    rows = log_session.query(models.LogEntry).all()
    assert len(rows) == 1
    assert rows[0].severity == SEVERITY_ERROR
    # The message is the literal message; the exception text lives in stacktrace.
    assert rows[0].message == "caught a value error"
    assert rows[0].stacktrace is not None
    assert "ValueError: kaboom-value" in rows[0].stacktrace
    assert "Traceback" in rows[0].stacktrace
    assert entry.stacktrace == rows[0].stacktrace


def test_log_exception_without_exc_captures_current_frame(log_session) -> None:
    """Without an exc, log_exception captures the *active* traceback frame.

    Must be invoked from inside an except block for format_exc() to have a
    current exception to render.
    """
    try:
        raise RuntimeError("boom-frame")
    except RuntimeError:
        entry = log_exception(SEVERITY_ERROR, "no exc given", source="test.exc2")
    assert entry.stacktrace is not None
    assert "Traceback" in entry.stacktrace
    assert "RuntimeError: boom-frame" in entry.stacktrace


def test_context_is_rendered_into_message(log_session) -> None:
    """Structured context is appended to the message (no context column)."""
    entry = log_error(
        "request failed", source="test.ctx", context={"user_id": 42, "retry": 3}
    )
    assert "request failed" in entry.message
    assert "user_id" in entry.message
    assert "42" in entry.message


def test_no_empty_except_blocks_in_backend() -> None:
    """Static audit: no bare/empty ``except`` blocks remain in src/backend.

    A handler is "empty" if its body is only ``pass`` (optionally with a doc
    string) — i.e. it swallows the exception with no logging/action (R12).
    """
    backend_root = pathlib.Path(__file__).resolve().parents[2] / "src" / "backend"
    assert backend_root.exists(), f"backend dir not found at {backend_root}"

    empty_handlers = 0
    for py_file in backend_root.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            for handler in node.handlers:
                # Body considered empty if it has no meaningful statements.
                # `pass` is not meaningful; a bare docstring (Expr -> Constant
                # str) is not meaningful; but a logging/action call
                # (Expr -> Call) IS meaningful (R12: log, don't swallow).
                meaningful = False
                for n in handler.body:
                    if isinstance(n, ast.Pass):
                        continue
                    if (
                        isinstance(n, ast.Expr)
                        and isinstance(n.value, ast.Constant)
                        and isinstance(n.value.value, str)
                    ):
                        continue  # docstring
                    meaningful = True
                    break
                if not meaningful:
                    empty_handlers += 1

    assert empty_handlers == 0, (
        f"found {empty_handlers} empty except handler(s) — violates R12 (no empty catch)"
    )

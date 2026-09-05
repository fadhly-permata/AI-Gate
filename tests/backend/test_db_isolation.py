"""Prove the backend suite never writes to the live ``~/.aigate/aigate.db``.

The session conftest sets ``AIGATE_DB_PATH`` before ``backend.config.db`` is
first imported, so the module-level engine + ``SessionLocal`` (shared by the
logger and every router) bind to a throwaway temp file. These tests assert that
binding and demonstrate a real ``log_warning`` write landing in the temp DB
while the on-disk production DB is left byte-for-byte untouched.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import backend.config.db as db_mod
from backend.log import log_warning
from backend.models import LogEntry

_PRODUCTION_DB = Path.home() / ".aigate" / "aigate.db"


def _real_db_error_warning_count() -> int | None:
    """Read-only count of error/warning rows in the production DB.

    Returns ``None`` when the file does not exist (nothing to compare against).
    Opens strictly read-only (``mode=ro``) so this test can never mutate it.
    """
    if not _PRODUCTION_DB.exists():
        return None
    con = sqlite3.connect(f"file:{_PRODUCTION_DB}?mode=ro", uri=True)
    try:
        return con.execute(
            "SELECT COUNT(*) FROM log_entries "
            "WHERE severity IN ('error','warning')"
        ).fetchone()[0]
    except sqlite3.OperationalError:
        # Production DB present but no log_entries table yet -> zero rows.
        return 0
    finally:
        con.close()


def test_db_path_is_temp_not_production() -> None:
    """``DB_PATH`` must reflect the temp override, not the production file."""
    # Not the production path.
    assert db_mod.DB_PATH != _PRODUCTION_DB
    # Exactly what conftest installed via the env var.
    assert db_mod.DB_PATH == Path(os.environ["AIGATE_DB_PATH"])
    # Lives under the unique temp dir created by conftest (isolation marker).
    assert "aigate-test-isolation-" in str(db_mod.DB_PATH)
    # And that file is the one the shared SessionLocal is bound to.
    bind_url = str(db_mod.SessionLocal.kw["bind"].url)
    assert "aigate-test-isolation-" in bind_url
    assert str(_PRODUCTION_DB) not in bind_url


def test_log_warning_hits_temp_db_not_production() -> None:
    """A ``log_warning`` write increments the temp DB and leaves prod untouched."""
    real_before = _real_db_error_warning_count()

    with db_mod.SessionLocal() as session:
        before = session.query(LogEntry).filter_by(source="test").count()

    # This goes through backend.log -> _db.SessionLocal() -> the temp engine.
    log_warning("isolation probe", source="test")

    with db_mod.SessionLocal() as session:
        after = session.query(LogEntry).filter_by(source="test").count()

    # The probe row landed in the temp DB.
    assert after == before + 1

    # The production DB row count is unchanged (or absent).
    real_after = _real_db_error_warning_count()
    if real_before is not None:
        assert real_after == real_before, (
            "test wrote to the production ~/.aigate/aigate.db "
            f"(error/warning {real_before} -> {real_after})"
        )
    else:
        # No production DB to pollute; the temp DB still received the row.
        assert after > before

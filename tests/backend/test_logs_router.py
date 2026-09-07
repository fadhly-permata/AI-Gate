"""Hermetic tests for the log-cleanup backend (T1).

Covers:
- DELETE /api/logs: severity-scoped delete, confirm=all guard for wipe-all,
  ``before`` cutoff + invalid-``before`` 400, post-commit audit LogEntry.
- POST /api/logs/{id}/resolve and POST /api/logs/resolve (bulk).
- GET /api/logs ``show_resolved`` semantics (default hides resolved rows).
- ``purge_expired_logs`` retention: explicit days, Setting fallback (missing /
  invalid / non-positive -> 7).

Pattern mirrors tests/backend/test_gateway.py: an in-memory SQLite
sessionmaker (StaticPool) replaces every SessionLocal binding the router and
``backend.log`` touch, so no on-disk DB is touched.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.config.db as db_mod
import backend.config.logs_router as logs_router
from backend.models import LogEntry
from backend.server import app


def _make_sessionmaker() -> sessionmaker:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    from backend import models  # noqa: F401  (register mappers)
    from backend.config.db import Base

    Base.metadata.create_all(engine)
    return sessionmaker(
        bind=engine, autoflush=False, autocommit=False, future=True
    )


@pytest.fixture
def sf(monkeypatch) -> sessionmaker:
    """Rebind the router's SessionLocal AND backend.log's (audit rows)."""
    factory = _make_sessionmaker()
    monkeypatch.setattr(logs_router, "SessionLocal", factory)
    monkeypatch.setattr(db_mod, "SessionLocal", factory)
    return factory


@pytest.fixture
def client(sf) -> TestClient:
    # Not a context manager: the lifespan must NOT fire (it would purge rows).
    return TestClient(app)


def _seed(sf: sessionmaker, **kwargs) -> int:
    """Insert one LogEntry (defaults overridable), return its id."""
    row = LogEntry(
        severity=kwargs.pop("severity", "info"),
        source=kwargs.pop("source", "test"),
        message=kwargs.pop("message", "m"),
        stacktrace=kwargs.pop("stacktrace", None),
        resolved=kwargs.pop("resolved", False),
        timestamp=kwargs.pop("timestamp", datetime.utcnow()),
    )
    assert not kwargs, f"unexpected seed kwargs: {kwargs}"
    with sf() as s:
        s.add(row)
        s.commit()
        return row.id


def _ids(sf: sessionmaker, **filters) -> set[int]:
    with sf() as s:
        q = s.query(LogEntry)
        for k, v in filters.items():
            q = q.filter(getattr(LogEntry, k) == v)
        return {r.id for r in q.all()}


# --------------------------------------------------------------------------- #
# Task A — DELETE /api/logs
# --------------------------------------------------------------------------- #
def test_delete_with_severity_filter_deletes_only_matching(client, sf):
    err_id = _seed(sf, severity="error", message="boom")
    warn_id = _seed(sf, severity="warning", message="meh")
    info_id = _seed(sf, severity="info", message="fyi")

    resp = client.delete("/api/logs", params={"severity": "error"})
    assert resp.status_code == 200
    assert resp.json() == {"deleted": 1}

    remaining = _ids(sf)
    assert info_id in remaining and warn_id in remaining
    assert err_id not in remaining

    # Audit row: written AFTER the delete, severity=info (an or-match on
    # "error" would otherwise have deleted it with the rest).
    with sf() as s:
        audit = (
            s.query(LogEntry)
            .filter(
                LogEntry.source == "backend.config.logs_router",
                LogEntry.message.like("logs purged: deleted=%"),
            )
            .one()
        )
        assert "severity=error" in audit.message
        assert "deleted=1" in audit.message


def test_delete_wipe_all_requires_confirm(client, sf):
    _seed(sf, severity="error")
    _seed(sf, severity="info")

    resp = client.delete("/api/logs")
    assert resp.status_code == 200
    # Fixed T1 contract: 200 + error field, NOT 4xx.
    assert resp.json() == {"deleted": 0, "error": "confirmation required"}
    # Nothing was deleted.
    assert len(_ids(sf)) == 2


def test_delete_wipe_all_with_confirm_deletes_everything(client, sf):
    _seed(sf, severity="error", message="a")
    _seed(sf, severity="warning", message="b")
    _seed(sf, severity="info", message="c")

    resp = client.delete("/api/logs", params={"confirm": "all"})
    assert resp.status_code == 200
    assert resp.json() == {"deleted": 3}

    remaining = _ids(sf)
    # Only the post-commit audit row survives a wipe-all.
    assert len(remaining) == 1
    with sf() as s:
        audit = s.query(LogEntry).one()
        assert audit.severity == "info"
        assert "severity=all" in audit.message


def test_delete_before_cutoff_deletes_only_older_rows(client, sf):
    old_id = _seed(sf, severity="error", timestamp=datetime.utcnow() - timedelta(days=10))
    new_id = _seed(sf, severity="error", timestamp=datetime.utcnow() - timedelta(days=1))
    cutoff = (datetime.utcnow() - timedelta(days=5)).isoformat()

    resp = client.delete("/api/logs", params={"severity": "error", "before": cutoff})
    assert resp.status_code == 200
    assert resp.json() == {"deleted": 1}
    assert new_id in _ids(sf)
    assert old_id not in _ids(sf)


def test_delete_invalid_before_returns_400_and_deletes_nothing(client, sf):
    _seed(sf, severity="error", message="a")
    _seed(sf, severity="error", message="b")

    resp = client.delete("/api/logs", params={"severity": "error", "before": "not-a-date"})
    assert resp.status_code == 400
    assert resp.json() == {"detail": "invalid 'before'"}
    assert len(_ids(sf, severity="error")) == 2


# --------------------------------------------------------------------------- #
# Task C — resolve endpoints + GET show_resolved
# --------------------------------------------------------------------------- #
def test_resolve_single_flags_row(client, sf):
    entry_id = _seed(sf, severity="warning", message="fixme")

    resp = client.post(f"/api/logs/{entry_id}/resolve")
    assert resp.status_code == 200
    assert resp.json() == {"resolved": 1}

    with sf() as s:
        row = s.get(LogEntry, entry_id)
        assert row.resolved is True


def test_resolve_single_unknown_id_returns_zero(client, sf):
    """Fixed T1 contract: unknown id → 200 {"resolved": 0}, not 404."""
    resp = client.post("/api/logs/999999/resolve")
    assert resp.status_code == 200
    assert resp.json() == {"resolved": 0}


def test_resolve_bulk_mixed_ids_returns_matched_count(client, sf):
    id1 = _seed(sf, severity="warning", message="a")
    id2 = _seed(sf, severity="error", message="b")
    _seed(sf, severity="warning", message="c")

    resp = client.post("/api/logs/resolve", json={"ids": [id1, id2, 424242]})
    assert resp.status_code == 200
    assert resp.json() == {"resolved": 2}

    flagged = _ids(sf, resolved=True)
    assert flagged == {id1, id2}


def test_resolve_bulk_empty_ids_resolves_nothing(client, sf):
    _seed(sf, severity="warning")
    resp = client.post("/api/logs/resolve", json={"ids": []})
    assert resp.status_code == 200
    assert resp.json() == {"resolved": 0}
    assert _ids(sf, resolved=True) == set()


def test_get_default_excludes_resolved_show_resolved_includes(client, sf):
    _seed(sf, severity="warning", message="open issue")
    _seed(sf, severity="warning", message="closed issue", resolved=True)

    resp = client.get("/api/logs")
    assert resp.status_code == 200
    messages = [e["message"] for e in resp.json()["data"]]
    assert messages == ["open issue"]

    resp = client.get("/api/logs", params={"show_resolved": "true"})
    assert resp.status_code == 200
    messages = sorted(e["message"] for e in resp.json()["data"])
    assert messages == ["closed issue", "open issue"]

    # Shape carries the flag for the UI.
    entry = next(
        e
        for e in client.get("/api/logs", params={"show_resolved": "true"}).json()["data"]
        if e["message"] == "closed issue"
    )
    assert entry["resolved"] is True


def test_get_row_dict_includes_resolved_false_by_default(client, sf):
    _seed(sf, severity="info", message="plain")
    entry = client.get("/api/logs").json()["data"][0]
    assert entry["resolved"] is False


# --------------------------------------------------------------------------- #
# Task B — purge_expired_logs retention
# --------------------------------------------------------------------------- #
def test_purge_expired_logs_explicit_days_7(sf):
    old_id = _seed(sf, severity="warning", timestamp=datetime.utcnow() - timedelta(days=10))
    new_id = _seed(sf, severity="warning", timestamp=datetime.utcnow() - timedelta(days=1))

    with sf() as s:
        deleted = logs_router.purge_expired_logs(days=7, session=s)
        s.commit()  # caller owns the session: purge never commits for it

    assert deleted == 1
    assert new_id in _ids(sf)
    assert old_id not in _ids(sf)


def test_purge_expired_logs_days_0_deletes_everything_past(sf):
    _seed(sf, severity="warning", timestamp=datetime.utcnow() - timedelta(days=2))
    _seed(sf, severity="error", timestamp=datetime.utcnow() - timedelta(days=30))

    with sf() as s:
        deleted = logs_router.purge_expired_logs(days=0, session=s)
        s.commit()

    assert deleted == 2
    assert _ids(sf) == set()


def test_purge_expired_logs_invalid_setting_falls_back_to_7(sf, monkeypatch):
    from backend.config import settings as settings_repo

    old_id = _seed(sf, severity="warning", timestamp=datetime.utcnow() - timedelta(days=10))
    new_id = _seed(sf, severity="warning", timestamp=datetime.utcnow() - timedelta(days=1))

    monkeypatch.setattr(settings_repo, "get", lambda *a, **k: "banana")
    with sf() as s:
        deleted = logs_router.purge_expired_logs(days=None, session=s)
        s.commit()
    assert deleted == 1
    assert old_id not in _ids(sf) and new_id in _ids(sf)

    # Non-positive values fall back to 7 too.
    monkeypatch.setattr(settings_repo, "get", lambda *a, **k: "0")
    with sf() as s:
        assert logs_router.purge_expired_logs(days=None, session=s) == 0

    # Missing Setting -> default 7 (nothing else is older than 7 days now).
    monkeypatch.setattr(settings_repo, "get", lambda *a, **k: None)
    with sf() as s:
        assert logs_router.purge_expired_logs(days=None, session=s) == 0


def test_purge_expired_logs_uses_session_factory_when_no_session(sf):
    _seed(sf, severity="warning", timestamp=datetime.utcnow() - timedelta(days=10))

    # days explicit, no session -> uses the (patched) SessionLocal binding.
    assert logs_router.purge_expired_logs(days=7) == 1
    assert _ids(sf) == set()

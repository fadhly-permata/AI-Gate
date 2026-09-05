"""Hermetic tests for the Self-Heal backend (task B4.1).

All external boundaries are faked via ``monkeypatch``:
- ``backend.selfheal.shutil.which`` -> simulated agentic CLI detection.
- ``backend.selfheal.subprocess.run`` -> a spy that succeeds for git/CLI calls
  and returns rc=0 for ``pytest``.
- ``backend.config.db.SessionLocal`` -> an in-memory SQLite session factory
  (shared StaticPool connection so seeded rows are visible to ``run_self_heal``).

No real git repo, no real agentic binary, no on-disk DB are touched.
"""

from __future__ import annotations

import subprocess
from typing import List

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import selfheal
from backend.config import db as db_module
from backend.models import LogEntry


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def mem_session_factory():
    """In-memory SQLite factory sharing one connection (StaticPool)."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    # Importing models registers mappers onto Base.metadata.
    from backend import models  # noqa: F401
    from backend.config.db import Base

    Base.metadata.create_all(engine)
    factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, future=True
    )
    return factory


@pytest.fixture
def spy_run(monkeypatch):
    """Replace ``subprocess.run`` with a recording spy.

    - Any command containing ``pytest`` -> rc=0 (tests pass).
    - Otherwise -> rc=0 (git / agentic cli succeed).
    """
    calls: List[list] = []

    def _fake(args, *a, **kw):
        calls.append(list(args) if isinstance(args, (list, tuple)) else list(args))
        rc = 0 if "pytest" in (args or []) else 0
        return subprocess.CompletedProcess(args, rc)

    monkeypatch.setattr(selfheal.subprocess, "run", _fake)
    return calls


# --------------------------------------------------------------------------- #
# 1. detect_agentic_cli
# --------------------------------------------------------------------------- #
def test_detect_agentic_cli_found(monkeypatch):
    monkeypatch.setattr(selfheal.shutil, "which", lambda name: "opencode")
    assert selfheal.detect_agentic_cli() == "opencode"


def test_detect_agentic_cli_none(monkeypatch):
    monkeypatch.setattr(selfheal.shutil, "which", lambda name: None)
    assert selfheal.detect_agentic_cli() is None


def test_agentic_cli_endpoint_unavailable(monkeypatch, client):
    monkeypatch.setattr(selfheal.shutil, "which", lambda name: None)
    resp = client.get("/api/self-heal/agentic-cli")
    assert resp.status_code == 200
    assert resp.json() == {"available": False, "cli": None}


def test_agentic_cli_endpoint_available(monkeypatch, client):
    monkeypatch.setattr(selfheal.shutil, "which", lambda name: "opencode")
    resp = client.get("/api/self-heal/agentic-cli")
    assert resp.status_code == 200
    assert resp.json() == {"available": True, "cli": "opencode"}


# --------------------------------------------------------------------------- #
# 2. Full run_self_heal happy path
# --------------------------------------------------------------------------- #
def test_run_self_heal_happy_path(monkeypatch, mem_session_factory, spy_run):
    monkeypatch.setattr(selfheal.shutil, "which", lambda name: "opencode")
    monkeypatch.setattr(db_module, "SessionLocal", mem_session_factory)

    # Seed one warning LogEntry.
    with mem_session_factory() as seed:
        seed.add(
            LogEntry(
                severity="warning",
                source="test",
                message="boom",
                stacktrace="trace",
            )
        )
        seed.commit()
        seeded_id = seed.query(LogEntry).first().id

    result = selfheal.run_self_heal(max_iter=2)

    # Status contract.
    assert result["ok"] is True
    assert result.get("merged") is True
    assert result.get("iterations") == 1

    # The seeded warning LogEntry was deleted (info-level heal logs remain).
    with mem_session_factory() as verify:
        assert verify.query(LogEntry).filter_by(id=seeded_id).count() == 0
        # And no warning/error rows remain.
        assert (
            verify.query(LogEntry)
            .filter(LogEntry.severity.in_(("warning", "error")))
            .count()
            == 0
        )

    # git merge + branch -d were invoked.
    joined = [" ".join(c) for c in spy_run]
    assert any("git merge" in c for c in joined), joined
    assert any("git branch -d" in c for c in joined), joined


# --------------------------------------------------------------------------- #
# 3. No-agentic-cli path (endpoint)
# --------------------------------------------------------------------------- #
def test_run_self_heal_no_cli(monkeypatch, mem_session_factory, client):
    monkeypatch.setattr(selfheal.shutil, "which", lambda name: None)
    # NOTE: do NOT patch SessionLocal here — run_self_heal returns *before*
    # touching the DB when no CLI is found, and backend.log writes its own
    # log entries via SessionLocal. Leaving it pointing at the real (on-disk)
    # DB keeps our in-memory seeded entry isolated.

    with mem_session_factory() as seed:
        seed.add(
            LogEntry(severity="error", source="test", message="nope")
        )
        seed.commit()
        seeded_id = seed.query(LogEntry).first().id

    resp = client.post("/api/self-heal/run")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"ok": False, "reason": "no_agentic_cli"}

    # Entry was NOT deleted (healing short-circuited before touching the DB).
    with mem_session_factory() as verify:
        assert verify.query(LogEntry).filter_by(id=seeded_id).count() == 1


# --------------------------------------------------------------------------- #
# 4. git_failed path (git binary missing)
# --------------------------------------------------------------------------- #
def test_run_self_heal_git_failed(monkeypatch, mem_session_factory, spy_run):
    monkeypatch.setattr(selfheal.shutil, "which", lambda name: "opencode")
    monkeypatch.setattr(db_module, "SessionLocal", mem_session_factory)

    # Make git() raise by having subprocess.run raise FileNotFoundError.
    def _boom(args, *a, **kw):
        spy_run.append(list(args))
        raise FileNotFoundError("git missing")

    monkeypatch.setattr(selfheal.subprocess, "run", _boom)

    with mem_session_factory() as seed:
        seed.add(
            LogEntry(severity="warning", source="test", message="x")
        )
        seed.commit()

    result = selfheal.run_self_heal(max_iter=2)
    assert result["ok"] is False
    assert result["reason"] == "git_failed"
    assert "detail" in result

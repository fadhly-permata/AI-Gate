"""Hermetic tests for the Self-Heal backend (task B4.1).

All external boundaries are faked via ``monkeypatch``:
- ``backend.selfheal.shutil.which`` -> simulated agentic CLI detection.
- ``backend.selfheal.subprocess.run`` -> a spy that succeeds for git/CLI calls
  and returns rc=0 for ``pytest``.
- ``backend.config.db.SessionLocal`` -> an in-memory SQLite session factory
  (shared StaticPool connection so seeded rows are visible to ``run_self_heal``).
- The terminal PTY layer -> :class:`FakeHealSession` (records the command the
  orchestrator types; can simulate the shell's ``touch`` and a dead session),
  so no real shell is spawned.

No real git repo, no real agentic binary, no on-disk DB, no real PTY.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
import threading
import time
import types
from pathlib import Path
from typing import List

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import selfheal
from backend import selfheal_router
from backend.config import db as db_module
from backend.models import LogEntry, TerminalTab


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


class FakeHealSession:
    """PtySession double: records writes; simulates the shell's ``touch``.

    ``touch_done=True`` makes ``write_text`` create the done-sentinel file the
    command asks the shell to touch (so ``wait_for_done`` returns immediately).
    ``die_after_write`` marks the session exited right after the write, which
    is how "user closed the tab / shell died mid-issue" is simulated.
    """

    def __init__(self, touch_done: bool = True, die_after_write: bool = False):
        self.writes: List[str] = []
        self.exited = False
        self.touch_done = touch_done
        self.die_after_write = die_after_write
        self.db_tab_id = None
        self.pty = types.SimpleNamespace(pid=4242, is_alive=lambda: not self.exited)

    def write_text(self, text: str) -> None:
        self.writes.append(text)
        if self.touch_done:
            match = re.search(r"touch '([^']+)'", text)
            assert match, f"command lacks the touch sentinel: {text!r}"
            Path(match.group(1)).write_text("", encoding="utf-8")
        if self.die_after_write:
            self.exited = True


@pytest.fixture
def mute_heal_logs(monkeypatch):
    """Silence backend.log inside selfheal.

    Why: log_warning() persists LogEntry(severity='warning') rows — into the
    SAME patched in-memory DB the tests seed — so heal diagnostics would
    pollute the very issue-count the orchestration reports. Muted here to
    keep ``remaining`` assertions deterministic (logging itself is exercised
    elsewhere).
    """
    monkeypatch.setattr(selfheal, "log_info", lambda *a, **k: None)
    monkeypatch.setattr(selfheal, "log_warning", lambda *a, **k: None)
    monkeypatch.setattr(selfheal, "log_error_exc", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def _clean_heal_state():
    """Zero the async run state after every test (no cross-test leakage)."""
    yield
    selfheal.reset_self_heal_state()


def _wait_until(cond, timeout: float = 3.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cond():
            return True
        time.sleep(0.01)
    return False


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
    monkeypatch.setattr(
        selfheal, "_ensure_heal_session", lambda: FakeHealSession(touch_done=True)
    )

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
# 3. No-agentic-cli path (sync service contract; POST /run is async now)
# --------------------------------------------------------------------------- #
def test_run_self_heal_no_cli(monkeypatch, mem_session_factory):
    """No CLI installed -> run_self_heal short-circuits before any DB/PTY use.

    (POST /api/self-heal/run no longer returns this synchronously — it starts
    the background thread; the shape surfaces later as status.last. Here the
    sync service contract is verified directly.)
    """
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

    result = selfheal.run_self_heal(max_iter=2)
    assert result == {"ok": False, "reason": "no_agentic_cli"}

    # Entry was NOT deleted (healing short-circuited before touching the DB).
    with mem_session_factory() as verify:
        assert verify.query(LogEntry).filter_by(id=seeded_id).count() == 1


def test_start_self_heal_no_cli_records_result(
    monkeypatch, mem_session_factory
):
    """Async path: even 'no_agentic_cli' ends up as status.last once the
    background thread finishes."""
    monkeypatch.setattr(selfheal.shutil, "which", lambda name: None)
    outcome = selfheal.start_self_heal(max_iter=1)
    assert outcome == {"started": True, "tab": "self-heal"}
    assert _wait_until(
        lambda: selfheal.heal_status() == {
            "running": False,
            "last": {"ok": False, "reason": "no_agentic_cli"},
        }
    )


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


# --------------------------------------------------------------------------- #
# 5. Terminal-driven CLI: command typed into the PTY, donefile polled
# --------------------------------------------------------------------------- #
def test_run_self_heal_types_command_into_pty(
    monkeypatch, mem_session_factory, spy_run
):
    """Per-issue: one command line goes to the PTY, prompt lives ONLY in the
    temp file (never in the command), and the run proceeds via the donefile."""
    monkeypatch.setattr(selfheal.shutil, "which", lambda name: "opencode")
    monkeypatch.setattr(db_module, "SessionLocal", mem_session_factory)
    fake = FakeHealSession(touch_done=True)
    monkeypatch.setattr(selfheal, "_ensure_heal_session", lambda: fake)

    with mem_session_factory() as seed:
        seed.add(LogEntry(severity="error", source="t", message="boom"))
        seed.commit()

    result = selfheal.run_self_heal(max_iter=1)
    assert result["ok"] is True and result["merged"] is True

    # Exactly one command, one line, ending with \n.
    assert len(fake.writes) == 1
    command = fake.writes[0]
    assert command.endswith("\n")
    assert "\n" not in command[:-1]
    # CLI + promptfile indirection + donefile sentinel present.
    assert command.startswith("opencode --prompt \"$(cat '")
    assert "touch '" in command
    assert "aigate: issue done" in command
    # Shell-injection guard: no LogEntry content may leak into the command.
    assert "boom" not in command
    # The prompt file is gone (cleaned up in finally).
    match = re.search(r"cat '([^']+)'", command)
    assert match and not Path(match.group(1)).exists()


def test_run_self_heal_cli_timeout_continues_to_tests(
    monkeypatch, mem_session_factory, spy_run, mute_heal_logs
):
    """Donefile never appears -> per-issue timeout -> tests still decide."""
    monkeypatch.setattr(selfheal.shutil, "which", lambda name: "opencode")
    monkeypatch.setattr(db_module, "SessionLocal", mem_session_factory)
    # touch_done=False: the "shell" never touches the sentinel.
    fake = FakeHealSession(touch_done=False)
    monkeypatch.setattr(selfheal, "_ensure_heal_session", lambda: fake)
    monkeypatch.setattr(selfheal, "HEAL_CLI_TIMEOUT_SECONDS", 0.3)
    monkeypatch.setattr(selfheal, "DONE_POLL_INTERVAL_SECONDS", 0.05)

    with mem_session_factory() as seed:
        seed.add(LogEntry(severity="error", source="t", message="stuck"))
        seed.commit()
        issue_id = seed.query(LogEntry).first().id

    result = selfheal.run_self_heal(max_iter=1)
    # Timeout logged a warning; tests ran (spy rc=0) and deleted the issue.
    assert result["ok"] is True and result["merged"] is True
    with mem_session_factory() as verify:
        assert verify.query(LogEntry).filter_by(id=issue_id).count() == 0


def test_run_self_heal_aborts_when_session_dies(
    monkeypatch, mem_session_factory, spy_run, mute_heal_logs
):
    """User closes the tab / shell dies mid-issue -> abort, nothing deleted,
    shape ``{"ok": True, "merged": False, "remaining": N}``."""
    monkeypatch.setattr(selfheal.shutil, "which", lambda name: "opencode")
    monkeypatch.setattr(db_module, "SessionLocal", mem_session_factory)
    fake = FakeHealSession(touch_done=False, die_after_write=True)
    monkeypatch.setattr(selfheal, "_ensure_heal_session", lambda: fake)

    with mem_session_factory() as seed:
        seed.add(LogEntry(severity="error", source="t", message="a"))
        seed.commit()
        issue_id = seed.query(LogEntry).first().id

    result = selfheal.run_self_heal(max_iter=3)
    assert result == {"ok": True, "merged": False, "remaining": 1}
    with mem_session_factory() as verify:
        assert verify.query(LogEntry).filter_by(id=issue_id).count() == 1
    # Aborted BEFORE run_tests -> no pytest, and the branch is left unmerged.
    joined = [" ".join(c) for c in spy_run]
    assert not any("pytest" in c for c in joined), joined
    assert not any("git merge" in c for c in joined), joined


def test_run_self_heal_aborts_remaining_minus_one_on_db_error(
    monkeypatch, mem_session_factory, spy_run, mute_heal_logs
):
    """Session-death abort when even the remaining-count fails -> -1."""
    monkeypatch.setattr(selfheal.shutil, "which", lambda name: "opencode")
    monkeypatch.setattr(db_module, "SessionLocal", mem_session_factory)
    fake = FakeHealSession(touch_done=False, die_after_write=True)
    monkeypatch.setattr(selfheal, "_ensure_heal_session", lambda: fake)

    with mem_session_factory() as seed:
        seed.add(LogEntry(severity="error", source="t", message="a"))
        seed.commit()

    def _boom(_session):
        raise RuntimeError("db gone")

    monkeypatch.setattr(selfheal, "_count_remaining", _boom)
    result = selfheal.run_self_heal(max_iter=1)
    assert result == {"ok": True, "merged": False, "remaining": -1}


def test_wait_for_done_polls_until_sentinel(monkeypatch, tmp_path):
    """wait_for_done: True as soon as the sentinel exists; session-alive
    probes are consulted while waiting."""
    donefile = tmp_path / "x.prompt.done"
    probes: List[bool] = []

    def fake_alive(_session):
        probes.append(True)
        donefile.parent.mkdir(parents=True, exist_ok=True)
        donefile.write_text("", encoding="utf-8")  # appear on first probe
        return True

    monkeypatch.setattr(selfheal, "_session_alive", fake_alive)
    assert selfheal.wait_for_done(donefile, object(), timeout=5.0, poll=0.01)
    assert probes  # at least one liveness probe happened


# --------------------------------------------------------------------------- #
# 6. Async run: start_self_heal / heal_status / router contract
# --------------------------------------------------------------------------- #
def test_start_self_heal_starts_thread_and_status_flips(
    monkeypatch, mem_session_factory
):
    """start_self_heal spawns a daemon thread, status goes running=True then
    back to False with last=result when the run finishes."""
    monkeypatch.setattr(selfheal.shutil, "which", lambda name: None)
    monkeypatch.setattr(db_module, "SessionLocal", mem_session_factory)
    started = threading.Event()
    release = threading.Event()

    def slow_run(max_iter: int = 5) -> dict:
        started.set()
        release.wait(3.0)
        return {"ok": True, "merged": False, "remaining": 0}

    monkeypatch.setattr(selfheal, "run_self_heal", slow_run)

    outcome = selfheal.start_self_heal(max_iter=2)
    assert outcome == {"started": True, "tab": "self-heal"}
    assert started.wait(3.0)
    snap = selfheal.heal_status()
    assert snap["running"] is True
    assert snap["last"] is None

    release.set()
    assert _wait_until(lambda: selfheal.heal_status()["running"] is False)
    snap = selfheal.heal_status()
    assert snap["last"] == {"ok": True, "merged": False, "remaining": 0}


def test_start_self_heal_rejects_second_run(monkeypatch):
    """A run already in flight -> {"started": False, "reason":
    "already_running"} (router maps it to 409)."""
    release = threading.Event()
    try:
        monkeypatch.setattr(
            selfheal,
            "run_self_heal",
            lambda max_iter=5: (release.wait(3.0), {"ok": True, "merged": False})[1],
        )
        first = selfheal.start_self_heal()
        second = selfheal.start_self_heal()
        assert first == {"started": True, "tab": "self-heal"}
        assert second == {"started": False, "reason": "already_running"}
    finally:
        release.set()
        assert _wait_until(lambda: not selfheal.heal_status()["running"])


def test_router_run_200_then_409(monkeypatch, client):
    """POST /run: 200 accept envelope, then 409 while the first still runs."""
    release = threading.Event()
    try:
        monkeypatch.setattr(
            selfheal,
            "run_self_heal",
            lambda max_iter=5: (release.wait(3.0), {"ok": True, "merged": False})[1],
        )
        resp = client.post("/api/self-heal/run")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True, "started": True, "tab": "self-heal"}

        resp2 = client.post("/api/self-heal/run")
        assert resp2.status_code == 409
        assert resp2.json() == {
            "ok": False,
            "reason": "already_running",
            "tab": "self-heal",
        }
    finally:
        release.set()
        assert _wait_until(lambda: not selfheal.heal_status()["running"])


def test_router_run_500_envelope(monkeypatch, client):
    """start_self_heal raising -> structured self_heal_failed envelope."""
    def boom():
        raise RuntimeError("kaboom")

    monkeypatch.setattr(selfheal_router, "start_self_heal", boom)
    resp = client.post("/api/self-heal/run")
    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["code"] == "self_heal_failed"
    assert "kaboom" in body["error"]["message"]


def test_router_status_running_and_last(monkeypatch, client):
    """GET /status mirrors heal_status(): idle-null and running+last shapes."""
    # Idle: nothing running, no last result.
    selfheal.reset_self_heal_state()
    resp = client.get("/api/self-heal/status")
    assert resp.status_code == 200
    assert resp.json() == {"running": False, "last": None}

    release = threading.Event()
    try:
        monkeypatch.setattr(
            selfheal,
            "run_self_heal",
            lambda max_iter=5: (release.wait(3.0), {"ok": False, "reason": "x"})[1],
        )
        assert selfheal.start_self_heal()["started"] is True
        assert _wait_until(lambda: selfheal.heal_status()["running"] is True)
        resp = client.get("/api/self-heal/status")
        assert resp.status_code == 200
        assert resp.json() == {"running": True, "last": None}

        release.set()
        assert _wait_until(lambda: not selfheal.heal_status()["running"])
        resp = client.get("/api/self-heal/status")
        assert resp.json() == {"running": False, "last": {"ok": False, "reason": "x"}}
    finally:
        release.set()


def test_start_self_heal_creates_db_tab_row_with_title(
    monkeypatch, mem_session_factory
):
    """First session spawn binds a TerminalTab row titled 'Self-Heal'."""
    monkeypatch.setattr(db_module, "SessionLocal", mem_session_factory)
    tab_id = selfheal._create_heal_db_tab()
    assert tab_id > 0
    with mem_session_factory() as s:
        row = s.get(TerminalTab, tab_id)
        assert row is not None
        assert row.title == "Self-Heal"
        assert row.pty_pid == ""  # pid set later by the session registry


def test_ensure_heal_session_uses_registry_and_creates_row(
    monkeypatch, mem_session_factory
):
    """_ensure_heal_session reuses a LIVE registered session (no respawn) and
    passes the DB-row factory into get_or_create."""
    import backend.terminal.session as term_mod

    monkeypatch.setattr(db_module, "SessionLocal", mem_session_factory)

    fake = FakeHealSession()
    monkeypatch.setattr(term_mod, "get_session", lambda key: fake)
    captured: dict = {}

    def fake_get_or_create(key, create_tab=None):
        captured["key"] = key
        captured["create_tab"] = create_tab
        return fake

    monkeypatch.setattr(term_mod, "get_or_create", fake_get_or_create)
    got = selfheal._ensure_heal_session()
    assert got is fake  # live session reused, get_or_create never called
    assert captured == {}  # no respawn attempt for a live session

    # Dead session -> dropped, fresh one requested via get_or_create.
    fake.exited = True
    fake2 = FakeHealSession()
    monkeypatch.setattr(
        term_mod,
        "get_or_create",
        lambda key, create_tab=None: captured.update(
            key=key, create_tab=create_tab
        )
        or fake2,
    )
    got2 = selfheal._ensure_heal_session()
    assert got2 is fake2
    assert captured["key"] == selfheal.HEAL_TAB_KEY
    assert callable(captured["create_tab"])


def test_create_heal_db_tab_failure_is_soft(monkeypatch, mem_session_factory):
    """DB hiccup -> log (best-effort) + return 0, never raise into the run."""

    class FlakyFactory:
        """First call raises (tab creation), later calls succeed (logging)."""

        def __init__(self) -> None:
            self.calls = 0

        def __call__(self):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("db down")
            return mem_session_factory()

    monkeypatch.setattr(db_module, "SessionLocal", FlakyFactory())
    assert selfheal._create_heal_db_tab() == 0


def test_build_heal_command_shape(tmp_path):
    """Command is one \\n-terminated line embedding only controlled paths."""
    promptfile = tmp_path / "aigate-heal-x.prompt"
    donefile = Path(str(promptfile) + ".done")
    command = selfheal.build_heal_command("opencode", promptfile, donefile)
    assert command.endswith("\n")
    assert "\n" not in command[:-1]
    assert command.startswith("opencode --prompt \"$(cat '")
    assert str(promptfile) in command and str(donefile) in command

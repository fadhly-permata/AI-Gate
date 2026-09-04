"""Tests for the PTY session registry (SAFETY: the PTY outlives the WS).

Guards the safety fix: a dropped WebSocket (tab freeze / network blip) must
NEVER kill a running shell. The WS is a detachable view over a server-side
:class:`PtySession`; only an explicit ``{"type":"close"}`` control frame or
the reaper (exited PTY / long-orphaned idle session) terminate the process.

All tests use a :class:`FakePty` (no real shell) by monkeypatching
``backend.terminal.session.spawn_shell`` — mirroring how test_terminal.py
treats the native PTY dep.
"""

from __future__ import annotations

import threading
import time

import pytest
from fastapi.testclient import TestClient

import backend.terminal.session as session_mod
from backend.terminal.session import (
    RING_MAX_BYTES,
    PtySession,
    get_or_create,
    get_session,
    reap_idle,
    snapshot_sessions,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
class FakePty:
    """PTY double: scripted reads, then blocks like a real idle pty.

    ``read()`` pops the script (bytes or an exception to raise); when the
    script is exhausted it blocks (polling every 20 ms, so data appended
    later is picked up) and raises EOFError once killed — exactly what a
    real pty does on teardown.
    """

    def __init__(self, script=None, pid: int = 4242) -> None:
        self._script = list(script) if script is not None else [b"hello-1\r\n"]
        self.pid = pid
        self.killed = False
        self.writes: list[bytes] = []
        self.resizes: list[tuple[int, int]] = []
        self._wake = threading.Event()

    def read(self, size: int = 65536) -> bytes:
        while True:
            if self._script:
                item = self._script.pop(0)
                if isinstance(item, BaseException):
                    raise item
                return item
            if self.killed:
                raise EOFError("fake pty closed")
            self._wake.wait(0.02)

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    def set_winsize(self, cols: int, rows: int) -> None:
        self.resizes.append((cols, rows))

    def is_alive(self) -> bool:
        return not self.killed

    def kill(self) -> None:
        self.killed = True
        self._wake.set()


@pytest.fixture
def fake_spawn(monkeypatch: pytest.MonkeyPatch):
    """Patch ``spawn_shell``; record every fake PTY created."""
    created: list[FakePty] = []

    def factory(cols: int = 80, rows: int = 24) -> FakePty:
        pty = FakePty()
        created.append(pty)
        return pty

    monkeypatch.setattr(session_mod, "spawn_shell", factory)
    return created


@pytest.fixture(autouse=True)
def _clean_registry():
    """Terminate any session left in the registry after each test."""
    yield
    for sess in snapshot_sessions():
        sess.terminate()


def _wait_until(cond, timeout: float = 3.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cond():
            return True
        time.sleep(0.01)
    return False


def _recv_until(ws, needle: str, max_frames: int = 50) -> str:
    got = ""
    for _ in range(max_frames):
        try:
            got += ws.receive_text()
        except Exception:  # noqa: BLE001 - closed / drained before needle
            break
        if needle in got:
            break
    return got


# --------------------------------------------------------------------------- #
# 1) get_or_create: spawn ONCE per tab_id, reattach never respawns
# --------------------------------------------------------------------------- #
def test_get_or_create_same_session_no_respawn(fake_spawn):
    s1 = get_or_create(11)
    s2 = get_or_create(11, cols=120, rows=40)  # reattach-style second call
    assert s1 is s2
    assert len(fake_spawn) == 1  # pty spawned exactly once
    assert get_session(11) is s1
    # A different tab gets its own session.
    s3 = get_or_create(12)
    assert s3 is not s1
    assert len(fake_spawn) == 2


def test_get_or_create_respawns_after_pty_exit(fake_spawn):
    s1 = get_or_create(41)
    s1.pty.killed = True  # simulate the shell process exiting
    assert _wait_until(lambda: s1.exited)  # reader marks it exited
    s2 = get_or_create(41)  # lazy reap sweep drops the dead one → fresh spawn
    assert s2 is not s1
    assert len(fake_spawn) == 2


# --------------------------------------------------------------------------- #
# 2) SAFETY: detach keeps the PTY alive + buffers output for replay
# --------------------------------------------------------------------------- #
def test_detach_keeps_pty_alive_and_buffers_for_reattach():
    pty = FakePty(script=[])
    sess = PtySession(tab_id=99, pty=pty, cols=80, rows=24)
    sess.start_reader()
    ws = object()
    # loop=None → live delivery skipped; ring buffer still records output.
    replay, _queue = sess.attach(ws, None)  # type: ignore[arg-type]
    assert replay == []

    sess.detach(ws)
    assert sess.attached is None
    assert pty.killed is False  # SAFETY: detach must NOT kill the shell
    assert sess.reader is not None and sess.reader.is_alive()  # reader runs on

    # Output produced while detached is buffered, not lost...
    pty._script.append(b"while-away\r\n")
    assert _wait_until(lambda: b"while-away\r\n" in list(sess.ring))
    # ...and replayed to the next view that attaches.
    replay2, _ = sess.attach(object(), None)  # type: ignore[arg-type]
    assert b"while-away\r\n" in replay2
    assert sess.attached is not None

    sess.terminate()  # the deliberate-close path DOES kill
    assert pty.killed is True
    assert _wait_until(lambda: not sess.reader.is_alive())


# --------------------------------------------------------------------------- #
# 3) Ring buffer: capped total size, keeps the most recent chunks
# --------------------------------------------------------------------------- #
def test_ring_buffer_capped_and_replays_recent():
    sess = PtySession(tab_id=98, pty=FakePty(script=[]), cols=80, rows=24)
    chunk = b"x" * 40960  # 40 KB
    for i in range(10):
        sess._publish(chunk + bytes([65 + i]))  # A..J, oldest first
    assert sess.ring_bytes <= RING_MAX_BYTES
    # 7th publish crosses the cap → oldest evicted; newest always kept.
    assert sess.ring[-1].endswith(b"J")
    assert sess.ring[0].endswith(b"E")
    assert all(not c.endswith(b"A") for c in sess.ring)


# --------------------------------------------------------------------------- #
# 4) Reaper: exited → reaped; live-detached within grace → NOT reaped
# --------------------------------------------------------------------------- #
def test_try_reap_rules():
    now = time.monotonic()
    grace = 3600.0

    # Exited PTY → reaped immediately (kill + gone from registry).
    p1 = FakePty(script=[])
    s1 = PtySession(tab_id=21, pty=p1, cols=80, rows=24)
    s1.exited = True
    assert s1.try_reap(now, grace) is True
    assert p1.killed is True

    # Live + detached, idle within grace → NEVER reaped (running job safe).
    p2 = FakePty(script=[])
    s2 = PtySession(tab_id=22, pty=p2, cols=80, rows=24)
    s2.last_output_ts = now - 10
    assert s2.try_reap(now, grace) is False
    assert p2.killed is False
    # Live + detached beyond the generous grace → orphan, reaped.
    s2.last_output_ts = now - (grace + 1)
    assert s2.try_reap(now, grace) is True
    assert p2.killed is True

    # Attached (someone is watching) → never reaped, however idle.
    p3 = FakePty(script=[])
    s3 = PtySession(tab_id=23, pty=p3, cols=80, rows=24)
    s3.attach(object(), None)  # type: ignore[arg-type]
    s3.last_output_ts = now - 999999
    assert s3.try_reap(now, grace) is False
    assert p3.killed is False


def test_reap_idle_sweeps_registry(fake_spawn):
    sess = get_or_create(31)
    assert get_session(31) is sess
    sess.pty.killed = True  # shell exits
    assert _wait_until(lambda: sess.exited)
    assert 31 in reap_idle()
    assert get_session(31) is None

    # A fresh live-but-detached session survives the sweep.
    sess2 = get_or_create(32)
    assert reap_idle() == []
    assert get_session(32) is sess2


# --------------------------------------------------------------------------- #
# 5) WS handler lifecycle: disconnect→detach, reconnect→replay, close→kill
# --------------------------------------------------------------------------- #
def test_ws_disconnect_reattach_close_lifecycle(client, fake_spawn):
    from backend.config.db import SessionLocal
    from backend.models import TerminalTab
    from backend.terminal.router import _create_tab

    tid = _create_tab()
    with TestClient(client.app) as c:
        # -- connection 1: fresh spawn, keystrokes + resize reach the pty ---- #
        with c.websocket_connect(f"/ws/terminal/{tid}") as ws:
            got = _recv_until(ws, "hello-1")
            assert "hello-1" in got
            ws.send_text("ls\r")
            ws.send_text('{"type":"resize","cols":120,"rows":40}')
        assert len(fake_spawn) == 1
        pty = fake_spawn[0]

        # SAFETY: disconnect DETACHED — it must NOT kill the shell.
        sess = get_session(tid)
        assert sess is not None
        assert _wait_until(lambda: sess.attached is None)
        assert pty.killed is False
        assert sess.reader is not None and sess.reader.is_alive()
        assert b"ls\r" in pty.writes
        assert (120, 40) in pty.resizes
        with SessionLocal() as s:
            assert s.get(TerminalTab, tid).pty_pid == str(pty.pid)

        # Output produced while no client is attached is buffered...
        pty._script.append(b"while-away\r\n")
        assert _wait_until(lambda: b"while-away\r\n" in list(sess.ring))

        # -- connection 2: SAME session (no respawn), replays recent output -- #
        with c.websocket_connect(f"/ws/terminal/{tid}") as ws2:
            got2 = _recv_until(ws2, "while-away")
        assert "hello-1" in got2 and "while-away" in got2
        assert len(fake_spawn) == 1  # reattached, never respawned
        assert get_session(tid) is sess

        # -- connection 3: explicit {"type":"close"} kills + removes --------- #
        with c.websocket_connect(f"/ws/terminal/{tid}") as ws3:
            ws3.send_text('{"type":"close"}')
            try:
                while True:
                    ws3.receive_text()
            except Exception:  # noqa: BLE001 - server closed the socket
                pass
        assert pty.killed is True
        assert get_session(tid) is None
        with SessionLocal() as s:
            assert s.get(TerminalTab, tid).pty_pid == ""


# --------------------------------------------------------------------------- #
# 6) Grace default: Setting value + fallback on garbage
# --------------------------------------------------------------------------- #
def test_grace_seconds_reads_setting(monkeypatch):
    def fake_get(key, default=None, session=None):
        assert key == session_mod.SETTING_IDLE_REAP_MINUTES
        return default

    monkeypatch.setattr(session_mod.settings_repo, "get", fake_get)
    assert session_mod._grace_seconds() == session_mod.DEFAULT_IDLE_REAP_MINUTES * 60

    def bad_get(key, default=None, session=None):
        raise RuntimeError("db down")

    monkeypatch.setattr(session_mod.settings_repo, "get", bad_get)
    # Must fall back to the safe default, never raise into the reaper.
    assert session_mod._grace_seconds() == session_mod.DEFAULT_IDLE_REAP_MINUTES * 60

    def zero_get(key, default=None, session=None):
        return "0"

    monkeypatch.setattr(session_mod.settings_repo, "get", zero_get)
    assert session_mod._grace_seconds() == 0.0

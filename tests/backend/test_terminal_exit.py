"""Tests for the terminal EXIT control frame + zombie-session cleanup (T1).

Contract under test (documents/architecture/TSD.md §3.1, step 6):
when the shell dies — ``exit``, Ctrl-D, a crash, or a kill — the server sends
exactly ONE TEXT frame ``{"type":"exit","code":<int>}`` to the attached view
and closes the WebSocket (1000), then reclaims the session (registry entry +
``TerminalTab.pty_pid``) so no zombie is left behind.

Guards that matter most:
* the exit frame is a CONTROL message, never terminal output — it must not
  enter the replay ring buffer, or a reattaching client would see its JSON
  painted into the terminal;
* ``code`` is always an int (``-1`` when the status cannot be read);
* the reaper reaps an EXITED session even while a view is attached, but still
  never touches a LIVE session whose WS merely dropped (the safety property
  this module exists for).

All PTY-touching tests use a fake PTY by monkeypatching
``backend.terminal.session.spawn_shell`` — mirroring test_terminal_session.py.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time

import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient

import backend.terminal.session as session_mod
from backend.terminal.router import _pump, exit_frame
from backend.terminal.session import (
    EXIT_CODE_UNKNOWN,
    PtyExit,
    PtySession,
    _reader_loop,
    get_or_create,
    get_session,
    reap_idle,
    read_exit_code,
    snapshot_sessions,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
class ExitFakePty:
    """PTY double that can *die* like a real shell.

    ``read()`` pops the script, then — when ``exit_after_script`` is set —
    marks the process gone with that exit status and raises EOFError, exactly
    what a real pty does when the user types ``exit``. ``kill()`` models a
    signal death (status unreadable → the server must report -1).
    """

    def __init__(self, script=None, pid: int = 4242, exit_after_script=None) -> None:
        self._script = list(script) if script is not None else [b"hello-1\r\n"]
        self._exit_after = exit_after_script
        self.pid = pid
        self.alive = True
        self.killed = False
        self._exitstatus: int | None = None
        self.writes: list[bytes] = []
        self.resizes: list[tuple[int, int]] = []
        self._wake = threading.Event()

    @property
    def exit_status(self):
        """Mirrors ``PtyProcess.exit_status``: only set once the child is gone."""
        return None if self.alive else self._exitstatus

    def shell_exit(self, code: int = 0) -> None:
        """User typed ``exit`` / pressed Ctrl-D: process gone with a status."""
        self._exitstatus = code
        self.alive = False
        self._wake.set()

    def read(self, size: int = 65536) -> bytes:
        while True:
            if self._script:
                item = self._script.pop(0)
                if isinstance(item, BaseException):
                    raise item
                return item
            if self._exit_after is not None:
                code, self._exit_after = self._exit_after, None
                self.shell_exit(code)
            if not self.alive:
                raise EOFError("fake pty closed")
            self._wake.wait(0.02)

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    def set_winsize(self, cols: int, rows: int) -> None:
        self.resizes.append((cols, rows))

    def is_alive(self) -> bool:
        return self.alive

    def kill(self) -> None:
        self.killed = True
        self.alive = False
        self._exitstatus = None  # died from a signal: status not readable
        self._wake.set()


class _FakeView:
    """WebSocket view double: records sent frames + the close code."""

    def __init__(self) -> None:
        self.sent: list[str] = []
        self.close_code: int | None = None

    async def send_text(self, text: str) -> None:
        self.sent.append(text)

    async def close(self, code: int = 1000, reason=None) -> None:
        self.close_code = code


class _GoneView(_FakeView):
    """View whose sends always fail like a client that already disconnected."""

    async def send_text(self, text: str) -> None:
        raise WebSocketDisconnect(code=1006)


@pytest.fixture
def fake_spawn(monkeypatch: pytest.MonkeyPatch):
    """Patch ``spawn_shell``; record every fake PTY created."""
    created: list[ExitFakePty] = []

    def factory(cols: int = 80, rows: int = 24) -> ExitFakePty:
        pty = ExitFakePty()
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


def _recv_frame(ws, timeout: float = 10.0) -> str:
    """One bounded WS read.

    ``TestClient.receive_text()`` blocks forever when the expected frame never
    arrives, so a regression in the exit path would HANG the suite instead of
    failing it. Reading in a daemon thread with a join timeout turns that
    silence into a clear assertion failure.
    """
    box: list = []

    def _get() -> None:
        try:
            box.append(ws.receive_text())
        except BaseException as exc:  # noqa: BLE001 - re-raised in the caller
            box.append(exc)

    reader = threading.Thread(target=_get, daemon=True)
    reader.start()
    reader.join(timeout)
    if not box:
        raise AssertionError(f"terminal ws read timed out after {timeout}s")
    item = box[0]
    if isinstance(item, BaseException):
        raise item
    return item


def _recv_until(ws, needle: str, max_frames: int = 50) -> str:
    got = ""
    for _ in range(max_frames):
        try:
            got += _recv_frame(ws)
        except Exception:  # noqa: BLE001 - closed / drained before needle
            break
        if needle in got:
            break
    return got


def _recv_exit_frame(ws, max_frames: int = 50) -> dict:
    """Return the first frame that IS the exit control object.

    Each frame is JSON-parsed on its own: a frame only parses when it contains
    nothing but the control JSON, so this also proves the exit frame is not
    smuggled inside terminal text.
    """
    for _ in range(max_frames):
        text = _recv_frame(ws)  # raises if the server closed before the frame
        try:
            obj = json.loads(text)
        except ValueError:
            continue
        if isinstance(obj, dict) and obj.get("type") == "exit":
            return obj
    raise AssertionError("no exit control frame received")


async def _drain(queue: "asyncio.Queue") -> list:
    await asyncio.sleep(0.05)  # let run_coroutine_threadsafe deliveries land
    items: list = []
    while not queue.empty():
        items.append(queue.get_nowait())
    return items


# --------------------------------------------------------------------------- #
# 1) The frame shape is the frontend contract: {"type":"exit","code":<int>}
# --------------------------------------------------------------------------- #
def test_exit_frame_shape_and_int_coercion():
    assert json.loads(exit_frame(0)) == {"type": "exit", "code": 0}
    assert json.loads(exit_frame(2)) == {"type": "exit", "code": 2}
    assert json.loads(exit_frame(EXIT_CODE_UNKNOWN)) == {"type": "exit", "code": -1}
    # Always an int in the payload — never null, never a string.
    assert json.loads(exit_frame(1))["code"] == 1
    assert "null" not in exit_frame(EXIT_CODE_UNKNOWN)


def test_exit_code_unknown_when_status_unreadable():
    class _NoStatus:
        pass

    assert read_exit_code(_NoStatus()) == EXIT_CODE_UNKNOWN

    class _SignalDeath:
        exit_status = None  # ptyprocess: killed by a signal → exitstatus None

    assert read_exit_code(_SignalDeath()) == EXIT_CODE_UNKNOWN

    class _Raising:
        @property
        def exit_status(self):
            raise RuntimeError("backend blew up")

    assert read_exit_code(_Raising()) == EXIT_CODE_UNKNOWN

    class _Zero:
        exit_status = 0

    assert read_exit_code(_Zero()) == 0


# --------------------------------------------------------------------------- #
# 2) _pump: sentinel → exactly one exit frame → close(1000) → stop
# --------------------------------------------------------------------------- #
async def test_pump_sends_one_exit_frame_then_closes():
    ws = _FakeView()
    queue: "asyncio.Queue" = asyncio.Queue()
    await queue.put(b"output-line\r\n")
    await queue.put(PtyExit(3))
    await queue.put(PtyExit(4))  # defensive: a second sentinel must be ignored

    await asyncio.wait_for(_pump(ws, queue, tab_key="p1"), timeout=2)

    assert ws.sent[0] == "output-line\r\n"
    assert json.loads(ws.sent[1]) == {"type": "exit", "code": 3}
    assert len(ws.sent) == 2  # the output chunk + ONE exit frame only
    assert ws.close_code == 1000
    # The sentinel object itself was never written to the wire.
    assert not any("PtyExit" in frame for frame in ws.sent)


async def test_pump_closes_socket_even_when_exit_frame_cannot_be_sent():
    """A half-open client must still get its socket closed: no zombie tab."""
    ws = _GoneView()
    queue: "asyncio.Queue" = asyncio.Queue()
    await queue.put(PtyExit(0))

    await asyncio.wait_for(_pump(ws, queue, tab_key="p2"), timeout=2)

    assert ws.sent == []
    assert ws.close_code == 1000


# --------------------------------------------------------------------------- #
# 3) notify_exit: once per view, int code, never in the ring buffer
# --------------------------------------------------------------------------- #
async def test_notify_exit_delivers_exactly_one_sentinel_with_real_code():
    pty = ExitFakePty(script=[])
    sess = PtySession(tab_key="n1", pty=pty, cols=80, rows=24)
    replay, queue = sess.attach(_FakeView(), asyncio.get_running_loop())
    assert replay == []

    pty.shell_exit(5)
    assert sess.notify_exit() is True
    assert sess.notify_exit() is False  # the same view is never told twice

    items = await _drain(queue)
    assert len(items) == 1
    assert isinstance(items[0], PtyExit)
    assert items[0].code == 5
    # Ring buffer untouched: the control frame can never be replayed as text.
    assert list(sess.ring) == []


async def test_notify_exit_code_falls_back_to_minus_one_on_signal_death():
    pty = ExitFakePty(script=[])
    sess = PtySession(tab_key="n2", pty=pty, cols=80, rows=24)
    _, queue = sess.attach(_FakeView(), asyncio.get_running_loop())
    pty.kill()  # died from a signal → exitstatus None

    assert sess.notify_exit() is True
    items = await _drain(queue)
    assert items[0].code == EXIT_CODE_UNKNOWN


async def test_notify_exit_is_noop_when_detached():
    sess = PtySession(tab_key="n3", pty=ExitFakePty(script=[]), cols=80, rows=24)
    assert sess.notify_exit() is False  # nothing attached, nothing to tell
    assert sess.exited is True  # but the session is still marked dead


async def test_attach_to_already_exited_session_seeds_sentinel():
    """A view that attaches to a dead shell must be told, not left hanging."""
    pty = ExitFakePty(script=[b"last-output\r\n"], exit_after_script=2)
    sess = PtySession(tab_key="n4", pty=pty, cols=80, rows=24)
    await asyncio.get_running_loop().run_in_executor(None, _reader_loop, sess)
    assert sess.exited is True and sess.exit_code == 2

    _, queue = sess.attach(_FakeView(), asyncio.get_running_loop())
    items = await _drain(queue)
    assert [type(i) for i in items] == [PtyExit]
    assert items[0].code == 2
    # Reattaching a second time re-seeds (per-view), and the replay is clean.
    replay, queue2 = sess.attach(_FakeView(), asyncio.get_running_loop())
    assert replay == [b"last-output\r\n"]
    assert all(b'"exit"' not in chunk for chunk in replay)
    items2 = await _drain(queue2)
    assert len(items2) == 1


# --------------------------------------------------------------------------- #
# 4) Reader thread: exit detection notifies the attached view, ring stays clean
# --------------------------------------------------------------------------- #
async def test_reader_loop_notifies_attached_view_and_keeps_ring_clean():
    pty = ExitFakePty(script=[b"line-1\r\n", b"line-2\r\n"], exit_after_script=0)
    sess = PtySession(tab_key="r1", pty=pty, cols=80, rows=24)
    ws = _FakeView()
    _, queue = sess.attach(ws, asyncio.get_running_loop())

    await asyncio.get_running_loop().run_in_executor(None, _reader_loop, sess)

    assert sess.exited is True
    assert sess.exit_code == 0
    # Output streamed live; the death notice rides the same queue as a sentinel.
    items = await _drain(queue)
    assert sum(isinstance(i, PtyExit) for i in items) == 1
    # Replay buffer holds ONLY terminal bytes — no exit frame, no sentinel.
    assert list(sess.ring) == [b"line-1\r\n", b"line-2\r\n"]
    assert all(isinstance(chunk, bytes) for chunk in sess.ring)
    assert not any(b'"exit"' in chunk or b"type" in chunk for chunk in sess.ring)


# --------------------------------------------------------------------------- #
# 4b) Churn guard: reattaching while output streams must never hand one chunk to
#     the SAME view twice (replayed AND streamed live). The atomicity that
#     guarantees it is structural — the ring append and the queue capture happen
#     under one lock in ``_publish`` — so this is a stress check of the user
#     visible invariant, not a proof (the 2-bytecode window cannot be hit
#     reliably from a test).
# --------------------------------------------------------------------------- #
async def test_reattach_during_output_never_duplicates_a_chunk():
    loop = asyncio.get_running_loop()
    sess = PtySession(tab_key="d1", pty=ExitFakePty(script=[]), cols=80, rows=24)
    views: list[tuple[list[bytes], "asyncio.Queue"]] = []

    def publish_all() -> None:
        for i in range(400):
            sess._publish(f"c{i}\r\n".encode())
            time.sleep(0.0005)  # keep the churn alive long enough to interleave

    publisher = threading.Thread(target=publish_all)
    publisher.start()
    try:
        for _ in range(60):
            replay, queue = sess.attach(_FakeView(), loop)
            views.append((replay, queue))
            await asyncio.sleep(0.005)
    finally:
        publisher.join()
    await asyncio.sleep(0.1)  # let scheduled deliveries land

    assert len(views) == 60, "expected reattaches to interleave with the output"
    for replay, queue in views:
        live = []
        while not queue.empty():
            item = queue.get_nowait()
            if isinstance(item, bytes):
                live.append(item)
        overlap = set(replay) & set(live)
        assert not overlap, f"chunk delivered twice: {sorted(overlap)[:3]}"


# --------------------------------------------------------------------------- #
# 5) Reaper: exited-but-attached IS reapable; live-but-detached is NOT
# --------------------------------------------------------------------------- #
def test_try_reap_exited_but_attached_is_reapable():
    now = time.monotonic()
    grace = 3600.0
    pty = ExitFakePty(script=[])
    sess = PtySession(tab_key="21", pty=pty, cols=80, rows=24)
    sess.attach(object(), None)  # type: ignore[arg-type]  # a view is watching
    sess.exited = True

    assert sess.try_reap(now, grace) is True
    assert get_session("21") is None


def test_try_reap_never_touches_live_detached_session():
    """REGRESSION GUARD: a dropped WS (frozen tab) must not kill a running job."""
    now = time.monotonic()
    grace = 3600.0
    pty = ExitFakePty(script=[])
    sess = PtySession(tab_key="22", pty=pty, cols=80, rows=24)
    sess.last_output_ts = now - 10
    assert sess.try_reap(now, grace) is False
    assert pty.alive is True and pty.killed is False
    # ... and a LIVE session with an attached view is not reaped either.
    sess.attach(object(), None)  # type: ignore[arg-type]
    assert sess.try_reap(now, grace) is False
    assert pty.alive is True


async def test_reaper_reclaims_exited_but_attached_and_closes_view(fake_spawn):
    """End of the zombie: exited session + attached view → killed, unregistered,
    registry entry + tab pid cleared, and the stale view's socket closed."""
    from backend.config.db import SessionLocal
    from backend.models import TerminalTab

    key = "reap-attached-1"
    sess = get_or_create(key, create_tab=lambda: _make_tab())
    db_tab = sess.db_tab_id
    assert db_tab is not None
    ws = _FakeView()
    sess.attach(ws, asyncio.get_running_loop())

    fake_spawn[0].shell_exit(0)
    assert _wait_until(lambda: sess.exited)

    reaped = await asyncio.get_running_loop().run_in_executor(None, reap_idle)
    assert key in reaped
    assert get_session(key) is None
    await asyncio.sleep(0.05)  # the close was scheduled onto the loop
    assert ws.close_code == 1000
    with SessionLocal() as s:
        assert s.get(TerminalTab, db_tab).pty_pid == ""


def _make_tab() -> int:
    from backend.terminal.router import _create_tab

    return _create_tab()


# --------------------------------------------------------------------------- #
# 6) End-to-end over the WebSocket: frame → close → session reclaimed
# --------------------------------------------------------------------------- #
def test_ws_exit_frame_closes_socket_and_reclaims_session(client, fake_spawn):
    from backend.config.db import SessionLocal
    from backend.models import TerminalTab

    key = "exit-e2e-1"
    with TestClient(client.app) as c:
        with c.websocket_connect(f"/ws/terminal/{key}") as ws:
            assert "hello-1" in _recv_until(ws, "hello-1")
            sess = get_session(key)
            assert sess is not None
            db_tab = sess.db_tab_id
            with SessionLocal() as s:
                assert s.get(TerminalTab, db_tab).pty_pid == str(fake_spawn[0].pid)

            fake_spawn[0].shell_exit(0)  # the user typed `exit`

            frame = _recv_exit_frame(ws)
            assert frame == {"type": "exit", "code": 0}
            # ... and the server closed the socket right after the frame.
            with pytest.raises(WebSocketDisconnect):
                _recv_frame(ws)

        assert _wait_until(lambda: get_session(key) is None)
        # The exit frame never entered the replay buffer of the dead session.
        assert all(isinstance(chunk, bytes) for chunk in sess.ring)
        assert not any(b'"exit"' in chunk for chunk in sess.ring)
        with SessionLocal() as s:
            assert s.get(TerminalTab, db_tab).pty_pid == ""


def test_exit_frame_not_replayed_to_a_new_tab(client, fake_spawn):
    """Reopening the tab spawns a fresh shell whose replay has no exit JSON."""
    key = "exit-e2e-2"
    with TestClient(client.app) as c:
        with c.websocket_connect(f"/ws/terminal/{key}") as ws:
            _recv_until(ws, "hello-1")
            fake_spawn[0].shell_exit(0)
            assert _recv_exit_frame(ws) == {"type": "exit", "code": 0}
        assert _wait_until(lambda: get_session(key) is None)

        with c.websocket_connect(f"/ws/terminal/{key}") as ws2:
            got = _recv_until(ws2, "hello-1")
        assert "hello-1" in got
        assert '"exit"' not in got and "PtyExit" not in got
        assert len(fake_spawn) == 2  # a genuinely fresh shell, not the dead one
    fake_spawn[1].shell_exit(0)


def test_ws_kill_path_also_notifies_attached_view(client, fake_spawn):
    """``kill`` of a live shell (reaper/grace path) still tells the client.

    Driven directly through the reclaim path so the exit frame is checked for a
    PTY that dies while a real WS view is attached.
    """
    key = "exit-e2e-3"
    with TestClient(client.app) as c:
        with c.websocket_connect(f"/ws/terminal/{key}") as ws:
            _recv_until(ws, "hello-1")
            sess = get_session(key)
            assert sess is not None
            fake_spawn[0].kill()  # shell vanished (crash / OOM kill)
            assert _wait_until(lambda: sess.exited)
            frame = _recv_exit_frame(ws)
            assert frame["type"] == "exit"
            assert frame["code"] == EXIT_CODE_UNKNOWN  # signal death: unreadable
        assert _wait_until(lambda: get_session(key) is None)


def test_ws_deliberate_close_still_kills_and_cleans(client, fake_spawn):
    """The pre-existing ``{"type":"close"}`` path must not regress."""
    key = "exit-e2e-4"
    with TestClient(client.app) as c:
        with c.websocket_connect(f"/ws/terminal/{key}") as ws:
            ws.send_text('{"type":"close"}')
            try:
                while True:
                    _recv_frame(ws)
            except Exception:  # noqa: BLE001 - server closed the socket
                pass
        assert fake_spawn[0].killed is True
        assert get_session(key) is None


# --------------------------------------------------------------------------- #
# 7) REAL-PTY integration: the exact runtime path the mock tests cannot prove.
#    Spawns an actual shell (no ``spawn_shell`` monkeypatch), drives it over a
#    real WebSocket, types ``exit``, and asserts the ``{"type":"exit","code":N}``
#    frame + server close actually reach the client. This is the regression that
#    the fake-PTY unit tests share a queue with the reader and therefore cannot
#    catch: it exercises ptyprocess EOF/exit-status + the reader thread + the
#    router pump end to end, exactly as a browser tab does.
# --------------------------------------------------------------------------- #
_REAL_PTY_REASON = None
try:  # pragma: no cover - platform dependent
    import shutil as _shutil

    if os.name != "posix" or _shutil.which("bash") is None:
        _REAL_PTY_REASON = "needs a POSIX shell (bash)"
    import ptyprocess as _ptyprocess  # noqa: F401
except Exception:  # noqa: BLE001 - missing native dep → skip, not fail
    _REAL_PTY_REASON = "ptyprocess/bash unavailable"


@pytest.mark.skipif(_REAL_PTY_REASON is not None, reason=_REAL_PTY_REASON or "")
def test_real_shell_exit_sends_frame_and_closes_ws(client):
    """Type ``exit`` into a REAL shell over a REAL WS → exit frame + close(1000)."""
    key = "real-pty-exit-1"
    with TestClient(client.app) as c:
        with c.websocket_connect(f"/ws/terminal/{key}") as ws:
            # The handler spawns the real shell on the portal thread; wait for
            # the registry entry (and a live pid) before driving it.
            assert _wait_until(lambda: get_session(key) is not None)
            sess = get_session(key)
            assert sess is not None and sess.pty.pid is not None
            ws.send_text("exit\r")  # the user types `exit` + Enter
            frame = _recv_exit_frame(ws)  # skips banner/prompt bytes
            assert frame["type"] == "exit"
            assert isinstance(frame["code"], int)
            assert frame["code"] == 0  # clean shell exit
            # The server closes the socket right after the frame (no zombie tab).
            with pytest.raises(Exception):  # noqa: BLE001 - WebSocketDisconnect
                _recv_frame(ws, timeout=5)
        assert _wait_until(lambda: get_session(key) is None)

"""Tests for the terminal WebSocket application-level HEARTBEAT (be-dev).

Covers the keepalive added on top of uvicorn's protocol-level ws_ping:

* **Launcher tuning** — ``uvicorn.run`` is called with
  ``ws_ping_interval=15.0, ws_ping_timeout=15.0`` (host/port logic unchanged).
* **Control-frame classification** — an inbound ``{"type":"pong"}`` (and any
  unknown ``{"type":"foo"}`` / client ``ping``) is a CONTROL frame and is NEVER
  written to the PTY; only non-JSON text is a keystroke.
* **Heartbeat emission** — the per-connection ``_heartbeat_loop`` task emits
  ``{"type":"ping","t":<unix_seconds>}`` frames while attached (driven with a
  fake websocket + a short interval).
* **Conservative stale handling** — a view that ponged then went silent past
  the timeout is DETACHED (PTY kept alive), never killed.

All PTY-touching tests use a fake PTY (no real shell) by monkeypatching
``backend.terminal.session.spawn_shell`` — mirroring test_terminal_session.py.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import sys
import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketState

import backend.terminal.session as session_mod
from backend.terminal.router import (
    INBOUND_CLOSE,
    INBOUND_CONTROL,
    INBOUND_KEYSTROKE,
    _classify_inbound,
    _heartbeat_loop,
    _is_disconnect_error,
)
from backend.terminal.session import PtySession, snapshot_sessions


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
class _NullPty:
    """Bare PTY double for PtySession lifecycle tests (no reader thread)."""

    def __init__(self) -> None:
        self.pid = 4242
        self.killed = False
        self.writes: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    def set_winsize(self, cols: int, rows: int) -> None:
        pass

    def is_alive(self) -> bool:
        return not self.killed

    def kill(self) -> None:
        self.killed = True


class _FakePty:
    """PTY double for the WS integration test: scripted reads then idle."""

    def __init__(self, script=None, pid: int = 4242) -> None:
        self._script = list(script) if script is not None else [b"hello-1\r\n"]
        self.pid = pid
        self.killed = False
        self.writes: list[bytes] = []
        self.resizes: list[tuple[int, int]] = []

    def read(self, size: int = 65536) -> bytes:
        if self._script:
            item = self._script.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item
        if self.killed:
            raise EOFError("fake pty closed")
        time.sleep(0.02)
        return b""

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    def set_winsize(self, cols: int, rows: int) -> None:
        self.resizes.append((cols, rows))

    def is_alive(self) -> bool:
        return not self.killed

    def kill(self) -> None:
        self.killed = True


class _CaptureWS:
    """Minimal websocket double capturing sends + close for heartbeat tests."""

    def __init__(self) -> None:
        self.sent: list[str] = []
        self.closed = False
        self.client_state = WebSocketState.CONNECTED

    async def send_text(self, text: str) -> None:
        self.sent.append(text)

    async def close(self, *args, **kwargs) -> None:
        self.closed = True


class _SpySession:
    """Records which PTY-facing ops the classifier triggers."""

    def __init__(self) -> None:
        self.writes: list[str] = []
        self.resizes: list[tuple[int, int]] = []
        self.pongs = 0

    def write_text(self, text: str) -> None:
        self.writes.append(text)

    def resize(self, cols: int, rows: int) -> None:
        self.resizes.append((cols, rows))

    def record_pong(self) -> None:
        self.pongs += 1


@pytest.fixture
def fake_spawn(monkeypatch: pytest.MonkeyPatch):
    """Patch ``spawn_shell``; record every fake PTY created."""
    created: list[_FakePty] = []

    def factory(cols: int = 80, rows: int = 24) -> _FakePty:
        pty = _FakePty()
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
# 1) Launcher keepalive tuning
# --------------------------------------------------------------------------- #
def test_launcher_passes_ws_ping_keepalive(monkeypatch):
    import uvicorn

    import backend.launcher as launcher

    captured: dict = {}

    def fake_run(app, **kwargs) -> None:
        captured["app"] = app
        captured.update(kwargs)

    monkeypatch.setattr(uvicorn, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["launcher"])
    monkeypatch.delenv("AIGATE_PORT", raising=False)

    launcher.main()

    assert captured["ws_ping_interval"] == 15.0
    assert captured["ws_ping_timeout"] == 15.0
    # host/port logic unchanged.
    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 8080
    assert captured["app"] is not None


def test_launcher_keepalive_does_not_break_port_override(monkeypatch):
    import uvicorn

    import backend.launcher as launcher

    captured: dict = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: captured.update(kw))
    monkeypatch.setattr(sys, "argv", ["launcher", "--port", "9999"])

    launcher.main()

    assert captured["port"] == 9999
    assert captured["ws_ping_interval"] == 15.0
    assert captured["ws_ping_timeout"] == 15.0


# --------------------------------------------------------------------------- #
# 2) Control-frame classification: pong/unknown/ping are NEVER keystrokes
# --------------------------------------------------------------------------- #
def test_classify_pong_is_control_not_keystroke():
    spy = _SpySession()
    assert _classify_inbound('{"type":"pong"}', spy, "k") == INBOUND_CONTROL
    assert spy.writes == []  # never written to the PTY
    assert spy.pongs == 1  # liveness recorded


def test_classify_unknown_control_type_is_ignored_not_keystroke():
    spy = _SpySession()
    assert _classify_inbound('{"type":"foo"}', spy, "k") == INBOUND_CONTROL
    assert spy.writes == []


def test_classify_client_ping_is_ignored_not_keystroke():
    spy = _SpySession()
    assert _classify_inbound('{"type":"ping"}', spy, "k") == INBOUND_CONTROL
    assert spy.writes == []


def test_classify_resize_and_close_still_work():
    spy = _SpySession()
    assert (
        _classify_inbound('{"type":"resize","cols":10,"rows":5}', spy, "k")
        == INBOUND_CONTROL
    )
    assert spy.resizes == [(10, 5)]
    assert spy.writes == []
    assert _classify_inbound('{"type":"close"}', spy, "k") == INBOUND_CLOSE
    assert spy.writes == []


def test_classify_plain_and_edge_text_is_keystroke():
    spy = _SpySession()
    # Real keystrokes / pasted text.
    assert _classify_inbound("ls\r", spy, "k") == INBOUND_KEYSTROKE
    # A lone brace the user typed (invalid JSON) → keystroke, not swallowed.
    assert _classify_inbound("{not json", spy, "k") == INBOUND_KEYSTROKE
    # JSON that is not a control object (no 'type' key) → keystroke.
    assert _classify_inbound('{"no_type":1}', spy, "k") == INBOUND_KEYSTROKE
    # A JSON array → keystroke.
    assert _classify_inbound("[1,2,3]", spy, "k") == INBOUND_KEYSTROKE
    # The classifier itself never writes; the handler does, on KEYSTROKE only.
    assert spy.writes == []


def test_ws_control_frames_never_reach_the_shell(client, fake_spawn):
    """End-to-end: pong/unknown/ping over the wire must NOT hit the PTY."""
    uuid_tab = "hb-e2e-tab-0001"
    with TestClient(client.app) as c:
        with c.websocket_connect(f"/ws/terminal/{uuid_tab}") as ws:
            _recv_until(ws, "hello-1")  # attached + first output seen
            ws.send_text('{"type":"pong"}')
            ws.send_text('{"type":"foo"}')
            ws.send_text('{"type":"ping"}')
            # A real keystroke AFTER the controls: once it lands in the PTY we
            # know the earlier frames were already classified (same loop).
            ws.send_text("SENTINEL\r")
            pty = fake_spawn[0]
            assert _wait_until(lambda: b"SENTINEL\r" in pty.writes)

    joined = b"".join(pty.writes)
    assert b"SENTINEL\r" in pty.writes
    # No control frame content leaked into the shell.
    assert b'"type"' not in joined
    assert b"pong" not in joined
    assert b'"foo"' not in joined
    # SAFETY: leaving the WS only DETACHED the view; the PTY is still alive.
    assert pty.killed is False


# --------------------------------------------------------------------------- #
# 3) Heartbeat task emits ping frames while attached
# --------------------------------------------------------------------------- #
async def test_heartbeat_emits_ping_frames():
    ws = _CaptureWS()
    sess = PtySession(tab_key="hb1", pty=_NullPty(), cols=80, rows=24)
    sess.attach(ws, asyncio.get_running_loop())
    lock = asyncio.Lock()

    task = asyncio.create_task(
        _heartbeat_loop(ws, lock, sess, "hb1", interval=0.02, pong_timeout=1000.0)
    )
    await asyncio.sleep(0.12)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    assert ws.sent, "expected at least one heartbeat frame"
    for frame in ws.sent:
        obj = json.loads(frame)
        assert obj["type"] == "ping"
        assert isinstance(obj["t"], int)  # unix seconds
    # Not stale (client never ponged) → view stays attached, PTY untouched.
    assert sess.attached is ws
    assert sess.pty.killed is False


async def test_heartbeat_detaches_stale_view_but_keeps_pty_alive():
    ws = _CaptureWS()
    pty = _NullPty()
    sess = PtySession(tab_key="hb2", pty=pty, cols=80, rows=24)
    sess.attach(ws, asyncio.get_running_loop())
    sess.record_pong()  # client was alive once...
    sess.last_pong_ts = time.monotonic() - 1000  # ...then went silent

    lock = asyncio.Lock()
    task = asyncio.create_task(
        _heartbeat_loop(ws, lock, sess, "hb2", interval=0.02, pong_timeout=0.05)
    )
    # Async poll (must yield to the loop so the heartbeat task can run).
    detached = False
    for _ in range(200):
        if sess.attached is None:
            detached = True
            break
        await asyncio.sleep(0.01)
    assert detached
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    assert sess.attached is None  # stale view detached
    assert ws.closed is True  # socket closed so the client can reconnect
    assert pty.killed is False  # SAFETY: PTY NOT killed
    # A ping was emitted before the stale check fired.
    assert any(json.loads(f)["type"] == "ping" for f in ws.sent)


# --------------------------------------------------------------------------- #
# 4) Session heartbeat bookkeeping primitives
# --------------------------------------------------------------------------- #
def test_record_pong_and_heartbeat_stale_semantics():
    sess = PtySession(tab_key="hb3", pty=_NullPty(), cols=80, rows=24)
    ws = _CaptureWS()
    sess.attach(ws, None)  # type: ignore[arg-type]

    # No pong yet → never stale (a non-heartbeat client is not penalised).
    assert sess.last_pong_ts is None
    assert sess.heartbeat_stale(time.monotonic(), 60.0) is False

    # Fresh pong → not stale.
    sess.record_pong()
    assert sess.last_pong_ts is not None
    assert sess.heartbeat_stale(time.monotonic(), 60.0) is False

    # Ponged then went silent past the timeout → stale.
    sess.last_pong_ts = time.monotonic() - 120
    assert sess.heartbeat_stale(time.monotonic(), 60.0) is True

    # Detached → never stale (nothing to watch), even if last pong is old.
    sess.detach(ws)
    assert sess.heartbeat_stale(time.monotonic(), 60.0) is False


def test_attach_resets_last_pong_ts():
    sess = PtySession(tab_key="hb4", pty=_NullPty(), cols=80, rows=24)
    sess.attach(_CaptureWS(), None)  # type: ignore[arg-type]
    sess.record_pong()
    assert sess.last_pong_ts is not None
    # A reattach (new view) must clear the previous connection's pong state.
    sess.attach(_CaptureWS(), None)  # type: ignore[arg-type]
    assert sess.last_pong_ts is None


# --------------------------------------------------------------------------- #
# 5) Disconnect classification: transport teardown must NOT log as ERROR
# --------------------------------------------------------------------------- #
def test_is_disconnect_error_generic_valueerror_is_not_disconnect():
    """A real bug (ValueError) on a CONNECTED socket is NOT a disconnect."""
    ws = _CaptureWS()  # client_state == CONNECTED → not the state-based path
    assert _is_disconnect_error(ValueError("boom"), ws) is False


def test_is_disconnect_error_starlette_and_send_runtimeerror():
    """WebSocketDisconnect + starlette's send-after-close RuntimeError count."""
    from fastapi import WebSocketDisconnect

    ws = _CaptureWS()
    assert _is_disconnect_error(WebSocketDisconnect(), ws) is True
    assert (
        _is_disconnect_error(
            RuntimeError('Cannot call "send" once a close message has been sent.'),
            ws,
        )
        is True
    )
    # A DISCONNECTED client_state alone also means "client gone".
    gone = _CaptureWS()
    gone.client_state = WebSocketState.DISCONNECTED
    assert _is_disconnect_error(ValueError("whatever"), gone) is True


def test_is_disconnect_error_websockets_invalidstate_is_disconnect():
    """Regression: uvicorn's sansio impl raises ``InvalidState`` (NOT a
    ``ConnectionClosed`` subclass) when sending on a CONNECTING/CLOSING/CLOSED
    connection during normal teardown. It must classify as a disconnect (INFO,
    "client gone"), not an ERROR. Skips gracefully if websockets is absent."""
    websockets_exceptions = pytest.importorskip("websockets.exceptions")
    ws = _CaptureWS()  # CONNECTED → the True must come from the exception type
    exc = websockets_exceptions.InvalidState(
        "cannot send TEXT frame when connection state is CLOSING"
    )
    assert _is_disconnect_error(exc, ws) is True
    # Defensive: the base + concrete ConnectionClosed* also classify.
    assert _is_disconnect_error(websockets_exceptions.WebSocketException("x"), ws)
    assert _is_disconnect_error(websockets_exceptions.ConnectionClosedOK(None, None), ws)
    assert _is_disconnect_error(
        websockets_exceptions.ConnectionClosedError(None, None), ws
    )
    # A generic ValueError is STILL not a disconnect.
    assert _is_disconnect_error(ValueError("boom"), ws) is False

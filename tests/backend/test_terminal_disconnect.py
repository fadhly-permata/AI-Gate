"""Disconnect-classification tests for the terminal WS router (log-noise fix).

Guards the rule: a normal terminal close must log at INFO, never ERROR.

* ``_is_disconnect_error`` unit tests (WebSocketDisconnect, starlette
  send-after-close RuntimeError, websockets ConnectionClosed*, plain bugs).
* ``_pump`` behavior: disconnect-during-send → log_info, real error →
  log_error_exc (log fns monkeypatched on ``backend.terminal.router``).
* ``session._reader_loop`` behavior: EOF/OSError or shutdown-time read
  failure → log_info, unexpected reader error → log_error_exc. (The reader
  moved to ``backend.terminal.session`` when the PTY was decoupled from the
  WebSocket; it now feeds the session ring buffer instead of a per-WS queue.)
"""

from __future__ import annotations

import asyncio
import threading
from typing import Optional

import pytest
from fastapi import WebSocketDisconnect
from starlette.websockets import WebSocketState

import backend.terminal.router as router_mod
import backend.terminal.session as session_mod
from backend.terminal.router import _is_disconnect_error, _pump
from backend.terminal.session import PtySession

try:
    from websockets.exceptions import ConnectionClosed, ConnectionClosedError
    from websockets.frames import Close as WsClose

    _HAS_WEBSOCKETS = True
except ImportError:  # pragma: no cover - env without the websockets library
    _HAS_WEBSOCKETS = False


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
class _LogCapture:
    """Stand-in for a module's log_info / log_error_exc (default: router)."""

    def __init__(
        self, monkeypatch: pytest.MonkeyPatch, module: object = None
    ) -> None:
        self.infos: list[str] = []
        self.errors: list[str] = []
        target = module if module is not None else router_mod
        monkeypatch.setattr(target, "log_info", self._info)
        monkeypatch.setattr(target, "log_error_exc", self._error)

    def _info(self, message: str, source: Optional[str] = None, **kw) -> None:
        self.infos.append(message)

    def _error(self, message: str, source: Optional[str] = None, **kw) -> None:
        self.errors.append(message)


class _FakeWS:
    """Minimal websocket double: fixed client_state + scripted send_text."""

    def __init__(self, exc: Optional[BaseException], state=WebSocketState.CONNECTED):
        self._exc = exc
        self.client_state = state
        self.sent: list[str] = []

    async def send_text(self, text: str) -> None:
        if self._exc is not None:
            raise self._exc
        self.sent.append(text)


class _FakePty:
    """PTY double: yields scripted read() results, then stops being alive."""

    def __init__(self, reads):
        self._reads = list(reads)
        self.pid = 4242

    def read(self, size: int = 65536):
        if not self._reads:
            raise AssertionError("fake pty read() called too many times")
        item = self._reads.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    def is_alive(self) -> bool:
        return False

    def kill(self) -> None:
        pass


# --------------------------------------------------------------------------- #
# 1) _is_disconnect_error unit tests
# --------------------------------------------------------------------------- #
def test_disconnect_error_websocket_disconnect_is_true():
    assert _is_disconnect_error(WebSocketDisconnect(code=1006), _FakeWS(None)) is True


def test_disconnect_error_starlette_send_runtime_error_is_true():
    # Exact message raised by starlette 0.27 WebSocket.send after close.
    exc = RuntimeError('Cannot call "send" once a close message has been sent.')
    assert _is_disconnect_error(exc, _FakeWS(None)) is True


def test_disconnect_error_disconnected_runtime_error_is_true():
    exc = RuntimeError("Cannot call 'send' once disconnected from client")
    assert _is_disconnect_error(exc, _FakeWS(None)) is True


@pytest.mark.skipif(not _HAS_WEBSOCKETS, reason="websockets lib not installed")
def test_disconnect_error_connection_closed_is_true():
    exc = ConnectionClosedError(WsClose(1006, b""), None)
    assert _is_disconnect_error(exc, _FakeWS(None)) is True
    assert isinstance(exc, ConnectionClosed)  # sanity: base class match


def test_disconnect_error_plain_value_error_is_false():
    assert _is_disconnect_error(ValueError("boom"), _FakeWS(None)) is False


def test_disconnect_error_unrelated_runtime_error_is_false():
    exc = RuntimeError("bad config value somewhere")
    assert _is_disconnect_error(exc, _FakeWS(None)) is False


def test_disconnect_error_disconnected_client_state_wins():
    # Any exception counts as disconnect once the ws is already DISCONNECTED.
    ws = _FakeWS(None, state=WebSocketState.DISCONNECTED)
    assert _is_disconnect_error(ValueError("boom"), ws) is True


def test_disconnect_error_none_websocket_is_false():
    assert _is_disconnect_error(ValueError("boom"), None) is False


# --------------------------------------------------------------------------- #
# 2) _pump: disconnect during send → INFO, real error → ERROR
# --------------------------------------------------------------------------- #
async def _run_pump_with_one_item(ws: _FakeWS) -> None:
    queue: "asyncio.Queue[bytes]" = asyncio.Queue()
    await queue.put(b"hello")
    # _pump loops forever on an empty queue; bound it with a timeout after the
    # first item is processed (it breaks out of the loop on send failure).
    await asyncio.wait_for(_pump(ws, queue, tid=7), timeout=2)


def test_pump_websocket_disconnect_logs_info_not_error(monkeypatch):
    logs = _LogCapture(monkeypatch)
    ws = _FakeWS(WebSocketDisconnect(code=1006))
    asyncio.run(_run_pump_with_one_item(ws))
    assert logs.errors == []
    assert any("client gone during send" in m for m in logs.infos)


def test_pump_starlette_runtime_error_logs_info_not_error(monkeypatch):
    logs = _LogCapture(monkeypatch)
    ws = _FakeWS(RuntimeError('Cannot call "send" once a close message has been sent.'))
    asyncio.run(_run_pump_with_one_item(ws))
    assert logs.errors == []
    assert any("client gone during send" in m for m in logs.infos)


@pytest.mark.skipif(not _HAS_WEBSOCKETS, reason="websockets lib not installed")
def test_pump_connection_closed_logs_info_not_error(monkeypatch):
    logs = _LogCapture(monkeypatch)
    ws = _FakeWS(ConnectionClosedError(WsClose(1006, b""), None))
    asyncio.run(_run_pump_with_one_item(ws))
    assert logs.errors == []
    assert any("client gone during send" in m for m in logs.infos)


def test_pump_real_error_still_logs_error(monkeypatch):
    logs = _LogCapture(monkeypatch)
    ws = _FakeWS(ValueError("boom"))
    asyncio.run(_run_pump_with_one_item(ws))
    assert logs.infos == []
    assert any("terminal send error" in m for m in logs.errors)


def test_pump_happy_path_sends_and_stays_silent(monkeypatch):
    logs = _LogCapture(monkeypatch)
    ws = _FakeWS(None)
    queue: "asyncio.Queue[bytes]" = asyncio.Queue()

    async def run() -> None:
        await queue.put(b"hi")
        task = asyncio.create_task(_pump(ws, queue, tid=1))
        for _ in range(100):
            if ws.sent:
                break
            await asyncio.sleep(0.01)
        task.cancel()

    asyncio.run(run())
    assert ws.sent == ["hi"]
    assert logs.infos == []
    assert logs.errors == []


# --------------------------------------------------------------------------- #
# 3) session._reader_loop: EOF/OSError/shutdown → INFO, unexpected → ERROR
# --------------------------------------------------------------------------- #
def _make_session(pty: "_FakePty") -> PtySession:
    """A bare PtySession (no thread, no registry) for reader-loop tests."""
    return PtySession(tab_id=1, pty=pty, cols=80, rows=24)


def test_reader_eof_logs_info_not_error(monkeypatch):
    logs = _LogCapture(monkeypatch, session_mod)
    sess = _make_session(_FakePty([EOFError("read of closed file")]))
    session_mod._reader_loop(sess)
    assert logs.errors == []
    assert any("reader stopped" in m for m in logs.infos)
    # pty dead → session marked exited (kept in registry; reaper cleans up).
    assert sess.exited is True


def test_reader_oserror_logs_info_not_error(monkeypatch):
    logs = _LogCapture(monkeypatch, session_mod)
    sess = _make_session(_FakePty([OSError(5, "Input/output error")]))
    session_mod._reader_loop(sess)
    assert logs.errors == []
    assert any("reader stopped" in m for m in logs.infos)


def test_reader_shutdown_time_error_logs_info_not_error(monkeypatch):
    logs = _LogCapture(monkeypatch, session_mod)

    class _StopThenRaisePty(_FakePty):
        def __init__(self, stop: threading.Event):
            super().__init__([])
            self._stop = stop

        def read(self, size: int = 65536):
            self._stop.set()  # shutdown began while blocked in read()
            raise RuntimeError("pty blew up mid-kill")

    pty = _StopThenRaisePty(threading.Event())
    sess = _make_session(pty)
    pty._stop = sess.stop_event
    session_mod._reader_loop(sess)
    assert logs.errors == []
    assert any("reader stopped" in m for m in logs.infos)


def test_reader_unexpected_error_still_logs_error(monkeypatch):
    logs = _LogCapture(monkeypatch, session_mod)
    sess = _make_session(_FakePty([ValueError("genuinely unexpected")]))
    session_mod._reader_loop(sess)
    assert any("terminal reader error" in m for m in logs.errors)
    # The read failure itself must be ERROR, never the INFO shutdown path.
    assert not any("reader stopped" in m for m in logs.infos)


def test_reader_feeds_ring_buffer_then_stops_on_eof(monkeypatch):
    """Happy path: data lands in the session ring buffer (detached → no live
    queue); EOF is INFO, not ERROR."""
    logs = _LogCapture(monkeypatch, session_mod)
    sess = _make_session(_FakePty([b"chunk-1", EOFError("pty closed")]))
    session_mod._reader_loop(sess)
    assert list(sess.ring) == [b"chunk-1"]
    assert sess.exited is True
    assert logs.errors == []
    assert any("reader stopped" in m for m in logs.infos)

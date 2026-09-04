"""WebSocket terminal endpoint (task B3.2).

Endpoint
--------
``WS /ws/terminal/{tab_id}``

tab_id resolution
-----------------
* ``tab_id`` is a valid existing :class:`TerminalTab` id (int > 0) → reuse it.
* Anything else (``0``, non-numeric, or unknown id) → create a fresh
  :class:`TerminalSession` + :class:`TerminalTab` and use its new id.

Message protocol (for frontend B3.3)
------------------------------------
* **Server → client**: terminal output as TEXT frames (UTF-8 decoded bytes).
* **Client → server (keystrokes)**: raw TEXT frames are written verbatim to
  the PTY (keystrokes / pasted text).
* **Client → server (control)**: a TEXT frame that is JSON
  ``{"type":"resize","cols":<int>,"rows":<int>}`` is treated as a resize
  command and is NOT written to the PTY. Any other JSON / text is treated as
  raw input (forwarded to the shell).

Concurrency model
-----------------
PTY reads are blocking. A dedicated **daemon thread** calls
``PtyProcess.read()`` and pushes decoded bytes into an ``asyncio.Queue`` via
``asyncio.run_coroutine_threadsafe``. The async side awaits the queue and
``send_text``\\ s to the client. Writes come from ``websocket.iter_text()`` on
the event loop. On disconnect (or process exit) the PTY is killed, the tab's
``pty_pid`` is cleared, and everything is logged (ADR-011).
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from backend.config.db import SessionLocal
from backend.log import log_error_exc, log_info
from backend.models import TerminalSession, TerminalTab
from backend.terminal.pty import PtyError, PtyProcess, spawn_shell

LOG_SOURCE = "backend.terminal.router"

router = APIRouter()

# ``websockets`` is an optional runtime dep (uvicorn's default WS impl). When
# absent (e.g. wsproto) the disconnect-type tuple simply omits its exception.
try:
    from websockets.exceptions import ConnectionClosed as _WsConnectionClosed
except ImportError:  # pragma: no cover - env without the websockets library
    _WsConnectionClosed = None

# Exception types that mean "the client/transport went away", not a real bug.
_DISCONNECT_EXC_TYPES: "tuple[type[BaseException], ...]" = (WebSocketDisconnect,)
if _WsConnectionClosed is not None:  # pragma: no cover - depends on env
    _DISCONNECT_EXC_TYPES += (_WsConnectionClosed,)


def _is_disconnect_error(exc: BaseException, websocket: Optional[WebSocket]) -> bool:
    """True if ``exc`` means the WS client disconnected, not a real send failure.

    An abrupt client close surfaces in several shapes, none of which is an
    application error:

    * :class:`WebSocketDisconnect` — starlette/fastapi saw the disconnect.
    * ``websockets.exceptions.ConnectionClosed*`` — raised by uvicorn's
      websockets implementation at the transport layer.
    * starlette's ``RuntimeError('Cannot call "send" once a close message
      has been sent.')`` — raised when the app tries to send after the
      connection state already moved past CONNECTED.
    * Any exception while ``websocket.client_state`` is already DISCONNECTED.
    """
    if isinstance(exc, _DISCONNECT_EXC_TYPES):
        return True
    if (
        websocket is not None
        and getattr(websocket, "client_state", None) == WebSocketState.DISCONNECTED
    ):
        return True
    if isinstance(exc, RuntimeError):
        msg = str(exc).lower()
        if "send" in msg and ("close message" in msg or "disconnected" in msg):
            return True
    return False


# --------------------------------------------------------------------------- #
# DB helpers (own short-lived sessions; never leak connections)
# --------------------------------------------------------------------------- #
def _resolve_tab_id(raw: str) -> int:
    """Return an existing tab id or create a new session+tab and return its id."""
    try:
        tid = int(raw)
    except (TypeError, ValueError):
        tid = 0
    if tid > 0:
        with SessionLocal() as s:
            if s.get(TerminalTab, tid) is not None:
                return tid
    return _create_tab()


def _create_tab() -> int:
    shell = "powershell" if os.name == "nt" else "bash"
    with SessionLocal() as s:
        ts = TerminalSession(session_name="default")
        s.add(ts)
        s.flush()
        tab = TerminalTab(session_id=ts.id, title="", shell_type=shell)
        s.add(tab)
        s.commit()
        s.refresh(tab)
        return tab.id


def _update_tab_pid(tid: int, pid: str) -> None:
    try:
        with SessionLocal() as s:
            tab = s.get(TerminalTab, tid)
            if tab is not None:
                tab.pty_pid = pid
                s.commit()
    except Exception as exc:  # noqa: BLE001 - best-effort bookkeeping
        log_error_exc(
            f"terminal: update tab pid failed tab={tid}", source=LOG_SOURCE, exc=exc
        )


def _reader_loop(
    pty: PtyProcess,
    queue: "asyncio.Queue[bytes]",
    loop: asyncio.AbstractEventLoop,
    stop_event: threading.Event,
) -> None:
    """Blocking reader: feeds decoded PTY output into the async queue.

    Runs as a daemon thread. A read failure during shutdown (``stop_event``
    set) or an EOF/OSError from the killed PTY is expected teardown → INFO,
    not ERROR. Only genuinely unexpected reads while still running are
    logged as errors.
    """
    while not stop_event.is_set():
        try:
            data = pty.read()
        except Exception as exc:  # noqa: BLE001 - classified below
            if stop_event.is_set() or isinstance(exc, (EOFError, OSError)):
                # Normal shutdown: pty.kill()/close makes read() raise EOF/OSError.
                log_info(
                    f"terminal reader stopped during shutdown: {exc!r}",
                    source=LOG_SOURCE,
                )
            else:
                log_error_exc("terminal reader error", source=LOG_SOURCE, exc=exc)
            break
        if not data and not pty.is_alive():
            break  # EOF + dead → done
        if not data:
            continue  # transient empty read
        asyncio.run_coroutine_threadsafe(queue.put(data), loop)


async def _pump(
    websocket: WebSocket, queue: "asyncio.Queue[bytes]", tid: int
) -> None:
    """Async side: drain the queue and send frames to the client.

    A send failure caused by the client going away (disconnect) is normal
    teardown → INFO; only unexpected send errors are logged as ERROR.
    """
    while True:
        data = await queue.get()
        try:
            await websocket.send_text(data.decode("utf-8", "replace"))
        except Exception as exc:  # noqa: BLE001 - classified below
            if _is_disconnect_error(exc, websocket):
                log_info(
                    f"terminal ws client gone during send tab={tid}",
                    source=LOG_SOURCE,
                )
            else:
                log_error_exc("terminal send error", source=LOG_SOURCE, exc=exc)
            break


# --------------------------------------------------------------------------- #
# WebSocket endpoint
# --------------------------------------------------------------------------- #
@router.websocket("/ws/terminal/{tab_id}")
async def terminal_ws(websocket: WebSocket, tab_id: str) -> None:
    await websocket.accept()
    log_info(f"terminal ws connect tab_id={tab_id}", source=LOG_SOURCE)

    tid = _resolve_tab_id(tab_id)

    # Spawn the shell. On failure, log and close gracefully.
    try:
        pty = spawn_shell()
    except PtyError as exc:
        log_error_exc(
            f"terminal ws spawn failed tab={tid}: {exc}", source=LOG_SOURCE, exc=exc
        )
        await websocket.close(code=1011)
        return

    _update_tab_pid(tid, str(pty.pid))
    log_info(f"terminal ws spawned pid={pty.pid} tab={tid}", source=LOG_SOURCE)

    loop = asyncio.get_running_loop()
    queue: "asyncio.Queue[bytes]" = asyncio.Queue()
    stop_event = threading.Event()

    reader = threading.Thread(
        target=_reader_loop, args=(pty, queue, loop, stop_event), daemon=True
    )
    reader.start()

    pump_task = asyncio.create_task(_pump(websocket, queue, tid))

    try:
        async for msg in websocket.iter_text():
            # Control frame? JSON {"type":"resize",...} → resize, not keystroke.
            if msg.startswith("{"):
                try:
                    obj = json.loads(msg)
                    if isinstance(obj, dict) and obj.get("type") == "resize":
                        cols = int(obj.get("cols", 80))
                        rows = int(obj.get("rows", 24))
                        pty.set_winsize(cols, rows)
                        continue
                except (ValueError, json.JSONDecodeError) as exc:
                    log_info(
                        f"terminal: non-JSON control frame ignored: {exc}",
                        source=LOG_SOURCE,
                    )
            pty.write(msg.encode("utf-8"))
    except WebSocketDisconnect:
        log_info(f"terminal ws client disconnected tab={tid}", source=LOG_SOURCE)
    except Exception as exc:  # noqa: BLE001 - never crash the loop silently
        log_error_exc("terminal ws loop error", source=LOG_SOURCE, exc=exc)
    finally:
        stop_event.set()
        pump_task.cancel()
        try:
            pty.kill()
        except Exception as exc:  # noqa: BLE001
            log_error_exc("terminal kill error", source=LOG_SOURCE, exc=exc)
        _update_tab_pid(tid, "")
        log_info(f"terminal ws disconnect tab={tid}", source=LOG_SOURCE)
        try:
            await websocket.close()
        except Exception as exc:  # noqa: BLE001 - already closing
            log_info(f"terminal ws close note: {exc}", source=LOG_SOURCE)


__all__ = ["router"]

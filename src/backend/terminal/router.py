"""WebSocket terminal endpoint (task B3.2 — PTY lifetime decoupled from WS).

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
  On (re)connect the server first REPLAYS the recent-output ring buffer, then
  streams live output.
* **Client → server (keystrokes)**: raw TEXT frames are written verbatim to
  the PTY (keystrokes / pasted text).
* **Client → server (control)**: a TEXT frame that is JSON:

  - ``{"type":"resize","cols":<int>,"rows":<int>}`` → resize the PTY.
  - ``{"type":"close"}`` → **explicitly terminate this session** (kill the
    PTY + drop it from the registry). This is the ONLY client path that
    kills the shell — send it when the user deliberately closes the tab.

  Any other JSON / text is treated as raw input (forwarded to the shell).

Concurrency model (SAFETY: disconnect ≠ kill)
---------------------------------------------
PTY lifetime is owned by the server-side registry in
``backend.terminal.session`` — NOT by this WebSocket. A dedicated daemon
thread per session reads the PTY into a ring buffer and (while attached) an
``asyncio.Queue``. On WS connect we ``get_or_create`` the session (reattach,
never respawn a live one), replay the buffer, and pump live output. On
disconnect / send failure we **detach only**: the shell keeps running and
buffering so a reattach (tab unfreeze, network recovery) sees everything.
Only ``{"type":"close"}`` or the reaper (exited PTY / long-orphaned idle
session) terminate the process. All teardown is logged (ADR-011).
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from backend.config.db import SessionLocal
from backend.log import log_error_exc, log_info
from backend.models import TerminalSession, TerminalTab
from backend.terminal.pty import PtyError
from backend.terminal.session import PtySession, get_or_create

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


async def _pump(
    websocket: WebSocket, queue: "asyncio.Queue[bytes]", tid: int
) -> None:
    """Async side: drain the session queue and send frames to the client.

    A send failure caused by the client going away (disconnect) is normal
    teardown → INFO; only unexpected send errors are logged as ERROR. The
    PTY is NOT touched here — the handler's ``finally`` detaches the view
    while the session (shell + reader + buffer) keeps running.
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
    loop = asyncio.get_running_loop()

    # Reattach to the live session for this tab, or spawn one (never both).
    try:
        session: PtySession = get_or_create(tid)
    except PtyError as exc:
        log_error_exc(
            f"terminal ws spawn failed tab={tid}: {exc}", source=LOG_SOURCE, exc=exc
        )
        await websocket.close(code=1011)
        return

    replay, queue = session.attach(websocket, loop)
    log_info(
        f"terminal ws attached tab={tid} pid={session.pty.pid} replay_chunks={len(replay)}",
        source=LOG_SOURCE,
    )

    # Catch-up: replay the ring buffer so a reattaching client sees recent
    # output produced while it was away.
    for chunk in replay:
        try:
            await websocket.send_text(chunk.decode("utf-8", "replace"))
        except Exception as exc:  # noqa: BLE001 - classified below
            if _is_disconnect_error(exc, websocket):
                log_info(
                    f"terminal ws client gone during replay tab={tid}",
                    source=LOG_SOURCE,
                )
            else:
                log_error_exc("terminal replay send error", source=LOG_SOURCE, exc=exc)
            break

    pump_task = asyncio.create_task(_pump(websocket, queue, tid))

    close_requested = False
    try:
        async for msg in websocket.iter_text():
            # Control frame? JSON {"type":"resize"/"close",...} → not a keystroke.
            if msg.startswith("{"):
                try:
                    obj = json.loads(msg)
                    if isinstance(obj, dict):
                        mtype = obj.get("type")
                        if mtype == "resize":
                            cols = int(obj.get("cols", 80))
                            rows = int(obj.get("rows", 24))
                            session.resize(cols, rows)
                            continue
                        if mtype == "close":
                            # Deliberate user close: the ONLY client path that
                            # kills the shell.
                            close_requested = True
                            break
                except (TypeError, ValueError, json.JSONDecodeError) as exc:
                    log_info(
                        f"terminal: non-JSON control frame ignored: {exc}",
                        source=LOG_SOURCE,
                    )
            try:
                session.write_text(msg)
            except PtyError as exc:
                log_error_exc(
                    f"terminal ws write failed tab={tid}: {exc}",
                    source=LOG_SOURCE,
                    exc=exc,
                )
    except WebSocketDisconnect:
        log_info(f"terminal ws client disconnected tab={tid}", source=LOG_SOURCE)
    except Exception as exc:  # noqa: BLE001 - never crash the loop silently
        log_error_exc("terminal ws loop error", source=LOG_SOURCE, exc=exc)
    finally:
        pump_task.cancel()
        if close_requested:
            session.terminate()
            log_info(f"terminal ws closed by client tab={tid}", source=LOG_SOURCE)
        else:
            # SAFETY-CRITICAL: a dropped WS (tab freeze, network blip) must
            # NOT kill the shell — detach the view only. The PTY keeps
            # running + buffering; the reaper handles truly-dead/orphaned
            # sessions later.
            session.detach(websocket)
            log_info(
                f"terminal ws detached tab={tid} pid={session.pty.pid} "
                f"(pty kept alive)",
                source=LOG_SOURCE,
            )
        try:
            await websocket.close()
        except Exception as exc:  # noqa: BLE001 - already closing
            log_info(f"terminal ws close note: {exc}", source=LOG_SOURCE)


__all__ = ["router"]

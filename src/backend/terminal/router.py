"""WebSocket terminal endpoint (task B3.2 — PTY lifetime decoupled from WS).

Endpoint
--------
``WS /ws/terminal/{tab_id}``

tab_id handling (SAFETY-CRITICAL: stable registry key)
-------------------------------------------------------
``tab_id`` (the RAW URL string) is the registry key of the PTY session. The
frontend generates its own UUID per tab and REUSES it on every reconnect, so
the same string must always map to the same live session — that is what makes
reattach (buffer replay, running job kept alive) work. Minting a new int per
connect (the old bug) respawned a fresh shell every time and leaked a
TerminalTab row per reconnect.

The DB :class:`TerminalTab` row is created ONLY when a NEW session spawns
(first connect for a key), via :func:`_ensure_db_tab`:
* numeric raw id naming an existing tab → reuse that row (backward compat);
* anything else (UUID, ``0``, unknown id) → create a fresh
  :class:`TerminalSession` + :class:`TerminalTab` and bind its id to the
  session (``session.db_tab_id``).
Reconnects never create a row and never respawn the PTY.

Message protocol (for frontend B3.3)
------------------------------------
* **Server → client**: terminal output as TEXT frames (UTF-8 decoded bytes).
  On (re)connect the server first REPLAYS the recent-output ring buffer, then
  streams live output. While attached it also sends an application-level
  heartbeat TEXT frame ``{"type":"ping","t":<unix_seconds>}`` every
  ``HEARTBEAT_INTERVAL_SECONDS`` so the client sees steady traffic and can spot
  a half-open/dead socket fast (uvicorn's protocol-level ws_ping is set in
  launcher.py; this is the app-level complement).
* **Client → server (keystrokes)**: raw TEXT frames are written verbatim to
  the PTY (keystrokes / pasted text). A frame is a keystroke ONLY if it is not
  a JSON control object (see below).
* **Client → server (control)**: a TEXT frame that is a JSON **object carrying
  a ``type`` field** is a CONTROL frame and is NEVER written to the PTY:

  - ``{"type":"resize","cols":<int>,"rows":<int>}`` → resize the PTY.
  - ``{"type":"close"}`` → **explicitly terminate this session** (kill the
    PTY + drop it from the registry). This is the ONLY client path that
    kills the shell — send it when the user deliberately closes the tab.
  - ``{"type":"pong"}`` → the client's heartbeat reply; records liveness, is
    NOT echoed to the shell.
  - ``{"type":"ping"}`` / any other ``type`` → ignored (logged), never a
    keystroke.

  Anything that is not such a JSON object — plain text, a JSON array/number,
  an object without ``type``, or text that merely starts with ``{`` but fails
  to parse — is treated as raw input and forwarded to the shell.

Concurrency model (SAFETY: disconnect ≠ kill)
---------------------------------------------
PTY lifetime is owned by the server-side registry in
``backend.terminal.session`` — NOT by this WebSocket. A dedicated daemon
thread per session reads the PTY into a ring buffer and (while attached) an
``asyncio.Queue``. On WS connect we ``get_or_create`` the session (reattach,
never respawn a live one), replay the buffer, and pump live output. A separate
per-connection heartbeat task emits ``{"type":"ping"}`` frames while attached
(both senders share one ``asyncio.Lock`` so frames never interleave). On
disconnect / send failure we **detach only**: the shell keeps running and
buffering so a reattach (tab unfreeze, network recovery) sees everything.
Only ``{"type":"close"}`` or the reaper (exited PTY / long-orphaned idle
session) terminate the process. All teardown is logged (ADR-011).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from backend.config.db import SessionLocal
from backend.log import log_error_exc, log_info
from backend.models import TerminalSession, TerminalTab
from backend.terminal.pty import PtyError
from backend.terminal.session import (
    HEARTBEAT_INTERVAL_SECONDS,
    PONG_TIMEOUT_SECONDS,
    PtySession,
    get_or_create,
)

LOG_SOURCE = "backend.terminal.router"

# Stdlib logger for routine, high-frequency diagnostics (per-frame heartbeat
# notes) that must NOT hit the LogEntry table; R12 reserves log_info/warning/
# error for the persisted, meaningful events.
_log = logging.getLogger(__name__)

router = APIRouter()

# Inbound-frame classification returned by :func:`_classify_inbound`.
INBOUND_KEYSTROKE = "keystroke"  # raw input → write to the PTY
INBOUND_CONTROL = "control"  # handled/ignored control frame → NOT a keystroke
INBOUND_CLOSE = "close"  # deliberate user close → terminate + break

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
def _ensure_db_tab(raw: str) -> int:
    """Resolve/create the DB TerminalTab row to bind to a NEW session.

    Backward compat: a numeric ``raw`` naming an existing tab reuses that
    row. Anything else (UUID string, ``0``, unknown id) creates a fresh
    TerminalSession + TerminalTab. Invoked ONCE per spawned session (via
    ``get_or_create``'s ``create_tab`` hook) — reconnects never reach here,
    which is what stops the old per-connect row leak.
    """
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
    websocket: WebSocket,
    queue: "asyncio.Queue[bytes]",
    tab_key: str,
    send_lock: "Optional[asyncio.Lock]" = None,
) -> None:
    """Async side: drain the session queue and send frames to the client.

    A send failure caused by the client going away (disconnect) is normal
    teardown → INFO; only unexpected send errors are logged as ERROR. The
    PTY is NOT touched here — the handler's ``finally`` detaches the view
    while the session (shell + reader + buffer) keeps running.

    ``send_lock`` serializes writes against the heartbeat task so a ping and a
    PTY chunk never interleave on the socket (starlette WebSockets are not safe
    for concurrent sends). It is held only for the duration of one send.
    """
    if send_lock is None:
        send_lock = asyncio.Lock()
    while True:
        data = await queue.get()
        async with send_lock:
            try:
                await websocket.send_text(data.decode("utf-8", "replace"))
            except Exception as exc:  # noqa: BLE001 - classified below
                if _is_disconnect_error(exc, websocket):
                    log_info(
                        f"terminal ws client gone during send tab={tab_key}",
                        source=LOG_SOURCE,
                    )
                else:
                    log_error_exc("terminal send error", source=LOG_SOURCE, exc=exc)
                break


async def _heartbeat_loop(
    websocket: WebSocket,
    send_lock: "asyncio.Lock",
    session: PtySession,
    tab_key: str,
    interval: float = HEARTBEAT_INTERVAL_SECONDS,
    pong_timeout: float = PONG_TIMEOUT_SECONDS,
) -> None:
    """Per-connection application-level keepalive.

    While the view is attached, emit ``{"type":"ping","t":<unix_seconds>}``
    every ``interval`` seconds. Sends go through ``send_lock`` so they never
    interleave with PTY output from :func:`_pump`.

    Conservative stale handling: once the client has ponged at least once, a
    silence longer than ``pong_timeout`` detaches the VIEW (the PTY keeps
    running + buffering; the client can reattach) and closes the socket so the
    browser reconnects. A client that never pongs is never dropped for it.

    This task is started on attach and cancelled in the handler's ``finally``
    (detach), so it stops cleanly and never blocks PTY output.
    """
    while True:
        await asyncio.sleep(interval)
        payload = json.dumps({"type": "ping", "t": int(time.time())})
        async with send_lock:
            try:
                await websocket.send_text(payload)
            except Exception as exc:  # noqa: BLE001 - classified below
                if _is_disconnect_error(exc, websocket):
                    log_info(
                        f"terminal heartbeat stopped (client gone) tab={tab_key}",
                        source=LOG_SOURCE,
                    )
                else:
                    log_error_exc(
                        "terminal heartbeat send error", source=LOG_SOURCE, exc=exc
                    )
                return
        if session.heartbeat_stale(time.monotonic(), pong_timeout):
            log_info(
                f"terminal heartbeat: no pong >{pong_timeout:.0f}s, dropping stale "
                f"view tab={tab_key} (pty kept alive)",
                source=LOG_SOURCE,
            )
            session.detach(websocket)
            try:
                await websocket.close()
            except Exception as exc:  # noqa: BLE001 - already tearing down
                _log.debug("terminal heartbeat close note tab=%s: %r", tab_key, exc)
            return


def _classify_inbound(
    msg: str, session: PtySession, tab_key: str
) -> str:
    """Decide whether one inbound TEXT frame is a keystroke or a control frame.

    Returns :data:`INBOUND_CLOSE` for a deliberate close, :data:`INBOUND_CONTROL`
    for any JSON object carrying a ``type`` field (resize acted on, pong records
    liveness, ping/unknown ignored), else :data:`INBOUND_KEYSTROKE` for raw
    input. SAFETY: only INBOUND_KEYSTROKE may ever be written to the PTY — a
    ``{"type":"pong"}`` or unknown control frame must never reach the shell.
    """
    if not msg.startswith("{"):
        return INBOUND_KEYSTROKE
    try:
        obj = json.loads(msg)
    except (TypeError, ValueError):
        # Starts with '{' but is not valid JSON → literal keystroke (e.g. the
        # user typed '{'). Not a control frame.
        _log.debug("terminal: brace-led non-JSON frame treated as keystroke")
        return INBOUND_KEYSTROKE
    if not isinstance(obj, dict) or "type" not in obj:
        # Valid JSON but not a control object (array/number/object without a
        # 'type' key) → raw input.
        return INBOUND_KEYSTROKE
    mtype = obj.get("type")
    if mtype == "close":
        return INBOUND_CLOSE
    if mtype == "resize":
        try:
            cols = int(obj.get("cols", 80))
            rows = int(obj.get("rows", 24))
            session.resize(cols, rows)
        except (TypeError, ValueError) as exc:
            log_info(
                f"terminal: bad resize frame ignored tab={tab_key}: {exc}",
                source=LOG_SOURCE,
            )
        return INBOUND_CONTROL
    if mtype == "pong":
        session.record_pong()
        _log.debug("terminal heartbeat pong tab=%s", tab_key)
        return INBOUND_CONTROL
    if mtype == "ping":
        # Client-initiated ping: nothing to do (server owns the heartbeat).
        _log.debug("terminal: ignoring client ping tab=%s", tab_key)
        return INBOUND_CONTROL
    # Unknown control type: ignore, never a keystroke.
    log_info(
        f"terminal: ignoring unknown control type={mtype!r} tab={tab_key}",
        source=LOG_SOURCE,
    )
    return INBOUND_CONTROL


# --------------------------------------------------------------------------- #
# WebSocket endpoint
# --------------------------------------------------------------------------- #
@router.websocket("/ws/terminal/{tab_id}")
async def terminal_ws(websocket: WebSocket, tab_id: str) -> None:
    await websocket.accept()
    log_info(f"terminal ws connect tab_id={tab_id}", source=LOG_SOURCE)

    loop = asyncio.get_running_loop()

    # Reattach to the live session for this client key, or spawn one (never
    # both). The registry key is the RAW URL string: the frontend reuses its
    # UUID across reconnects, so the same key returns the SAME running shell.
    # The DB tab row is created only on a fresh spawn (create_tab hook).
    try:
        session: PtySession = get_or_create(
            tab_id, create_tab=lambda: _ensure_db_tab(tab_id)
        )
    except PtyError as exc:
        log_error_exc(
            f"terminal ws spawn failed tab={tab_id}: {exc}",
            source=LOG_SOURCE,
            exc=exc,
        )
        await websocket.close(code=1011)
        return

    replay, queue = session.attach(websocket, loop)
    log_info(
        f"terminal ws attached tab={tab_id} pid={session.pty.pid} "
        f"replay_chunks={len(replay)}",
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
                    f"terminal ws client gone during replay tab={tab_id}",
                    source=LOG_SOURCE,
                )
            else:
                log_error_exc("terminal replay send error", source=LOG_SOURCE, exc=exc)
            break

    # One lock serializes every server→client send on this connection (PTY
    # output from _pump + heartbeat pings) so frames never interleave.
    send_lock: asyncio.Lock = asyncio.Lock()
    pump_task = asyncio.create_task(_pump(websocket, queue, tab_id, send_lock))
    # App-level keepalive: emits {"type":"ping"} while attached, stops cleanly
    # when cancelled in the finally below (detach).
    heartbeat_task = asyncio.create_task(
        _heartbeat_loop(websocket, send_lock, session, tab_id)
    )

    close_requested = False
    try:
        async for msg in websocket.iter_text():
            kind = _classify_inbound(msg, session, tab_id)
            if kind == INBOUND_CLOSE:
                # Deliberate user close: the ONLY client path that kills the
                # shell.
                close_requested = True
                break
            if kind == INBOUND_CONTROL:
                # resize/pong/ping/unknown: acted on or ignored above, never a
                # keystroke.
                continue
            try:
                session.write_text(msg)
            except PtyError as exc:
                log_error_exc(
                    f"terminal ws write failed tab={tab_id}: {exc}",
                    source=LOG_SOURCE,
                    exc=exc,
                )
    except WebSocketDisconnect:
        log_info(
            f"terminal ws client disconnected tab={tab_id}", source=LOG_SOURCE
        )
    except Exception as exc:  # noqa: BLE001 - never crash the loop silently
        log_error_exc("terminal ws loop error", source=LOG_SOURCE, exc=exc)
    finally:
        pump_task.cancel()
        heartbeat_task.cancel()
        if close_requested:
            session.terminate()
            log_info(
                f"terminal ws closed by client tab={tab_id}", source=LOG_SOURCE
            )
        else:
            # SAFETY-CRITICAL: a dropped WS (tab freeze, network blip) must
            # NOT kill the shell — detach the view only. The PTY keeps
            # running + buffering; the reaper handles truly-dead/orphaned
            # sessions later.
            session.detach(websocket)
            log_info(
                f"terminal ws detached tab={tab_id} pid={session.pty.pid} "
                f"(pty kept alive)",
                source=LOG_SOURCE,
            )
        try:
            await websocket.close()
        except Exception as exc:  # noqa: BLE001 - already closing
            log_info(f"terminal ws close note: {exc}", source=LOG_SOURCE)


__all__ = ["router"]

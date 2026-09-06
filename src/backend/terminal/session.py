"""Server-side PTY session registry (SAFETY: PTY outlives the WebSocket).

Why this module exists
----------------------
Previously the terminal WS handler owned the PTY: any transient WebSocket
drop (Chrome freezing a backgrounded/minimized tab, a network blip) ran the
handler's ``finally`` and killed the shell — aborting a running agentic CLI
(e.g. aider) mid-operation. That is dangerous.

New model (tmux/wetty-style)
---------------------------
* A :class:`PtySession` owns the PTY + a dedicated reader thread that runs
  **independently of any WS connection**.
* Sessions live in a module-level registry keyed by the client's **raw tab id
  string** (:func:`get_or_create`) — e.g. the frontend's UUID, which it reuses
  on every reconnect, so the same key always maps to the same running shell.
  The WebSocket is just a detachable *view*. The DB ``TerminalTab`` row is
  created ONCE per spawned session (``PtySession.db_tab_id``), never per
  connect (the old per-connect int minting leaked rows and broke reattach).
* While attached, output is streamed live through an ``asyncio.Queue``;
  always, output is appended to a bounded **ring buffer** so a reattaching
  client can replay recent output and catch up.
* Disconnect ⇒ **detach only** (the PTY keeps running + buffering).
* The ONLY paths that kill a PTY are:
  1. an explicit client control frame ``{"type":"close"}`` (user closed the
     tab deliberately), handled by the router via :meth:`PtySession.terminate`;
  2. the reaper (:func:`reap_idle` / :func:`reaper_loop`), which terminates
     sessions whose PTY has **exited** (even while a view is still attached),
     or that are detached AND idle (no output) for longer than the grace
     period. A *running* job is never reaped just because its WS dropped —
     only truly-dead or extremely-long-orphaned sessions (default grace:
     60 minutes, Setting ``terminal_idle_reap_minutes``).

When the shell dies (``exit`` / Ctrl-D / crash / killed) the reader thread
calls :meth:`PtySession.notify_exit`, which pushes ONE :class:`PtyExit`
sentinel onto the attached view's queue. The sentinel rides the live queue
only — never the ring buffer — so the router can turn it into a single
``{"type":"exit","code":<int>}`` control frame (TSD §3.1) without a
reattaching client ever replaying it as terminal text.

Threading
---------
``PtySession.lock`` guards the ring buffer + attach state; the registry has
its own ``_registry_lock``. Lock order is registry → session, never the
reverse while holding both (``terminate``/``try_reap`` release the session
lock before touching the registry). Reader-thread → event-loop delivery uses
``asyncio.run_coroutine_threadsafe``.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from typing import Any, Callable, Optional, Union

from starlette.websockets import WebSocketState

from backend.config import settings as settings_repo
from backend.config.db import SessionLocal
from backend.log import log_error_exc, log_info, log_warning
from backend.models import TerminalTab
from backend.terminal.pty import PtyError, PtyProcess, spawn_shell

LOG_SOURCE = "backend.terminal.session"

# Normal WebSocket close code used when the server ends a terminal connection
# (TSD §3.1: shell exited → send the exit control frame → close the WS).
WS_CLOSE_NORMAL = 1000

# ``code`` value of the exit control frame when the shell's real exit status
# cannot be read (killed by signal, backend does not expose it). The contract
# with the frontend is that ``code`` is ALWAYS an integer, never null.
EXIT_CODE_UNKNOWN = -1

# Ring buffer cap: total bytes of recent PTY output kept per session so a
# reattaching client can catch up without unbounded memory growth.
RING_MAX_BYTES = 256 * 1024

# Idle-orphan grace (minutes) when the Setting row is absent/unparseable.
DEFAULT_IDLE_REAP_MINUTES = 60.0

# How often the background reaper task sweeps the registry.
REAPER_INTERVAL_SECONDS = 60.0

SETTING_IDLE_REAP_MINUTES = "terminal_idle_reap_minutes"

# Application-level WebSocket heartbeat (complements uvicorn's protocol-level
# ws_ping_* set in launcher.py). While a view is ATTACHED the router sends a
# TEXT frame ``{"type":"ping","t":<unix_seconds>}`` every HEARTBEAT_INTERVAL
# seconds so the client sees steady traffic and can spot a half-open/dead
# socket quickly. If the client ponged at least once but then goes silent for
# longer than PONG_TIMEOUT seconds, the router DETACHES the stale view (never
# kills the PTY). Conservative on purpose: a client that never pongs (older
# frontend) is never dropped for missing pongs, and a frozen-then-resumed tab
# simply reattaches.
HEARTBEAT_INTERVAL_SECONDS = 15.0
PONG_TIMEOUT_SECONDS = 60.0


# --------------------------------------------------------------------------- #
# DB bookkeeping (own short-lived sessions; never leak connections)
# --------------------------------------------------------------------------- #
def _update_tab_pid(tid: int, pid: str) -> None:
    """Persist (or clear) the tab's ``pty_pid``. Best-effort, logged."""
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


def _grace_seconds() -> float:
    """Idle-orphan reap grace in seconds, read from the Setting store."""
    try:
        raw = settings_repo.get(
            SETTING_IDLE_REAP_MINUTES, default=str(DEFAULT_IDLE_REAP_MINUTES)
        )
        return max(0.0, float(raw)) * 60.0
    except Exception as exc:  # noqa: BLE001 - bad DB/value → safe default
        log_warning(
            f"terminal: cannot read {SETTING_IDLE_REAP_MINUTES}, "
            f"using default {DEFAULT_IDLE_REAP_MINUTES}min: {exc!r}",
            source=LOG_SOURCE,
        )
        return DEFAULT_IDLE_REAP_MINUTES * 60.0


# --------------------------------------------------------------------------- #
# Exit control: sentinel + view teardown
# --------------------------------------------------------------------------- #
class PtyExit:
    """Queue sentinel marking "the PTY is gone" — NOT terminal output.

    Pushed onto the attached view's live queue (never the ring buffer) so the
    router's pump can emit exactly one ``{"type":"exit","code":<int>}`` control
    frame and close the socket. A distinct object type (instead of a magic byte
    string) means real PTY output can never be mistaken for it.
    """

    __slots__ = ("code",)

    def __init__(self, code: int) -> None:
        self.code = code

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"PtyExit(code={self.code})"


def read_exit_code(pty: Any) -> int:
    """Best-effort shell exit status; :data:`EXIT_CODE_UNKNOWN` when unreadable.

    The contract guarantees an ``int`` in the exit frame, so every failure mode
    (backend without ``exit_status``, status not yet reaped, killed by signal)
    collapses to ``-1`` instead of leaking ``None`` to the client.
    """
    try:
        code = getattr(pty, "exit_status", None)
    except Exception as exc:  # noqa: BLE001 - a raising property is still "unknown"
        log_warning(
            f"terminal: cannot read pty exit status ({exc!r}), reporting "
            f"{EXIT_CODE_UNKNOWN}",
            source=LOG_SOURCE,
        )
        return EXIT_CODE_UNKNOWN
    return code if isinstance(code, int) else EXIT_CODE_UNKNOWN


async def close_view(websocket: Any, tab_key: str, code: int = WS_CLOSE_NORMAL) -> None:
    """Close one WS view, tolerating an already-closed socket.

    Shared by the router (exit frame + handler teardown) and the kill path so
    the "was it already closed?" dance lives in exactly one place. Closing is
    how a dead shell stops being a zombie tab: the client sees the socket end
    right after the exit frame.
    """
    try:
        if getattr(websocket, "application_state", None) is WebSocketState.DISCONNECTED:
            return
        await websocket.close(code=code)
    except Exception as exc:  # noqa: BLE001 - already tearing down
        log_info(f"terminal ws close note tab={tab_key}: {exc}", source=LOG_SOURCE)


# --------------------------------------------------------------------------- #
# PtySession
# --------------------------------------------------------------------------- #
class PtySession:
    """A PTY + reader thread + output ring buffer, independent of any WS.

    The session is created (and its reader started) by :func:`get_or_create`
    only. ``attach`` / ``detach`` manage the (optional) live WebSocket view;
    ``terminate`` / ``try_reap`` are the only ways the PTY dies.
    """

    def __init__(self, tab_key: str, pty: PtyProcess, cols: int, rows: int) -> None:
        # Registry key: the client's raw tab id string (stable across
        # reconnects — this is what makes reattach work).
        self.tab_key = tab_key
        self.pty = pty
        self.cols = cols
        self.rows = rows
        # DB TerminalTab row bound to this session, created ONCE at spawn by
        # get_or_create's ``create_tab`` hook (None → no row bookkeeping).
        self.db_tab_id: Optional[int] = None
        # Output ring buffer (bytes chunks, capped at RING_MAX_BYTES total).
        self.ring: deque[bytes] = deque()
        self.ring_bytes = 0
        # Attach state (guarded by ``lock``).
        self.lock = threading.Lock()
        self.attached: Any = None  # websocket or None
        self.queue: Optional["asyncio.Queue[Union[bytes, PtyExit]]"] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        # Lifecycle.
        self.stop_event = threading.Event()
        self.reader: Optional[threading.Thread] = None
        self.exited = False
        # Shell exit status once the reader reaped it (None → unknown → -1).
        self.exit_code: Optional[int] = None
        # The view queue that already received the PtyExit sentinel: makes the
        # "exactly one exit frame" contract per-VIEW (a reattach to a session
        # that died while detached still gets told).
        self.exit_view: Optional["asyncio.Queue[Union[bytes, PtyExit]]"] = None
        self.created_ts = time.monotonic()
        self.last_output_ts = self.created_ts
        # Heartbeat bookkeeping for the currently-attached view (guarded by
        # ``lock``). None until the client's first pong arrives, so a client
        # that does not implement the heartbeat is never dropped for it.
        self.last_pong_ts: Optional[float] = None

    # ------------------------------------------------------------------ #
    # Reader thread (runs independent of any WS)
    # ------------------------------------------------------------------ #
    def start_reader(self) -> None:
        """Spawn the dedicated daemon reader thread (once)."""
        self.reader = threading.Thread(
            target=_reader_loop,
            args=(self,),
            daemon=True,
            name=f"pty-reader-{self.tab_key}",
        )
        self.reader.start()

    def _deliver(
        self,
        queue: "Optional[asyncio.Queue[Union[bytes, PtyExit]]]",
        loop: Optional[asyncio.AbstractEventLoop],
        item: "Union[bytes, PtyExit]",
    ) -> None:
        """Push one item onto a view's queue (reader thread → event loop).

        ``queue``/``loop`` are the view the caller captured UNDER the session
        lock — that atomicity is what keeps a chunk from being both replayed
        (it is already in the ring) and streamed live to a just-attached view.
        A dead loop means the view is gone → detach it (never kill the PTY).
        """
        if queue is None or loop is None:
            return  # detached: buffered only, replayed on reattach
        try:
            asyncio.run_coroutine_threadsafe(queue.put(item), loop)
        except Exception as exc:  # noqa: BLE001 - loop closed → view gone, keep pty
            log_warning(
                f"terminal live delivery failed tab={self.tab_key} (detaching): {exc!r}",
                source=LOG_SOURCE,
            )
            with self.lock:
                if self.queue is queue:
                    self.attached = None
                    self.queue = None
                    self.loop = None

    def _publish(self, data: bytes) -> None:
        """Record one PTY output chunk: ring buffer always, live queue if attached.

        Called from the reader thread.
        """
        with self.lock:
            self.last_output_ts = time.monotonic()
            self.ring.append(data)
            self.ring_bytes += len(data)
            while self.ring_bytes > RING_MAX_BYTES and len(self.ring) > 1:
                self.ring_bytes -= len(self.ring.popleft())
            queue, loop = self.queue, self.loop
        self._deliver(queue, loop, data)

    def notify_exit(self) -> bool:
        """Tell the attached view that the PTY died — at most once per view.

        Called from the reader thread when the shell exits and from the kill
        path. The :class:`PtyExit` sentinel goes on the LIVE queue only, so the
        exit frame can never be replayed to a reattaching client as terminal
        text. Returns True when a sentinel was actually queued.
        """
        sentinel: PtyExit = PtyExit(self.resolved_exit_code())
        with self.lock:
            self.exited = True
            queue, loop = self.queue, self.loop
            if queue is None or queue is self.exit_view:
                return False  # detached, or this view was already told
            self.exit_view = queue
        self._deliver(queue, loop, sentinel)
        return True

    def resolved_exit_code(self) -> int:
        """Exit status for the control frame (reader-captured, else best-effort).

        Always an ``int``: the frontend contract forbids a null/string code.
        """
        code = self.exit_code
        if code is None:
            code = read_exit_code(self.pty)
        return code if isinstance(code, int) else EXIT_CODE_UNKNOWN

    # ------------------------------------------------------------------ #
    # WS view attach / detach (never touches the PTY lifecycle)
    # ------------------------------------------------------------------ #
    def attach(
        self, websocket: Any, loop: asyncio.AbstractEventLoop
    ) -> "tuple[list[bytes], asyncio.Queue[Union[bytes, PtyExit]]]":
        """Attach a WS view. Returns (replay chunks, live queue).

        The caller must send the replay chunks, then drain the queue for
        live output. Attaching twice (e.g. double connect on one tab) steals
        the view: the old WS's queue simply stops receiving and its pump is
        cancelled by its own handler teardown.

        A view attached to an ALREADY-dead session is seeded with the exit
        sentinel, so it can never hang on a shell that will not produce the
        "I'm gone" frame (the exit frame is per-view, hence not a duplicate).
        """
        # Resolved before taking the lock: status lookup must not run under it.
        code = self.resolved_exit_code()
        with self.lock:
            replay = list(self.ring)
            queue: "asyncio.Queue[Union[bytes, PtyExit]]" = asyncio.Queue()
            self.attached = websocket
            self.queue = queue
            self.loop = loop
            # Fresh view: no pong seen yet on this connection, and this view
            # has not been told about the exit yet.
            self.last_pong_ts = None
            self.exit_view = queue if self.exited else None
            if self.exited:
                queue.put_nowait(PtyExit(code))
            return replay, queue

    def record_pong(self) -> None:
        """Note that the attached client answered a heartbeat ping.

        Called from the router's receive loop (event-loop thread). The first
        pong arms the stale-view watchdog: from then on, silence beyond
        ``PONG_TIMEOUT_SECONDS`` means the view is dead and may be detached.
        """
        with self.lock:
            self.last_pong_ts = time.monotonic()

    def heartbeat_stale(self, now: float, timeout: float) -> bool:
        """True if an attached view has ponged before but gone silent too long.

        Deliberately conservative: returns False when detached (nothing to
        watch) and False until the FIRST pong (a client that never pongs is
        not penalised). Only an established-then-silent heartbeat is stale.
        """
        with self.lock:
            if self.attached is None or self.last_pong_ts is None:
                return False
            return (now - self.last_pong_ts) > timeout

    def detach(self, websocket: Any) -> None:
        """Detach a WS view (idempotent; no-op if another view already stole it).

        SAFETY-CRITICAL: this does NOT kill the PTY and does NOT stop the
        reader. The shell keeps running and its output keeps buffering.
        """
        with self.lock:
            if self.attached is websocket:
                self.attached = None
                self.queue = None
                self.loop = None

    # ------------------------------------------------------------------ #
    # Client → PTY operations
    # ------------------------------------------------------------------ #
    def write_text(self, text: str) -> None:
        """Forward keystrokes / pasted text to the PTY (raises PtyError)."""
        self.pty.write(text.encode("utf-8"))

    def resize(self, cols: int, rows: int) -> None:
        """Resize the PTY; failure is logged, non-fatal."""
        try:
            self.pty.set_winsize(cols, rows)
            self.cols = cols
            self.rows = rows
        except PtyError as exc:
            log_warning(
                f"terminal resize failed tab={self.tab_key}: {exc}",
                source=LOG_SOURCE,
            )

    # ------------------------------------------------------------------ #
    # Termination (the ONLY PTY-kill paths)
    # ------------------------------------------------------------------ #
    def terminate(self, reason: str = "client close") -> None:
        """Kill the PTY + unregister (client close, or post-exit reclaim).

        Never raises. The attached view (if any) is told the shell is gone via
        the exit sentinel before its state is dropped.
        """
        self.stop_event.set()
        self._kill_and_unregister(reason=reason)

    def try_reap(self, now: float, grace_seconds: float) -> bool:
        """Reap-check under the session lock; kill + unregister if eligible.

        Eligible when the PTY has **exited** (attached view or not — a dead
        shell must never linger as a zombie tab) or when it is detached AND
        idle beyond the grace period.

        SAFETY (the reason this module exists): a session whose shell is still
        RUNNING is never killed just because its WS dropped — that case stays
        behind the ``attached is None`` + grace guard.
        Returns True if this session was terminated.
        """
        with self.lock:
            exited = self.exited or not self.pty.is_alive()
            if not exited:
                if self.attached is not None:
                    return False  # someone is watching a live job
                if (now - self.last_output_ts) < grace_seconds:
                    return False  # running job, WS blip: keep it
            self.stop_event.set()
        self._kill_and_unregister(reason="pty exited" if exited else "idle orphan")
        return True

    def _kill_and_unregister(self, reason: str) -> None:
        """Kill the PTY, notify + drop the view, clear registry entry + tab pid."""
        # Notify BEFORE the view state is cleared: the sentinel has to reach the
        # live queue, or the client waits forever on a socket nobody serves.
        self.notify_exit()
        if self.pty.is_alive():
            try:
                self.pty.kill()
            except Exception as exc:  # noqa: BLE001 - kill failure must not strand registry
                log_error_exc(
                    f"terminal kill error tab={self.tab_key} ({reason})",
                    source=LOG_SOURCE,
                    exc=exc,
                )
        pid = self.pty.pid
        with self.lock:
            self.exited = True
            websocket, loop = self.attached, self.loop
            self.attached = None
            self.queue = None
            self.loop = None
        unregister(self.tab_key, expected=self)
        if self.db_tab_id is not None:
            _update_tab_pid(self.db_tab_id, "")
        if websocket is not None and loop is not None:
            # Backstop for a view whose pump is gone (half-open socket, cancelled
            # task): its WS must still close, or the tab stays a zombie.
            try:
                asyncio.run_coroutine_threadsafe(
                    close_view(websocket, self.tab_key), loop
                )
            except Exception as exc:  # noqa: BLE001 - loop already dead: nothing to close
                log_warning(
                    f"terminal cannot close stale view tab={self.tab_key}: {exc!r}",
                    source=LOG_SOURCE,
                )
        log_info(
            f"terminal session terminated ({reason}) tab={self.tab_key} pid={pid}",
            source=LOG_SOURCE,
        )


def _reader_loop(session: PtySession) -> None:
    """Blocking reader: feeds decoded PTY output into the session.

    Runs as a daemon thread, independent of any WS. A read failure during
    shutdown (``stop_event`` set) or an EOF/OSError from the killed PTY is
    expected teardown → INFO, not ERROR. Only genuinely unexpected reads are
    logged as errors. When the PTY is no longer alive the session is marked
    ``exited`` and the attached view is told with one exit sentinel (TSD §3.1:
    the client must close its tab instead of hanging on a dead shell). Reaping
    the registry entry stays with the reaper / the handler teardown — the
    reader never touches the registry or the DB.
    """
    pty = session.pty
    stop_event = session.stop_event
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
        session._publish(data)
    if not pty.is_alive():
        code = read_exit_code(pty)
        with session.lock:
            session.exited = True
            session.exit_code = code
        log_info(
            f"terminal pty exited tab={session.tab_key} code={code}",
            source=LOG_SOURCE,
        )
        # Tell the attached view so its tab closes (TSD §3.1). Reclaiming the
        # registry entry + tab pid is the reaper's / the handler's job: the
        # reader thread never touches the registry or the DB.
        session.notify_exit()


# --------------------------------------------------------------------------- #
# Registry (thread-safe)
# --------------------------------------------------------------------------- #
_sessions: dict[str, PtySession] = {}
_registry_lock = threading.Lock()


def get_or_create(
    tab_key: str,
    cols: int = 80,
    rows: int = 24,
    create_tab: Optional[Callable[[], int]] = None,
) -> PtySession:
    """Return the live session for ``tab_key``; spawn one only if absent.

    ``tab_key`` is the client's RAW tab id string (e.g. the frontend UUID).
    The frontend reuses the same string on reconnect, so the same key maps
    to the same running shell — reattach works, the PTY is never respawned
    while live. SAFETY: an existing session is returned as-is; a lazy reap
    sweep runs first so exited sessions transparently respawn fresh shells.

    ``create_tab`` is invoked ONLY when a NEW session is spawned, under the
    registry lock, to create/resolve the DB ``TerminalTab`` row exactly once
    per session; its id is stored as ``session.db_tab_id`` for pid
    bookkeeping. Reattaches never call it (no duplicate rows, no DB leak).
    Row-creation failures are logged best-effort — a DB hiccup must not
    strand the freshly spawned PTY. Raises :class:`PtyError` (from
    ``spawn_shell``) only when creating.
    """
    reap_idle()
    with _registry_lock:
        existing = _sessions.get(tab_key)
        if existing is not None:
            return existing
        pty = spawn_shell(cols=cols, rows=rows)
        session = PtySession(tab_key=tab_key, pty=pty, cols=cols, rows=rows)
        if create_tab is not None:
            try:
                session.db_tab_id = create_tab()
            except Exception as exc:  # noqa: BLE001 - terminal stays usable
                log_error_exc(
                    f"terminal: cannot create tab row key={tab_key}",
                    source=LOG_SOURCE,
                    exc=exc,
                )
        _sessions[tab_key] = session
    session.start_reader()
    if session.db_tab_id is not None:
        _update_tab_pid(
            session.db_tab_id, str(pty.pid) if pty.pid is not None else ""
        )
    log_info(
        f"terminal session spawned tab={tab_key} pid={pty.pid} "
        f"db_tab={session.db_tab_id}",
        source=LOG_SOURCE,
    )
    return session


def unregister(tab_key: str, expected: Optional[PtySession] = None) -> None:
    """Remove ``tab_key`` from the registry (only if it is still ``expected``)."""
    with _registry_lock:
        current = _sessions.get(tab_key)
        if current is None or (expected is not None and current is not expected):
            return
        _sessions.pop(tab_key, None)


def get_session(tab_key: str) -> Optional[PtySession]:
    """Registry lookup (tests / introspection)."""
    with _registry_lock:
        return _sessions.get(tab_key)


def snapshot_sessions() -> list[PtySession]:
    """Copy of all registered sessions (tests / diagnostics)."""
    with _registry_lock:
        return list(_sessions.values())


def reap_idle(now: Optional[float] = None) -> list[str]:
    """Sweep the registry; terminate exited / long-orphaned sessions.

    Returns the tab keys reaped. An **exited** session is reclaimed even while
    a view is still attached (its tab must not linger as a zombie). A *running*
    session is only touched when detached AND idle beyond the (generous) grace
    period — a dropped WS never kills a live job.
    """
    grace = _grace_seconds()
    if now is None:
        now = time.monotonic()
    with _registry_lock:
        candidates = list(_sessions.values())
    reaped: list[str] = []
    for session in candidates:
        try:
            if session.try_reap(now, grace):
                reaped.append(session.tab_key)
        except Exception as exc:  # noqa: BLE001 - one bad session must not stop sweep
            log_error_exc(
                f"terminal reap check failed tab={session.tab_key}",
                source=LOG_SOURCE,
                exc=exc,
            )
    return reaped


async def reaper_loop(interval_seconds: float = REAPER_INTERVAL_SECONDS) -> None:
    """Background sweep task (started from the app lifespan). Cancel to stop."""
    try:
        while True:
            await asyncio.sleep(interval_seconds)
            reap_idle()
    except asyncio.CancelledError:
        log_info("terminal reaper loop cancelled", source=LOG_SOURCE)
        raise


__all__ = [
    "DEFAULT_IDLE_REAP_MINUTES",
    "EXIT_CODE_UNKNOWN",
    "HEARTBEAT_INTERVAL_SECONDS",
    "LOG_SOURCE",
    "PONG_TIMEOUT_SECONDS",
    "REAPER_INTERVAL_SECONDS",
    "RING_MAX_BYTES",
    "SETTING_IDLE_REAP_MINUTES",
    "WS_CLOSE_NORMAL",
    "PtyExit",
    "PtySession",
    "close_view",
    "get_or_create",
    "get_session",
    "read_exit_code",
    "reap_idle",
    "reaper_loop",
    "snapshot_sessions",
    "unregister",
]

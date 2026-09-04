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
     sessions whose PTY has **exited**, or that are detached AND idle (no
     output) for longer than the grace period. A *running* job is never
     reaped just because its WS dropped — only truly-dead or
     extremely-long-orphaned sessions (default grace: 60 minutes, Setting
     ``terminal_idle_reap_minutes``).

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
from typing import Any, Callable, Optional

from backend.config import settings as settings_repo
from backend.config.db import SessionLocal
from backend.log import log_error_exc, log_info, log_warning
from backend.models import TerminalTab
from backend.terminal.pty import PtyError, PtyProcess, spawn_shell

LOG_SOURCE = "backend.terminal.session"

# Ring buffer cap: total bytes of recent PTY output kept per session so a
# reattaching client can catch up without unbounded memory growth.
RING_MAX_BYTES = 256 * 1024

# Idle-orphan grace (minutes) when the Setting row is absent/unparseable.
DEFAULT_IDLE_REAP_MINUTES = 60.0

# How often the background reaper task sweeps the registry.
REAPER_INTERVAL_SECONDS = 60.0

SETTING_IDLE_REAP_MINUTES = "terminal_idle_reap_minutes"


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
        self.queue: Optional["asyncio.Queue[bytes]"] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        # Lifecycle.
        self.stop_event = threading.Event()
        self.reader: Optional[threading.Thread] = None
        self.exited = False
        self.created_ts = time.monotonic()
        self.last_output_ts = self.created_ts

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

    def _publish(self, data: bytes) -> None:
        """Record one PTY output chunk: ring buffer always, live queue if attached.

        Called from the reader thread. Live delivery crosses into the event
        loop via ``run_coroutine_threadsafe``; a dead loop means the view is
        gone → detach (never kill the PTY).
        """
        with self.lock:
            self.last_output_ts = time.monotonic()
            self.ring.append(data)
            self.ring_bytes += len(data)
            while self.ring_bytes > RING_MAX_BYTES and len(self.ring) > 1:
                self.ring_bytes -= len(self.ring.popleft())
            queue, loop = self.queue, self.loop
        if queue is None or loop is None:
            return  # detached: buffered only, replayed on reattach
        try:
            asyncio.run_coroutine_threadsafe(queue.put(data), loop)
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

    # ------------------------------------------------------------------ #
    # WS view attach / detach (never touches the PTY lifecycle)
    # ------------------------------------------------------------------ #
    def attach(
        self, websocket: Any, loop: asyncio.AbstractEventLoop
    ) -> "tuple[list[bytes], asyncio.Queue[bytes]]":
        """Attach a WS view. Returns (replay chunks, live queue).

        The caller must send the replay chunks, then drain the queue for
        live output. Attaching twice (e.g. double connect on one tab) steals
        the view: the old WS's queue simply stops receiving and its pump is
        cancelled by its own handler teardown.
        """
        with self.lock:
            replay = list(self.ring)
            queue: "asyncio.Queue[bytes]" = asyncio.Queue()
            self.attached = websocket
            self.queue = queue
            self.loop = loop
            return replay, queue

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
    def terminate(self) -> None:
        """Explicit user close: kill the PTY + unregister. Never raises."""
        self.stop_event.set()
        self._kill_and_unregister(reason="client close")

    def try_reap(self, now: float, grace_seconds: float) -> bool:
        """Reap-check under the session lock; kill + unregister if eligible.

        Eligible when: not attached AND (PTY exited OR idle beyond grace).
        Returns True if this session was terminated.
        """
        with self.lock:
            if self.attached is not None:
                return False
            exited = self.exited or not self.pty.is_alive()
            if not exited and (now - self.last_output_ts) < grace_seconds:
                return False
            self.stop_event.set()
        self._kill_and_unregister(reason="pty exited" if exited else "idle orphan")
        return True

    def _kill_and_unregister(self, reason: str) -> None:
        """Kill the PTY, mark exited, drop the registry entry + tab pid."""
        try:
            self.pty.kill()
        except Exception as exc:  # noqa: BLE001 - kill failure must not strand registry
            log_error_exc(
                f"terminal kill error tab={self.tab_id} ({reason})",
                source=LOG_SOURCE,
                exc=exc,
            )
        pid = self.pty.pid
        with self.lock:
            self.exited = True
            self.attached = None
            self.queue = None
            self.loop = None
        unregister(self.tab_key, expected=self)
        if self.db_tab_id is not None:
            _update_tab_pid(self.db_tab_id, "")
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
    ``exited`` (the reaper removes it later; we never delete here).
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
        with session.lock:
            session.exited = True
        log_info(f"terminal pty exited tab={session.tab_key}", source=LOG_SOURCE)


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

    Returns the tab keys reaped. Running-but-detached sessions are only
    touched after the (generous) idle grace; attached sessions never.
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
    "LOG_SOURCE",
    "REAPER_INTERVAL_SECONDS",
    "RING_MAX_BYTES",
    "SETTING_IDLE_REAP_MINUTES",
    "PtySession",
    "get_or_create",
    "get_session",
    "reap_idle",
    "reaper_loop",
    "snapshot_sessions",
    "unregister",
]

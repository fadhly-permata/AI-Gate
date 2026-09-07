"""Self-Heal orchestrator (task B4.1) — backend only.

Auto git branch + launch an agentic CLI + fix/test loop driven by ``LogEntry``
warning/error rows, delete resolved ``LogEntry`` rows, then merge to ``main`` +
delete the branch (per FSD §2.8 Self-Heal + PRD §2.8).

The run is made **visible to the user**: instead of an invisible
``subprocess.run`` call, the agentic CLI runs inside a LIVE terminal (PTY)
session registered under the tab key ``"self-heal"`` (FSD §2.8 / TSD §3.5).
The orchestrator types one shell line per issue into that PTY — the CLI reads
its prompt from a backend-controlled temp file, so no LogEntry content is ever
embedded in the command line (no shell injection). Completion of one issue is
detected by polling a ``<prompt>.done`` sentinel file the command touches.
The ``PtySession`` registry (not this module) owns the PTY lifetime; the run
aborts cleanly if the session dies mid-issue (user closed the tab).

The actual agentic CLI execution depends on a user-installed binary. Every
external call (git / agentic cli / pytest) is wrapped so a missing binary or a
non-zero exit becomes a clean status — never a crash.

ADR-011 / R12: every step is logged via ``backend.log`` with
``source="backend.selfheal.*"``. No bare ``except: pass`` — every exception is
caught, logged via ``log_error_exc``/``log_warning``, and turned into a safe
status dict.

Pydantic is NOT used here (this is service/orchestration code, not a router).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.config import db as _db  # referenced lazily so tests can rebind
from backend.log import log_error_exc, log_info, log_warning
from backend.models import LogEntry, TerminalSession, TerminalTab

LOG_SOURCE = "backend.selfheal.orchestrate"

# Grup A presets — agentic CLI binaries we know how to drive via --prompt.
AGENTIC_CLIS = [
    "opencode",
    "claude",
    "aider",
    "codex",
    "gemini",
    "goose",
    "amp",
    "qwen",
    "cline",
    "kilo",
]

# Workspace root = the git repo (repo is two levels above this file:
# src/backend/selfheal.py -> /src/backend -> /src -> /repo).
REPO_DIR: Path = Path(__file__).resolve().parents[2]

# Terminal registry key of the dedicated Self-Heal tab (the run's "window").
HEAL_TAB_KEY = "self-heal"

# Per-issue ceiling for the agentic CLI running inside the terminal PTY. On
# timeout the loop logs a warning and proceeds to run_tests (tests decide
# whether the issue is deleted). Module-level so tests can monkeypatch it.
HEAL_CLI_TIMEOUT_SECONDS = 1800.0

# How often the done-sentinel file is polled while the CLI works.
DONE_POLL_INTERVAL_SECONDS = 2.0


# --------------------------------------------------------------------------- #
# Detection + git helpers
# --------------------------------------------------------------------------- #
def detect_agentic_cli() -> Optional[str]:
    """Return the first agentic CLI binary found on PATH, else ``None``.

    Order follows ``AGENTIC_CLIS`` (Grup A presets). Returns ``None`` when the
    user has not installed any, so callers can short-circuit cleanly.
    """
    for cli in AGENTIC_CLIS:
        if shutil.which(cli):
            return cli
    return None


def git(*args: str, cwd: Path = REPO_DIR) -> subprocess.CompletedProcess:
    """Run ``git`` with ``args`` in ``cwd`` (default ``REPO_DIR``).

    Raises ``RuntimeError`` on a missing git binary or a non-zero exit so the
    caller can log + convert to a safe status (does NOT swallow the error).
    """
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:  # git binary absent
        raise RuntimeError(f"git binary not found: {exc}") from exc
    except subprocess.CalledProcessError as exc:  # non-zero exit
        stderr = (exc.stderr or "").strip()
        raise RuntimeError(
            f"git {' '.join(args)} failed (rc={exc.returncode}): {stderr or exc}"
        ) from exc


def create_heal_branch() -> str:
    """Create + checkout ``aigate/self-heal-<YYYYMMDD-HHMMSS>``; return name.

    Raises ``RuntimeError`` if the repo is not a git repo or git is missing —
    the caller logs and returns a status dict (no crash).
    """
    name = f"aigate/self-heal-{datetime.now():%Y%m%d-%H%M%S}"
    git("checkout", "-b", name)
    return name


# --------------------------------------------------------------------------- #
# Terminal (PTY) driving — the run becomes visible in the "self-heal" tab
# --------------------------------------------------------------------------- #
def _create_heal_db_tab() -> int:
    """Create the ``TerminalTab`` DB row bound to the self-heal PTY session.

    Mirrors ``backend.terminal.router._create_tab`` (same session/tab row
    pattern) with a sensible title so the tab survives reopen. Failures are
    caught here and reported as ``0`` (``get_or_create`` treats a falsy id as
    "no bookkeeping"), because a DB hiccup must not abort the heal run.
    """
    try:
        with _db.SessionLocal() as session:
            ts = TerminalSession(session_name="default")
            session.add(ts)
            session.flush()
            tab = TerminalTab(
                session_id=ts.id,
                title="Self-Heal",
                shell_type="bash",
            )
            session.add(tab)
            session.commit()
            session.refresh(tab)
            return int(tab.id)
    except Exception as exc:  # noqa: BLE001 - best-effort row, run must go on
        log_error_exc(
            "self-heal: create TerminalTab row failed (continuing without it)",
            source=LOG_SOURCE,
            exc=exc,
        )
        return 0


def _session_alive(sess: Any) -> bool:
    """True if ``sess`` (PtySession or test double) still runs its shell."""
    try:
        alive = bool(sess.pty.is_alive())
    except Exception:  # noqa: BLE001 - a raising probe counts as dead
        return False
    return alive and not bool(getattr(sess, "exited", False))


def _get_heal_session() -> Optional[Any]:
    """Live ``self-heal`` session; dead/exited entries are dropped so the next
    ``get_or_create`` respawns a fresh shell. Never touches a live session."""
    from backend.terminal import session as terminal_session_mod

    try:
        existing = terminal_session_mod.get_session(HEAL_TAB_KEY)
    except Exception as exc:  # noqa: BLE001 - registry hiccup → treat as absent
        log_warning(
            f"self-heal: terminal registry lookup failed: {exc!r}",
            source=LOG_SOURCE,
        )
        return None
    if existing is not None and not _session_alive(existing):
        try:
            terminal_session_mod.unregister(HEAL_TAB_KEY, expected=existing)
            log_info(
                "self-heal: dropping dead terminal session "
                f"tab='{HEAL_TAB_KEY}' (fresh shell will spawn)",
                source=LOG_SOURCE,
            )
        except Exception as exc:  # noqa: BLE001 - best-effort reclaim
            log_warning(
                "self-heal: cannot unregister dead terminal session: "
                f"{exc!r}",
                source=LOG_SOURCE,
            )
            return None
        existing = None
    return existing


def _ensure_heal_session() -> Any:
    """Spawn (or reattach to) the terminal session under key ``self-heal``."""
    from backend.terminal import session as terminal_session_mod

    existing = _get_heal_session()
    if existing is not None:
        return existing
    session = terminal_session_mod.get_or_create(
        HEAL_TAB_KEY,
        create_tab=_create_heal_db_tab,
    )
    log_info(
        f"self-heal: terminal session ready tab='{HEAL_TAB_KEY}' "
        f"pid={session.pty.pid} db_tab={session.db_tab_id}",
        source=LOG_SOURCE,
    )
    return session


def build_heal_command(cli: str, promptfile: Path, donefile: Path) -> str:
    """One shell line that runs the CLI visibly and signals completion.

    Only backend-controlled paths appear in the command — the prompt text
    (arbitrary LogEntry content) never touches the shell, so no injection is
    possible. ``touch`` + ``echo`` give the user a visible end marker.
    """
    return (
        f"{cli} --prompt \"$(cat '{promptfile}')\"; "
        f"touch '{donefile}'; "
        f"echo \"aigate: issue done\"\n"
    )


def wait_for_done(
    donefile: Path,
    session: Any,
    timeout: Optional[float] = None,
    poll: Optional[float] = None,
) -> bool:
    """Poll for the CLI's done-sentinel file; abort early on session death.

    ``timeout``/``poll`` default to the module constants resolved at CALL time
    (not def time), so tests can monkeypatch ``HEAL_CLI_TIMEOUT_SECONDS``.
    Returns ``True`` when the sentinel appeared, ``False`` on timeout or when
    the terminal session died mid-issue (user closed the tab / shell exited).
    """
    if timeout is None:
        timeout = HEAL_CLI_TIMEOUT_SECONDS
    if poll is None:
        poll = DONE_POLL_INTERVAL_SECONDS
    deadline = time.monotonic() + max(0.0, timeout)
    while True:
        if donefile.exists():
            return True
        if not _session_alive(session):
            log_warning(
                "self-heal: terminal session died while CLI was running "
                f"(issue donefile={donefile.name} never appeared)",
                source=LOG_SOURCE,
            )
            return False
        if time.monotonic() >= deadline:
            log_warning(
                f"self-heal: agentic cli timed out after {timeout:.0f}s "
                f"(donefile={donefile.name} never appeared); "
                "proceeding to run_tests",
                source=LOG_SOURCE,
            )
            return False
        time.sleep(max(0.05, poll))


def _drive_cli_in_terminal(
    cli: str,
    issue_id: int,
    prompt: str,
    session: Any,
) -> bool:
    """Run one issue's CLI pass inside the terminal PTY; ``True`` on donefile.

    Writes the prompt to a unique backend-controlled temp file, types the
    one-line command into the PTY (visible to the user), then waits for the
    done sentinel. Temp files are always cleaned up. ``False`` means timeout
    or a dead session — the caller proceeds to ``run_tests`` either way.
    """
    tmpdir = Path(tempfile.mkdtemp(prefix="aigate-heal-"))
    promptfile = tmpdir / f"issue-{issue_id}.prompt"
    donefile = Path(str(promptfile) + ".done")
    try:
        promptfile.write_text(prompt, encoding="utf-8")
        command = build_heal_command(cli, promptfile, donefile)
        log_info(
            f"self-heal: typing cli command into terminal tab='{HEAL_TAB_KEY}' "
            f"for issue id={issue_id}",
            source=LOG_SOURCE,
        )
        session.write_text(command)
        if wait_for_done(donefile, session):
            log_info(
                f"self-heal: cli finished for issue id={issue_id}",
                source=LOG_SOURCE,
            )
            return True
        return False
    except Exception as exc:  # noqa: BLE001 - PTY write hiccup → safe status
        log_error_exc(
            f"self-heal: driving cli in terminal failed for issue "
            f"id={issue_id}",
            source=LOG_SOURCE,
            exc=exc,
        )
        return False
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# --------------------------------------------------------------------------- #
# Async run state (POST /run starts a thread; GET /status reports)
# --------------------------------------------------------------------------- #
_state_lock = threading.Lock()
_running = False
_last_result: Optional[dict] = None


def heal_status() -> dict:
    """Snapshot for ``GET /api/self-heal/status`` (thread-safe copy)."""
    with _state_lock:
        last = dict(_last_result) if _last_result is not None else None
        return {"running": _running, "last": last}


def _run_thread_target(max_iter: int) -> None:
    """Thread body: run the sync loop once, then record + clear state."""
    global _running, _last_result
    try:
        result = run_self_heal(max_iter=max_iter)
    except Exception as exc:  # noqa: BLE001 - a thread must never die loudly
        log_error_exc(
            "self-heal: background run crashed",
            source=LOG_SOURCE,
            exc=exc,
        )
        result = {"ok": False, "reason": "internal_error", "detail": str(exc)}
    with _state_lock:
        _last_result = result
        _running = False
    log_info(
        f"self-heal: background run finished ok={result.get('ok')}",
        source=LOG_SOURCE,
    )


def start_self_heal(max_iter: int = 5) -> dict:
    """Start the orchestration in a daemon thread; never blocks the caller.

    Returns ``{"started": True, "tab": "self-heal"}`` or
    ``{"started": False, "reason": "already_running"}``. The global state is
    flipped under one lock so two concurrent POSTs cannot double-start.
    """
    global _running
    with _state_lock:
        if _running:
            return {"started": False, "reason": "already_running"}
        _running = True
    thread = threading.Thread(
        target=_run_thread_target,
        args=(max_iter,),
        daemon=True,
        name="self-heal-run",
    )
    thread.start()
    log_info(
        f"self-heal: run started in terminal tab '{HEAL_TAB_KEY}' "
        f"(max_iter={max_iter})",
        source=LOG_SOURCE,
    )
    return {"started": True, "tab": HEAL_TAB_KEY}


def reset_self_heal_state() -> None:
    """Test hook: zero the async state between tests (not used in prod)."""
    global _running, _last_result
    with _state_lock:
        _running = False
        _last_result = None


# --------------------------------------------------------------------------- #
# LogEntry access
# --------------------------------------------------------------------------- #
def current_issue(session: Session) -> Optional[LogEntry]:
    """First warning/error ``LogEntry`` ordered by (timestamp asc, id asc)."""
    return (
        session.query(LogEntry)
        .filter(LogEntry.severity.in_(("warning", "error")))
        .order_by(LogEntry.timestamp.asc(), LogEntry.id.asc())
        .first()
    )


def delete_log_entry(session: Session, entry_id: int) -> None:
    """Delete the ``LogEntry`` row with ``entry_id`` and commit."""
    obj = session.get(LogEntry, entry_id)
    if obj is not None:
        session.delete(obj)
        session.commit()


def _count_remaining(session: Session) -> int:
    """Count warning/error ``LogEntry`` rows."""
    return (
        session.query(LogEntry)
        .filter(LogEntry.severity.in_(("warning", "error")))
        .count()
    )


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def run_tests() -> bool:
    """Run the backend test suite; return ``True`` iff all pass.

    Missing ``pytest`` / un-runnable interpreter -> ``False`` (never raise).
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/backend", "-q"],
            cwd=str(REPO_DIR),
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return False
    return result.returncode == 0


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def _remaining_safe(session: Session) -> int:
    """Count remaining issues; ``-1`` semantics when the count itself fails."""
    try:
        return _count_remaining(session)
    except Exception as exc:
        log_error_exc(
            "self-heal: count remaining failed",
            source=LOG_SOURCE,
            exc=exc,
        )
        return -1


def run_self_heal(max_iter: int = 5) -> dict:
    """Orchestrate the self-heal loop. Always returns a status ``dict``.

    Synchronous by contract (the async entry point is :func:`start_self_heal`,
    which calls this from a daemon thread). The agentic CLI runs inside the
    live ``self-heal`` terminal tab, so the user watches the fix happen.

    Status shapes:
    - ``{"ok": False, "reason": "no_agentic_cli"}``
    - ``{"ok": False, "reason": "git_failed", "detail": str}``
    - ``{"ok": True, "merged": True, "iterations": int}``
    - ``{"ok": True, "merged": False, "remaining": int}`` (also the
      abort-on-session-death shape; ``remaining=-1`` when the count fails)
    """
    # 1. Detect agentic CLI.
    cli = detect_agentic_cli()
    if cli is None:
        log_info(
            "self-heal skipped: no agentic CLI installed",
            source=LOG_SOURCE,
        )
        return {"ok": False, "reason": "no_agentic_cli"}

    # 2. Create the heal branch.
    try:
        branch = create_heal_branch()
        log_info(f"self-heal: created branch '{branch}'", source=LOG_SOURCE)
    except Exception as exc:  # git missing / not a repo
        log_error_exc(
            "self-heal: create_heal_branch failed",
            source=LOG_SOURCE,
            exc=exc,
        )
        return {"ok": False, "reason": "git_failed", "detail": str(exc)}

    # 3. Heal loop. Own session; closed in ``finally``.
    db_session = _db.SessionLocal()
    iterations = 0
    try:
        for _ in range(max(0, max_iter)):
            try:
                issue = current_issue(db_session)
            except Exception as exc:
                log_error_exc(
                    "self-heal: current_issue failed",
                    source=LOG_SOURCE,
                    exc=exc,
                )
                break

            if issue is None:
                # Nothing left to fix -> healed.
                break

            # Only count iterations that actually process an issue.
            iterations += 1

            prompt = (
                "Fix this issue in the aigate codebase based on this log:\n"
                f"{issue.message}\n"
                f"{issue.stacktrace or ''}"
            )

            # Make the run visible: ensure the dedicated terminal tab exists
            # (a dead session was already dropped by _get_heal_session, so a
            # fresh shell spawns transparently between issues).
            try:
                term = _ensure_heal_session()
            except Exception as exc:
                log_error_exc(
                    f"self-heal: cannot open terminal session tab="
                    f"'{HEAL_TAB_KEY}'",
                    source=LOG_SOURCE,
                    exc=exc,
                )
                return {
                    "ok": False,
                    "reason": "terminal_unavailable",
                    "detail": str(exc),
                }

            log_info(
                f"self-heal: running agentic cli '{cli}' in terminal tab "
                f"'{HEAL_TAB_KEY}' for issue id={issue.id}",
                source=LOG_SOURCE,
            )
            cli_done = _drive_cli_in_terminal(cli, issue.id, prompt, term)
            if not cli_done and not _session_alive(term):
                # Tab closed / shell died mid-issue (timeout keeps going, but
                # a dead session cannot run the next command): abort the run,
                # leave the branch. Tests did not run -> nothing is deleted.
                remaining = _remaining_safe(db_session)
                log_warning(
                    f"self-heal: run aborted (terminal session gone), "
                    f"remaining={remaining}",
                    source=LOG_SOURCE,
                )
                return {"ok": True, "merged": False, "remaining": remaining}

            if run_tests():
                try:
                    delete_log_entry(db_session, issue.id)
                    log_info(
                        f"self-heal: resolved issue id={issue.id}",
                        source=LOG_SOURCE,
                    )
                except Exception as exc:
                    log_error_exc(
                        f"self-heal: delete_log_entry failed for id={issue.id}",
                        source=LOG_SOURCE,
                        exc=exc,
                    )
                    break
            else:
                log_warning(
                    f"self-heal: tests failed after heal attempt for issue "
                    f"id={issue.id}",
                    source=LOG_SOURCE,
                )
                break

        # 4. After the loop: merge if fully healed, else leave the branch.
        remaining = _remaining_safe(db_session)

        if remaining == 0:
            try:
                git("checkout", "main")
                git("merge", branch)
                git("branch", "-d", branch)
                return {"ok": True, "merged": True, "iterations": iterations}
            except Exception as exc:
                log_error_exc(
                    "self-heal: merge / branch-delete failed",
                    source=LOG_SOURCE,
                    exc=exc,
                )
                return {
                    "ok": False,
                    "reason": "git_failed",
                    "detail": str(exc),
                }
        return {"ok": True, "merged": False, "remaining": remaining}
    finally:
        db_session.close()


__all__ = [
    "AGENTIC_CLIS",
    "DONE_POLL_INTERVAL_SECONDS",
    "HEAL_CLI_TIMEOUT_SECONDS",
    "HEAL_TAB_KEY",
    "REPO_DIR",
    "build_heal_command",
    "create_heal_branch",
    "current_issue",
    "delete_log_entry",
    "detect_agentic_cli",
    "git",
    "heal_status",
    "reset_self_heal_state",
    "run_self_heal",
    "run_tests",
    "start_self_heal",
    "wait_for_done",
]

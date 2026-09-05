"""Self-Heal orchestrator (task B4.1) — backend only.

Auto git branch + launch an agentic CLI + fix/test loop driven by ``LogEntry``
warning/error rows, delete resolved ``LogEntry`` rows, then merge to ``main`` +
delete the branch (per FSD §2.8 Self-Heal + PRD §2.8).

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
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from backend.config import db as _db  # referenced lazily so tests can rebind
from backend.log import log_error_exc, log_info, log_warning
from backend.models import LogEntry

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
def run_self_heal(max_iter: int = 5) -> dict:
    """Orchestrate the self-heal loop. Always returns a status ``dict``.

    Status shapes:
    - ``{"ok": False, "reason": "no_agentic_cli"}``
    - ``{"ok": False, "reason": "git_failed", "detail": str}``
    - ``{"ok": True, "merged": True, "iterations": int}``
    - ``{"ok": True, "merged": False, "remaining": int}``
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
    session = _db.SessionLocal()
    iterations = 0
    try:
        for _ in range(max(0, max_iter)):
            try:
                issue = current_issue(session)
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
            try:
                log_info(
                    f"self-heal: running agentic cli '{cli}' for issue "
                    f"id={issue.id}",
                    source=LOG_SOURCE,
                )
                subprocess.run(
                    [cli, "--prompt", prompt],
                    cwd=str(REPO_DIR),
                    check=False,
                )
            except Exception as exc:
                log_error_exc(
                    f"self-heal: agentic cli run failed for issue id={issue.id}",
                    source=LOG_SOURCE,
                    exc=exc,
                )

            if run_tests():
                try:
                    delete_log_entry(session, issue.id)
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
        try:
            remaining = _count_remaining(session)
        except Exception as exc:
            log_error_exc(
                "self-heal: count remaining failed",
                source=LOG_SOURCE,
                exc=exc,
            )
            remaining = -1

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
        session.close()


__all__ = [
    "AGENTIC_CLIS",
    "REPO_DIR",
    "detect_agentic_cli",
    "git",
    "create_heal_branch",
    "current_issue",
    "delete_log_entry",
    "run_tests",
    "run_self_heal",
]

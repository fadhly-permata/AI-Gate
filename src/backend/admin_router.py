"""Developer-mode self-restart endpoint (task DEV-RESTART / be-dev).

Exposes a single protected endpoint, ``POST /api/dev/restart``, that triggers a
FULL in-process restart of the server by re-executing ``run.py`` on the same
process image via ``os.execv``. The server runs in a single process
(``run.py`` -> ``backend.launcher.main()`` -> ``uvicorn.run(app)`` in-process),
so ``os.execv`` on the serving process is a full restart: it re-runs ``run.py``
(idempotent auto-pip), reloads code, and re-binds the same socket.

Design (locked by PM handover):
- Server-side gate on the ``dev_mode`` Setting: if it is not ``"true"`` we return
  403 and **never** restart (fail-closed).
- When ON we return ``{"status":"restarting"}`` (200) FIRST, then schedule the
  ``os.execv`` on a daemon ``threading.Timer`` (0.6s) so the response is flushed
  to the client before the process image is replaced.
- A module-level guard prevents scheduling more than one restart timer, so
  repeated calls (e.g. double-click) do not stack timers.

Testability contract:
- ``os.execv`` is invoked through the ``os`` module (patch ``os.execv``).
- The timer is created via the module-level ``Timer`` binding (patch
  ``backend.admin_router.Timer`` with a fake) so tests never spawn a real thread
  or wait on the interval.
- ``sys.argv`` is read at call time, so tests can assert the reconstructed argv
  preserves the user's original arguments.

This file NEVER imports or touches the frontend, ``/api/health``, or ``/v1/*``.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from threading import Lock, Timer

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.config.settings import get as get_setting
from backend.log import SEVERITY_ERROR, log_exception

logger = logging.getLogger(__name__)

router = APIRouter()

# Seconds to wait (after the 200 response is flushed) before re-exec'ing the
# process. Long enough for uvicorn to flush the socket; short enough that the
# FE polling /api/health notices the restart promptly.
RESTART_DELAY_S: float = 0.6

# Module-level guard so a restart is scheduled at most once per process lifetime.
_restart_lock = Lock()
_restart_scheduled: bool = False


def _resolve_run_py() -> str:
    """Return the absolute path to this project's ``run.py`` launcher.

    Prefer deriving it from THIS module's known location
    (``<root>/src/backend/admin_router.py`` -> ``<root>/run.py``) rather than
    trusting ``sys.argv[0]`` resolution, which depends on the caller's cwd.
    Fall back to ``sys.argv[0]`` resolved against cwd only if the derived path
    does not exist (e.g. the package is launched via a console script).
    """
    module_dir = Path(__file__).resolve().parent  # <root>/src/backend
    derived = module_dir.parent.parent / "run.py"  # <root>/run.py
    if derived.is_file():
        return str(derived)
    # Fallback: whatever the interpreter was started with.
    argv0 = sys.argv[0] if sys.argv else "run.py"
    return str(Path(argv0).resolve())


def _build_restart_argv() -> list[str]:
    """Reconstruct the command line that re-executes the current server.

    ``[sys.executable, <abs run.py>, *sys.argv[1:]]`` — preserves any user
    arguments (e.g. ``--port 9000``) passed when the server was launched.
    """
    return [sys.executable, _resolve_run_py(), *sys.argv[1:]]


def _do_restart(argv: list[str]) -> None:
    """Replace the current process image with a fresh ``run.py`` invocation.

    ``os.execv`` does not return on success (the process becomes the new
    ``run.py``). On failure we log loudly and re-raise rather than silently
    leaving a dead-but-serving process.
    """
    try:
        logger.info("admin_router: execv restart -> %s", argv)
        os.execv(argv[0], argv)
    except Exception as exc:  # noqa: BLE001 — must never fail silently
        log_exception(
            SEVERITY_ERROR,
            "admin_router: os.execv restart failed",
            source="backend.admin_router._do_restart",
            exc=exc,
        )
        raise


def _schedule_restart(argv: list[str]) -> None:
    """Schedule the restart on a daemon Timer (0.6s) so the HTTP response is
    flushed before the process image is replaced."""
    timer = Timer(RESTART_DELAY_S, _do_restart, args=(argv,))
    timer.daemon = True
    timer.start()


def _dev_mode_enabled() -> bool:
    """True only when the ``dev_mode`` Setting is exactly ``"true"``.

    Any other value (``"false"``, missing, or a read error) is treated as OFF so
    the gate fails closed and never restarts unexpectedly.
    """
    try:
        value = get_setting("dev_mode")
    except Exception as exc:  # noqa: BLE001 — fail closed, but log the reason
        log_exception(
            SEVERITY_ERROR,
            "admin_router: failed to read dev_mode setting; restart denied",
            source="backend.admin_router._dev_mode_enabled",
            exc=exc,
        )
        return False
    return bool(value) and value.strip().lower() == "true"


@router.post("/api/dev/restart")
def dev_restart() -> JSONResponse:
    """Restart the server in-process (dev mode only).

    Returns 403 (``dev_mode_required``) unless ``dev_mode`` is ``"true"``. When
    enabled, returns 200 ``{"status":"restarting"}`` and schedules an in-process
    ``os.execv`` of ``run.py`` after the response is sent. Repeated calls in the
    same process schedule at most one restart.
    """
    global _restart_scheduled  # noqa: PLW0603 — module-level single-shot guard
    if not _dev_mode_enabled():
        return JSONResponse(
            status_code=403,
            content={"error": {"message": "developer mode is off",
                                "type": "invalid_request_error",
                                "code": "dev_mode_required"}},
        )
    with _restart_lock:
        if not _restart_scheduled:
            argv = _build_restart_argv()
            _restart_scheduled = True
            # Optional audit trail — must never crash the response if logging
            # fails (log_event is caller-safe, but stay defensive).
            try:
                from backend.log import log_info

                log_info(
                    "aigate restart requested (dev mode)",
                    source="backend.admin_router.dev_restart",
                )
            except Exception:  # noqa: BLE001 — logging is best-effort
                logger.exception("admin_router: restart log failed (ignored)")
            _schedule_restart(argv)

    return JSONResponse(status_code=200, content={"status": "restarting"})


__all__ = ["router", "RESTART_DELAY_S", "_resolve_run_py", "_build_restart_argv"]

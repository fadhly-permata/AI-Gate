"""Mandatory backend logging helper — writes to the ``LogEntry`` table (ADR-011).

ADR-011 / rule R12: every backend warning/error **must** land in ``LogEntry``
with its severity and (for warning/error) a stacktrace when available. This
module is the single choke point for that. Convenience wrappers also emit to
the stdlib logger so the console still shows output (we never log to
stdout-**only** for errors).

Public API
----------
- ``log_event(severity, message, source=None, stacktrace=None, context=None,
  session=None)`` -> persisted ``LogEntry`` (or a detached stub on DB failure).
- ``log_info / log_warning / log_error(message, source=None, ...)``.
- ``log_exception(severity, message, source=None, exc=None, ...)`` -> captures
  a formatted traceback from ``exc`` (or the current frame if ``exc`` is None).

Design notes
------------
- A caller-supplied ``session`` is used as-is and never committed/closed here;
  this lets a log entry participate in an outer transaction. Otherwise a
  short-lived ``SessionLocal`` is created, committed and closed.
- Importing this module must never raise and ``log_event`` must never crash the
  caller: if the DB write fails we fall back to the stdlib logger and return a
  detached ``LogEntry`` (not persisted) so callers can still use the return.
- ``SessionLocal`` is referenced via the ``backend.config.db`` module object
  (not a direct import binding) so tests can rebind it to an in-memory engine.
"""

from __future__ import annotations

import json
import logging
import traceback
from typing import Any, Mapping, Optional

from sqlalchemy.orm import Session

from backend.config import db as _db
from backend.models import LogEntry

logger = logging.getLogger(__name__)

SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"

# Severities that require a stacktrace when available (ADR-011).
_STACKTRACE_SEVERITIES = frozenset({SEVERITY_WARNING, SEVERITY_ERROR})


def _render_context(context: Any) -> Optional[str]:
    """Best-effort JSON rendering of an optional structured context."""
    if context is None:
        return None
    if isinstance(context, (str, bytes)):
        return context if isinstance(context, str) else context.decode("utf-8", "replace")
    if isinstance(context, Mapping):
        try:
            return json.dumps(context, default=str, ensure_ascii=False)
        except Exception:  # noqa: BLE001 - context is diagnostic only
            return str(context)
    try:
        return json.dumps(context, default=str, ensure_ascii=False)
    except Exception:  # noqa: BLE001
        return str(context)


def _build_message(message: str, context: Any) -> str:
    """Append a rendered context to the message (LogEntry has no context col)."""
    rendered = _render_context(context)
    if not rendered:
        return message
    return f"{message} | context: {rendered}"


def log_event(
    severity: str,
    message: str,
    source: Optional[str] = None,
    stacktrace: Optional[str] = None,
    context: Any = None,
    session: Optional[Session] = None,
) -> LogEntry:
    """Persist a ``LogEntry`` row and return it.

    If ``session`` is given it is used and left unmanaged (no commit/close).
    Otherwise a fresh ``SessionLocal`` is committed and closed. On DB failure a
    stdlib error is emitted and a detached (non-persisted) ``LogEntry`` is
    returned so the caller never crashes.
    """
    full_message = _build_message(message, context)
    own = session is None
    s: Session = session if session is not None else _db.SessionLocal()
    entry = LogEntry(
        severity=severity,
        source=source or "",
        message=full_message,
        stacktrace=stacktrace,
    )
    try:
        s.add(entry)
        s.flush()
        if own:
            s.commit()
            s.refresh(entry)
        return entry
    except Exception:  # noqa: BLE001 - logging must never raise into the caller
        if own:
            s.rollback()
        logger.error(
            "log_event failed to persist LogEntry (severity=%s, source=%s): %s",
            severity,
            source,
            full_message,
            exc_info=True,
        )
        return entry  # detached stub; not in DB but caller-safe
    finally:
        if own:
            s.close()


def log_info(
    message: str,
    source: Optional[str] = None,
    context: Any = None,
    session: Optional[Session] = None,
) -> LogEntry:
    """Record an INFO-level entry."""
    logger.info("%s | %s", source or "-", message)
    return log_event(
        SEVERITY_INFO, message, source=source, context=context, session=session
    )


def log_warning(
    message: str,
    source: Optional[str] = None,
    stacktrace: Optional[str] = None,
    context: Any = None,
    session: Optional[Session] = None,
) -> LogEntry:
    """Record a WARNING-level entry (prefer a stacktrace when available)."""
    logger.warning("%s | %s", source or "-", message)
    return log_event(
        SEVERITY_WARNING,
        message,
        source=source,
        stacktrace=stacktrace,
        context=context,
        session=session,
    )


def log_error(
    message: str,
    source: Optional[str] = None,
    stacktrace: Optional[str] = None,
    context: Any = None,
    session: Optional[Session] = None,
) -> LogEntry:
    """Record an ERROR-level entry (prefer a stacktrace when available)."""
    logger.error("%s | %s", source or "-", message)
    return log_event(
        SEVERITY_ERROR,
        message,
        source=source,
        stacktrace=stacktrace,
        context=context,
        session=session,
    )


def log_exception(
    severity: str,
    message: str,
    source: Optional[str] = None,
    exc: Optional[BaseException] = None,
    context: Any = None,
    session: Optional[Session] = None,
) -> LogEntry:
    """Record an entry, auto-capturing a formatted traceback.

    If ``exc`` is provided, its traceback is formatted; otherwise the current
    exception frame (``traceback.format_exc()``) is used. The captured text is
    attached as ``stacktrace``.
    """
    if exc is not None:
        tb = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )
    else:
        tb = traceback.format_exc()
    if severity in _STACKTRACE_SEVERITIES:
        return log_event(
            severity, message, source=source, stacktrace=tb, context=context, session=session
        )
    # info-level exceptions still keep the traceback for diagnostics.
    return log_event(
        severity, message, source=source, stacktrace=tb, context=context, session=session
    )


def log_error_exc(
    message: str,
    source: Optional[str] = None,
    exc: Optional[BaseException] = None,
    context: Any = None,
    session: Optional[Session] = None,
) -> LogEntry:
    """Convenience: ERROR-level ``log_exception``."""
    return log_exception(
        SEVERITY_ERROR, message, source=source, exc=exc, context=context, session=session
    )


def log_warning_exc(
    message: str,
    source: Optional[str] = None,
    exc: Optional[BaseException] = None,
    context: Any = None,
    session: Optional[Session] = None,
) -> LogEntry:
    """Convenience: WARNING-level ``log_exception``."""
    return log_exception(
        SEVERITY_WARNING, message, source=source, exc=exc, context=context, session=session
    )


__all__ = [
    "SEVERITY_INFO",
    "SEVERITY_WARNING",
    "SEVERITY_ERROR",
    "log_event",
    "log_info",
    "log_warning",
    "log_error",
    "log_exception",
    "log_error_exc",
    "log_warning_exc",
]

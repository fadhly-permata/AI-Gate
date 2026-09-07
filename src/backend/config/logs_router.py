"""Operational log HTTP API (FastAPI router) for dev-mode observability.

Exposes the ``/api/logs`` endpoints from the OpenAI-compatible contract
(``documents/api/OPENAI_COMPATIBLE_CONTRACT.md``):

* ``GET /api/logs`` — list ``LogEntry`` rows (newest first), filtered by
  ``severity`` (comma-separated substrings, OR-matched), optional
  ``since`` ISO8601 timestamp and optional ``show_resolved`` (default false:
  rows with ``resolved == True`` are excluded), capped by ``limit`` (default
  100). Shape: ``{"object":"list","data":[{"id","timestamp","severity",
  "source","message","stacktrace","resolved"}]}``.
* ``POST /api/logs`` — accept a log written by the frontend and persist it via
  ``backend.log.log_event`` (the single ADR-011 choke point).
* ``DELETE /api/logs`` — purge rows filtered by ``severity`` (comma-separated
  substrings, OR-matched; absent = all) and optional ``before`` ISO8601
  upper bound. Wipe-all (no ``severity``) requires ``confirm=all`` — without
  it the request is a no-op returning 200 ``{"deleted": 0, "error":
  "confirmation required"}`` (never 4xx, per the fixed T1 contract).
  Shape: ``{"deleted": N}``.
* ``POST /api/logs/{entry_id}/resolve`` — mark one row ``resolved = True``.
  Returns ``{"resolved": 1}``, or ``{"resolved": 0}`` when the id is unknown
  (per the fixed T1 contract — not 404).
* ``POST /api/logs/resolve`` — bulk-resolve rows by ids. Shape:
  ``{"resolved": N}``.

Log cleanup (T1) retention: ``purge_expired_logs`` deletes rows older than the
``log_retention_days`` Setting (default 7) and is wired into app startup.

Rule R10: Pydantic **v1** ``BaseModel`` only.
Rule R12: every failure path logs to ``LogEntry`` (no silent failures).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import delete, or_, select

logger = logging.getLogger(__name__)

from backend.config.db import SessionLocal
from backend.log import log_event, log_warning
from backend.models import LogEntry


class LogCreate(BaseModel):
    """Frontend → backend log payload (Pydantic v1)."""

    severity: str
    source: str
    message: str
    stacktrace: Optional[str] = None

    class Config:
        extra = "allow"


class LogResolveRequest(BaseModel):
    """Bulk-resolve payload (Pydantic v1): ids of ``LogEntry`` rows."""

    ids: List[int]


router = APIRouter()

# Retention fallback when the ``log_retention_days`` Setting is missing,
# non-numeric or <= 0 (never crash startup — T1 Task B).
_DEFAULT_RETENTION_DAYS = 7


def _row_to_dict(row: LogEntry) -> dict:
    return {
        "id": row.id,
        "timestamp": row.timestamp.isoformat() if row.timestamp else None,
        "severity": row.severity,
        "source": row.source,
        "message": row.message,
        "stacktrace": row.stacktrace,
        "resolved": bool(row.resolved) if row.resolved is not None else False,
    }


def _severity_filter(stmt, severity: Optional[str]):
    """Apply the shared GET/DELETE severity semantics to ``stmt``.

    Comma-separated substrings, OR-matched (ilike) on ``LogEntry.severity``.
    Absent/blank = no severity constraint.
    """
    if severity:
        parts = [p.strip() for p in severity.split(",") if p.strip()]
        if parts:
            conds = [LogEntry.severity.ilike(f"%{p}%") for p in parts]
            stmt = stmt.where(or_(*conds))
    return stmt


@router.get("/api/logs")
def list_logs(
    severity: Optional[str] = Query(None, description="substring filter; comma=OR"),
    limit: int = Query(100, ge=1, le=1000),
    since: Optional[str] = Query(None, description="ISO8601 lower bound"),
    show_resolved: bool = Query(
        False, description="include rows flagged resolved (default: hide them)"
    ),
) -> dict:
    """Return stored ``LogEntry`` rows, newest first.

    Default hides ``resolved == True`` rows so the self-heal log feed and the
    UI focus on actionable entries; ``show_resolved=true`` includes everything.
    """
    stmt = select(LogEntry)

    stmt = _severity_filter(stmt, severity)

    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            stmt = stmt.where(LogEntry.timestamp >= since_dt)
        except ValueError:  # noqa: BLE001 - invalid input, skip filter + log
            log_warning(
                f"GET /api/logs: invalid 'since' value: {since}",
                source="backend.config.logs_router",
            )

    if not show_resolved:
        stmt = stmt.where(LogEntry.resolved == False)  # noqa: E712 - SQL filter

    stmt = stmt.order_by(LogEntry.timestamp.desc(), LogEntry.id.desc()).limit(limit)

    try:
        with SessionLocal() as session:
            rows = session.execute(stmt).scalars().all()
        return {"object": "list", "data": [_row_to_dict(r) for r in rows]}
    except Exception as exc:  # noqa: BLE001 - log + surface as 500
        log_warning(
            f"GET /api/logs failed: {exc}",
            source="backend.config.logs_router",
        )
        raise HTTPException(status_code=500, detail="Failed to read logs")


@router.post("/api/logs")
def create_log(payload: LogCreate) -> dict:
    """Persist a frontend-submitted log entry via ``backend.log.log_event``."""
    try:
        entry = log_event(
            severity=payload.severity,
            source=payload.source,
            message=payload.message,
            stacktrace=payload.stacktrace,
        )
        return _row_to_dict(entry)
    except Exception as exc:  # noqa: BLE001 - log + surface as 500
        log_warning(
            f"POST /api/logs failed: {exc}",
            source="backend.config.logs_router",
        )
        raise HTTPException(status_code=500, detail="Failed to write log")


@router.delete("/api/logs")
def delete_logs(
    severity: Optional[str] = Query(None, description="substring filter; comma=OR"),
    before: Optional[str] = Query(None, description="ISO8601 upper bound"),
    confirm: Optional[str] = Query(None, description="'all' required to wipe every entry"),
) -> dict:
    """Delete ``LogEntry`` rows matching the filters and return ``{"deleted": N}``.

    Semantics mirror GET, except for ``before``: this is a destructive op, so
    an invalid ISO value must NOT silently widen the delete — it returns 400.
    Wipe-all (no ``severity`` filter) requires ``confirm=all``; without it the
    request is a NO-OP returning 200 ``{"deleted": 0, "error": "confirmation
    required"}`` (fixed T1 contract). A scoped delete needs no confirmation.
    An info audit row is written AFTER the delete commits so a wipe-all cannot
    delete its own audit entry.
    """
    if not severity or not severity.strip():
        if confirm != "all":
            return {"deleted": 0, "error": "confirmation required"}

    before_dt: Optional[datetime] = None
    if before:
        try:
            before_dt = datetime.fromisoformat(before)
        except ValueError:
            log_warning(
                f"DELETE /api/logs: invalid 'before' value: {before}",
                source="backend.config.logs_router",
            )
            raise HTTPException(status_code=400, detail="invalid 'before'")

    stmt = delete(LogEntry)
    stmt = _severity_filter(stmt, severity)
    if before_dt is not None:
        stmt = stmt.where(LogEntry.timestamp < before_dt)

    try:
        with SessionLocal() as session:
            result = session.execute(stmt)
            session.commit()
            deleted = result.rowcount or 0
    except Exception as exc:  # noqa: BLE001 - log + surface as 500
        log_warning(
            f"DELETE /api/logs failed: {exc}",
            source="backend.config.logs_router",
        )
        raise HTTPException(status_code=500, detail="Failed to delete logs")

    # Audit AFTER commit (wipe-all must not swallow its own audit row).
    scope_parts = [f"deleted={deleted}"]
    scope_parts.append(
        f"severity={severity.strip() if severity and severity.strip() else 'all'}"
    )
    if before_dt is not None:
        scope_parts.append(f"before={before_dt.isoformat()}")
    log_event(
        "info",
        f"logs purged: {' '.join(scope_parts)}",
        source="backend.config.logs_router",
    )
    return {"deleted": deleted}


@router.post("/api/logs/{entry_id}/resolve")
def resolve_log(entry_id: int) -> dict:
    """Mark one ``LogEntry`` resolved (self-heal skip + hide from GET default).

    Unknown id → ``{"resolved": 0}`` (fixed T1 contract — idempotent shape,
    not 404).
    """
    try:
        with SessionLocal() as session:
            row = session.get(LogEntry, entry_id)
            if row is None:
                return {"resolved": 0}
            row.resolved = True
            session.commit()
    except Exception as exc:  # noqa: BLE001 - log + surface as 500
        log_warning(
            f"POST /api/logs/{entry_id}/resolve failed: {exc}",
            source="backend.config.logs_router",
        )
        raise HTTPException(status_code=500, detail="Failed to resolve log")
    return {"resolved": 1}


@router.post("/api/logs/resolve")
def resolve_logs_bulk(payload: LogResolveRequest) -> dict:
    """Bulk-mark matching ids resolved; unmatched ids are silently ignored.

    Empty ids list resolves nothing and returns ``{"resolved": 0}``.
    """
    if not payload.ids:
        return {"resolved": 0}
    try:
        with SessionLocal() as session:
            rows = (
                session.query(LogEntry)
                .filter(LogEntry.id.in_(payload.ids))
                .all()
            )
            for row in rows:
                row.resolved = True
            session.commit()
            count = len(rows)
    except Exception as exc:  # noqa: BLE001 - log + surface as 500
        log_warning(
            f"POST /api/logs/resolve failed: {exc}",
            source="backend.config.logs_router",
        )
        raise HTTPException(status_code=500, detail="Failed to resolve logs")
    return {"resolved": count}


# --------------------------------------------------------------------------- #
# Retention auto-purge (T1 Task B)
# --------------------------------------------------------------------------- #
def purge_expired_logs(days: Optional[int] = None, session=None) -> int:
    """Delete ``LogEntry`` rows older than ``days``; return the deleted count.

    ``days=None`` reads the ``log_retention_days`` Setting via
    ``backend.config.settings.get``. Missing/invalid/<=0 values fall back to
    ``_DEFAULT_RETENTION_DAYS`` (log_warning, never crash — startup safety).
    Pass ``session`` to participate in an outer transaction; otherwise a
    short-lived ``SessionLocal`` is created and committed.

    Note for tests: when ``days`` is given explicitly no Setting lookup happens,
    so no DB is touched unless ``session`` is None and rows are actually
    deleted.
    """
    if days is None:
        from backend.config import settings as settings_repo

        try:
            raw = settings_repo.get("log_retention_days")
        except Exception as exc:  # noqa: BLE001 - config read must not crash purge
            log_warning(
                f"purge_expired_logs: reading 'log_retention_days' failed: {exc}",
                source="backend.config.logs_router",
            )
            raw = None
        if raw is None:
            days = _DEFAULT_RETENTION_DAYS
        else:
            try:
                days = int(str(raw).strip())
            except (TypeError, ValueError):
                log_warning(
                    f"purge_expired_logs: invalid 'log_retention_days' value "
                    f"{raw!r}; falling back to {_DEFAULT_RETENTION_DAYS}",
                    source="backend.config.logs_router",
                )
                days = _DEFAULT_RETENTION_DAYS
        if days <= 0:
            log_warning(
                f"purge_expired_logs: non-positive 'log_retention_days' value "
                f"{days}; falling back to {_DEFAULT_RETENTION_DAYS}",
                source="backend.config.logs_router",
            )
            days = _DEFAULT_RETENTION_DAYS

    cutoff = datetime.utcnow() - timedelta(days=days)
    stmt = delete(LogEntry).where(LogEntry.timestamp < cutoff)

    own = session is None
    s = session if session is not None else SessionLocal()
    try:
        result = s.execute(stmt)
        if own:
            s.commit()
        return result.rowcount or 0
    except Exception as exc:  # noqa: BLE001 - R12: log, then surface
        if own:
            s.rollback()
        log_warning(
            f"purge_expired_logs failed: {exc}",
            source="backend.config.logs_router",
        )
        raise
    finally:
        if own:
            s.close()


__all__ = ["router", "LogCreate", "LogResolveRequest", "purge_expired_logs"]

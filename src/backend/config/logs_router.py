"""Operational log HTTP API (FastAPI router) for dev-mode observability.

Exposes the ``/api/logs`` endpoints from the OpenAI-compatible contract
(``documents/api/OPENAI_COMPATIBLE_CONTRACT.md``):

* ``GET /api/logs`` — list ``LogEntry`` rows (newest first), filtered by
  ``severity`` (comma-separated substrings, OR-matched) and optional
  ``since`` ISO8601 timestamp, capped by ``limit`` (default 100).
  Shape: ``{"object":"list","data":[{"id","timestamp","severity","source",
  "message","stacktrace"}]}``.
* ``POST /api/logs`` — accept a log written by the frontend and persist it via
  ``backend.log.log_event`` (the single ADR-011 choke point).

Rule R10: Pydantic **v1** ``BaseModel`` only.
Rule R12: every failure path logs to ``LogEntry`` (no silent failures).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, select

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


router = APIRouter()


def _row_to_dict(row: LogEntry) -> dict:
    return {
        "id": row.id,
        "timestamp": row.timestamp.isoformat() if row.timestamp else None,
        "severity": row.severity,
        "source": row.source,
        "message": row.message,
        "stacktrace": row.stacktrace,
    }


@router.get("/api/logs")
def list_logs(
    severity: Optional[str] = Query(None, description="substring filter; comma=OR"),
    limit: int = Query(100, ge=1, le=1000),
    since: Optional[str] = Query(None, description="ISO8601 lower bound"),
) -> dict:
    """Return stored ``LogEntry`` rows, newest first."""
    stmt = select(LogEntry)

    if severity:
        parts = [p.strip() for p in severity.split(",") if p.strip()]
        if parts:
            conds = [LogEntry.severity.ilike(f"%{p}%") for p in parts]
            stmt = stmt.where(or_(*conds))

    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            stmt = stmt.where(LogEntry.timestamp >= since_dt)
        except ValueError:  # noqa: BLE001 - invalid input, skip filter + log
            log_warning(
                f"GET /api/logs: invalid 'since' value: {since}",
                source="backend.config.logs_router",
            )

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


__all__ = ["router", "LogCreate"]

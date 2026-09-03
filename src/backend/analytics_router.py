"""Request-log + usage-analytics API (B5.6 / PRD §2.4.3 / FSD §2.4.3).

Endpoints (contract for fe-dev — shapes are EXACT):

* ``GET /api/request-logs?endpoint_id=&limit=50``
  -> ``{"object": "list", "data": [RequestLog DTO...]}``
  Newest first (id desc). ``limit`` default 50, capped at 500. Bad params ->
  400 OpenAI-style error envelope. Rows exist only while the
  ``request_log_enabled`` Setting is 'true' (debug gate).
* ``GET /api/analytics?range=day|week|month&group_by=provider|model``
  -> the ``backend.usage.analytics()`` dict:
  ``{"object":"analytics","range":...,"group_by":...,"buckets":[...],
     "totals":{...},"by_group":[...]}``
  day = 24 hourly buckets, week = 7 daily, month = 30 daily (see
  :func:`backend.usage.analytics` for the full contract).

Layering: aggregation lives in :mod:`backend.usage`; this module only
validates params, opens a session and serializes. R12/ADR-011: every call is
logged to ``LogEntry`` via ``backend.log``.

Pydantic **v1** only (rule R10): ``BaseModel`` + ``class Config``, no v2 syntax.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend import usage as usage_service
from backend.config.db import SessionLocal
from backend.log import log_info, log_warning
from backend.models import RequestLog

LOG_SOURCE = "backend.analytics.router"

router = APIRouter()

VALID_RANGES = ("day", "week", "month")
VALID_GROUP_BY = ("provider", "model")
DEFAULT_LIMIT = 50
MAX_LIMIT = 500


# --------------------------------------------------------------------------- #
# Pydantic v1 DTOs
# --------------------------------------------------------------------------- #
class RequestLogDTO(BaseModel):
    """One request-level debug row (ERD §RequestLog / PRD §2.4.3)."""

    id: int
    endpoint_id: Optional[int]
    model: str
    ts: Optional[str]  # ISO-8601 (naive UTC) or null
    duration_ms: int
    request: str  # JSON dump of headers (secrets redacted) + body, truncated
    response: str  # short response/error summary, truncated

    class Config:
        pass


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _error(status: int, message: str, code: str, etype: str = "invalid_request_error"):
    return JSONResponse(
        status_code=status,
        content={"error": {"message": message, "type": etype, "code": code}},
    )


def _parse_int_param(value: Optional[str], name: str):
    """Return ``(parsed_int_or_None, error_response_or_None)``."""
    if value is None or value == "":
        return None, None
    try:
        return int(value), None
    except (ValueError, TypeError):
        err = _error(400, f"{name} must be an integer", f"invalid_{name}")
        return None, err


def _parse_limit(value: Optional[str]):
    """Return ``(limit_or_None, error_or_None)``; default 50, capped at 500."""
    if value is None or value == "":
        return DEFAULT_LIMIT, None
    try:
        n = int(value)
    except (ValueError, TypeError):
        return None, _error(400, "limit must be an integer", "invalid_limit")
    if n < 1:
        return None, _error(400, "limit must be >= 1", "invalid_limit")
    return min(n, MAX_LIMIT), None


def _validate_choice(
    value: Optional[str], allowed: tuple, name: str, default: str
):
    """Return ``(choice_or_None, error_or_None)``; case-insensitive, default."""
    choice = (value or default).lower()
    if choice not in allowed:
        return None, _error(
            400, f"{name} must be one of {list(allowed)}", f"invalid_{name}"
        )
    return choice, None


def _row_to_dto(row: RequestLog) -> RequestLogDTO:
    return RequestLogDTO(
        id=row.id,
        endpoint_id=row.endpoint_id,
        model=row.model or "",
        ts=row.ts.isoformat() if row.ts is not None else None,
        duration_ms=int(row.duration_ms or 0),
        request=row.request or "",
        response=row.response or "",
    )


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
@router.get("/api/request-logs")
def get_request_logs(
    endpoint_id: Optional[str] = Query(None),
    limit: Optional[str] = Query(None),
) -> Any:
    """List RequestLog debug rows, newest first (``limit`` default 50, max 500)."""
    eid, err = _parse_int_param(endpoint_id, "endpoint_id")
    if err is not None:
        log_warning(
            f"GET /api/request-logs invalid endpoint_id={endpoint_id!r}",
            source=LOG_SOURCE,
        )
        return err
    n, err = _parse_limit(limit)
    if err is not None:
        log_warning(
            f"GET /api/request-logs invalid limit={limit!r}", source=LOG_SOURCE
        )
        return err

    with SessionLocal() as session:
        q = session.query(RequestLog)
        if eid is not None:
            q = q.filter(RequestLog.endpoint_id == eid)
        rows = q.order_by(RequestLog.id.desc()).limit(n).all()
        data = [_row_to_dto(r).dict() for r in rows]
    log_info(
        f"GET /api/request-logs endpoint_id={eid} limit={n} "
        f"-> {len(data)} record(s)",
        source=LOG_SOURCE,
    )
    return {"object": "list", "data": data}


@router.get("/api/analytics")
def get_analytics(
    range: Optional[str] = Query(None),
    group_by: Optional[str] = Query(None),
) -> Any:
    """Token & usage TRENDS over time buckets + totals + per-group breakdown.

    ``range``: day (24 hourly buckets) | week (7 daily) | month (30 daily),
    default day. ``group_by``: provider | model, default model. Full shape +
    semantics: :func:`backend.usage.analytics`.
    """
    rng, err = _validate_choice(range, VALID_RANGES, "range", usage_service.DEFAULT_RANGE)
    if err is not None:
        log_warning(
            f"GET /api/analytics invalid range={range!r}", source=LOG_SOURCE
        )
        return err
    gb, err = _validate_choice(
        group_by, VALID_GROUP_BY, "group_by", usage_service.DEFAULT_GROUP_BY
    )
    if err is not None:
        log_warning(
            f"GET /api/analytics invalid group_by={group_by!r}", source=LOG_SOURCE
        )
        return err

    with SessionLocal() as session:
        out = usage_service.analytics(session, range=rng, group_by=gb)
    log_info(
        f"GET /api/analytics range={rng} group_by={gb} "
        f"-> {out['totals']['requests']} request(s)",
        source=LOG_SOURCE,
    )
    return out


__all__ = [
    "router",
    "RequestLogDTO",
    "VALID_RANGES",
    "VALID_GROUP_BY",
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
]

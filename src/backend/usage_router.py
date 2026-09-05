"""Quota & usage API (B5.5 / PRD §2.4.2 / contract §Quota & Usage).

Endpoints (documents/api/OPENAI_COMPATIBLE_CONTRACT.md lines 95-98):

* ``GET /api/usage?provider_id=&endpoint_id=&range=day|week|month``
  -> ``{"object":"list","range":...,"data":[UsageRecord DTO...]}``
* ``GET /api/usage/summary?provider_id=&endpoint_id=&range=``
  -> the ``backend.usage.summarize()`` dict
* ``GET /api/quota?provider_id=``
  -> ``{"object":"list","data":[quota_status...]}``

All business logic lives in :mod:`backend.usage` (layering); this module only
validates params, opens a session and serializes. Invalid ``range`` /
non-integer ids -> 400 OpenAI-style error envelope. R12/ADR-011: every call
is logged to ``LogEntry`` via ``backend.log``.

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
from backend.models import UsageRecord

LOG_SOURCE = "backend.usage.router"

router = APIRouter()

VALID_RANGES = ("day", "week", "month")


# --------------------------------------------------------------------------- #
# Pydantic v1 DTOs
# --------------------------------------------------------------------------- #
class UsageRecordDTO(BaseModel):
    """One recorded usage row (telemetry/kuota per ERD §UsageRecord)."""

    id: int
    endpoint_id: Optional[int]
    provider_id: int
    account_id: Optional[int]
    model: str
    tokens_in: int
    tokens_out: int
    cost_est: float
    ts: Optional[str]  # ISO-8601 (naive UTC) or null

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


def _validate_range(range_value: Optional[str]):
    """Return ``(range_or_None, error_or_None)``; default 'day'."""
    rng = (range_value or usage_service.DEFAULT_RANGE).lower()
    if rng not in VALID_RANGES:
        return None, _error(
            400, f"range must be one of {list(VALID_RANGES)}", "invalid_range"
        )
    return rng, None


def _row_to_dto(row: UsageRecord) -> UsageRecordDTO:
    return UsageRecordDTO(
        id=row.id,
        endpoint_id=row.endpoint_id,
        provider_id=row.provider_id,
        account_id=row.account_id,
        model=row.model,
        tokens_in=int(row.tokens_in or 0),
        tokens_out=int(row.tokens_out or 0),
        cost_est=float(row.cost_est or 0.0),
        ts=row.ts.isoformat() if row.ts is not None else None,
    )


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
@router.get("/api/usage")
def get_usage(
    provider_id: Optional[str] = Query(None),
    endpoint_id: Optional[str] = Query(None),
    range: Optional[str] = Query(None),
) -> Any:
    """List raw UsageRecords within the rolling window (newest first)."""
    rng, err = _validate_range(range)
    if err is not None:
        log_warning(f"GET /api/usage invalid range={range!r}", source=LOG_SOURCE)
        return err
    pid, err = _parse_int_param(provider_id, "provider_id")
    if err is not None:
        log_warning(
            f"GET /api/usage invalid provider_id={provider_id!r}", source=LOG_SOURCE
        )
        return err
    eid, err = _parse_int_param(endpoint_id, "endpoint_id")
    if err is not None:
        log_warning(
            f"GET /api/usage invalid endpoint_id={endpoint_id!r}", source=LOG_SOURCE
        )
        return err

    since = usage_service.since_for_range(rng)
    with SessionLocal() as session:
        q = session.query(UsageRecord).filter(UsageRecord.ts >= since)
        if pid is not None:
            q = q.filter(UsageRecord.provider_id == pid)
        if eid is not None:
            q = q.filter(UsageRecord.endpoint_id == eid)
        rows = q.order_by(UsageRecord.id.desc()).all()
        data = [_row_to_dto(r).dict() for r in rows]
    log_info(
        f"GET /api/usage range={rng} provider_id={pid} endpoint_id={eid} "
        f"-> {len(data)} record(s)",
        source=LOG_SOURCE,
    )
    return {"object": "list", "range": rng, "data": data}


@router.get("/api/usage/summary")
def get_usage_summary(
    provider_id: Optional[str] = Query(None),
    endpoint_id: Optional[str] = Query(None),
    range: Optional[str] = Query(None),
) -> Any:
    """Aggregated totals + by_provider + by_model within the window."""
    rng, err = _validate_range(range)
    if err is not None:
        log_warning(
            f"GET /api/usage/summary invalid range={range!r}", source=LOG_SOURCE
        )
        return err
    pid, err = _parse_int_param(provider_id, "provider_id")
    if err is not None:
        log_warning(
            f"GET /api/usage/summary invalid provider_id={provider_id!r}",
            source=LOG_SOURCE,
        )
        return err
    eid, err = _parse_int_param(endpoint_id, "endpoint_id")
    if err is not None:
        log_warning(
            f"GET /api/usage/summary invalid endpoint_id={endpoint_id!r}",
            source=LOG_SOURCE,
        )
        return err

    with SessionLocal() as session:
        summary = usage_service.summarize(
            session, provider_id=pid, endpoint_id=eid, range=rng
        )
    log_info(
        f"GET /api/usage/summary range={rng} provider_id={pid} "
        f"-> {summary['totals']['requests']} request(s)",
        source=LOG_SOURCE,
    )
    return summary


@router.get("/api/quota")
def get_quota(provider_id: Optional[str] = Query(None)) -> Any:
    """Remaining quota + reset countdown per provider (B5.5 / PRD §2.4.2)."""
    pid, err = _parse_int_param(provider_id, "provider_id")
    if err is not None:
        log_warning(
            f"GET /api/quota invalid provider_id={provider_id!r}", source=LOG_SOURCE
        )
        return err
    with SessionLocal() as session:
        data = usage_service.quota_status(session, provider_id=pid)
    log_info(
        f"GET /api/quota provider_id={pid} -> {len(data)} provider(s)",
        source=LOG_SOURCE,
    )
    return {"object": "list", "data": data}


__all__ = ["router", "UsageRecordDTO", "VALID_RANGES"]

"""Self-Heal API (task B4.1) — backend only. Frontend is a later step.

Exposes:
- ``GET /api/self-heal/agentic-cli`` -> ``{"available": bool, "cli": str|null}``
- ``POST /api/self-heal/run``      -> ``RunResultDTO`` (the dict from
  ``run_self_heal``), or a 500 error envelope on unexpected failure.

ADR-011 / R12: every call + result is logged via ``backend.log`` with
``source="backend.selfheal.router"``. No bare ``except: pass`` — unexpected
failures are logged via ``log_error_exc`` and returned as a structured
``self_heal_failed`` envelope.
Pydantic **v1** only (rule R10): ``BaseModel`` + ``class Config``.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.log import log_error_exc, log_info
from backend.selfheal import detect_agentic_cli, run_self_heal

LOG_SOURCE = "backend.selfheal.router"

router = APIRouter()


# --------------------------------------------------------------------------- #
# Pydantic v1 DTOs
# --------------------------------------------------------------------------- #
class AgenticCliDTO(BaseModel):
    available: bool
    cli: Optional[str]

    class Config:
        pass


class RunResultDTO(BaseModel):
    ok: bool
    reason: Optional[str] = None
    merged: Optional[bool] = None
    remaining: Optional[int] = None
    iterations: Optional[int] = None
    detail: Optional[str] = None

    class Config:
        pass


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@router.get("/api/self-heal/agentic-cli")
def agentic_cli() -> dict:
    """Report whether an agentic CLI binary is installed on PATH."""
    cli = detect_agentic_cli()
    log_info(
        f"self-heal agentic-cli check: available={cli is not None} cli={cli}",
        source=LOG_SOURCE,
    )
    return AgenticCliDTO(available=cli is not None, cli=cli).dict()


@router.post("/api/self-heal/run")
def run() -> dict:
    """Run the self-heal orchestration synchronously and return its status."""
    log_info("self-heal run requested", source=LOG_SOURCE)
    try:
        result = run_self_heal()
    except Exception as exc:  # never crash the endpoint
        log_error_exc(
            "self-heal run unexpected failure",
            source=LOG_SOURCE,
            exc=exc,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": str(exc),
                    "type": "internal",
                    "code": "self_heal_failed",
                }
            },
        )
    log_info(
        f"self-heal run result ok={result.get('ok')}",
        source=LOG_SOURCE,
        context=result,
    )
    return result


__all__ = ["router", "AgenticCliDTO", "RunResultDTO"]

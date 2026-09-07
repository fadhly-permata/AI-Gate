"""Self-Heal API (task B4.1) — backend only. Frontend is a later step.

Exposes:
- ``GET /api/self-heal/agentic-cli`` -> ``{"available": bool, "cli": str|null}``
- ``POST /api/self-heal/run``        -> starts the orchestration in a daemon
  thread (the agentic CLI runs visibly inside the ``self-heal`` terminal tab)
  and returns immediately ``200 {"ok": true, "started": true, "tab":
  "self-heal"}``; ``409`` with ``{"ok": false, "reason": "already_running",
  "tab": "self-heal"}`` when a run is already in flight.
- ``GET /api/self-heal/status``      -> ``{"running": bool, "last": <dict|null>``
  where ``last`` is the most recent ``run_self_heal`` result (all its shapes
  preserved).

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
from backend.selfheal import (
    detect_agentic_cli,
    get_self_heal_cli_setting,
    get_self_heal_model_setting,
    heal_status,
    list_agentic_clis,
    list_self_heal_models,
    set_self_heal_cli_setting,
    set_self_heal_model_setting,
    start_self_heal,
)

LOG_SOURCE = "backend.selfheal.router"

router = APIRouter()

# Tab key of the visible terminal the run streams into (selfheal.HEAL_TAB_KEY;
# mirrored literally so the router stays import-light in tests).
SELF_HEAL_TAB = "self-heal"


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


class StartRunDTO(BaseModel):
    started: bool
    tab: Optional[str] = None
    reason: Optional[str] = None

    class Config:
        pass


class StatusDTO(BaseModel):
    running: bool
    # Raw passthrough of the last ``run_self_heal`` result — every documented
    # shape must survive verbatim (RunResultDTO above documents that schema;
    # DTO-serializing would inject null keys and alter the shapes).
    last: Optional[dict] = None
    # Richer live progress snapshot for the frontend preview.
    progress: Optional[dict] = None

    class Config:
        pass


class RunRequestBody(BaseModel):
    cli: str = ""
    model: str = ""

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


@router.get("/api/self-heal/clis")
def clis() -> dict:
    """List every agentic CLI found on PATH plus the persisted selection."""
    found = list_agentic_clis()
    selected = get_self_heal_cli_setting()
    log_info(
        f"self-heal clis: found={found} selected={selected!r}",
        source=LOG_SOURCE,
    )
    return {"clis": found, "selected": selected}


@router.get("/api/self-heal/models")
def models() -> dict:
    """List models grouped by provider/combo (dict list) plus the selection.

    Each entry is ``{"value", "label", "group"}``; ``group`` is the provider
    name or the ``"__combos__"`` sentinel. ``selected`` stays the stored bare
    model-name value.
    """
    found = list_self_heal_models()
    selected = get_self_heal_model_setting()
    log_info(
        f"self-heal models: count={len(found)} selected={selected!r}",
        source=LOG_SOURCE,
    )
    return {"models": found, "selected": selected}


@router.post("/api/self-heal/run")
def run(body: Optional[RunRequestBody] = None) -> dict:
    """Start a self-heal run asynchronously (visible in the self-heal tab).

    Accepts an optional ``{"cli": str, "model": str}`` body (both may be "" to
    use the persisted setting / auto-detect). When the body is absent, empty
    values are used (no override). The chosen cli+model are persisted to
    settings before the run starts.
    """
    cli = body.cli if body else ""
    model = body.model if body else ""
    log_info(
        f"self-heal run requested cli={cli!r} model={model!r}",
        source=LOG_SOURCE,
    )
    try:
        set_self_heal_cli_setting(cli or "")
        set_self_heal_model_setting(model or "")
        outcome = start_self_heal(cli=cli or None, model=model or None)
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
    # Contract: immediate acceptance (200) when a thread was started;
    # a second concurrent start is a 409 conflict.
    if not outcome.get("started"):
        log_info(
            f"self-heal run rejected: {outcome.get('reason')}",
            source=LOG_SOURCE,
        )
        return JSONResponse(
            status_code=409,
            content={
                "ok": False,
                "reason": outcome.get("reason", "already_running"),
                "tab": SELF_HEAL_TAB,
            },
        )
    return {
        "ok": True,
        "started": True,
        "tab": outcome.get("tab", SELF_HEAL_TAB),
    }


@router.get("/api/self-heal/status")
def status() -> dict:
    """Report whether a run is active and the last finished run's result.

    Read-only poll (the frontend may call it frequently): deliberately NOT
    persisted via ``backend.log`` — R12 keeps LogEntry rows for meaningful
    events, and this is routine polling.
    """
    snap = heal_status()
    return StatusDTO(
        running=bool(snap.get("running")),
        last=snap.get("last"),
        progress=snap.get("progress"),
    ).dict()


__all__ = ["router", "AgenticCliDTO", "RunResultDTO", "StartRunDTO", "StatusDTO"]

"""CLI Tools API (task B3.4): list preset groups + resolve a tool for launch.

Backend-only. This does NOT spawn anything — it returns the data the frontend
(fe-dev, later step) uses to open a PTY tab with env injected (FSD §2.6 / ADR:
CLI auto-launcher). Scope is: expose preset groups/tools and a ``resolve``
endpoint that checks the binary and returns run/install commands + env
injection values.

Contracts:
- ``GET /api/cli-tools`` -> ``{"object":"list","data":[GroupDTO,...]}``
- ``POST /api/cli-tools/resolve`` -> ``ResolveDTO`` (or 404 envelope
  ``code:"tool_not_found"``).

ADR-007 / R11: ``internal_api_key`` returned **plaintext** (it is injected as
``OPENAI_API_KEY``). ADR-011 / R12: resolve is logged via ``backend.log`` with
``source="backend.cli_tools.router"``; no bare ``except: pass``.
Pydantic **v1** only (rule R10): ``BaseModel`` + ``class Config``.
"""

from __future__ import annotations

import shutil
from typing import Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config.db import SessionLocal
from backend.config.settings import get as get_setting
from backend.log import log_info
from backend.models import CLITool, CLIToolGroup, Endpoint

LOG_SOURCE = "backend.cli_tools.router"

# Default gateway base when no ``gateway_base_url`` Setting exists (FSD §2.4/2.6).
DEFAULT_GATEWAY_BASE = "http://localhost:8080/v1"

router = APIRouter()


# --------------------------------------------------------------------------- #
# Pydantic v1 DTOs
# --------------------------------------------------------------------------- #
class ToolDTO(BaseModel):
    id: int
    name: str
    binary_name: str
    install_command: str
    default_flags: str
    enabled: bool

    class Config:
        pass


class GroupDTO(BaseModel):
    code: str
    name: str
    tools: List[ToolDTO]

    class Config:
        pass


class ResolveRequest(BaseModel):
    tool: str  # tool name or id
    model: Optional[str] = None

    class Config:
        pass


class ResolveDTO(BaseModel):
    binary_found: bool
    install_command: Optional[str]
    run_command: str
    env: Dict[str, str]
    model: Optional[str]

    class Config:
        pass


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _tool_to_dto(tool: CLITool) -> ToolDTO:
    return ToolDTO(
        id=tool.id,
        name=tool.name,
        binary_name=tool.binary_name,
        install_command=tool.install_command,
        default_flags=tool.default_flags,
        enabled=bool(tool.enabled),
    )


def _find_tool(session: Session, ref: str) -> Optional[CLITool]:
    """Locate a ``CLITool`` by integer id (if ``ref`` parses) or by ``name``."""
    try:
        tid = int(ref)
    except (ValueError, TypeError):
        # Not an id lookup -> fall back to name match.
        return session.query(CLITool).filter(CLITool.name == ref).first()
    return session.get(CLITool, tid)


def _resolve_gateway_base(session: Session) -> str:
    """Read ``gateway_base_url`` Setting; fall back to default if absent."""
    try:
        val = get_setting("gateway_base_url", session=session)
    except Exception:  # noqa: BLE001 - never crash resolve over a config read
        val = None
    return val if val else DEFAULT_GATEWAY_BASE


def _resolve_internal_key(session: Session) -> str:
    """Plaintext ``internal_api_key`` of first access-controlled Endpoint (R11).

    Returns ``""`` when no access-controlled endpoint exists.
    """
    ep = (
        session.query(Endpoint)
        .filter(Endpoint.access_control_enabled == True)  # noqa: E712
        .order_by(Endpoint.id)
        .first()
    )
    if ep is None:
        return ""
    return ep.internal_api_key  # ADR-007: returned plaintext


def _not_found(message: str, code: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "error": {"message": message, "type": "not_found", "code": code}
        },
    )


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@router.get("/api/cli-tools")
def list_cli_tools() -> dict:
    """Return all preset CLI tool groups (ordered by display_priority) + tools."""
    with SessionLocal() as session:
        groups = (
            session.query(CLIToolGroup)
            .order_by(CLIToolGroup.display_priority)
            .all()
        )
        data = []
        for g in groups:
            tools = (
                session.query(CLITool)
                .filter_by(group_id=g.id)
                .order_by(CLITool.id)
                .all()
            )
            data.append(
                GroupDTO(
                    code=g.code,
                    name=g.name,
                    tools=[_tool_to_dto(t) for t in tools],
                ).dict()
            )
    log_info(
        f"listed {len(data)} cli tool group(s)",
        source=LOG_SOURCE,
    )
    return {"object": "list", "data": data}


@router.post("/api/cli-tools/resolve")
def resolve_cli_tool(req: ResolveRequest) -> dict:
    """Resolve a tool for launch: check binary, build run/install + env.

    ``binary_found`` = ``shutil.which(tool.binary_name) is not None``.
    When not found, ``install_command`` is returned; otherwise it is null.
    ``env`` carries ``OPENAI_API_BASE`` (gateway) + ``OPENAI_API_KEY``
    (plaintext internal key, ADR-007). Unknown tool -> 404 ``tool_not_found``.
    """
    with SessionLocal() as session:
        tool = _find_tool(session, req.tool)
        if tool is None:
            log_info(
                f"resolve: tool '{req.tool}' not found",
                source=LOG_SOURCE,
            )
            return _not_found(
                f"tool '{req.tool}' not found", "tool_not_found"
            )

        binary_found = shutil.which(tool.binary_name) is not None
        install_command = tool.install_command if not binary_found else None

        run_command = tool.binary_name
        if tool.default_flags:
            run_command += " " + tool.default_flags
        if req.model:
            run_command += f" --model {req.model}"

        env = {
            "OPENAI_API_BASE": _resolve_gateway_base(session),
            "OPENAI_API_KEY": _resolve_internal_key(session),
        }

        result = ResolveDTO(
            binary_found=binary_found,
            install_command=install_command,
            run_command=run_command,
            env=env,
            model=req.model,
        ).dict()

        log_info(
            f"resolve: tool='{req.tool}' binary_found={binary_found} "
            f"model={req.model}",
            source=LOG_SOURCE,
            context={"run_command": run_command},
        )
        return result


__all__ = ["router"]

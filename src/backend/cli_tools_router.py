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

import os
import shutil
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config.db import SessionLocal
from backend.config.settings import get as get_setting
from backend.log import log_info, log_warning
from backend.models import CLITool, CLIToolGroup, Endpoint

LOG_SOURCE = "backend.cli_tools.router"

# Default gateway base when no ``gateway_base_url`` Setting exists (FSD §2.4/2.6).
DEFAULT_GATEWAY_BASE = "http://localhost:8080/v1"

# Placeholder OPENAI_API_KEY handed to a launched CLI when NO access-controlled
# Endpoint exists. The gateway ignores this key entirely while access control is
# off, but CLIs like aider refuse to start with an empty ``--openai-api-key`` /
# ``OPENAI_API_KEY``. A non-empty dummy lets them boot; it is never a real secret.
PLACEHOLDER_API_KEY = "aigate-local"

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
    """Launch payload for one tool.

    ``binary_found`` is a **hint** only (server-side PATH probe — see
    ``_which_with_extra_paths``): the PTY the tool is finally spawned in has the
    user's real login PATH, which the gateway process may not. The frontend
    therefore branches on the binary itself::

        if command -v <binary_name>; then <run_command>; else <install_command>; fi

    which is why ``install_command`` is ALWAYS present (never nulled when the
    binary happens to be found) and ``binary_name`` is exposed.
    """

    binary_found: bool
    binary_name: str
    install_command: str
    run_command: str
    env: Dict[str, str]
    model: Optional[str]

    class Config:
        pass


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
# Extra directories searched when probing for a CLI binary.
#
# WHY: ``shutil.which`` uses the SERVER process's PATH. aigate is often started
# from a shell whose PATH does not include where the user installed a tool
# (pip/pipx ``~/.local/bin``, ``~/.cargo/bin``, npm global, a pyenv shim, the
# Termux prefix...). The tool is then reported as missing and the frontend runs
# its INSTALL command even though the tool is installed and would run fine in
# the interactive PTY (which has the real login PATH). Searching these common
# install dirs server-side makes the hint far more accurate. Still only a hint:
# the frontend re-checks with ``command -v <binary_name>`` inside the PTY.
_EXTRA_PATH_DIRS: Tuple[str, ...] = (
    "~/.local/bin",  # pip --user / pipx
    "~/.cargo/bin",  # rust/cargo installs
    "~/bin",  # classic per-user bin
    "$PREFIX/bin",  # Termux prefix bin (pkg installs)
    "/data/data/com.termux/files/usr/bin",  # Termux absolute fallback
    "~/.pyenv/shims",  # pyenv-managed python CLIs
    "~/.npm-global/bin",  # npm global (custom prefix)
    "~/.deno/bin",  # deno install
    "~/go/bin",  # go install
    "/usr/local/bin",  # system-wide local installs
)


def _extra_search_paths() -> List[str]:
    """Resolve ``_EXTRA_PATH_DIRS`` to the ones that actually exist right now.

    ``~`` expands to ``$HOME`` and ``$PREFIX`` to the environment's Termux
    prefix (absent on non-Termux hosts, so that entry simply drops out). Best
    effort: a missing/unreadable dir is skipped, never an error.
    """
    out: List[str] = []
    seen = set()
    for raw in _EXTRA_PATH_DIRS:
        path = os.path.expandvars(os.path.expanduser(raw))
        if not path or path in seen:
            continue
        seen.add(path)
        try:
            if os.path.isdir(path):
                out.append(path)
        except OSError as exc:  # R12: log, never swallow silently
            log_warning(
                f"cli probe: cannot stat extra path '{path}': {exc}",
                source=LOG_SOURCE,
            )
    return out


def _which_with_extra_paths(binary: str) -> Optional[str]:
    """``shutil.which`` over PATH + common user install dirs.

    Returns the resolved absolute path, or ``None`` when the binary is not found
    anywhere. The extended PATH is ``os.environ["PATH"]`` first (so the normal
    lookup order wins) followed by the existing dirs from
    ``_extra_search_paths()``.
    """
    if not binary:
        return None
    base = os.environ.get("PATH", "")
    extended = os.pathsep.join([p for p in [base] if p] + _extra_search_paths())
    return shutil.which(binary, path=extended)


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

    Returns ``PLACEHOLDER_API_KEY`` when no access-controlled endpoint exists:
    the gateway ignores the key while access control is off, but CLIs like aider
    refuse to launch with an empty key, so a non-empty dummy is injected instead.
    """
    ep = (
        session.query(Endpoint)
        .filter(Endpoint.access_control_enabled == True)  # noqa: E712
        .order_by(Endpoint.id)
        .first()
    )
    if ep is None:
        return PLACEHOLDER_API_KEY
    return ep.internal_api_key  # ADR-007: returned plaintext


def _not_found(message: str, code: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "error": {"message": message, "type": "not_found", "code": code}
        },
    )


# --------------------------------------------------------------------------- #
# Per-tool launch strategy
#
# Each CLI tool is launched with a command built by a strategy keyed on the
# tool's ``binary_name``. ``aider`` is the currently-known tool that needs the
# explicit custom-endpoint flags (``--openai-api-base`` / ``--openai-api-key`` /
# ``--model openai/<model>``); every other tool falls back to the generic
# ``<binary> <flags> --model <model>`` form and relies on the injected
# ``OPENAI_API_BASE`` / ``OPENAI_API_KEY`` env. Add confirmed tools to
# ``_LAUNCH_BUILDERS`` as their custom-endpoint form is verified.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class _LaunchCtx:
    """Inputs a launch builder needs to compose a tool's run command."""

    binary_name: str
    default_flags: str
    model: Optional[str]  # the aigate model ref exactly as requested
    raw_model: Optional[str]  # ref stripped to what the CLI sends upstream
    base: str  # gateway base url (also injected as OPENAI_API_BASE)
    key: str  # plaintext internal key (also injected as OPENAI_API_KEY)


def _raw_model_for_ref(model: Optional[str]) -> Optional[str]:
    """Reduce an aigate model ref to the concrete id a CLI should send upstream.

    * ``provider:<name>:<m>`` -> ``<m>``
    * ``provider:<name>``     -> ``None`` (no concrete model chosen)
    * ``combo:<name>``        -> ``combo:<name>`` (kept verbatim)
    * bare ``<m>``            -> ``<m>`` (aigate now bare-resolves it)
    """
    if not model:
        return None
    if model.startswith("provider:"):
        rest = model[len("provider:"):]
        if ":" in rest:
            _name, model_id = rest.split(":", 1)
            return model_id
        return None  # provider:<name> with no model segment
    return model  # combo:<name> or a bare model id


def _generic_builder(ctx: _LaunchCtx) -> str:
    """Default launch form: ``<binary> <flags> --model <model>`` + env injection.

    The tool reads ``OPENAI_API_BASE`` / ``OPENAI_API_KEY`` from the injected
    env; ``--model`` carries the aigate ref verbatim (aigate resolves it).
    """
    parts: List[str] = [ctx.binary_name]
    if ctx.default_flags:
        parts.append(ctx.default_flags)
    if ctx.model:
        parts += ["--model", ctx.model]
    return " ".join(parts)


def _aider_builder(ctx: _LaunchCtx) -> str:
    """aider's documented OpenAI-compatible form (custom endpoint + model).

    The ``openai/`` prefix makes aider accept an arbitrary model name and
    forward ``<raw_model>`` to aigate (which now bare-resolves it). When no
    concrete model was chosen (``provider:<name>``), the ``--model`` part is
    omitted so aider uses its own default / aigate's provider default.
    """
    parts: List[str] = [ctx.binary_name]
    if ctx.default_flags:
        parts.append(ctx.default_flags)
    parts += ["--openai-api-base", ctx.base, "--openai-api-key", ctx.key]
    if ctx.raw_model:
        parts += ["--model", f"openai/{ctx.raw_model}"]
    return " ".join(parts)


# binary_name -> builder. Anything absent uses ``_generic_builder``.
_LAUNCH_BUILDERS: Dict[str, Callable[[_LaunchCtx], str]] = {
    "aider": _aider_builder,
}


def _build_run_command(ctx: _LaunchCtx) -> str:
    """Dispatch to the tool's launch builder (aider form) or the generic one."""
    builder = _LAUNCH_BUILDERS.get(ctx.binary_name, _generic_builder)
    return builder(ctx)


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

    ``binary_found`` = ``_which_with_extra_paths(tool.binary_name) is not None``
    — PATH plus common user install dirs. It is a HINT only: the server process
    may still not see a binary the interactive PTY can run, so the frontend
    re-checks with ``command -v <binary_name>`` inside the PTY and only installs
    when that fails. ``install_command`` is therefore ALWAYS returned (the tool's
    install string, never null), together with ``binary_name``.
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

        binary_path = _which_with_extra_paths(tool.binary_name)
        binary_found = binary_path is not None
        # Always expose the install command: the frontend's PTY-side
        # ``command -v`` check is authoritative, so it needs the string even when
        # the server-side hint says the binary is present.
        install_command = tool.install_command or ""

        base = _resolve_gateway_base(session)
        key = _resolve_internal_key(session)
        env = {
            "OPENAI_API_BASE": base,
            "OPENAI_API_KEY": key,
        }

        ctx = _LaunchCtx(
            binary_name=tool.binary_name,
            default_flags=tool.default_flags or "",
            model=req.model,
            raw_model=_raw_model_for_ref(req.model),
            base=base,
            key=key,
        )
        run_command = _build_run_command(ctx)

        result = ResolveDTO(
            binary_found=binary_found,
            binary_name=tool.binary_name,
            install_command=install_command,
            run_command=run_command,
            env=env,
            model=req.model,
        ).dict()

        # R12 / skill: never persist a secret to LogEntry. aider embeds the
        # plaintext key in run_command, so mask it in the LOGGED copy only — the
        # API response above still returns it plaintext per ADR-007.
        logged_command = run_command.replace(key, "***") if key else run_command
        log_info(
            f"resolve: tool='{req.tool}' binary='{tool.binary_name}' "
            f"binary_found={binary_found} path={binary_path} model={req.model}",
            source=LOG_SOURCE,
            context={"run_command": logged_command},
        )
        return result


__all__ = ["router"]

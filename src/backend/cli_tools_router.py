"""CLI Tools API (task B3.4): list preset groups + resolve a tool for launch.

Backend-only. This does NOT spawn anything — it returns the data the frontend
(fe-dev, later step) uses to open a PTY tab with env injected (FSD §2.6 / ADR:
CLI auto-launcher). Scope is: expose preset groups/tools and a ``resolve``
endpoint that checks the binary and returns run/install commands + env
injection values.

Contracts:
- ``GET /api/cli-tools`` -> ``{"object":"list","data":[GroupDTO,...]}``
- ``POST /api/cli-tools/resolve`` -> ``ResolveDTO`` (or 404 envelope
  ``code:"tool_not_found"``, or 409 envelope ``code:"tool_unsupported"`` for a
  tool without a verified launch form).

ADR-007 / R11: ``internal_api_key`` returned **plaintext** (it is injected as
``OPENAI_API_KEY``). ADR-011 / R12: resolve is logged via ``backend.log`` with
``source="backend.cli_tools.router"``; no bare ``except: pass``.
Pydantic **v1** only (rule R10): ``BaseModel`` + ``class Config``.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config.db import SessionLocal
from backend.config.settings import get as get_setting
from backend.cli_presets import (
    LAUNCH_VERIFIED,
    install_command_for,
    launch_support_for,
)
from backend.log import log_info
from backend.models import CLITool, CLIToolGroup, Endpoint, Provider, ProviderModel
from backend.paths import extra_path_dirs as _extra_path_dirs_impl
from backend.paths import is_termux

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
    # Launch support (see ``cli_presets.LAUNCH_SUPPORT``): ``verified`` tools have
    # a documented launch builder and speak the gateway's OpenAI format;
    # ``pending`` / ``unsupported`` are struck through in the UI and refused by
    # ``resolve``. ``launch_reason`` is a stable code the frontend translates.
    launch_mode: str = "pending"
    launch_reason: str = ""

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
#
# SINGLE SOURCE OF TRUTH: the dir list + existence filtering live in
# ``backend.paths`` so CLI detection and the PTY spawn env (terminal/pty.py)
# always agree on which dirs count as "the user's install dirs".


def _extra_search_paths() -> List[str]:
    """Existing user-install dirs (see ``backend.paths.extra_path_dirs``)."""
    return _extra_path_dirs_impl()


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


def _tool_to_dto(tool: CLITool, termux: Optional[bool] = None) -> ToolDTO:
    support = launch_support_for(tool.name)
    if termux is None:
        termux = is_termux()
    return ToolDTO(
        id=tool.id,
        name=tool.name,
        binary_name=tool.binary_name,
        install_command=install_command_for(
            tool.name, tool.install_command or "", termux=termux
        ),
        default_flags=tool.default_flags,
        enabled=bool(tool.enabled),
        launch_mode=support.mode,
        launch_reason=support.reason,
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


def _unsupported(tool_name: str, mode: str, reason: str) -> JSONResponse:
    """Refuse to build a launch command for a tool we cannot serve yet.

    WHY 409 and not a silent generic command: the generic
    ``<binary> --model <ref>`` form is a guess, and guessing is what made most
    presets fail in the terminal (unknown flag / wrong wire format). The UI
    strikes these names through, so a refusal here is only reachable through a
    stale client or a direct API call.
    """
    return JSONResponse(
        status_code=409,
        content={
            "error": {
                "message": (
                    f"tool '{tool_name}' has no verified launch form for the "
                    f"aigate gateway yet (mode={mode}"
                    + (f" reason={reason})" if reason else ")")
                ),
                "type": "invalid_request_error",
                "code": "tool_unsupported",
            }
        },
    )


# --------------------------------------------------------------------------- #
# Per-tool launch strategy
#
# Each CLI tool is launched with a command built by a strategy keyed on the
# tool's ``binary_name``. A tool is only RESOLVABLE when ``cli_presets`` marks
# it ``verified`` — meaning a builder exists here (or the tool genuinely needs
# nothing but the injected ``OPENAI_API_BASE``/``OPENAI_API_KEY`` env) and the
# form is documented by the upstream project. ``_generic_builder`` is the
# fallback for verified tools without a dedicated builder, NOT a licence to
# launch unverified tools with guessed flags (that is what broke most presets:
# e.g. ``claude openai-compatible`` is not a real flag).
#
# Confirmed so far: ``aider`` (custom-endpoint flags), ``opencode``
# (``opencode.json`` custom provider + interactive TUI). Add builders to
# ``_LAUNCH_BUILDERS`` one tool at a time and flip its preset to ``verified``.
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
    # Discovered model ids for the provider named in ``model`` (empty when the
    # ref is not a ``provider:<name>`` form or nothing was discovered). Used by
    # builders that must enumerate the provider's models in a config file
    # (e.g. opencode's ``opencode.json``).
    provider_models: List[str] = field(default_factory=list)


def _provider_name_for_ref(model: Optional[str]) -> Optional[str]:
    """Extract the provider name from a ``provider:<name>[:<model>]`` ref.

    Returns ``None`` for bare model ids / combo refs (no provider segment).
    """
    if not model or not model.startswith("provider:"):
        return None
    rest = model[len("provider:"):]
    if ":" in rest:
        name, _mid = rest.split(":", 1)
        return name or None
    return rest or None


def _discovered_models_for_ref(
    session: Session, model: Optional[str]
) -> List[str]:
    """Discovered ``ProviderModel.model_id`` list for the provider in ``model``.

    Empty when the ref carries no provider, the provider is unknown, or nothing
    has been discovered for it. Ordered by id (stable).
    """
    name = _provider_name_for_ref(model)
    if not name:
        return []
    provider = session.query(Provider).filter(Provider.name == name).first()
    if provider is None:
        return []
    rows = (
        session.query(ProviderModel)
        .filter(ProviderModel.provider_id == provider.id)
        .order_by(ProviderModel.id)
        .all()
    )
    return [r.model_id for r in rows]


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


# Fixed provider id opencode uses for the aigate gateway (model selected as
# ``aigate/<model_id>``). Kept in sync with the ``opencode.json`` we write.
_OPENCODE_PROVIDER_ID = "aigate"


def _opencode_builder(ctx: _LaunchCtx) -> str:
    """opencode's documented custom-provider form (opencode.ai/docs/providers).

    opencode reads ``opencode.json`` from the working dir. We write a custom
    OpenAI-compatible provider (npm ``@ai-sdk/openai-compatible``) whose
    ``options.baseURL`` points at the aigate gateway and whose ``models`` map
    lists the provider's discovered model ids (falling back to just the
    requested model when nothing was discovered). The JSON is built with
    ``json.dumps`` (never string-concatenated) so quoting/escaping is correct,
    and handed to the shell via a single-quoted heredoc (``<<'AIGATE_EOF'``) so
    nothing is expanded. We set BOTH ``options.apiKey`` and rely on the injected
    ``OPENAI_API_KEY`` env (belt-and-suspenders; the gateway ignores the key
    while access control is off).

    Launch: plain ``opencode`` (the interactive TUI) — ``opencode run`` is
    one-shot and would sit waiting on stdin inside the PTY. The model is
    preselected via the top-level ``model`` key of the generated config
    (``aigate/<modelID>``, opencode docs: top-level ``model`` = default model,
    format ``providerID/modelID``). When no concrete model was chosen, no
    ``model`` key is written and the TUI still opens with whatever config
    exists. The env exports (OPENAI_API_BASE/KEY) are injected by the caller
    exactly as for aider — this builder only emits the config write + the
    command.

    Combo refs (``combo:<name>``): the combo is exposed as a selectable model id
    (key ``combo:<name>``, name identical) so opencode can DISCOVER + SELECT it;
    the gateway resolver already routes ``combo:<name>`` via the combo, so the
    default model is ``aigate/combo:<name>``.
    """
    model = ctx.model or ""
    if model.startswith("combo:"):
        # Combo ref -> the combo itself is the selectable model id (verbatim).
        model_ids = [model]
    else:
        # Provider / bare ref -> enumerate the provider's discovered models so
        # the whole provider is browsable; fall back to the requested model.
        model_ids = list(ctx.provider_models)
        if not model_ids and ctx.raw_model:
            model_ids = [ctx.raw_model]

    config: Dict[str, object] = {
        "$schema": "https://opencode.ai/config.json",
    }
    if ctx.raw_model:
        # Top-level default model: providerID/modelID (raw ref, same reduction
        # as the models map — combo refs stay ``combo:<name>`` verbatim).
        config["model"] = f"{_OPENCODE_PROVIDER_ID}/{ctx.raw_model}"
    config["provider"] = {
        _OPENCODE_PROVIDER_ID: {
            "npm": "@ai-sdk/openai-compatible",
            "name": _OPENCODE_PROVIDER_ID,
            "options": {"baseURL": ctx.base, "apiKey": ctx.key},
            "models": {mid: {"name": mid} for mid in model_ids},
        }
    }
    cfg_json = json.dumps(config, indent=2)

    # Single-quoted heredoc delimiter -> the shell writes the JSON verbatim.
    # Always launch the interactive TUI; the model comes from the config.
    cmd = "cat > opencode.json <<'AIGATE_EOF'\n" + cfg_json + "\nAIGATE_EOF\n"
    cmd += "opencode"
    return cmd


# Fixed client name aichat registers for the aigate gateway; model ids then look
# like ``aigate:<modelID>``. aichat splits the id on the FIRST separator, so a
# combo ref stays intact as the model part (``aigate:combo:Test``).
_AICHAT_CLIENT_NAME = "aigate"
# Generated config lives in the working dir and is pointed at via
# ``AICHAT_CONFIG_FILE`` (honoured by aichat's config loader) — the user's own
# ``~/.config/aichat/config.yaml`` is never touched.
_AICHAT_CONFIG_FILE = "aichat-aigate.yaml"


def _yaml_str(value: Optional[str]) -> str:
    """Quote one scalar for the generated YAML (double-quoted + escaped).

    Values come from the DB (base url, api key, model ids), so they are never
    interpolated bare: backslash, quote and control chars are escaped and the
    result is always a quoted string.
    """
    text = "" if value is None else str(value)
    escaped = (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def _aichat_builder(ctx: _LaunchCtx) -> str:
    """aichat's openai-compatible client form (verified against aichat 0.30.0).

    aichat has no ``custom_providers``/``providers`` key (both fail to load);
    the config field is ``clients:`` — a list of internally-tagged client
    configs. A client declares ``type: openai-compatible``, a ``name``, the
    ``api_base`` / ``api_key`` of the gateway, and the ``models`` it exposes
    (each a ``ModelData`` mapping — a bare string is rejected). Verified on the
    device: ``aichat --dry-run`` resolves ``aigate:<model>`` and a real call
    reached the gateway (the only error came from the upstream provider).

    The whole provider is enumerated when the models were discovered, so the
    user can switch inside aichat (``/model``) without relaunching. The
    requested model is preselected through the top-level ``model`` key.
    """
    model_ids: List[str] = list(ctx.provider_models)
    if ctx.raw_model and ctx.raw_model not in model_ids:
        model_ids.insert(0, ctx.raw_model)

    lines: List[str] = []
    if ctx.raw_model:
        # aichat model ids are `<client-name>:<model>` (it splits on the FIRST
        # colon, so a `combo:<name>` ref survives intact as the model part).
        lines.append(
            f"model: {_yaml_str(f'{_AICHAT_CLIENT_NAME}:{ctx.raw_model}')}"
        )
    lines += [
        "clients:",
        "  - type: openai-compatible",
        f"    name: {_yaml_str(_AICHAT_CLIENT_NAME)}",
        f"    api_base: {_yaml_str(ctx.base)}",
        f"    api_key: {_yaml_str(ctx.key)}",
    ]
    if model_ids:
        lines.append("    models:")
        lines += [f"      - name: {_yaml_str(mid)}" for mid in model_ids]
    cfg_yaml = "\n".join(lines)

    # Single-quoted heredoc -> the shell writes the YAML verbatim; the env
    # prefix scopes the config override to this one command.
    cmd = f"cat > {_AICHAT_CONFIG_FILE} <<'AIGATE_EOF'\n" + cfg_yaml + "\nAIGATE_EOF\n"
    cmd += f"AICHAT_CONFIG_FILE={_AICHAT_CONFIG_FILE} {ctx.binary_name}"
    return cmd


# --------------------------------------------------------------------------- #
# qwen (Qwen Code) — documented multi-protocol auth (docs/users/configuration/
# auth.md + settings.md). The OpenAI-compatible protocol is auth type ``openai``
# and its models are declared under ``modelProviders.openai`` (each entry:
# id/name/baseUrl/envKey). Settings resolve in layers and the PROJECT file
# ``<cwd>/.qwen/settings.json`` overrides the user's ``~/.qwen/settings.json``,
# so aigate writes a project-scoped file instead of touching user config.
# --------------------------------------------------------------------------- #
_QWEN_SETTINGS_PATH = ".qwen/settings.json"
_QWEN_ENV_KEY = "OPENAI_API_KEY"  # default key env for auth type ``openai``


def _qwen_builder(ctx: _LaunchCtx) -> str:
    """qwen's documented OpenAI-compatible form (project settings + TUI).

    Every discovered model of the provider is declared so qwen's ``/model``
    picker can switch without relaunching; the requested model is preselected
    through ``model.name``. ``security.auth.selectedType = "openai"`` skips the
    interactive ``/auth`` flow, and ``env.OPENAI_API_KEY`` carries the gateway
    key (the caller also exports it, so both routes work).

    No model chosen -> no ``modelProviders``/``model`` keys: the CLI still
    launches and the user can authenticate/choose inside it.
    """
    model_ids: List[str] = list(ctx.provider_models)
    if ctx.raw_model and ctx.raw_model not in model_ids:
        model_ids.insert(0, ctx.raw_model)

    config: Dict[str, object] = {}
    if model_ids:
        config["modelProviders"] = {
            "openai": [
                {
                    "id": mid,
                    "name": mid,
                    "baseUrl": ctx.base,
                    "envKey": _QWEN_ENV_KEY,
                }
                for mid in model_ids
            ]
        }
        config["security"] = {"auth": {"selectedType": "openai"}}
    if ctx.raw_model:
        config["model"] = {"name": ctx.raw_model}
    config["env"] = {_QWEN_ENV_KEY: ctx.key}

    cfg_json = json.dumps(config, indent=2)
    # mkdir -p first: the redirect would otherwise fail on a fresh directory.
    cmd = (
        f"mkdir -p {os.path.dirname(_QWEN_SETTINGS_PATH)}\n"
        f"cat > {_QWEN_SETTINGS_PATH} <<'AIGATE_EOF'\n" + cfg_json + "\nAIGATE_EOF\n"
    )
    cmd += ctx.binary_name
    return cmd


def _llm_builder(ctx: _LaunchCtx) -> str:
    """llm's documented one-shot form for ANY OpenAI-compatible endpoint.

    ``llm openai endpoint <base_url> -m <model> --key <key> --chat``
    (docs/other-models.md, "Run against an endpoint without configuring it").
    Chosen over ``extra-openai-models.yaml`` because it needs no config file at
    all — nothing in the user's llm home is written or registered, and the
    gateway base url is passed per invocation. ``--chat`` gives the interactive
    session a terminal tab wants; the docs note the command does NOT send the
    user's configured OpenAI key, so the gateway key is passed explicitly
    (ADR-007: local app, plaintext key is the documented injection route).

    No model chosen -> ``--models`` lists what the gateway advertises (the
    documented discovery flag) instead of inventing a model id.
    """
    parts: List[str] = [ctx.binary_name, "openai", "endpoint", ctx.base]
    if ctx.default_flags:
        parts.append(ctx.default_flags)
    if ctx.raw_model:
        parts += ["-m", ctx.raw_model, "--key", ctx.key, "--chat"]
    else:
        parts.append("--models")
    return " ".join(parts)


def _gptme_builder(ctx: _LaunchCtx) -> str:
    """gptme's documented route for any OpenAI-compatible server.

    docs/providers.html ("Local"):
    ``OPENAI_BASE_URL="http://127.0.0.1:11434/v1" gptme 'hello' -m local/<model>``

    The ``local/`` provider prefix is what keeps gptme on the chat-completions
    path — the docs note that direct ``openai/*`` GPT-5-class models are routed
    to ``/v1/responses`` instead, which the gateway does not serve. The key
    needs no flag: gptme reads ``OPENAI_API_KEY``, already exported by the
    launcher. No prompt is passed, so gptme opens its interactive chat.
    """
    parts: List[str] = [ctx.binary_name]
    if ctx.default_flags:
        parts.append(ctx.default_flags)
    if ctx.raw_model:
        parts += ["-m", f"local/{ctx.raw_model}"]
    return f"OPENAI_BASE_URL={shlex.quote(ctx.base)} " + " ".join(parts)


# --------------------------------------------------------------------------- #
# kilo (Kilo Code CLI, npm @kilocode/cli — bins `kilo` + `kilocode`).
#
# Documented custom-provider form (kilocode.ai/docs/ai-providers/openai-compatible,
# "CLI" tab): a provider key of our choosing + ``npm: "@ai-sdk/openai-compatible"``
# (the OpenAI Chat Completions protocol package) + ``options.baseURL`` /
# ``options.apiKey`` + a ``models`` map ("You must define at least one model"),
# with the default model as ``provider-id/model-id``. The same shape is repeated
# in docs/code-with-ai/agents/custom-models.md ("OpenAI-compatible provider with
# a custom endpoint"), and that page also fixes the resolution order: 1) the
# ``-m/--model`` flag, 2) the config ``model`` key, 3) last used, 4) first
# available — so the flag is what wins over anything the user already has.
#
# Config location: NOT a project ``kilo.json``. Two documented reasons:
#   1. ``.kilo/kilo.json`` and ``./kilo.json[c]`` ARE user-owned project config
#      paths (docs/getting-started/settings.md: "Project config: ``kilo.jsonc``
#      in your project root, or ``.kilo/kilo.jsonc``"), so writing one would
#      clobber whatever the user already has there.
#   2. a project config is UNTRUSTED, so ``{env:VAR}`` is rejected outright:
#      docs/code-with-ai/agents/custom-models.md — "`apiKey` (or any option)
#      references are resolved only when the config lives in a trusted location:
#      your global config (``~/.config/kilo``), a config passed via
#      ``KILO_CONFIG`` / ``KILO_CONFIG_CONTENT``, or organization/MDM-managed
#      config. A project-level ``kilo.json`` / ``opencode.json`` committed to a
#      repository cannot resolve ``{env:VAR}``". Writing the project file would
#      therefore force the plaintext gateway key onto disk.
# ``KILO_CONFIG`` is that trusted location and is an ADDITIVE layer: the runtime
# precedence table (docs/contributing/architecture/cli-runtime.md) loads global
# config first, then "Explicit ``KILO_CONFIG`` file" (5), then project files (6)
# — so the user's global config and auth records keep working and our provider
# is just merged in. Our file gets a namespaced name (``aigate-kilo.json``) that
# is not one of kilo's implicit config filenames, so it can never overwrite a
# user config. The ``model`` key can still lose to a user project file, which is
# exactly why the preselect is ALSO passed as ``-m`` (priority 1).
# --------------------------------------------------------------------------- #
_KILO_PROVIDER_ID = "aigate"  # arbitrary key, docs: "it can be any name you like"
# Our own config file (never a filename kilo auto-discovers) + the env var that
# points the CLI at it (docs/contributing/architecture/cli-runtime.md).
_KILO_CONFIG_PATH = ".kilo/aigate-kilo.json"
_KILO_CONFIG_ENV = "KILO_CONFIG"
# The key is NOT written to disk: the launcher exports OPENAI_API_KEY for every
# tool, and {env:...} resolves because a KILO_CONFIG file is trusted.
_KILO_ENV_KEY = "OPENAI_API_KEY"


def _kilo_builder(ctx: _LaunchCtx) -> str:
    """kilo's documented OpenAI-compatible form (trusted config + TUI).

    Every discovered model of the chosen provider is declared so kilo's
    ``/models`` picker can switch without relaunching (the docs warn a custom
    provider with no ``models`` entry exposes nothing). The requested model is
    preselected twice: through the config ``model`` key (for a later manual
    ``kilo`` in the same project) and through ``-m``, which per the docs has the
    highest priority ("Model Loading Priority": 1 flag, 2 config key, 3 last
    used, 4 first available) and therefore beats any ``model`` key the user's own
    config files carry. Model ids keep the ``provider:<name>:<id>`` reduction and
    combo refs stay verbatim, exactly like the other builders.

    ``limit`` (context/output tokens) is deliberately NOT written: the docs call
    it recommended but every model field is optional, and inventing a context
    window for a gateway model is a guess — omitting only disables automatic
    compaction, while a wrong value would truncate real windows.

    No model chosen -> the config still registers the gateway (plus every model
    that was discovered) but no ``model`` key and no ``-m`` flag: the TUI opens
    and the user picks with ``/models``. Nothing is invented.

    ``ctx.key`` is deliberately unused here: the gateway key reaches kilo as the
    exported ``OPENAI_API_KEY`` (the launcher injects it for every tool) and is
    resolved by kilo inside the trusted file — so the secret appears in neither
    the command line (``ps``) nor the generated config.

    DOCS-VERIFIED, not device-verified: like cline, ``@kilocode/cli`` ships
    per-platform binaries and npm on Termux (``process.platform == "android"``)
    never installs the linux-arm64 one, so the form comes from the upstream docs.
    """
    model_ids: List[str] = list(ctx.provider_models)
    if ctx.raw_model and ctx.raw_model not in model_ids:
        model_ids.insert(0, ctx.raw_model)

    config: Dict[str, object] = {
        "$schema": "https://app.kilo.ai/config.json",
    }
    if ctx.raw_model:
        # `provider_id/model_id` (docs: custom-models.md, "model" key format).
        config["model"] = f"{_KILO_PROVIDER_ID}/{ctx.raw_model}"
    config["provider"] = {
        _KILO_PROVIDER_ID: {
            "npm": "@ai-sdk/openai-compatible",
            "options": {
                "baseURL": ctx.base,
                # Env reference, not the secret itself — legal here because a
                # KILO_CONFIG file is a trusted location (see the block above).
                "apiKey": f"{{env:{_KILO_ENV_KEY}}}",
            },
            "models": {mid: {"name": mid} for mid in model_ids},
        }
    }
    cfg_json = json.dumps(config, indent=2)

    # mkdir -p first: the redirect would otherwise fail on a fresh directory.
    cmd = (
        f"mkdir -p {os.path.dirname(_KILO_CONFIG_PATH)}\n"
        f"cat > {_KILO_CONFIG_PATH} <<'AIGATE_EOF'\n" + cfg_json + "\nAIGATE_EOF\n"
    )
    parts: List[str] = [ctx.binary_name]
    if ctx.default_flags:
        parts.append(ctx.default_flags)
    if ctx.raw_model:
        parts += ["-m", shlex.quote(f"{_KILO_PROVIDER_ID}/{ctx.raw_model}")]
    # Env prefix scopes the config override to this one command (same route as
    # aichat's AICHAT_CONFIG_FILE); the path is relative to the PTY's CWD, which
    # is the directory the heredoc above just wrote.
    prefix = f"{_KILO_CONFIG_ENV}={shlex.quote(_KILO_CONFIG_PATH)} "
    return cmd + prefix + " ".join(parts)


def _cline_builder(ctx: _LaunchCtx) -> str:
    """cline CLI's documented "quick provider setup", then the interactive TUI.

    apps/cli/README.md:
    ``cline auth --provider openai-native --apikey sk-... --modelid gpt-5
    --baseurl https://api.example.com/v1``

    ``openai-native`` is cline's OpenAI-compatible provider id, so the gateway
    is registered as a plain OpenAI endpoint. The setup is chained with ``&&``
    to a bare ``cline`` (interactive mode — cline's documented default when no
    prompt is given).

    DOCS-VERIFIED, not device-verified: cline ships per-platform binaries
    (macOS/Linux/Windows on arm64/x64) and cannot be installed on Termux, so
    the flag form comes from the upstream README rather than a live run.

    No model chosen -> the setup step is skipped entirely (inventing a model id
    would just make cline fail later); plain ``cline`` lets the user configure
    inside the CLI.
    """
    if not ctx.raw_model:
        return ctx.binary_name
    setup = " ".join(
        [
            ctx.binary_name, "auth",
            "--provider", "openai-native",
            "--apikey", shlex.quote(ctx.key),
            "--modelid", shlex.quote(ctx.raw_model),
            "--baseurl", shlex.quote(ctx.base),
        ]
    )
    tail = f" {ctx.default_flags}" if ctx.default_flags else ""
    return f"{setup} && {ctx.binary_name}{tail}"


# --------------------------------------------------------------------------- #
# open-interpreter — the PYTHON package that ``pip install open-interpreter``
# actually installs (PyPI ``open-interpreter`` 0.4.3, released 2024-10-26, the
# last Python release). IMPORTANT: the GitHub repo OpenInterpreter/open-interpreter
# now hosts a DIFFERENT product — a new Rust agent (a Codex fork, installed via
# curl, whose CLI reference lists no --api_base/--api_key). The Python project
# lives on as the community fork endolith/open-interpreter. Verified against the
# docs of THAT project + the PyPI 0.4.3 README (docs-only, read 2026-09-05):
#   docs/settings/all-settings.mdx  -> "API Base"   : interpreter --api_base <url>
#                                    -> "API Key"    : interpreter --api_key <key>
#                                    -> "Model Selection": interpreter --model <litellm-id>
#   docs/language-models/local-models/lm-studio.mdx  -> any OpenAI-compatible
#       server: interpreter --api_base "http://localhost:1234/v1" --api_key "fake_key";
#       llm.model = "openai/x" "tells OI to send messages in OpenAI's format"
#   README "Interactive Chat" -> bare ``interpreter`` (no positional prompt)
#       opens the interactive chat — exactly what the PTY tab needs.
# The model is sent as ``openai/<raw>``: --model sets the same llm.model
# attribute the docs configure with "openai/x", and the explicit prefix also
# sidesteps the auto-prefix heuristic in start_terminal_interface.py (verified
# present at tags v0.4.0/v0.4.2 + main): a bare id starting with "local",
# "ollama" or "jan" would NOT get the openai/ prefix and would be routed to a
# local provider instead of the gateway. LiteLLM strips the prefix before the
# request, so the gateway receives the raw id (combo refs stay verbatim) and
# resolves it as usual.
# No model chosen -> the documented LM-Studio form WITHOUT --model: OI keeps its
# own default model and still points at the gateway; nothing is invented.
# OI has no documented way to enumerate/select several models per session (the
# model is fixed at launch), so provider_models is deliberately unused here.
# --------------------------------------------------------------------------- #
def _interpreter_builder(ctx: _LaunchCtx) -> str:
    """open-interpreter's documented OpenAI-compatible flag form + chat."""
    parts: List[str] = [ctx.binary_name]
    if ctx.default_flags:
        parts.append(ctx.default_flags)
    parts += [
        "--api_base",
        shlex.quote(ctx.base),
        "--api_key",
        shlex.quote(ctx.key),
    ]
    if ctx.raw_model:
        parts += ["--model", shlex.quote(f"openai/{ctx.raw_model}")]
    return " ".join(parts)


# binary_name -> builder. Anything absent uses ``_generic_builder``.
_LAUNCH_BUILDERS: Dict[str, Callable[[_LaunchCtx], str]] = {
    "aider": _aider_builder,
    "opencode": _opencode_builder,
    "aichat": _aichat_builder,
    "qwen": _qwen_builder,
    "llm": _llm_builder,
    "gptme": _gptme_builder,
    "cline": _cline_builder,
    "kilo": _kilo_builder,
    "interpreter": _interpreter_builder,
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

    Only a tool whose preset is marked ``verified`` is resolvable; anything else
    gets a 409 ``tool_unsupported`` (see ``_unsupported`` for why we refuse
    instead of guessing a command).

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

        support = launch_support_for(tool.name)
        if support.mode != LAUNCH_VERIFIED:
            log_info(
                f"resolve: tool '{tool.name}' not launchable "
                f"(mode={support.mode} reason={support.reason or '-'})",
                source=LOG_SOURCE,
            )
            return _unsupported(tool.name, support.mode, support.reason)

        binary_path = _which_with_extra_paths(tool.binary_name)
        binary_found = binary_path is not None
        # Always expose the install command: the frontend's PTY-side
        # ``command -v`` check is authoritative, so it needs the string even when
        # the server-side hint says the binary is present. On Termux the
        # platform route wins where one exists (``pkg install``), because the
        # portable npm/pip form cannot work there (see cli_presets.TERMUX_INSTALL).
        install_command = install_command_for(
            tool.name, tool.install_command or "", termux=is_termux()
        )

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
            provider_models=_discovered_models_for_ref(session, req.model),
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

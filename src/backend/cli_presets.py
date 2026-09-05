"""CLI tool preset groups (A/B/C) + idempotent seed/upsert (task B3.4).

Transcribes ``documents/config/CLI_CONFIG_SCHEMA.md`` into ORM rows for
``CLIToolGroup`` / ``CLITool``. The lists are the single seed source; the
frontend (fe-dev, later step) renders them and spawns the tool. The backend
here only provides the data + a ``resolve`` helper (see
``cli_tools_router.py``).

Map schema -> our columns:
- group ``id``/``label`` -> ``CLIToolGroup(code=id, label, display_priority)``
  display_priority: agentic_coding=1, autonomous_agents=2, chat_shell=3.
- tool ``name``/``binary``/``install``/``presets|default_flags`` ->
  ``CLITool(name, binary_name, install_command, default_flags, enabled=True)``.

WHY THE PRESETS CARRY VERIFIED INSTALL STRINGS: the original transcription used
``pip install <name>`` for everything, and most of those PyPI names belong to
UNRELATED packages (``pip install codex`` = a comic-archive web server,
``pip install gemini`` = a genetics DB framework, ``pip install claude-code`` =
a reserved stub). Every package name + bin below was checked against the npm /
PyPI registries; the ones with no installable package for this platform carry an
``echo`` no-op instead of a command that would install garbage.

Rule R12 / ADR-011: seed logs via ``backend.log`` (no bare ``except: pass``);
any caught exception is persisted to ``LogEntry`` via ``log_exception``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from backend.log import SEVERITY_ERROR, log_exception, log_info
from backend.models import CLITool, CLIToolGroup

# display_priority per FSD §2.6.1: A (Agentic Coding) first, then B, then C.
_DISPLAY_PRIORITY: dict[str, int] = {
    "agentic_coding": 1,
    "autonomous_agents": 2,
    "chat_shell": 3,
}

# No installable package for this platform (or the name is squatted by an
# unrelated project). An explicit no-op beats a command that installs garbage:
# the PTY-side branch is ``if command -v <bin>; then <run>; else <install>; fi``.
NO_INSTALL = "echo 'aigate: no verified install command for this tool'"


def _npm(pkg: str) -> str:
    return f"npm install -g {pkg}"


def _pip(pkg: str) -> str:
    return f"pip install {pkg}"


# CLI_PRESETS: list of group dicts. Each group owns a ``tools`` list.
# tool keys: name (required), binary (optional, default=name),
# install (optional; ALWAYS explicit here — see the module docstring),
# default_flags (optional list, joined with space into a string).
#
# ``default_flags`` is empty for every preset on purpose: a flag string is part
# of the tool's launch form, and the launch form belongs to the verified
# builder in ``cli_tools_router``. Guessing flags here is what produced
# ``claude openai-compatible`` (a flag that does not exist).
CLI_PRESETS: list[dict] = [
    {
        "code": "agentic_coding",
        "name": "Agentic Coding Assistants",
        "tools": [
            {"name": "claude", "binary": "claude", "install": _npm("@anthropic-ai/claude-code")},
            {"name": "opencode", "binary": "opencode", "install": _npm("opencode-ai")},
            {"name": "codex", "binary": "codex", "install": _npm("@openai/codex")},
            {"name": "gemini", "binary": "gemini", "install": _npm("@google/gemini-cli")},
            {"name": "antigravity", "binary": "antigravity", "install": NO_INSTALL},
            {"name": "phi", "binary": "phi", "install": NO_INSTALL},
            {"name": "aider", "binary": "aider", "install": _pip("aider-chat")},
            {"name": "goose", "binary": "goose", "install": NO_INSTALL},
            {"name": "amp", "binary": "amp", "install": NO_INSTALL},
            {"name": "qwen", "binary": "qwen", "install": _npm("@qwen-code/qwen-code")},
            {"name": "cline", "binary": "cline", "install": _npm("cline")},
            {"name": "kilo", "binary": "kilo", "install": _npm("@kilocode/cli")},
        ],
    },
    {
        "code": "autonomous_agents",
        "name": "Autonomous Software Agents",
        "tools": [
            {"name": "openhands", "binary": "openhands", "install": _pip("openhands")},
            {"name": "swe-agent", "binary": "swe-agent", "install": NO_INSTALL},
            {"name": "open-interpreter", "binary": "interpreter", "install": _pip("open-interpreter")},
            {"name": "autogpt", "binary": "autogpt", "install": NO_INSTALL},
            {"name": "gpt-researcher", "binary": "gpt-researcher", "install": _pip("gpt-researcher")},
            {"name": "crewai", "binary": "crewai", "install": _pip("crewai")},
        ],
    },
    {
        "code": "chat_shell",
        "name": "Chat & Shell Assistants",
        "tools": [
            {"name": "llm", "binary": "llm", "install": _pip("llm")},
            {"name": "sgpt", "binary": "sgpt", "install": NO_INSTALL},
            {"name": "mods", "binary": "mods", "install": NO_INSTALL},
            {"name": "oterm", "binary": "oterm", "install": _pip("oterm")},
            {"name": "gptme", "binary": "gptme", "install": _pip("gptme")},
            {"name": "aichat", "binary": "aichat", "install": "cargo install aichat"},
        ],
    },
]


# --------------------------------------------------------------------------- #
# Launch support registry (code-level truth, NOT a DB column)
#
# This changes with the launch builders in ``cli_tools_router`` and with what
# the aigate gateway can actually serve — never with user data, so it is kept
# out of the DB and exposed through ``ToolDTO`` instead.
#
#   verified    -> a documented launch builder exists (_LAUNCH_BUILDERS) and the
#                  tool talks the gateway's OpenAI /v1/chat/completions format
#   pending     -> usable with aigate, but the launch form is not written or
#                  verified yet (work-through-the-list marker)
#   unsupported -> cannot be launched at aigate today: it needs a wire format
#                  the gateway does not expose, or it is not a CLI at all
#
# ``pending`` and ``unsupported`` are both struck through in the UI (the marker
# the operator uses to pick the next tool to fix) and both refuse ``resolve``.
# --------------------------------------------------------------------------- #
LAUNCH_VERIFIED = "verified"
LAUNCH_PENDING = "pending"
LAUNCH_UNSUPPORTED = "unsupported"

REASON_PENDING = "pending"
REASON_ANTHROPIC_ONLY = "anthropic_only"
REASON_GEMINI_ONLY = "gemini_only"
REASON_RESPONSES_ONLY = "responses_only"
REASON_NOT_A_CLI = "not_a_cli"
REASON_NO_BINARY = "no_binary"
REASON_INSTALL_UNVERIFIED = "install_unverified"


@dataclass(frozen=True)
class LaunchSupport:
    """Whether + why a preset tool may be launched against the gateway."""

    mode: str
    reason: str = ""


# tool name -> support. Anything absent is treated as ``pending`` (fail-closed:
# a newly added preset can never be launched until someone looks at it).
#
# Every entry below was checked ON THE DEVICE (Termux/aarch64), not from memory:
#   claude / gemini  -> the gateway serves OpenAI /v1/chat/completions only;
#                       these two speak Anthropic Messages / Google generateContent.
#   codex            -> verified live: codex 0.122.0 (Termux tur build) refuses to
#                       start with `wire_api = "chat"` ("no longer supported",
#                       openai/codex discussion #7782) — it needs /v1/responses.
#   goose / amp / mods / sgpt / swe-agent / autogpt / phi ->
#                       no installable package for this platform under that name
#                       (PyPI names belong to unrelated projects; npm ships no
#                       android build, and Termux's `goose` is a DB migration
#                       tool, not Block's agent).
#                       Tools the Termux repo DOES package (e.g. `pkg install
#                       aichat`) get their own entry + install string once their
#                       launch form is verified.
LAUNCH_SUPPORT: Dict[str, LaunchSupport] = {
    # --- Group A: agentic coding ---
    "aider": LaunchSupport(LAUNCH_VERIFIED),
    "opencode": LaunchSupport(LAUNCH_VERIFIED),
    "claude": LaunchSupport(LAUNCH_UNSUPPORTED, REASON_ANTHROPIC_ONLY),
    "gemini": LaunchSupport(LAUNCH_UNSUPPORTED, REASON_GEMINI_ONLY),
    "antigravity": LaunchSupport(LAUNCH_UNSUPPORTED, REASON_NOT_A_CLI),
    "phi": LaunchSupport(LAUNCH_UNSUPPORTED, REASON_INSTALL_UNVERIFIED),
    "goose": LaunchSupport(LAUNCH_UNSUPPORTED, REASON_NO_BINARY),
    "amp": LaunchSupport(LAUNCH_UNSUPPORTED, REASON_NO_BINARY),
    "codex": LaunchSupport(LAUNCH_UNSUPPORTED, REASON_RESPONSES_ONLY),
    "qwen": LaunchSupport(LAUNCH_VERIFIED),
    "cline": LaunchSupport(LAUNCH_VERIFIED),
    "kilo": LaunchSupport(LAUNCH_VERIFIED),
    # --- Group B: autonomous agents ---
    # The interactive TUI ships as PyPI `openhands` (repo OpenHands/OpenHands-CLI,
    # [project.scripts] openhands=...); `openhands-ai` since 1.x is the Agent
    # Canvas/server stack and provides no terminal CLI, so the install string
    # below was corrected to match the binary. Launch form: documented LLM_*
    # env route + --override-with-envs (see _openhands_builder).
    "openhands": LaunchSupport(LAUNCH_VERIFIED),
    # pip artifact = Python open-interpreter 0.4.3 (PyPI, 2024-10-26); its
    # --api_base/--api_key/--model form is documented (see _interpreter_builder).
    # NOT the new Rust agent that now occupies the GitHub repo (curl-installed,
    # no such flags) — the preset installs via pip, so the Python docs are the
    # contract here.
    "open-interpreter": LaunchSupport(LAUNCH_VERIFIED),
    # NOT A CLI: `pip install gpt-researcher` ships a library + web-app backend
    # only — no console script (pyproject [project] has no [project.scripts],
    # setup.py has no entry_points; README's pip section shows `import
    # GPTResearcher` usage only). The docs' "Run with CLI" page is a
    # repo-checkout script (`python cli.py "<query>" --report_type ...`),
    # requires a query and exits after writing a report file — no binary to
    # spawn and no interactive chat. See CLI_CONFIG_SCHEMA.md bullet (2026-09-05).
    "gpt-researcher": LaunchSupport(LAUNCH_UNSUPPORTED, REASON_NOT_A_CLI),
    # NOT A LAUNCHABLE ASSISTANT: the `crewai` console script exists
    # (lib/crewai/pyproject.toml [project.scripts]), but it is a framework
    # project scaffolder/runner: `crewai run` runs the Crew/Flow DEFINED BY THE
    # PROJECT in the CWD (docs: "Make sure to run these commands from the
    # directory where your CrewAI project is set up"), and `crewai chat` is an
    # interactive session with THAT crew (crew_chat.run_chat -> read_toml() +
    # load_crew_and_name()). Neither takes a model/base-url/prompt at launch —
    # the OpenAI-compatible route (LLM(model="openai/<id>", base_url=...)) is
    # Python code inside the generated project, not a CLI surface. In an empty
    # directory both error out. See CLI_CONFIG_SCHEMA.md bullet (2026-09-06).
    "crewai": LaunchSupport(LAUNCH_UNSUPPORTED, REASON_NOT_A_CLI),
    "swe-agent": LaunchSupport(LAUNCH_UNSUPPORTED, REASON_INSTALL_UNVERIFIED),
    "autogpt": LaunchSupport(LAUNCH_UNSUPPORTED, REASON_INSTALL_UNVERIFIED),
    # --- Group C: chat & shell ---
    "llm": LaunchSupport(LAUNCH_VERIFIED),
    # openaiCompatible config block + OTERM_DATA_DIR override are documented
    # (ggozad.github.io/oterm app_config.md, v0.24.0) — see _oterm_builder.
    "oterm": LaunchSupport(LAUNCH_VERIFIED),
    "gptme": LaunchSupport(LAUNCH_VERIFIED),
    "sgpt": LaunchSupport(LAUNCH_UNSUPPORTED, REASON_INSTALL_UNVERIFIED),
    "mods": LaunchSupport(LAUNCH_UNSUPPORTED, REASON_NO_BINARY),
    "aichat": LaunchSupport(LAUNCH_VERIFIED),
}


def launch_support_for(name: str) -> LaunchSupport:
    """Support entry for a tool name (unknown/user-added -> ``pending``)."""
    return LAUNCH_SUPPORT.get(name, LaunchSupport(LAUNCH_PENDING))


# Termux-only install routes, verified against the device's package lists
# (``apt-cache search``) rather than guessed. WHY: the portable string is often
# unusable on Android — npm reports ``process.platform == "android"`` so it
# never installs the ``*-linux-arm64`` binary a CLI needs, while Termux ships a
# working bionic build of the same tool. Only tools actually present in the
# Termux/tur repos belong here.
TERMUX_INSTALL: Dict[str, str] = {
    "aichat": "pkg install aichat",  # termux-main, verified 0.30.0 runs
    "codex": "pkg install codex",  # tur-repo, verified 0.122.0 runs
}


def install_command_for(name: str, default: str = "", termux: bool = False) -> str:
    """Install string for a tool, honouring the Termux override when on Termux.

    ``termux`` is a parameter (not an internal ``is_termux()`` call) so the
    choice stays deterministic + testable, and the caller decides once per
    request.
    """
    if termux:
        override = TERMUX_INSTALL.get(name)
        if override:
            return override
    return default


def _tool_defaults(tool: dict) -> dict:
    """Map a schema tool dict to ``CLITool`` column kwargs."""
    name = tool["name"]
    binary = tool.get("binary", name)
    install = tool.get("install", NO_INSTALL)
    flags = tool.get("default_flags", [])
    if isinstance(flags, (list, tuple)):
        default_flags = " ".join(str(f) for f in flags)
    else:
        default_flags = flags or ""
    return {
        "name": name,
        "binary_name": binary,
        "install_command": install,
        "default_flags": default_flags,
        "enabled": True,
    }


# Preset-owned columns. ``enabled`` is deliberately absent: it is the one
# user-facing toggle, so an upsert must never reset it.
_TOOL_PRESET_COLUMNS = ("binary_name", "install_command", "default_flags")


def seed_cli_tools(session) -> int:
    """Create OR refresh the preset groups + tools (idempotent upsert).

    Returns the number of rows created or changed (0 = DB already matches the
    presets).

    WHY UPSERT: the original guard was ``if any group exists: skip``, which made
    every preset fix after the first startup dead code — the running DB kept the
    wrong install commands forever. Preset-owned columns are therefore rewritten
    from ``CLI_PRESETS`` on every startup; user-owned state (``enabled``, and
    rows the user added by hand) is left alone.
    """
    try:
        changed = 0

        for group in CLI_PRESETS:
            priority = _DISPLAY_PRIORITY.get(group["code"], 99)
            g = (
                session.query(CLIToolGroup)
                .filter(CLIToolGroup.code == group["code"])
                .first()
            )
            if g is None:
                g = CLIToolGroup(
                    code=group["code"],
                    name=group["name"],
                    display_priority=priority,
                )
                session.add(g)
                session.flush()  # populate g.id for FK
                changed += 1
            else:
                if g.name != group["name"]:
                    g.name = group["name"]
                    changed += 1
                if g.display_priority != priority:
                    g.display_priority = priority
                    changed += 1

            for tool in group["tools"]:
                defaults = _tool_defaults(tool)
                row = (
                    session.query(CLITool)
                    .filter(
                        CLITool.group_id == g.id,
                        CLITool.name == defaults["name"],
                    )
                    .first()
                )
                if row is None:
                    session.add(CLITool(group_id=g.id, **defaults))
                    changed += 1
                    continue
                for col in _TOOL_PRESET_COLUMNS:
                    if getattr(row, col) != defaults[col]:
                        setattr(row, col, defaults[col])
                        changed += 1

        session.commit()

        if changed:
            log_info(
                f"seed_cli_tools: upserted {changed} preset row(s) "
                f"({sum(len(g['tools']) for g in CLI_PRESETS)} tools in "
                f"{len(CLI_PRESETS)} groups)",
                source="backend.cli_tools.seed",
                context={"codes": [g["code"] for g in CLI_PRESETS]},
            )
        else:
            log_info(
                "seed_cli_tools: presets already up to date",
                source="backend.cli_tools.seed",
            )
        return changed
    except Exception as exc:  # noqa: BLE001 - log then surface to caller
        try:
            session.rollback()
        except Exception as rb_exc:  # noqa: BLE001 - rollback diagnostics only
            log_exception(
                SEVERITY_ERROR,
                "seed_cli_tools rollback failed",
                source="backend.cli_tools.seed",
                exc=rb_exc,
            )
        log_exception(
            SEVERITY_ERROR,
            "seed_cli_tools failed",
            source="backend.cli_tools.seed",
            exc=exc,
        )
        raise


__all__ = [
    "CLI_PRESETS",
    "LAUNCH_SUPPORT",
    "LAUNCH_VERIFIED",
    "LAUNCH_PENDING",
    "LAUNCH_UNSUPPORTED",
    "LaunchSupport",
    "launch_support_for",
    "seed_cli_tools",
]

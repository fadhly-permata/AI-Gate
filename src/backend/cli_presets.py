"""CLI tool preset groups (A/B/C) + idempotent DB seed (task B3.4).

Transcribes ``documents/config/CLI_CONFIG_SCHEMA.md`` into ORM rows for
``CLIToolGroup`` / ``CLITool``. The lists are the single seed source; the
frontend (fe-dev, later step) renders them and spawns the tool. The backend
here only provides the data + a ``resolve`` helper (see
``cli_tools_router.py``).

Map schema -> our columns:
- group ``id``/``label`` -> ``CLIToolGroup(code=id, name=label, display_priority)``
  display_priority: agentic_coding=1, autonomous_agents=2, chat_shell=3.
- tool ``name``/``binary``/``install``/``presets|default_flags`` ->
  ``CLITool(name, binary_name, install_command, default_flags, enabled=True)``.

Rule R12 / ADR-011: seed logs via ``backend.log`` (no bare ``except: pass``);
any caught exception is persisted to ``LogEntry`` via ``log_exception``.
"""

from __future__ import annotations

from backend.log import SEVERITY_ERROR, log_exception, log_info
from backend.models import CLITool, CLIToolGroup

# display_priority per FSD §2.6.1: A (Agentic Coding) first, then B, then C.
_DISPLAY_PRIORITY: dict[str, int] = {
    "agentic_coding": 1,
    "autonomous_agents": 2,
    "chat_shell": 3,
}

# CLI_PRESETS: list of group dicts. Each group owns a ``tools`` list.
# tool keys: name (required), binary (optional, default=name),
# install (optional, default=f"pip install {name}"),
# default_flags (optional list, joined with space into a string).
CLI_PRESETS: list[dict] = [
    {
        "code": "agentic_coding",
        "name": "Agentic Coding Assistants",
        "tools": [
            {
                "name": "claude",
                "binary": "claude",
                "install": "pip install claude-code",
                "default_flags": ["openai-compatible"],
            },
            {"name": "opencode"},
            {"name": "codex"},
            {"name": "gemini"},
            {"name": "antigravity"},
            {"name": "phi"},
            {"name": "aider"},
            {"name": "goose"},
            {"name": "amp"},
            {"name": "qwen"},
            {"name": "cline"},
            {"name": "kilo"},
        ],
    },
    {
        "code": "autonomous_agents",
        "name": "Autonomous Software Agents",
        "tools": [
            {"name": "openhands"},
            {"name": "swe-agent"},
            {"name": "open-interpreter", "binary": "interpreter"},
            {"name": "autogpt"},
            {"name": "gpt-researcher"},
            {"name": "crewai"},
        ],
    },
    {
        "code": "chat_shell",
        "name": "Chat & Shell Assistants",
        "tools": [
            {"name": "llm"},
            {"name": "sgpt"},
            {"name": "mods"},
            {"name": "oterm"},
            {"name": "gptme"},
            {"name": "aichat"},
        ],
    },
]


def _tool_defaults(tool: dict) -> dict:
    """Map a schema tool dict to ``CLITool`` column kwargs."""
    name = tool["name"]
    binary = tool.get("binary", name)
    install = tool.get("install", f"pip install {name}")
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


def seed_cli_tools(session) -> int:
    """Idempotently insert preset CLI groups + tools if the table is empty.

    Returns the number of groups inserted (0 if already seeded). Logs via
    ``backend.log`` (``source=backend.cli_tools.seed``). On failure the
    exception is logged (with traceback) and re-raised so the caller (the
    lifespan) can decide whether to abort startup.

    The caller owns the ``session`` lifecycle (open/commit/close); this
    function commits its own inserts.
    """
    try:
        if session.query(CLIToolGroup).count() > 0:
            log_info(
                "seed_cli_tools: skipped (groups already present)",
                source="backend.cli_tools.seed",
            )
            return 0

        inserted = 0
        for group in CLI_PRESETS:
            g = CLIToolGroup(
                code=group["code"],
                name=group["name"],
                display_priority=_DISPLAY_PRIORITY.get(group["code"], 99),
            )
            session.add(g)
            session.flush()  # populate g.id for FK
            for tool in group["tools"]:
                session.add(CLITool(group_id=g.id, **_tool_defaults(tool)))
            inserted += 1
        session.commit()

        log_info(
            f"seed_cli_tools: inserted {inserted} group(s) "
            f"({sum(len(g['tools']) for g in CLI_PRESETS)} tools)",
            source="backend.cli_tools.seed",
            context={"codes": [g["code"] for g in CLI_PRESETS]},
        )
        return inserted
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


__all__ = ["CLI_PRESETS", "seed_cli_tools"]

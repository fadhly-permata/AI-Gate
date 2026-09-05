"""CLI Tools backend tests (task B3.4): seed + list + resolve.

Hermetic, no on-disk DB. Mirrors ``test_endpoints.py``: an in-memory SQLite
engine (StaticPool) replaces every ``SessionLocal`` binding the routers and the
logger touch. ``backend.log`` references ``backend.config.db`` via the module
object (``_db.SessionLocal``), so patching ``backend.config.db.SessionLocal``
also covers the logger. We additionally patch ``backend.cli_tools_router``.
"""

from __future__ import annotations

import dataclasses
import json
import os
import shutil
import stat

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.cli_presets as cli_presets
import backend.cli_tools_router as cli_tools_router
import backend.config.db as db_mod
from backend.config.db import Base
from backend.models import (
    CLITool,
    CLIToolGroup,
    Combo,
    Endpoint,
    LogEntry,
    Provider,
    ProviderModel,
)
from fastapi.testclient import TestClient

from backend.server import app


def _make_sf() -> sessionmaker:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _patch(monkeypatch, sf: sessionmaker) -> None:
    """Rebind every ``SessionLocal`` the CLI tools code paths touch."""
    monkeypatch.setattr(db_mod, "SessionLocal", sf)
    monkeypatch.setattr(cli_tools_router, "SessionLocal", sf)
    # backend.log uses backend.config.db via the module object -> covered above.


def _client(monkeypatch, sf: sessionmaker) -> TestClient:
    _patch(monkeypatch, sf)
    return TestClient(app)


def _seed_all(sf: sessionmaker) -> None:
    with sf() as s:
        cli_presets.seed_cli_tools(s)


# =========================================================================== #
# 1. Seed/upsert: 3 groups + tool counts (12 / 6 / 6)
# =========================================================================== #
def test_seed_cli_tools(monkeypatch) -> None:
    sf = _make_sf()
    with sf() as s:
        # 3 groups + 24 tools created on an empty DB.
        changed = cli_presets.seed_cli_tools(s)
        assert changed == 27

        groups = (
            s.query(CLIToolGroup)
            .order_by(CLIToolGroup.display_priority)
            .all()
        )
        assert len(groups) == 3
        by_code = {g.code: g for g in groups}

        # display_priority mapping
        assert by_code["agentic_coding"].display_priority == 1
        assert by_code["autonomous_agents"].display_priority == 2
        assert by_code["chat_shell"].display_priority == 3

        # tool counts per group
        assert len(by_code["agentic_coding"].tools) == 12
        assert len(by_code["autonomous_agents"].tools) == 6
        assert len(by_code["chat_shell"].tools) == 6
        assert s.query(CLITool).count() == 24

        # specific mappings — install strings are registry-verified: the old
        # ``pip install claude-code`` / ``pip install codex`` pulled UNRELATED
        # PyPI packages (a reserved stub / a comic-archive web server).
        claude = s.query(CLITool).filter_by(name="claude").first()
        assert claude.binary_name == "claude"
        assert claude.install_command == "npm install -g @anthropic-ai/claude-code"
        assert claude.default_flags == ""  # no guessed flags in the preset
        assert claude.enabled is True

        aider = s.query(CLITool).filter_by(name="aider").first()
        assert aider.install_command == "pip install aider-chat"

        codex = s.query(CLITool).filter_by(name="codex").first()
        assert codex.install_command == "npm install -g @openai/codex"

        interp = s.query(CLITool).filter_by(name="open-interpreter").first()
        assert interp.binary_name == "interpreter"

        # default binary falls back to name
        ollama_style = s.query(CLITool).filter_by(name="llm").first()
        assert ollama_style.binary_name == "llm"
        assert ollama_style.install_command == "pip install llm"

    # idempotent: second call changes nothing
    with sf() as s:
        assert cli_presets.seed_cli_tools(s) == 0


def test_seed_upserts_stale_preset_and_keeps_user_state(monkeypatch) -> None:
    """A preset fix must reach an ALREADY-SEEDED DB (the old skip-if-seeded
    guard made every later fix dead code), while ``enabled`` and user-added
    rows survive."""
    sf = _make_sf()
    with sf() as s:
        cli_presets.seed_cli_tools(s)

    # Simulate an old DB: stale install string + a user toggle + a custom row.
    with sf() as s:
        aider = s.query(CLITool).filter_by(name="aider").first()
        aider.install_command = "pip install aider"  # the old, wrong string
        aider.enabled = False                        # user turned it off
        s.add(
            CLITool(
                group_id=aider.group_id,
                name="my-own-cli",
                binary_name="my-own-cli",
                install_command="pip install whatever",
                default_flags="--fast",
                enabled=True,
            )
        )
        s.commit()

    with sf() as s:
        changed = cli_presets.seed_cli_tools(s)
        assert changed == 1  # only the stale aider row was refreshed

        aider = s.query(CLITool).filter_by(name="aider").first()
        assert aider.install_command == "pip install aider-chat"
        assert aider.enabled is False  # user-owned column never touched

        custom = s.query(CLITool).filter_by(name="my-own-cli").first()
        assert custom is not None  # user rows are never deleted/rewritten
        assert custom.default_flags == "--fast"


# =========================================================================== #
# 2. GET /api/cli-tools returns the 3 groups with tools
# =========================================================================== #
def test_list_cli_tools(monkeypatch) -> None:
    sf = _make_sf()
    _seed_all(sf)
    client = _client(monkeypatch, sf)

    r = client.get("/api/cli-tools")
    assert r.status_code == 200
    body = r.json()
    assert body["object"] == "list"
    data = body["data"]
    assert len(data) == 3

    by_code = {g["code"]: g for g in data}
    assert set(by_code) == {"agentic_coding", "autonomous_agents", "chat_shell"}
    assert len(by_code["agentic_coding"]["tools"]) == 12
    assert len(by_code["autonomous_agents"]["tools"]) == 6
    assert len(by_code["chat_shell"]["tools"]) == 6

    # ordering: agentic_coding first (display_priority 1)
    assert data[0]["code"] == "agentic_coding"

    # ToolDTO shape (+ launch support markers)
    tool = by_code["chat_shell"]["tools"][0]
    assert set(tool) == {
        "id",
        "name",
        "binary_name",
        "install_command",
        "default_flags",
        "enabled",
        "launch_mode",
        "launch_reason",
    }

    modes = {
        t["name"]: (t["launch_mode"], t["launch_reason"])
        for g in data
        for t in g["tools"]
    }
    # verified: a documented builder exists -> launchable
    assert modes["aider"][0] == "verified"
    assert modes["opencode"][0] == "verified"
    # unsupported: needs a wire format the gateway does not expose -> struck
    assert modes["claude"] == ("unsupported", "anthropic_only")
    assert modes["antigravity"] == ("unsupported", "not_a_cli")
    # pending: real CLI, launch form not written yet -> struck, reason empty
    assert modes["codex"] == ("pending", "")


# =========================================================================== #
# 3. POST /api/cli-tools/resolve for a verified tool -> ResolveDTO
# =========================================================================== #
def test_resolve_tool_by_name(monkeypatch) -> None:
    sf = _make_sf()
    _seed_all(sf)
    client = _client(monkeypatch, sf)

    r = client.post("/api/cli-tools/resolve", json={"tool": "aider"})
    assert r.status_code == 200
    body = r.json()

    assert body["run_command"].startswith("aider")
    # gateway env injected
    assert body["env"]["OPENAI_API_BASE"] == "http://localhost:8080/v1"
    # no access-controlled endpoint seeded -> non-empty placeholder so CLIs like
    # aider accept the key (gateway ignores it while access control is off).
    assert body["env"]["OPENAI_API_KEY"] == cli_tools_router.PLACEHOLDER_API_KEY
    assert body["env"]["OPENAI_API_KEY"] != ""
    # aider binary not on PATH in sandbox -> install command present
    assert body["binary_found"] is False
    assert body["install_command"] == "pip install aider-chat"
    assert body["model"] is None


# --------------------------------------------------------------------------- #
# 3b. A tool without a verified launch form is REFUSED, not guessed at.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "tool,mode,reason",
    [
        ("llm", "pending", ""),  # real CLI, launch form not written yet
        ("claude", "unsupported", "anthropic_only"),  # needs /v1/messages
        ("antigravity", "unsupported", "not_a_cli"),  # GUI IDE, no binary
    ],
)
def test_resolve_unverified_tool_is_refused(monkeypatch, tool, mode, reason) -> None:
    sf = _make_sf()
    _seed_all(sf)
    client = _client(monkeypatch, sf)

    r = client.post("/api/cli-tools/resolve", json={"tool": tool, "model": "gpt-4o"})
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "tool_unsupported"
    assert tool in err["message"]
    assert f"mode={mode}" in err["message"]
    if reason:
        assert f"reason={reason}" in err["message"]


def test_generic_builder_is_the_verified_tool_fallback() -> None:
    """``_generic_builder`` is the form used for a verified tool that needs
    nothing but the injected env — it must never be reached by an unverified
    tool (that path is blocked by ``resolve``)."""
    ctx = cli_tools_router._LaunchCtx(
        binary_name="demo",
        default_flags="",
        model="provider:B.AI:gpt-5.5",
        raw_model="gpt-5.5",
        base="http://localhost:8080/v1",
        key="k",
    )
    assert cli_tools_router._build_run_command(ctx) == "demo --model provider:B.AI:gpt-5.5"

    ctx_flags = dataclasses.replace(ctx, default_flags="--verbose")
    assert cli_tools_router._build_run_command(ctx_flags) == (
        "demo --verbose --model provider:B.AI:gpt-5.5"
    )


def test_every_verified_preset_has_a_launch_path() -> None:
    """Guard: ``verified`` means launchable. Either the tool has a dedicated
    builder in ``_LAUNCH_BUILDERS`` (keyed by binary) or it is deliberately
    generic — so a preset can never be flipped to verified without code."""
    builders = set(cli_tools_router._LAUNCH_BUILDERS)
    for group in cli_presets.CLI_PRESETS:
        for tool in group["tools"]:
            support = cli_presets.launch_support_for(tool["name"])
            if support.mode != cli_presets.LAUNCH_VERIFIED:
                continue
            binary = tool.get("binary", tool["name"])
            assert binary in builders, (
                f"{tool['name']} is marked verified but has no builder"
            )


def test_resolve_tool_with_model_and_key(monkeypatch) -> None:
    sf = _make_sf()
    _seed_all(sf)
    # seed an access-controlled endpoint so internal_api_key is returned.
    with sf() as s:
        s.add(
            Endpoint(
                name="ep",
                access_control_enabled=True,
                internal_api_key="plain-key-xyz",
            )
        )
        s.commit()

    client = _client(monkeypatch, sf)
    r = client.post(
        "/api/cli-tools/resolve", json={"tool": "aider", "model": "gpt-4o"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["model"] == "gpt-4o"
    assert body["env"]["OPENAI_API_KEY"] == "plain-key-xyz"  # ADR-007 plaintext


# =========================================================================== #
# 4. POST /resolve with unknown tool -> 404 envelope
# =========================================================================== #
def test_resolve_unknown_tool_404(monkeypatch) -> None:
    sf = _make_sf()
    _seed_all(sf)
    client = _client(monkeypatch, sf)

    r = client.post("/api/cli-tools/resolve", json={"tool": "does-not-exist"})
    assert r.status_code == 404
    err = r.json()["error"]
    assert err["code"] == "tool_not_found"
    assert err["type"] == "not_found"


# =========================================================================== #
# 5. aider custom-endpoint launch form (task: CLI-tool gateway init)
# =========================================================================== #
def _seed_endpoint(sf: sessionmaker, key: str = "plain-key-xyz") -> None:
    with sf() as s:
        s.add(
            Endpoint(
                name="ep",
                access_control_enabled=True,
                internal_api_key=key,
            )
        )
        s.commit()


def test_resolve_aider_custom_endpoint_form(monkeypatch) -> None:
    """aider gets --openai-api-base/--openai-api-key + --model openai/<raw>."""
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)
    client = _client(monkeypatch, sf)

    r = client.post(
        "/api/cli-tools/resolve",
        json={"tool": "aider", "model": "provider:B.AI:gpt-5.5"},
    )
    assert r.status_code == 200
    body = r.json()
    rc = body["run_command"]

    # aider's documented OpenAI-compatible form; provider: prefix stripped to
    # the raw model, wrapped in aider's openai/ namespace.
    assert "--openai-api-base" in rc
    assert "--openai-api-key" in rc
    assert "--model openai/gpt-5.5" in rc
    assert "http://localhost:8080/v1" in rc
    assert "plain-key-xyz" in rc
    # the raw provider: ref must NOT leak into the aider --model value.
    assert "provider:" not in rc

    # env still injected (aider reads these too).
    assert body["env"]["OPENAI_API_BASE"] == "http://localhost:8080/v1"
    assert body["env"]["OPENAI_API_KEY"] == "plain-key-xyz"
    # model echoed as requested.
    assert body["model"] == "provider:B.AI:gpt-5.5"


def test_resolve_aider_bare_model(monkeypatch) -> None:
    """A bare model id is passed straight through as openai/<model>."""
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)
    client = _client(monkeypatch, sf)

    r = client.post(
        "/api/cli-tools/resolve", json={"tool": "aider", "model": "gpt-5.5"}
    )
    rc = r.json()["run_command"]
    assert "--model openai/gpt-5.5" in rc


def test_resolve_aider_no_model_segment_omits_model(monkeypatch) -> None:
    """provider:<name> (no model) -> aider omits --model, keeps endpoint flags."""
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)
    client = _client(monkeypatch, sf)

    r = client.post(
        "/api/cli-tools/resolve", json={"tool": "aider", "model": "provider:B.AI"}
    )
    rc = r.json()["run_command"]
    assert "--openai-api-base" in rc
    assert "--openai-api-key" in rc
    assert "--model" not in rc


def test_resolve_aider_no_endpoint_uses_placeholder_key(monkeypatch) -> None:
    """No access-controlled endpoint -> aider gets the non-empty placeholder key
    in BOTH env and run_command (aider refuses to boot on an empty key)."""
    sf = _make_sf()
    _seed_all(sf)  # NOTE: no endpoint seeded
    client = _client(monkeypatch, sf)

    placeholder = cli_tools_router.PLACEHOLDER_API_KEY
    assert placeholder  # must be non-empty by design

    r = client.post(
        "/api/cli-tools/resolve",
        json={"tool": "aider", "model": "provider:B.AI:gpt-5.5"},
    )
    assert r.status_code == 200
    body = r.json()

    # env carries the placeholder (not empty).
    assert body["env"]["OPENAI_API_KEY"] == placeholder
    assert body["env"]["OPENAI_API_KEY"] != ""
    # aider run_command embeds the placeholder via --openai-api-key (non-empty).
    rc = body["run_command"]
    assert f"--openai-api-key {placeholder}" in rc
    assert "--openai-api-key " in rc
    assert "--openai-api-key\n" not in rc  # never a dangling empty flag


def test_resolve_non_aider_generic_form_preserved(monkeypatch) -> None:
    """A verified tool WITHOUT a dedicated builder falls back to the generic
    ``<binary> <flags> --model <ref>`` form + env injection (no custom flags)."""
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)
    client = _client(monkeypatch, sf)

    # Temporarily verify a builder-less tool to exercise the fallback route.
    monkeypatch.setitem(
        cli_presets.LAUNCH_SUPPORT,
        "llm",
        cli_presets.LaunchSupport(cli_presets.LAUNCH_VERIFIED),
    )

    r = client.post(
        "/api/cli-tools/resolve",
        json={"tool": "llm", "model": "provider:B.AI:gpt-5.5"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["run_command"] == "llm --model provider:B.AI:gpt-5.5"
    # generic tools do NOT get aider's custom-endpoint flags.
    assert "--openai-api-base" not in body["run_command"]
    assert body["env"]["OPENAI_API_BASE"] == "http://localhost:8080/v1"
    assert body["env"]["OPENAI_API_KEY"] == "plain-key-xyz"


def test_resolve_aider_key_not_persisted_to_logentry(monkeypatch) -> None:
    """R12/skill: the plaintext key embedded in aider's run_command must be
    masked in LogEntry (the API response still returns it plaintext, ADR-007)."""
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf, key="secret-key-abc")
    client = _client(monkeypatch, sf)

    r = client.post(
        "/api/cli-tools/resolve",
        json={"tool": "aider", "model": "provider:B.AI:gpt-5.5"},
    )
    # response carries the real key (ADR-007 plaintext to the caller)...
    assert "secret-key-abc" in r.json()["run_command"]
    # ...but the persisted LogEntry must NOT leak it.
    with sf() as s:
        entries = (
            s.query(LogEntry)
            .filter_by(source="backend.cli_tools.router")
            .all()
        )
    assert entries, "resolve must log an entry"
    assert all("secret-key-abc" not in (e.message or "") for e in entries)
    assert any("***" in (e.message or "") for e in entries)


# =========================================================================== #
# 6. Robust binary detection + always-present install_command.
#
# WHY: ``shutil.which`` only saw the SERVER process PATH. aigate started from a
# shell without e.g. ~/.local/bin reported aider as missing, so the frontend ran
# the INSTALL command for a tool that was already installed and would run fine
# in the PTY (real login PATH). Fix: broaden detection over common user install
# dirs AND always expose binary_name + install_command so the frontend can do
# the authoritative PTY-side check:
#   if command -v <binary_name>; then <run_command>; else <install_command>; fi
# =========================================================================== #
FAKE_TOOL = "aigate-fake-cli-tool"


def _make_fake_binary(directory: str, name: str) -> str:
    """Create an executable stub ``<directory>/<name>`` and return its path."""
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("#!/bin/sh\necho stub\n")
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return path


def test_which_with_extra_paths_finds_binary_off_base_path(monkeypatch, tmp_path) -> None:
    """A binary in ~/.local/bin is found even though it is NOT on the base PATH."""
    fake_home = tmp_path / "home"
    installed = _make_fake_binary(str(fake_home / ".local" / "bin"), FAKE_TOOL)

    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("PREFIX", raising=False)
    # base PATH = an empty dir -> plain which() cannot see the tool.
    empty = tmp_path / "emptybin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    assert shutil.which(FAKE_TOOL) is None  # sanity: old detection fails here
    assert cli_tools_router._which_with_extra_paths(FAKE_TOOL) == installed


def test_which_with_extra_paths_none_for_absent_binary(monkeypatch, tmp_path) -> None:
    """A genuinely absent binary still resolves to None (no false positive)."""
    monkeypatch.setenv("HOME", str(tmp_path / "nohome"))
    monkeypatch.delenv("PREFIX", raising=False)
    empty = tmp_path / "emptybin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    assert cli_tools_router._which_with_extra_paths(FAKE_TOOL) is None
    # empty/None-ish binary name is handled without touching the filesystem
    assert cli_tools_router._which_with_extra_paths("") is None


def test_which_with_extra_paths_still_honours_base_path(monkeypatch, tmp_path) -> None:
    """Base PATH entries keep working (extended search is additive, not a replace)."""
    on_path = _make_fake_binary(str(tmp_path / "sysbin"), FAKE_TOOL)
    monkeypatch.setenv("HOME", str(tmp_path / "nohome"))
    monkeypatch.delenv("PREFIX", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path / "sysbin"))

    assert cli_tools_router._which_with_extra_paths(FAKE_TOOL) == on_path


def test_extra_search_paths_only_returns_existing_dirs(monkeypatch, tmp_path) -> None:
    """Non-existent candidate dirs are skipped; the real HOME ones are kept."""
    fake_home = tmp_path / "home"
    (fake_home / ".cargo" / "bin").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("PREFIX", raising=False)

    paths = cli_tools_router._extra_search_paths()
    assert str(fake_home / ".cargo" / "bin") in paths
    # ~/.local/bin was never created -> must not appear
    assert str(fake_home / ".local" / "bin") not in paths
    # every returned entry really is a directory
    assert all(os.path.isdir(p) for p in paths)


def test_resolve_reports_binary_found_via_extra_paths(monkeypatch, tmp_path) -> None:
    """End-to-end: resolve flips binary_found True for a tool installed in a
    user dir missing from the server PATH (the original bug)."""
    sf = _make_sf()
    _seed_all(sf)

    fake_home = tmp_path / "home"
    _make_fake_binary(str(fake_home / ".npm-global" / "bin"), "aider")
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("PREFIX", raising=False)
    empty = tmp_path / "emptybin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    client = _client(monkeypatch, sf)
    r = client.post("/api/cli-tools/resolve", json={"tool": "aider"})
    assert r.status_code == 200
    body = r.json()
    assert body["binary_found"] is True
    assert body["binary_name"] == "aider"


def test_resolve_exposes_binary_name(monkeypatch) -> None:
    """``binary_name`` is part of ResolveDTO (frontend needs it for command -v).
    The name!=binary case (open-interpreter -> interpreter) is covered by the
    list endpoint, since only verified tools are resolvable."""
    sf = _make_sf()
    _seed_all(sf)
    client = _client(monkeypatch, sf)

    r = client.post("/api/cli-tools/resolve", json={"tool": "opencode"})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {
        "binary_found",
        "binary_name",
        "install_command",
        "run_command",
        "env",
        "model",
    }
    assert body["binary_name"] == "opencode"

    listed = client.get("/api/cli-tools").json()
    interp = [
        t
        for g in listed["data"]
        for t in g["tools"]
        if t["name"] == "open-interpreter"
    ][0]
    assert interp["binary_name"] == "interpreter"


def test_resolve_install_command_present_when_binary_found(monkeypatch) -> None:
    """install_command is ALWAYS the tool's install string — even when the
    server-side hint says the binary was found (behaviour intentionally changed:
    it used to be null when found). The frontend builds the 'else install'
    branch from it, so it must never be null/missing."""
    sf = _make_sf()
    _seed_all(sf)
    client = _client(monkeypatch, sf)

    monkeypatch.setattr(
        cli_tools_router,
        "_which_with_extra_paths",
        lambda binary: f"/fake/bin/{binary}",
    )

    r = client.post("/api/cli-tools/resolve", json={"tool": "aider"})
    assert r.status_code == 200
    body = r.json()
    assert body["binary_found"] is True
    assert body["install_command"] == "pip install aider-chat"
    assert body["install_command"] is not None

    # and the PTY-side branch the frontend builds is fully populated
    assert body["run_command"].startswith("aider")
    assert body["binary_name"] == "aider"


def test_resolve_install_command_present_when_not_found(monkeypatch) -> None:
    """Not-found case is unchanged: install_command still returned."""
    sf = _make_sf()
    _seed_all(sf)
    client = _client(monkeypatch, sf)

    monkeypatch.setattr(
        cli_tools_router, "_which_with_extra_paths", lambda binary: None
    )
    body = client.post("/api/cli-tools/resolve", json={"tool": "aider"}).json()
    assert body["binary_found"] is False
    assert body["install_command"]  # non-empty install string
    assert body["binary_name"] == "aider"



# =========================================================================== #
# 7. opencode launch builder: writes opencode.json (custom OpenAI-compatible
#    provider + top-level default ``model``) via a single-quoted heredoc, then
#    opens the interactive TUI (plain ``opencode`` — never ``opencode run``,
#    which is one-shot and hangs waiting on stdin in the PTY).
# =========================================================================== #
_HEREDOC_OPEN = "<<'AIGATE_EOF'\n"
_HEREDOC_CLOSE = "\nAIGATE_EOF\n"


def _extract_heredoc_json(run_command: str) -> dict:
    """Pull the JSON body written by ``cat > opencode.json <<'AIGATE_EOF'``."""
    assert "cat > opencode.json" in run_command
    assert _HEREDOC_OPEN in run_command
    assert _HEREDOC_CLOSE in run_command
    start = run_command.index(_HEREDOC_OPEN) + len(_HEREDOC_OPEN)
    end = run_command.index(_HEREDOC_CLOSE, start)
    return json.loads(run_command[start:end])


def test_resolve_opencode_writes_config_and_runs(monkeypatch) -> None:
    """opencode -> heredoc config (provider aigate + top-level model) + TUI."""
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)  # key = plain-key-xyz
    client = _client(monkeypatch, sf)

    r = client.post(
        "/api/cli-tools/resolve",
        json={"tool": "opencode", "model": "provider:B.AI:gpt-5.5"},
    )
    assert r.status_code == 200
    body = r.json()
    rc = body["run_command"]

    # 1. config is written via a single-quoted heredoc.
    assert "cat > opencode.json" in rc
    cfg = _extract_heredoc_json(rc)

    # 2. valid JSON with the custom provider under id ``aigate``.
    prov = cfg["provider"]["aigate"]
    assert prov["npm"] == "@ai-sdk/openai-compatible"
    assert prov["name"] == "aigate"
    assert prov["options"]["baseURL"] == "http://localhost:8080/v1"
    assert prov["options"]["apiKey"] == "plain-key-xyz"
    # no provider seeded -> falls back to the requested model id only.
    assert "gpt-5.5" in prov["models"]
    assert prov["models"]["gpt-5.5"]["name"] == "gpt-5.5"

    # 3. top-level default model preselects aigate/<raw> in the TUI.
    assert cfg["model"] == "aigate/gpt-5.5"
    # key order: $schema, model, provider
    assert list(cfg) == ["$schema", "model", "provider"]

    # 4. interactive TUI launched — NEVER the one-shot ``opencode run``.
    tail = rc.split(_HEREDOC_CLOSE)[-1]
    assert tail == "opencode"
    assert "opencode run" not in rc
    # the raw provider: ref must NOT leak into the command tail.
    assert "provider:" not in tail

    # env still injected (OPENAI_API_KEY belt-and-suspenders).
    assert body["env"]["OPENAI_API_BASE"] == "http://localhost:8080/v1"
    assert body["env"]["OPENAI_API_KEY"] == "plain-key-xyz"
    assert body["model"] == "provider:B.AI:gpt-5.5"


def test_resolve_opencode_lists_discovered_models(monkeypatch) -> None:
    """When the provider has discovered models, all are enumerated in the config."""
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)
    with sf() as s:
        p = Provider(name="B.AI", type="openai", base_url="https://x", api_key="k")
        s.add(p)
        s.commit()
        s.add_all(
            [
                ProviderModel(provider_id=p.id, model_id="gpt-5.5", model_name="GPT 5.5"),
                ProviderModel(provider_id=p.id, model_id="o3", model_name="o3"),
            ]
        )
        s.commit()
    client = _client(monkeypatch, sf)

    r = client.post(
        "/api/cli-tools/resolve",
        json={"tool": "opencode", "model": "provider:B.AI:gpt-5.5"},
    )
    assert r.status_code == 200
    rc = r.json()["run_command"]
    cfg = _extract_heredoc_json(rc)
    models = cfg["provider"]["aigate"]["models"]
    assert set(models) == {"gpt-5.5", "o3"}
    assert models["o3"]["name"] == "o3"
    # default model preselects the requested one; TUI (never ``opencode run``).
    assert cfg["model"] == "aigate/gpt-5.5"
    assert rc.split(_HEREDOC_CLOSE)[-1] == "opencode"
    assert "opencode run" not in rc


def test_resolve_opencode_no_model_opens_tui(monkeypatch) -> None:
    """No model chosen -> plain ``opencode`` (TUI), config still written,
    and NO top-level ``model`` key (nothing to preselect)."""
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)
    client = _client(monkeypatch, sf)

    r = client.post("/api/cli-tools/resolve", json={"tool": "opencode"})
    assert r.status_code == 200
    rc = r.json()["run_command"]
    cfg = _extract_heredoc_json(rc)
    assert cfg["provider"]["aigate"]["models"] == {}
    assert "model" not in cfg
    tail = rc.split(_HEREDOC_CLOSE)[-1]
    assert tail == "opencode"
    assert "run --model" not in tail


def test_resolve_opencode_combo_ref(monkeypatch) -> None:
    """combo:<name> -> opencode.json models map has key ``combo:<name>``, the
    top-level default model is ``aigate/combo:<name>``, and the interactive TUI
    is launched (the gateway resolver already routes combo refs, so the combo
    must be selectable)."""
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)  # key = plain-key-xyz
    with sf() as s:
        s.add(Combo(name="Test", strategy="fallback", enabled=True))
        s.commit()
    client = _client(monkeypatch, sf)

    r = client.post(
        "/api/cli-tools/resolve",
        json={"tool": "opencode", "model": "combo:Test"},
    )
    assert r.status_code == 200
    rc = r.json()["run_command"]

    # 1. config written via the single-quoted heredoc + valid JSON.
    cfg = _extract_heredoc_json(rc)
    prov = cfg["provider"]["aigate"]
    assert prov["npm"] == "@ai-sdk/openai-compatible"
    assert prov["options"]["baseURL"] == "http://localhost:8080/v1"
    assert prov["options"]["apiKey"] == "plain-key-xyz"

    # 2. the combo is the selectable model id (key == name == combo:Test).
    assert "combo:Test" in prov["models"]
    assert prov["models"]["combo:Test"]["name"] == "combo:Test"

    # 3. default model = aigate/combo:Test (provider id + combo ref).
    assert cfg["model"] == "aigate/combo:Test"

    # 4. interactive TUI launched (never one-shot ``opencode run``).
    assert rc.split(_HEREDOC_CLOSE)[-1] == "opencode"
    assert "opencode run" not in rc
    assert r.json()["model"] == "combo:Test"

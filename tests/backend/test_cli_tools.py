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
    Setting,
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
    # verified live on Termux: codex 0.122 dropped wire_api="chat" -> needs
    # /v1/responses, which the gateway does not serve
    assert modes["codex"] == ("unsupported", "responses_only")
    # pending: real CLI, launch form not written yet -> struck, reason empty
    assert modes["cline"] == ("verified", "")
    assert modes["llm"] == ("verified", "")
    assert modes["gptme"] == ("verified", "")
    assert modes["kilo"] == ("verified", "")
    assert modes["open-interpreter"] == ("verified", "")
    assert modes["oterm"] == ("verified", "")
    # unsupported: `pip install gpt-researcher` ships NO console script — the
    # tool is a library + web app, its documented "CLI" is a repo-checkout
    # one-shot script (python cli.py "<query>"), not a launchable binary
    assert modes["gpt-researcher"] == ("unsupported", "not_a_cli")


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
        ("claude", "unsupported", "anthropic_only"),  # needs /v1/messages
        ("codex", "unsupported", "responses_only"),  # needs /v1/responses
        ("antigravity", "unsupported", "not_a_cli"),  # GUI IDE, no binary
        # library + web app only: pip installs NO `gpt-researcher` binary
        ("gpt-researcher", "unsupported", "not_a_cli"),
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

    # oterm is verified but now HAS a builder — drop it for this test so the
    # builder-less fallback route is still exercised.
    monkeypatch.delitem(cli_tools_router._LAUNCH_BUILDERS, "oterm")

    r = client.post(
        "/api/cli-tools/resolve",
        json={"tool": "oterm", "model": "provider:B.AI:gpt-5.5"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["run_command"] == "oterm --model provider:B.AI:gpt-5.5"
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


# =========================================================================== #
# 8. aichat launch builder — verified against aichat 0.30.0 ON THE DEVICE.
#
# aichat's config field is `clients:` (a list of internally-tagged client
# configs). `custom_providers:` / `providers:` do not exist (both fail to load),
# and `models:` entries must be mappings (`- name: x`), not bare strings.
# The generated file is scoped with AICHAT_CONFIG_FILE so the user's own
# ~/.config/aichat/config.yaml is never overwritten.
# =========================================================================== #
AICHAT_CFG_FILE = "aichat-aigate.yaml"


def _heredoc_block(run_command: str, filename: str) -> str:
    """Body of ``cat > <filename> <<'AIGATE_EOF' ... AIGATE_EOF``."""
    open_tag = f"cat > {filename} <<'AIGATE_EOF'\n"
    assert open_tag in run_command, f"no heredoc for {filename}"
    start = run_command.index(open_tag) + len(open_tag)
    end = run_command.index(_HEREDOC_CLOSE, start)
    return run_command[start:end]


def test_resolve_aichat_writes_client_config_and_launches(monkeypatch) -> None:
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)  # key = plain-key-xyz
    client = _client(monkeypatch, sf)

    r = client.post(
        "/api/cli-tools/resolve",
        json={"tool": "aichat", "model": "provider:B.AI:gpt-5.5"},
    )
    assert r.status_code == 200
    rc = r.json()["run_command"]

    block = _heredoc_block(rc, AICHAT_CFG_FILE)
    assert 'model: "aigate:gpt-5.5"' in block  # client-name:MODEL (colon, not /)
    assert "clients:" in block
    assert "  - type: openai-compatible" in block
    assert '    name: "aigate"' in block
    assert '    api_base: "http://localhost:8080/v1"' in block
    assert '    api_key: "plain-key-xyz"' in block
    assert '      - name: "gpt-5.5"' in block  # ModelData mapping, not a string
    # the provider: ref must never leak into the config
    assert "provider:" not in block

    # scoped config + interactive aichat (no subcommand, no guessed flags)
    assert rc.split(_HEREDOC_CLOSE)[-1] == f"AICHAT_CONFIG_FILE={AICHAT_CFG_FILE} aichat"
    # env is still injected for the generic path
    assert r.json()["env"]["OPENAI_API_BASE"] == "http://localhost:8080/v1"


def test_resolve_aichat_enumerates_discovered_models(monkeypatch) -> None:
    """Whole provider is declared so aichat's /model can switch without relaunch."""
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
                ProviderModel(provider_id=p.id, model_id="glm-5.2", model_name="GLM 5.2"),
            ]
        )
        s.commit()
    client = _client(monkeypatch, sf)

    r = client.post(
        "/api/cli-tools/resolve",
        json={"tool": "aichat", "model": "provider:B.AI:glm-5.2"},
    )
    block = _heredoc_block(r.json()["run_command"], AICHAT_CFG_FILE)
    assert 'model: "aigate:glm-5.2"' in block
    assert '      - name: "gpt-5.5"' in block
    assert '      - name: "glm-5.2"' in block


def test_resolve_aichat_combo_ref(monkeypatch) -> None:
    """combo:<name> stays intact as the model part of aigate:combo:<name>."""
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)
    with sf() as s:
        s.add(Combo(name="Test", strategy="fallback", enabled=True))
        s.commit()
    client = _client(monkeypatch, sf)

    r = client.post(
        "/api/cli-tools/resolve", json={"tool": "aichat", "model": "combo:Test"}
    )
    block = _heredoc_block(r.json()["run_command"], AICHAT_CFG_FILE)
    assert 'model: "aigate:combo:Test"' in block
    assert '      - name: "combo:Test"' in block


def test_resolve_aichat_escapes_yaml_scalars(monkeypatch) -> None:
    """DB-sourced values are quoted+escaped, never interpolated bare."""
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf, key='we"ird\\key')
    client = _client(monkeypatch, sf)

    r = client.post("/api/cli-tools/resolve", json={"tool": "aichat", "model": "m1"})
    block = _heredoc_block(r.json()["run_command"], AICHAT_CFG_FILE)
    assert '    api_key: "we\\"ird\\\\key"' in block


def test_resolve_aichat_no_model_still_configures(monkeypatch) -> None:
    """No model chosen -> no top-level model key, client still declared."""
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)
    client = _client(monkeypatch, sf)

    r = client.post("/api/cli-tools/resolve", json={"tool": "aichat"})
    rc = r.json()["run_command"]
    block = _heredoc_block(rc, AICHAT_CFG_FILE)
    assert "model:" not in block
    assert "clients:" in block
    assert rc.split(_HEREDOC_CLOSE)[-1] == f"AICHAT_CONFIG_FILE={AICHAT_CFG_FILE} aichat"


# =========================================================================== #
# 9. Termux install route.
#
# WHY: on Termux, npm reports process.platform == "android" and therefore never
# installs the *-linux-arm64 binary an npm-shipped CLI needs at run time, while
# the Termux repo ships a working bionic build of the same tool. The portable
# string stays in the DB; the platform route is chosen per request.
# =========================================================================== #
def test_install_command_for_picks_the_termux_route() -> None:
    assert cli_presets.install_command_for(
        "aichat", "cargo install aichat", termux=True
    ) == "pkg install aichat"
    # non-Termux keeps the portable command
    assert cli_presets.install_command_for(
        "aichat", "cargo install aichat", termux=False
    ) == "cargo install aichat"
    # tools without a Termux package fall through to the portable string
    assert cli_presets.install_command_for(
        "aider", "pip install aider-chat", termux=True
    ) == "pip install aider-chat"


def test_resolve_uses_termux_install_on_termux(monkeypatch) -> None:
    sf = _make_sf()
    _seed_all(sf)
    client = _client(monkeypatch, sf)
    monkeypatch.setattr(cli_tools_router, "is_termux", lambda: True)

    body = client.post("/api/cli-tools/resolve", json={"tool": "aichat"}).json()
    assert body["install_command"] == "pkg install aichat"

    # ...and the list endpoint agrees with it
    listed = client.get("/api/cli-tools").json()
    aichat = [
        t for g in listed["data"] for t in g["tools"] if t["name"] == "aichat"
    ][0]
    assert aichat["install_command"] == "pkg install aichat"


# =========================================================================== #
# 10. qwen (Qwen Code) launch builder.
#
# Documented form (docs/users/configuration/auth.md): auth type ``openai`` +
# models declared under ``modelProviders.openai`` (id/name/baseUrl/envKey).
# Settings are layered and the PROJECT file <cwd>/.qwen/settings.json overrides
# the user's ~/.qwen/settings.json (docs/.../settings.md precedence table), so
# the generated file is project-scoped and never touches user config.
# =========================================================================== #
QWEN_CFG = ".qwen/settings.json"


def _qwen_cfg(run_command: str) -> dict:
    return json.loads(_heredoc_block(run_command, QWEN_CFG))


def test_resolve_qwen_writes_project_settings_and_opens_tui(monkeypatch) -> None:
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)  # key = plain-key-xyz
    client = _client(monkeypatch, sf)

    r = client.post(
        "/api/cli-tools/resolve",
        json={"tool": "qwen", "model": "provider:B.AI:gpt-5.5"},
    )
    assert r.status_code == 200
    rc = r.json()["run_command"]

    # the dir is created before the redirect, or `cat >` would fail
    assert "mkdir -p .qwen" in rc
    cfg = _qwen_cfg(rc)
    prov = cfg["modelProviders"]["openai"]
    assert prov[0]["id"] == "gpt-5.5"
    assert prov[0]["baseUrl"] == "http://localhost:8080/v1"
    assert prov[0]["envKey"] == "OPENAI_API_KEY"
    # non-interactive auth + preselected model
    assert cfg["security"]["auth"]["selectedType"] == "openai"
    assert cfg["model"]["name"] == "gpt-5.5"
    assert cfg["env"]["OPENAI_API_KEY"] == "plain-key-xyz"
    assert "provider:" not in json.dumps(cfg)

    # interactive TUI (no subcommand, no guessed flags)
    assert rc.split(_HEREDOC_CLOSE)[-1] == "qwen"


def test_resolve_qwen_enumerates_discovered_models(monkeypatch) -> None:
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
                ProviderModel(provider_id=p.id, model_id="glm-5.2", model_name="GLM 5.2"),
            ]
        )
        s.commit()
    client = _client(monkeypatch, sf)

    r = client.post(
        "/api/cli-tools/resolve", json={"tool": "qwen", "model": "provider:B.AI:glm-5.2"}
    )
    cfg = _qwen_cfg(r.json()["run_command"])
    assert [m["id"] for m in cfg["modelProviders"]["openai"]] == ["gpt-5.5", "glm-5.2"]
    assert cfg["model"]["name"] == "glm-5.2"


def test_resolve_qwen_combo_ref(monkeypatch) -> None:
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)
    with sf() as s:
        s.add(Combo(name="Test", strategy="fallback", enabled=True))
        s.commit()
    client = _client(monkeypatch, sf)

    r = client.post("/api/cli-tools/resolve", json={"tool": "qwen", "model": "combo:Test"})
    cfg = _qwen_cfg(r.json()["run_command"])
    assert cfg["modelProviders"]["openai"][0]["id"] == "combo:Test"
    assert cfg["model"]["name"] == "combo:Test"


def test_resolve_qwen_no_model_launches_for_interactive_auth(monkeypatch) -> None:
    """No model chosen -> no provider/model keys (nothing invented), env kept,
    and the auth-type pin is dropped so the user can pick inside the TUI."""
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)
    client = _client(monkeypatch, sf)

    r = client.post("/api/cli-tools/resolve", json={"tool": "qwen"})
    rc = r.json()["run_command"]
    cfg = _qwen_cfg(rc)
    assert "modelProviders" not in cfg
    assert "security" not in cfg
    assert "model" not in cfg
    assert cfg["env"]["OPENAI_API_KEY"] == "plain-key-xyz"
    assert rc.split(_HEREDOC_CLOSE)[-1] == "qwen"


# =========================================================================== #
# 11. llm launch builder — documented endpoint form, no config file needed.
#
# docs/other-models.md ("Run against an endpoint without configuring it"):
#   llm openai endpoint <base_url> -m <model> --key <key> --chat
# The command registers nothing and deliberately does NOT send the user's
# configured OpenAI key, so the gateway key is passed explicitly.
# =========================================================================== #
def test_resolve_llm_uses_documented_endpoint_chat(monkeypatch) -> None:
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)  # key = plain-key-xyz
    client = _client(monkeypatch, sf)

    r = client.post(
        "/api/cli-tools/resolve",
        json={"tool": "llm", "model": "provider:B.AI:gpt-5.5"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["run_command"] == (
        "llm openai endpoint http://localhost:8080/v1 "
        "-m gpt-5.5 --key plain-key-xyz --chat"
    )
    # no config file is written for llm (nothing in the user's llm home changes)
    assert "AIGATE_EOF" not in body["run_command"]
    assert "provider:" not in body["run_command"]


def test_resolve_llm_combo_ref_passed_verbatim(monkeypatch) -> None:
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)
    with sf() as s:
        s.add(Combo(name="Test", strategy="fallback", enabled=True))
        s.commit()
    client = _client(monkeypatch, sf)

    r = client.post("/api/cli-tools/resolve", json={"tool": "llm", "model": "combo:Test"})
    assert "-m combo:Test" in r.json()["run_command"]


def test_resolve_llm_no_model_lists_gateway_models(monkeypatch) -> None:
    """No model chosen -> discovery flag, never an invented model id."""
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)
    client = _client(monkeypatch, sf)

    r = client.post("/api/cli-tools/resolve", json={"tool": "llm"})
    rc = r.json()["run_command"]
    assert rc == "llm openai endpoint http://localhost:8080/v1 --models"
    assert " -m " not in rc  # never invent a model id


# =========================================================================== #
# 12. gptme launch builder — documented "Local" route for OpenAI-compatible
# servers (docs/providers.html):
#   OPENAI_BASE_URL="http://127.0.0.1:11434/v1" gptme 'hello' -m local/<model>
# The local/ prefix is required: direct openai/* GPT-5-class models are routed
# to /v1/responses, which the gateway does not serve.
# =========================================================================== #
def test_resolve_gptme_uses_base_url_env_and_local_prefix(monkeypatch) -> None:
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)  # key = plain-key-xyz
    client = _client(monkeypatch, sf)

    r = client.post(
        "/api/cli-tools/resolve",
        json={"tool": "gptme", "model": "provider:B.AI:gpt-5.5"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["run_command"] == (
        "OPENAI_BASE_URL=http://localhost:8080/v1 gptme -m local/gpt-5.5"
    )
    # key travels through the exported OPENAI_API_KEY, never a gptme flag
    assert "plain-key-xyz" not in body["run_command"]
    assert body["env"]["OPENAI_API_KEY"] == "plain-key-xyz"
    # no prompt -> interactive chat; never the responses-api prefix
    assert "openai/" not in body["run_command"]


def test_resolve_gptme_combo_ref_keeps_local_prefix(monkeypatch) -> None:
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)
    with sf() as s:
        s.add(Combo(name="Test", strategy="fallback", enabled=True))
        s.commit()
    client = _client(monkeypatch, sf)

    r = client.post("/api/cli-tools/resolve", json={"tool": "gptme", "model": "combo:Test"})
    assert "-m local/combo:Test" in r.json()["run_command"]


def test_resolve_gptme_quotes_a_base_url_with_shell_metacharacters(monkeypatch) -> None:
    sf = _make_sf()
    _seed_all(sf)
    with sf() as s:
        s.add(Setting(key="gateway_base_url", value="http://host/v1;rm -rf"))
        s.commit()
    client = _client(monkeypatch, sf)

    r = client.post("/api/cli-tools/resolve", json={"tool": "gptme", "model": "m1"})
    rc = r.json()["run_command"]
    assert rc.startswith("'http://host/v1;rm -rf' gptme") or rc.startswith(
        "OPENAI_BASE_URL='http://host/v1;rm -rf'"
    )


# =========================================================================== #
# 13. cline launch builder — documented CLI "quick provider setup"
# (apps/cli/README.md): cline auth --provider openai-native --apikey ...
# --modelid ... --baseurl ...  then the interactive TUI.
# DOCS-VERIFIED only: cline ships per-platform binaries with no Termux build.
# =========================================================================== #
def test_resolve_cline_registers_gateway_then_opens_tui(monkeypatch) -> None:
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)  # key = plain-key-xyz
    client = _client(monkeypatch, sf)

    r = client.post(
        "/api/cli-tools/resolve",
        json={"tool": "cline", "model": "provider:B.AI:gpt-5.5"},
    )
    assert r.status_code == 200
    rc = r.json()["run_command"]
    assert rc == (
        "cline auth --provider openai-native --apikey plain-key-xyz "
        "--modelid gpt-5.5 --baseurl http://localhost:8080/v1 && cline"
    )
    assert "provider:" not in rc


def test_resolve_cline_no_model_skips_setup(monkeypatch) -> None:
    """Nothing is invented: without a model the setup step is dropped entirely."""
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)
    client = _client(monkeypatch, sf)

    r = client.post("/api/cli-tools/resolve", json={"tool": "cline"})
    assert r.json()["run_command"] == "cline"


def test_resolve_cline_quotes_shell_metacharacters(monkeypatch) -> None:
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf, key='k;echo pwned')
    client = _client(monkeypatch, sf)

    r = client.post("/api/cli-tools/resolve", json={"tool": "cline", "model": "m 1"})
    rc = r.json()["run_command"]
    assert "'k;echo pwned'" in rc
    assert "'m 1'" in rc



# =========================================================================== #
# 14. kilo (Kilo Code CLI) launch builder — documented custom-provider form.
#
# docs/ai-providers/openai-compatible.md ("CLI" tab) + docs/code-with-ai/agents/
# custom-models.md: a provider key of our choosing with
# ``npm: "@ai-sdk/openai-compatible"`` + ``options.baseURL`` + a ``models`` map,
# default model as ``provider-id/model-id``.
#
# The file is OURS (``.kilo/aigate-kilo.json`` — not one of the filenames kilo
# auto-discovers) and is handed to the CLI through the trusted ``KILO_CONFIG``
# env var, for two documented reasons: writing ``.kilo/kilo.json`` /
# ``./kilo.json`` would clobber a user-owned project config, and a project
# config cannot resolve ``{env:VAR}`` (custom-models.md: references resolve "only
# when the config lives in a trusted location: your global config
# (~/.config/kilo), a config passed via KILO_CONFIG / KILO_CONFIG_CONTENT, or
# organization/MDM-managed config") — which would force the plaintext key onto
# disk. KILO_CONFIG is additive (cli-runtime.md precedence table loads global
# first, then the explicit file), so user config/auth survives and the key never
# lands on disk. DOCS-VERIFIED only: per-platform binaries, no Termux build
# (same case as cline).
# =========================================================================== #
KILO_CFG = ".kilo/aigate-kilo.json"
KILO_TAIL = "KILO_CONFIG=.kilo/aigate-kilo.json"


def _kilo_cfg(run_command: str) -> dict:
    return json.loads(_heredoc_block(run_command, KILO_CFG))


def test_resolve_kilo_writes_trusted_config_and_opens_tui(monkeypatch) -> None:
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)  # key = plain-key-xyz
    client = _client(monkeypatch, sf)

    r = client.post(
        "/api/cli-tools/resolve",
        json={"tool": "kilo", "model": "provider:B.AI:gpt-5.5"},
    )
    assert r.status_code == 200
    body = r.json()

    # exact command: mkdir (the redirect needs the dir), single-quoted heredoc,
    # then the TUI through KILO_CONFIG with the model flag (priority 1 per docs).
    assert body["run_command"] == (
        "mkdir -p .kilo\n"
        "cat > .kilo/aigate-kilo.json <<'AIGATE_EOF'\n"
        "{\n"
        '  "$schema": "https://app.kilo.ai/config.json",\n'
        '  "model": "aigate/gpt-5.5",\n'
        '  "provider": {\n'
        '    "aigate": {\n'
        '      "npm": "@ai-sdk/openai-compatible",\n'
        '      "options": {\n'
        '        "baseURL": "http://localhost:8080/v1",\n'
        '        "apiKey": "{env:OPENAI_API_KEY}"\n'
        "      },\n"
        '      "models": {\n'
        '        "gpt-5.5": {\n'
        '          "name": "gpt-5.5"\n'
        "        }\n"
        "      }\n"
        "    }\n"
        "  }\n"
        "}\n"
        "AIGATE_EOF\n"
        "KILO_CONFIG=.kilo/aigate-kilo.json kilo -m aigate/gpt-5.5"
    )
    # the provider: ref must NOT leak into the command or the config
    assert "provider:" not in body["run_command"]
    # the plaintext key is NOT in the command at all — it travels through the
    # exported OPENAI_API_KEY and kilo resolves {env:...} in the trusted file
    assert "plain-key-xyz" not in body["run_command"]
    assert "{env:OPENAI_API_KEY}" in body["run_command"]
    assert body["env"]["OPENAI_API_KEY"] == "plain-key-xyz"
    assert body["env"]["OPENAI_API_BASE"] == "http://localhost:8080/v1"
    assert body["model"] == "provider:B.AI:gpt-5.5"


def test_resolve_kilo_never_writes_a_user_config_path(monkeypatch) -> None:
    """`.kilo/kilo.json` + `./kilo.json[c]` belong to the user — never touch them."""
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)
    client = _client(monkeypatch, sf)

    rc = client.post(
        "/api/cli-tools/resolve", json={"tool": "kilo", "model": "m1"}
    ).json()["run_command"]
    for owned in ("cat > .kilo/kilo.json", "cat > kilo.json", "cat > kilo.jsonc"):
        assert owned not in rc


def test_resolve_kilo_enumerates_discovered_models(monkeypatch) -> None:
    """Whole provider is declared so kilo's /models can switch without relaunch."""
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
                ProviderModel(provider_id=p.id, model_id="glm-5.2", model_name="GLM 5.2"),
            ]
        )
        s.commit()
    client = _client(monkeypatch, sf)

    r = client.post(
        "/api/cli-tools/resolve", json={"tool": "kilo", "model": "provider:B.AI:glm-5.2"}
    )
    rc = r.json()["run_command"]
    cfg = _kilo_cfg(rc)
    prov = cfg["provider"]["aigate"]
    assert list(prov["models"]) == ["gpt-5.5", "glm-5.2"]
    assert prov["models"]["glm-5.2"]["name"] == "glm-5.2"
    # the requested model — not the first discovered one — is the default
    assert cfg["model"] == "aigate/glm-5.2"
    assert rc.endswith(f"{KILO_TAIL} kilo -m aigate/glm-5.2")


def test_resolve_kilo_combo_ref_passed_verbatim(monkeypatch) -> None:
    """combo:<name> stays verbatim in both the models map and the model ref."""
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)
    with sf() as s:
        s.add(Combo(name="Test", strategy="fallback", enabled=True))
        s.commit()
    client = _client(monkeypatch, sf)

    r = client.post(
        "/api/cli-tools/resolve", json={"tool": "kilo", "model": "combo:Test"}
    )
    rc = r.json()["run_command"]
    cfg = _kilo_cfg(rc)
    assert "combo:Test" in cfg["provider"]["aigate"]["models"]
    assert cfg["model"] == "aigate/combo:Test"
    assert rc.endswith(f"{KILO_TAIL} kilo -m aigate/combo:Test")


def test_resolve_kilo_no_model_opens_tui_without_inventing(monkeypatch) -> None:
    """No model chosen -> gateway still configured, but no model key and no -m."""
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)
    client = _client(monkeypatch, sf)

    r = client.post("/api/cli-tools/resolve", json={"tool": "kilo"})
    rc = r.json()["run_command"]
    cfg = _kilo_cfg(rc)
    assert "model" not in cfg
    assert cfg["provider"]["aigate"]["models"] == {}
    assert cfg["provider"]["aigate"]["options"]["baseURL"] == "http://localhost:8080/v1"
    # bare interactive TUI through our config, never a dangling -m / invented id
    assert rc.split(_HEREDOC_CLOSE)[-1] == f"{KILO_TAIL} kilo"
    assert " -m" not in rc


def test_resolve_kilo_quotes_the_model_flag(monkeypatch) -> None:
    """The one value interpolated into the command line is shell-quoted."""
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)
    client = _client(monkeypatch, sf)

    r = client.post(
        "/api/cli-tools/resolve", json={"tool": "kilo", "model": "m 1;echo pwned"}
    )
    rc = r.json()["run_command"]
    assert rc.endswith(f"{KILO_TAIL} kilo -m 'aigate/m 1;echo pwned'")
    # the same value is JSON-encoded (never bare) inside the config
    assert '"aigate/m 1;echo pwned"' in rc


# =========================================================================== #
# 15. open-interpreter launch builder — documented OpenAI-compatible flags for
# the PYTHON package that ``pip install open-interpreter`` installs (PyPI
# open-interpreter 0.4.3, 2024-10-26). The GitHub repo now hosts a DIFFERENT
# (Rust/Codex-fork) agent with no such flags, so the form is verified against
# the community fork's docs + the PyPI README (docs-only, read 2026-09-05):
#   docs/settings/all-settings.mdx  -> --api_base / --api_key / --model
#   docs/language-models/local-models/lm-studio.mdx -> any OpenAI-compatible
#     server via --api_base; llm.model = "openai/x" = "send messages in OpenAI's
#     format"
#   README "Interactive Chat" -> bare ``interpreter`` opens the interactive chat
# The model is sent as ``openai/<raw>`` (LiteLLM strips the prefix before the
# request, so the gateway gets the raw id / verbatim combo ref).
# =========================================================================== #
def test_resolve_open_interpreter_documented_flag_form(monkeypatch) -> None:
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)  # key = plain-key-xyz
    client = _client(monkeypatch, sf)

    r = client.post(
        "/api/cli-tools/resolve",
        json={"tool": "open-interpreter", "model": "provider:B.AI:gpt-5.5"},
    )
    assert r.status_code == 200
    body = r.json()
    # exact command: binary + the three documented flags, model in openai/ form
    assert body["run_command"] == (
        "interpreter --api_base http://localhost:8080/v1 "
        "--api_key plain-key-xyz --model openai/gpt-5.5"
    )
    # the provider: ref must NOT leak; the gateway receives the raw id
    assert "provider:" not in body["run_command"]
    # interactive chat: no positional prompt, no one-shot subcommand
    assert "interpreter exec" not in body["run_command"]
    # env is still injected for the generic path
    assert body["env"]["OPENAI_API_BASE"] == "http://localhost:8080/v1"
    assert body["env"]["OPENAI_API_KEY"] == "plain-key-xyz"
    assert body["model"] == "provider:B.AI:gpt-5.5"


def test_resolve_open_interpreter_combo_ref_verbatim(monkeypatch) -> None:
    """combo:<name> stays verbatim after the openai/ prefix (gateway routes it)."""
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)
    with sf() as s:
        s.add(Combo(name="Test", strategy="fallback", enabled=True))
        s.commit()
    client = _client(monkeypatch, sf)

    r = client.post(
        "/api/cli-tools/resolve",
        json={"tool": "open-interpreter", "model": "combo:Test"},
    )
    rc = r.json()["run_command"]
    assert "--model openai/combo:Test" in rc


def test_resolve_open_interpreter_no_model_omits_flag(monkeypatch) -> None:
    """provider:<name> (no model) -> documented LM-Studio form, no --model,
    no invented id; the endpoint flags stay."""
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)
    client = _client(monkeypatch, sf)

    r = client.post(
        "/api/cli-tools/resolve",
        json={"tool": "open-interpreter", "model": "provider:B.AI"},
    )
    rc = r.json()["run_command"]
    assert rc == (
        "interpreter --api_base http://localhost:8080/v1 --api_key plain-key-xyz"
    )
    assert "--model" not in rc


def test_resolve_open_interpreter_quotes_shell_metacharacters(monkeypatch) -> None:
    """Every interpolated value (base/key/model) is shlex-quoted."""
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf, key="k;echo pwned")
    with sf() as s:
        s.add(Setting(key="gateway_base_url", value="http://host/v1;rm -rf"))
        s.commit()
    client = _client(monkeypatch, sf)

    r = client.post(
        "/api/cli-tools/resolve",
        json={"tool": "open-interpreter", "model": "m 1"},
    )
    rc = r.json()["run_command"]
    assert "'http://host/v1;rm -rf'" in rc
    assert "'k;echo pwned'" in rc
    assert "'openai/m 1'" in rc


# =========================================================================== #
# 16. oterm launch builder — documented openaiCompatible config block +
# OTERM_DATA_DIR override (ggozad.github.io/oterm app_config.md, v0.24.0).
#
# oterm's config.json lives in its data dir; the default (~/.local/share/oterm)
# is USER-owned, so aigate writes its OWN namespaced dir (.oterm-aigate) and
# scopes the override to the launch command (kilo pattern). The key is NOT on
# disk: the config carries ${OPENAI_API_KEY} (oterm expands it at load) and the
# launcher exports it. There is no model/base/key CLI flag, so the command is
# identical for every ref shape and nothing is invented; the model is picked in
# oterm's new-chat dialog (gateway /v1/models feeds suggestions).
# =========================================================================== #
OTERM_CFG = ".oterm-aigate/config.json"
OTERM_TAIL = "OTERM_DATA_DIR=.oterm-aigate oterm"


def _oterm_cfg(run_command: str) -> dict:
    return json.loads(_heredoc_block(run_command, OTERM_CFG))


def test_resolve_oterm_writes_namespaced_config_and_opens_tui(monkeypatch) -> None:
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)  # key = plain-key-xyz
    client = _client(monkeypatch, sf)

    r = client.post(
        "/api/cli-tools/resolve",
        json={"tool": "oterm", "model": "provider:B.AI:gpt-5.5"},
    )
    assert r.status_code == 200
    body = r.json()

    # exact command: mkdir (the redirect needs the dir), single-quoted heredoc
    # writing the openaiCompatible block, then the TUI via OTERM_DATA_DIR.
    assert body["run_command"] == (
        "mkdir -p .oterm-aigate\n"
        "cat > .oterm-aigate/config.json <<'AIGATE_EOF'\n"
        "{\n"
        '  "openaiCompatible": {\n'
        '    "aigate": {\n'
        '      "base_url": "http://localhost:8080/v1",\n'
        '      "api_key": "${OPENAI_API_KEY}"\n'
        "    }\n"
        "  }\n"
        "}\n"
        "AIGATE_EOF\n"
        "OTERM_DATA_DIR=.oterm-aigate oterm"
    )
    cfg = _oterm_cfg(body["run_command"])
    ep = cfg["openaiCompatible"]["aigate"]
    assert ep["base_url"] == "http://localhost:8080/v1"
    # the plaintext key is NOT in the command or the config — it travels
    # through the exported OPENAI_API_KEY, which oterm expands ${VAR} against
    assert "plain-key-xyz" not in body["run_command"]
    assert ep["api_key"] == "${OPENAI_API_KEY}"
    # interactive TUI (no subcommand, no one-shot), never a leaked provider: ref
    assert body["run_command"].split(_HEREDOC_CLOSE)[-1] == OTERM_TAIL
    assert "provider:" not in body["run_command"]
    assert body["env"]["OPENAI_API_BASE"] == "http://localhost:8080/v1"
    assert body["env"]["OPENAI_API_KEY"] == "plain-key-xyz"
    assert body["model"] == "provider:B.AI:gpt-5.5"


def test_resolve_oterm_never_writes_a_user_config_path(monkeypatch) -> None:
    """The namespaced dir is ours; oterm's default data dir is never touched."""
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)
    client = _client(monkeypatch, sf)

    rc = client.post(
        "/api/cli-tools/resolve", json={"tool": "oterm", "model": "m1"}
    ).json()["run_command"]
    for owned in (
        "cat > config.json",
        ".local/share/oterm",
        "XDG_DATA_HOME",
    ):
        assert owned not in rc


def test_resolve_oterm_command_is_ref_invariant_and_invents_nothing(monkeypatch) -> None:
    """No model/base CLI flag exists for oterm, so provider / combo / no-model
    refs all yield the SAME command (nothing is guessed onto the command line)."""
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)
    with sf() as s:
        s.add(Combo(name="Test", strategy="fallback", enabled=True))
        s.commit()
    client = _client(monkeypatch, sf)

    cmds = {}
    for ref in ("provider:B.AI:gpt-5.5", "combo:Test", "gpt-5.5", None):
        r = client.post(
            "/api/cli-tools/resolve",
            json={"tool": "oterm", "model": ref},
        )
        assert r.status_code == 200
        cmds[ref] = r.json()["run_command"]

    assert len(set(cmds.values())) == 1
    rc = cmds[None]
    # nothing about the model leaks into the command (it is chosen in the TUI)
    assert "--model" not in rc
    assert "gpt-5.5" not in rc
    assert "combo" not in rc


def test_resolve_oterm_json_encodes_a_base_url_with_metacharacters(monkeypatch) -> None:
    """DB-sourced base url is JSON-encoded inside the single-quoted heredoc, so
    shell metacharacters are inert (never interpolated bare into the command)."""
    sf = _make_sf()
    _seed_all(sf)
    with sf() as s:
        s.add(Setting(key="gateway_base_url", value="http://host/v1;rm -rf"))
        s.commit()
    client = _client(monkeypatch, sf)

    rc = client.post(
        "/api/cli-tools/resolve", json={"tool": "oterm", "model": "m1"}
    ).json()["run_command"]
    cfg = _oterm_cfg(rc)
    assert cfg["openaiCompatible"]["aigate"]["base_url"] == "http://host/v1;rm -rf"
    # the dangerous value only ever appears INSIDE the quoted heredoc body
    block = _heredoc_block(rc, OTERM_CFG)
    assert "http://host/v1;rm -rf" in block
    tail = rc.split(_HEREDOC_CLOSE)[-1]
    assert "rm -rf" not in tail

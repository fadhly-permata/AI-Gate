"""CLI Tools backend tests (task B3.4): seed + list + resolve.

Hermetic, no on-disk DB. Mirrors ``test_endpoints.py``: an in-memory SQLite
engine (StaticPool) replaces every ``SessionLocal`` binding the routers and the
logger touch. ``backend.log`` references ``backend.config.db`` via the module
object (``_db.SessionLocal``), so patching ``backend.config.db.SessionLocal``
also covers the logger. We additionally patch ``backend.cli_tools_router``.
"""

from __future__ import annotations

import json
import os
import shutil
import stat

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.cli_presets as cli_presets
import backend.cli_tools_router as cli_tools_router
import backend.config.db as db_mod
from backend.config.db import Base
from backend.models import CLITool, CLIToolGroup, Endpoint, LogEntry, Provider, ProviderModel
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
# 1. Seeding: 3 groups + tool counts (12 / 6 / 6)
# =========================================================================== #
def test_seed_cli_tools(monkeypatch) -> None:
    sf = _make_sf()
    with sf() as s:
        inserted = cli_presets.seed_cli_tools(s)
        assert inserted == 3

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

        # specific mappings
        claude = s.query(CLITool).filter_by(name="claude").first()
        assert claude.binary_name == "claude"
        assert claude.install_command == "pip install claude-code"
        assert claude.default_flags == "openai-compatible"
        assert claude.enabled is True

        interp = s.query(CLITool).filter_by(name="open-interpreter").first()
        assert interp.binary_name == "interpreter"

        # default binary falls back to name
        ollama_style = s.query(CLITool).filter_by(name="llm").first()
        assert ollama_style.binary_name == "llm"
        assert ollama_style.install_command == "pip install llm"

    # idempotent: second call inserts nothing
    with sf() as s:
        assert cli_presets.seed_cli_tools(s) == 0


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

    # ToolDTO shape
    tool = by_code["chat_shell"]["tools"][0]
    assert set(tool) == {
        "id",
        "name",
        "binary_name",
        "install_command",
        "default_flags",
        "enabled",
    }


# =========================================================================== #
# 3. POST /api/cli-tools/resolve for a tool name -> ResolveDTO
# =========================================================================== #
def test_resolve_tool_by_name(monkeypatch) -> None:
    sf = _make_sf()
    _seed_all(sf)
    client = _client(monkeypatch, sf)

    r = client.post("/api/cli-tools/resolve", json={"tool": "llm"})
    assert r.status_code == 200
    body = r.json()

    assert body["run_command"].startswith("llm")
    # gateway env injected
    assert body["env"]["OPENAI_API_BASE"] == "http://localhost:8080/v1"
    # no access-controlled endpoint seeded -> non-empty placeholder so CLIs like
    # aider accept the key (gateway ignores it while access control is off).
    assert body["env"]["OPENAI_API_KEY"] == cli_tools_router.PLACEHOLDER_API_KEY
    assert body["env"]["OPENAI_API_KEY"] != ""
    # llm binary not on PATH in sandbox -> install command present
    assert body["binary_found"] is False
    assert body["install_command"] == "pip install llm"
    assert body["model"] is None


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
        "/api/cli-tools/resolve", json={"tool": "claude", "model": "gpt-4o"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["run_command"] == "claude openai-compatible --model gpt-4o"
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
    """Non-aider tools keep the generic <binary> <flags> --model <ref> form."""
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)
    client = _client(monkeypatch, sf)

    r = client.post(
        "/api/cli-tools/resolve",
        json={"tool": "claude", "model": "provider:B.AI:gpt-5.5"},
    )
    body = r.json()
    assert body["run_command"] == (
        "claude openai-compatible --model provider:B.AI:gpt-5.5"
    )
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
    _make_fake_binary(str(fake_home / ".npm-global" / "bin"), "llm")
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("PREFIX", raising=False)
    empty = tmp_path / "emptybin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    client = _client(monkeypatch, sf)
    r = client.post("/api/cli-tools/resolve", json={"tool": "llm"})
    assert r.status_code == 200
    body = r.json()
    assert body["binary_found"] is True
    assert body["binary_name"] == "llm"


def test_resolve_exposes_binary_name(monkeypatch) -> None:
    """``binary_name`` is part of ResolveDTO (frontend needs it for command -v)."""
    sf = _make_sf()
    _seed_all(sf)
    client = _client(monkeypatch, sf)

    r = client.post("/api/cli-tools/resolve", json={"tool": "open-interpreter"})
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
    # name != binary for this preset (open-interpreter -> interpreter)
    assert body["binary_name"] == "interpreter"


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

    r = client.post("/api/cli-tools/resolve", json={"tool": "llm"})
    assert r.status_code == 200
    body = r.json()
    assert body["binary_found"] is True
    assert body["install_command"] == "pip install llm"
    assert body["install_command"] is not None

    # and the PTY-side branch the frontend builds is fully populated
    assert body["run_command"].startswith("llm")
    assert body["binary_name"] == "llm"


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
#    provider) via a single-quoted heredoc, then runs opencode with the chosen
#    model as ``aigate/<model>`` (or the TUI when none chosen).
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
    """opencode -> heredoc config (provider aigate) + ``opencode run --model``."""
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

    # 3. opencode is launched with the selected model as aigate/<raw>.
    assert "opencode run --model aigate/gpt-5.5" in rc
    # the raw provider: ref must NOT leak into the --model value.
    assert "provider:" not in rc.split(_HEREDOC_CLOSE)[-1]

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
    cfg = _extract_heredoc_json(r.json()["run_command"])
    models = cfg["provider"]["aigate"]["models"]
    assert set(models) == {"gpt-5.5", "o3"}
    assert models["o3"]["name"] == "o3"
    # still launches the specifically requested model.
    assert "opencode run --model aigate/gpt-5.5" in r.json()["run_command"]


def test_resolve_opencode_no_model_opens_tui(monkeypatch) -> None:
    """No model chosen -> plain ``opencode`` (TUI), config still written."""
    sf = _make_sf()
    _seed_all(sf)
    _seed_endpoint(sf)
    client = _client(monkeypatch, sf)

    r = client.post("/api/cli-tools/resolve", json={"tool": "opencode"})
    assert r.status_code == 200
    rc = r.json()["run_command"]
    cfg = _extract_heredoc_json(rc)
    assert cfg["provider"]["aigate"]["models"] == {}
    tail = rc.split(_HEREDOC_CLOSE)[-1]
    assert tail == "opencode"
    assert "run --model" not in tail

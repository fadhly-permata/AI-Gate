"""CLI Tools backend tests (task B3.4): seed + list + resolve.

Hermetic, no on-disk DB. Mirrors ``test_endpoints.py``: an in-memory SQLite
engine (StaticPool) replaces every ``SessionLocal`` binding the routers and the
logger touch. ``backend.log`` references ``backend.config.db`` via the module
object (``_db.SessionLocal``), so patching ``backend.config.db.SessionLocal``
also covers the logger. We additionally patch ``backend.cli_tools_router``.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.cli_presets as cli_presets
import backend.cli_tools_router as cli_tools_router
import backend.config.db as db_mod
from backend.config.db import Base
from backend.models import CLITool, CLIToolGroup, Endpoint, LogEntry
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
    # no access-controlled endpoint seeded -> empty key (ADR-007 plaintext "")
    assert body["env"]["OPENAI_API_KEY"] == ""
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


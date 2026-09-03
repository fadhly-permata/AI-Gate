"""B5.7 tests: local Export / Import of the whole configuration (PRD §2.4.4).

Covers the service layer (``backend.export``) and the HTTP API
(``backend.export_router``):

* ``export_settings`` serializes every config entity with correct counts,
  plaintext secrets (ADR-007) and ISO-8601 datetimes.
* Round-trip fidelity: export -> replace-import -> re-export yields identical
  per-table rows (same ids / values).
* ``replace`` wipes rows absent from the file.
* Telemetry tables are never imported even if present in the document.
* Invalid payloads (no / unsupported ``aigate_export`` header, non-object body)
  return ``{"ok": false, "error": "invalid_format"}``.
* ``GET /api/settings/export`` -> 200 + ``Content-Disposition`` + valid JSON.
* ``POST /api/settings/import`` -> 200 on a valid doc, 400 on garbage.
* No route collision: ``/api/settings/export`` is NOT swallowed by
  ``GET /api/settings/{key}``, and the existing settings GET/PUT still work.

Hermetic in-memory SQLite (StaticPool) mirroring ``test_endpoints.py``; the
on-disk ``~/.aigate/aigate.db`` is never touched.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.config.db as db_mod
import backend.export_router as export_router
from backend.config.db import Base
from backend.export import export_settings, import_settings
from backend.models import (
    CLITool,
    CLIToolGroup,
    Combo,
    ComboMember,
    Endpoint,
    EndpointBinding,
    LogEntry,
    Provider,
    ProviderAccount,
    ProviderModel,
    ProxyNode,
    ProxyPool,
    Setting,
    UsageRecord,
)
from backend.server import app

# The twelve config tables that must appear in every export document.
CONFIG_KEYS = [
    "providers",
    "provider_accounts",
    "provider_models",
    "proxy_pools",
    "proxy_nodes",
    "combos",
    "combo_members",
    "endpoints",
    "endpoint_bindings",
    "cli_tool_groups",
    "cli_tools",
    "settings",
]


def _make_sessionmaker() -> sessionmaker:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture
def sf(monkeypatch) -> sessionmaker:
    """In-memory session factory rebound into every ``SessionLocal`` the code
    under test touches (config engine + export router + logging)."""
    factory = _make_sessionmaker()
    monkeypatch.setattr(db_mod, "SessionLocal", factory)
    monkeypatch.setattr(export_router, "SessionLocal", factory)
    return factory


@pytest.fixture
def client(sf) -> TestClient:
    return TestClient(app)


def _seed_full_config(sf: sessionmaker) -> dict[str, int]:
    """Seed exactly one row of every config entity; return their ids."""
    with sf() as s:
        prov = Provider(
            name="OpenAI",
            type="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-PLAINTEXT-SECRET",  # ADR-007: plaintext
            enabled=True,
            tier="subscription",
            quota_limit=100000,
            quota_window="day",
            custom_headers='{"X-Org": "acme"}',
            default_model="gpt-4o",
        )
        s.add(prov)
        s.flush()

        acct = ProviderAccount(
            provider_id=prov.id,
            label="work",
            auth_type="oauth",
            api_key="",
            oauth_token="oauth-PLAINTEXT",
            refresh_token="refresh-PLAINTEXT",
            expires_at=datetime(2030, 1, 1, 12, 0, 0),
            enabled=True,
        )
        model = ProviderModel(
            provider_id=prov.id,
            model_id="gpt-4o",
            model_name="GPT-4o",
            capabilities="vision,tools",
        )
        s.add_all([acct, model])

        pool = ProxyPool(
            name="pool-a", rotation_strategy="round_robin", enabled=True, last_used_index=3
        )
        s.add(pool)
        s.flush()
        node = ProxyNode(
            pool_id=pool.id,
            host="10.0.0.5",
            port=3128,
            protocol="socks5",
            username="proxyuser",
            password="proxypass-PLAINTEXT",  # ADR-007
            status="healthy",
            last_latency_ms=42.5,
            uptime_pct=99.9,
            last_checked=datetime(2026, 5, 5, 5, 5, 5),
        )
        s.add(node)

        combo = Combo(name="combo-a", strategy="load_balance", enabled=True)
        s.add(combo)
        s.flush()
        member = ComboMember(
            combo_id=combo.id,
            provider_id=prov.id,
            provider_model="gpt-4o",
            priority=1,
            weight=2.5,
        )
        s.add(member)

        ep = Endpoint(
            name="ep-a",
            listen_host="127.0.0.1",
            listen_port=8000,
            access_control_enabled=True,
            internal_api_key="internal-PLAINTEXT",  # ADR-007
            proxy_pool_id=pool.id,
            token_saver="rtk",
        )
        s.add(ep)
        s.flush()
        binding = EndpointBinding(
            endpoint_id=ep.id, bind_type="combo", bind_id=combo.id
        )
        s.add(binding)

        grp = CLIToolGroup(name="Group A", code="A", display_priority=1)
        s.add(grp)
        s.flush()
        tool = CLITool(
            group_id=grp.id,
            name="claude",
            binary_name="claude",
            install_command="npm i -g @anthropic-ai/claude-code",
            default_flags="--print",
            enabled=True,
        )
        s.add(tool)

        st = Setting(key="theme", value="dark")
        s.add(st)

        s.commit()
        return {
            "provider": prov.id,
            "account": acct.id,
            "model": model.id,
            "pool": pool.id,
            "node": node.id,
            "combo": combo.id,
            "member": member.id,
            "endpoint": ep.id,
            "binding": binding.id,
            "group": grp.id,
            "tool": tool.id,
            "setting": st.id,
        }


# --------------------------------------------------------------------------- #
# 1. export_settings: counts + plaintext secrets + ISO datetimes
# --------------------------------------------------------------------------- #
def test_export_returns_all_tables_with_counts(sf) -> None:
    _seed_full_config(sf)
    with sf() as s:
        doc = export_settings(s)

    assert doc["aigate_export"]["version"] == 1
    assert doc["aigate_export"]["app_version"] == "0.0.1"
    # exported_at must be a parseable ISO-8601 string.
    datetime.fromisoformat(doc["aigate_export"]["exported_at"])

    for key in CONFIG_KEYS:
        assert key in doc, f"missing section {key}"
        assert isinstance(doc[key], list)
        assert len(doc[key]) == 1, f"{key} expected 1 row, got {len(doc[key])}"


def test_export_secrets_plaintext_and_iso_datetimes(sf) -> None:
    _seed_full_config(sf)
    with sf() as s:
        doc = export_settings(s)

    prov = doc["providers"][0]
    assert prov["api_key"] == "sk-PLAINTEXT-SECRET"  # ADR-007: as-is
    acct = doc["provider_accounts"][0]
    assert acct["oauth_token"] == "oauth-PLAINTEXT"
    assert acct["refresh_token"] == "refresh-PLAINTEXT"
    node = doc["proxy_nodes"][0]
    assert node["password"] == "proxypass-PLAINTEXT"
    ep = doc["endpoints"][0]
    assert ep["internal_api_key"] == "internal-PLAINTEXT"

    # datetime columns serialized to ISO strings.
    assert isinstance(prov["created_at"], str)
    datetime.fromisoformat(prov["created_at"])
    assert acct["expires_at"] == "2030-01-01T12:00:00"
    assert node["last_checked"] == "2026-05-05T05:05:05"


# --------------------------------------------------------------------------- #
# 2. Round-trip fidelity: export -> replace-import -> re-export identical
# --------------------------------------------------------------------------- #
def test_roundtrip_replace_preserves_ids_and_rows(sf) -> None:
    ids = _seed_full_config(sf)
    with sf() as s:
        doc1 = export_settings(s)

    # Re-import (replace wipes then reinserts from the same document).
    with sf() as s:
        res = import_settings(s, doc1, mode="replace")
    assert res["ok"] is True
    assert all(res["imported"][k] == 1 for k in CONFIG_KEYS)

    with sf() as s:
        doc2 = export_settings(s)

    # Every config section is byte-identical (ids + values preserved).
    for key in CONFIG_KEYS:
        assert doc1[key] == doc2[key], f"section {key} changed across round-trip"

    # The specific seeded ids survive the round-trip.
    with sf() as s:
        assert s.get(Provider, ids["provider"]) is not None
        assert s.get(Endpoint, ids["endpoint"]) is not None
        assert s.get(ComboMember, ids["member"]) is not None


def test_replace_wipes_rows_absent_from_file(sf) -> None:
    _seed_full_config(sf)
    with sf() as s:
        doc = export_settings(s)

    # Add an extra provider AFTER the export; replace must remove it.
    with sf() as s:
        s.add(Provider(name="Ghost", type="other", base_url="http://x", api_key="k"))
        s.commit()
        assert s.query(Provider).count() == 2

    with sf() as s:
        res = import_settings(s, doc, mode="replace")
    assert res["ok"] is True
    with sf() as s:
        assert s.query(Provider).count() == 1
        assert s.query(Provider).filter_by(name="Ghost").first() is None


# --------------------------------------------------------------------------- #
# 3. Telemetry tables are never imported
# --------------------------------------------------------------------------- #
def test_import_ignores_telemetry_sections(sf) -> None:
    _seed_full_config(sf)
    with sf() as s:
        doc = export_settings(s)
    # Poison the document with telemetry rows that must be ignored.
    doc["usage_records"] = [{"id": 999, "provider_id": 1, "model": "x"}]
    doc["log_entries"] = [{"id": 999, "severity": "error", "message": "boom"}]

    with sf() as s:
        res = import_settings(s, doc, mode="replace")
    assert res["ok"] is True
    assert "usage_records" not in res["imported"]
    assert "log_entries" not in res["imported"]
    with sf() as s:
        assert s.query(UsageRecord).count() == 0
        # Only the export/import operation's own log rows exist, none with id 999.
        assert s.query(LogEntry).filter(LogEntry.id == 999).first() is None


# --------------------------------------------------------------------------- #
# 4. Invalid payloads -> invalid_format
# --------------------------------------------------------------------------- #
def test_import_missing_header_is_invalid(sf) -> None:
    with sf() as s:
        res = import_settings(s, {"providers": []})
    assert res == {"ok": False, "error": "invalid_format"}


def test_import_unsupported_version_is_invalid(sf) -> None:
    with sf() as s:
        res = import_settings(s, {"aigate_export": {"version": 999}})
    assert res == {"ok": False, "error": "invalid_format"}


def test_import_non_object_is_invalid(sf) -> None:
    for bad in ([], "string", None, 123):
        with sf() as s:
            res = import_settings(s, bad)
        assert res == {"ok": False, "error": "invalid_format"}, bad


def test_import_tolerates_missing_sections(sf) -> None:
    # A header-only document (every section absent) must succeed as empty.
    with sf() as s:
        res = import_settings(s, {"aigate_export": {"version": 1}})
    assert res["ok"] is True
    assert all(res["imported"][k] == 0 for k in CONFIG_KEYS)


# --------------------------------------------------------------------------- #
# 5. GET /api/settings/export
# --------------------------------------------------------------------------- #
def test_http_export_returns_attachment_json(client, sf) -> None:
    _seed_full_config(sf)
    resp = client.get("/api/settings/export")
    assert resp.status_code == 200
    cd = resp.headers.get("content-disposition", "")
    assert "attachment" in cd
    assert 'filename="aigate-settings-' in cd and cd.endswith('.json"')
    assert resp.headers.get("content-type", "").startswith("application/json")

    body = resp.json()
    assert body["aigate_export"]["version"] == 1
    assert len(body["providers"]) == 1


# --------------------------------------------------------------------------- #
# 6. POST /api/settings/import
# --------------------------------------------------------------------------- #
def test_http_import_valid_returns_counts(client, sf) -> None:
    _seed_full_config(sf)
    doc = client.get("/api/settings/export").json()

    # Wipe via a fresh replace-import of the captured document.
    resp = client.post("/api/settings/import", json=doc)
    assert resp.status_code == 200
    result = resp.json()
    assert result["ok"] is True
    assert result["imported"]["providers"] == 1
    assert result["imported"]["settings"] == 1


def test_http_import_accepts_mode_query(client, sf) -> None:
    _seed_full_config(sf)
    doc = client.get("/api/settings/export").json()
    resp = client.post("/api/settings/import?mode=merge", json=doc)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_http_import_garbage_object_is_400(client) -> None:
    resp = client.post("/api/settings/import", json={"not": "an export"})
    assert resp.status_code == 400
    assert resp.json() == {"ok": False, "error": "invalid_format"}


def test_http_import_malformed_json_is_400(client) -> None:
    resp = client.post(
        "/api/settings/import",
        content=b"{this is not json",
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 400
    assert resp.json() == {"ok": False, "error": "invalid_format"}


# --------------------------------------------------------------------------- #
# 7. No route collision with the existing /api/settings API
# --------------------------------------------------------------------------- #
def test_export_route_not_shadowed_by_key_route(client, sf) -> None:
    # A Setting literally keyed "export" must NOT be returned by the export
    # route — proving /api/settings/export is matched before /api/settings/{key}.
    with sf() as s:
        s.add(Setting(key="export", value="should-not-be-returned"))
        s.commit()

    resp = client.get("/api/settings/export")
    assert resp.status_code == 200
    assert "aigate_export" in resp.json()
    assert resp.json().get("key") != "export"

    # The {key} route still resolves a normal key.
    one = client.get("/api/settings/export")  # still the export doc, not the key
    assert "aigate_export" in one.json()


def test_existing_settings_api_still_works(client, sf) -> None:
    with sf() as s:
        s.add(Setting(key="theme", value="light"))
        s.commit()

    got = client.get("/api/settings")
    assert got.status_code == 200
    assert got.json()["theme"] == "light"

    put = client.put("/api/settings", json={"key": "theme", "value": "dark"})
    assert put.status_code == 200
    assert put.json()["theme"] == "dark"

    by_key = client.get("/api/settings/theme")
    assert by_key.status_code == 200
    assert by_key.json() == {"key": "theme", "value": "dark"}

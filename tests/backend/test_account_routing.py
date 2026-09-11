"""Provider-account routing engine tests (9router multi-account strategy).

Covers the WIP landed in ``a237414`` + the review follow-up:

* ``fill-first``   — priority asc, id asc, skip unavailable (raise OR empty cred);
* ``round-robin``  — STICKY for ``sticky_round_robin_limit`` calls (read from
  the COLUMN, never hardcoded), then advance by least-recently-used
  (``last_used_at`` asc, NULL first, id asc);
* pin ``x-connection-id`` — wins over both strategies; an unusable pin
  (unknown / disabled / foreign / raising / empty cred) falls back (fail-safe);
* legacy fallback  — no accounts / all unavailable -> ``provider.api_key``;
* DTO + validation on /api/providers + /api/accounts — including the partial
  ``PUT /api/accounts/{id}`` edit (label | api_key | enabled | priority; absent
  fields never overwritten; ``auth_type`` ignored; oauth+key rejected);
* the idempotent self-heal migration in ``backend.config.db``.

Hermetic in-memory SQLite (StaticPool), mirroring ``test_accounts.py``. The
conftest already redirects the module-level DB to a session temp file.
"""

from __future__ import annotations

import types
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.accounts_router as accounts_router
import backend.combo_routing as combo_routing
import backend.combos_router as combos_router
import backend.config.db as db_mod
import backend.gateway.resolver as resolver
import backend.oauth as oauth
import backend.providers_router as providers_router
from backend.config import db as db_module
from backend.config.db import Base
from backend.gateway.router import CONNECTION_ID_HEADER, _preferred_account_id
from backend.models import LogEntry, Provider, ProviderAccount, ProviderModel
from backend.server import app


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _reset_sticky() -> None:
    """The sticky counter is module-global in-memory state; never leak it."""
    oauth.reset_routing_state()
    yield
    oauth.reset_routing_state()


def _make_sessionmaker() -> sessionmaker:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _patch_db(monkeypatch, sf: sessionmaker) -> None:
    monkeypatch.setattr(db_mod, "SessionLocal", sf)
    monkeypatch.setattr(resolver, "SessionLocal", sf)
    monkeypatch.setattr(providers_router, "SessionLocal", sf)
    monkeypatch.setattr(accounts_router, "SessionLocal", sf)
    monkeypatch.setattr(combo_routing, "SessionLocal", sf)
    monkeypatch.setattr(combos_router, "SessionLocal", sf)


def _seed(
    sf: sessionmaker,
    *,
    strategy: str = "fill-first",
    sticky: int = 3,
    accounts: list[dict] | None = None,
) -> dict:
    """Seed one provider + its accounts. ``accounts`` items: label, priority,
    api_key (default per-label), enabled, auth_type (default 'api_key'),
    oauth_token (default ''). Returns ids + the provider id."""
    accounts = accounts or []
    with sf() as session:
        provider = Provider(
            name="rt",
            type="openai",
            base_url="http://provider.test/v1",
            api_key="sk-legacy",
            enabled=True,
            fallback_strategy=strategy,
            sticky_round_robin_limit=sticky,
        )
        session.add(provider)
        session.flush()
        session.add(
            ProviderModel(
                provider_id=provider.id,
                model_id="m1",
                model_name="M1",
                capabilities="chat",
            )
        )
        ids = []
        for spec in accounts:
            acc = ProviderAccount(
                provider_id=provider.id,
                label=spec["label"],
                auth_type=spec.get("auth_type", "api_key"),
                api_key=spec.get("api_key", f"key-{spec['label']}"),
                oauth_token=spec.get("oauth_token", ""),
                enabled=spec.get("enabled", True),
                priority=spec.get("priority", 0),
            )
            session.add(acc)
            session.flush()
            ids.append(acc.id)
        pid = provider.id
        session.commit()
    return {"provider_id": pid, "account_ids": ids}


def _select(sf: sessionmaker, preferred_account_id: int | None = None):
    """Open a fresh session and run the engine; return (cred, account_id)."""
    with sf() as session:
        provider = session.get(Provider, session.query(Provider).first().id)
        return oauth.select_provider_credential_with_account(
            provider, session, preferred_account_id=preferred_account_id
        )


def _make_failing_token(bad_ids: set[int], real):
    """Wrap get_valid_token: raise for accounts whose id is in ``bad_ids``."""

    def fake(account, session):
        if account.id in bad_ids:
            raise RuntimeError(f"token unavailable for {account.id}")
        return real(account, session)

    return fake


# --------------------------------------------------------------------------- #
# Engine — fill-first
# --------------------------------------------------------------------------- #
def test_no_accounts_legacy_fallback(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed(sf)
    cred, acct = _select(sf)
    assert (cred, acct) == ("sk-legacy", None)
    assert ids["account_ids"] == []


def test_fill_first_prefers_lowest_priority_then_id(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed(
        sf,
        accounts=[
            {"label": "c-high", "priority": 5},
            {"label": "a-p1-early", "priority": 1},  # wins: p1 + lowest id
            {"label": "b-p1-late", "priority": 1},
        ],
    )
    winner = ids["account_ids"][1]  # a-p1-early: priority 1, id < b-p1-late
    for _ in range(3):  # fill-first is NOT rotating: same account every call.
        cred, acct = _select(sf)
        assert acct == winner
        assert cred == "key-a-p1-early"


def test_fill_first_skips_unavailable_account(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed(
        sf,
        accounts=[{"label": "a", "priority": 0}, {"label": "b", "priority": 9}],
    )
    monkeypatch.setattr(
        oauth,
        "get_valid_token",
        _make_failing_token({ids["account_ids"][0]}, oauth.get_valid_token),
    )
    cred, acct = _select(sf)
    assert (cred, acct) == ("key-b", ids["account_ids"][1])


def test_fill_first_skips_empty_credential(monkeypatch) -> None:
    """Review follow-up: an empty stored credential = unavailable (contract
    "skip yang unavailable") — must NEVER be forwarded upstream as ""."""
    sf = _make_sessionmaker()
    ids = _seed(
        sf,
        accounts=[
            {"label": "empty", "priority": 0, "api_key": ""},
            {"label": "good", "priority": 1},
        ],
    )
    cred, acct = _select(sf)
    assert (cred, acct) == ("key-good", ids["account_ids"][1])


def test_all_accounts_unavailable_fall_back_to_legacy(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed(sf, accounts=[{"label": "a"}, {"label": "b"}])
    monkeypatch.setattr(
        oauth,
        "get_valid_token",
        _make_failing_token(set(ids["account_ids"]), oauth.get_valid_token),
    )
    cred, acct = _select(sf)
    assert (cred, acct) == ("sk-legacy", None)


def test_unknown_strategy_is_fail_safe_fill_first(monkeypatch) -> None:
    """Read-side guard: a value outside the enum (e.g. legacy row / manual DB
    edit) behaves as the default fill-first, never breaks routing."""
    sf = _make_sessionmaker()
    ids = _seed(
        sf,
        strategy="weighted",  # NOT in the supported enum
        accounts=[{"label": "a", "priority": 0}, {"label": "b", "priority": 1}],
    )
    for _ in range(4):  # would rotate if treated as round-robin
        cred, acct = _select(sf)
        assert (cred, acct) == ("key-a", ids["account_ids"][0])


# --------------------------------------------------------------------------- #
# Engine — round-robin (STICKY, limit from the COLUMN)
# --------------------------------------------------------------------------- #
def test_round_robin_is_sticky_default_three(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed(
        sf,
        strategy="round-robin",
        accounts=[{"label": "a", "priority": 0}, {"label": "b", "priority": 1}],
    )
    a, b = ids["account_ids"]
    picked = [_select(sf)[1] for _ in range(8)]
    # 3 consecutive uses of one account, then advance — exactly the contract.
    assert picked == [a, a, a, b, b, b, a, a]


def test_round_robin_limit_comes_from_the_column(monkeypatch) -> None:
    """Proves the limit is not hardcoded: 1 rotates every call, 2 pairs."""
    sf1 = _make_sessionmaker()
    ids1 = _seed(
        sf1,
        strategy="round-robin",
        sticky=1,
        accounts=[{"label": "a", "priority": 0}, {"label": "b", "priority": 1}],
    )
    assert [_select(sf1)[1] for _ in range(4)] == [
        ids1["account_ids"][0],
        ids1["account_ids"][1],
        ids1["account_ids"][0],
        ids1["account_ids"][1],
    ]
    oauth.reset_routing_state()  # fresh in-memory streak for the second half
    sf2 = _make_sessionmaker()
    ids2 = _seed(
        sf2,
        strategy="round-robin",
        sticky=2,
        accounts=[{"label": "a", "priority": 0}, {"label": "b", "priority": 1}],
    )
    assert [_select(sf2)[1] for _ in range(4)] == [
        ids2["account_ids"][0],
        ids2["account_ids"][0],
        ids2["account_ids"][1],
        ids2["account_ids"][1],
    ]


def test_clamp_sticky_limit_matrix() -> None:
    assert oauth.clamp_sticky_limit(None) == 3  # contract default
    assert oauth.clamp_sticky_limit(0) == 1  # >= 1, never 0 (infinite advance)
    assert oauth.clamp_sticky_limit(-7) == 1
    assert oauth.clamp_sticky_limit(5) == 5
    assert oauth.clamp_sticky_limit("x") == 3  # garbage -> default


def test_round_robin_zero_limit_behaves_as_one(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed(
        sf,
        strategy="round-robin",
        sticky=0,  # clamped to 1 -> rotates every call
        accounts=[{"label": "a", "priority": 0}, {"label": "b", "priority": 1}],
    )
    assert [_select(sf)[1] for _ in range(2)] == ids["account_ids"]


def test_last_used_at_persisted_on_selection(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed(sf, accounts=[{"label": "a"}, {"label": "b"}])
    with sf() as session:
        assert session.get(ProviderAccount, ids["account_ids"][0]).last_used_at is None
    _select(sf)
    with sf() as session:
        chosen = session.get(ProviderAccount, ids["account_ids"][0])
        untouched = session.get(ProviderAccount, ids["account_ids"][1])
        assert isinstance(chosen.last_used_at, datetime)
        assert untouched.last_used_at is None


def test_round_robin_order_survives_process_restart(monkeypatch) -> None:
    """The sticky counter is in-memory; after a restart the LRU order must be
    re-derived from the persisted ``last_used_at`` (NULL = least recently used)."""
    sf = _make_sessionmaker()
    ids = _seed(
        sf,
        strategy="round-robin",
        accounts=[{"label": "a", "priority": 0}, {"label": "b", "priority": 1}],
    )
    a, b = ids["account_ids"]
    with sf() as session:
        session.get(ProviderAccount, a).last_used_at = datetime.utcnow()
        session.commit()
    oauth.reset_routing_state()  # simulate the restart
    cred, acct = _select(sf)
    assert (cred, acct) == ("key-b", b)  # b never used -> LRU head


def test_round_robin_skips_unavailable_keeps_sticky_contract(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed(
        sf,
        strategy="round-robin",
        sticky=1,
        accounts=[
            {"label": "a", "priority": 0},
            {"label": "b", "priority": 1},
        ],
    )
    a, b = ids["account_ids"]
    monkeypatch.setattr(
        oauth, "get_valid_token", _make_failing_token({b}, oauth.get_valid_token)
    )
    # b is always unreachable -> a is picked; a failed candidate does NOT count
    # as a use, and the streak stays coherent (limit=1, only a usable).
    assert [_select(sf)[1] for _ in range(3)] == [a, a, a]


# --------------------------------------------------------------------------- #
# Engine — pin (x-connection-id)
# --------------------------------------------------------------------------- #
def test_pin_beats_fill_first(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed(
        sf,
        accounts=[{"label": "a", "priority": 0}, {"label": "b", "priority": 1}],
    )
    b = ids["account_ids"][1]
    for _ in range(2):
        cred, acct = _select(sf, preferred_account_id=b)
        assert (cred, acct) == ("key-b", b)  # fill-first would forever give a


def test_pin_beats_round_robin_streak(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed(
        sf,
        strategy="round-robin",
        accounts=[{"label": "a", "priority": 0}, {"label": "b", "priority": 1}],
    )
    a, b = ids["account_ids"]
    assert _select(sf)[1] == a  # start a streak on a
    assert _select(sf, preferred_account_id=b)[1] == b  # pin wins immediately
    assert _select(sf)[1] == b  # streak transfers to the pinned account
    assert _select(sf)[1] == b
    assert _select(sf)[1] == a  # after 3 uses of b, advance to LRU (a)


def test_pin_unknown_disabled_or_foreign_falls_back_to_strategy(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed(
        sf,
        accounts=[
            {"label": "a", "priority": 0},
            {"label": "b", "priority": 1},
            {"label": "off", "priority": 2, "enabled": False},
        ],
    )
    a, _b, off = ids["account_ids"]
    other = a + 1000  # no such account
    for bad_pin in (other, off):
        cred, acct = _select(sf, preferred_account_id=bad_pin)
        assert (cred, acct) == ("key-a", a)  # strategy ran, request NOT errored


def test_pin_with_unusable_credential_falls_back(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed(
        sf,
        accounts=[{"label": "a", "priority": 0}, {"label": "b", "priority": 1}],
    )
    a, b = ids["account_ids"]
    monkeypatch.setattr(
        oauth, "get_valid_token", _make_failing_token({b}, oauth.get_valid_token)
    )
    cred, acct = _select(sf, preferred_account_id=b)
    assert (cred, acct) == ("key-a", a)


def test_wrapper_forwards_pin() -> None:
    """``select_provider_credential`` (str-only wrapper) forwards the pin."""
    sf = _make_sessionmaker()
    ids = _seed(
        sf,
        accounts=[{"label": "a", "priority": 0}, {"label": "b", "priority": 1}],
    )
    b = ids["account_ids"][1]
    with sf() as session:
        provider = session.query(Provider).first()
        cred = oauth.select_provider_credential(
            provider, session, preferred_account_id=b
        )
    assert cred == "key-b"


# --------------------------------------------------------------------------- #
# Header parsing (gateway layer in front of resolve_target)
# --------------------------------------------------------------------------- #
def _req_with_headers(headers: dict) -> types.SimpleNamespace:
    return types.SimpleNamespace(headers=headers)


def test_preferred_account_id_header_parsing() -> None:
    assert _preferred_account_id(_req_with_headers({})) is None
    assert _preferred_account_id(_req_with_headers({CONNECTION_ID_HEADER: "  "})) is None
    assert _preferred_account_id(_req_with_headers({CONNECTION_ID_HEADER: "abc"})) is None
    assert _preferred_account_id(_req_with_headers({CONNECTION_ID_HEADER: " 12 "})) == 12


def test_resolve_target_forwards_pin(monkeypatch) -> None:
    """End-to-end through the resolver: the pin lands on ResolvedTarget.account_id."""
    sf = _make_sessionmaker()
    ids = _seed(
        sf,
        accounts=[{"label": "a", "priority": 0}, {"label": "b", "priority": 1}],
    )
    _patch_db(monkeypatch, sf)
    b = ids["account_ids"][1]
    target = resolver.resolve_target("provider:rt:m1", preferred_account_id=b)
    assert target.account_id == b
    assert target.api_key == "key-b"


# --------------------------------------------------------------------------- #
# Providers / accounts DTO + validation (route level)
# --------------------------------------------------------------------------- #
def test_provider_dto_defaults(monkeypatch) -> None:
    sf = _make_sessionmaker()
    _seed(sf)
    _patch_db(monkeypatch, sf)
    client = TestClient(app)
    r = client.get("/api/providers")
    assert r.status_code == 200
    p = r.json()["data"][0]
    assert p["fallback_strategy"] == "fill-first"
    assert p["sticky_round_robin_limit"] == 3


def test_provider_create_round_robin(monkeypatch) -> None:
    sf = _make_sessionmaker()
    _patch_db(monkeypatch, sf)
    client = TestClient(app)
    r = client.post(
        "/api/providers",
        json={
            "name": "rr",
            "type": "openai",
            "base_url": "http://rr.test/v1",
            "api_key": "sk-rr",
            "fallback_strategy": "round-robin",
            "sticky_round_robin_limit": 2,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["fallback_strategy"] == "round-robin"
    assert body["sticky_round_robin_limit"] == 2


def test_provider_create_rejects_out_of_enum_strategy(monkeypatch) -> None:
    """The locked decision: ONLY fill-first | round-robin exist (9router
    account-level set) — weighted/latency/cost must 400, not silently land."""
    sf = _make_sessionmaker()
    _patch_db(monkeypatch, sf)
    client = TestClient(app)
    r = client.post(
        "/api/providers",
        json={
            "name": "bad",
            "type": "openai",
            "base_url": "http://bad.test/v1",
            "api_key": "sk-bad",
            "fallback_strategy": "weighted",
        },
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_fallback_strategy"


def test_provider_update_strategy_and_clamp(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed(sf)
    _patch_db(monkeypatch, sf)
    client = TestClient(app)
    r = client.put(
        f"/api/providers/{ids['provider_id']}",
        json={"fallback_strategy": "round-robin", "sticky_round_robin_limit": 0},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["fallback_strategy"] == "round-robin"
    assert body["sticky_round_robin_limit"] == 1  # clamped >= 1
    r = client.put(
        f"/api/providers/{ids['provider_id']}",
        json={"fallback_strategy": "least-load"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_fallback_strategy"


def test_account_create_dto_priority_and_last_used(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed(sf)
    _patch_db(monkeypatch, sf)
    client = TestClient(app)
    r = client.post(
        "/api/accounts",
        json={
            "provider_id": ids["provider_id"],
            "label": "p5",
            "auth_type": "api_key",
            "api_key": "sk-p5",
            "priority": 5,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["priority"] == 5
    assert body["last_used_at"] is None  # engine-owned, read-only


def test_account_update_priority_and_404(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed(sf, accounts=[{"label": "a", "priority": 7}])
    _patch_db(monkeypatch, sf)
    client = TestClient(app)
    a = ids["account_ids"][0]
    r = client.put(f"/api/accounts/{a}", json={"priority": 2})
    assert r.status_code == 200
    assert r.json()["priority"] == 2
    r = client.put("/api/accounts/99999", json={"priority": 1})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "account_not_found"


# --------------------------------------------------------------------------- #
# PUT /api/accounts/{id} — full partial EDIT (label | api_key | enabled | priority)
# --------------------------------------------------------------------------- #
def _account_row(sf: sessionmaker, account_id: int) -> ProviderAccount:
    """Fresh-session reload of the stored row (asserts what really landed)."""
    with sf() as session:
        return session.get(ProviderAccount, account_id)


def test_account_update_label_only(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed(sf, accounts=[{"label": "a", "priority": 4}])
    _patch_db(monkeypatch, sf)
    client = TestClient(app)
    a = ids["account_ids"][0]
    r = client.put(f"/api/accounts/{a}", json={"label": "renamed"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["label"] == "renamed"
    assert body["priority"] == 4 and body["api_key"] == "key-a"
    assert body["enabled"] is True and body["auth_type"] == "api_key"
    # ``id`` is the DTO's own key; the response is the bare DTO, not {"data":..}.
    assert "data" not in body
    row = _account_row(sf, a)
    assert (row.label, row.priority, row.api_key) == ("renamed", 4, "key-a")


def test_account_update_api_key_only(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed(sf, accounts=[{"label": "a", "priority": 1}])
    _patch_db(monkeypatch, sf)
    client = TestClient(app)
    a = ids["account_ids"][0]
    r = client.put(f"/api/accounts/{a}", json={"api_key": "sk-rotated"})
    assert r.status_code == 200, r.text
    assert r.json()["api_key"] == "sk-rotated"  # ADR-007 plaintext out
    assert r.json()["label"] == "a" and r.json()["priority"] == 1
    row = _account_row(sf, a)
    assert row.api_key == "sk-rotated" and row.label == "a"


def test_account_update_404_for_any_field(monkeypatch) -> None:
    sf = _make_sessionmaker()
    _patch_db(monkeypatch, sf)
    client = TestClient(app)
    r = client.put("/api/accounts/99999", json={"label": "x", "enabled": False})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "account_not_found"


def test_account_update_clear_api_key_makes_account_unusable(monkeypatch) -> None:
    """``api_key: ""`` is a DELIBERATE write (absent ≠ empty): it lands in the DB
    and the selection engine then skips the account (empty credential = unusable)
    and falls back to ``provider.api_key`` — end-to-end proof."""
    sf = _make_sessionmaker()
    ids = _seed(sf, accounts=[{"label": "a"}])
    _patch_db(monkeypatch, sf)
    client = TestClient(app)
    a = ids["account_ids"][0]
    # Selected while it has a key.
    assert _select(sf) == ("key-a", a)
    r = client.put(f"/api/accounts/{a}", json={"api_key": ""})
    assert r.status_code == 200, r.text
    assert r.json()["api_key"] == ""
    assert _account_row(sf, a).api_key == ""
    # Now unusable -> skipped by the engine, legacy credential wins, no 500.
    assert _select(sf) == ("sk-legacy", None)


def test_account_update_toggle_enabled(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed(sf, accounts=[{"label": "a"}, {"label": "b"}])
    _patch_db(monkeypatch, sf)
    client = TestClient(app)
    a = ids["account_ids"][0]
    r = client.put(f"/api/accounts/{a}", json={"enabled": False})
    assert r.status_code == 200, r.text
    assert r.json()["enabled"] is False
    assert _account_row(sf, a).enabled is False
    # The engine only sees enabled rows -> account "b" is used now.
    assert _select(sf) == ("key-b", ids["account_ids"][1])
    assert client.put(f"/api/accounts/{a}", json={"enabled": True}).json()["enabled"]


def test_account_update_all_fields_at_once(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed(sf, accounts=[{"label": "a", "priority": 9, "enabled": True}])
    _patch_db(monkeypatch, sf)
    client = TestClient(app)
    a = ids["account_ids"][0]
    r = client.put(
        f"/api/accounts/{a}",
        json={
            "label": "all",
            "api_key": "sk-all",
            "enabled": False,
            "priority": -3,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["label"] == "all"
    assert body["api_key"] == "sk-all"
    assert body["enabled"] is False
    assert body["priority"] == -3
    row = _account_row(sf, a)
    assert (row.label, row.api_key, row.enabled, row.priority) == (
        "all",
        "sk-all",
        False,
        -3,
    )


def test_account_update_absent_fields_keep_their_values(monkeypatch) -> None:
    """REGRESSION GUARD: the DTO defaults of ``AccountUpdate`` (label '', key '',
    enabled True, priority 0) must NEVER be written for fields the client omit.
    """
    sf = _make_sessionmaker()
    ids = _seed(
        sf,
        accounts=[
            {
                "label": "keep-me",
                "api_key": "sk-keep",
                "enabled": False,
                "priority": 7,
            }
        ],
    )
    _patch_db(monkeypatch, sf)
    client = TestClient(app)
    a = ids["account_ids"][0]
    r = client.put(f"/api/accounts/{a}", json={"label": "only-label"})
    assert r.status_code == 200, r.text
    row = _account_row(sf, a)
    assert row.label == "only-label"
    assert row.api_key == "sk-keep"  # not blanked by the model default
    assert row.enabled is False  # not flipped by the model default
    assert row.priority == 7  # not zeroed by the model default
    # An explicit null is also "no write" (the columns are NOT NULL).
    r = client.put(f"/api/accounts/{a}", json={"api_key": None, "priority": None})
    assert r.status_code == 200, r.text
    row = _account_row(sf, a)
    assert (row.api_key, row.priority) == ("sk-keep", 7)


def test_account_update_empty_body_is_a_noop_200(monkeypatch) -> None:
    """Old behavior preserved: no field sent -> 200 with the CURRENT DTO, nothing
    rewritten (``last_used_at`` included)."""
    sf = _make_sessionmaker()
    ids = _seed(sf, accounts=[{"label": "a", "priority": 5}])
    _patch_db(monkeypatch, sf)
    client = TestClient(app)
    a = ids["account_ids"][0]
    before = client.get(f"/api/accounts?provider_id={ids['provider_id']}").json()
    r = client.put(f"/api/accounts/{a}", json={})
    assert r.status_code == 200, r.text
    assert r.json() == before["data"][0]


def test_account_update_auth_type_is_ignored_not_rejected(monkeypatch) -> None:
    """``auth_type`` cannot be flipped from this endpoint (oauth credentials are
    minted by the callback, not typed into a form): it is silently ignored and
    the DTO keeps reporting the stored type."""
    sf = _make_sessionmaker()
    ids = _seed(
        sf,
        accounts=[
            {"label": "k", "auth_type": "api_key", "api_key": "sk-k"},
            {"label": "o", "auth_type": "oauth", "api_key": "", "oauth_token": "tok"},
        ],
    )
    _patch_db(monkeypatch, sf)
    client = TestClient(app)
    k, o = ids["account_ids"]
    r = client.put(f"/api/accounts/{k}", json={"auth_type": "oauth", "label": "k2"})
    assert r.status_code == 200, r.text
    assert r.json()["auth_type"] == "api_key" and r.json()["label"] == "k2"
    assert _account_row(sf, k).auth_type == "api_key"
    r = client.put(f"/api/accounts/{o}", json={"auth_type": "api_key", "priority": 2})
    assert r.status_code == 200, r.text
    assert r.json()["auth_type"] == "oauth"
    assert r.json()["has_oauth_token"] is True
    assert r.json()["priority"] == 2


def test_account_update_api_key_on_oauth_account_is_rejected(monkeypatch) -> None:
    """Storing a key in ``api_key`` for an oauth account would be a trap (the
    engine reads ``oauth_token``), so it is refused with a 400 envelope."""
    sf = _make_sessionmaker()
    ids = _seed(
        sf, accounts=[{"label": "o", "auth_type": "oauth", "api_key": "", "oauth_token": "tok"}]
    )
    _patch_db(monkeypatch, sf)
    client = TestClient(app)
    o = ids["account_ids"][0]
    for payload in ({"api_key": "sk-no"}, {"api_key": ""}):
        r = client.put(f"/api/accounts/{o}", json=payload)
        assert r.status_code == 400, r.text
        assert r.json()["error"]["code"] == "oauth_account_key_readonly"
        assert r.json()["error"]["type"] == "invalid_request_error"
    # Rejected writes land nothing; unrelated fields still edit fine.
    assert _account_row(sf, o).api_key == ""
    r = client.put(f"/api/accounts/{o}", json={"label": "renamed-oauth"})
    assert r.status_code == 200 and r.json()["label"] == "renamed-oauth"


def test_account_update_logs_field_names_never_values(monkeypatch) -> None:
    """R12 + secrets rule: the LogEntry row names the changed fields and must
    never carry the key value."""
    sf = _make_sessionmaker()
    ids = _seed(sf, accounts=[{"label": "a"}])
    _patch_db(monkeypatch, sf)
    client = TestClient(app)
    a = ids["account_ids"][0]
    r = client.put(
        f"/api/accounts/{a}", json={"label": "lab", "api_key": "sk-super-secret"}
    )
    assert r.status_code == 200, r.text
    with sf() as session:
        rows = (
            session.query(LogEntry)
            .filter_by(source="backend.accounts.router")
            .order_by(LogEntry.id.desc())
            .all()
        )
        update_rows = [e.message for e in rows if "updated account" in e.message]
    assert update_rows, "the update was not logged at all"
    message = update_rows[0]
    assert "label" in message and "api_key" in message
    assert "sk-super-secret" not in message
    assert "updated account" in message



def test_accounts_list_ordered_by_priority_then_id(monkeypatch) -> None:
    sf = _make_sessionmaker()
    ids = _seed(
        sf,
        accounts=[
            {"label": "z-late", "priority": 0},
            {"label": "mid", "priority": 1},
            {"label": "top", "priority": -1},
        ],
    )
    _patch_db(monkeypatch, sf)
    client = TestClient(app)
    top, mid, zlate = ids["account_ids"][2], ids["account_ids"][1], ids["account_ids"][0]
    r = client.get(f"/api/accounts?provider_id={ids['provider_id']}")
    assert r.status_code == 200
    got = [row["id"] for row in r.json()["data"]]
    assert got == [top, zlate, mid]  # priority asc (-1, 0, 1); id is tie-break


# --------------------------------------------------------------------------- #
# Migration — idempotent self-heal of the 4 new columns (db.py pattern)
# --------------------------------------------------------------------------- #
def test_routing_columns_migration_is_idempotent(tmp_path) -> None:
    """Old DB (pre-feature schema) gets the 4 columns applied twice without
    error, defaults land on pre-existing rows; nullable ``last_used_at`` = NULL.
    """
    db_file = tmp_path / "old.db"
    engine = create_engine(f"sqlite:///{db_file}", future=True)
    with engine.connect() as conn:
        conn.execute(
            text(
                "CREATE TABLE providers (id INTEGER PRIMARY KEY, name TEXT, "
                "api_key TEXT)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE provider_accounts (id INTEGER PRIMARY KEY, "
                "provider_id INTEGER, label TEXT)"
            )
        )
        conn.execute(text("INSERT INTO providers VALUES (1, 'old', 'sk-old')"))
        conn.execute(text("INSERT INTO provider_accounts VALUES (1, 1, 'acc-old')"))
        conn.commit()

    db_module._ensure_provider_account_routing_columns(engine)  # 1st run
    db_module._ensure_provider_account_routing_columns(engine)  # idempotency

    with engine.connect() as conn:
        prov = {r[1] for r in conn.execute(text("PRAGMA table_info(providers)"))}
        acc = {r[1] for r in conn.execute(text("PRAGMA table_info(provider_accounts)"))}
        assert {"fallback_strategy", "sticky_round_robin_limit"} <= prov
        assert {"priority", "last_used_at"} <= acc
        row = conn.execute(
            text(
                "SELECT fallback_strategy, sticky_round_robin_limit FROM providers "
                "WHERE id=1"
            )
        ).fetchone()
        assert row == ("fill-first", 3)  # defaults applied to old rows
        row = conn.execute(
            text("SELECT priority, last_used_at FROM provider_accounts WHERE id=1")
        ).fetchone()
        assert row == (0, None)
    engine.dispose()

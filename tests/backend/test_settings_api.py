"""Hermetic tests for the Settings API (B1.3).

Uses an in-memory SQLite engine by rebinding ``SessionLocal`` (same object the
repo references), so no on-disk ``~/.aigate/aigate.db`` is touched. Lifespan is
deliberately NOT triggered (TestClient without context manager) to keep the
sandbox hermetic; we seed defaults ourselves.
"""

from __future__ import annotations

from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from backend import models  # noqa: F401  (register mappers on Base.metadata)
from backend.config.db import Base, SessionLocal
from backend.config.settings import DEFAULT_SETTINGS, ensure_seeded


@pytest.fixture
def settings_client() -> Iterator[TestClient]:
    """Yield a TestClient backed by an in-memory Settings store.

    ``StaticPool`` keeps a single shared in-memory DB across all connections
    (otherwise ``:memory:`` gives each connection a fresh empty database).
    """
    original_bind = SessionLocal.kw.get("bind")
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal.configure(bind=engine)
    Base.metadata.create_all(engine)
    ensure_seeded()
    try:
        from backend.server import app

        yield TestClient(app)
    finally:
        SessionLocal.configure(bind=original_bind)
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_get_settings_returns_seeded_defaults(
    settings_client: TestClient,
) -> None:
    response = settings_client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    for key, value in DEFAULT_SETTINGS.items():
        assert data.get(key) == value


def test_put_settings_updates_value_and_get_reflects_it(
    settings_client: TestClient,
) -> None:
    # Single key/value shape.
    resp = settings_client.put("/api/settings", json={"key": "port", "value": "9090"})
    assert resp.status_code == 200
    assert resp.json()["port"] == "9090"

    # Subsequent GET reflects the change.
    get_resp = settings_client.get("/api/settings")
    assert get_resp.status_code == 200
    assert get_resp.json()["port"] == "9090"


def test_put_settings_bulk_shape(
    settings_client: TestClient,
) -> None:
    resp = settings_client.put(
        "/api/settings",
        json={"settings": {"theme": "dark", "locale": "id", "dev_mode": "true"}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["theme"] == "dark"
    assert data["locale"] == "id"
    assert data["dev_mode"] == "true"


def test_put_settings_scalar_coercion_to_string(
    settings_client: TestClient,
) -> None:
    # int/bool must be stored as strings.
    resp = settings_client.put("/api/settings", json={"key": "port", "value": 7070})
    assert resp.status_code == 200
    assert resp.json()["port"] == "7070"


def test_get_setting_by_key_and_404(
    settings_client: TestClient,
) -> None:
    ok = settings_client.get("/api/settings/theme")
    assert ok.status_code == 200
    assert ok.json() == {"key": "theme", "value": DEFAULT_SETTINGS["theme"]}

    missing = settings_client.get("/api/settings/does_not_exist")
    assert missing.status_code == 404

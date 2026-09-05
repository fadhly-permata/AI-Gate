"""Tests for the ADR-007 plaintext file secret store.

Never touches the real home dir: ``SECRETS_PATH`` is monkeypatched to a
``tmp_path`` location so the store is exercised in isolation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.backend.config import secrets


@pytest.fixture
def temp_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the store at a temp file and return its path."""
    path = tmp_path / "secrets.json"
    monkeypatch.setattr(secrets, "SECRETS_PATH", path)
    return path


def test_set_then_get_roundtrip(temp_secrets: Path) -> None:
    secrets.set_secret("x", "y")
    assert secrets.get_secret("x") == "y"


def test_file_is_plaintext_json(temp_secrets: Path) -> None:
    secrets.set_secret("x", "y")
    assert temp_secrets.exists()
    raw = temp_secrets.read_text(encoding="utf-8")
    # Plaintext: value present unencrypted, valid JSON dict.
    assert '"y"' in raw
    parsed = json.loads(raw)
    assert parsed["x"] == "y"


def test_delete_removes_key(temp_secrets: Path) -> None:
    secrets.set_secret("x", "y")
    secrets.delete_secret("x")
    assert secrets.get_secret("x") is None
    if temp_secrets.exists():
        assert "x" not in json.loads(temp_secrets.read_text(encoding="utf-8"))


def test_missing_file_returns_none(temp_secrets: Path) -> None:
    assert secrets.get_secret("nope") is None
    assert secrets.load_secrets() == {}


def test_load_secrets_returns_dict(temp_secrets: Path) -> None:
    secrets.set_secret("a", "1")
    secrets.set_secret("b", "2")
    data = secrets.load_secrets()
    assert data == {"a": "1", "b": "2"}

"""Tests for the aigate runtime launcher."""

import sys
from unittest.mock import MagicMock

import pytest

import backend.launcher


def test_main_is_callable() -> None:
    assert callable(backend.launcher.main)


def test_main_wires_up_without_starting_server(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_run = MagicMock()
    monkeypatch.setattr("uvicorn.run", fake_run)
    monkeypatch.setattr(sys, "argv", ["launcher"])

    backend.launcher.main()

    fake_run.assert_called_once()
    _, kwargs = fake_run.call_args
    assert kwargs["host"] == "0.0.0.0"
    assert kwargs["port"] == 8080

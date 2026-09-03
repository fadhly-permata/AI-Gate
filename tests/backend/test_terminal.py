"""Tests for the PTY backend + terminal WebSocket (task B3.2).

These tests are hermetic where possible:

* The **import test** always runs and verifies lazy imports: the modules load
  even when ``ptyprocess`` / ``pywinpty`` are absent, and ``spawn_shell``
  raises a clear :class:`PtyError` (never a raw ``ImportError``) on the current
  platform when its native dep is missing.
* The **PTY echo** and **WebSocket** tests are best-effort. When the current
  platform's PTY dependency cannot be imported they ``pytest.skip`` so the
  suite stays green in CI/sandboxes without a working PTY.
"""

from __future__ import annotations

import importlib
import sys

import pytest

# --- lazy import check: modules must import even without the native deps ----- #
import backend.terminal.pty as pty_mod  # noqa: E402
import backend.terminal.router as router_mod  # noqa: E402

from backend.terminal.pty import PtyError, spawn_shell  # noqa: E402


def _pty_dep_available() -> bool:
    """True if the current platform's PTY dependency can be imported."""
    if sys.platform == "win32":
        try:
            importlib.import_module("pywinpty")
            return True
        except ImportError:
            return False
    try:
        importlib.import_module("ptyprocess")
        return True
    except ImportError:
        return False


# --------------------------------------------------------------------------- #
# 1) Module import (always runs)
# --------------------------------------------------------------------------- #
def test_modules_import_without_native_dep():
    # If we got here the imports succeeded (lazy imports).
    assert hasattr(pty_mod, "spawn_shell")
    assert hasattr(pty_mod, "PtyError")
    assert hasattr(router_mod, "router")


def test_spawn_raises_clear_pty_error_when_dep_missing():
    if _pty_dep_available():
        pytest.skip("native PTY dep present on this platform; cannot test missing-dep path")
    with pytest.raises(PtyError):
        spawn_shell()
    # Crucially it must NOT surface as an ImportError to callers.
    try:
        spawn_shell()
    except PtyError:
        pass  # expected
    except ImportError as exc:
        pytest.fail(f"spawn_shell leaked ImportError instead of PtyError: {exc}")


# --------------------------------------------------------------------------- #
# 2) PTY echo (best-effort, POSIX Termux/Linux)
# --------------------------------------------------------------------------- #
def test_pty_echo_roundtrip():
    if not _pty_dep_available():
        pytest.skip("PTY native dependency unavailable in this environment")
    pty = spawn_shell()
    try:
        pty.write(b"echo hello\r")
        collected = b""
        # Read with a small bounded loop; shell prompt/echo is fast.
        for _ in range(200):
            chunk = pty.read(65536)
            collected += chunk
            if b"hello" in collected:
                break
        assert b"hello" in collected, f"expected 'hello' in PTY output, got: {collected!r}"
    finally:
        pty.kill()


# --------------------------------------------------------------------------- #
# 3) WebSocket round-trip (best-effort)
# --------------------------------------------------------------------------- #
def test_terminal_websocket_roundtrip(client):
    if not _pty_dep_available():
        pytest.skip("PTY native dependency unavailable in this environment")

    from fastapi.testclient import TestClient

    with TestClient(client.app) as c:  # triggers lifespan (DB bootstrap)
        with c.websocket_connect("/ws/terminal/0") as ws:
            # Resize control frame (must NOT be written to the shell).
            ws.send_text('{"type":"resize","cols":120,"rows":40}')
            # A real command.
            ws.send_text("echo hi-from-ws\r")
            got = ""
            for _ in range(200):
                try:
                    got += ws.receive_text()
                except Exception:  # noqa: BLE001 - closed / drained
                    break
                if "hi-from-ws" in got:
                    break
            assert "hi-from-ws" in got, f"expected output from ws shell, got: {got!r}"
        # Disconnect cleanup is exercised by leaving the `with` block.

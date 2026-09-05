"""Tests for the shared PATH augmentation helper + PTY spawn env (bug fix).

Bug: the terminal PTY inherited the SERVER process env, so a narrow server
PATH hid user-installed CLI tools (aider via pip --user/pipx → ~/.local/bin,
cargo → ~/.cargo/bin, ...). Fix: ``backend.paths.extra_path_dirs()`` is the
single source of truth; ``terminal.pty.build_spawn_env`` appends those dirs to
PATH and passes ``env=`` to the PTY spawn; ``cli_tools_router`` detection
imports the same helper.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import backend.paths as paths_mod  # noqa: E402
from backend.paths import EXTRA_PATH_DIRS, extra_path_dirs  # noqa: E402


# --------------------------------------------------------------------------- #
# extra_path_dirs(): single source of truth
# --------------------------------------------------------------------------- #
def test_extra_path_dirs_only_existing_dirs(monkeypatch, tmp_path) -> None:
    """Non-existent candidates are dropped; created ones are kept."""
    fake_home = tmp_path / "home"
    (fake_home / ".local" / "bin").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("PREFIX", raising=False)

    dirs = extra_path_dirs()
    assert str(fake_home / ".local" / "bin") in dirs
    # ~/.cargo/bin was never created -> must not appear
    assert str(fake_home / ".cargo" / "bin") not in dirs
    assert all(os.path.isdir(p) for p in dirs)


def test_extra_path_dirs_includes_home_local_bin(monkeypatch, tmp_path) -> None:
    """The original bug case: $HOME/.local/bin (pip --user / pipx) is included."""
    fake_home = tmp_path / "pyhome"
    local_bin = fake_home / ".local" / "bin"
    local_bin.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("PREFIX", raising=False)

    assert str(local_bin) in extra_path_dirs()


def test_extra_path_dirs_deduped(monkeypatch, tmp_path) -> None:
    """Duplicate expansions (e.g. $PREFIX/bin == absolute Termux fallback)
    appear exactly once."""
    fake_home = tmp_path / "duphome"
    (fake_home / ".local" / "bin").mkdir(parents=True)
    # Point PREFIX at a dir whose /bin expansion collides with the absolute
    # Termux fallback entry in EXTRA_PATH_DIRS.
    monkeypatch.setenv("PREFIX", "/data/data/com.termux/files/usr")
    monkeypatch.setenv("HOME", str(fake_home))

    dirs = extra_path_dirs()
    assert len(dirs) == len(set(dirs)), f"duplicates in {dirs}"


def test_extra_path_dirs_expands_prefix_var(monkeypatch, tmp_path) -> None:
    """``$PREFIX/bin`` expands from the environment."""
    prefix = tmp_path / "prefix"
    (prefix / "bin").mkdir(parents=True)
    monkeypatch.setenv("PREFIX", str(prefix))
    monkeypatch.setenv("HOME", str(tmp_path / "nohome"))

    assert str(prefix / "bin") in extra_path_dirs()


def test_extra_path_dirs_source_list_matches_history() -> None:
    """The centralized list keeps the dirs the CLI probe always searched."""
    for raw in ("~/.local/bin", "~/.cargo/bin", "$PREFIX/bin", "/usr/local/bin"):
        assert raw in EXTRA_PATH_DIRS


# --------------------------------------------------------------------------- #
# build_spawn_env(): PATH handed to the PTY
# --------------------------------------------------------------------------- #
def test_build_spawn_env_keeps_base_and_appends_extras(monkeypatch, tmp_path) -> None:
    """Existing PATH entries win; user install dirs are appended after them."""
    fake_home = tmp_path / "home"
    local_bin = fake_home / ".local" / "bin"
    local_bin.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("PREFIX", raising=False)
    base = tmp_path / "basebin"
    base.mkdir()
    monkeypatch.setenv("PATH", str(base))

    from backend.terminal.pty import build_spawn_env

    env = build_spawn_env()
    assert env is not None
    parts = env["PATH"].split(os.pathsep)
    assert parts[0] == str(base)  # server PATH preserved, searched first
    assert str(local_bin) in parts  # user tool dir now visible to the shell
    # other env vars are inherited untouched
    assert env["HOME"] == str(fake_home)


def test_build_spawn_env_falls_back_to_none_on_failure(monkeypatch) -> None:
    """A broken PATH build must yield None → caller uses the default spawn."""
    from backend.terminal import pty as pty_mod

    def boom() -> list[str]:
        raise RuntimeError("stat exploded")

    monkeypatch.setattr(pty_mod, "extra_path_dirs", boom)
    assert pty_mod.build_spawn_env() is None


# --------------------------------------------------------------------------- #
# _spawn_posix(): env actually reaches PtyProcess.spawn
# --------------------------------------------------------------------------- #
class _FakeImpl:
    def setwinsize(self, rows: int, cols: int) -> None:  # noqa: D102
        pass


def test_spawn_posix_passes_augmented_env_to_pty(monkeypatch, tmp_path) -> None:
    """Capture the ``env`` kwarg of ptyprocess.PtyProcess.spawn and assert the
    PTY PATH contains the user install dir (the real bug: it didn't)."""
    try:
        import ptyprocess
    except ImportError:
        pytest.skip("ptyprocess not importable in this environment")

    fake_home = tmp_path / "home"
    local_bin = fake_home / ".local" / "bin"
    local_bin.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("PREFIX", raising=False)
    base = tmp_path / "basebin"
    base.mkdir()
    monkeypatch.setenv("PATH", str(base))

    captured: dict = {}

    class FakePty:
        @classmethod
        def spawn(cls, argv, cwd=None, env=None, **kwargs):  # noqa: ANN001, D102
            captured["argv"] = argv
            captured["env"] = env
            return _FakeImpl()

    monkeypatch.setattr(ptyprocess.PtyProcess, "spawn", FakePty.spawn)

    from backend.terminal.pty import spawn_shell

    proc = spawn_shell(cols=80, rows=24)
    assert proc._platform == "posix"
    env = captured.get("env")
    assert env is not None, "spawn_shell must pass an explicit env to the PTY"
    parts = env["PATH"].split(os.pathsep)
    assert str(local_bin) in parts, f"~/.local/bin missing from PTY PATH: {parts}"
    assert str(base) in parts, "server PATH entries must be kept"


def test_cli_router_shares_paths_helper() -> None:
    """cli_tools_router._extra_search_paths delegates to backend.paths —
    detection and the PTY cannot drift apart."""
    from backend import cli_tools_router
    from backend.paths import extra_path_dirs as ssot

    assert cli_tools_router._extra_search_paths is not ssot  # wrapper kept
    # behavior identity: same result under the same env
    assert cli_tools_router._extra_search_paths() == paths_mod.extra_path_dirs()


# --------------------------------------------------------------------------- #
# is_termux(): platform fact used to pick a WORKING install route per tool
# (see cli_presets.TERMUX_INSTALL).
# --------------------------------------------------------------------------- #
def test_is_termux_true_for_termux_prefix(monkeypatch) -> None:
    monkeypatch.setenv("PREFIX", "/data/data/com.termux/files/usr")
    assert paths_mod.is_termux() is True


def test_is_termux_false_off_termux(monkeypatch) -> None:
    monkeypatch.setenv("PREFIX", "/usr/local")
    # the absolute-prefix fallback must not fire either
    monkeypatch.setattr(paths_mod.os.path, "isdir", lambda p: False)
    assert paths_mod.is_termux() is False


def test_is_termux_true_via_absolute_fallback(monkeypatch) -> None:
    monkeypatch.setenv("PREFIX", "")
    monkeypatch.setattr(
        paths_mod.os.path,
        "isdir",
        lambda p: p == "/data/data/com.termux/files/usr",
    )
    assert paths_mod.is_termux() is True

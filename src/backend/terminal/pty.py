"""PTY backend abstraction for aigate (task B3.2).

Cross-platform shell bridge:

* POSIX / Termux  → :mod:`ptyprocess`
* Windows         → :mod:`pywinpty`

Both deps are lazy-imported so this module imports cleanly even when a
platform's dependency is missing. The dependency is only required at
**spawn time** on that platform; if absent, :func:`spawn_shell` raises a
clear :class:`PtyError` (never a raw ``ImportError``).

Platform detection uses ``sys.platform`` so Termux (``linux``) takes the
POSIX branch.

The spawned shell gets an **augmented PATH** (see :func:`build_spawn_env`):
the server process PATH plus the user install dirs from ``backend.paths``
(``~/.local/bin``, ``~/.cargo/bin``, ...), so CLI tools the user installed are
findable inside the terminal even when aigate itself was started with a
narrow PATH.
"""

from __future__ import annotations

import os
import sys
from typing import Dict, Optional

from backend.paths import extra_path_dirs

LOG_SOURCE = "backend.terminal.pty"


class PtyError(Exception):
    """Raised for any PTY spawn / I/O failure.

    Wraps low-level errors (including missing native deps) so callers never
    have to special-case ``ImportError``.
    """


class PtyProcess:
    """Unified byte-oriented wrapper around a platform PTY.

    The underlying implementations differ in shape:

    * ``ptyprocess.PtyProcess`` works in ``bytes``.
    * ``pywinpty.PTY`` works in ``str`` (already decoded).

    This wrapper normalises both to ``bytes`` for :meth:`read` /
    :meth:`write` so the WebSocket layer stays byte-clean.
    """

    def __init__(self, impl: object, platform: str) -> None:
        self._impl = impl
        self._platform = platform  # "posix" | "win"

    # ------------------------------------------------------------------ #
    # Introspection
    # ------------------------------------------------------------------ #
    @property
    def pid(self) -> Optional[int]:
        try:
            return int(self._impl.pid)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 - pid is best-effort
            return None

    def is_alive(self) -> bool:
        try:
            return bool(self._impl.isalive())  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 - treat errors as dead
            return False

    # ------------------------------------------------------------------ #
    # I/O
    # ------------------------------------------------------------------ #
    def read(self, size: int = 65536) -> bytes:
        """Blocking read of up to ``size`` bytes.

        Returns ``b""`` at EOF. The caller (a dedicated reader thread in the
        router) decides whether EOF + not-alive means "done".
        """
        try:
            data = self._impl.read(size)  # type: ignore[attr-defined]
        except EOFError:
            return b""
        except Exception as exc:  # noqa: BLE001 - normalise to PtyError
            from backend.log import log_error_exc

            log_error_exc("pty read failed", source=LOG_SOURCE, exc=exc)
            raise PtyError(f"pty read failed: {exc}") from exc
        if data is None:
            return b""
        if isinstance(data, str):
            return data.encode("utf-8", "replace")
        return bytes(data)

    def write(self, data: bytes) -> None:
        try:
            if self._platform == "win":
                # pywinpty expects str.
                self._impl.write(data.decode("utf-8", "replace"))  # type: ignore[attr-defined]
            else:
                self._impl.write(data)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001 - normalise to PtyError
            from backend.log import log_error_exc

            log_error_exc("pty write failed", source=LOG_SOURCE, exc=exc)
            raise PtyError(f"pty write failed: {exc}") from exc

    def set_winsize(self, cols: int, rows: int) -> None:
        """Resize the PTY. Argument order differs per backend.

        * ``ptyprocess`` → ``setwinsize(rows, cols)``
        * ``pywinpty``   → ``setwinsize(cols, rows)``
        """
        try:
            if self._platform == "win":
                self._impl.setwinsize(cols, rows)  # type: ignore[attr-defined]
            else:
                self._impl.setwinsize(rows, cols)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001 - non-fatal resize failure
            from backend.log import log_error_exc

            log_error_exc("pty set_winsize failed", source=LOG_SOURCE, exc=exc)
            raise PtyError(f"pty set_winsize failed: {exc}") from exc

    def kill(self) -> None:
        """Terminate (then kill) the child process / PTY."""
        try:
            self._impl.terminate()  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001 - try kill next
            from backend.log import log_warning_exc

            log_warning_exc(
                "pty terminate failed, attempting kill", source=LOG_SOURCE, exc=exc
            )
        if self.is_alive():
            try:
                self._impl.kill()  # type: ignore[attr-defined]
            except Exception as exc:  # noqa: BLE001
                from backend.log import log_error_exc

                log_error_exc("pty kill failed", source=LOG_SOURCE, exc=exc)
                raise PtyError(f"pty kill failed: {exc}") from exc


# ---------------------------------------------------------------------- #
# Spawn factory
# ---------------------------------------------------------------------- #
def build_spawn_env() -> Optional[Dict[str, str]]:
    """Env for the spawned shell: server env + user install dirs on PATH.

    WHY: ``_Pty.spawn`` without ``env`` inherits the SERVER process env. When
    aigate is started from a shell with a narrow PATH, the interactive PTY
    cannot see tools the user installed via ``pip install --user``/pipx
    (``~/.local/bin``), cargo (``~/.cargo/bin``), npm global, etc. — so
    ``command -v aider`` fails inside the terminal even though aider is
    installed. The extra dirs come from :func:`backend.paths.extra_path_dirs`
    (the SAME source of truth used by CLI-tool detection in
    ``cli_tools_router``, so the "binary found" hint and the shell agree).

    Existing PATH entries are kept and searched first; extra dirs are appended.
    Returns ``None`` on any failure so the caller falls back to the default
    spawn (a broken PATH must never prevent the terminal from opening).
    """
    try:
        env = dict(os.environ)
        base = env.get("PATH", "")
        extras = extra_path_dirs()
        parts = [p for p in base.split(os.pathsep) if p] + extras
        env["PATH"] = os.pathsep.join(parts)
        return env
    except Exception as exc:  # noqa: BLE001 - PATH build is best-effort
        from backend.log import log_warning

        log_warning(
            f"pty: failed to build augmented PATH, using inherited env: {exc}",
            source=LOG_SOURCE,
        )
        return None


def spawn_shell(cols: int = 80, rows: int = 24) -> PtyProcess:
    """Spawn an interactive shell and return a :class:`PtyProcess`.

    Platform mapping:

    * ``win32`` → :mod:`pywinpty` (``cmd.exe``)
    * everything else (Linux / macOS / Termux) → :mod:`ptyprocess`
      (``bash -i``, falling back to ``sh``)

    Raises :class:`PtyError` (clear message) if the platform dependency is
    missing or spawn otherwise fails.
    """
    if sys.platform == "win32":
        return _spawn_windows(cols, rows)
    return _spawn_posix(cols, rows)


def _spawn_posix(cols: int, rows: int) -> PtyProcess:
    try:
        from ptyprocess import PtyProcess as _Pty
    except ImportError as exc:  # missing native dep on POSIX
        raise PtyError(
            "ptyprocess is not installed; required for POSIX/Termux PTY support. "
            "Install with `pip install ptyprocess` (or `pip install -e .`)."
        ) from exc
    try:
        env = build_spawn_env()
        try:
            impl = _Pty.spawn(["bash", "-i"], env=env)
        except Exception:  # noqa: BLE001 - bash missing → fall back to sh
            impl = _Pty.spawn(["sh"], env=env)
        impl.setwinsize(rows, cols)
        return PtyProcess(impl, "posix")
    except PtyError:
        raise
    except Exception as exc:  # noqa: BLE001 - normalise spawn failure
        raise PtyError(f"failed to spawn POSIX shell: {exc}") from exc


def _spawn_windows(cols: int, rows: int) -> PtyProcess:
    try:
        from pywinpty import PTY
    except ImportError as exc:  # missing native dep on Windows
        raise PtyError(
            "pywinpty is not installed; required for Windows PTY support. "
            "Install with `pip install pywinpty` (or `pip install -e .`)."
        ) from exc
    try:
        env = build_spawn_env()
        impl = PTY(cols, rows)
        if env is None:  # PATH build failed → default spawn (no env kwarg)
            impl.spawn("cmd.exe")
        else:
            # pywinpty accepts env as a mapping; augments cmd.exe's PATH with
            # the same user install dirs CLI detection searches.
            impl.spawn("cmd.exe", env=env)
        return PtyProcess(impl, "win")
    except PtyError:
        raise
    except Exception as exc:  # noqa: BLE001 - normalise spawn failure
        raise PtyError(f"failed to spawn Windows shell: {exc}") from exc


__all__ = ["PtyError", "PtyProcess", "spawn_shell", "build_spawn_env"]

"""Single source of truth for user-level executable search dirs (PATH augmentation).

WHY: the gateway server process is often started from a shell whose ``PATH`` is
narrower than the user's interactive login PATH. Tools installed via
``pip install --user`` / pipx (``~/.local/bin``), cargo (``~/.cargo/bin``), npm
global, pyenv, go, the Termux prefix, etc. then become invisible BOTH to:

* CLI-tool detection (:func:`backend.cli_tools_router._which_with_extra_paths`), and
* the interactive terminal PTY (:func:`backend.terminal.pty.spawn_shell`),

so the two could disagree with each other and with the user's real shell. This
module centralises the extra-dir list so detection and the spawned shell search
the SAME directories.
"""

from __future__ import annotations

import os
from typing import List, Tuple

from backend.log import log_warning

LOG_SOURCE = "backend.paths"

# Extra directories searched when probing for a CLI binary / building the PTY
# spawn PATH. ``~`` expands to ``$HOME``; ``$PREFIX`` to the Termux prefix
# (absent on non-Termux hosts, so that entry simply drops out).
EXTRA_PATH_DIRS: Tuple[str, ...] = (
    "~/.local/bin",  # pip --user / pipx
    "~/.cargo/bin",  # rust/cargo installs
    "~/bin",  # classic per-user bin
    "$PREFIX/bin",  # Termux prefix bin (pkg installs)
    "/data/data/com.termux/files/usr/bin",  # Termux absolute fallback
    "~/.pyenv/shims",  # pyenv-managed python CLIs
    "~/.npm-global/bin",  # npm global (custom prefix)
    "~/.deno/bin",  # deno install
    "~/go/bin",  # go install
    "/usr/local/bin",  # system-wide local installs
)


def extra_path_dirs() -> List[str]:
    """Resolve :data:`EXTRA_PATH_DIRS` to the ones that actually exist right now.

    Each candidate is passed through ``expanduser`` + ``expandvars``; entries
    that are empty, duplicated, or not a directory are dropped. Best effort:
    an unstatable dir is logged and skipped, never raised (R12 — no silent
    ``except: pass``).
    """
    out: List[str] = []
    seen: set[str] = set()
    for raw in EXTRA_PATH_DIRS:
        try:
            path = os.path.expandvars(os.path.expanduser(raw))
        except Exception as exc:  # noqa: BLE001 - bad env var expansion: skip entry
            log_warning(
                f"paths: cannot expand '{raw}': {exc}",
                source=LOG_SOURCE,
            )
            continue
        if not path or path in seen:
            continue
        seen.add(path)
        try:
            if os.path.isdir(path):
                out.append(path)
        except OSError as exc:  # R12: log, never swallow silently
            log_warning(
                f"paths: cannot stat extra path '{path}': {exc}",
                source=LOG_SOURCE,
            )
    return out


def is_termux() -> bool:
    """True when this process runs under Termux (Android).

    WHY: package routing differs there. Several CLIs are packaged for Termux
    (``pkg install aichat``) while their npm form cannot work: Node reports
    ``process.platform == "android"``, so npm never fetches the
    ``*-linux-arm64`` optional dependency the CLI needs at run time. CLI-tool
    presets use this to pick the install string that actually works (see
    ``backend.cli_presets.install_command_for``).

    Detection order: explicit ``$PREFIX`` pointing at the com.termux data dir
    (the normal case), then the absolute Termux prefix as a fallback.
    """
    prefix = os.environ.get("PREFIX", "")
    if "com.termux" in prefix:
        return True
    return os.path.isdir("/data/data/com.termux/files/usr")


__all__ = ["EXTRA_PATH_DIRS", "extra_path_dirs", "is_termux"]

"""Per-tool × per-platform compatibility catalog (CLI Tools compatibility view).

Source of truth for the ``cli tools`` compatibility display. The CLI Tools
launcher panel (``src/frontend/static/clitools.js``) renders one status badge
per platform for every tool and highlights the platform the gateway is actually
running on.

DATA LIVES IN ``cli_compat.json`` (shipped next to this file). This module is a
thin loader: it reads that JSON at import time and exposes the same public API
the rest of the codebase already depends on, so the cross-platform harness
(``scripts/cli-tools/compat-test.sh``) can write a platform column
programmatically — without parsing Python.

Public API (stable, do not rename without updating callers):
  * ``CLI_COMPAT``        — ``tool -> platform -> {status, note, source}``.
  * ``PLATFORMS``         — the canonical platform key order.
  * ``current_platform()``— detects the platform from Python (authoritative; the
    shell helpers in ``scripts/cli-tools/_common.sh`` detect it too, but the UI
    must agree with the server, so we detect it here).
  * ``compat_for(name)``  — safe lookup returning an ``unknown`` row per platform
    for unknown tools (fail-open, never raises).

Status vocabulary (stable codes, shared with the frontend):
  * ``verified``     — confirmed working on this platform, wired to aigate.
  * ``installable``  — can be installed + launched here (not yet confirmed live).
  * ``broken``       — install/build fails or the binary cannot run on this platform.
  * ``no_install``   — no verified install path for this platform.
  * ``not_a_cli``    — library/framework, not a launchable terminal CLI.
  * ``not_wired``    — installs, but runs in a mode aigate does not serve.
  * ``unknown``      — not yet tested on this platform (user fills in later).

``termux`` is seeded from on-device verification (Termux/aarch64, Python 3.14.6,
2026-09). The other three platforms are left ``unknown`` for the user to fill in
after testing on Windows / Linux / macOS. ``source`` = ``"tested-termux-2026-09"``
for the seeded rows so they are easy to find and update.

Cross-checked against ``cli_presets.LAUNCH_SUPPORT`` (launch wiring) — note the
two are DIFFERENT axes:
  * ``LAUNCH_SUPPORT`` = "does aigate have a launch builder + does the tool speak
    the gateway's OpenAI/Anthropic wire format" (code-level).
  * ``CLI_COMPAT``    = "does the tool actually install/run on THIS platform"
    (runtime/install-level). A tool can be ``LAUNCH_VERIFIED`` yet ``broken`` here
    (e.g. ``aider`` has a builder but needs Python 3.12 on a 3.14 device).
"""

from __future__ import annotations

import json
import os
import platform
from typing import Dict

# Resolve the JSON next to this file so `import cli_compat` works both as
# `backend.cli_compat` and as a bare `cli_compat` from `src/backend`.
_STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cli_compat.json")

# Reuse the authoritative Termux detector so detection agrees with install routing.
# Imported lazily inside :func:`current_platform` (not at module load) so that
# ``import cli_compat`` stays dependency-free and works both as ``backend.cli_compat``
# and as a bare ``cli_compat`` from ``src/backend``.

# --- status codes (kept in sync with the frontend badge renderer) -----------
STATUS_VERIFIED = "verified"
STATUS_INSTALLABLE = "installable"
STATUS_BROKEN = "broken"
STATUS_NO_INSTALL = "no_install"
STATUS_NOT_A_CLI = "not_a_cli"
STATUS_NOT_WIRED = "not_wired"
STATUS_UNKNOWN = "unknown"

# Canonical platform order. The current platform is highlighted in the UI.
PLATFORMS: tuple = ("termux", "linux", "windows", "macos")

# Statuses that should raise a visible warning on the CURRENT platform.
WARN_STATUSES = (
    STATUS_BROKEN,
    STATUS_NO_INSTALL,
    STATUS_NOT_A_CLI,
    STATUS_NOT_WIRED,
)

_SEEDED_SOURCE = "tested-termux-2026-09"


def _unknown_row() -> Dict[str, str]:
    """A blank per-platform row (status unknown)."""
    return {"status": STATUS_UNKNOWN, "note": "", "source": "unknown"}


def _unknown_compat() -> Dict[str, Dict[str, str]]:
    """A full four-platform unknown block for an unlisted tool."""
    return {p: _unknown_row() for p in PLATFORMS}


def _row(status: str, note: str, source: str = _SEEDED_SOURCE) -> Dict[str, str]:
    return {"status": status, "note": note, "source": source}


def _load_compat() -> Dict[str, Dict[str, Dict[str, str]]]:
    """Build ``CLI_COMPAT`` from ``cli_compat.json``.

    Only the CURRENT platform column for each tool is ever overwritten (by the
    harness); other platforms are preserved verbatim. Missing platforms fall
    back to an ``unknown`` row so the shape stays uniform.
    """
    try:
        with open(_STATUS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError as exc:  # pragma: no cover - file always ships
        raise FileNotFoundError(
            f"cli_compat.json not found at {_STATUS_FILE}; "
            "it must ship next to cli_compat.py"
        ) from exc

    compat: Dict[str, Dict[str, Dict[str, str]]] = {}
    for tool, platforms in data.get("compat", {}).items():
        compat[tool] = {}
        for p in PLATFORMS:
            row = platforms.get(p)
            if not isinstance(row, dict):
                compat[tool][p] = _unknown_row()
            else:
                compat[tool][p] = {
                    "status": row.get("status", STATUS_UNKNOWN),
                    "note": row.get("note", ""),
                    "source": row.get("source", "unknown"),
                }
    return compat


# CLI_COMPAT — tool name -> platform -> {status, note, source}
# Loaded from cli_compat.json (single source of truth).
CLI_COMPAT: Dict[str, Dict[str, Dict[str, str]]] = _load_compat()


def current_platform() -> str:
    """Detect the platform aigate is running on (authoritative, from Python).

    Reuses :func:`backend.paths.is_termux` so the platform used for install
    routing and the one shown in the UI are identical. Falls back to an
    environment/path probe (mirroring ``scripts/cli-tools/_common.sh``) and then
    ``platform.system()`` when the ``backend`` package is not importable — e.g. a
    bare ``import cli_compat`` from ``src/backend`` outside the app, or the
    cross-platform harness.
    """
    try:
        from backend.paths import is_termux as _is_termux

        if _is_termux():
            return "termux"
    except Exception:  # noqa: BLE001 - backend package not on path in isolation
        pass
    # Isolated fallback: Termux is detected by env/path, not by uname (some
    # Termux Python builds report platform.system() == "Android").
    if os.environ.get("TERMUX_VERSION") or os.path.isdir("/data/data/com.termux/files"):
        return "termux"
    sysname = platform.system()
    if sysname in ("Windows", "win32"):
        return "windows"
    if sysname == "Darwin":
        return "macos"
    if sysname == "Linux":
        return "linux"
    if sysname == "Android":  # Android userspace == Termux
        return "termux"
    return "unknown"


def compat_for(name: str) -> Dict[str, Dict[str, str]]:
    """Return the four-platform compatibility block for a tool name.

    Unknown tools get an all-``unknown`` block (fail-open). Callers must not rely
    on mutation — the returned object is the live catalog entry; copy if mutating.
    """
    return CLI_COMPAT.get(name, _unknown_compat())


__all__ = [
    "CLI_COMPAT",
    "PLATFORMS",
    "WARN_STATUSES",
    "STATUS_VERIFIED",
    "STATUS_INSTALLABLE",
    "STATUS_BROKEN",
    "STATUS_NO_INSTALL",
    "STATUS_NOT_A_CLI",
    "STATUS_NOT_WIRED",
    "STATUS_UNKNOWN",
    "current_platform",
    "compat_for",
]

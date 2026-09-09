"""Per-tool × per-platform compatibility catalog (CLI Tools compatibility view).

Source of truth for the ``cli tools`` compatibility display. The CLI Tools
launcher panel (``src/frontend/static/clitools.js``) renders one status badge
per platform for every tool and highlights the platform the gateway is actually
running on.

This module is intentionally DATA-ONLY and framework-free:

* ``CLI_COMPAT`` — ``tool -> platform -> {status, note, source}``.
* ``PLATFORMS`` — the canonical platform key order.
* ``current_platform()`` — detects the platform from Python (authoritative; the
  shell helpers in ``scripts/cli-tools/_common.sh`` detect it too, but the UI
  must agree with the server, so we detect it here).
* ``compat_for(name)`` — safe lookup returning an ``unknown`` row per platform
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

import platform
from typing import Dict

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


def _row(status: str, note: str) -> Dict[str, str]:
    return {"status": status, "note": note, "source": _SEEDED_SOURCE}


# Blank templates for the three not-yet-tested platforms.
_LIN = _unknown_row()
_WIN = _unknown_row()
_MAC = _unknown_row()

# --------------------------------------------------------------------------- #
# CLI_COMPAT — tool name -> platform -> {status, note, source}
# Only `termux` is seeded from device testing; the rest stay `unknown`.
# --------------------------------------------------------------------------- #
CLI_COMPAT: Dict[str, Dict[str, Dict[str, str]]] = {
    # ----- Group A: agentic coding -----
    "claude": {
        "termux": _row(STATUS_BROKEN,
                       "npm @anthropic-ai/claude-code has no Android binary; npm is dead on Termux."),
        "linux": _LIN, "windows": _WIN, "macos": _MAC,
    },
    "opencode": {
        "termux": _row(STATUS_BROKEN,
                       "npm opencode-ai has no Android binary; npm is dead on Termux."),
        "linux": _LIN, "windows": _WIN, "macos": _MAC,
    },
    "codex": {
        "termux": _row(STATUS_NOT_WIRED,
                       "NOT_WIRED — runs native OpenAI Responses API; aigate has no streaming responses inbound."),
        "linux": _LIN, "windows": _WIN, "macos": _MAC,
    },
    "gemini": {
        "termux": _row(STATUS_NOT_WIRED,
                       "NOT_WIRED — runs native Google mode; aigate serves OpenAI/Anthropic only."),
        "linux": _LIN, "windows": _WIN, "macos": _MAC,
    },
    "antigravity": {
        "termux": _row(STATUS_NO_INSTALL,
                       "NO_INSTALL — no verified CLI package (npm squat / 404)."),
        "linux": _LIN, "windows": _WIN, "macos": _MAC,
    },
    "phi": {
        "termux": _row(STATUS_NO_INSTALL,
                       "NO_INSTALL — no verified CLI package (npm squat / PyPI unrelated)."),
        "linux": _LIN, "windows": _WIN, "macos": _MAC,
    },
    "aider": {
        "termux": _row(STATUS_BROKEN,
                       "pip install aider-chat needs Python 3.10-3.12 (device is 3.14); version guard exits."),
        "linux": _LIN, "windows": _WIN, "macos": _MAC,
    },
    "goose": {
        "termux": _row(STATUS_NO_INSTALL,
                       "NO_INSTALL — no Android/Termux binary for Block's goose."),
        "linux": _LIN, "windows": _WIN, "macos": _MAC,
    },
    "amp": {
        "termux": _row(STATUS_NO_INSTALL,
                       "NO_INSTALL — @ampcode/cli has no Android/Termux build."),
        "linux": _LIN, "windows": _WIN, "macos": _MAC,
    },
    "qwen": {
        "termux": _row(STATUS_BROKEN,
                       "npm @qwen-code/qwen-code has no Android binary; npm is dead on Termux."),
        "linux": _LIN, "windows": _WIN, "macos": _MAC,
    },
    "cline": {
        "termux": _row(STATUS_BROKEN,
                       "npm cline has no Android binary; npm is dead on Termux."),
        "linux": _LIN, "windows": _WIN, "macos": _MAC,
    },
    "kilo": {
        "termux": _row(STATUS_BROKEN,
                       "npm @kilocode/cli has no Android binary; npm is dead on Termux."),
        "linux": _LIN, "windows": _WIN, "macos": _MAC,
    },
    # ----- Group B: autonomous agents -----
    "openhands": {
        "termux": _row(STATUS_BROKEN,
                       "pip install openhands needs Python 3.12 (device is 3.14); version guard exits."),
        "linux": _LIN, "windows": _WIN, "macos": _MAC,
    },
    "swe-agent": {
        "termux": _row(STATUS_NO_INSTALL,
                       "NO_INSTALL — PyPI 404; Docker/conda setup impractical on Termux."),
        "linux": _LIN, "windows": _WIN, "macos": _MAC,
    },
    "open-interpreter": {
        "termux": _row(STATUS_BROKEN,
                       "pip install open-interpreter is heavy but reportedly installable on Termux (Py3.14)."),
        "linux": _LIN, "windows": _WIN, "macos": _MAC,
    },
    "autogpt": {
        "termux": _row(STATUS_NO_INSTALL,
                       "NO_INSTALL — official AutoGPT is a Docker platform; PyPI 'autogpt' is an unrelated squat."),
        "linux": _LIN, "windows": _WIN, "macos": _MAC,
    },
    "gpt-researcher": {
        "termux": _row(STATUS_NOT_A_CLI,
                       "NOT_A_CLI — pip package is a library/backend only; no launchable binary."),
        "linux": _LIN, "windows": _WIN, "macos": _MAC,
    },
    "crewai": {
        "termux": _row(STATUS_NOT_A_CLI,
                       "NOT_A_CLI — console script is a framework scaffolder/runner requiring a project in CWD."),
        "linux": _LIN, "windows": _WIN, "macos": _MAC,
    },
    # ----- Group C: chat & shell -----
    "llm": {
        "termux": _row(STATUS_BROKEN,
                       "pip install llm fails building 'jiter' (no Android wheel, Py3.14)."),
        "linux": _LIN, "windows": _WIN, "macos": _MAC,
    },
    "sgpt": {
        "termux": _row(STATUS_NO_INSTALL,
                       "NO_INSTALL — npm squat / PyPI 404 / Go binary has no Android build."),
        "linux": _LIN, "windows": _WIN, "macos": _MAC,
    },
    "mods": {
        "termux": _row(STATUS_NO_INSTALL,
                       "NO_INSTALL — Go binary (charmbracelet/mods) has no Android build."),
        "linux": _LIN, "windows": _WIN, "macos": _MAC,
    },
    "oterm": {
        "termux": _row(STATUS_BROKEN,
                       "pip install oterm fails building 'jiter' (no Android wheel, Py3.14)."),
        "linux": _LIN, "windows": _WIN, "macos": _MAC,
    },
    "gptme": {
        "termux": _row(STATUS_BROKEN,
                       "pip install gptme fails building 'jiter' (no Android wheel, Py3.14)."),
        "linux": _LIN, "windows": _WIN, "macos": _MAC,
    },
    "aichat": {
        "termux": _row(STATUS_VERIFIED,
                       "pkg install aichat (0.30.0 verified runs on Termux); OpenAI-compatible, wired to aigate."),
        "linux": _LIN, "windows": _WIN, "macos": _MAC,
    },
}


def current_platform() -> str:
    """Detect the platform aigate is running on (authoritative, from Python).

    Reuses :func:`backend.paths.is_termux` so the platform used for install
    routing and the one shown in the UI are identical. Falls back to
    ``platform.system()`` alone when the ``backend`` package is not importable
    (e.g. a bare ``import cli_compat`` from ``src/backend`` outside the app).
    """
    try:
        from backend.paths import is_termux as _is_termux

        if _is_termux():
            return "termux"
    except Exception:  # noqa: BLE001 - backend package not on path in isolation
        pass
    sysname = platform.system()
    if sysname == "Windows":
        return "windows"
    if sysname == "Darwin":
        return "macos"
    if sysname == "Linux":
        return "linux"
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

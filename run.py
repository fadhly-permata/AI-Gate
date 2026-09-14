#!/usr/bin/env python3
"""Zero-setup launcher for aigate.

Just run `python run.py` (needs Python 3.10+ and internet on first run).
Any missing Python dependency is auto-installed via pip, then the aigate
server starts. On Windows, `pywinpty` is included automatically; on POSIX/Termux
`ptyprocess` is used.

For a pre-installed environment you can instead use `uvicorn backend.server:app`
or the `aigate` console script after `pip install -e .`.
"""

import importlib.util
import os
import subprocess
import sys

# Minimum required Python version. Mirrors pyproject.toml [project]
# requires-python = ">=3.10" (line 11) — that entry is the source of truth;
# keep this constant in sync if it ever changes.
MIN_PYTHON = (3, 10)


def _check_python_version(info) -> None:
    """Exit with one friendly message if the interpreter is older than MIN_PYTHON.

    info is a version tuple such as sys.version_info[:3]. Runs before any path
    setup, dependency install, or backend import so an old Python sees this
    message instead of a traceback from a package that needs 3.10+. Kept as a
    separate function so it can be tested in isolation. The whole file avoids
    3.10+ syntax (no match, no except*, no union annotations) so old
    interpreters can still parse the gate itself.
    """
    if tuple(info[:2]) >= MIN_PYTHON:
        return
    need = ".".join(str(part) for part in MIN_PYTHON)
    have = ".".join(str(part) for part in tuple(info[:3]))
    sys.stderr.write(
        f"aigate needs Python {need} or newer - you have {have}\n"
        f"Install Python {need} or newer, then run this again.\n"
    )
    sys.exit(1)


# Gate first: must stop old interpreters before anything below can break.
_check_python_version(sys.version_info[:3])

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))

# module-name -> pip spec (pinned to match pyproject.toml)
REQUIRED = {
    "fastapi": "fastapi>=0.95,<0.100",
    "pydantic": "pydantic>=1.10,<2",
    "uvicorn": "uvicorn",
    "websockets": "websockets",  # WS support for the terminal PTY bridge
    "sqlalchemy": "sqlalchemy",
    "ptyprocess": "ptyprocess",
    "httpx": "httpx",
}
if sys.platform == "win32":
    REQUIRED["pywinpty"] = "pywinpty"


def ensure_deps() -> None:
    """Install any missing dependency automatically (first run needs network)."""
    for _mod, spec in REQUIRED.items():
        if importlib.util.find_spec(_mod) is None:
            subprocess.check_call([sys.executable, "-m", "pip", "install", spec])


if __name__ == "__main__":
    ensure_deps()
    from backend.launcher import main

    main()

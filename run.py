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

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))

# module-name -> pip spec (pinned to match pyproject.toml)
REQUIRED = {
    "fastapi": "fastapi>=0.95,<0.100",
    "pydantic": "pydantic>=1.10,<2",
    "uvicorn": "uvicorn",
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

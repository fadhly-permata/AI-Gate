"""Runtime entry point for aigate.

Dependency auto-install (including the Windows-only ``pywinpty`` extra) is
handled by the repo-root ``run.py`` shim before this module is imported.
All heavy imports are deferred into :func:`main` so they only run after the
shim has guaranteed the environment is ready.
"""

import os
import sys


def main() -> None:
    """Parse options and run the aigate server via uvicorn."""
    import uvicorn
    from backend.server import app

    port: int = 8080
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            port = int(sys.argv[idx + 1])
    else:
        port = int(os.environ.get("AIGATE_PORT", "8080"))

    dev: bool = os.environ.get("AIGATE_DEV", "0") == "1"

    # WebSocket keepalive (protocol level, uvicorn's `websockets` impl): the
    # server pings every 15s and drops a connection whose pong is not back
    # within 15s. This detects half-open/dead sockets fast (Chrome freezing a
    # backgrounded tab, a network blip) so the transport tears down cleanly and
    # the client can reconnect to the still-running PTY (see terminal.session).
    # An APPLICATION-level heartbeat complements this (terminal.router).
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        ws_ping_interval=15.0,
        ws_ping_timeout=15.0,
    )


if __name__ == "__main__":
    main()

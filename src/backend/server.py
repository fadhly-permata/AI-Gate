"""aigate FastAPI application.

Serves the local web UI static files (produced by the fe-dev specialist) and
exposes the gateway/management REST API. Runs native as a Python app
(ADR-009) — no deployment or packaging step required.

Run with: `uvicorn backend.server:app`
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.cli_tools_router import router as cli_tools_router
from backend.analytics_router import router as analytics_router
from backend.combos_router import router as combos_router
from backend.config.db import SessionLocal
from backend.config.logs_router import router as logs_router
from backend.endpoints_router import router as endpoints_router
from backend.export_router import router as export_router
from backend.config.settings_router import router as settings_router
from backend.gateway.errors import GatewayError, gateway_error_handler
from backend.gateway.router import router
from backend.log import SEVERITY_ERROR, log_exception
from backend.providers_router import router as providers_router
from backend.selfheal_router import router as selfheal_router
from backend.proxies_router import router as proxies_router
from backend.accounts_router import router as accounts_router
from backend.terminal.router import router as terminal_router
from backend.usage_router import router as usage_router

STATIC_DIR: Path = (
    Path(__file__).resolve().parent.parent / "frontend" / "static"
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Bootstrap the config engine before serving requests (ADR-004/010)."""
    from backend.config.db import init_db
    from backend.config.settings import ensure_seeded

    init_db()
    # Seed default config-in-DB rows on first boot (idempotent, R12-safe).
    try:
        ensure_seeded()
    except Exception:  # noqa: BLE001 — startup must not crash on seed failure
        # ADR-011: persist to LogEntry (DB) with auto-captured traceback.
        log_exception(
            SEVERITY_ERROR,
            "lifespan: ensure_seeded failed during startup",
            source="backend.server.lifespan",
        )
    # Seed preset CLI tool groups (B3.4) — idempotent, never crash startup.
    try:
        from backend.cli_presets import seed_cli_tools

        with SessionLocal() as seed_session:
            seed_cli_tools(seed_session)
    except Exception:  # noqa: BLE001 — startup must not crash on seed failure
        # ADR-011: persist to LogEntry (DB) with auto-captured traceback.
        log_exception(
            SEVERITY_ERROR,
            "lifespan: seed_cli_tools failed during startup",
            source="backend.server.lifespan",
        )
    yield


app = FastAPI(title="aigate", version="0.0.1", lifespan=lifespan)

# OpenAI-compatible gateway endpoints (/v1/chat/completions, /v1/models).
app.include_router(router)
# Provider CRUD + model auto-discovery + key management (B2.2).
app.include_router(providers_router)
# Proxy Pools CRUD + node management + health check (B2.3).
app.include_router(proxies_router)
# Combo CRUD + strategy config (B2.4).
app.include_router(combos_router)
# Endpoint CRUD + binding (B2.5 / ADR-008).
app.include_router(endpoints_router)
# Export / Import the whole config as one JSON file (B5.7 / PRD §2.4.4).
# MUST be included BEFORE settings_router: settings_router exposes
# GET /api/settings/{key}, and Starlette matches routes in registration order,
# so /api/settings/export would otherwise be swallowed as key="export".
app.include_router(export_router)
# Settings UI API (B1.3): read/write config-in-DB Setting rows.
app.include_router(settings_router)
# CLI Tools presets + resolve (B3.4): group/tool list + launch resolver.
app.include_router(cli_tools_router)
# Operational log API (dev-mode / observability): GET + POST /api/logs.
app.include_router(logs_router)
# Terminal PTY bridge (B3.2): WS /ws/terminal/{tab_id}.
app.include_router(terminal_router)
# Self-Heal (B4.1): agentic CLI detection + self-heal run endpoint.
app.include_router(selfheal_router)
# Multi-account + OAuth management (B5.1).
app.include_router(accounts_router)
# Quota & usage tracking API (B5.5): GET /api/usage, /api/usage/summary, /api/quota.
app.include_router(usage_router)
# Request-log (debug) + usage analytics API (B5.6): GET /api/request-logs, /api/analytics.
app.include_router(analytics_router)
# Render gateway failures as the OpenAI error envelope from the contract.
app.add_exception_handler(GatewayError, gateway_error_handler)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness probe for the backend."""
    return {"status": "ok"}


# fe-dev owns src/frontend/static; mount only when it exists (parallel build).
if STATIC_DIR.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(STATIC_DIR), html=True),
        name="ui",
    )

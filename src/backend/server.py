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

from backend.gateway.errors import GatewayError, gateway_error_handler
from backend.gateway.router import router

STATIC_DIR: Path = (
    Path(__file__).resolve().parent.parent.parent / "frontend" / "static"
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Bootstrap the config engine before serving requests (ADR-004)."""
    from backend.config.db import init_db

    init_db()
    yield


app = FastAPI(title="aigate", version="0.0.1", lifespan=lifespan)

# OpenAI-compatible gateway endpoints (/v1/chat/completions, /v1/models).
app.include_router(router)
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

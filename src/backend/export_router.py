"""Export / Import HTTP API (task B5.7 — PRD §2.4.4, local settings backup).

Two endpoints back the "save all settings to one file / restore on another
device" flow, replacing cloud sync:

* ``GET  /api/settings/export`` -> the full config document as a JSON download
  (``Content-Disposition: attachment`` so the browser saves it).
* ``POST /api/settings/import`` -> restore config from such a document.

Route ordering: ``backend.config.settings_router`` also serves
``GET /api/settings/{key}``. This router MUST be included in ``server.py``
BEFORE ``settings_router`` so ``/api/settings/export`` and
``/api/settings/import`` are matched here and never swallowed by the ``{key}``
path parameter.

Rule R10: Pydantic **v1** only (these handlers take a raw ``Request`` body, so
no v2 syntax is involved). Rule R11 / ADR-007: the exported document carries
secrets in plaintext — it is a local file the user owns. Rule R12: every error
is logged to ``LogEntry`` via ``backend.log`` before an error response.

Shapes (documented for fe-dev):
* ``GET /api/settings/export`` -> 200, ``application/json`` body = the export
  document (see ``backend.export.export_settings``), plus a
  ``Content-Disposition: attachment; filename="aigate-settings-YYYYMMDD.json"``
  header.
* ``POST /api/settings/import`` -> body = that same export document (raw JSON
  object). Optional ``mode`` via query string (``?mode=replace`` default, or
  ``?mode=merge``) or a top-level ``"mode"`` key in the body.
    - 200 ``{"ok": true, "imported": {"providers": N, ...}}`` on success.
    - 400 ``{"ok": false, "error": "invalid_format"}`` when the payload is not
      a valid aigate export document.
    - 500 ``{"ok": false, "error": "<reason>"}`` on a restore failure (rolled
      back + logged).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.config.db import SessionLocal
from backend.export import import_settings
from backend.log import log_error, log_info, log_warning

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/settings/export")
def export_settings_endpoint() -> JSONResponse:
    """Return the whole configuration as a downloadable JSON document."""
    with SessionLocal() as session:
        # Imported lazily so the module-level import stays light.
        from backend.export import export_settings

        doc = export_settings(session)
    log_info("GET /api/settings/export served", source="backend.export_router")

    filename = f"aigate-settings-{datetime.utcnow().strftime('%Y%m%d')}.json"
    return JSONResponse(
        content=doc,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/api/settings/import")
async def import_settings_endpoint(request: Request) -> JSONResponse:
    """Restore configuration from an exported JSON document.

    Accepts the raw export object as the body. ``mode`` may be supplied either
    as a query parameter (``?mode=merge``) or as a top-level ``"mode"`` key in
    the body; ``replace`` is the default.
    """
    try:
        payload = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:  # body was not valid JSON
        log_warning(
            "POST /api/settings/import: body is not valid JSON",
            source="backend.export_router",
            context={"error": str(exc)},
        )
        return JSONResponse(
            status_code=400, content={"ok": False, "error": "invalid_format"}
        )

    # ``mode`` precedence: query string > body key > default 'replace'.
    mode = request.query_params.get("mode")
    if not mode and isinstance(payload, dict):
        mode = payload.get("mode")
    mode = mode or "replace"

    with SessionLocal() as session:
        result: Dict[str, Any] = import_settings(session, payload, mode=mode)

    if result.get("ok"):
        log_info(
            f"POST /api/settings/import ok (mode={mode})",
            source="backend.export_router",
            context=result.get("imported"),
        )
        return JSONResponse(status_code=200, content=result)

    error = result.get("error")
    if error == "invalid_format":
        log_warning(
            "POST /api/settings/import rejected: invalid_format",
            source="backend.export_router",
        )
        return JSONResponse(status_code=400, content=result)

    # A genuine restore failure (already rolled back + logged by the service).
    log_error(
        f"POST /api/settings/import failed: {error}",
        source="backend.export_router",
    )
    return JSONResponse(status_code=500, content=result)


__all__ = ["router"]

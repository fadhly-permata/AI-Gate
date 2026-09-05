"""Settings HTTP API (FastAPI router) for task B1.3 — Settings UI.

Exposes read/write of the config-in-DB ``Setting`` key-value store so the
frontend Settings panel can read & persist ``port``, ``dev_mode``, ``theme``,
``locale`` (and any other ``Setting`` rows).

Rule R10: Pydantic **v1** ``BaseModel`` only.
Rule R11: values stored plaintext (the repo handles this; nothing here encrypts).
Rule R12: every error is logged to ``LogEntry`` via ``backend.log`` (no silent
failures) before an ``HTTPException`` is raised.

Shapes (documented for fe-dev):
- ``GET /api/settings`` -> full settings dict ``{ key: value, ... }``.
- ``PUT /api/settings`` -> update one or many keys in a single call.
    * Bulk:    ``{ "settings": { "port": "8080", "theme": "dark" } }``
    * Single:  ``{ "key": "port", "value": "8080" }``
  Both return the full settings dict after applying the change(s).
  JSON scalars (int/bool) are coerced to strings to match the DB column.
- ``GET /api/settings/{key}`` -> ``{ "key": ..., "value": ... }`` or 404.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config.settings import get as get_setting
from backend.config.settings import list_all, set as set_setting
from backend.log import SEVERITY_ERROR, log_exception

logger = logging.getLogger(__name__)

router = APIRouter()


class SettingUpdate(BaseModel):
    """Update payload for ``PUT /api/settings``.

    Accepts EITHER a bulk ``settings`` map OR a single ``key``/``value`` pair
    (see module docstring). ``value`` accepts JSON scalars and is coerced to a
    string before being stored (Pydantic v1 does int/bool->str coercion).
    """

    settings: Optional[Dict[str, str]] = None
    key: Optional[str] = None
    value: Optional[Any] = None


@router.get("/api/settings")
def get_settings() -> Dict[str, str]:
    """Return the full settings dict (every ``Setting`` row)."""
    try:
        return list_all()
    except Exception as exc:  # noqa: BLE001 - log then surface as 500
        log_exception(
            SEVERITY_ERROR,
            "GET /api/settings failed",
            source="backend.config.settings_router",
            exc=exc,
        )
        raise HTTPException(status_code=500, detail="Failed to read settings")


@router.put("/api/settings")
def put_settings(payload: SettingUpdate) -> Dict[str, str]:
    """Update one or many settings, returning the full dict afterwards."""
    try:
        if payload.settings:
            for key, value in payload.settings.items():
                set_setting(key, str(value))
        elif payload.key is not None and payload.value is not None:
            set_setting(payload.key, str(payload.value))
        else:
            raise HTTPException(
                status_code=400,
                detail="Provide 'settings' map or a 'key'/'value' pair",
            )
        return list_all()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - log then surface as 500
        log_exception(
            SEVERITY_ERROR,
            "PUT /api/settings failed",
            source="backend.config.settings_router",
            exc=exc,
        )
        raise HTTPException(status_code=500, detail="Failed to update settings")


@router.get("/api/settings/{key}")
def get_setting_by_key(key: str) -> Dict[str, str]:
    """Convenience lookup of a single setting; 404 if the key is absent."""
    try:
        value = get_setting(key)
    except Exception as exc:  # noqa: BLE001 - log then surface as 500
        log_exception(
            SEVERITY_ERROR,
            f"GET /api/settings/{key} failed",
            source="backend.config.settings_router",
            exc=exc,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to read setting '{key}'"
        )
    if value is None:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    return {"key": key, "value": value}


__all__ = ["router"]

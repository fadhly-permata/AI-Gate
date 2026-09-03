"""Provider CRUD + model auto-discovery + key management (task B2.2).

Backend-only implementation of the ``/api/providers`` contract pinned by PM.

ADR-007: ``api_key`` is stored and returned in **plaintext** — no encryption,
no masking. ``custom_headers`` is a JSON-encoded string column in the DB and a
plain dict in the API.

ADR-011 / R12: every method logs to ``LogEntry`` via ``backend.log``. No
``except: pass`` — failures are logged (warning) and surfaced as ``ok:false``
or an OpenAI-style error envelope, never swallowed.

Pydantic **v1** only (rule R10): ``BaseModel`` + ``class Config``, no v2 syntax.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config.db import SessionLocal
from backend.log import log_error_exc, log_info, log_warning
from backend.models import (
    ComboMember,
    EndpointBinding,
    Provider,
    ProviderModel,
)

LOG_SOURCE = "backend.providers.router"

router = APIRouter()


# --------------------------------------------------------------------------- #
# Pydantic v1 DTOs / request bodies
# --------------------------------------------------------------------------- #
class ProviderCreate(BaseModel):
    name: str
    type: str
    base_url: str
    api_key: str
    enabled: Optional[bool] = True
    custom_headers: Optional[Dict[str, Any]] = None

    class Config:
        pass


class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    enabled: Optional[bool] = None
    custom_headers: Optional[Dict[str, Any]] = None

    class Config:
        pass


class ModelDTO(BaseModel):
    id: int
    model_id: str
    model_name: str
    capabilities: str

    class Config:
        pass


class ProviderDTO(BaseModel):
    id: int
    name: str
    type: str
    base_url: str
    api_key: str
    enabled: bool
    custom_headers: Dict[str, Any]
    models: List[ModelDTO]

    class Config:
        pass


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _encode_headers(headers: Optional[Dict[str, Any]]) -> str:
    """JSON-encode a headers dict for the DB column (default '{}')."""
    try:
        return json.dumps(headers or {}, ensure_ascii=False)
    except Exception:  # noqa: BLE001 - never crash on bad input
        return "{}"


def _decode_headers(raw: Optional[str]) -> Dict[str, Any]:
    """Parse the DB JSON string back into a dict; tolerate garbage gracefully."""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:  # noqa: BLE001 - bad data must not 500
        return {}


def _provider_to_dto(session: Session, provider: Provider) -> ProviderDTO:
    models = (
        session.query(ProviderModel)
        .filter_by(provider_id=provider.id)
        .all()
    )
    return ProviderDTO(
        id=provider.id,
        name=provider.name,
        type=provider.type,
        base_url=provider.base_url,
        api_key=provider.api_key,  # ADR-007: plaintext in/out
        enabled=bool(provider.enabled),
        custom_headers=_decode_headers(provider.custom_headers),
        models=[
            ModelDTO(
                id=m.id,
                model_id=m.model_id,
                model_name=m.model_name,
                capabilities=m.capabilities or "",
            )
            for m in models
        ],
    )


def _not_found(message: str, code: str = "provider_not_found") -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"error": {"message": message, "type": "not_found", "code": code}},
    )


async def _fetch_models(provider: Provider) -> tuple[bool, Any]:
    """Best-effort OpenAI-style model discovery.

    Returns ``(ok, payload)`` where ``payload`` is a list of normalized model
    dicts on success, or an error message string on failure. Never raises.
    """
    url = provider.base_url.rstrip("/") + "/models"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {provider.api_key}",
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            body = resp.json()
    except Exception as exc:  # noqa: BLE001 - network/parse failures are expected
        return False, str(exc)

    try:
        if not isinstance(body, dict):
            return False, "unexpected /models response shape"
        data = body.get("data", [])
        if not isinstance(data, list):
            return False, "unexpected /models 'data' shape"
        normalized: List[Dict[str, Any]] = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            mid = entry.get("id")
            if not mid:
                continue
            normalized.append(
                {
                    "model_id": str(mid),
                    "model_name": str(entry.get("id")),
                    "capabilities": str(entry.get("capabilities", "") or ""),
                }
            )
        return True, normalized
    except Exception as exc:  # noqa: BLE001 - malformed payload
        return False, str(exc)


async def _discover_and_persist(
    session: Session, provider: Provider
) -> tuple[bool, str]:
    """Run discovery and replace the provider's ProviderModel rows.

    Returns ``(ok, error_message)``. On failure logs a warning and returns
    ``ok=False`` with the message; the caller decides how to respond.
    """
    ok, payload = await _fetch_models(provider)
    if not ok:
        log_warning(
            f"model discovery failed for provider {provider.id} "
            f"({provider.name}): {payload}",
            source=LOG_SOURCE,
        )
        return False, str(payload)

    # Replace existing rows for this provider.
    session.query(ProviderModel).filter_by(provider_id=provider.id).delete()
    for entry in payload:
        session.add(
            ProviderModel(
                provider_id=provider.id,
                model_id=entry["model_id"],
                model_name=entry["model_name"],
                capabilities=entry["capabilities"],
            )
        )
    session.commit()
    log_info(
        f"discovered {len(payload)} model(s) for provider {provider.id} "
        f"({provider.name})",
        source=LOG_SOURCE,
    )
    return True, ""


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@router.get("/api/providers")
def list_providers() -> dict:
    """List all providers with their (possibly empty) discovered models."""
    with SessionLocal() as session:
        providers = session.query(Provider).order_by(Provider.id).all()
        data = [_provider_to_dto(session, p).dict() for p in providers]
    log_info(f"listed {len(data)} provider(s)", source=LOG_SOURCE)
    return {"object": "list", "data": data}


@router.post("/api/providers", status_code=201)
async def create_provider(req: ProviderCreate) -> dict:
    """Create a provider; best-effort auto-discover models afterward."""
    provider = Provider(
        name=req.name,
        type=req.type,
        base_url=req.base_url,
        api_key=req.api_key,  # ADR-007: plaintext
        enabled=bool(req.enabled),
        custom_headers=_encode_headers(req.custom_headers),
    )
    with SessionLocal() as session:
        session.add(provider)
        session.commit()
        session.refresh(provider)
        created_id = provider.id
        # Best-effort discovery (do NOT 500 on failure).
        await _discover_and_persist(session, provider)
        dto = _provider_to_dto(session, provider).dict()
    log_info(
        f"created provider {created_id} ({req.name}, type={req.type})",
        source=LOG_SOURCE,
    )
    return dto


@router.get("/api/providers/{provider_id}")
def get_provider(provider_id: int) -> Any:
    with SessionLocal() as session:
        provider = session.get(Provider, provider_id)
        if provider is None:
            log_warning(
                f"get_provider: provider {provider_id} not found",
                source=LOG_SOURCE,
            )
            return _not_found(f"provider {provider_id} not found")
        dto = _provider_to_dto(session, provider).dict()
    log_info(f"fetched provider {provider_id}", source=LOG_SOURCE)
    return dto


@router.put("/api/providers/{provider_id}")
def update_provider(provider_id: int, req: ProviderUpdate) -> Any:
    with SessionLocal() as session:
        provider = session.get(Provider, provider_id)
        if provider is None:
            log_warning(
                f"update_provider: provider {provider_id} not found",
                source=LOG_SOURCE,
            )
            return _not_found(f"provider {provider_id} not found")

        changed: List[str] = []
        if req.name is not None:
            provider.name = req.name
            changed.append("name")
        if req.type is not None:
            provider.type = req.type
            changed.append("type")
        if req.base_url is not None:
            provider.base_url = req.base_url
            changed.append("base_url")
        if req.api_key is not None:
            provider.api_key = req.api_key  # ADR-007: plaintext
            changed.append("api_key")
        if req.enabled is not None:
            provider.enabled = bool(req.enabled)
            changed.append("enabled")
        if req.custom_headers is not None:
            provider.custom_headers = _encode_headers(req.custom_headers)
            changed.append("custom_headers")

        session.commit()
        session.refresh(provider)
        dto = _provider_to_dto(session, provider).dict()
    log_info(
        f"updated provider {provider_id}: {', '.join(changed) or 'no fields'}",
        source=LOG_SOURCE,
    )
    return dto


@router.delete("/api/providers/{provider_id}")
def delete_provider(provider_id: int) -> Any:
    with SessionLocal() as session:
        provider = session.get(Provider, provider_id)
        if provider is None:
            log_warning(
                f"delete_provider: provider {provider_id} not found",
                source=LOG_SOURCE,
            )
            return _not_found(f"provider {provider_id} not found")

        # Cascade (manual, matching the contract):
        # 1. ProviderModel rows
        session.query(ProviderModel).filter_by(provider_id=provider_id).delete()
        # 2. ComboMember rows referencing this provider
        session.query(ComboMember).filter_by(provider_id=provider_id).delete()
        # 3. EndpointBinding rows (bind_type=='provider', bind_id==id)
        session.query(EndpointBinding).filter_by(
            bind_type="provider", bind_id=provider_id
        ).delete()
        # 4. The provider itself
        session.delete(provider)
        session.commit()
    log_info(
        f"deleted provider {provider_id} (cascaded models/members/bindings)",
        source=LOG_SOURCE,
    )
    return {"ok": True}


@router.post("/api/providers/{provider_id}/discover")
async def discover_provider(provider_id: int) -> dict:
    """Re-run model discovery; replaces the provider's model rows.

    Always returns 200. ``ok:true`` with discovered ``models`` on success, or
    ``ok:false`` with an ``error`` message on failure (logged as warning).
    """
    with SessionLocal() as session:
        provider = session.get(Provider, provider_id)
        if provider is None:
            log_warning(
                f"discover_provider: provider {provider_id} not found",
                source=LOG_SOURCE,
            )
            return {"ok": False, "error": f"provider {provider_id} not found"}
        ok, err = await _discover_and_persist(session, provider)
        if not ok:
            return {"ok": False, "error": err}
        models = (
            session.query(ProviderModel)
            .filter_by(provider_id=provider_id)
            .all()
        )
        model_dtos = [
            ModelDTO(
                id=m.id,
                model_id=m.model_id,
                model_name=m.model_name,
                capabilities=m.capabilities or "",
            ).dict()
            for m in models
        ]
    return {"ok": True, "models": model_dtos}


__all__ = ["router"]

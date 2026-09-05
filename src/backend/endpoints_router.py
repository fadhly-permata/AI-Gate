"""Endpoint CRUD API (task B2.5 — ADR-008 binding proxy at Endpoint level).

Backend-only implementation of the ``/api/endpoints`` contract pinned by PM.

Each ``Endpoint`` represents a named OpenAI-compatible gateway entry point. It
optionally binds (via a single ``EndpointBinding`` row) to either a ``Provider``
or a ``Combo``, and may reference a ``ProxyPool`` (``proxy_pool_id``) for egress.

ADR-007: ``internal_api_key`` stored + returned **plaintext** (no encryption).
ADR-011 / R12: every method logs to ``LogEntry`` via ``backend.log``; no
swallowed exceptions. 404/400 return the OpenAI-style error envelope
``{"error": {"message", "type", "code"}}``.
Pydantic **v1** only (rule R10): ``BaseModel`` + ``class Config``.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config.db import SessionLocal
from backend.gateway.token_saver import TOKEN_SAVER_MODES
from backend.log import log_info, log_warning
from backend.models import Endpoint, EndpointBinding

LOG_SOURCE = "backend.endpoints.router"

router = APIRouter()


# --------------------------------------------------------------------------- #
# Pydantic v1 DTOs / request bodies
# --------------------------------------------------------------------------- #
class BindingRef(BaseModel):
    bind_type: str  # "provider" | "combo"
    bind_id: int

    class Config:
        pass


class EndpointCreate(BaseModel):
    name: str
    listen_host: Optional[str] = None
    listen_port: Optional[int] = None
    access_control_enabled: Optional[bool] = False
    internal_api_key: Optional[str] = ""
    proxy_pool_id: Optional[int] = None
    token_saver: Optional[str] = "off"  # ADR-013: 'off'|'rtk'|'caveman'|'ponytail'
    binding: Optional[BindingRef] = None

    class Config:
        pass


class EndpointUpdate(BaseModel):
    name: Optional[str] = None
    listen_host: Optional[str] = None
    listen_port: Optional[int] = None
    access_control_enabled: Optional[bool] = None
    internal_api_key: Optional[str] = None
    proxy_pool_id: Optional[int] = None
    token_saver: Optional[str] = None
    binding: Optional[BindingRef] = None

    class Config:
        pass


class EndpointDTO(BaseModel):
    id: int
    name: str
    listen_host: str
    listen_port: int
    access_control_enabled: bool
    internal_api_key: str  # ADR-007: plaintext
    proxy_pool_id: Optional[int]
    token_saver: str  # ADR-013
    binding: Optional[dict]

    class Config:
        pass


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _binding_to_dict(binding: Optional[EndpointBinding]) -> Optional[dict]:
    if binding is None:
        return None
    return {"bind_type": binding.bind_type, "bind_id": binding.bind_id}


def _endpoint_to_dto(session: Session, endpoint: Endpoint) -> dict:
    binding = (
        session.query(EndpointBinding)
        .filter_by(endpoint_id=endpoint.id)
        .first()
    )
    return EndpointDTO(
        id=endpoint.id,
        name=endpoint.name,
        listen_host=endpoint.listen_host or "127.0.0.1",
        listen_port=endpoint.listen_port or 8000,
        access_control_enabled=bool(endpoint.access_control_enabled),
        internal_api_key=endpoint.internal_api_key,  # ADR-007: plaintext
        proxy_pool_id=endpoint.proxy_pool_id,
        token_saver=endpoint.token_saver or "off",  # ADR-013
        binding=_binding_to_dict(binding),
    ).dict()


def _not_found(message: str, code: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"error": {"message": message, "type": "not_found", "code": code}},
    )


def _bad_request(message: str, code: str) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "message": message,
                "type": "invalid_request_error",
                "code": code,
            }
        },
    )


def _replace_binding(
    session: Session, endpoint_id: int, bind_type: str, bind_id: int
) -> None:
    """Delete any existing single binding for the endpoint, then insert one."""
    session.query(EndpointBinding).filter_by(endpoint_id=endpoint_id).delete()
    session.add(
        EndpointBinding(
            endpoint_id=endpoint_id, bind_type=bind_type, bind_id=bind_id
        )
    )


# --------------------------------------------------------------------------- #
# Routes: Endpoint CRUD
# --------------------------------------------------------------------------- #
@router.get("/api/endpoints")
def list_endpoints() -> dict:
    with SessionLocal() as session:
        endpoints = session.query(Endpoint).order_by(Endpoint.id).all()
        data = [_endpoint_to_dto(session, e) for e in endpoints]
    log_info(f"listed {len(data)} endpoint(s)", source=LOG_SOURCE)
    return {"object": "list", "data": data}


@router.post("/api/endpoints", status_code=201)
def create_endpoint(req: EndpointCreate) -> dict:
    if req.token_saver is not None and req.token_saver not in TOKEN_SAVER_MODES:
        return _bad_request(
            f"invalid token_saver: '{req.token_saver}' "
            f"(must be one of {TOKEN_SAVER_MODES})",
            "invalid_token_saver",
        )
    endpoint = Endpoint(
        name=req.name,
        listen_host=req.listen_host or "127.0.0.1",
        listen_port=req.listen_port or 8000,
        access_control_enabled=bool(req.access_control_enabled),
        internal_api_key=req.internal_api_key or "",
        proxy_pool_id=req.proxy_pool_id,
        token_saver=(req.token_saver or "off"),
    )
    with SessionLocal() as session:
        session.add(endpoint)
        session.commit()
        session.refresh(endpoint)
        eid = endpoint.id
        if req.binding is not None:
            _replace_binding(
                session, eid, req.binding.bind_type, req.binding.bind_id
            )
        session.commit()
        dto = _endpoint_to_dto(session, session.get(Endpoint, eid))
    log_info(
        f"created endpoint {eid} ('{req.name}', "
        f"proxy_pool_id={req.proxy_pool_id}, binding={req.binding is not None})",
        source=LOG_SOURCE,
    )
    return dto


@router.get("/api/endpoints/{endpoint_id}")
def get_endpoint(endpoint_id: int) -> dict:
    with SessionLocal() as session:
        endpoint = session.get(Endpoint, endpoint_id)
        if endpoint is None:
            log_warning(
                f"get_endpoint: endpoint {endpoint_id} not found", source=LOG_SOURCE
            )
            return _not_found(
                f"endpoint {endpoint_id} not found", "endpoint_not_found"
            )
        dto = _endpoint_to_dto(session, endpoint)
    log_info(f"fetched endpoint {endpoint_id}", source=LOG_SOURCE)
    return dto


@router.put("/api/endpoints/{endpoint_id}")
def update_endpoint(endpoint_id: int, req: EndpointUpdate) -> dict:
    with SessionLocal() as session:
        endpoint = session.get(Endpoint, endpoint_id)
        if endpoint is None:
            log_warning(
                f"update_endpoint: endpoint {endpoint_id} not found",
                source=LOG_SOURCE,
            )
            return _not_found(
                f"endpoint {endpoint_id} not found", "endpoint_not_found"
            )

        changed: List[str] = []
        if req.name is not None:
            endpoint.name = req.name
            changed.append("name")
        if req.listen_host is not None:
            endpoint.listen_host = req.listen_host
            changed.append("listen_host")
        if req.listen_port is not None:
            endpoint.listen_port = req.listen_port
            changed.append("listen_port")
        if req.access_control_enabled is not None:
            endpoint.access_control_enabled = bool(req.access_control_enabled)
            changed.append("access_control_enabled")
        if req.internal_api_key is not None:
            endpoint.internal_api_key = req.internal_api_key  # ADR-007 plaintext
            changed.append("internal_api_key")
        if req.proxy_pool_id is not None:
            endpoint.proxy_pool_id = req.proxy_pool_id
            changed.append("proxy_pool_id")
        if req.token_saver is not None:
            if req.token_saver not in TOKEN_SAVER_MODES:
                return _bad_request(
                    f"invalid token_saver: '{req.token_saver}' "
                    f"(must be one of {TOKEN_SAVER_MODES})",
                    "invalid_token_saver",
                )
            endpoint.token_saver = req.token_saver
            changed.append("token_saver")
        if req.binding is not None:
            # Replace the endpoint's single binding.
            _replace_binding(
                session, endpoint_id, req.binding.bind_type, req.binding.bind_id
            )
            changed.append("binding")

        session.commit()
        session.refresh(endpoint)
        dto = _endpoint_to_dto(session, endpoint)
    log_info(
        f"updated endpoint {endpoint_id}: {', '.join(changed) or 'no fields'}",
        source=LOG_SOURCE,
    )
    return dto


@router.delete("/api/endpoints/{endpoint_id}")
def delete_endpoint(endpoint_id: int) -> dict:
    with SessionLocal() as session:
        endpoint = session.get(Endpoint, endpoint_id)
        if endpoint is None:
            log_warning(
                f"delete_endpoint: endpoint {endpoint_id} not found",
                source=LOG_SOURCE,
            )
            return _not_found(
                f"endpoint {endpoint_id} not found", "endpoint_not_found"
            )
        # Cascade delete its EndpointBinding row(s).
        session.query(EndpointBinding).filter_by(endpoint_id=endpoint_id).delete()
        session.delete(endpoint)
        session.commit()
    log_info(
        f"deleted endpoint {endpoint_id} (cascaded binding)",
        source=LOG_SOURCE,
    )
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Optional convenience: explicit bind / unbind (only if trivial)
# --------------------------------------------------------------------------- #
@router.post("/api/endpoints/{endpoint_id}/bind", status_code=201)
def bind_endpoint(endpoint_id: int, req: BindingRef) -> dict:
    with SessionLocal() as session:
        endpoint = session.get(Endpoint, endpoint_id)
        if endpoint is None:
            log_warning(
                f"bind_endpoint: endpoint {endpoint_id} not found",
                source=LOG_SOURCE,
            )
            return _not_found(
                f"endpoint {endpoint_id} not found", "endpoint_not_found"
            )
        _replace_binding(session, endpoint_id, req.bind_type, req.bind_id)
        session.commit()
        session.refresh(endpoint)
        dto = _endpoint_to_dto(session, endpoint)
    log_info(
        f"bound endpoint {endpoint_id} -> {req.bind_type}:{req.bind_id}",
        source=LOG_SOURCE,
    )
    return dto


@router.delete("/api/endpoints/{endpoint_id}/bind")
def unbind_endpoint(endpoint_id: int) -> dict:
    with SessionLocal() as session:
        endpoint = session.get(Endpoint, endpoint_id)
        if endpoint is None:
            log_warning(
                f"unbind_endpoint: endpoint {endpoint_id} not found",
                source=LOG_SOURCE,
            )
            return _not_found(
                f"endpoint {endpoint_id} not found", "endpoint_not_found"
            )
        deleted = (
            session.query(EndpointBinding)
            .filter_by(endpoint_id=endpoint_id)
            .delete()
        )
        session.commit()
    log_info(
        f"unbound endpoint {endpoint_id} ({deleted} binding row(s) removed)",
        source=LOG_SOURCE,
    )
    return {"ok": True}


__all__ = ["router"]

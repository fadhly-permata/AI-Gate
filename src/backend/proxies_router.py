"""Proxy Pools CRUD + node management + health check (task B2.3).

Backend-only implementation of the ``/api/proxy-pools`` contract pinned by PM.

ADR-007: ``username``/``password`` stored + returned **plaintext** (no
encryption/masking) — matching ERD.md data dictionary.
ADR-011 / R12: every method logs to ``LogEntry`` via ``backend.log``; no
``except: pass`` — per-node health failures are caught, logged, and recorded as
``dead`` rather than aborting the batch or 500'ing.
Pydantic **v1** only (rule R10): ``BaseModel`` + ``class Config``.
"""

from __future__ import annotations

import socket
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config.db import SessionLocal
from backend.log import log_info, log_warning
from backend.models import ProxyNode, ProxyPool
from backend.proxy_selector import build_proxy_url

LOG_SOURCE = "backend.proxies.router"

_HEALTH_TIMEOUT = 5.0  # seconds, per the task contract

router = APIRouter()


# --------------------------------------------------------------------------- #
# Pydantic v1 DTOs / request bodies
# --------------------------------------------------------------------------- #
class ProxyPoolCreate(BaseModel):
    name: str
    rotation_strategy: Optional[str] = "round_robin"
    enabled: Optional[bool] = True

    class Config:
        pass


class ProxyPoolUpdate(BaseModel):
    name: Optional[str] = None
    rotation_strategy: Optional[str] = None
    enabled: Optional[bool] = None

    class Config:
        pass


class NodeCreate(BaseModel):
    host: str
    port: int
    protocol: Optional[str] = "http"
    username: Optional[str] = ""
    password: Optional[str] = ""

    class Config:
        pass


class NodeUpdate(BaseModel):
    host: Optional[str] = None
    port: Optional[int] = None
    protocol: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    status: Optional[str] = None

    class Config:
        pass


class NodeDTO(BaseModel):
    id: int
    pool_id: int
    host: str
    port: int
    protocol: str
    username: str
    password: str
    status: str
    last_latency_ms: float
    uptime_pct: float
    last_checked: Optional[str]

    class Config:
        pass


class ProxyPoolDTO(BaseModel):
    id: int
    name: str
    rotation_strategy: str
    enabled: bool
    last_used_index: int
    nodes: List[NodeDTO]

    class Config:
        pass


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _node_to_dto(node: ProxyNode) -> NodeDTO:
    checked = node.last_checked
    checked_iso = (
        checked.isoformat() if isinstance(checked, datetime) else None
    )
    return NodeDTO(
        id=node.id,
        pool_id=node.pool_id,
        host=node.host,
        port=node.port,
        protocol=node.protocol or "http",
        username=node.username,  # ADR-007: plaintext
        password=node.password,  # ADR-007: plaintext
        status=node.status,
        last_latency_ms=node.last_latency_ms,
        uptime_pct=node.uptime_pct,
        last_checked=checked_iso,
    )


def _pool_to_dto(session: Session, pool: ProxyPool) -> ProxyPoolDTO:
    nodes = (
        session.query(ProxyNode).filter_by(pool_id=pool.id).order_by(ProxyNode.id).all()
    )
    return ProxyPoolDTO(
        id=pool.id,
        name=pool.name,
        rotation_strategy=pool.rotation_strategy,
        enabled=bool(pool.enabled),
        last_used_index=pool.last_used_index,
        nodes=[_node_to_dto(n) for n in nodes],
    )


def _not_found(message: str, code: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"error": {"message": message, "type": "not_found", "code": code}},
    )


def _check_node_liveness(node: ProxyNode) -> tuple[str, float]:
    """TCP liveness probe to ``(host, port)``. Returns ``(status, latency_ms)``.

    ``healthy`` on success (latency measured in ms); ``dead`` on any failure with
    ``latency_ms == 0.0``. A successful TCP connect to the proxy port is the
    liveness proof (SOCKS5/HTTPS full tunnel test is out of scope for B2.3).
    """
    start = datetime.now()
    try:
        with socket.create_connection((node.host, node.port), timeout=_HEALTH_TIMEOUT):
            elapsed_ms = (datetime.now() - start).total_seconds() * 1000.0
            return "healthy", round(elapsed_ms, 3)
    except Exception as exc:  # noqa: BLE001 - per-node; recorded as dead
        log_warning(
            f"health-check: node {node.id} ({node.host}:{node.port}) "
            f"unreachable: {exc}",
            source=LOG_SOURCE,
        )
        return "dead", 0.0


# --------------------------------------------------------------------------- #
# Routes: ProxyPool CRUD
# --------------------------------------------------------------------------- #
@router.get("/api/proxy-pools")
def list_proxy_pools() -> dict:
    with SessionLocal() as session:
        pools = session.query(ProxyPool).order_by(ProxyPool.id).all()
        data = [_pool_to_dto(session, p).dict() for p in pools]
    log_info(f"listed {len(data)} proxy pool(s)", source=LOG_SOURCE)
    return {"object": "list", "data": data}


@router.post("/api/proxy-pools", status_code=201)
def create_proxy_pool(req: ProxyPoolCreate) -> dict:
    pool = ProxyPool(
        name=req.name,
        rotation_strategy=req.rotation_strategy or "round_robin",
        enabled=bool(req.enabled),
    )
    with SessionLocal() as session:
        session.add(pool)
        session.commit()
        session.refresh(pool)
        dto = _pool_to_dto(session, pool).dict()
    log_info(
        f"created proxy pool {pool.id} ({req.name}, "
        f"strategy={pool.rotation_strategy})",
        source=LOG_SOURCE,
    )
    return dto


@router.get("/api/proxy-pools/{pool_id}")
def get_proxy_pool(pool_id: int) -> dict:
    with SessionLocal() as session:
        pool = session.get(ProxyPool, pool_id)
        if pool is None:
            log_warning(
                f"get_proxy_pool: pool {pool_id} not found", source=LOG_SOURCE
            )
            return _not_found(f"proxy pool {pool_id} not found", "proxy_pool_not_found")
        dto = _pool_to_dto(session, pool).dict()
    log_info(f"fetched proxy pool {pool_id}", source=LOG_SOURCE)
    return dto


@router.put("/api/proxy-pools/{pool_id}")
def update_proxy_pool(pool_id: int, req: ProxyPoolUpdate) -> dict:
    with SessionLocal() as session:
        pool = session.get(ProxyPool, pool_id)
        if pool is None:
            log_warning(
                f"update_proxy_pool: pool {pool_id} not found", source=LOG_SOURCE
            )
            return _not_found(f"proxy pool {pool_id} not found", "proxy_pool_not_found")

        changed: List[str] = []
        if req.name is not None:
            pool.name = req.name
            changed.append("name")
        if req.rotation_strategy is not None:
            pool.rotation_strategy = req.rotation_strategy
            changed.append("rotation_strategy")
        if req.enabled is not None:
            pool.enabled = bool(req.enabled)
            changed.append("enabled")

        session.commit()
        session.refresh(pool)
        dto = _pool_to_dto(session, pool).dict()
    log_info(
        f"updated proxy pool {pool_id}: {', '.join(changed) or 'no fields'}",
        source=LOG_SOURCE,
    )
    return dto


@router.delete("/api/proxy-pools/{pool_id}")
def delete_proxy_pool(pool_id: int) -> dict:
    with SessionLocal() as session:
        pool = session.get(ProxyPool, pool_id)
        if pool is None:
            log_warning(
                f"delete_proxy_pool: pool {pool_id} not found", source=LOG_SOURCE
            )
            return _not_found(f"proxy pool {pool_id} not found", "proxy_pool_not_found")
        # Cascade: delete all nodes in the pool.
        session.query(ProxyNode).filter_by(pool_id=pool_id).delete()
        session.delete(pool)
        session.commit()
    log_info(f"deleted proxy pool {pool_id} (cascaded nodes)", source=LOG_SOURCE)
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Routes: Node CRUD under a pool
# --------------------------------------------------------------------------- #
@router.get("/api/proxy-pools/{pool_id}/nodes")
def list_nodes(pool_id: int) -> dict:
    with SessionLocal() as session:
        pool = session.get(ProxyPool, pool_id)
        if pool is None:
            log_warning(f"list_nodes: pool {pool_id} not found", source=LOG_SOURCE)
            return _not_found(f"proxy pool {pool_id} not found", "proxy_pool_not_found")
        nodes = (
            session.query(ProxyNode)
            .filter_by(pool_id=pool_id)
            .order_by(ProxyNode.id)
            .all()
        )
        data = [_node_to_dto(n).dict() for n in nodes]
    log_info(
        f"listed {len(data)} node(s) for pool {pool_id}", source=LOG_SOURCE
    )
    return {"object": "list", "data": data}


@router.post("/api/proxy-pools/{pool_id}/nodes", status_code=201)
def create_node(pool_id: int, req: NodeCreate) -> dict:
    with SessionLocal() as session:
        pool = session.get(ProxyPool, pool_id)
        if pool is None:
            log_warning(f"create_node: pool {pool_id} not found", source=LOG_SOURCE)
            return _not_found(f"proxy pool {pool_id} not found", "proxy_pool_not_found")
        node = ProxyNode(
            pool_id=pool_id,
            host=req.host,
            port=req.port,
            protocol=req.protocol or "http",
            username=req.username or "",
            password=req.password or "",
        )
        session.add(node)
        session.commit()
        session.refresh(node)
        dto = _node_to_dto(node).dict()
    log_info(
        f"created node {node.id} in pool {pool_id} "
        f"({req.host}:{req.port}, {node.protocol})",
        source=LOG_SOURCE,
    )
    return dto


@router.put("/api/proxy-pools/{pool_id}/nodes/{node_id}")
def update_node(pool_id: int, node_id: int, req: NodeUpdate) -> dict:
    with SessionLocal() as session:
        node = session.get(ProxyNode, node_id)
        if node is None or node.pool_id != pool_id:
            log_warning(
                f"update_node: node {node_id} not found in pool {pool_id}",
                source=LOG_SOURCE,
            )
            return _not_found(
                f"node {node_id} not found in pool {pool_id}",
                "proxy_node_not_found",
            )

        changed: List[str] = []
        if req.host is not None:
            node.host = req.host
            changed.append("host")
        if req.port is not None:
            node.port = req.port
            changed.append("port")
        if req.protocol is not None:
            node.protocol = req.protocol
            changed.append("protocol")
        if req.username is not None:
            node.username = req.username  # ADR-007: plaintext
            changed.append("username")
        if req.password is not None:
            node.password = req.password  # ADR-007: plaintext
            changed.append("password")
        if req.status is not None:
            node.status = req.status
            changed.append("status")

        session.commit()
        session.refresh(node)
        dto = _node_to_dto(node).dict()
    log_info(
        f"updated node {node_id} in pool {pool_id}: "
        f"{', '.join(changed) or 'no fields'}",
        source=LOG_SOURCE,
    )
    return dto


@router.delete("/api/proxy-pools/{pool_id}/nodes/{node_id}")
def delete_node(pool_id: int, node_id: int) -> dict:
    with SessionLocal() as session:
        node = session.get(ProxyNode, node_id)
        if node is None or node.pool_id != pool_id:
            log_warning(
                f"delete_node: node {node_id} not found in pool {pool_id}",
                source=LOG_SOURCE,
            )
            return _not_found(
                f"node {node_id} not found in pool {pool_id}",
                "proxy_node_not_found",
            )
        session.delete(node)
        session.commit()
    log_info(f"deleted node {node_id} from pool {pool_id}", source=LOG_SOURCE)
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Health check
# --------------------------------------------------------------------------- #
@router.post("/api/proxy-pools/{pool_id}/health-check")
def health_check(pool_id: int) -> dict:
    with SessionLocal() as session:
        pool = session.get(ProxyPool, pool_id)
        if pool is None:
            log_warning(
                f"health_check: pool {pool_id} not found", source=LOG_SOURCE
            )
            return _not_found(f"proxy pool {pool_id} not found", "proxy_pool_not_found")

        nodes = (
            session.query(ProxyNode)
            .filter_by(pool_id=pool_id)
            .order_by(ProxyNode.id)
            .all()
        )
        results: List[dict] = []
        healthy = 0
        for node in nodes:
            status, latency = _check_node_liveness(node)
            node.status = status
            node.last_latency_ms = latency
            node.uptime_pct = 100.0 if status == "healthy" else 0.0
            node.last_checked = datetime.now(timezone.utc)
            results.append(
                {"node_id": node.id, "status": status, "latency_ms": latency}
            )
            if status == "healthy":
                healthy += 1
        session.commit()

    log_info(
        f"health-check pool {pool_id}: {healthy}/{len(results)} healthy",
        source=LOG_SOURCE,
    )
    return {"ok": True, "results": results}


__all__ = ["router", "build_proxy_url"]

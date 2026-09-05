"""Combo CRUD API (task B2.4).

Backend-only implementation of the ``/api/combos`` contract pinned by PM.

ADR-011 / R12: every method logs to ``LogEntry`` via ``backend.log``; no
swallowed exceptions. 404s return the OpenAI-style error envelope
``{"error": {"message", "type": "not_found", "code"}}``.

Pydantic **v1** only (rule R10): ``BaseModel`` + ``class Config``.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config.db import SessionLocal
from backend.log import log_info, log_warning
from backend.models import Combo, ComboMember

LOG_SOURCE = "backend.combos.router"

# Allowed combo strategies (FSD.md 2.3). ``three_tier`` adds the 3-tier
# fallback ordering (subscription -> cheap -> free) on top of sequential
# fallback semantics (B5.2).
ALLOWED_STRATEGIES = frozenset(
    {"fallback", "load_balance", "latency_cost", "three_tier"}
)

router = APIRouter()


# --------------------------------------------------------------------------- #
# Pydantic v1 DTOs / request bodies
# --------------------------------------------------------------------------- #
class ComboMemberCreate(BaseModel):
    provider_id: int
    provider_model: Optional[str] = ""
    priority: Optional[int] = 0
    weight: Optional[float] = 1.0

    class Config:
        pass


class ComboCreate(BaseModel):
    name: str
    strategy: Optional[str] = "fallback"
    enabled: Optional[bool] = True
    members: Optional[List[ComboMemberCreate]] = None

    class Config:
        pass


class ComboUpdate(BaseModel):
    name: Optional[str] = None
    strategy: Optional[str] = None
    enabled: Optional[bool] = None

    class Config:
        pass


class ComboMemberUpdate(BaseModel):
    provider_id: Optional[int] = None
    provider_model: Optional[str] = None
    priority: Optional[int] = None
    weight: Optional[float] = None

    class Config:
        pass


class ComboMemberDTO(BaseModel):
    id: int
    combo_id: int
    provider_id: int
    provider_model: str
    priority: int
    weight: float

    class Config:
        pass


class ComboDTO(BaseModel):
    id: int
    name: str
    strategy: str
    enabled: bool
    members: List[ComboMemberDTO]

    class Config:
        pass


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _member_to_dto(member: ComboMember) -> ComboMemberDTO:
    return ComboMemberDTO(
        id=member.id,
        combo_id=member.combo_id,
        provider_id=member.provider_id,
        provider_model=member.provider_model or "",
        priority=member.priority,
        weight=member.weight,
    )


def _combo_to_dto(combo: Combo) -> ComboDTO:
    members = sorted(combo.members, key=lambda m: m.priority)
    return ComboDTO(
        id=combo.id,
        name=combo.name,
        strategy=combo.strategy,
        enabled=bool(combo.enabled),
        members=[_member_to_dto(m) for m in members],
    )


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


# --------------------------------------------------------------------------- #
# Routes: Combo CRUD
# --------------------------------------------------------------------------- #
@router.get("/api/combos")
def list_combos() -> dict:
    with SessionLocal() as session:
        combos = session.query(Combo).order_by(Combo.id).all()
        data = [_combo_to_dto(c).dict() for c in combos]
    log_info(f"listed {len(data)} combo(s)", source=LOG_SOURCE)
    return {"object": "list", "data": data}


@router.post("/api/combos", status_code=201)
def create_combo(req: ComboCreate) -> dict:
    strategy = req.strategy or "fallback"
    if strategy not in ALLOWED_STRATEGIES:
        log_warning(
            f"create_combo: invalid strategy '{strategy}'",
            source=LOG_SOURCE,
        )
        return _bad_request(
            f"invalid strategy '{strategy}' (expected one of "
            f"{sorted(ALLOWED_STRATEGIES)})",
            "invalid_strategy",
        )

    combo = Combo(name=req.name, strategy=strategy, enabled=bool(req.enabled))
    with SessionLocal() as session:
        session.add(combo)
        session.commit()
        session.refresh(combo)
        if req.members:
            for m in req.members:
                session.add(
                    ComboMember(
                        combo_id=combo.id,
                        provider_id=m.provider_id,
                        provider_model=m.provider_model or "",
                        priority=m.priority or 0,
                        weight=m.weight if m.weight is not None else 1.0,
                    )
                )
            session.commit()
        dto = _combo_to_dto(session.get(Combo, combo.id)).dict()
    log_info(
        f"created combo {combo.id} ('{req.name}', strategy={strategy}, "
        f"members={len(req.members or [])})",
        source=LOG_SOURCE,
    )
    return dto


@router.get("/api/combos/{combo_id}")
def get_combo(combo_id: int) -> dict:
    with SessionLocal() as session:
        combo = session.get(Combo, combo_id)
        if combo is None:
            log_warning(f"get_combo: combo {combo_id} not found", source=LOG_SOURCE)
            return _not_found(f"combo {combo_id} not found", "combo_not_found")
        dto = _combo_to_dto(combo).dict()
    log_info(f"fetched combo {combo_id}", source=LOG_SOURCE)
    return dto


@router.put("/api/combos/{combo_id}")
def update_combo(combo_id: int, req: ComboUpdate) -> dict:
    with SessionLocal() as session:
        combo = session.get(Combo, combo_id)
        if combo is None:
            log_warning(
                f"update_combo: combo {combo_id} not found", source=LOG_SOURCE
            )
            return _not_found(f"combo {combo_id} not found", "combo_not_found")

        changed: List[str] = []
        if req.name is not None:
            combo.name = req.name
            changed.append("name")
        if req.strategy is not None:
            if req.strategy not in ALLOWED_STRATEGIES:
                log_warning(
                    f"update_combo: invalid strategy '{req.strategy}'",
                    source=LOG_SOURCE,
                )
                return _bad_request(
                    f"invalid strategy '{req.strategy}' (expected one of "
                    f"{sorted(ALLOWED_STRATEGIES)})",
                    "invalid_strategy",
                )
            combo.strategy = req.strategy
            changed.append("strategy")
        if req.enabled is not None:
            combo.enabled = bool(req.enabled)
            changed.append("enabled")

        session.commit()
        session.refresh(combo)
        dto = _combo_to_dto(combo).dict()
    log_info(
        f"updated combo {combo_id}: {', '.join(changed) or 'no fields'}",
        source=LOG_SOURCE,
    )
    return dto


@router.delete("/api/combos/{combo_id}")
def delete_combo(combo_id: int) -> dict:
    with SessionLocal() as session:
        combo = session.get(Combo, combo_id)
        if combo is None:
            log_warning(
                f"delete_combo: combo {combo_id} not found", source=LOG_SOURCE
            )
            return _not_found(f"combo {combo_id} not found", "combo_not_found")
        # Cascade delete members.
        session.query(ComboMember).filter_by(combo_id=combo_id).delete()
        session.delete(combo)
        session.commit()
    log_info(
        f"deleted combo {combo_id} (cascaded members)", source=LOG_SOURCE
    )
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Routes: ComboMember CRUD under a combo
# --------------------------------------------------------------------------- #
@router.post("/api/combos/{combo_id}/members", status_code=201)
def create_member(combo_id: int, req: ComboMemberCreate) -> dict:
    with SessionLocal() as session:
        combo = session.get(Combo, combo_id)
        if combo is None:
            log_warning(
                f"create_member: combo {combo_id} not found", source=LOG_SOURCE
            )
            return _not_found(f"combo {combo_id} not found", "combo_not_found")
        member = ComboMember(
            combo_id=combo_id,
            provider_id=req.provider_id,
            provider_model=req.provider_model or "",
            priority=req.priority or 0,
            weight=req.weight if req.weight is not None else 1.0,
        )
        session.add(member)
        session.commit()
        session.refresh(member)
        dto = _member_to_dto(member).dict()
    log_info(
        f"created member {member.id} in combo {combo_id} "
        f"(provider={req.provider_id}, priority={member.priority})",
        source=LOG_SOURCE,
    )
    return dto


@router.put("/api/combos/{combo_id}/members/{member_id}")
def update_member(combo_id: int, member_id: int, req: ComboMemberUpdate) -> dict:
    with SessionLocal() as session:
        member = session.get(ComboMember, member_id)
        if member is None or member.combo_id != combo_id:
            log_warning(
                f"update_member: member {member_id} not found in combo {combo_id}",
                source=LOG_SOURCE,
            )
            return _not_found(
                f"member {member_id} not found in combo {combo_id}",
                "combo_member_not_found",
            )

        changed: List[str] = []
        if req.provider_id is not None:
            member.provider_id = req.provider_id
            changed.append("provider_id")
        if req.provider_model is not None:
            member.provider_model = req.provider_model
            changed.append("provider_model")
        if req.priority is not None:
            member.priority = req.priority
            changed.append("priority")
        if req.weight is not None:
            member.weight = req.weight
            changed.append("weight")

        session.commit()
        session.refresh(member)
        dto = _member_to_dto(member).dict()
    log_info(
        f"updated member {member_id} in combo {combo_id}: "
        f"{', '.join(changed) or 'no fields'}",
        source=LOG_SOURCE,
    )
    return dto


@router.delete("/api/combos/{combo_id}/members/{member_id}")
def delete_member(combo_id: int, member_id: int) -> dict:
    with SessionLocal() as session:
        member = session.get(ComboMember, member_id)
        if member is None or member.combo_id != combo_id:
            log_warning(
                f"delete_member: member {member_id} not found in combo {combo_id}",
                source=LOG_SOURCE,
            )
            return _not_found(
                f"member {member_id} not found in combo {combo_id}",
                "combo_member_not_found",
            )
        session.delete(member)
        session.commit()
    log_info(
        f"deleted member {member_id} from combo {combo_id}", source=LOG_SOURCE
    )
    return {"ok": True}


__all__ = ["router"]

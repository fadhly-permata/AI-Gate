"""Multi-account + OAuth management API (Backlog B5.1).

Endpoints:

* ``GET  /api/accounts?provider_id=`` — list a provider's accounts.
* ``POST /api/accounts``             — create an account (api_key | oauth).
* ``DELETE /api/accounts/{id}``     — delete an account.
* ``POST /api/oauth/<provider>/start``    — begin OAuth flow; return authorize URL.
* ``GET  /api/oauth/<provider>/callback`` — exchange code -> store token.

ADR-007: ``api_key`` / ``oauth_token`` / ``refresh_token`` returned in
**plaintext** — no encryption, no masking, no hashing. The UI (fe-dev) renders
them verbatim.

Rule R12 / ADR-011: every failure logs to ``LogEntry`` via ``backend.log``. No
``except: pass`` — OAuth exchange failures log the stacktrace and return an
``{ok:false, error}`` envelope, never a swallowed 500.

Pydantic **v1** only (rule R10): ``BaseModel`` + ``class Config``, no v2 syntax.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

import httpx

from backend.config.db import SessionLocal
from backend.log import log_error_exc, log_info
from backend.models import Provider, ProviderAccount
from backend.oauth import OAUTH_REGISTRY, OAUTH_STATES, REDIRECT_BASE

LOG_SOURCE = "backend.accounts.router"

router = APIRouter()


# --------------------------------------------------------------------------- #
# Pydantic v1 DTOs
# --------------------------------------------------------------------------- #
class AccountCreate(BaseModel):
    provider_id: int
    label: str
    auth_type: str  # 'api_key' | 'oauth'
    api_key: Optional[str] = ""
    oauth_token: Optional[str] = ""
    refresh_token: Optional[str] = ""
    expires_at: Optional[str] = None  # ISO-8601 string
    enabled: Optional[bool] = True

    class Config:
        pass


class AccountDTO(BaseModel):
    id: int
    provider_id: int
    label: str
    auth_type: str
    api_key: str  # ADR-007: plaintext in/out
    has_oauth_token: bool
    expires_at: Optional[str]  # ISO-8601 string or null
    enabled: bool

    class Config:
        pass


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 datetime string (tolerant of trailing 'Z')."""
    if not value:
        return None
    try:
        v = value.strip()
        if v.endswith("Z"):
            v = v[:-1] + "+00:00"
        dt = datetime.fromisoformat(v)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:  # noqa: BLE001 - bad input -> None, never crash
        return None


def _dt_to_iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.isoformat()


def _account_to_dto(account: ProviderAccount) -> AccountDTO:
    return AccountDTO(
        id=account.id,
        provider_id=account.provider_id,
        label=account.label,
        auth_type=account.auth_type,
        api_key=account.api_key,  # ADR-007: plaintext
        has_oauth_token=bool(account.oauth_token),
        expires_at=_dt_to_iso(account.expires_at),
        enabled=bool(account.enabled),
    )


def _resolve_provider(session: Session, identifier: str) -> Optional[Provider]:
    """Look up a provider by integer id OR by ``name``.

    ``<provider>`` in the OAuth routes may be either the numeric provider id or
    its name. Returns ``None`` when nothing matches.
    """
    # Try integer id first (no risky parse exception; names are non-numeric).
    if identifier.isdigit():
        provider = session.get(Provider, int(identifier))
        if provider is not None:
            return provider
    return session.query(Provider).filter(Provider.name == identifier).first()


def _error(status: int, message: str, code: str, etype: str = "not_found"):
    return JSONResponse(
        status_code=status,
        content={"error": {"message": message, "type": etype, "code": code}},
    )


def _pkce_challenge() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) for PKCE (plain method).

    Uses the ``plain`` challenge method (verifier == challenge) to avoid any
    hashing dependency in the backend (the app must not import crypto libs that
    could be mistaken for secret encryption; ADR-007 stores tokens in plaintext
    and we do not encrypt them). Acceptable for a local single-user gateway.
    """
    verifier = secrets.token_urlsafe(64)
    return verifier, verifier


# --------------------------------------------------------------------------- #
# Account CRUD
# --------------------------------------------------------------------------- #
@router.get("/api/accounts")
def list_accounts(provider_id: Optional[str] = Query(None)) -> Any:
    """List accounts for a provider. ``provider_id`` required (int).

    Missing / non-integer ``provider_id`` -> 400 envelope. Provider not found ->
    404 envelope.
    """
    if provider_id is None or provider_id == "":
        return _error(
            400, "provider_id is required", "missing_provider_id", "invalid_request_error"
        )
    try:
        pid = int(provider_id)
    except (ValueError, TypeError):
        return _error(
            400,
            "provider_id must be an integer",
            "invalid_provider_id",
            "invalid_request_error",
        )

    with SessionLocal() as session:
        provider = session.get(Provider, pid)
        if provider is None:
            return _error(404, f"provider {pid} not found", "provider_not_found")
        rows = (
            session.query(ProviderAccount)
            .filter_by(provider_id=pid)
            .order_by(ProviderAccount.id.asc())
            .all()
        )
        data = [_account_to_dto(a).dict() for a in rows]
    log_info(f"listed {len(data)} account(s) for provider {pid}", source=LOG_SOURCE)
    return {"object": "list", "data": data}


@router.post("/api/accounts", status_code=201)
def create_account(req: AccountCreate) -> Any:
    """Create a ProviderAccount (api_key or oauth)."""
    if req.auth_type not in ("api_key", "oauth"):
        return _error(
            400,
            "auth_type must be 'api_key' or 'oauth'",
            "invalid_auth_type",
            "invalid_request_error",
        )

    with SessionLocal() as session:
        provider = session.get(Provider, req.provider_id)
        if provider is None:
            return _error(
                404, f"provider {req.provider_id} not found", "provider_not_found"
            )
        account = ProviderAccount(
            provider_id=req.provider_id,
            label=req.label,
            auth_type=req.auth_type,
            api_key=req.api_key or "",
            oauth_token=req.oauth_token or "",
            refresh_token=req.refresh_token or "",
            expires_at=_parse_dt(req.expires_at),
            enabled=bool(req.enabled),
        )
        session.add(account)
        session.commit()
        session.refresh(account)
        dto = _account_to_dto(account).dict()
    log_info(
        f"created account {account.id} for provider {req.provider_id} "
        f"(auth_type={req.auth_type})",
        source=LOG_SOURCE,
    )
    return dto


@router.delete("/api/accounts/{account_id}")
def delete_account(account_id: int) -> Any:
    """Delete a ProviderAccount. 404 if missing."""
    with SessionLocal() as session:
        account = session.get(ProviderAccount, account_id)
        if account is None:
            return _error(404, f"account {account_id} not found", "account_not_found")
        session.delete(account)
        session.commit()
    log_info(f"deleted account {account_id}", source=LOG_SOURCE)
    return {"ok": True}


# --------------------------------------------------------------------------- #
# OAuth flow
# --------------------------------------------------------------------------- #
@router.post("/api/oauth/{provider}/start")
async def oauth_start(provider: str) -> Any:
    """Begin an OAuth flow for a provider (id or name).

    Looks up the provider, reads its OAuth config from ``OAUTH_REGISTRY`` keyed
    by provider ``type``. Builds an authorize URL with ``redirect_uri`` pointing
    at this app's local callback, a random ``state`` (stored in-memory keyed by
    state -> provider id), the configured ``scope`` and ``client_id``. PKCE
    providers also get a ``code_challenge``.

    Returns ``{authorize_url, state}``. Unknown provider type -> 400
    ``oauth_not_configured``. Provider not found -> 404.
    """
    with SessionLocal() as session:
        prov = _resolve_provider(session, provider)
        if prov is None:
            return _error(404, f"provider '{provider}' not found", "provider_not_found")
        cfg = OAUTH_REGISTRY.get((prov.type or "").lower())
        if not cfg:
            return _error(
                400,
                f"provider type '{prov.type}' has no OAuth configuration",
                "oauth_not_configured",
                "invalid_request_error",
            )

        state = secrets.token_urlsafe(24)
        redirect_uri = f"{REDIRECT_BASE}/api/oauth/{provider}/callback"

        params: Dict[str, Any] = {
            "client_id": cfg.get("client_id", ""),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(cfg.get("scopes", [])),
            "state": state,
        }
        entry: Dict[str, Any] = {"provider_id": prov.id}
        if cfg.get("pkce"):
            verifier, challenge = _pkce_challenge()
            params["code_challenge"] = challenge
            params["code_challenge_method"] = "plain"
            entry["code_verifier"] = verifier
        OAUTH_STATES[state] = entry

        auth_url = f"{cfg['auth_url']}?{urlencode(params)}"

    log_info(
        f"oauth start for provider '{provider}' (type={prov.type})",
        source=LOG_SOURCE,
        context={"provider_id": prov.id, "state": state},
    )
    return {"authorize_url": auth_url, "state": state}


@router.get("/api/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str = Query(...),
    state: str = Query(...),
) -> Any:
    """OAuth redirect target. Exchanges ``code`` for tokens and stores them.

    Validates ``state``, POSTs the authorization code to the registry
    ``token_url`` (``grant_type=authorization_code``), parses
    ``access_token`` / ``refresh_token`` / ``expires_in``, and creates a
    ``ProviderAccount`` (auth_type='oauth') with the token + ``expires_at``.

    On failure: ``log_error_exc`` + return ``{ok:false, error}`` (never swallow).
    """
    entry = OAUTH_STATES.pop(state, None)
    if entry is None:
        log_error_exc(
            "oauth callback: invalid/missing state",
            source=LOG_SOURCE,
            context={"provider": provider, "state": state},
        )
        return JSONResponse(
            400, {"ok": False, "error": "invalid or expired oauth state"}
        )

    with SessionLocal() as session:
        prov = session.get(Provider, entry["provider_id"])
        if prov is None:
            return JSONResponse(
                404, {"ok": False, "error": "provider not found"}
            )
        provider_id = prov.id
        cfg = OAUTH_REGISTRY.get((prov.type or "").lower())
        if not cfg:
            return JSONResponse(
                400,
                {"ok": False, "error": "oauth_not_configured"},
            )

        data: Dict[str, Any] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": f"{REDIRECT_BASE}/api/oauth/{provider}/callback",
            "client_id": cfg.get("client_id", ""),
        }
        if cfg.get("client_secret"):
            data["client_secret"] = cfg["client_secret"]
        if entry.get("code_verifier"):
            data["code_verifier"] = entry["code_verifier"]

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(cfg["token_url"], data=data)
                resp.raise_for_status()
                body = resp.json()
        except Exception as exc:  # noqa: BLE001 - must log + surface, not swallow
            log_error_exc(
                "oauth callback token exchange failed",
                source=LOG_SOURCE,
                exc=exc,
                context={"provider": provider, "provider_type": prov.type},
            )
            return JSONResponse(
                502, {"ok": False, "error": "token_exchange_failed"}
            )

        access_token = body.get("access_token", "")
        refresh_token = body.get("refresh_token", "")
        expires_in = body.get("expires_in")
        expires_at = (
            datetime.utcnow() + timedelta(seconds=int(expires_in))
            if expires_in
            else None
        )
        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        account = ProviderAccount(
            provider_id=prov.id,
            label=f"{prov.name}-oauth-{ts}",
            auth_type="oauth",
            api_key="",
            oauth_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            enabled=True,
        )
        session.add(account)
        session.commit()
        session.refresh(account)
        created_id = account.id

    log_info(
        f"oauth account {created_id} created for provider {provider_id}",
        source=LOG_SOURCE,
        context={"provider_id": provider_id, "has_refresh": bool(refresh_token)},
    )
    return {"ok": True, "account_id": created_id}


__all__ = ["router"]

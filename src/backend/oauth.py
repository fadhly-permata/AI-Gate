"""OAuth registry + token management (Backlog B5.1).

Implements ADR-013 (OAuth Auto-Refresh): ``ProviderAccount.auth_type='oauth'``
stores ``oauth_token`` + ``refresh_token`` + ``expires_at``; before a request the
system refreshes the token automatically when it is near expiry (no manual
re-login). Multi-account selection (strategy-driven choice among a provider's
enabled accounts) is also provided here so the gateway can pick an account
credential instead of the legacy ``provider.api_key``.

Provider-account routing (adopted from 9router ``src/sse/services/auth.js``):

* ``fill-first`` (default) — the highest-priority available account wins
  (``priority`` asc, ``id`` asc tie-break); unusable accounts are skipped.
* ``round-robin`` — STICKY: the same account is returned for
  ``sticky_round_robin_limit`` consecutive calls (default 3) before advancing
  to the least-recently-used one (``last_used_at`` asc, nulls first, id asc).
* pin bypass — a ``preferred_account_id`` (gateway header ``x-connection-id``)
  that belongs to the provider forces that account, skipping the strategy.

The consecutive-use counter is in-memory (single-process local app, same
trade-off as the cursor it replaced); ``last_used_at`` is persisted.

ADR-007: the OAuth registry ``client_id``/``client_secret`` are stored
**plaintext** (local app) — no encryption, no masking. This is acceptable for a
local single-user gateway; the values below are placeholders where the provider
does not publish a public/anonymous client id. Operators must substitute their
own OAuth app credentials (see RECEIPT / module docstring notes).

Rule R12 / ADR-011: every failure path logs to ``LogEntry`` via ``backend.log``.
No ``except: pass`` — token-exchange / refresh failures are logged with a
stacktrace and surfaced to the caller, never swallowed.

Pydantic not used (ORM-only module); keep it import-light.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from backend.log import log_error, log_error_exc, log_info, log_warning
from backend.models import Provider, ProviderAccount

LOG_SOURCE = "backend.oauth"


# --------------------------------------------------------------------------- #
# OAuth client registry — keyed by provider ``type``.
#
# NOTE ON client_id: where a provider publishes a public/client OAuth app id
# (e.g. GitHub Copilot CLI, Anthropic Claude) that id is used below. Where no
# public id exists, a clearly-marked placeholder is used and MUST be replaced by
# the operator with their own OAuth application credentials. This is a local app,
# so plaintext storage (ADR-007) is acceptable.
# --------------------------------------------------------------------------- #
OAUTH_REGISTRY: Dict[str, dict] = {
    "anthropic": {
        "auth_url": "https://claude.ai/oauth/authorize",
        "token_url": "https://api.anthropic.com/v1/oauth/token",
        # Public client id published by Anthropic for the Claude OAuth flow.
        "client_id": "9d1c250a-e61b-44d9-88ed-5944d1962f6e",
        "scopes": ["org.read", "user.read"],
        "pkce": True,
    },
    "claude": {
        # alias of 'anthropic' (same OAuth app)
        "auth_url": "https://claude.ai/oauth/authorize",
        "token_url": "https://api.anthropic.com/v1/oauth/token",
        "client_id": "9d1c250a-e61b-44d9-88ed-5944d1962f6e",
        "scopes": ["org.read", "user.read"],
        "pkce": True,
    },
    "openai": {
        "auth_url": "https://auth.openai.com/authorize",
        "token_url": "https://auth.openai.com/token",
        # PLACEHOLDER — replace with your OpenAI OAuth app client_id.
        "client_id": "REPLACE_WITH_OPENAI_CLIENT_ID",
        "scopes": ["model.request", "model.read"],
        "pkce": True,
    },
    "codex": {
        # Codex uses the OpenAI identity OAuth app.
        "auth_url": "https://auth.openai.com/authorize",
        "token_url": "https://auth.openai.com/token",
        "client_id": "REPLACE_WITH_OPENAI_CLIENT_ID",
        "scopes": ["model.request", "model.read"],
        "pkce": True,
    },
    "github": {
        "auth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        # Public OAuth app id for GitHub Copilot CLI.
        "client_id": "Iv1.b507a08c87ecfe98",
        "scopes": ["read:user", "copilot"],
        "pkce": False,
    },
    "copilot": {
        "auth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        # Public OAuth app id for GitHub Copilot CLI.
        "client_id": "Iv1.b507a08c87ecfe98",
        "scopes": ["read:user", "copilot"],
        "pkce": False,
    },
    "cursor": {
        "auth_url": "https://cursor.com/oauth/authorize",
        "token_url": "https://cursor.com/api/oauth/token",
        # PLACEHOLDER — replace with your Cursor OAuth app client_id.
        "client_id": "REPLACE_WITH_CURSOR_CLIENT_ID",
        "scopes": ["openid", "profile", "email"],
        "pkce": True,
    },
    "antigravity": {
        "auth_url": "https://aistudio.google.com/oauth/authorize",
        "token_url": "https://oauth2.googleapis.com/token",
        # PLACEHOLDER — replace with your Google OAuth client_id.
        "client_id": "REPLACE_WITH_ANTIGRAVITY_CLIENT_ID",
        "scopes": ["https://www.googleapis.com/auth/aistudio"],
        "pkce": True,
    },
}

# --------------------------------------------------------------------------- #
# Provider-account routing contract (9router account-level strategy set ONLY).
# Single source of truth for the enum + defaults; the DTOs and the engine both
# read these so the two can never drift.
# --------------------------------------------------------------------------- #
FILL_FIRST = "fill-first"
ROUND_ROBIN = "round-robin"
ROUTING_STRATEGIES: Tuple[str, ...] = (FILL_FIRST, ROUND_ROBIN)
DEFAULT_FALLBACK_STRATEGY = FILL_FIRST
DEFAULT_STICKY_ROUND_ROBIN_LIMIT = 3
MIN_STICKY_ROUND_ROBIN_LIMIT = 1
# Gateway request header that pins one account (bypasses the strategy).
CONNECTION_ID_HEADER = "x-connection-id"

# Sticky round-robin bookkeeping: provider.id -> (account_id, consecutive_uses).
# In-memory on purpose (single-process local app, like the cursor it replaced);
# ``ProviderAccount.last_used_at`` is the persisted half of the algorithm.
_STICKY: Dict[int, Tuple[int, int]] = {}

# In-memory map of OAuth state -> {provider_id, code_verifier?}. Keyed by the
# random ``state`` token; consumed (popped) on callback. Local app only.
OAUTH_STATES: Dict[str, dict] = {}

# The app's local OAuth redirect URI host:port (single process). The callback
# always lands back here.
REDIRECT_BASE = "http://127.0.0.1:8080"


def _provider_type(provider: Provider) -> str:
    return (provider.type or "").lower()


def get_valid_token(account: ProviderAccount, session: Session) -> str:
    """Return a usable credential for ``account`` (ADR-013 auto-refresh).

    * ``auth_type='api_key'`` -> the stored ``api_key`` (plaintext, ADR-007).
    * ``auth_type='oauth'``:
      - if ``oauth_token`` present and not near expiry (>= 60s slack) -> it.
      - elif ``refresh_token`` present -> POST refresh grant to the registry
        ``token_url``, persist new tokens + ``expires_at``, return new token.
      - else -> log_error + raise a clear ``RuntimeError`` (token unavailable).

    Failures are never swallowed: refresh/network errors are logged via
    ``log_error_exc`` and re-raised so the caller can surface them.
    """
    if account.auth_type == "api_key":
        return account.api_key or ""

    # OAuth path.
    now = datetime.utcnow()
    if account.oauth_token and (
        account.expires_at is None
        or account.expires_at > now + timedelta(seconds=60)
    ):
        return account.oauth_token

    provider_type = _provider_type(account.provider) if account.provider else ""
    if account.refresh_token and provider_type:
        cfg = OAUTH_REGISTRY.get(provider_type)
        if not cfg:
            log_error(
                "oauth auto-refresh unavailable: provider type not in registry",
                source=LOG_SOURCE,
                context={"provider_type": provider_type, "account_id": account.id},
            )
            raise RuntimeError(
                f"oauth token unavailable: provider type '{provider_type}' "
                f"not configured for OAuth"
            )
        data = {
            "grant_type": "refresh_token",
            "refresh_token": account.refresh_token,
            "client_id": cfg.get("client_id", ""),
        }
        if cfg.get("client_secret"):
            data["client_secret"] = cfg["client_secret"]
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(cfg["token_url"], data=data)
                resp.raise_for_status()
                body = resp.json()
        except Exception as exc:  # noqa: BLE001 - must log + surface, not swallow
            log_error_exc(
                "oauth auto-refresh failed",
                source=LOG_SOURCE,
                exc=exc,
                context={"provider_type": provider_type, "account_id": account.id},
            )
            raise

        account.oauth_token = body.get("access_token", "") or account.oauth_token
        if body.get("refresh_token"):
            account.refresh_token = body["refresh_token"]
        if body.get("expires_in"):
            account.expires_at = now + timedelta(seconds=int(body["expires_in"]))
        session.commit()
        log_info(
            "oauth token auto-refreshed",
            source=LOG_SOURCE,
            context={"provider_type": provider_type, "account_id": account.id},
        )
        return account.oauth_token

    log_error(
        "oauth token unavailable: no valid token and no refresh_token",
        source=LOG_SOURCE,
        context={"provider_type": provider_type, "account_id": account.id},
    )
    raise RuntimeError(
        "oauth token unavailable: account has no valid token and no refresh_token"
    )


def select_provider_credential(
    provider: Provider,
    session: Session,
    preferred_account_id: Optional[int] = None,
) -> str:
    """Pick a credential for a provider across its enabled accounts (B5.1).

    Thin wrapper over :func:`select_provider_credential_with_account` kept for
    backward compatibility (B5.5 added the account-id return).

    :param provider: a loaded :class:`Provider`.
    :param session: an active SQLAlchemy session.
    :param preferred_account_id: optional account pin (gateway header
        ``x-connection-id``); bypasses the strategy when it is an enabled
        account of ``provider``.
    :returns: the credential string to forward upstream.
    """
    credential, _account_id = select_provider_credential_with_account(
        provider, session, preferred_account_id=preferred_account_id
    )
    return credential


def _strategy_of(provider: Provider) -> str:
    """Normalize ``provider.fallback_strategy`` to the supported enum.

    Anything that is not ``round-robin`` (including NULL from a pre-migration
    row and any unknown string) resolves to the ``fill-first`` default. The
    write-side guard is the DTO (``ProviderCreate``/``ProviderUpdate``); this
    is the read-side fail-safe so routing never breaks.
    """
    raw = (getattr(provider, "fallback_strategy", None) or "").strip().lower()
    return ROUND_ROBIN if raw == ROUND_ROBIN else FILL_FIRST


def clamp_sticky_limit(value: Optional[int]) -> int:
    """Coerce a raw ``sticky_round_robin_limit`` to an int >= 1 (default 3).

    One implementation shared by the engine (reads the persisted value) and the
    provider DTOs (write-side normalization), so the clamp can never drift.
    """
    try:
        limit = int(value) if value is not None else DEFAULT_STICKY_ROUND_ROBIN_LIMIT
    except (TypeError, ValueError):
        limit = DEFAULT_STICKY_ROUND_ROBIN_LIMIT
    return max(MIN_STICKY_ROUND_ROBIN_LIMIT, limit)


def _sticky_limit(provider: Provider) -> int:
    """Consecutive calls per account for ``round-robin`` (clamped to >= 1)."""
    return clamp_sticky_limit(getattr(provider, "sticky_round_robin_limit", None))


def _lru_key(account: ProviderAccount) -> "tuple[datetime, int]":
    """Least-recently-used sort key: ``last_used_at`` asc (NULL first), id asc."""
    return (account.last_used_at or datetime.min, account.id)


def _record_account_use(
    provider: Provider, account: ProviderAccount, session: Session, strategy: str
) -> None:
    """Persist the selection so the next ``round-robin`` call can see it.

    ``last_used_at`` is always written (it is the persisted half of the LRU
    advance and keeps the order sane across a strategy switch); the
    consecutive-use counter is only maintained for ``round-robin``.
    """
    account.last_used_at = datetime.utcnow()
    if strategy == ROUND_ROBIN:
        previous_id, previous_uses = _STICKY.get(provider.id, (None, 0))
        uses = previous_uses + 1 if previous_id == account.id else 1
        _STICKY[provider.id] = (account.id, uses)
    session.commit()


def _round_robin_order(
    provider: Provider, accounts: List[ProviderAccount]
) -> List[ProviderAccount]:
    """STICKY order: current account first (while its streak lasts), then the
    rest by least-recently-used.

    The streak ends after ``sticky_round_robin_limit`` consecutive successful
    selections of the same account, at which point the LRU head takes over —
    which is exactly "stay on the same account for N calls, then advance".
    """
    lru = sorted(accounts, key=_lru_key)
    state = _STICKY.get(provider.id)
    if state is not None:
        account_id, uses = state
        if uses < _sticky_limit(provider):
            current = next((a for a in accounts if a.id == account_id), None)
            if current is not None:
                return [current] + [a for a in lru if a.id != current.id]
    return lru


def select_provider_credential_with_account(
    provider: Provider,
    session: Session,
    preferred_account_id: Optional[int] = None,
) -> "tuple[str, Optional[int]]":
    """Strategy-driven account selection -> ``(credential, account_id)``.

    B5.5 needs the chosen ``ProviderAccount.id`` to attribute a ``UsageRecord``
    per account; the routing strategy + pin bypass (9router adoption) need the
    same return. Resolution order:

    1. ``preferred_account_id`` (gateway header ``x-connection-id``) that is an
       ENABLED account of THIS provider -> that account, strategy bypassed.
       Absent / unknown / foreign / disabled -> ignored (logged), strategy runs.
    2. enabled accounts ordered by ``priority`` asc, ``id`` asc;
    3. ``fill-first`` -> first usable account in that order;
       ``round-robin`` -> :func:`_round_robin_order` (sticky, then LRU);
    4. no accounts at all -> ``(provider.api_key, None)`` (legacy fallback,
       unchanged behavior);
    5. every candidate's token unresolvable -> logged + legacy fallback, so the
       gateway is never crashed by an OAuth refresh failure (ADR-013 fail-safe).

    A successful selection persists ``last_used_at`` (and, for ``round-robin``,
    the consecutive-use counter).

    :param provider: a loaded :class:`Provider`.
    :param session: an active SQLAlchemy session.
    :param preferred_account_id: optional account pin (bypasses the strategy).
    """
    accounts = (
        session.query(ProviderAccount)
        .filter_by(provider_id=provider.id, enabled=True)
        .order_by(ProviderAccount.priority.asc(), ProviderAccount.id.asc())
        .all()
    )
    if not accounts:
        return provider.api_key, None  # legacy fallback — unchanged behavior

    strategy = _strategy_of(provider)

    # 1. Pin bypass (x-connection-id). Fail-safe: an unusable pin falls through
    #    to the strategy instead of erroring the request.
    if preferred_account_id is not None:
        pinned = next((a for a in accounts if a.id == preferred_account_id), None)
        if pinned is None:
            log_warning(
                "preferred account not usable for this provider; "
                "falling back to the routing strategy",
                source=LOG_SOURCE,
                context={
                    "provider_id": provider.id,
                    "preferred_account_id": preferred_account_id,
                },
            )
        else:
            try:
                credential = get_valid_token(pinned, session)
            except Exception as exc:  # noqa: BLE001 - never crash the gateway
                log_error_exc(
                    "pinned account credential unavailable; falling back to "
                    "the routing strategy",
                    source=LOG_SOURCE,
                    exc=exc,
                    context={
                        "provider_id": provider.id,
                        "account_id": pinned.id,
                    },
                )
            else:
                account_id = pinned.id
                _record_account_use(provider, pinned, session, strategy)
                return credential, account_id

    # 2-5. Strategy path.
    candidates = (
        _round_robin_order(provider, accounts)
        if strategy == ROUND_ROBIN
        else list(accounts)  # fill-first: priority asc, id asc
    )
    for account in candidates:
        try:
            credential = get_valid_token(account, session)
        except Exception as exc:  # noqa: BLE001 - skip + try the next account
            log_error_exc(
                "account credential unavailable; trying the next account",
                source=LOG_SOURCE,
                exc=exc,
                context={
                    "provider_id": provider.id,
                    "account_id": account.id,
                    "strategy": strategy,
                },
            )
            continue
        account_id = account.id
        _record_account_use(provider, account, session, strategy)
        return credential, account_id

    log_error(
        "no enabled provider account yielded a usable credential; "
        "falling back to provider.api_key",
        source=LOG_SOURCE,
        context={"provider_id": provider.id, "strategy": strategy},
    )
    return provider.api_key, None


def reset_routing_state() -> None:
    """Drop all in-memory sticky round-robin counters (test / admin helper).

    ``last_used_at`` in the DB is untouched — it is the durable half, so a
    restart simply re-derives the order from it.
    """
    _STICKY.clear()


__all__ = [
    "CONNECTION_ID_HEADER",
    "DEFAULT_FALLBACK_STRATEGY",
    "DEFAULT_STICKY_ROUND_ROBIN_LIMIT",
    "FILL_FIRST",
    "MIN_STICKY_ROUND_ROBIN_LIMIT",
    "OAUTH_REGISTRY",
    "OAUTH_STATES",
    "REDIRECT_BASE",
    "ROUND_ROBIN",
    "ROUTING_STRATEGIES",
    "get_valid_token",
    "reset_routing_state",
    "select_provider_credential",
    "select_provider_credential_with_account",
]

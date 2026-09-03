"""OAuth registry + token management (Backlog B5.1).

Implements ADR-013 (OAuth Auto-Refresh): ``ProviderAccount.auth_type='oauth'``
stores ``oauth_token`` + ``refresh_token`` + ``expires_at``; before a request the
system refreshes the token automatically when it is near expiry (no manual
re-login). Multi-account selection (round-robin across a provider's enabled
accounts) is also provided here so the gateway can pick an account credential
instead of the legacy ``provider.api_key``.

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
from typing import Dict, Optional

import httpx
from sqlalchemy.orm import Session

from backend.log import log_error, log_error_exc, log_info
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

# Module-global round-robin cursor keyed by provider.id. Cheap in-memory state;
# wraps with modulo at selection time.
_ROUND_ROBIN: Dict[int, int] = {}

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


def select_provider_credential(provider: Provider, session: Session) -> str:
    """Pick a credential for a provider across its enabled accounts (B5.1).

    Thin wrapper over :func:`select_provider_credential_with_account` kept for
    backward compatibility (B5.5 added the account-id return).

    :param provider: a loaded :class:`Provider`.
    :param session: an active SQLAlchemy session.
    :returns: the credential string to forward upstream.
    """
    credential, _account_id = select_provider_credential_with_account(
        provider, session
    )
    return credential


def select_provider_credential_with_account(
    provider: Provider, session: Session
) -> "tuple[str, Optional[int]]":
    """Round-robin account selection returning ``(credential, account_id)``.

    B5.5: the gateway needs the chosen ``ProviderAccount.id`` to attribute a
    ``UsageRecord`` per account (quota tracking per subscription account).
    Semantics are identical to :func:`select_provider_credential`:

    * zero enabled accounts -> ``(provider.api_key, None)`` (legacy fallback);
    * an account whose token cannot be resolved -> log + ``(provider.api_key,
      None)`` so the gateway still serves the request.
    """
    accounts = (
        session.query(ProviderAccount)
        .filter_by(provider_id=provider.id, enabled=True)
        .order_by(ProviderAccount.id.asc())
        .all()
    )
    if not accounts:
        return provider.api_key, None  # legacy fallback — unchanged behavior

    idx = _ROUND_ROBIN.get(provider.id, 0) % len(accounts)
    _ROUND_ROBIN[provider.id] = idx + 1
    account = accounts[idx]
    try:
        return get_valid_token(account, session), account.id
    except Exception as exc:  # noqa: BLE001 - never crash the gateway on refresh
        log_error_exc(
            "select_provider_credential failed; falling back to provider.api_key",
            source=LOG_SOURCE,
            exc=exc,
            context={"provider_id": provider.id, "account_id": account.id},
        )
        return provider.api_key, None


__all__ = [
    "OAUTH_REGISTRY",
    "OAUTH_STATES",
    "REDIRECT_BASE",
    "get_valid_token",
    "select_provider_credential",
    "select_provider_credential_with_account",
]

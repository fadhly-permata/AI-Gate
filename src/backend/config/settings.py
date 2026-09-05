"""Config-in-DB repository for the ``Setting`` key-value store (ADR-010/011).

Replaces separate config files. All config values are stored plaintext in the
database — no encryption, matching ADR-010/ADR-011 and rule R11. Secrets live
elsewhere (Provider/Endpoint/ProxyNode, ADR-007); this table holds only
non-credential config keys.

Public API:
- ``get(key, default=None, session=None)`` -> value string or default.
- ``set(key, value, session=None)`` -> upsert a Setting row (updates updated_at).
- ``ensure_seeded(session=None)`` -> idempotent seed of default settings.
- ``list_all(session=None)`` -> dict of all key -> value.

Rule R12: no bare ``except: pass``; caught errors are logged via ``logging``.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable, Mapping, Sequence

from sqlalchemy import select

from backend.config import db as _db
from backend.log import log_error_exc, log_info
from backend.models import Setting

logger = logging.getLogger(__name__)


# Sensible defaults seeded on first boot. These feed the B1.3 Settings UI
# and dev-mode behavior. Values are plaintext strings (R11) by design.
DEFAULT_SETTINGS: dict[str, str] = {
    "port": "8080",
    "dev_mode": "false",
    "theme": "light",
    "locale": "en",
    # B5.6 / PRD §2.4.3: request-level debug logging (RequestLog). 'true'
    # enables per-request/response persistence on the gateway; default OFF
    # to avoid DB bloat. Read by backend.gateway.router per request.
    "request_log_enabled": "false",
    # Terminal PTY reaper grace (minutes): a DETACHED session (no WS view)
    # with no output for this long is reaped. Deliberately generous — a
    # dropped WS must never kill a running shell; only truly-dead or
    # extremely-long-orphaned PTYs are cleaned up. Read by
    # backend.terminal.session._grace_seconds().
    "terminal_idle_reap_minutes": "60",
}


def get(key: str, default: str | None = None, session: Any | None = None) -> str | None:
    """Return the ``value`` for ``key``, or ``default`` if not present.

    Pass an existing ``session`` to participate in a transaction; otherwise a
    short-lived ``SessionLocal`` is created, committed and closed.
    """
    own_session = session is None
    s = session if session is not None else _db.SessionLocal()
    try:
        row = _get_by_key(s, key)
        return row.value if row is not None else default
    except Exception:  # noqa: BLE001 — log then surface via caller contract
        logger.error("config.settings.get failed for key=%r", key, exc_info=True)
        log_error_exc(
            f"config.settings.get failed for key={key!r}",
            source="backend.config.settings",
        )
        raise
    finally:
        if own_session:
            s.close()


def set(key: str, value: str, session: Any | None = None) -> Setting:
    """Upsert a ``Setting`` row for ``key`` with ``value``.

    Updates ``updated_at`` automatically (model ``onupdate``). Returns the
    persisted ``Setting``. Commits when owning the session.
    """
    own_session = session is None
    s = session if session is not None else _db.SessionLocal()
    try:
        row = _get_by_key(s, key)
        if row is None:
            row = Setting(key=key, value=value)
            s.add(row)
        else:
            row.value = value
        s.flush()
        if own_session:
            s.commit()
            s.refresh(row)
        return row
    except Exception:  # noqa: BLE001
        if own_session:
            s.rollback()
        logger.error("config.settings.set failed for key=%r", key, exc_info=True)
        log_error_exc(
            f"config.settings.set failed for key={key!r}",
            source="backend.config.settings",
        )
        raise
    finally:
        if own_session:
            s.close()


def ensure_seeded(session: Any | None = None) -> None:
    """Idempotently insert default ``Setting`` rows that are missing.

    Existing keys are never overwritten (read-only seed). Safe to call on
    every startup. Commits when owning the session.
    """
    own_session = session is None
    s = session if session is not None else _db.SessionLocal()
    try:
        existing = {k for k in _existing_keys(s)}
        to_insert = [
            Setting(key=k, value=v)
            for k, v in DEFAULT_SETTINGS.items()
            if k not in existing
        ]
        if to_insert:
            s.add_all(to_insert)
            s.flush()
        if own_session:
            s.commit()
        logger.info(
            "config.settings.ensure_seeded: inserted=%d existing=%d",
            len(to_insert),
            len(existing),
        )
        log_info(
            f"config.settings.ensure_seeded: inserted={len(to_insert)} "
            f"existing={len(existing)}",
            source="backend.config.settings",
        )
    except Exception:  # noqa: BLE001
        if own_session:
            s.rollback()
        logger.error("config.settings.ensure_seeded failed", exc_info=True)
        log_error_exc(
            "config.settings.ensure_seeded failed", source="backend.config.settings"
        )
        raise
    finally:
        if own_session:
            s.close()


def list_all(session: Any | None = None) -> dict[str, str]:
    """Return a dict of every ``Setting`` key -> value."""
    own_session = session is None
    s = session if session is not None else _db.SessionLocal()
    try:
        rows: Sequence[Setting] = s.execute(select(Setting)).scalars().all()
        return {row.key: row.value for row in rows}
    except Exception:  # noqa: BLE001
        logger.error("config.settings.list_all failed", exc_info=True)
        log_error_exc(
            "config.settings.list_all failed", source="backend.config.settings"
        )
        raise
    finally:
        if own_session:
            s.close()


# --- internal helpers -------------------------------------------------------


def _get_by_key(s: Any, key: str) -> Setting | None:
    """Lookup a ``Setting`` row by its unique string ``key`` (PK is int id)."""
    return s.execute(
        select(Setting).where(Setting.key == key)
    ).scalars().first()


def _existing_keys(s: Any) -> Iterable[str]:
    """Return all current ``Setting`` keys in the session."""
    rows = s.execute(select(Setting.key)).scalars().all()
    return rows


__all__ = ["DEFAULT_SETTINGS", "get", "set", "ensure_seeded", "list_all"]

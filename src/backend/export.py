"""Export / Import of the entire local configuration to a single JSON document
(task B5.7 — PRD §2.4.4 / FSD §2.4.4, the local replacement for cloud sync).

Design (ERD line 378): export/import is a **serialization of the existing
config entities** — no new tables. It walks the twelve configuration entities
(``Provider``, ``ProviderAccount``, ``ProviderModel``, ``ProxyPool``,
``ProxyNode``, ``Combo``, ``ComboMember``, ``Endpoint``, ``EndpointBinding``,
``CLIToolGroup``, ``CLITool``, ``Setting``) and writes them — column by column,
ids included so foreign keys resolve on import — into one JSON-safe dict with a
schema header.

Runtime / telemetry entities (``TerminalSession``, ``TerminalTab``,
``LogEntry``, ``UsageRecord``, ``RequestLog``) are deliberately **excluded**:
they are operational history, not configuration, and must never be restored
onto another device.

ADR-007 / rule R11: secrets (``api_key``, ``oauth_token``, ``refresh_token``,
``password``, ``internal_api_key``) are serialized **in plaintext, as-is**.
This is a local file the user owns (the whole point of "no cloud"); the UI does
not redact it either.

Rule R12 / ADR-011: every failure is logged to ``LogEntry`` via ``backend.log``
before an error envelope is returned — no ``except: pass``.

Pydantic **v1** only (rule R10) — this module uses plain dicts, no v2 syntax.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.orm import Session

from backend import __version__ as APP_VERSION
from backend.log import log_error_exc, log_info, log_warning
from backend.models import (
    CLITool,
    CLIToolGroup,
    Combo,
    ComboMember,
    Endpoint,
    EndpointBinding,
    Provider,
    ProviderAccount,
    ProviderModel,
    ProxyNode,
    ProxyPool,
    Setting,
)

LOG_SOURCE = "backend.export"

# Bumped only on a breaking change to the document shape. Import rejects any
# version it does not understand rather than half-restoring a mismatched file.
EXPORT_VERSION = 1
SUPPORTED_VERSIONS = frozenset({1})

# (document key -> model) in PARENT-FIRST order: every entity appears after the
# entities its foreign keys point at, so a straight forward pass inserts rows
# without ever referencing a not-yet-inserted parent.
EXPORT_ORDER: list[tuple[str, type]] = [
    ("providers", Provider),
    ("provider_accounts", ProviderAccount),
    ("provider_models", ProviderModel),
    ("proxy_pools", ProxyPool),
    ("proxy_nodes", ProxyNode),
    ("combos", Combo),
    ("combo_members", ComboMember),
    ("endpoints", Endpoint),
    ("endpoint_bindings", EndpointBinding),
    ("cli_tool_groups", CLIToolGroup),
    ("cli_tools", CLITool),
    ("settings", Setting),
]

# CHILD-FIRST delete order for ``replace`` mode: every entity appears before the
# entities it depends on, so no parent is removed while a child still points at
# it. (SQLite FK enforcement is off by default here, but a correct order keeps
# the operation sound if it is ever switched on.)
DELETE_ORDER: list[type] = [
    EndpointBinding,
    ComboMember,
    ProviderModel,
    ProviderAccount,
    CLITool,
    ProxyNode,
    Endpoint,
    Provider,
    Combo,
    CLIToolGroup,
    ProxyPool,
    Setting,
]


# --------------------------------------------------------------------------- #
# Serialization helpers
# --------------------------------------------------------------------------- #
def _jsonify(value: Any) -> Any:
    """Coerce a single column value into a JSON-safe primitive.

    ``datetime`` -> ISO-8601 string; everything else (int / float / bool / str /
    None) is already JSON-safe and returned untouched.
    """
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _serialize_row(obj: Any) -> dict[str, Any]:
    """Serialize one ORM instance to a plain dict keyed by column name.

    Iterating ``__table__.columns`` (rather than hard-coding fields) means new
    model columns are exported automatically and ids are always included so the
    foreign keys resolve on import.
    """
    return {col.name: _jsonify(getattr(obj, col.name)) for col in obj.__table__.columns}


def _make_instance(model: type, row: dict[str, Any]) -> Any:
    """Build a transient ORM instance from an exported row dict.

    Only columns the model actually declares are consumed (unknown keys — e.g.
    a field from a newer app version — are ignored, so import stays tolerant).
    ``DateTime`` columns given as ISO strings are parsed back into
    ``datetime`` objects; a malformed timestamp raises so the caller's
    transaction rolls the whole import back rather than persisting bad data.
    """
    kwargs: dict[str, Any] = {}
    for col in model.__table__.columns:
        if col.name not in row:
            continue
        value = row[col.name]
        if isinstance(col.type, DateTime) and isinstance(value, str):
            value = datetime.fromisoformat(value)
        kwargs[col.name] = value
    return model(**kwargs)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def export_settings(session: Session) -> dict[str, Any]:
    """Serialize every configuration entity into one JSON-safe document.

    Returns a dict shaped::

        {
          "aigate_export": {"version": 1, "exported_at": "<iso>", "app_version": "0.0.1"},
          "providers": [...], "provider_accounts": [...], ... , "settings": [...]
        }

    Rows are ordered by primary key so two exports of an unchanged database are
    byte-identical (except ``exported_at``). Secrets are plaintext (ADR-007).
    """
    doc: dict[str, Any] = {
        "aigate_export": {
            "version": EXPORT_VERSION,
            "exported_at": datetime.utcnow().isoformat(),
            "app_version": APP_VERSION,
        }
    }
    total = 0
    for key, model in EXPORT_ORDER:
        rows = session.query(model).order_by(model.id).all()
        doc[key] = [_serialize_row(r) for r in rows]
        total += len(rows)
    log_info(
        f"export_settings: serialized {total} config row(s) across "
        f"{len(EXPORT_ORDER)} table(s)",
        source=LOG_SOURCE,
    )
    return doc


def import_settings(
    session: Session, data: Any, mode: str = "replace"
) -> dict[str, Any]:
    """Restore configuration from an exported document.

    ``mode``:
      - ``"replace"`` (default): wipe every config table (child-first) then
        insert the file's rows (parent-first, ids preserved). One transaction.
      - ``"merge"``: upsert each row by primary key (``session.merge``) without
        deleting anything. A basic PK-merge — rows sharing an id are overwritten,
        new ids inserted; it never removes config absent from the file.

    Returns ``{"ok": True, "imported": {<table>: <count>, ...}}`` on success, or
    ``{"ok": False, "error": <code>}`` on failure. A missing / unsupported
    ``aigate_export`` header yields ``error="invalid_format"``. Any DB error
    rolls the whole operation back and is logged (R12). Telemetry tables are
    never touched even if present in ``data``.
    """
    if not isinstance(data, dict):
        log_warning("import_settings: payload is not a JSON object", source=LOG_SOURCE)
        return {"ok": False, "error": "invalid_format"}

    header = data.get("aigate_export")
    if not isinstance(header, dict) or header.get("version") not in SUPPORTED_VERSIONS:
        log_warning(
            "import_settings: missing or unsupported 'aigate_export' header",
            source=LOG_SOURCE,
            context={"header": header if isinstance(header, dict) else type(header).__name__},
        )
        return {"ok": False, "error": "invalid_format"}

    if mode not in ("replace", "merge"):
        mode = "replace"

    try:
        if mode == "replace":
            for model in DELETE_ORDER:
                session.query(model).delete(synchronize_session=False)
            # Detach any stale instances loaded before the wipe so re-inserting
            # the same primary keys is treated as a fresh INSERT.
            session.expunge_all()

        imported: dict[str, int] = {}
        for key, model in EXPORT_ORDER:
            rows = data.get(key)
            if not isinstance(rows, list):
                rows = []  # tolerate a missing / malformed section as empty
            count = 0
            for row in rows:
                if not isinstance(row, dict):
                    continue
                instance = _make_instance(model, row)
                if mode == "merge":
                    session.merge(instance)
                else:
                    session.add(instance)
                count += 1
            imported[key] = count

        session.commit()
    except Exception as exc:  # noqa: BLE001 — rollback + log + error envelope (R12)
        session.rollback()
        log_error_exc(
            f"import_settings failed (mode={mode}); rolled back",
            source=LOG_SOURCE,
            exc=exc,
        )
        return {"ok": False, "error": str(exc)}

    log_info(
        f"import_settings: restored config (mode={mode})",
        source=LOG_SOURCE,
        context=imported,
    )
    return {"ok": True, "imported": imported}


__all__ = ["export_settings", "import_settings", "EXPORT_VERSION", "EXPORT_ORDER"]

"""File-based plaintext secret store — ADR-007 compliant.

ADR-007 (see documents/architecture/TSD.md §5.1) RESOLVED: application-level
secrets are stored in a plain file with **NO encryption**. This module is the
explicit mechanism for secrets kept *outside* the relational config DB
(``~/.aigate/aigate.db``), e.g. a gateway internal/master key.

- Store path: ``~/.aigate/secrets.json`` (parent created if missing).
- Format: plaintext JSON (``dict[str, str]``). No Fernet, no hashing, no
  encryption of any kind.
- Operations are minimal read-modify-write guarded by a ``threading.Lock``.

This is intentionally NOT the ORM secret columns (api_key, internal_api_key,
password) defined in models.py / ERD.md — those live in SQLite. This file
store is for singleton app-level secrets that must not live in the DB.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

# Path to the plaintext secrets file. Overridable (tests point it at tmp dir).
SECRETS_PATH: Path = Path.home() / ".aigate" / "secrets.json"

_lock = threading.Lock()


def _read_raw() -> dict[str, str]:
    """Read the raw secrets file, returning an empty dict if absent."""
    if not SECRETS_PATH.exists():
        return {}
    try:
        with SECRETS_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _write_raw(data: dict[str, str]) -> None:
    """Write the secrets dict as plaintext JSON, creating the parent dir."""
    SECRETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SECRETS_PATH.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def load_secrets() -> dict[str, str]:
    """Load all secrets as a plaintext dict (empty dict if none stored)."""
    with _lock:
        return _read_raw()


def get_secret(key: str) -> str | None:
    """Return the plaintext value for ``key`` or ``None`` if not present."""
    with _lock:
        return _read_raw().get(key)


def set_secret(key: str, value: str) -> None:
    """Store ``key`` = ``value`` as plaintext (no encryption). Overwrites."""
    with _lock:
        data = _read_raw()
        data[key] = value
        _write_raw(data)


def delete_secret(key: str) -> None:
    """Remove ``key`` from the store if present. No-op if absent."""
    with _lock:
        data = _read_raw()
        if key in data:
            del data[key]
            _write_raw(data)

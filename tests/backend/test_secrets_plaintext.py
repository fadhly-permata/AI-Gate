"""B0.3 — ADR-007 plaintext secret storage verification.

Prove secrets round-trip unchanged (no encryption/hashing) and that the
backend contains zero encryption code.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from sqlalchemy import String, inspect

# Resolve the backend source tree relative to this file so the import works
# regardless of how pytest is invoked (src/ layout -> installed as `backend`).
_BACKEND_ROOT = Path(__file__).resolve().parents[2] / "src" / "backend"

from backend.config.db import Base  # noqa: E402
from backend.models import Endpoint, Provider, ProxyNode, ProxyPool  # noqa: E402


def test_provider_api_key_plaintext_roundtrip(db_session) -> None:
    """A stored Provider api_key must come back byte-for-byte unchanged."""
    provider = Provider(
        name="pt-plain",
        type="openai-compatible",
        base_url="http://localhost:9999/v1",
        api_key="sk-test-plaintext",
    )
    db_session.add(provider)
    db_session.commit()

    got = db_session.query(Provider).filter_by(name="pt-plain").one()
    # ADR-007: NOT transformed, NOT encrypted, NOT hashed.
    assert got.api_key == "sk-test-plaintext"


def test_endpoint_internal_api_key_plaintext_roundtrip(db_session) -> None:
    endpoint = Endpoint(name="ep-plain", internal_api_key="sk-internal-plain")
    db_session.add(endpoint)
    db_session.commit()

    got = db_session.query(Endpoint).filter_by(name="ep-plain").one()
    assert got.internal_api_key == "sk-internal-plain"


def test_proxy_node_credentials_plaintext_roundtrip(db_session) -> None:
    pool = ProxyPool(name="pool-plain")
    db_session.add(pool)
    db_session.commit()
    node = ProxyNode(
        pool_id=pool.id,
        host="10.0.0.1",
        port=8080,
        username="proxyuser",
        password="proxy-pass-plain",
    )
    db_session.add(node)
    db_session.commit()

    got = db_session.query(ProxyNode).filter_by(pool_id=pool.id).one()
    assert got.username == "proxyuser"
    assert got.password == "proxy-pass-plain"


def test_secret_columns_are_plain_string(db_session) -> None:
    """Secret columns must be plain String (no custom encrypted type)."""
    engine = db_session.get_bind()
    cols = {c["name"]: c for c in inspect(engine).get_columns("providers")}
    assert isinstance(cols["api_key"]["type"], String)
    ecols = {c["name"]: c for c in inspect(engine).get_columns("endpoints")}
    assert isinstance(ecols["internal_api_key"]["type"], String)
    pcols = {c["name"]: c for c in inspect(engine).get_columns("proxy_nodes")}
    assert isinstance(pcols["username"]["type"], String)
    assert isinstance(pcols["password"]["type"], String)


def test_no_encryption_imports_in_backend() -> None:
    """Grep src/backend: must contain NO import of any encryption library.

    ADR-007 docstrings legitimately mention "no encryption" — those are
    allowed. Only real import statements of crypto libraries are forbidden.
    """
    forbidden_imports = (
        "import cryptography",
        "from cryptography",
        "import fernet",
        "from cryptography.fernet",
        "import hashlib",
        "from hashlib",
        "import bcrypt",
        "from bcrypt",
        "import itsdangerous",
        "from itsdangerous",
    )
    hits: list[str] = []
    for py_file in _BACKEND_ROOT.rglob("*.py"):
        for line in py_file.read_text(encoding="utf-8").splitlines():
            stripped = line.lstrip()
            if not (stripped.startswith("import ") or stripped.startswith("from ")):
                continue
            for imp in forbidden_imports:
                if stripped.startswith(imp):
                    hits.append(
                        f"{py_file.relative_to(_BACKEND_ROOT)}: {stripped}"
                    )
    assert not hits, "Encryption imports found:\n" + "\n".join(hits)

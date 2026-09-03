"""SQLAlchemy ORM models for all aigate config entities (from ERD.md).

Fifteen entities are modeled with exact columns and foreign keys per
``documents/analysis/ERD.md``:

    Provider, ProviderModel, ProxyPool, ProxyNode, Combo, ComboMember,
    Endpoint, EndpointBinding, CLIToolGroup, CLITool, TerminalSession,
    TerminalTab, LogEntry, Setting, UsageRecord.

ADR-007: secret columns (``api_key``, ``internal_api_key``, ``password``)
are stored in plaintext — no encryption, matching the ERD data dictionary.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.config.db import Base


class Provider(Base):
    """AI provider credentials + base configuration."""

    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    base_url: Mapped[str] = mapped_column(String, nullable=False)
    # ADR-007: plaintext per design (local app) — NO encryption, NO hashing.
    api_key: Mapped[str] = mapped_column(String, nullable=False, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # B5.2: 3-Tier Fallback tier classification. Allowed: 'subscription' |
    # 'cheap' | 'free'. Defaults to 'subscription'; if unset/unknown, the
    # routing layer classifies by provider ``type`` via ``provider_tier``.
    tier: Mapped[str] = mapped_column(String, default="subscription")
    # B5.5 / PRD §2.4.2: quota tracking. ``quota_limit`` = total tokens
    # (in+out) allowed per ``quota_window``; None = no quota tracked
    # (treated as "has quota" by routing, unlimited in /api/quota).
    # ``quota_window`` in {'hour', 'day', 'week'}; None defaults to 'day'
    # when a limit is set.
    quota_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    quota_window: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # JSON-encoded dict of extra HTTP headers (e.g. org/region headers).
    # Empty -> "{}". Stored as text; ADR-007 plaintext (no encryption).
    custom_headers: Mapped[str] = mapped_column(String, default="{}")
    # Default model hint for this provider (nullable; free-form provider model id).
    default_model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    models: Mapped[list["ProviderModel"]] = relationship(back_populates="provider")
    accounts: Mapped[list["ProviderAccount"]] = relationship(
        back_populates="provider"
    )
    combo_members: Mapped[list["ComboMember"]] = relationship(
        back_populates="provider"
    )
    # B5.5: usage telemetry rows produced against this provider.
    usages: Mapped[list["UsageRecord"]] = relationship(back_populates="provider")
    bindings: Mapped[list["EndpointBinding"]] = relationship(
        primaryjoin=(
            "and_(foreign(EndpointBinding.bind_id) == Provider.id, "
            "EndpointBinding.bind_type == 'provider')"
        ),
        viewonly=True,
    )


class ProviderAccount(Base):
    """Per-provider credential account (B5.1 / ADR-007 / ADR-013).

    A provider may have many accounts. Each account carries either a static
    ``api_key`` (``auth_type='api_key'``) or an OAuth token set
    (``auth_type='oauth'``): ``oauth_token``, ``refresh_token``,
    ``expires_at``. Tokens are stored in **plaintext** (ADR-007) — no
    encryption, no masking, returned as-is by the API.
    """

    __tablename__ = "provider_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("providers.id"), nullable=False
    )
    label: Mapped[str] = mapped_column(String, nullable=False, default="")
    auth_type: Mapped[str] = mapped_column(String, nullable=False, default="api_key")
    # ADR-007: plaintext per design (local app) — NO encryption, NO hashing.
    api_key: Mapped[str] = mapped_column(String, default="")
    oauth_token: Mapped[str] = mapped_column(String, default="")
    refresh_token: Mapped[str] = mapped_column(String, default="")
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    provider: Mapped["Provider"] = relationship(back_populates="accounts")


class ProviderModel(Base):
    """Auto-discovered model for a provider."""

    __tablename__ = "provider_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("providers.id"), nullable=False
    )
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    capabilities: Mapped[str] = mapped_column(String, default="")

    provider: Mapped["Provider"] = relationship(back_populates="models")


class ProxyPool(Base):
    """A pool of proxy nodes with a rotation strategy."""

    __tablename__ = "proxy_pools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    rotation_strategy: Mapped[str] = mapped_column(String, default="round_robin")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Round-robin cursor state (B2.3). Index into the healthy-node list;
    # wrapped with modulo at selection time.
    last_used_index: Mapped[int] = mapped_column(Integer, default=0)

    nodes: Mapped[list["ProxyNode"]] = relationship(back_populates="pool")


class ProxyNode(Base):
    """A single proxy node belonging to a pool."""

    __tablename__ = "proxy_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pool_id: Mapped[int] = mapped_column(
        ForeignKey("proxy_pools.id"), nullable=False
    )
    host: Mapped[str] = mapped_column(String, nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    protocol: Mapped[str] = mapped_column(String, default="http")
    # ADR-007: plaintext per design (local app) — NO encryption, NO hashing.
    username: Mapped[str] = mapped_column(String, default="")
    password: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="unknown")
    last_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    uptime_pct: Mapped[float] = mapped_column(Float, default=0.0)
    last_checked: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    pool: Mapped["ProxyPool"] = relationship(back_populates="nodes")


class Combo(Base):
    """Routing group (fallback / load_balance / latency_cost)."""

    __tablename__ = "combos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    strategy: Mapped[str] = mapped_column(String, default="fallback")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    members: Mapped[list["ComboMember"]] = relationship(back_populates="combo")
    bindings: Mapped[list["EndpointBinding"]] = relationship(
        primaryjoin=(
            "and_(foreign(EndpointBinding.bind_id) == Combo.id, "
            "EndpointBinding.bind_type == 'combo')"
        ),
        viewonly=True,
    )


class ComboMember(Base):
    """A provider/model member of a combo with priority + weight."""

    __tablename__ = "combo_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    combo_id: Mapped[int] = mapped_column(ForeignKey("combos.id"), nullable=False)
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("providers.id"), nullable=False
    )
    provider_model: Mapped[str] = mapped_column(String, default="")
    priority: Mapped[int] = mapped_column(Integer, default=0)
    weight: Mapped[float] = mapped_column(Float, default=1.0)

    combo: Mapped["Combo"] = relationship(back_populates="members")
    provider: Mapped["Provider"] = relationship(back_populates="combo_members")


class Endpoint(Base):
    """Local OpenAI-compatible gateway endpoint."""

    __tablename__ = "endpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    listen_host: Mapped[str] = mapped_column(String, default="127.0.0.1")
    listen_port: Mapped[int] = mapped_column(Integer, default=8000)
    access_control_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    # ADR-007: plaintext per design (local app) — NO encryption, NO hashing.
    internal_api_key: Mapped[str] = mapped_column(String, default="")
    # ADR-008: Endpoint -> ProxyPool binding (nullable; per-endpoint egress
    # proxy). FK to proxy_pools.id; null = no proxy for this endpoint.
    proxy_pool_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("proxy_pools.id"), nullable=True
    )
    # ADR-013 / B5.4: Token Saver hook mode applied as a pre-translate hook.
    # Allowed: 'off' | 'rtk' | 'caveman' | 'ponytail'. Default 'off' (no hook).
    token_saver: Mapped[str] = mapped_column(
        String, nullable=False, default="off"
    )

    bindings: Mapped[list["EndpointBinding"]] = relationship(
        back_populates="endpoint"
    )
    # B5.5: usage rows produced through this endpoint (ERD Endpoint||--o{UsageRecord).
    usages: Mapped[list["UsageRecord"]] = relationship(back_populates="endpoint")


class EndpointBinding(Base):
    """Polymorphic mapping: endpoint -> one Provider or Combo.

    ``bind_type`` is ``"provider"`` or ``"combo"``; ``bind_id`` points to the
    corresponding row. No FK is declared because the target table varies.
    """

    __tablename__ = "endpoint_bindings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    endpoint_id: Mapped[int] = mapped_column(
        ForeignKey("endpoints.id"), nullable=False
    )
    bind_type: Mapped[str] = mapped_column(String, nullable=False)
    bind_id: Mapped[int] = mapped_column(Integer, nullable=False)

    endpoint: Mapped["Endpoint"] = relationship(back_populates="bindings")


class UsageRecord(Base):
    """Token & cost telemetry per request (ERD §UsageRecord / PRD §2.4.2, B5.5).

    Written by the gateway after a SUCCESSFUL chat completion (fail-open —
    recording errors never break the client response) and read by
    ``backend.usage`` / ``backend.usage_router`` for ``/api/usage`` +
    ``/api/quota``.

    Nullability note vs the ERD: ``endpoint_id`` is nullable because
    model-based gateway requests (no ``X-Aigate-Endpoint`` header) have no
    endpoint attribution; ``account_id`` is nullable for the legacy
    ``provider.api_key`` path (ERD marks it optional).
    """

    __tablename__ = "usage_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    endpoint_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("endpoints.id"), nullable=True
    )
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("providers.id"), nullable=False
    )
    account_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("provider_accounts.id"), nullable=True
    )
    model: Mapped[str] = mapped_column(String, default="")
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    # B5.5: estimated USD cost (best-effort; see backend.usage.estimate_cost).
    cost_est: Mapped[float] = mapped_column(Float, default=0.0)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    endpoint: Mapped[Optional["Endpoint"]] = relationship(back_populates="usages")
    provider: Mapped["Provider"] = relationship(back_populates="usages")
    account: Mapped[Optional["ProviderAccount"]] = relationship()


class CLIToolGroup(Base):
    """Category group for CLI tools (A / B / C)."""

    __tablename__ = "cli_tool_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[str] = mapped_column(String, nullable=False)
    display_priority: Mapped[int] = mapped_column(Integer, default=0)

    tools: Mapped[list["CLITool"]] = relationship(back_populates="group")


class CLITool(Base):
    """A single CLI tool preset."""

    __tablename__ = "cli_tools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("cli_tool_groups.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    binary_name: Mapped[str] = mapped_column(String, default="")
    install_command: Mapped[str] = mapped_column(String, default="")
    default_flags: Mapped[str] = mapped_column(String, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    group: Mapped["CLIToolGroup"] = relationship(back_populates="tools")


class TerminalSession(Base):
    """A terminal workspace session."""

    __tablename__ = "terminal_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tabs: Mapped[list["TerminalTab"]] = relationship(back_populates="session")


class TerminalTab(Base):
    """A tab within a terminal session."""

    __tablename__ = "terminal_tabs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("terminal_sessions.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String, default="")
    shell_type: Mapped[str] = mapped_column(String, default="bash")
    pty_pid: Mapped[str] = mapped_column(String, default="")
    is_fullscreen: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["TerminalSession"] = relationship(back_populates="tabs")


class LogEntry(Base):
    """Operational application log (PRD §2.8 / ADR-011).

    Every backend method (and the frontend) must write to this table.
    ``stacktrace`` is nullable and only populated for warning/error.
    """

    __tablename__ = "log_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    severity: Mapped[str] = mapped_column(String, nullable=False, default="info")
    source: Mapped[str] = mapped_column(String, nullable=False, default="")
    message: Mapped[str] = mapped_column(String, nullable=False, default="")
    stacktrace: Mapped[str | None] = mapped_column(Text, nullable=True)


class Setting(Base):
    """Application configuration key-value store (PRD §2.8 / ADR-010).

    Replaces separate config files; ``value`` is free-form serialization.
    Secrets elsewhere (Provider/Endpoint/ProxyNode) remain plaintext
    per ADR-007 — this table holds only config keys, not credentials.
    """

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    value: Mapped[str] = mapped_column(String, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


__all__ = [
    "Provider",
    "ProviderAccount",
    "ProviderModel",
    "ProxyPool",
    "ProxyNode",
    "Combo",
    "ComboMember",
    "Endpoint",
    "EndpointBinding",
    "CLIToolGroup",
    "CLITool",
    "TerminalSession",
    "TerminalTab",
    "LogEntry",
    "Setting",
    "UsageRecord",
]

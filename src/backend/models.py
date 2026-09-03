"""SQLAlchemy ORM models for all aigate config entities (from ERD.md).

Twelve entities are modeled with exact columns and foreign keys per
``documents/analysis/ERD.md``:

    Provider, ProviderModel, ProxyPool, ProxyNode, Combo, ComboMember,
    Endpoint, EndpointBinding, CLIToolGroup, CLITool, TerminalSession,
    TerminalTab.

ADR-007: secret columns (``api_key``, ``internal_api_key``, ``password``)
are stored in plaintext — no encryption, matching the ERD data dictionary.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.config.db import Base


class Provider(Base):
    """AI provider credentials + base configuration."""

    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    base_url: Mapped[str] = mapped_column(String, nullable=False)
    api_key: Mapped[str] = mapped_column(String, nullable=False, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    models: Mapped[list["ProviderModel"]] = relationship(back_populates="provider")
    combo_members: Mapped[list["ComboMember"]] = relationship(
        back_populates="provider"
    )


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
    internal_api_key: Mapped[str] = mapped_column(String, default="")

    bindings: Mapped[list["EndpointBinding"]] = relationship(
        back_populates="endpoint"
    )


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


__all__ = [
    "Provider",
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
]

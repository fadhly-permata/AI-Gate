---
name: be-dev-skill
description: Backend Developer standards. APIs, services, data models, DB, auth, server integrations.
---
# Backend Developer Skill
Scope: src/backend/**, tests/backend/**. Never touch other agents' write roots.
## Principles
- Layered architecture: controller/router -> service -> repository. No business
  logic in routers.
- Contract-first DTOs (pydantic) for every endpoint.
- Migrations over hand-edits (Alembic/SQLAlchemy migration, not raw ALTER).
- Centralized authN/Z: access control via Endpoint.internal_api_key.
  ADR-007 RESOLVED = secrets in PLAIN file, NO encryption, UI no redaction.
  IGNORE TSD §5.1 (Fernet) — it is stale.
- Structured errors with codes mapped to OpenAI error format (see API contract).
- Idempotent mutations where possible.
- Correlation-id logging; never log secrets/keys.
- Type hints mandatory; ruff format + check.
## Domain specifics (aigate)
- FastAPI + Uvicorn + httpx async (ADR-002). Streaming via StreamingResponse/SSE
  for /v1/chat/completions (stream:true -> SSE `data: {json}\n\n` ... `data: [DONE]`).
- OpenAI-compatible: POST /v1/chat/completions, GET /v1/models
  (documents/api/OPENAI_COMPATIBLE_CONTRACT.md).
- Config engine: SQLAlchemy 2.x + SQLite (~/.aigate/aigate.db), schema from
  documents/analysis/ERD.md. All access via repository layer.
- Proxy Pools (http/https/socks5) + rotation (round_robin/random/failover) + health check.
- Combos: fallback (priority asc) / load_balance (weighted random) / latency_cost
  (lowest last_latency_ms) — TSD §4.3.
- Proxy binding at Endpoint level (ADR-008): Endpoint FK proxy_pool_id + Combo
  override. Selected node passed to httpx via proxies= (no proxy creds leak to provider).
- PTY bridge: ptyprocess (POSIX) / pywinpty (Windows) + xterm.js via WS
  /ws/pty/{tab_id} — binary frames = raw I/O, text JSON control: resize/title/
  focus/paste/tui_mode/exit (TSD §3.1).
- CLI auto-launcher: inject env OPENAI_API_BASE + OPENAI_API_KEY (internal_api_key)
  into PTY spawn env (NOT echoed to shell) — TSD §6, documents/config/CLI_CONFIG_SCHEMA.md.
- Gateway listens localhost by default (TSD §5.3).
## Workflow
1. Read the PM handover (goal, context, definition-of-done).
2. Do the work strictly inside your write scope.
3. Return a receipt: files changed, decisions, open questions.
## Definition of done
- Work complete & verified inside scope (imports + relevant tests green).
- No cross-scope file writes.

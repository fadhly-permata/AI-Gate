# Handover: Log cleanup backend (T1) — be-dev — 2026-09-07

Owner: @be-dev. Write scope: `src/backend/**`, `tests/backend/**` ONLY.
Read context: this file, `src/backend/config/logs_router.py`, `src/backend/models.py`
(LogEntry at :396), `src/backend/config/db.py`, `src/backend/config/settings.py`,
`src/backend/server.py`, `src/backend/selfheal.py` (LogEntry access block ~:718-745),
`src/backend/log.py`, `tests/backend/conftest.py`.

User-approved feature: three log-cleanup options. PM already deleted stale prod row
id=64 — do NOT touch `~/.aigate/aigate.db` (tests use temp DB via conftest `AIGATE_DB_PATH`).

## Constraints (hard)
- Rule R10: Pydantic **v1** `BaseModel` only.
- Rule R12: no bare except; every failure path logged (ADR-011 via `backend.log`).
- Keep self-heal delete-on-success (`selfheal.py:731` `delete_log_entry`, used ~:951)
  behavior UNCHANGED.
- No new config mechanism — reuse `Setting` key-value store (`config/settings.py`).
- Follow existing migration pattern in `db.py` (PRAGMA check + guarded ALTER),
  see `_ensure_usage_record_saved_tokens_column` for the exact template.

## Task A — DELETE /api/logs (in `logs_router.py`)
- `@router.delete("/api/logs")` with optional query params:
  - `severity`: comma-separated (mirror GET semantics: ilike substring OR-match on
    `LogEntry.severity`). Absent = ALL.
  - `before`: ISO datetime string; delete only rows with `timestamp < before`.
    Invalid ISO → same handling pattern as GET's `since` (log_warning + ignore? NO —
    for a destructive op, invalid `before` must NOT silently widen the delete:
    return HTTP 400 `{"detail": "invalid 'before'"}`).
  - Guard: deleting with NO severity filter (wipe-all) requires `confirm=all`
    query param. Missing → HTTP 400 `{"detail": "confirm=all required to delete all entries"}`.
    With severity filter → no confirm needed.
- Return `{"deleted": N}` with HTTP 200 on success.
- **Audit trail**: AFTER the delete commits, write one info LogEntry via
  `log_event(severity="info", source="backend.config.logs_router",
  message=f"logs purged: deleted={n} scope=...")` (include severity filter /
  before cutoff in the message). Log AFTER so wipe-all doesn't delete its own audit row.
- Delete pattern: build `delete()` stmt with the same filter logic as GET, execute
  inside `with SessionLocal()`, commit, return `rowcount`.
- DB failure → log_warning + HTTP 500 (mirror existing GET/POST error paths).

## Task B — Retention auto-purge
- Add to `DEFAULT_SETTINGS` in `config/settings.py`: `"log_retention_days": "7"`.
- New function (put it in `logs_router.py` next to the DELETE logic, reusing filter
  semantics): `purge_expired_logs(days: int | None = None, session=None) -> int`.
  - `days=None` → read Setting `log_retention_days` via `backend.config.settings.get`;
    parse int; invalid/<=0 → fall back to 7 (log_warning, never crash).
  - Delete rows with `timestamp < utcnow - days` (use `datetime.utcnow` to match
    the model default timezone convention).
  - Return deleted count.
- Wire into startup in `server.py` lifespan, after `ensure_seeded()` (BEFORE the
  reaper block is fine). Wrap in try/except like the other startup seeds — startup
  must never crash; on exception `log_exception` + continue.
  On success log ONE info line: `retention purge removed N entries`
  (via `log_event` so it lands in LogEntry; message exactly contains
  "retention purge removed" — tests grep it).

## Task C — `resolved` column + resolve endpoints
- `models.py` LogEntry: add `resolved: Mapped[bool] = mapped_column(Boolean,
  nullable=False, default=False)` (import Boolean — already imported in models.py).
- `db.py`: new `_ensure_log_entry_resolved_column(engine)` copying the
  `_ensure_usage_record_saved_tokens_column` template exactly: PRAGMA
  `table_info(log_entries)`, if `resolved` missing →
  `ALTER TABLE log_entries ADD COLUMN resolved BOOLEAN NOT NULL DEFAULT 0`,
  commit; swallow only `OperationalError` with logger.warning. Call it from
  `init_db()`. This must be safe on the live 24MB DB with ~9700 rows (additive only).
- `_row_to_dict`: include `"resolved": bool(row.resolved) if row.resolved is not None else False`.
- GET `/api/logs`: new optional bool query param `show_resolved` (default false).
  When false → exclude `resolved == True` rows. When true → include everything.
  (Note: this changes GET default semantics — self-heal log feed and old tests only
  look at non-resolved rows, which is the desired behavior. Document in receipt.)
- Endpoints (both return `{"resolved": N}` HTTP 200):
  - `POST /api/logs/{entry_id}/resolve` → mark that row resolved=True; 404 if missing.
  - `POST /api/logs/resolve` with Pydantic v1 body `{"ids": [int, ...]}` →
    bulk update matching ids; return count. Empty ids list → `{"resolved": 0}`.
- **Self-heal integration (one-line filter — DO it + test):**
  `current_issue()` and `_count_remaining()` in `selfheal.py` get an extra
  `.filter(LogEntry.resolved == False)` so resolved rows are skipped by issue
  scanning (they must not block the "fully healed → merge" path). Delete-on-success
  logic untouched.

## Tests (backend) — all must pass
New `tests/backend/test_logs_router.py` (TestClient on `backend.server.app`,
conftest gives isolated temp-file DB):
1. DELETE with severity filter deletes only those rows, returns correct N, writes audit row.
2. DELETE without severity + `confirm=all` wipes all, returns N.
3. DELETE without severity and WITHOUT confirm → HTTP 400, nothing deleted.
4. DELETE with `before` cutoff only deletes older rows; invalid `before` → 400.
5. POST resolve single (200, count, row flagged; 404 unknown id) + bulk ids (mixed existing/missing → N = matched).
6. GET default excludes resolved; `show_resolved=true` includes them.
Retention (can live in same file): `purge_expired_logs(days=0/7, explicit session)`
deletes only old rows; invalid Setting value falls back to 7 (monkeypatch
`backend.config.settings.get` or insert a bad Setting row).
Migration safety (extend `tests/backend/test_db_migration.py` style): build a raw
SQLite engine + create `log_entries` WITHOUT the resolved column, insert rows, run
`_ensure_log_entry_resolved_column`, assert column exists, rows intact, old rows read
back with resolved falsy.
Self-heal filter: extend `tests/backend/test_selfheal.py` — resolved warning row is
NOT returned by `current_issue()` and NOT counted by `_count_remaining()`;
unresolved one still is.

## Run
`python -m pytest tests/backend/ -q` — full suite green (baseline 65 passed/1 skipped
+ your new tests). Do NOT commit. Do NOT touch anything outside your write scope.

## Receipt (return to PM)
Files changed per task; migration approach note; test counts; how resolved rows
interact with self-heal now (one-line filter done — confirm); anything deferred.

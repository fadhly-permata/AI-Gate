# Handover: Log cleanup frontend (T2) — fe-dev — 2026-09-07

Owner: @fe-dev. Write scope: `src/frontend/**` (incl. `src/frontend/tests/**`) ONLY.
Read context: this file, `src/frontend/static/index.html` (log window ~:1049-1086),
`src/frontend/static/app.js` (log window block ~:1180-1305, wiring ~:1605-1625,
`formatLogRow`/`buildLogsQuery` ~:449-490), `src/frontend/static/i18n.js`
(EN block ~:261, ID block ~:622, `{n}` placeholder pattern — see `term.session_ended`),
`src/frontend/tests/logwindow.test.js`, `src/frontend/tests/selfheal.test.js`
(fetch-mock style), `src/frontend/vitest.config.js` (include `tests/**/*.test.js`,
run from `src/frontend/`).

Backend contract (implemented in parallel by @be-dev — code against THIS, do not
edit backend):
- `DELETE /api/logs?severity=warning,error` → `{"deleted": N}` 200.
  Wipe-all additionally requires `&confirm=all` (backend 400s without it).
- `GET /api/logs` gains param `show_resolved` (default false = resolved rows
  excluded) and every row now has `"resolved": <bool>` field.
- `POST /api/logs/{id}/resolve` → `{"resolved": N}` 200; `POST /api/logs/resolve`
  body `{"ids":[...]}` → `{"resolved": N}` 200.

## Task 1 — Clear logs (irreversible → confirm)
- `index.html` logwindow-controls: add button `id="logClearBtn"` (fa-trash icon +
  i18n label), after the Refresh button.
- `app.js` log window block, new `clearLogs()`:
  - Scope = current `#logSeverity` value. `"all"` → wipe-all: query
    `?confirm=all`; else → `?severity=<value>` (reuse `buildLogsQuery`-style
    encoding; add new pure helper `buildClearLogsQuery(severity)` exported on
    `window.aigate` for tests).
  - ALWAYS confirm first via `window.confirm(getStr(key))` where key =
    `"log.clear_confirm_all"` (destructive) or `"log.clear_confirm"` (filtered).
    Cancel → no request.
  - `fetch(LOGS_API + query, { method: "DELETE" })` → parse JSON →
    `setLogMsg(getStr("log.cleared").replace("{n}", String(deleted)), "ok")` →
    `loadLogs()`. Failure → error msg in `#logMsg` (non-fatal, ADR-011 style).
- Wire click listener in `init()` next to logRefreshBtn.

## Task 2 — Show resolved toggle
- Button `id="logShowResolvedBtn"` in logwindow-controls (aria-pressed pattern,
  mirror `logWindowToggle`). Persisted in localStorage key
  `aigate.logShowResolved` ("1"/"0"), default "0".
- `loadLogs()`: when on → append `show_resolved=true` to the query (extend
  `buildLogsQuery(severity, limit, showResolved)` — keep old 2-arg calls working;
  update existing tests if signature change breaks them).
- aria-pressed/label reflect state (i18n `log.show_resolved`).

## Task 3 — Resolved row rendering + per-row resolve
- `formatLogRow(entry)`: normalize `resolved` (missing/undefined → `false`).
- `renderLogs(list)`: for `resolved === true` rows → `<tr class="log-row-resolved">`
  + extra badge in severity cell:
  `<span class="badge sev-info log-resolved-badge">` + getStr("log.resolved") + `</span>`.
- Per-row resolve button ONLY for severity warning|error AND not yet resolved:
  small icon button appended to the message cell (fa-check, `class="log-resolve-btn"`,
  `data-id` on it, i18n title/aria `log.resolve`). Resolved/info rows get no button.
  Filter on normalized row.severity (case-insensitive, same logic as severityClass).
- Click delegation on `logTableBody` (rows are re-rendered often): find
  `.log-resolve-btn` → `resolveLog(id)` → `POST /api/logs/{id}/resolve` → on
  success update local row state + `loadLogs()` + msg `log.resolved_n` with count.
- "Resolve all (filtered)" button `id="logResolveAllBtn"` in logwindow-controls:
  POSTs `/api/logs/resolve` with `{"ids":[...]}` of currently rendered
  unresolved warning|error rows (keep last rendered rows in a module var). Then
  reload + success msg. No confirm needed (non-destructive).

## Task 4 — styles.css
- `.log-row-resolved td { opacity: .55; }` (dim), `.log-resolved-badge` margin,
  `.log-resolve-btn` = small ghost/icon button consistent with existing icon-btn.
  Keep it minimal, no layout break in the docked panel.

## Task 5 — i18n.js (EN + ID, match existing key style)
EN: `log.clear` "Clear logs"; `log.clear_confirm_all` "Delete ALL log entries?
This cannot be undone."; `log.clear_confirm` "Delete the selected log entries?
This cannot be undone."; `log.cleared` "Deleted {n} log entries.";
`log.show_resolved` "Show resolved"; `log.resolved` "Resolved";
`log.resolve` "Mark as resolved"; `log.resolve_all` "Resolve all (filtered)";
`log.resolved_n` "Marked {n} entries resolved."
ID: `log.clear` "Bersihkan log"; `log.clear_confirm_all` "Hapus SEMUA log? Tindakan ini
tidak bisa dibatalkan."; `log.clear_confirm` "Hapus log terpilih? Tindakan ini tidak
bisa dibatalkan."; `log.cleared` "{n} log dihapus."; `log.show_resolved`
"Tampilkan yang selesai"; `log.resolved` "Selesai"; `log.resolve` "Tandai selesai";
`log.resolve_all` "Tandai semua selesai (terfilter)"; `log.resolved_n`
"{n} log ditandai selesai."

## Tests (vitest, from `src/frontend/`: `npx vitest run`)
Extend `tests/logwindow.test.js` (it already imports i18n.js + app.js with jsdom).
Mock fetch with `vi.stubGlobal` (copy style from selfheal.test.js). Cover:
1. `buildClearLogsQuery("all")` → `?confirm=all`; `("error")` → `?severity=error`.
2. `formatLogRow` resolved default false + passes through true.
3. renderLogs resolved row gets `.log-row-resolved` + resolved badge; warning row
   (unresolved) gets a `.log-resolve-btn`, info row does not.
4. Clear flow: confirm mocked true → DELETE called with right URL → `#logMsg`
   shows "Deleted N log entries."; confirm false → no request.
5. Show-resolved toggle flips aria-pressed + adds `show_resolved=true` to next
   GET URL (stub fetch, capture URL).
6. Resolve-all button POSTs ids of rendered unresolved warning/error rows.

## Run
`npx vitest run` from `src/frontend/` — full suite green (baseline 442 passed,
23 files + your additions; i18n.test.js may assert key parity EN=ID — keep both
locales in sync). Do NOT commit. Do NOT touch `src/backend/**` or `tests/backend/**`.
Do not change `selfheal.js` (its log feed keeps working — default GET now excludes
resolved rows, which is correct for that feed).

## Receipt (return to PM)
Files changed; test counts; any contract mismatch discovered; deferred items.

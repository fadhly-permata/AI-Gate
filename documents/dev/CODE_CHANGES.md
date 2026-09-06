# Code Changes Register (code ↔ docs alignment)

## 2026-09-07 — Terminal tab auto-close on shell exit + session-ended toast — DONE

Akar masalah "tab gak nutup": backend tidak pernah memberi tahu frontend saat shell
mati → tab jadi zombie view. (Plus: `terminal.js` ter-cache browser tanpa cache-buster,
sehingga perbaikan FE tidak ter-load.) BE terbukti benar via runtime (frame terkirim).

**Kontrak exit (sumber kebenaran):** server kirim TEXT frame `{"type":"exit","code":<int>}`
ke view yang sedang attached, LALU tutup WS (code 1000). Frame TIDAK masuk ring-buffer
replay. FE tangkap frame → tutup tab (tanpa kill-frame balasan, tanpa auto-open).

### `src/backend/terminal/pty.py`
- `PtyProcess` +properti `exit_status` (best-effort baca exit status child; guard).

### `src/backend/terminal/session.py`
- Sentinel `PtyExit(code)` (bukan output terminal) + `notify_exit()` (dorong SATU
  sentinel ke queue view aktif, at-most-once per view via `exit_view`), `resolved_exit_code()`
  / `read_exit_code()`, `close_view()`. Reader thread memanggil `notify_exit()` saat PTY
  mati. `try_reap`/`reap_idle` kini REAP sesi exited walau masih attached (tutup view);
  sesi hidup yang cuma detached tetap tidak disentuh (regression guard).

### `src/backend/terminal/router.py`
- `_pump()` kenali item `PtyExit` → kirim `exit_frame(code)` = `json.dumps({"type":"exit","code":int(code)})`
  lalu `websocket.close(1000)`. Handler reclaim sesi setelah exit.

### `tests/backend/test_terminal_exit.py` (baru)
- 17 test: exit → satu frame `{"type":"exit","code":N}` + close 1000; frame tidak
  ke-replay; reaper reap exited-but-attached; live-but-detached tetap aman.

### `src/frontend/static/terminal.js`
- `handleWsMessage`: guard `tab.userClosed`; cabang `info.type==="exit"` →
  `closeTab(tab.id,{exited:true})`. `closeTab(id,opts)`: `opts.exited` = TANPA kirim
  kill-frame + TANPA auto-open tab baru (empty state); `removeSavedTabId` dipanggil.

### `src/frontend/static/i18n.js`
- Key `term.session_ended` (EN + ID) untuk toast penanda sesi selesai.

### `src/frontend/static/styles.css`
- Gaya toast `term.session_ended`.

### `src/frontend/static/index.html`
- Cache-buster `?v=20260906` pada aset statik (terminal.js dkk) supaya versi baru
  selalu ter-load (akar bug: cache lama tanpa bust).

### `src/frontend/tests/terminal_exit.test.js` (baru)
- 14 test: exit frame → tab hilang, tanpa kill-frame, tanpa auto-open, forget id.

**Verification.** PM re-ran: backend terminal **65 passed / 1 skipped** (skip =
`test_terminal.py:59` native PTY dep); frontend **442 passed (24 files)**, no regresi.
Kontrak BE↔FE dicocokkan di kode nyata (frame dulu → close 1000). Belum di-exercise
end-to-end live di browser.

---

## 2026-09-06 — CLI Tools combobox: two-level (provider → model-prefix) grouping — DONE

### `src/frontend/static/combobox.js`
- Added `subGroupBy` (`null|prefix|group`). Options carry `_sub`; `setOptions` derives it (prefix → `familyOf(label)` unless `subGroup:false`; group → `m.subGroup`). `subGroup:false` opt-out keeps an option flat.
- Two-level render: main group header → flat items (`_sub==null`) directly under it → sub-group headers with nested items. New `collapsedSub`/`trackedSub` Sets (composite `group\u0001sub`) for per-sub collapse (default collapsed, persists across refresh, auto-expand while searching). `toggleSub(group,sub)`; click/Enter/Space on `.aigate-combo-subgroup` toggles.

### `src/frontend/static/clitools.js`
- `cliModelCtl()` adds `subGroupBy:"prefix"`. `fetchModels()` sets combo items `subGroup:false` (flat under `Kombo/Combos`); provider items auto sub-group by model-name prefix. Values stay full `provider:/combo:` ids.

### `src/frontend/static/styles.css`
- Added `.aigate-combo-subgroup` (indented header + caret) and `.aigate-combo-opt.aigate-combo-opt-sub` (44px indent).

### `src/frontend/tests/combobox.test.js`
- Added 6 tests: default-collapsed two-level, `Kombo/Combos` flat, provider→prefix sub-groups, expand-sub reveals items, keyboard toggle, search auto-expands.

**Verification.** PM re-ran vitest: **415 passed (21 files)**. No backend changes.

---

## 2026-09-06 — Model dropdown: indent + collapsible groups + fixed flexible positioning — DONE

### `src/frontend/static/combobox.js`
- Group child options indented (render unchanged; CSS does indent).
- Collapsible groups: `collapsed` Set, default all collapsed; click/Enter/Space on a `role="button"` group header toggles (keeps state across `setOptions` refreshes via a `tracked` Set). While a search query is active, all groups auto-expand so matches show. Headers always render (even when collapsed) so they stay expandable. `renderOptionsHtml()` iterates the full group list; `buildRenderGroups()` removed.
- `position()` rewritten to `position: fixed`, viewport-anchored to the input rect; opens below when there is room, above otherwise; `maxHeight` capped to `min(320, availableSpace)` so it never overflows. Adds `scroll`(capture)+`resize` listeners on open, removed on close/destroy. Fixes the panel being clipped by `.modal { overflow-y:auto }`.

### `src/frontend/static/styles.css`
- `.aigate-combo-list` now `position: fixed` (geometry set inline by JS).
- `.aigate-combo-opt` indented `padding-left: 28px`; `.aigate-combo-group` `cursor:pointer`, caret via `::before` (▾ expanded / ▸ collapsed).

### `src/frontend/tests/combobox.test.js` / `combos.test.js`
- Added tests: collapsed-by-default, click/keyboard toggle, auto-expand on search, persist across refresh, fixed positioning (above/below/cap/scroll-reposition/detach). `combos.test.js` updated for collapsed-default.

**Verification.** PM re-ran vitest: **409 passed (21 files)**. No backend changes.

---

## 2026-09-06 — Model dropdown: in-panel search + grouping — DONE

### `src/frontend/static/combobox.js`
- Added `searchInside` (search `<input>` as the FIRST panel `<li>`; two-way mirrored with the top value input; focused + cleared on open; committed value restored on cancel).
- Added `groupBy` (`none|prefix|group`) + `groupOrder` (pinned order, rest alpha). Prefix uses `familyOf()` (`deepseek-v1`+`deepseekv2`→`Deepseek`; `gpt-4o`→`Gpt`). Group headers are `role="presentation"`, skipped by keyboard nav.
- No-match + custom: appends a synthetic "Use \"%s\" as custom model" option so free text survives (ADR-011).

### `src/frontend/static/combos.js`
- `#comboMemberModel` combobox now `searchInside:true, groupBy:"prefix"` (Kombo page groups by model prefix).

### `src/frontend/static/clitools.js`
- `#cliModel` converted from native `<select>` to the combobox (`searchInside:true, groupBy:"group", groupOrder:["Kombo/Combos"]`).
- `fetchModels()` maps `/v1/models`: `combo:` → group `Kombo/Combos`; provider → group `owned_by`; value stays the full `provider:/combo:` id so `launch()` posts it verbatim.

### `src/frontend/static/index.html`
- Replaced `<select id="cliModel">` with combobox markup (`cliModel` input + `cliModelList` ul).

### `src/frontend/static/styles.css`
- Added `.aigate-combo-searchrow` (sticky top search row), `.aigate-combo-search`, `.aigate-combo-group` (non-selectable header).

### `src/frontend/static/i18n.js`
- Added `combobox.use_custom` + `combobox.group_combos` (en + id).

### `src/frontend/tests/combobox.test.js`
- Added 6 tests (prefix grouping, group+groupOrder pin, in-panel search filter+mirror, search focus/clear on open, no-match custom click, custom via Enter).

**Verification.** PM re-ran vitest: **401 passed (21 files)**. No backend changes.

---

## 2026-09-06 — Terminal toolbar icon-only main buttons — DONE

### `src/frontend/static/index.html`
- Removed visible Paste, Settings, and Full text from main dropdown buttons; submenu labels remain.

### `src/frontend/static/styles.css`
- Sized and centered icon-only main split buttons.

### `src/frontend/tests/terminal_toolbar.test.js`
- Added assertions for icon-only controls, accessibility labels, titles, and icon classes.

**Verification.** Vitest 395 passed (21 files); syntax and diff checks passed.

---

## 2026-09-06 — Terminal toolbar grouped dropdowns — DONE

### `src/frontend/static/index.html`
- Reordered terminal controls into three labeled dropdown groups: Paste, Settings, Full.
- Moved TUI Passthrough and Keep Screen On into Settings menu; retained two paste choices and two fullscreen choices.

### `src/frontend/static/terminal.js`
- Generalized dropdown setup and actions for Settings menu.
- Synchronized TUI, wake-lock, Full Page, and Fullscreen menu ARIA states.

### `src/frontend/static/i18n.js`
- Added labels for grouped toolbar controls and Paste normal action.

### `src/frontend/tests/terminal_layout.test.js`
- Verified exact three-group order and absence of standalone controls.

### `src/frontend/tests/terminal_toolbar.test.js`, `src/frontend/tests/views.test.js`
- Updated toolbar fixture IDs and behavior coverage.

**Verification.** Vitest 394 passed (21 files); syntax checks, diff check, and HTML artifact scan passed.

---

## 2026-09-06 — Tooltip lifecycle and independent fullscreen states — DONE

### `src/frontend/static/app.js`
- Icon popovers now auto-close 2 seconds after tap/click; timer is cleared on replacement and close events.

### `src/frontend/static/terminal.js`
- Added explicit `fullPageSelected` state and preserved it across true browser fullscreen entry/exit/failure.
- Synchronizes Full Page and true Fullscreen `aria-pressed`/`aria-checked` independently.

### `src/frontend/static/styles.css`
- Active blue styling applies only to controls with their own active ARIA state; caret has no active mode styling.

### `src/frontend/tests/terminal_toolbar.test.js`
- Added coverage for independent visual/accessibility states and request-failure restoration.

**Verification.** Vitest 394 passed (21 files), terminal toolbar 62 passed; syntax and diff checks passed.

---

**Purpose.** Every source-code change is logged here **per file** so the code and
the project documents never drift apart ("align"). This is the audit trail that
ties a running change back to the spec it implements.

**Rule.** Maintained per `documents/pm/OPERATING_RULES.md` **R22** — PM records each
verified code change here (newest section on top). Changes are logged AFTER they
are verified (tests run), not before. Environment tweaks outside the repo are
noted under "Environment (outside repo)". Not-yet-done work is marked **PENDING**
and completed when it lands.

---

## 2026-09-06 — Terminal toolbar markup repair — DONE ✅

**Goal.** Remove accidental tool-call text rendered beside the fullscreen icon and restore valid terminal toolbar HTML.

### `src/frontend/static/index.html`
- Replaced corrupted fullscreen split-button opening tag with valid `<span class="term-split" id="termFullscreenSplit">` markup.
- Preserved Keep Screen On control and `fa-mobile-screen-button` icon.

**Verification.** Final HTML read directly; frontend scan found no tool-call artifacts; `git diff --check` and JS syntax checks passed.

---

## 2026-09-06 — Side menu grouped by user needs — DONE ✅

**Goal.** Make sidebar navigation easier to scan by grouping items according to user needs without changing routes.

### `src/frontend/static/index.html`
- Grouped navigation into Gateway Setup, Operations, Insights, and System.
- Preserved all existing `data-view` values.
- Added accessible group labels and localized `aria-label` values for collapsed icon-only navigation.

### `src/frontend/static/styles.css`
- Added group headings and separators.
- Collapsed sidebar hides group text while retaining icon navigation.

### `src/frontend/static/i18n.js`
- Added EN/ID translations for four group headings.

### `src/frontend/tests/views.test.js`
- Added assertions for grouping order, route preservation, and localization keys.

**Verification.** Frontend Vitest: 21 files, 392 tests passed.

---

## 2026-09-05 — Terminal toolbar: Keep Screen On + Fullscreen/Paste dropdowns — DONE ✅

**Goal.** Three terminal-toolbar features: (1) a **Keep Screen On** toggle using
the Screen Wake Lock API so the tablet doesn't sleep mid-session (prevents the tab
freeze that drops the WS); (2) the **Fullscreen** button becomes a split-dropdown —
default stays "Full Page" (CSS), menu adds TRUE fullscreen (`requestFullscreen`,
F11-style); (3) the **Paste** button becomes a split-dropdown — default stays
normal paste, menu adds "Paste as Code Block" (wrap clipboard in a fenced block).

**Process note.** Two `fe-dev` spawns were interrupted by the flaky connection, but
the diffs landed (verified via markers + `git diff`). PM reviewed the code
line-by-line. A lingering `fe-dev` run (still alive after its receipt was cut) then
fixed the regex-literal typos (a missing closing `/` in `[^}]*\}` → `[^}]*\}/`) that
had desynced the esbuild/node lexer, and restored the "Dropdown CSS contract" block.
PM re-verified: the test file is now stable (md5 unchanged across checks, 0 live
writers). Feature tests authored by `fe-dev` (60 tests).

### `src/frontend/static/terminal.js` (+589, combined with the tab-id work below)
- **Keep Screen On:** `wakeLockSupported(nav)` (secure-context feature-detect),
  state `keepAwake={desired,sentinel,supported}`, `acquireKeepAwake()`,
  `releaseKeepAwakeSentinel()`, `toggleKeepAwake()`, `renderKeepAwake()` (disabled
  render when unsupported), `onVisibilityKeepAwake()` (re-acquire on return),
  `setupKeepAwake()`; intent persisted in `sessionStorage` key
  `aigate.term.keepAwake`.
- **True Fullscreen:** `fsElement()`, `fsSupported()`, `fsCall()`,
  `toggleTrueFullscreen()` (carries the full-page class while in, rolls back on
  exit via `fsRollbackCarried()`), `onFullscreenChange()`, `syncFullscreenMenu()`.
- **Paste as Code Block:** `wrapCodeBlock(text)` wraps the clipboard text between
  two triple-backtick fences with newlines — verbatim, NO added indentation, NO
  trailing newline; `pasteAsCodeBlock()`.
- **Shared dropdown:** `createTermMenu(caret,menu)` (tap-to-open, one-at-a-time,
  tap-outside + Esc + arrow-key focus, idempotent per node), `onDocTapClose`,
  `bindOnce`, `setupControlMenus()`.
- **Defaults preserved:** main `#termFullscreen` → `toggleFullscreen` (full page);
  main `#termPaste` → `pasteActive` (normal).
- **Exports:** test hooks added (`wrapCodeBlock`, `wakeLockSupported`, `_keepAwake`,
  `_toggleKeepAwake`, `_setupKeepAwake`, `_onVisibilityKeepAwake`,
  `_toggleFullscreen`, `_toggleTrueFullscreen`, `_onFullscreenChange`,
  `_fsSupported`, `_fsCarriedFullPage`, `_pasteActive`, `_pasteAsCodeBlock`,
  `_createTermMenu`, `_setupControlMenus`, `_openMenu`).

### `src/frontend/static/index.html` (+61)
- New `#termKeepAwake` toggle button; Fullscreen + Paste converted to split buttons
  with carets (`#termFullscreenCaret`/`#termPasteCaret`) and popover menus
  (`#termFullscreenMenu` → `#termMenuFullPage`/`#termMenuFullscreen`;
  `#termPasteMenu` → `#termMenuPaste`/`#termMenuPasteCode`), with
  `aria-haspopup`/`aria-expanded`/`role=menu`/`menuitemcheckbox`.

### `src/frontend/static/i18n.js` (+22)
- EN + ID keys: `term.full_page`, `term.exit_full_page`,
  `term.fullscreen_unsupported`, `term.fullscreen_menu`, `term.paste_code`,
  `term.keep_awake`, `term.keep_awake_on/off/unsupported/error`.

### `src/frontend/static/styles.css` (+92)
- `.term-split`, `.term-caret`, `.term-menu` (absolute popover, `pointer-events:auto`,
  z-index above the stage), `.term-menu-item` (≥40px touch target), checked +
  disabled states.

### `src/frontend/tests/terminal_toolbar.test.js` (NEW, 60 tests)
- wrapCodeBlock exact string; keep-awake feature-detect + acquire/release/
  re-acquire + disabled-when-unsupported; full-page default toggle; true-fullscreen
  enter/exit + fullscreenchange sync/rollback; paste normal vs fenced (exact);
  dropdown open/close (tap, outside, Esc).
- Includes a "Dropdown CSS contract" block (7 tests) — initially broken by a
  missing regex-closing `/` (lexer desync), fixed by the lingering `fe-dev` run.

### Verification (real, run in this env)
- `node --check src/frontend/static/terminal.js` → OK.
- `cd src/frontend && node node_modules/vitest/vitest.mjs run` → **21 files /
  390 tests passed** (330 prior + 60 new; no regression).
- **Not yet exercised in a real Chrome on the tablet** (R20 gap): wake-lock
  (needs http://localhost or HTTPS), true fullscreen, and the paste fence must be
  confirmed manually.

---

## 2026-09-05 — Terminal session persistence (survive Chrome tab DISCARD) — DONE ✅

**Goal.** The aigate web terminal survived a Chrome tab FREEZE (reconnect reuses
the in-memory `tab_id`) but LOST the session on a tab DISCARD: the renderer is
killed, the page reloads, and `openTab()` minted a fresh `crypto.randomUUID()` →
the backend treated it as a new session → fresh shell + orphaned PTY. Fix =
persist the terminal tab id(s) client-side so a reload REATTACHES to the same
backend PTY.

**Backend contract (unchanged, referenced for alignment).** WS
`/ws/terminal/{tab_id}`; the RAW `tab_id` string is the registry key; reconnect
with the SAME id reattaches + replays the ring buffer; a NEW id spawns a fresh
shell; disconnect ≠ kill (PTY survives up to `terminal_idle_reap_minutes`,
default 60); only `{"type":"close"}` kills. No backend file was touched.

### `src/frontend/static/terminal.js` (+123 / −18)
- **NEW persistence block (L46–102):** `TAB_IDS_KEY="aigate.term.tabIds"`,
  `readSavedTabIds()`, `writeSavedTabIds()`, `addSavedTabId()`,
  `removeSavedTabId()`, `mintTabId()`. Uses **`sessionStorage`** (per-tab;
  survives same-tab reload/discard-restore) — deliberately NOT `localStorage`
  (shared across browser tabs → two aigate tabs would collide on one PTY key).
- **`openTab(id)` (L451):** now takes an OPTIONAL id — reuses a given id
  (reattach), else mints a new one. Non-string arg (a click `Event`) is treated
  as "no id". Double-open guard: a live id → `activate(id)` + return existing.
  Registers the id via `addSavedTabId`. Returned tab shape unchanged.
- **`restoreTabs()` (NEW, L514):** opens one tab per saved id; returns true if
  ≥1 tab restored.
- **`closeTab(id)` (L590):** calls `removeSavedTabId(id)` (L616) AFTER
  `tabs.delete(id)` and BEFORE the last-tab `openTab()`, so a deliberately closed
  tab is never resurrected on reload and the replacement id is persisted.
- **`init()` (L828):** `newTabBtn` / `emptyNewTabBtn` click handlers wrapped so
  the click `Event` is never read as a tab id.
- **`onShow` (L909):** `if (activeId) refitActive(); else if (!restoreTabs()) openTab();`
  — restore-if-present, else first-load behavior. Lazy (no PTY/WS spawned for a
  user who never opens the Terminal view).
- **exports (L928):** added `_TAB_IDS_KEY`, `_readSavedTabIds`, `_restoreTabs`,
  `_mintTabId` (test/introspection hooks).
- **Untouched (verified):** WS protocol, `wireSocket`, `connectSocket`,
  `scheduleReconnect`, `checkLiveness`/`armLiveness`, ping/pong heartbeat,
  backoff, resize, close-frame, swipe/inertia, `launchInNewTab`.

### `src/frontend/tests/terminal_discard.test.js` (NEW, 16 tests)
Harness uses `vi.resetModules()` + re-import per test to simulate a real page
reload (fresh `tabs` Map + `activeId`). Covers:
- (a) `openTab()` persists its minted id; accumulates ids in order, deduped;
  `openTab(id)` reuses the given id; non-string arg still mints fresh.
- (b) restore opens the WS with the PERSISTED id (not a fresh uuid); does not
  also open a fresh tab; idempotent; empty/absent behaves like first load;
  corrupt stored values ignored; a restored tab keeps the FREEZE reattach path.
- (c) `closeTab(id)` removes exactly that id; keeps the "≥1 tab" invariant and
  persists the replacement; a user-closed tab is never resurrected by a reload.
- (d) `openTab()` returns a working tab when `sessionStorage` throws; a failing
  `setItem` (quota) still opens a working tab; without storage, behaves as before.

### Verification (real, run in this env)
- `node --check src/frontend/static/terminal.js` → OK.
- `cd src/frontend && node node_modules/vitest/vitest.mjs run` → **20 files /
  330 tests passed** (incl. `terminal_discard` 16, `terminal_reconnect` 24 — no
  regression). Re-run by PM independently.
- **Not yet exercised end-to-end in a real Chrome discard** (R20 gap) — the
  discard→reload reattach must be confirmed manually on the tablet.

### Environment (outside repo)
- `~/.bashrc` — added an idempotent `termux-wake-lock` auto-acquire block so the
  Termux-hosted aigate server (and its terminal PTYs) are not frozen by Android
  doze when the tablet screen is off. No package installed (binary already
  present). Wake lock also acquired live in the current session (exit 0).

---

## 2026-09-06 — codegraph bug patch (environment, outside repo) — DONE

### Environment (outside repo)
- **colbymchenry/codegraph v1.6.0** (npm global `@colbymchenry/codegraph`) — tool
  semantic code-graph (Rust kernel + bundled Node glibc). Di Termux/Android tool ini
  gagal out-of-the-box karena: (a) shim deteksi `process.platform='android'` → cari
  bundle `codegraph-android-arm64` yg TIDAK ada (404); (b) binary glibc butuh loader
  `/lib/ld-linux-aarch64.so.1` yg gak ada di Termux, padahal loader glibc WORKING ada
  di `/data/data/com.termux/files/usr/glibc/lib/ld-linux-aarch64.so.1` (libc.so.6 valid).
  Tiga patch diterapkan biar jalan:
  1. File global
     `/data/data/com.termux/files/usr/lib/node_modules/@colbymchenry/codegraph/npm-shim.js`
     — baris `var target = process.platform + '-' + process.arch;` diubah jadi
     `var target = 'linux-arm64';` (paksa download bundle linux-arm64 yg valid).
  2. Shebang shim `#!/usr/bin/env node` → `#!/data/data/com.termux/files/usr/bin/node`
     (Termux tidak punya `/usr/bin/env`).
  3. Launcher bundle `~/.codegraph/bundles/linux-arm64-1.6.0/bin/codegraph`: baris
     `exec "$DIR/node" ...` diubah jadi
     `exec /data/data/com.termux/files/usr/glibc/lib/ld-linux-aarch64.so.1 "$DIR/node" ...`
     agar node glibc dieksekusi lewat loader glibc yang ada.
  Tanpa patch ini `codegraph init` gagal total di Termux. Hasil: `codegraph init` di
  project → `.codegraph/codegraph.db`, 121 files / 2,851 nodes / 9,151 edges, 2.0s.
  CATATAN: (1)+(2) ada di global npm package — hilang kalau
  `npm i -g @colbymchenry/codegraph` diulang; (3) ada di cache bundle
  `~/.codegraph/bundles/linux-arm64-1.6.0` — hilang kalau dihapus. Bukan file repo;
  tidak ikut commit. (Catatan lama soal xnuinside/codegraph sudah tidak berlaku — itu
  tool salah yg sudah di-uninstall.)

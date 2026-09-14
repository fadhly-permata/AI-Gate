# Handover: Log Panel — stacktrace auto-collapse fix + icon-only buttons + Developer Mode gating

Owner: fe-dev (scope `src/frontend/**` only: `index.html`, `app.js`, `styles.css`,
`src/frontend/tests/logwindow.test.js`). PM verified everything below with `file:line`
read-only before writing this. Backend needs NO change (see §0).

## 0. Why no backend work
- `dev_mode` already seeded `"false"` at first boot: `src/backend/config/settings.py:35`
  (`DEFAULT_SETTINGS["dev_mode"] = "false"`).
- Already exposed to the frontend: `GET /api/settings` returns the full dict
  (`src/backend/config/settings_router.py:52`). `app.js:397 loadSettings()` already
  fetches it and sets the Settings checkbox (`app.js:410`).
- Therefore: new install ⇒ `dev_mode=false` ⇒ the 3 dev features are hidden with no
  server change. Frontend only has to READ the existing value and gate the UI.

## 1. BUG — stacktrace auto-collapses when expanded (Task 1)
Root cause (proven): `renderLogs()` rebuilds `logTableBody.innerHTML` from scratch
(`app.js:2126-2150`). It is called on every poll: `startLogAutoRefresh()` does
`setInterval(loadLogs, 3000)` (`app.js:2135-2138`) ⇒ `loadLogs` (`app.js:2155`) ⇒
`renderLogs`. Stacktrace is rendered as
`<details class="log-stack"><summary>…</summary><pre>…</pre></details>` (`app.js:2134`)
WITHOUT the `open` attribute. Each 3s rebuild recreates the element closed ⇒ any
expanded trace collapses within 3s.

Fix (preserve open state across re-render, not stop the poll):
- Add module-level `var openStackIds = new Set();`
- In `renderLogs`, add `open` to the `<details>` when `row.id` is in `openStackIds`
  (e.g. `…'<details class="log-stack"' + (openStackIds.has(row.id) ? ' open' : '') + '…'`).
- Add ONE delegated listener on `#logTableBody` (next to the existing resolve-delegate
  at `app.js:2560`) listening for the `<details>` `toggle` event: if the toggled
  element is `.log-stack`, read its row id (put `data-logid` on the `<details>` or
  look up the sibling `.log-resolve-btn[data-id]` / store id on the details) and
  add/remove from `openStackIds`. Keep the auto-refresh running.
- Do NOT change severity/filter/resolve behaviour.

DoD Task 1: expand a stacktrace, let one 3s poll pass, assert it stays `open`;
add/adjust `logwindow.test.js` to assert the `open` attribute is preserved across two
`renderLogs` calls with the id in the set; full vitest green.

## 2. Log Window buttons → icon only (Task 2)
User: on the log panel, replace all button text with icons (mobile readability; text
stacks/overflows on phones). Scope = the 4 buttons in `.logwindow-controls`
(`index.html:1283-1307`). FA glyphs verified present in the LOCAL vendor bundle
(`src/frontend/static/vendor/font-awesome/css/all.min.css`): fa-rotate, fa-trash,
fa-eye, fa-check-double.

- `#logRefreshBtn` (`index.html:1291`): drop `<span data-i18n="term.refresh">Refresh</span>`,
  keep `<i class="fa fa-rotate">`, add `data-i18n-aria="term.refresh"` + `title` (use the
  existing key `term.refresh`, present in all 7 locales).
- `#logClearBtn` (`index.html:1296`): drop `<span data-i18n="log.clear">Clear logs</span>`,
  keep `<i class="fa fa-trash">`, add `data-i18n-aria="log.clear"`.
- `#logShowResolvedBtn` (`index.html:1301`): currently TEXT ONLY (no icon). Add
  `<i class="fa fa-eye" aria-hidden="true"></i>` and drop the `<span>`, add
  `data-i18n-aria="log.show_resolved"`. (Runtime `applyShowResolved()` at `app.js:2099-2109`
  already sets `aria-label`/`title` from `log.show_resolved`, so it stays accessible.)
- `#logResolveAllBtn` (`index.html:1305`): currently TEXT ONLY. Add
  `<i class="fa fa-check-double" aria-hidden="true"></i>`, drop the `<span>`, add
  `data-i18n-aria="log.resolve_all"`.
- Severity filter (`index.html:1284-1290`): keep the `<select>`, but make its visible
  `<label>` text hide on narrow screens (`@media (max-width:600px)`) while keeping
  `aria-label` on the select (reuse key `term.severity`). This avoids the label+select
  wrapping on phones. If you prefer leaving the label as-is, say so — but the 4 buttons
  MUST become icon-only.
- CSS: ensure `.logwindow-controls` wraps without overflow at 375px (icons only, with
  `title`/`aria-label` tooltips). The icon-popover system (`app.js:2262 iconOnlyControl`)
  already shows the accessible name for icon-only buttons.

DoD Task 2: at 375px the 4 buttons render as icons in one tidy row, no overflow, no
wrapped text; `aria-label`/`title` present on all 4; tooltips work; no i18n key added
(reuse existing); vitest green (note `logwindow.test.js:118/210-213` builds minimal
button stubs — keep those IDs, no text assertions may rely on visible text).

## 3. Developer Mode gate — hide 3 features when off (Task 3, NEW UI behaviour)
Behaviour (per user): `dev_mode = true` ⇒ show Log Window, Device Simulation, Self Heal.
`dev_mode = false` ⇒ hide all three. Default after first run = false (already the backend
default; §0). The Settings "Developer Mode" switch itself MUST stay visible (it is the
only way to turn it back on).

Hidden surfaces (file:line):
- Log Window: topbar toggle `#logWindowToggle` (`index.html:78`) + panel `#logWindow`
  (`index.html:1277`).
- Device Simulation: `#deviceTriggerDesktop` sidebar (`index.html:166`) and
  `#deviceTriggerMobile` bottom-nav (`index.html:1423`) — both carry `data-device-trigger`.
  (The `#deviceModal` itself is `hidden` until opened, but also hide it via the same gate
  for safety.)
- Self Heal: `.selfheal-card` inside the CLI view (`index.html:866`).

Implementation:
- Markup default: add `data-devmode="off"` to `<body>` (`index.html:63`). This prevents a
  flash of dev tools before the value is known (matches the false default).
- New helper `applyDevMode(on)` (near the log-window helpers, ~`app.js:2074`):
  `document.body.dataset.devmode = on ? "on" : "off";`
  When off: do NOT start `startLogAutoRefresh()` (skip the pointless 3s `/api/logs` poll);
  when on: start it. (Reference the existing start/stop at `app.js:2235` / `app.js:2574`.)
- CSS (`styles.css`): `body[data-devmode="off"] #logWindowToggle,
  body[data-devmode="off"] #logWindow, body[data-devmode="off"] [data-device-trigger],
  body[data-devmode="off"] .selfheal-card, body[data-devmode="off"] #deviceModal
  { display: none !important; }`. Keep the offline/privacy rule intact (no new CDN).
- Wire it: in `loadSettings()` (`app.js:407-413`) after reading `data`, call
  `applyDevMode(String(data.dev_mode) === "true")`. Also call it in `saveSettings()`
  (`app.js:449-459`) right after applying theme/locale, using `f.dev_mode.checked`, so
  toggling the switch live shows/hides without a reload.
- Boot: `loadSettings()` is already invoked at init (`app.js:547` inside try) and when the
  Settings view opens (`app.js:2447`); reuse that — no second fetch needed.
- Guard for headless tests: the existing `if (typeof fetch === "function")` gate
  (`app.js:2572`) keeps jsdom safe; `applyDevMode` just toggles an attribute.

DoD Task 3: fresh install (dev_mode=false) ⇒ the 3 surfaces are hidden with NO user action;
toggling Developer Mode in Settings shows/hides them live; `body[data-devmode]` reflects the
value; log auto-refresh only runs when on; vitest green; no CDN/assets added.

## File map (all `src/frontend/**`)
- `index.html:63` (body attr), `:78` (log toggle), `:1277` (panel), `:1283-1307` (buttons),
  `:866` (selfheal card), `:166`/`:1423` (device triggers).
- `app.js:2074` area (applyDevMode), `:2126-2150` (renderLogs details), `:2135-2138`
  (interval), `:2235` (start), `:2560` (tbody delegate), `:397-417` (loadSettings),
  `:433-463` (saveSettings), `:547`/`:2447` (boot/settings-view calls).
- `styles.css`: add the `body[data-devmode="off"] …{display:none}` block + narrow-screen
  severity-label hide.
- `src/frontend/tests/logwindow.test.js`: extend for open-state preservation + keep button
  IDs.

## No-regression / constraints
- Scope strictly `src/frontend/**`. Do NOT touch `src/backend/**`, other views, i18n key sets.
- Reuse EXISTING i18n keys (`term.refresh`, `log.clear`, `log.show_resolved`,
  `log.resolve_all`, `term.severity`) — do not add keys.
- FA glyphs restricted to ones verified in the local vendor CSS (fa-rotate, fa-trash,
  fa-eye, fa-check-double) — no new icon font, no CDN (G3).
- After edits, bump the `?v=` cache-busters in `index.html` for any changed `.js`/`.css`
  (`styles.css?v`, `app.js?v`) per prior lessons (G3).
- Return a receipt: files changed, decisions, open questions.

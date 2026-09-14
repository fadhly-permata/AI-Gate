# Handover — Device Simulation → Modal Preview + Settings UX fix (2026-09-13)

> **SUPERSEDED (2026-09-13 10:zz) — JANGAN pakai diagnosis di berkas ini.** Blok "Context" di bawah
> menyebut settings "gak responsif" = re-render 26 CSS rule + terminal reflow = **FABRIKASI PM**: user tidak
> pernah bilang "lemot/laggy"; kata aslinya "gak responsif" + "aneh/berantakan" = responsive-design + layout,
> BUKAN performa. Aturan baru **F5** (`documents/pm/OPERATING_RULES.md`) melarang pola ini. Isi yang masih sah
> = denah device-sim→modal (kontrol di atas link Repo + modal preview). VERSI KERJA =
> `handover-20260913-settings-responsif-rapi.md` (peta `file:line` asli + Fix A/B/C + DoD). Berkas ini disimpan
> utuh sebagai arsip titik-waktu (A11: blok lama tidak ditulis ulang/dihapus — koreksi lewat banner ini).

## Context (diagnosis — needs confirmation via real-browser profile, DoD)
Settings page reported "gak responsif" + "aneh". Root-cause hypothesis (PM, targeted read):
`applyDevice()` (`src/frontend/static/app.js:63-74`) sets `document.body.dataset.device`,
which flips **26 `body[data-device=...]` rules** (`src/frontend/static/styles.css:718-741` + many
phone-only overrides) across the WHOLE app shell on every select change. The terminal carries a
`ResizeObserver` on `.term-stage` (`src/frontend/static/terminal.js:239` "BUG2", `:1410-1414`) that
refits xterm on any layout change → global reflow/repaint storm on a throttled phone CPU.
Plus the live whole-app shell swap is disorienting ("aneh"). Moving sim into an **isolated modal
preview** removes the live restyle entirely → fixes both.

## file:line map (settings + device-sim)
- Settings view: `src/frontend/static/index.html:175` (page-banner), `:206` settings-card,
  `:228-238` Device Simulation `<select id="setDevice">` + note, `:240-245` Save/msg,
  `:247+` Backup card.
- Settings render logic: `app.js:220` `loadSettings()`, `:236-258` build/PUT body, `:274-301` save.
- Settings CSS: `styles.css:493` `.settings-card{max-width:540px}`, `:495` title, `:501`
  `.settings-form`, `:503` `.form-row`, `:661` `.settings-dev-note`.
- Device sim: `device.js` (ALLOWED=["phone","tablet","desktop"], DEFAULT="desktop");
  `app.js:53-58` deviceAttr wrapper, `:63-74` applyDevice sets body class + syncs bottom-nav;
  `app.js:2243-2251` change handler (persists DEVICE_KEY).
- GitHub icon link: `index.html:162-169` `.sidebar-footer` `<a href=github fa-github>` (desktop);
  `index.html:1381` `.bn-item` in `.bottom-nav` (phone).
- Existing modal primitive (REUSE): `.modal-overlay` + `.modal role="dialog" aria-modal="true"
  aria-labelledby` (e.g. `index.html:917-919` provModal, `:1002` accModal, `:1058`, `:1081`,
  `:1092`, `:1195`, `:1229`, `:1334`). Toggled via `el.hidden=false/true`. CSS `styles.css:1089-1120`.
  NOTE: existing modals have NO focus-trap + NO global ESC-to-close (only popover/lang ESC).
  i18n keys already exist: `settings.device_sim/phone/tablet/desktop/note` ×7 dicts.

## Goal
1. Investigate non-responsiveness with a REAL browser profile (Chromium/Playwright) — confirm the
   global `data-device` restyle + terminal refit is the cost; report evidence (`file:line` + ms).
2. Relocate the device-simulation CONTROL from the settings form to ABOVE the GitHub icon link
   (desktop: `.sidebar-footer`, `index.html:162`; phone: `.bottom-nav`, `:1381`). Default per D2;
   confirm with user at ACC.
3. Selecting a mode opens an ACCESSIBLE modal (reuse `.modal-overlay`/`.modal`, add focus-trap +
   ESC-to-close + aria) rendering a LIVE preview at that device viewport:
   phone 375×667, tablet 768×1024, desktop 1280×800 (fe-dev finalizes). Recommended: same-origin
   `<iframe>` to app root with `body[data-device]` applied inside the frame (isolated, no live
   app restyle). Fraud-check: do NOT keep `applyDevice()` flipping the live app body.
4. Review + improve settings page layout/spacing/visual hierarchy; stay in the app design system
   (tokens `--panel/--panel-border/--radius/--shadow/--accent/--muted`). Keep `.settings-card`
   consistent.

## Scope (fe-dev ONLY — strict)
- WRITE: `src/frontend/static/index.html`, `src/frontend/static/app.js`,
  `src/frontend/static/styles.css`, `src/frontend/static/device.js` (if dims move there),
  `src/frontend/static/i18n/*.js` (add ≤2 new keys, mirror to all 7 dicts — parity guard
  `tests/.../i18n.test.js` must pass), `tests/frontend/**` (add/adjust tests).
- READ: `documents/pm/**`, `src/frontend/static/terminal.js` (to confirm refit cost only — DO NOT
  edit terminal.js), `src/frontend/e2e/**`.
- NEVER touch `src/backend/**`, other agents' scopes, `.env`.

## Definition-of-done (incl. G3)
- Real-browser evidence captured: before/after profile shows the live-app restyle is gone and the
  settings page is responsive (no jank) on a throttled-CPU run (Playwright `android.mjs` / smoke).
- Device-sim control sits above the GitHub link on desktop sidebar + phone bottom-nav.
- Selecting phone/tablet/desktop opens the modal preview; modal is focus-trapped, closes on ESC +
  backdrop + Close button, `role="dialog" aria-modal="true"` labelled, iframe shows live app at the
  device viewport; selecting another mode swaps the preview in-place.
- Changing device NO LONGER restyles the live app shell (the root cause is removed).
- Settings page layout reviewed/improved, design-system consistent, no new hardcoded colors.
- Vitest suite green (`node node_modules/.bin/vitest run`), i18n parity guard green, e2e smoke green.
- Feature exercised for REAL in a browser (G3), not just green tests — log the run.
- Returns a RECEIPT (files changed, decisions, open questions) — PM writes the report.

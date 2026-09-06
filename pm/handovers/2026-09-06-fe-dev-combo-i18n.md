# HANDOVER — fe-dev — Localized combo group header: harden + close test gaps
Date: 2026-09-06 · Owner: fe-dev · Requester: PM (routing rule R29)

## Goal
The hardcoded bilingual group literal `"Kombo/Combos"` in the CLI Tools model picker
was ALREADY replaced by an i18n lookup (`combobox.group_combos` → "Combos" EN /
"Kombo" ID) plus a `setGroupOrder()` re-pin hook. PM audited that diff and accepted it
functionally. Your job = **harden it so it provably scales to any future locale**
(zh, hi, …) and **close the coverage gaps**. Do NOT redesign the fix.

## Context (from PM audit — verified, do not re-audit)
Already changed (uncommitted; suite green **422 passed / 22 files**):
- `src/frontend/static/clitools.js` — `comboGroupName()` = `getStr("combobox.group_combos")`;
  used at combobox creation (`groupOrder:[comboGroupName()]`) and in `fetchModels()`;
  exposed via `window.aigate.cliTools._test.comboGroupName`.
- `src/frontend/static/combobox.js` — new controller method `setGroupOrder(names)` (~line 713).
- `src/frontend/static/i18n.js` — `combobox.group_combos` = `"Combos"` (en ~193) /
  `"Kombo"` (id ~529); `window.LANGS` registry (en, id) at end of file.
- `src/frontend/tests/clitools.test.js` — 3 tests on `comboGroupName()` (en / id / never-combined).

PM facts:
- Only `clitools` passes `groupOrder`; the other combobox consumers (`app.js:534`,
  `combos.js:237`) do not use groups → no sibling bug.
- `.modal-overlay` is `position:fixed; inset:0; z-index:100`, so the header language
  dropdown is NOT reachable while the launch modal is open → no live-switch staleness in
  that path; `fetchModels()` re-resolves the label and re-pins on every modal open.

## Work items (all inside `src/frontend/**`)
1. **LOCALE-PARITY GUARD test** — this is the real answer to "what about Chinese/Hindi".
   Iterate `window.LANGS` and assert, for EVERY registered locale:
   - a. the locale dictionary exists in `window.I18N`;
   - b. `combobox.group_combos` is defined **in that dictionary** (not merely inherited via
     `getStr`'s EN fallback), and is a non-empty string;
   - c. the value does **NOT** contain `"/"` (the bilingual-combined anti-pattern that
     caused this bug);
   - d. the registry entry's `nameKey` (`lang.<code>`) resolves in its own dictionary.
   The guard must **fail loudly** if someone adds `{code:"zh"}` to `window.LANGS` without
   the dictionary block. Prove it in-test (e.g. run the parity helper against a synthetic
   locale fixture and assert it reports the missing key) — do NOT permanently pollute
   `window.LANGS`.
2. **RE-PIN coverage** — `setGroupOrder` currently has ZERO direct tests:
   - Combobox test: `groupBy:"group"` + `groupOrder:["Kombo"]`, options with group `"Kombo"`
     plus two provider groups → assert the `"Kombo"` header renders FIRST.
   - Runtime re-pin: create with `groupOrder:["Combos"]`, call `setGroupOrder(["Kombo"])`,
     then `setOptions` with a `"Kombo"` group → assert `"Kombo"` is pinned first.
3. **STALE FIXTURE CLEANUP** — `src/frontend/tests/combobox.test.js` still uses the literal
   `"Kombo/Combos"` as a group fixture (~lines 256, 260, 263, 267, 479, 488, 496, 504, 509,
   512, 515, 516, 517, 519). Rename to a neutral token (e.g. `"Combos"`) keeping assertions
   equivalent, so a repo-wide grep for the removed bug string only hits the anti-leak
   regression in `clitools.test.js` plus documents/history.
4. Keep `comboGroupName()` as the **single source** (DRY). Do not duplicate the i18n key
   string across production sites.

## Constraints
- Vanilla JS, no build step (R13). Match each file's existing IIFE/style.
- DRY / KISS / SOLID / YAGNI (R25): no new abstraction beyond the parity guard.
- **WRITE ONLY: `src/frontend/**`** (production + `src/frontend/tests/**`). Never write
  `documents/**`, `pm/**`, `src/backend/**`. Do NOT change the existing
  `combobox.group_combos` values ("Combos"/"Kombo") — accepted as-is.
- Do NOT run any state-changing git command (add / commit / stash / checkout / restore).
  PM owns commits (R21).
- Run tests FROM `src/frontend` with: `node node_modules/vitest/vitest.mjs run`
  (the vitest bin shebang is broken on Termux; do NOT use `npx vitest`).

## Definition of done
- Full frontend suite green including your new tests; report exact pass + file counts.
- Parity guard exists and demonstrably catches a locale registered without
  `combobox.group_combos`.
- `setGroupOrder` has at least one direct test.
- No `"Kombo/Combos"` literal left anywhere in `src/frontend/static/**`.
- Return a **receipt**: files changed with +/- line counts, decisions taken, open
  questions / follow-ups.

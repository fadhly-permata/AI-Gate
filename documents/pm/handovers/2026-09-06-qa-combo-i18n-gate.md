# HANDOVER — qa-engineer — Quality gate: localized combo group header
Date: 2026-09-06 · Owner: qa-engineer · Requester: PM

## Goal
Independently verify (do not trust the implementer's word) that the CLI Tools model
picker's combo group header is now fully localized and that the fix **scales to any
future locale**. Produce a written quality-gate report. You do NOT fix code — you
verify, and file bugs.

## Context
- Original bug: the group header rendered a hardcoded bilingual literal `"Kombo/Combos"`
  instead of a locale-appropriate label. Fix (already applied + hardened by fe-dev):
  label resolves via `getStr("combobox.group_combos")` → `"Combos"` (en) / `"Kombo"` (id);
  `combobox.js` gained `setGroupOrder()` so the pinned group is re-resolved per fetch.
- Read `documents/pm/handovers/2026-09-06-fe-dev-combo-i18n.md` for the intended scope, and
  `documents/pm/memory-bank.md` for project rules context.
- fe-dev's receipt will be summarized by PM in this session; verify the CODE, not the claim.

## Checks to perform (all read-only on src/**)
1. **Literal leak:** repo-wide grep for `Kombo/Combos` under `src/**`.
   Expected: ZERO hits in `src/frontend/static/**`. Hits in `src/frontend/tests/clitools.test.js`
   are intentional (anti-leak regression). Anything else = bug.
2. **Locale parity:** for every entry in `window.LANGS`, assert the dictionary in
   `window.I18N` exists and defines `combobox.group_combos` locally (not via fallback),
   non-empty, and without a `"/"`. Also report the FULL en↔id key-parity delta (keys
   present in one and missing in the other) for the whole dictionary — this is the
   mechanism that makes adding Chinese/Hindi safe.
3. **Behavioral pin:** verify a test exists proving the localized group stays pinned
   FIRST (both at creation and after `setGroupOrder()`). If missing → bug.
4. **Mutation check of the parity guard:** prove the new guard actually FAILS when a
   locale is registered without the key. If your write scope blocks you from doing this
   inside `src/frontend/tests/**`, do it in your own scope or via a throwaway script under
   `.opencode/reports/` and record exactly what you ran. If you cannot run it at all,
   record it as a VERIFICATION GAP in the report — do not silently pass.
5. **Suite:** run the full frontend suite from `src/frontend` with
   `node node_modules/vitest/vitest.mjs run` (vitest bin shebang is broken on Termux —
   do NOT use `npx vitest`). Report exact test + file counts and every failure.
6. **R24 markup artifact scan:** inspect `src/frontend/static/index.html` and the
   combobox panel output for leaked tool-call/code artifacts (e.g. `tsoassistant`,
   `recipient_name`, `functions.`, raw JSON, `undefined`, `[object Object]`).
   Unit-green does not mean markup-clean.

## Constraints
- **WRITE ONLY:** `tests/**` outside `src/frontend/**` and `src/backend/**` (those dirs
  belong to fe-dev/be-dev — do NOT edit them), plus `.opencode/reports/**`.
- Never edit production source. Findings go in the report; real defects go through
  `/log-bug` into `documents/pm/bugs.md`.
- Do NOT run state-changing git commands. PM owns commits.
- Quality gate must include the DRY/KISS/SOLID/YAGNI principle review
  (`.opencode/rules/code-quality-principles.md`) on the changed frontend files.

## Definition of done
- Report written to `.opencode/reports/2026-09-06-combo-i18n-qa.md` with: verdict
  (PASS / PASS-WITH-FOLLOW-UPS / FAIL), each check above with evidence (command + output),
  test counts, and any bugs filed.
- Return a **receipt**: report path, verdict, bugs filed, verification gaps.

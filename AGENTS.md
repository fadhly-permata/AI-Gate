# aigate — Project Instructions (auto-loaded every session)

## HARD RULE — every request routes through @ProjectManager FIRST

Non-negotiable. Violated repeatedly. Read before acting.

1. **ALL** user input — questions, bugs, features, research, refactors, tiny edits,
   "kenapa"-nya, "gimana"-nya — goes to **ProjectManager** FIRST. Main thread MUST NOT
   implement, edit, or investigate-to-fix on its own.
2. Main thread's only allowed direct actions: call `@ProjectManager` (Task tool); pure
   meta/ops about opencode itself when explicitly asked. Anything touching `src/**`,
   `tests/**`, `documents/**`, or running a fix = PM's job.
3. Do NOT write code, edit files, run the app's tests, or "just quickly fix" in the main
   thread — even if trivial or half-done.
4. Work already landed in main thread by mistake: stop, hand to **@ProjectManager** to audit
   the diff, accept/re-work, delegate to the owning specialist, record it (RULES A1 ayat 3).

### Why this file exists
`documents/pm/**` is NOT auto-loaded — only `AGENTS.md` is. Rules that live only there never
reach the executor, so the same mistakes repeat. This file closes the gap for the rules that
must never be missed. `documents/pm/OPERATING_RULES.md` is injected via `opencode.json` →
`instructions`, so the full set is present without relying on anyone remembering to read it.

## ALWAYS-ON RULES (index; full text = `documents/pm/OPERATING_RULES.md`)

1. Route ALL user input to @ProjectManager first. Main thread never implements. [A1]
2. Question != command. Asked -> answer only. No edit, commit, PR, label, spawn until told. [D1]
3. Commanded task -> run without asking. Ambiguity -> pick default, log it. Stop only for
   irreversible/unsafe. [D2]
4. PM never writes `src/` or `tests/`. Delegate to specialist: goal, `file:line` map, scope,
   definition-of-done. [A2]
5. Each agent writes only its own scope. Roster: `.opencode/rules/agent-boundaries.md`. [A3]
6. No new file/folder at repo root. Docs -> `documents/`. Artifacts -> `.opencode/`. Reports ->
   `.opencode/reports/[yyyymmdd]/[type]/[hhmm]_[slug].md`. [B1-B5]
7. Every technical claim needs proof: `file:line`, URL, or user confirmation. External facts ->
   2 independent sources. [F3 · `.opencode/rules/no-hallucination.md`]
8. Find code location via graph channel first if installed; else targeted read. Never broad repo
   grep. [C4 — graph channel not installed yet: conditional, do not fake it]
9. Never kill/restart/pkill aigate, uvicorn, or the parent process. Compare `ps -o lstart` vs file
   mtime, report; USER decides restart. [J6]
10. Agent credentials: `.env` only. Never print values, never create a new credential store,
    never commit `.env`. Product plaintext-in-DB secrets are intentional [J3] — do not "fix" them.
    Before claiming "cannot / no access": read `.opencode/rules/*.md` + `.env` first. [J5]
11. Git: checkpoint at task start; commit per feature, never `git add -A` across features; log
    code changes per-file in `documents/dev/CODE_CHANGES.md`. [H1-H3]
12. Done only after the feature is exercised for real. Green tests != usable app. Vendor assets
    local, no CDN. [G3]

Not rules (canonical homes, referenced above): `.opencode/rules/` — language, secrets,
task-report, commands, no-hallucination, agent-generation, agent-boundaries,
parallel-sequential, request-routing, code-quality-principles, tools-scripts.

Rule gate after editing any rule file: `python3 .opencode/tools/governance/rules-index.py`
(exit 0 required). Old rule text (R1–R52) = `documents/pm/archive/OPERATING_RULES-v1-52rules.md`.

## Language
`.opencode/**`: English caveman ultra. `documents/**/*.md`: Indonesian caveman ultra.
Reports `.opencode/reports/**`: Indonesian formal. User talk/confirm: Indonesian casual, full
sentences, no abbreviations, non-IT clear. Terse never cuts a mandatory format. [I7]

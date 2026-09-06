# aigate — Project Instructions (auto-loaded every session)

## HARD RULE — every request routes through @ProjectManager FIRST

This is non-negotiable and has been violated repeatedly. Read before acting.

1. **ALL** user input in this repo — questions, bugs, features, research, refactors,
   tiny edits, "kenapa"-nya, "gimana"-nya — goes to the **ProjectManager** sub-agent
   FIRST. The main thread MUST NOT implement, edit, or investigate-to-fix on its own.
2. The main thread's ONLY allowed direct actions:
   - Calling `@ProjectManager` (via the Task tool) to own/decompose/delegate the request.
   - Pure meta/ops about opencode itself (this file, agent config) when explicitly asked.
   Anything that touches `src/**`, `tests/**`, `documents/**`, or runs a fix = PM's job.
3. **Do NOT** write code, edit files, run the app's tests, or "just quickly fix"
   in the main thread. Even if the fix looks trivial or already half-done.
4. If work already landed in the main thread by mistake (a violation): do NOT keep
   going. Hand it to **@ProjectManager** to audit the diff, decide accept/re-work,
   delegate any remaining work to the owning specialist, and record it (R29 ayat 3).

### Why this file exists
The routing rule lives in `pm/OPERATING_RULES.md` (R29), but the main thread does
NOT auto-load `pm/**` — it only auto-loads `AGENTS.md`. So the rule never reached
the executor and the mistake kept recurring. This file closes that gap: it is read
at the start of every session in this project.

### Source of truth
Full rule + rationale: `pm/OPERATING_RULES.md` → **R29** (and R21: PM delegates,
never implements). PM owns `pm/`; specialists own their scoped files. Main thread
owns NOTHING here except routing.

## Language
Match the user. User writes Indonesian casual → reply Indonesian casual.

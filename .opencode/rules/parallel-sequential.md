---
name: parallel-sequential
description: >
  For tasks that are large, big, or long-running, or that need multiple agents,
  the PM must offer the user a choice between parallel and sequential execution
  BEFORE starting. The choice persists for the session; re-ask on a new session.
---

# Parallel vs Sequential Offer

When a task is estimated to be large / multi-part / long-running, OR it requires
spawning 2+ sub-agents (multi-agent), the PM MUST pause and offer the user a
choice BEFORE executing.

This is an explicit EXCEPTION to R9 (no-confirmation policy): the execution-mode
decision for multi-agent work must come from the user, not a PM default.

## When to trigger
- Task has 3+ independent subtasks.
- Task touches multiple modules or agents.
- Estimated work spans many steps or a long session.
- Task requires spawning 2+ sub-agents (e.g. be-dev + fe-dev).
- User explicitly asks "cepetin" / "barengan" / "sekalian".

## What to offer (Indonesian casual, non-IT)
- **Paralel**: "Kita kerjakan barengan. Lebih cepat, tapi hasil tiap bagian
  perlu direview dan digabung di akhir."
- **Sekuensial**: "Kita urut satu-satu. Lebih lambat, tapi tiap langkah
  selesai & rapi dulu sebelum lanjut."

## Decision guidance
- Parallel only if subtasks are truly independent AND their file scopes don't
  overlap (see `agent-boundaries.md`).
- Sequential if subtasks depend on each other's output, or shared state.
- Not all work supports parallel (some "providers"/scenarios can't run in
  parallel) — always let the USER decide; don't assume parallel is safe.
- Always state the trade-off (speed vs review/merge cost) before the user picks.
- FORCED sequential: if the chosen subtasks' file scopes overlap or are dependent,
  PM MUST run sequential anyway and explain why to the user (even if they picked
  parallel).

## Session persistence (R16)
- The user's choice is recorded in `pm/state.md` under `multiagent_mode`
  (value: `parallel` | `sequential`).
- Once chosen, REUSE it for every subsequent multi-agent task in the SAME session
  — do NOT ask again within that session.
- NEW session: the choice does NOT carry over. PM MUST ask again at the start of a
  new session (treat `multiagent_mode` as unset if it wasn't recorded for the
  current run). Reset it to `ask` / clear it when a new session begins.
- Also record the choice in `pm/status.md` for traceability.

## Output
After the user chooses (or once a session choice is known), proceed with that mode.

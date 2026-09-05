---
description: Revise only the @documents/ that are affected by the latest user request (auto-detect which)
---
Update only the documents under `documents/` that are actually affected by the
latest user request. Do NOT make the user pick a scope — the command probes each
document and decides what needs changing, because every document has a different
purpose.

Args: $ARGUMENTS

If first arg in `help` / `info` / `information` / `?` -> print usage, stop.

Usage: /revise-docs [note]
  note = free text of the new user request (optional; if empty, read latest
         from conversation / pm/memory-bank.md / pm/status.md)

Procedure (PM executes):
1. Load the request:
   - Use `note` arg, or the latest user message, or pm/memory-bank.md &
     pm/status.md open items.
2. Inventory: glob `documents/**/*.md`.
3. Probe each document — read its purpose and decide impact:
   - PRD  : high-level what/why. Request adds/changes a feature/requirement? -> UPDATE.
   - BRD  : user stories + acceptance criteria. Request changes who/value/stories? -> UPDATE.
   - FSD  : functional flows + IO. Request changes behavior/flow? -> UPDATE.
   - ERD  : data model. Request changes entities/relations? -> UPDATE.
   - TSD  : technical design/ADRs. Request changes architecture/tech choice? -> UPDATE.
   Mark each: UPDATE / SKIP with a one-line reason.
4. Edit ONLY the docs marked UPDATE, strictly inside `documents/`.
5. Keep traceability PRD->BRD->FSD/ERD->TSD consistent (propagate IDs).
6. If a change needs specialist expertise, spawn the matching sub-agent
   (after registered — see R4) or edit directly as PM.
7. Log in pm/status.md + report under `.opencode/reports/`.
8. Print changelog: which docs updated + why, which skipped + why.

Definition of done:
- Affected docs updated; unaffected docs left untouched (reason logged).
- No contradiction between docs.

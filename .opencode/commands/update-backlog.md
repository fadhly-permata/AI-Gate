---
description: Sync/append implementation backlog from PRD (or other spec doc); finds features not yet represented as tasks and adds them as new phase entries. Reusable.
---
Update the implementation backlog from a spec doc.

Args: $ARGUMENTS (optional: "<source_doc> [target_backlog]";
       defaults: documents/PRD.md -> documents/plan/BACKLOG.md)

Usage: /update-backlog [source_doc] [target_backlog]

Procedure (PM executes):
1. Read source doc (default `documents/PRD.md`). Enumerate fitur sections
   (heading level 2/3, e.g. `## 2.x` / `### 2.x.y`) and note which are tagged
   "(adopsi dari 9router)" or explicitly new.
2. Read target backlog (default `documents/plan/BACKLOG.md`). List existing tasks
   (`Bx.y`) and the PRD features they already cover (by keyword/section).
3. Gap analysis: for each PRD feature NOT yet represented by a `[ ]`/`[x]`
   backlog task — prioritize ones tagged "(adopsi dari 9router)" or explicitly
   new — determine:
   - Task description (what to build, referencing the PRD section).
   - Owner: `be-dev` / `fe-dev` / `qa` / `PM` (UI-backed -> `be-dev`+`fe-dev`).
   - `Dep`: task IDs that must finish first (reference existing Fase tasks).
4. Append a new phase (e.g. `## Fase N — <topic>`) OR add under the relevant
   existing Fase, using next free `B`-id. Mark each `[ ]` (todo). Match the
   existing format (status / owner / Dep lines). Keep `R#` rules + ADR refs.
5. Do NOT modify existing `[x]` tasks unless user explicitly asks.
6. Report: list added task IDs + what each covers.

Definition of done:
- Backlog now contains a task for every PRD feature not yet implemented.
- No duplicate of existing tasks.
- Format consistent with the rest of BACKLOG.md.

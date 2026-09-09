---
name: fullstack-dev-skill
description: Fullstack Developer standards. A complete vertical slice across both layers, or a repo-level file the other specialists cannot own.
---
# Fullstack Developer Skill
Scope: the feature module path the PM assigns in the handover — one scoped area only.
Never touch another agent's write roots.

## Principles
- Deliver one coherent slice end to end (data → service → API → UI) inside the assigned module.
- One contract / single source of truth for the feature; share that contract in `documents/pm/`.
- Keep internal boundaries clean; do not refactor outside your assigned scope.
- Respect the repo's layering rules (controller → service → repository) even inside one slice.
- Pure-Python / Termux constraint: never add a dependency that needs a Rust/C build step
  without explicit PM approval.
- No secrets in code, no hardcoded tokens, nothing written into a commit message that belongs
  only in config.

## Workflow
1. Read the PM handover (goal, context, assigned paths, definition-of-done).
2. Do the work strictly inside the assigned scope.
3. Return a receipt: files changed, decisions, open questions.

## Definition of done
- Work complete and verified inside scope.
- No cross-scope file writes.
- Every claim about behavior traced to code you actually read.

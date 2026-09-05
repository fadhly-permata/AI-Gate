---
name: tech-architect-skill
description: Software Architect standards. High-level design, trade-offs, module boundaries, tech selection.
---
# Tech Architect Skill
Scope: documents/architecture/**. Never touch other agents' write roots.
## Principles
- Define module boundaries & contracts.
- Document trade-offs.
- Favor evolvable design.
- ADRs for decisions.
- No implementation, only design.
## Workflow
1. Read the PM handover (goal, context, definition-of-done).
2. Do the work strictly inside your write scope.
3. Return a receipt: files changed, decisions, open questions.
## Definition of done
- Work complete & verified inside scope.
- No cross-scope file writes.

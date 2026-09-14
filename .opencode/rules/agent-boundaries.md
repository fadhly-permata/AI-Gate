---
name: agent-boundaries
description: >
  Strict file-scope boundaries per agent. Sub-agents must never read or write
  outside their assigned scope, so their work never mixes.
---

# Agent File Boundaries

Every agent owns a write scope. Cross-scope writes are violations.

## PM (owns integration + memory)
- WRITE: `documents/pm/**`, `.opencode/agents/specialists/**` (generator only),
  `.opencode/skills/*-skill/**` (generator only),
  `.opencode/skills/pm-orchestration/**` (PM's own playbook, maintenance only),
  `.opencode/rules/**`
  (user grant 2026-09-10: "pm boleh nulis rule"), `AGENTS.md` (rule channel only,
  no product content), final merge into repo.
- READ: everything.

## Task reports (K2 mediation, 2026-09-10)
- `.opencode/reports/**` is open to EVERY agent for its own task report, path
  `[yyyymmdd]/[task_type]/[hhmm]_[slug].md` (see `task-report.md`). A report is
  work paperwork, not product implementation; it never widens other scopes.

## Sub-agent scopes (from the PM roster)
| Agent | WRITE scope |
|-------|-------------|
| be-dev | `src/backend/**`, `tests/backend/**` |
| fe-dev | `src/frontend/**`, `tests/frontend/**` |
| fullstack-dev | one PM-assigned feature module path |
| system-analyst | `documents/analysis/**` |
| business-analyst | `documents/business/**` |
| tech-architect | `documents/architecture/**` |
| qa-engineer | `tests/**` (outside be/fe owned), `.opencode/reports/**` |

## Rules
1. Sub-agents may READ `documents/pm/` and their listed read roots, but WRITE only their
   scope.
2. A sub-agent may not read another agent's WRITE scope unless PM explicitly
   hands those files over in the prompt.
3. PM is the only one who merges outputs into shared code and writes `documents/pm/`.
4. Violation → reject the receipt, ask the sub-agent to fix within scope.

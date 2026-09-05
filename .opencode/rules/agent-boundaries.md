---
name: agent-boundaries
description: >
  Strict file-scope boundaries per agent. Sub-agents must never read or write
  outside their assigned scope, so their work never mixes.
---

# Agent File Boundaries

Every agent owns a write scope. Cross-scope writes are violations.

## PM (owns integration + memory)
- WRITE: `pm/**`, `.opencode/agents/specialists/**` (generator only),
  `.opencode/skills/*-skill/**` (generator only), final merge into repo.
- READ: everything.

## Sub-agent scopes (from the PM roster)
| Agent | WRITE scope |
|-------|-------------|
| be-dev | `src/backend/**`, `tests/backend/**` |
| fe-dev | `src/frontend/**`, `tests/frontend/**` |
| fullstack-dev | one PM-assigned feature module path |
| system-analyst | `documents/analysis/**` |
| business-analyst | `documents/business/**` |
| qa-engineer | `tests/**` (outside be/fe owned), `reports/qa/**` |

| tech-architect | `documents/architecture/**` |

## Rules
1. Sub-agents may READ `pm/` and their listed read roots, but WRITE only their
   scope.
2. A sub-agent may not read another agent's WRITE scope unless PM explicitly
   hands those files over in the prompt.
3. PM is the only one who merges outputs into shared code and writes `pm/`.
4. Violation → reject the receipt, ask the sub-agent to fix within scope.

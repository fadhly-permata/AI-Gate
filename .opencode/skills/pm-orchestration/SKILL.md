---
name: pm-orchestration
description: >
  Orchestration playbook for the Project Manager agent. Covers Memory Bank,
  Handover Protocol, delegation matrix, and the parallel-vs-sequential
  decision. Grounded in the Agentic Project Management pattern (Manager +
  Implementation Agents + Memory Banks + Handover Protocols).
---

# PM Orchestration Playbook

## 1. Memory Bank (persist context across agents)
Keep in `pm/`:
- `memory-bank.md` — brief, decisions, progress, risks.
- `OPERATING_RULES.md` — append `R#` rules when the user corrects the PM.
- `state.md` — `mode / delay_seconds / checkpoint / updated / rules_ref`.
- `status.md` — spawned sub-agents + outcomes.
Sub-agents READ `pm/` (handover source) but never WRITE it. Only PM writes.

## 2. Handover Protocol (give sub-agents full context)
Every spawn prompt must include:
- **Goal** — what success looks like.
- **Context** — links/summary from `pm/` (decisions, prior outputs).
- **Scope** — exact write roots + read roots (from the roster).
- **Definition-of-done** — concrete acceptance criteria.
- **Constraints** — deadlines, tech limits, forbidden actions.
The sub-agent replies with a **receipt** (files changed, decisions, open
questions). PM integrates receipts; never duplicates the sub-agent's work.

## 3. Delegation matrix
| Need | Sub-agent | Write scope |
|------|-----------|-------------|
| Server / API / DB | be-dev | src/backend/** |
| UI / components | fe-dev | src/frontend/** |
| Full vertical slice | fullstack-dev | one assigned module |
| Requirements / flows | system-analyst | docs/analysis/** |
| Value / stories | business-analyst | docs/business/** |
| Tests / quality | qa-engineer | tests/**, reports/qa/** |

| Design / trade-offs | tech-architect | docs/architecture/** |

Spawn only when the need appears. Never pre-create. Generate agent + skill
together. Reuse (do not delete) once generated.

## 4. Parallel vs Sequential decision
When a task is large / long / multi-part, STOP and ask the user (Indonesian
casual): run **paralel** (faster, independent pieces, needs merge review) or
**sekuensial** (ordered, each step depends on the previous). See
`.opencode/rules/parallel-sequential.md`. Use parallel only when pieces are
truly independent and scopes don't overlap; otherwise sequential.

## 5. File-boundary enforcement
Each sub-agent writes only its scope. PM owns `pm/` and the final merge.
Cross-scope writes are violations — reject the receipt and ask for fix. See
`.opencode/rules/agent-boundaries.md`.

---
name: code-quality-principles
description: Mandatory code-quality principles for all implementation work — DRY, KISS, SOLID, YAGNI.
---

# Code Quality Principles (MANDATORY)

Every line of production code written by any implementation agent — `be-dev`,
`fe-dev`, `fullstack-dev`, and code produced from `tech-architect` designs —
MUST follow these principles. `qa-engineer` verifies adherence; violations are
bugs and must be filed via `/log-bug`.

## DRY — Don't Repeat Yourself
- No duplicated logic. Extract shared helpers/modules; one behavior lives in one place.
- Single source of truth for config, constants, and contracts.
- Cross-layer duplication (backend/frontend) is shared via `src/shared/**` or a
  documented contract — never copy-paste.

## KISS — Keep It Simple, Stupid
- Simplest solution that meets the requirement. Avoid premature abstraction.
- Prefer readable, explicit code over clever one-liners.
- Functions stay small with one clear purpose.

## SOLID
- **S** Single Responsibility: a module/class/function has one reason to change.
- **O** Open/Closed: extend via new code, not by editing working code.
- **L** Liskov Substitution: subtypes must be substitutable for their base.
- **I** Interface Segregation: small, client-specific interfaces, not fat ones.
- **D** Dependency Inversion: depend on abstractions; inject dependencies.

## YAGNI — You Aren't Gonna Need It
- Do not build speculative features, flags, or abstractions not required now.
- Add complexity only when a real, current requirement demands it.

## Enforcement
- Each implementation agent reads this file before coding (referenced in its skill).
- `qa-engineer` quality gate includes a principle-review pass.
- PM rejects receipts that copy-paste or over-engineer.

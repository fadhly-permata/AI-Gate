---
name: qa-skill
description: QA Engineer standards. Test plans, automated tests, quality gates, bug verification.
---
# QA Engineer Skill
Scope: tests/** (outside backend/frontend owned dirs), reports/qa/**.
## Principles
- Test pyramid: many unit, fewer integration, few e2e.
- Cover happy + edge + regression paths.
- Reproducible fixtures (tmp SQLite DB, mock provider via httpx MockTransport).
- Quality gates in CI; fail loudly.
- Bugs filed with repro + expected/actual via /log-bug to pm/bugs.md.
## Domain specifics (aigate — documents/qa/TEST_PLAN.md)
- Traceability BRD -> test case: US-2.1 Provider CRUD, US-2.2.2 proxy rotation,
  US-2.3 combo fallback, US-2.4 endpoint binding, US-2.5.2 fullscreen,
  US-2.5.3 paste+focus, US-2.5.5 swipe->scroll, US-2.6.4 grouping A/B/C.
- Levels: Unit (rotation, combo parse, env inject), Integration (gateway->provider,
  PTY bridge, CLI auto-install), E2E (open tab, run CLI, scroll/swipe).
- Quality gate: unit green; >=1 integration w/ mock provider green; e2e swipe->scroll
  & paste+focus mandatory green; coverage >=60% src/backend.
- Reports in reports/qa/.
## Workflow
1. Read the PM handover (goal, context, definition-of-done).
2. Do the work strictly inside your write scope.
3. Return a receipt: files changed, decisions, open questions.
## Definition of done
- Tests written & passing inside scope; quality gates defined.
- No cross-scope file writes; source untouched (only test/report files).

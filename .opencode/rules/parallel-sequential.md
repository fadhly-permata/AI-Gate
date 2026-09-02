---
name: parallel-sequential
description: >
  For tasks that are large, big, or long-running, the PM must offer the user a
  choice between parallel and sequential execution before starting.
---

# Parallel vs Sequential Offer

When a task is estimated to be large / multi-part / long-running, the PM MUST
pause and offer the user a choice before executing.

## When to trigger
- Task has 3+ independent subtasks.
- Task touches multiple modules or agents.
- Estimated work spans many steps or a long session.
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
- Always state the trade-off (speed vs review/merge cost) before the user picks.

## Output
After the user chooses, record the choice in `pm/status.md` and proceed.

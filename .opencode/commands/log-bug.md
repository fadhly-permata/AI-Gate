---
description: Log a bug from just a title; severity and other fields are filled automatically
---
Record a bug with minimal input — just the title. Severity, ID, date, reporter,
and status are filled automatically. User never types severity.

Args: $ARGUMENTS

If first arg in `help` / `info` / `information` / `?` -> print usage, stop.

Usage: /log-bug <title> [detail]
  title   = short bug title (required)
  detail  = optional free text (repro / expected / actual / env)

Procedure (PM executes):
1. Ensure `pm/bugs.md` exists (create header if not).
2. Auto-fill (no user input needed):
   - ID: BUG-<yyymmdd>-<n>            (n = increment per day)
   - Date: today
   - Reporter: user
   - Severity: AUTO — default `medium`; bump to `high` if title/detail hints
     crash / blocker / data-loss; `low` for typo / cosmetic.
   - Status: open
3. Append entry: Title, Severity, Status, plus Reproduction/Expected/Actual/
   Environment from `detail` (if given).
4. Update pm/status.md (new bug) and pm/memory-bank.md open risks if severity high.
5. Print created bug ID + auto severity.

Definition of done:
- Bug recorded in pm/bugs.md; user only supplied the title.

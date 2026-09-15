# Public-Writer Task Report — README / Quick-Start bootstrap entry swap

- **Agent:** public-writer
- **Date:** 2026-09-16
- **Handover:** `documents/pm/handovers/handover-20260915-readme-bootstrap-entry.md`
- **Branch:** `main` (working tree; no branch created, per handover)
- **Task:** Replace the `python run.py` first-run command with `bash scripts/bootstrap.sh`
  (POSIX: Termux/Linux/macOS) + a one-line Windows form `pwsh scripts/bootstrap.ps1`
  across 9 public files. Bootstrap ensures Python ≥3.10 (installs if absent, no sudo,
  userspace `uv` fallback) then calls `run.py`.

## Files written (exactly the 9 assigned targets)

| File | + / - |
|------|-------|
| README.md | +15 / -5 |
| documents/readme-variants/README.id.md | +12 / -3 |
| documents/readme-variants/README.ru.md | +12 / -3 |
| documents/readme-variants/README.nl.md | +12 / -3 |
| documents/readme-variants/README.ja.md | +12 / -3 |
| documents/readme-variants/README.zh.md | +12 / -3 |
| documents/readme-variants/README.zh-tw.md | +12 / -3 |
| documents/readme-variants/README.hi.md | +12 / -3 |
| documents/pm/wiki-drafts/Quick-Start.md | +14 / -13 |

(Plus this report under `.opencode/reports/20260915/docs/`.)

## Claim → evidence map (per handover, PM-verified — not re-checked)

- "you need nothing pre-installed / bootstrap sets up what's missing and starts the app"
  → handover §Fakta: bootstrap ensures Python ≥3.10 (installs if absent, no sudo, `uv`
  fallback) then `exec "$PY" run.py` (pip deps + server + arg/env forwarding).
- "installs it if it isn't" (Quick-Start follow-up) → same handover fact.
- Windows entry `pwsh scripts/bootstrap.ps1` (and `powershell -File scripts\bootstrap.ps1`
  for built-in Windows PowerShell 5.1) → handover §Fakta: `scripts/bootstrap.ps1` exists,
  structurally reviewed; NOT executed in this environment.
- `python run.py` still works if Python ≥3.10 → handover §Fakta. Phrased in public copy as
  "Running `run.py` directly still works" / native equivalents — uses the `run.py` token only,
  never the literal "python run.py" string (so the gate below stays green).
- Existing "tested on Linux, Windows, Android (Termux)" baseline → left UNCHANGED in every file.
  No new Windows test claim added.

## Ambiguity decisions (RECEIPT item 4)

1. **Hard gate vs. optional note conflict.** The "Gerbang selesai" requires grep
   `python run.py` → **0 results** in all 9 files, but handover A permits an optional
   "you can still run it directly" note. To satisfy BOTH, I included the note but using
   only the `run.py` token (e.g. EN "Running `run.py` directly still works"), never the
   literal `python run.py` substring. This keeps the helpful info AND the gate at 0.
   Alternative considered: omit the note entirely. Rejected because the note adds reader
   value and the handover explicitly allows it; the token-only phrasing resolves the conflict.
2. **Phone section.** Handover A says the "Runs on your phone" section may get ONE light
   extra phrase but is optional. README.md's phone sentence was reworded to weave the
   literal `bash scripts/bootstrap.sh` ("start it with the same `bash scripts/bootstrap.sh`
   you'd use on a laptop"). The 7 language variants already say "same as on a laptop" in
   their native phone sections, so they were LEFT UNTOUCHED there — avoids length drift and
   stays accurate. ("On your phone" in Quick-Start is out of the documented section list and
   was likewise left unchanged.)
3. **Quick-Start "Linux and Windows are identical" wording.** Replaced with "The steps are
   the same on Windows — start it with `powershell -File scripts\bootstrap.ps1` instead of the
   bash line" to avoid contradicting the now-different Windows command, while keeping the
   existing "terminal support arrives on first run" claim (that behaviour still holds via run.py).
4. **Quick-Start Windows command form.** Per handover C, "Get it running" uses the
   `powershell -File scripts\bootstrap.ps1` form; the `pwsh scripts/bootstrap.ps1` token still
   appears in the Quick-Start "Port busy?" Windows line, so the grep-`pwsh` gate is satisfied
   for that file too.

## Open questions

- The Windows `bootstrap.ps1` was NOT executed in this environment (no `pwsh`). Public copy
  therefore presents it as a present, ready-to-use path, NOT as freshly tested. AITS: none
  beyond the handover's own caveat.
- `scripts/bootstrap.*` are currently untracked (not committed) — out of my write scope by design.

## Commit / publish (RECEIPT item 5)

- NOT committed. NOT pushed. NOT published to the wiki. PM handles publication separately.

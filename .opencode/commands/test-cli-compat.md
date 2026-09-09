---
description: Test the 24 CLI tool install/launch scripts on the current platform and fill the per-platform compatibility catalog (cli_compat.py dict). Self-contained — no need to re-explain context.
---

Test the 24 CLI tool install/launch scripts in this repo against the **current platform** and record results into the compatibility catalog. All context is below — do NOT ask the user to re-explain; just execute.

Args: $ARGUMENTS

Usage: /test-cli-compat [platform | --dry-run]
  platform  = force one of: termux | linux | windows | macos
  --dry-run = only preview the plan, do not install or write

## Context (self-contained)
This repo has 24 CLI tool scripts in `scripts/cli-tools/*.sh` (+ `_common.sh`), wired to the aigate gateway. The compatibility catalog lives in `src/backend/cli_compat.py` as a Python `dict` (the `termux` column is already filled from on-device testing; `linux`/`windows`/`macos` = `unknown`). There is NO external harness script — this command is fully self-contained: opencode iterates the 24 scripts, classifies each, and edits the entry for the current platform directly in `cli_compat.py`.

The 24 tools:
- Group A (agentic coding): claude, opencode, gemini, codex, antigravity, phi, aider, goose, amp, qwen, cline, kilo
- Group B (autonomous agents): openhands, swe-agent, open-interpreter, autogpt, gpt-researcher, crewai
- Group C (chat/shell): llm, sgpt, mods, oterm, gptme, aichat

Platform-independent facts (same on every OS — set directly, no install needed):
- `no_install` (8): antigravity, phi, goose, amp, swe-agent, autogpt, sgpt, mods — the generic install commands pull the WRONG package, so there is no valid install route.
- `not_a_cli` (2): gpt-researcher, crewai — frameworks/libraries with no launchable binary.

The other 14 are PROBED by running each script (real install via npm/pip/cargo + launch `--help`):
claude, opencode, gemini, codex, aider, qwen, cline, kilo, openhands, open-interpreter, llm, oterm, gptme, aichat.
  - gemini & codex → `not_wired` if the probe succeeds (they launch in a native mode aigate does not proxy: Google mode / OpenAI Responses API).

Status vocabulary:
- `verified`   : installs + launches via aigate gateway
- `installable`: installs but needs an API key / interactive setup
- `broken`     : install fails on this platform
- `no_install` : no valid install route (wrong-package collision)
- `not_a_cli`  : framework/library, no launchable binary
- `not_wired`  : installs but launches in a native mode aigate doesn't proxy
- `unknown`    : not yet tested

## Procedure
1. Determine the platform: use the `$ARGUMENTS` override if given; else detect via `uname -s` (Linux→linux, Darwin→macos) or MINGW/MSYS (→windows). If ambiguous, use the detected value and note it.
2. From the repo root, test the 24 tools and record each into `src/backend/cli_compat.py` (the catalog `dict`; the `termux` column is already filled, all other platforms are `unknown`):
   - **10 platform-independent tools** — set their status directly WITHOUT installing anything: `no_install` for antigravity, phi, goose, amp, swe-agent, autogpt, sgpt, mods; and `not_a_cli` for gpt-researcher, crewai.
   - **The remaining 14** (claude, opencode, gemini, codex, aider, qwen, cline, kilo, openhands, open-interpreter, llm, oterm, gptme, aichat): run `bash scripts/cli-tools/<tool>.sh --help` from an isolated temp directory. Classify the result:
     - install fails → `broken`
     - install ok + launch (`--help`) ok → `verified` (for gemini / codex use `not_wired` instead)
     - install ok but needs an API key / interactive setup → `installable`
     Then edit that tool's entry in `cli_compat.py` for the CURRENT platform: change its `"status": "unknown"` to the resulting status and fill in `"note"`.
   - Windows native PowerShell CANNOT run the `.sh` scripts — tell the user to use Git Bash or WSL, and ensure `python3` is on PATH.
3. Review `git diff src/backend/cli_compat.py` and the printed summary. If a result is wrong (e.g. a tool that only failed due to a missing API key should be `installable` not `broken`; or gemini/codex should be `not_wired` not `verified`), correct it by editing `cli_compat.py` directly.
4. Commit: `git add src/backend/cli_compat.py && git commit -m "test(cli-tools): fill <platform> compat catalog"` (replace `<platform>` with the detected one).
5. Do NOT push unless the user explicitly asks. (They will push to share results.)
6. Print a short summary: per-tool status for this platform, and explicitly list any `broken` / `no_install` / `not_a_cli` / `not_wired` tools.

## Definition of done
- `cli_compat.py` current-platform column filled for all 24 tools; other platforms intact.
- Changes committed locally; no push without request.
- User got a per-tool status summary.

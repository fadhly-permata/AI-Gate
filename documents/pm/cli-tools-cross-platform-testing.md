# CLI Tools — Cross-Platform Compatibility Testing (self-contained guide)

> **Self-contained on purpose.** This document holds ALL the context needed to run
> the compatibility harness on a fresh Linux / macOS / Windows machine and feed the
> results back into the catalog — no need to re-read anything else or ask the PM.
> If you are a future session or a different machine, start here.

---

## 1. What this is for

aigate ships 24 CLI-tool launcher scripts (`scripts/cli-tools/<tool>.sh`). Whether
each tool actually **installs and launches** differs per operating system. We keep a
per-tool × per-platform compatibility catalog (`src/backend/cli_compat.json`) that
the **`cli tools`** view renders as one status badge per platform (the current
platform is highlighted, and a red warning shows for broken / no_install /
not_a_cli / not_wired on the platform you are running on).

The harness **`scripts/cli-tools/compat-test.sh`** probes every tool on the machine
it runs on and writes the result into the catalog — only for the platform it detects.
You run it once per OS, then commit + push. Repeat on each platform.

---

## 2. The 24 tools (authoritative list)

Grouped exactly as `src/backend/cli_presets.py` (`CLI_PRESETS`). Names here are
the keys used everywhere (scripts, JSON, UI).

**Group A — Agentic coding (12):** `claude`, `opencode`, `codex`, `gemini`,
`antigravity`, `phi`, `aider`, `goose`, `amp`, `qwen`, `cline`, `kilo`

**Group B — Autonomous agents (6):** `openhands`, `swe-agent`, `open-interpreter`,
`autogpt`, `gpt-researcher`, `crewai`

**Group C — Chat & shell (6):** `llm`, `sgpt`, `mods`, `oterm`, `gptme`, `aichat`

### Global classification (same on EVERY platform — no install needed)

These are filled in directly by the harness without running anything:

| Status | Tools (10) | Why |
|--------|-----------|-----|
| `no_install` (8) | `antigravity`, `phi`, `goose`, `amp`, `swe-agent`, `autogpt`, `sgpt`, `mods` | No verified install path (npm/pip/brew squat, 404, or no Android/Windows/macOS binary). |
| `not_a_cli` (2) | `gpt-researcher`, `crewai` | Installs as a library / framework scaffolder, not a launchable terminal CLI. |

### Probe-worthy (14) — the harness actually runs these

`claude`, `opencode`, `codex`, `gemini`, `aider`, `qwen`, `cline`, `kilo`,
`openhands`, `open-interpreter`, `llm`, `oterm`, `gptme`, `aichat`

Of these, **`gemini`** and **`codex`** are special: if the probe succeeds (install
+ launch OK) they are recorded as **`not_wired`** (they install, but run in a native
mode aigate does **not** serve — Google / OpenAI Responses — so aigate can't proxy
them). The other 12 probe-worthy tools become `verified` / `installable` / `broken`.

---

## 3. Status vocabulary (the enum)

| Status | Meaning |
|--------|---------|
| `verified` | Confirmed working on this platform, wired to aigate. |
| `installable` | Install + launch attempted; install OK but launch/`--help` failed or needs a key/interactive input. |
| `broken` | Install/build failed, or the binary cannot run on this platform. |
| `no_install` | No verified install path for this platform. |
| `not_a_cli` | Library/framework, not a launchable terminal CLI. |
| `not_wired` | Installs, but runs in a mode aigate does not serve (e.g. native Google / Responses API). |
| `unknown` | Not yet tested on this platform (default for every platform except Termux). |

`source` for any row the harness writes is `compat-test-<platform>-<date>` so the
row is easy to find. The seeded `termux` rows use `tested-termux-2026-09`.

---

## 4. How the harness decides a status (probe-worthy tools)

Each probe runs `bash scripts/cli-tools/<tool>.sh --help` inside an isolated temp
directory. The per-tool scripts forward `$@` to `exec "$BIN" "$@"`, so `--help`
makes a normal tool install then run `<bin> --help`; a `no_install`/`not_a_cli`
script just prints a message and exits 0 (no side effects). Classification:

- **exit 0** → install succeeded and the binary ran `--help`:
  - `gemini` / `codex` → **`not_wired`**
  - otherwise → **`verified`**
- **non-zero exit** and the log contains `"aborting launch"` (the script's own
  install-failure sentinel) → **`broken`** (install failed)
- **non-zero exit** otherwise → **`installable`** (install ran but launch/`--help`
  failed, e.g. needs a key or went interactive)

> Note: the `no_install` / `not_a_cli` scripts are **never run** by the harness —
> they are filled from the global table above.

---

## 5. Run it

### Prerequisites
- `bash`, `python3`, and `git` available.
- You are on the **`setup/cli-tools`** branch (the catalog + harness live there).
- On Windows: use **Git Bash** (the scripts are bash, meant for WSL / Git Bash).

### Linux / macOS
```bash
git fetch origin
git checkout setup/cli-tools        # or: git switch setup/cli-tools
cd scripts/cli-tools
bash compat-test.sh --apply
```

### Windows (Git Bash)
```bash
git fetch origin
git checkout setup/cli-tools
cd scripts/cli-tools
bash compat-test.sh --apply
```
(Git Bash provides `bash`; `python3` must be on PATH — install it via the official
installer or `winget install Python.Python.3` and let it add to PATH.)

### Dry run first (recommended)
Add `--dry-run` to print the plan for all 24 tools **without installing anything or
writing the JSON**:
```bash
bash compat-test.sh --dry-run
```

---

## 6. What happens to the data

- The harness writes **only the column for the platform it detected** into
  `src/backend/cli_compat.json` (`compat[<tool>][<platform>]`). All other platform
  columns (e.g. the seeded `termux` data) are **preserved**.
- It runs each probe in an isolated temp dir (`/tmp/...`, `%TEMP%`, or `$HOME` if
  those are unavailable) and cleans it up on exit.
- The **`cli tools`** view reads `cli_compat.json` directly (via
  `src/backend/cli_compat.py`, a thin loader), so the new data shows up on the next
  fetch — no rebuild needed.

---

## 7. Commit & push the result

After a successful `--apply` on a platform, review the change and send it back:
```bash
git status                                  # confirm only cli_compat.json changed
git add src/backend/cli_compat.json
git commit -m "test(cli-tools): fill <platform> compat from cross-platform harness"
git push origin setup/cli-tools
```
Replace `<platform>` with `linux` / `windows` / `macos`. Repeat on each OS. The
`documents/pm/cli-tools-compatibility.md` human-readable mirror is informational only
(source of truth is the JSON); no need to hand-edit it.

---

## 8. Safety notes / troubleshooting

- **It really installs things.** `--apply` runs the real install commands
  (`npm i -g ...`, `pip install ...`, `cargo install ...`, etc.) for the 14
  probe-worthy tools. That is the point. Use `--dry-run` first if unsure.
- **`broken` for a tool you expected to work?** Open the temp log (captured per tool
  during the run) or just re-run the script manually:
  `bash scripts/cli-tools/<tool>.sh --help`.
- **Wrong platform detected?** Check `uname -s` / `uname -o` and (on Android) the
  `TERMUX_VERSION` env var — that's what the harness keys off, same as
  `scripts/cli-tools/_common.sh`.
- **Don't hand-edit `cli_compat.py`.** It is a loader; edit `cli_compat.json`.
- Each probe is bounded by a 300s `timeout` so an interactive/hung tool can't block
  the whole run.

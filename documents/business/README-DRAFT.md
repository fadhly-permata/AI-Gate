# aigate 🚪

Your own local AI gateway + management console — one endpoint in front of all your providers, one tab in front of all your coding CLIs.

Point any OpenAI-compatible client at `http://localhost:8080/v1` and let aigate handle providers, fallbacks, quotas, and logs. No Docker. No cloud account. Runs on your laptop — or literally on your phone.

## What you get ✨

- **OpenAI-compatible gateway** — `POST /v1/chat/completions`, `POST /v1/responses` (non-streaming bridge), `GET /v1/models`, streaming, consistent error shapes.
- **Provider management** — model discovery, provider accounts, OAuth/token refresh, quota & usage tracking.
- **Combos** — fallback, load balancing, routing by latency/cost, tiered strategies across providers.
- **Endpoint routing** — access control per endpoint + proxy-pool binding.
- **Observability** — request logs, analytics, CSV export, local settings backup/restore.
- **In-app terminal** — WebSocket PTY, multi-tab, auto-closes when the shell exits. POSIX/Termux use `ptyprocess`, Windows uses `pywinpty`.
- **Zero-setup launcher** — Python deps install themselves on first run.
- **Polished UI** — responsive, light/dark, 7 languages (EN, ID, RU, NL, JA, ZH, ZH-TW), searchable model picker, device simulation in developer mode.

Stack: Python 3.10+ · FastAPI · vanilla JS (no build step) · SQLite. Config and data live in `~/.aigate/`.

## Vibe coding 😎

Two things built to work together:

### 1. CLI tool launcher — 24 AI coding tools, one click

Launch any preset straight into an in-app terminal tab (`src/backend/cli_presets.py`):

| Group | Tools |
|---|---|
| Agentic Coding Assistants | claude, opencode, codex, gemini, antigravity, phi, aider, goose, amp, qwen, cline, kilo |
| Autonomous Software Agents | openhands, swe-agent, open-interpreter, autogpt, gpt-researcher, crewai |
| Chat & Shell Assistants | llm, sgpt, mods, oterm, gptme, aichat |

Missing tool? The launcher shows an install command that actually works on your platform (see Termux below).

### 2. Self-Heal loop — watch your agent fix the code

The full loop (`src/backend/selfheal.py`):

1. Creates a git branch automatically.
2. Runs an agentic CLI in a **visible live PTY tab** — not a hidden subprocess. You watch it work.
3. Fix/test loop driven by warning/error log lines; resolved lines get cleared as it goes.
4. Merges to `main`, deletes the branch.

Safety built in: the CLI prompt is read from a temp file (never interpolated into a shell command — no injection), the "done" marker only counts on exit code 0 (failure leaves a `<prompt>.failed` file, never a silent fake success), and a missing binary shows a clean status instead of crashing.

## Runs on your phone 📱 (Termux)

Yes, really — aigate is a first-class Termux citizen:

- **Pure Python, no Rust compile** (ADR-012). Every core dependency installs and runs natively on Android Termux — and on any platform missing Rust wheels.
- **Per-platform install routes.** In Termux, npm reports `process.platform == "android"`, so `*-linux-arm64` packages never resolve. aigate has a `TERMUX_INSTALL` override plus `is_termux()` detection (`cli_presets.py`, `paths.py`) so the install command it suggests is one that actually works — e.g. `pkg install aichat`.
- **Presets verified on-device.** CLI presets are checked directly on Termux/aarch64 hardware, not from memory.
- **E2E testing on Android** too:

```bash
PW_EXECUTABLE=/path/to/chromium PW_NO_SANDBOX=1 npm run test:e2e:android
```

**Beyond Termux:** proot Linux distros (proot-distro Ubuntu/Debian on Termux) *should* work — same pure-Python stack — but this is not yet verified on-device, so consider it experimental.

<!-- TODO-VERIFY: belum dites di proot-distro -->

## Quick start 🚀

Zero-setup — installs missing Python deps, then serves:

```bash
python run.py
```

Open <http://localhost:8080>.

```bash
AIGATE_PORT=9090 python run.py   # different port
AIGATE_DEV=1 python run.py       # developer mode
```

Prefer a proper install?

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
aigate --port 8080
```

Or run uvicorn manually:

```bash
python -m uvicorn backend.server:app --host 0.0.0.0 --port 8080
```

No container required — by design.

## Gateway API 🔌

Use aigate as the base URL for any OpenAI-compatible client:

```text
http://localhost:8080/v1
```

Endpoints: `POST /v1/chat/completions` (streaming supported), `POST /v1/responses` (non-streaming bridge), `GET /v1/models`. Full contract: [`documents/api/OPENAI_COMPATIBLE_CONTRACT.md`](documents/api/OPENAI_COMPATIBLE_CONTRACT.md).

## Configuration & data 🗂️

Everything lives in `~/.aigate/` — SQLite database, settings, generated launcher config.

> 🔑 **API keys are local data. Never commit them.** Local `.env`, DB files, coverage output, and generated launcher config are Git-ignored.

Environment variables: `AIGATE_PORT` (server port), `AIGATE_DEV=1` (developer features).

## Testing 🧪

Backend:

```bash
python -m pip install -e '.[dev]'
pytest
```

Frontend:

```bash
cd src/frontend
npm install
npm test
npm run test:e2e
```

## Repo layout 🗺️

```text
src/backend/    FastAPI server, gateway, routing, providers, terminal, CLI tools
src/frontend/   Static vanilla JS UI and browser tests
tests/          Backend and project-level tests
documents/      Product, architecture, API, setup, UX, and QA docs
documents/pm/   Project-manager memory and progress records
run.py          Zero-setup launcher
pyproject.toml  Python package and test configuration
```

## Status 📌

Working local-first tool, developed actively. The gateway, console, terminal, and Termux paths are the tested core; the proot-distro route above is the one unverified claim. Contributions and feedback welcome — open an issue first for anything big.

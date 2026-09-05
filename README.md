# aigate

Local AI proxy gateway and management console built with Python, FastAPI, and a vanilla JavaScript frontend.

## What it provides

- OpenAI-compatible gateway endpoints:
  - `POST /v1/chat/completions`
  - `POST /v1/responses` (non-streaming Responses API bridge)
  - `GET /v1/models`
- Provider management and model discovery.
- Multi-provider combos with fallback, load balancing, latency/cost routing, and tiered strategies.
- Endpoint routing with access control and proxy-pool binding.
- Provider accounts, OAuth/token refresh support, quota and usage tracking.
- Request logs, analytics, CSV export, and local settings backup/restore.
- Local terminal with WebSocket PTY support and multiple tabs.
- CLI tool launcher and self-heal workflow.
- Responsive web UI with light/dark themes, EN/ID translations, searchable model pickers, and device simulation in developer mode.

## Requirements

- Python 3.10 or newer.
- Internet access on first run when using the zero-setup launcher.
- Node.js is only needed for frontend tests and browser automation.

## Quick start

Zero-setup launcher installs missing Python dependencies and starts the local server:

```bash
python run.py
```

Open <http://localhost:8080>.

For developer mode:

```bash
AIGATE_DEV=1 python run.py
```

Choose a different port with:

```bash
AIGATE_PORT=9090 python run.py
```

## Install manually

Using a virtual environment:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m uvicorn backend.server:app --host 0.0.0.0 --port 8080
```

After editable installation, the `aigate` console command is also available:

```bash
aigate --port 8080
```

On Windows, `pywinpty` is installed through the platform-specific dependency. POSIX and Termux use `ptyprocess`.

## Frontend tests

```bash
cd src/frontend
npm install
npm test
```

Browser tests:

```bash
npm run test:e2e
```

Android/Termux browser runner:

```bash
PW_EXECUTABLE=/path/to/chromium PW_NO_SANDBOX=1 npm run test:e2e:android
```

## Backend tests

From repository root, after installing development dependencies:

```bash
python -m pip install -e '.[dev]'
pytest
```

## Configuration and data

Runtime configuration and application data use the local SQLite database under `~/.aigate/`. API keys and other provider credentials are local application data; never commit them.

Useful environment variables:

- `AIGATE_PORT` — server port.
- `AIGATE_DEV=1` — enable developer features.

Local `.env`, database files, coverage output, and generated launcher configuration are ignored by Git.

## Repository layout

```text
src/backend/       FastAPI server, gateway, routing, providers, terminal, CLI tools
src/frontend/      Static vanilla JavaScript UI and browser tests
tests/             Backend and project-level tests
documents/         Product, architecture, API, setup, UX, and QA documentation
pm/                Project-manager memory and progress records
run.py             Zero-setup launcher
pyproject.toml     Python package and test configuration
```

## API compatibility

Clients can use aigate as an OpenAI-compatible API by setting their base URL to:

```text
http://localhost:8080/v1
```

See [`documents/api/OPENAI_COMPATIBLE_CONTRACT.md`](documents/api/OPENAI_COMPATIBLE_CONTRACT.md) for the gateway contract and [`documents/dev/SETUP.md`](documents/dev/SETUP.md) for development standards.

## Project status

This repository is designed to run natively as a local Python application; deployment containers are not required.

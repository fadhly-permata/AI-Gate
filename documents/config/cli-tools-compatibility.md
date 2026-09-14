# CLI Tools — Compatibility Catalog (per-tool × per-platform)

> Mirror human-readable dari `src/backend/cli_compat.py` (`CLI_COMPAT`).
> Edit di SINI untuk mengisi kolom Linux / Windows / macOS setelah diuji di
> masing-masing platform, lalu sinkronkan ke `cli_compat.py` (sumber kode).
>
> Status codes: `verified` · `installable` · `broken` · `no_install` ·
> `not_a_cli` · `not_wired` · `unknown`.
> `source` kolom Termux = `tested-termux-2026-09` (perangkat: Termux aarch64,
> Python 3.14.6).

## Legend

| Platform | Arti |
|----------|------|
| Termux | Android/Termux (aarch64) — **sudah diuji di perangkat ini** |
| Linux   | Linux x86_64/arm64 — belum diuji (user isi nanti) |
| Windows | Windows 10/11 — belum diuji (user isi nanti) |
| macOS   | macOS (Intel/Apple Silicon) — belum diuji (user isi nanti) |

## Catalog

| Tool | Group | Termux | Linux | Windows | macOS |
|------|-------|--------|-------|---------|-------|
| aichat | C | **verified** — `pkg install aichat` (0.30.0), OpenAI-compatible, wired | unknown | unknown | unknown |
| claude | A | **broken** — npm `@anthropic-ai/claude-code` no Android binary; npm dead on Termux | unknown | unknown | unknown |
| codex | A | **not_wired** — runs native OpenAI Responses API; aigate has no streaming responses inbound | unknown | unknown | unknown |
| gemini | A | **not_wired** — runs native Google mode; aigate serves OpenAI/Anthropic only | unknown | unknown | unknown |
| antigravity | A | **no_install** — no verified CLI package (npm squat / 404) | unknown | unknown | unknown |
| phi | A | **no_install** — no verified CLI package (npm squat / PyPI unrelated) | unknown | unknown | unknown |
| aider | A | **broken** — pip needs Python 3.10–3.12 (device 3.14); version guard exits | unknown | unknown | unknown |
| goose | A | **no_install** — no Android/Termux binary for Block's goose | unknown | unknown | unknown |
| amp | A | **no_install** — `@ampcode/cli` has no Android/Termux build | unknown | unknown | unknown |
| qwen | A | **broken** — npm `@qwen-code/qwen-code` no Android binary; npm dead on Termux | unknown | unknown | unknown |
| cline | A | **broken** — npm `cline` no Android binary; npm dead on Termux | unknown | unknown | unknown |
| kilo | A | **broken** — npm `@kilocode/cli` no Android binary; npm dead on Termux | unknown | unknown | unknown |
| openhands | B | **broken** — pip needs Python 3.12 (device 3.14); version guard exits | unknown | unknown | unknown |
| swe-agent | B | **no_install** — PyPI 404; Docker/conda setup impractical on Termux | unknown | unknown | unknown |
| open-interpreter | B | **broken** — pip heavy but reportedly installable on Termux (Py3.14) | unknown | unknown | unknown |
| autogpt | B | **no_install** — official AutoGPT is Docker platform; PyPI `autogpt` is unrelated squat | unknown | unknown | unknown |
| gpt-researcher | B | **not_a_cli** — pip package is library/backend only; no launchable binary | unknown | unknown | unknown |
| crewai | B | **not_a_cli** — console script is a framework scaffolder/runner (needs project in CWD) | unknown | unknown | unknown |
| llm | C | **broken** — pip fails building `jiter` (no Android wheel, Py3.14) | unknown | unknown | unknown |
| sgpt | C | **no_install** — npm squat / PyPI 404 / Go binary no Android build | unknown | unknown | unknown |
| mods | C | **no_install** — Go binary (charmbracelet/mods) no Android build | unknown | unknown | unknown |
| oterm | C | **broken** — pip fails building `jiter` (no Android wheel, Py3.14) | unknown | unknown | unknown |
| gptme | C | **broken** — pip fails building `jiter` (no Android wheel, Py3.14) | unknown | unknown | unknown |

## Ringkasan Termux (24 tool)

- **verified**: aichat (1)
- **broken**: claude, opencode, aider, qwen, cline, kilo, llm, oterm, gptme,
  openhands, open-interpreter (11)
- **no_install**: antigravity, phi, goose, amp, swe-agent, autogpt, sgpt, mods (8)
- **not_a_cli**: gpt-researcher, crewai (2)
- **not_wired**: gemini, codex (2)

## Catatan sinkronisasi

- Sumber otoritatif kode = `src/backend/cli_compat.py` (`CLI_COMPAT`,
  `PLATFORMS`, `current_platform()`, `compat_for()`).
- Perintah `cli tools` (frontend CLI Tools view) merender 4 badge per tool
  (Termux/Linux/Windows/macOS), menyorot platform saat ini (deteksi dari Python
  via `current_platform()`), dan menampilkan warning merah bila status platform
  saat ini ∈ {broken, no_install, not_a_cli, not_wired}.
- Mengubah status di `cli_compat.py` otomatis tercermin di UI pada fetch
  berikutnya (tanpa cache-buster khusus untuk data ini).

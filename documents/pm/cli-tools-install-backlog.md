# Backlog — Install Script per CLI Tool (branch `setup/cli-tools`)

Sumber otoritatif daftar tool: `src/backend/cli_presets.py` (`CLI_PRESETS`,
`TERMUX_INSTALL`, `LAUNCH_SUPPORT`) — transkripsi dari
`documents/config/CLI_CONFIG_SCHEMA.md`.

Tujuan: untuk tiap tool buat **script install + launch** yang (1) pasang
dependency via package manager Termux, (2) pasang tool-nya, (3) saat launch
cek `command -v <binary>` → kalau belum terinstall pasang dulu, kalau sudah
langsung jalankan. Idempoten & aman.

Konvensi status: `todo` | `in_progress` | `done` | `blocked`
Kolom `Install` = perintah pasang (dari `CLI_PRESETS` / `TERMUX_INSTALL`).
Kolom `Dep (pkg/PM)` = dependency yang wajib ada di Termux sebelum install.
Kolom `Launch` = status di `LAUNCH_SUPPORT` (konteks, bukan bagian script).

## Catatan platform (PENTING — baca sebelum eksekusi)
- Di Termux/aarch64, `npm` melaporkan `process.platform == "android"` sehingga
  TIDAK memasang binary per-platform (`*-linux-arm64`). Akibatnya beberapa CLI
  Node (claude, codex, cline, kilo, amp, qwen) **terpasang tapi mati saat
  jalan** ("Missing optional dependency ..."). Script tetap memasang, tapi tool
  bisa jadi tidak bisa dijalankan di perangkat ini.
- `goose` di repo Termux = tool migrasi DB, BUKAN agen Block → `NO_INSTALL`.
- Tool tanpa paket terverifikasi diberi `NO_INSTALL` (echo no-op) supaya script
  tidak memasang "sampah" (nama PyPI/npm disewa proyek lain).
- `codex` & `aichat` pakai `pkg install` (bukan npm/pip) — ada di `TERMUX_INSTALL`.

---

## Grup A — Agentic Coding Assistants (`agentic_coding`)

| # | Tool | Binary | Install (pkg/PM) | Dep (pkg/PM) | Launch | Status |
|---|------|--------|------------------|--------------|--------|--------|
| A1 | claude | claude | `npm i -g @anthropic-ai/claude-code` | nodejs (npm) | unsupported (anthropic_only) | done |
| A2 | opencode | opencode | `npm i -g opencode-ai` | nodejs (npm) | verified | done |
| A3 | gemini | gemini | `npm i -g @google/gemini-cli` | nodejs (npm) | unsupported (gemini_only) | done |
| A4 | codex | codex | `pkg install codex` (override) / `npm i -g @openai/codex` | nodejs (npm) atau pkg | unsupported (responses_only) | done |
| A5 | antigravity | antigravity | `NO_INSTALL` (no-op) | — | unsupported (not_a_cli) | todo |
| A6 | phi | phi | `NO_INSTALL` (no-op) | — | unsupported (install_unverified) | todo |
| A7 | aider | aider | `pip install aider-chat` | python (pip) | verified | todo |
| A8 | goose | goose | `NO_INSTALL` (no-op) | — | unsupported (no_binary) | todo |
| A9 | amp | amp | `NO_INSTALL` (no-op) | — | unsupported (no_binary) | todo |
| A10 | qwen | qwen | `npm i -g @qwen-code/qwen-code` | nodejs (npm) | verified | todo |
| A11 | cline | cline | `npm i -g cline` | nodejs (npm) | verified | todo |
| A12 | kilo | kilo | `npm i -g @kilocode/cli` | nodejs (npm) | verified | todo |

> **A3 gemini = done (2026-09-09):** install idempoten `npm i -g @google/gemini-cli` (alt `brew install gemini-cli`). Launch **native Google mode** — TIDAK di-wire aigate: `cli_presets.py:175` mark gemini `LAUNCH_UNSUPPORTED`/`REASON_GEMINI_ONLY` (aigate hanya serve OpenAI `/v1/chat/completions` + Anthropic `/v1/messages`, no Google generateContent inbound). Script sadar ini → tidak set `ANTHROPIC_BASE_URL`/`OPENAI_API_BASE` palsu (gemini CLI mengabaikannya → no-op).
> **A4 codex = done (2026-09-09):** install idempoten `pkg install codex` (Termux, tur-repo bionic) / `npm i -g @openai/codex` (non-Termux; npm `@openai/codex` v0.153.4 ada optional dep `linux-arm64`). Launch **native OpenAI mode** + warning — TIDAK di-wire aigate: `cli_presets.py:180` mark codex `LAUNCH_UNSUPPORTED`/`REASON_RESPONSES_ONLY`. aigate punya inbound `/v1/responses` (`router.py:342`) tapi **non-streaming only** (`responses.py:227-233`: `stream:true` → tolak `responses_streaming_unsupported`), sedangkan codex CLI **wajib streaming** → tak bisa di-rute. Script sadar ini → tidak set env palsu ke aigate. Commit `7f22713`.

## Grup B — Autonomous Software Agents (`autonomous_agents`)

| # | Tool | Binary | Install (pkg/PM) | Dep (pkg/PM) | Launch | Status |
|---|------|--------|------------------|--------------|--------|--------|
| B1 | openhands | openhands | `pip install openhands` (butuh Python 3.12) | python (pip) | verified | todo |
| B2 | swe-agent | swe-agent | `NO_INSTALL` (no-op) | — | unsupported (install_unverified) | todo |
| B3 | open-interpreter | interpreter | `pip install open-interpreter` | python (pip) | verified | todo |
| B4 | autogpt | autogpt | `NO_INSTALL` (no-op) | — | unsupported (install_unverified) | todo |
| B5 | gpt-researcher | gpt-researcher | `pip install gpt-researcher` | python (pip) | unsupported (not_a_cli) | todo |
| B6 | crewai | crewai | `pip install crewai` | python (pip) | unsupported (not_a_cli) | todo |

## Grup C — Chat & Shell Assistants (`chat_shell`)

| # | Tool | Binary | Install (pkg/PM) | Dep (pkg/PM) | Launch | Status |
|---|------|--------|------------------|--------------|--------|--------|
| C1 | llm | llm | `pip install llm` | python (pip) | verified | todo |
| C2 | sgpt | sgpt | `NO_INSTALL` (no-op) | — | unsupported (install_unverified) | todo |
| C3 | mods | mods | `NO_INSTALL` (no-op) | — | unsupported (no_binary) | todo |
| C4 | oterm | oterm | `pip install oterm` | python (pip) | verified | todo |
| C5 | gptme | gptme | `pip install gptme` | python (pip) | verified | todo |
| C6 | aichat | aichat | `pkg install aichat` (override) / `cargo install aichat` | pkg (atau rust/cargo) | verified | todo |

---

## Ringkasan
- Total tool: **24** (A=12, B=6, C=6).
- `NO_INSTALL` (tidak ada paket terverifikasi, script cuma pesan no-op): **8**
  (antigravity, phi, goose, amp, swe-agent, autogpt, sgpt, mods).
- Install via `npm`: 7 (claude, opencode, codex, gemini, qwen, cline, kilo).
- Install via `pip`: 9 (aider, openhands, open-interpreter, gpt-researcher,
  crewai, llm, oterm, gptme, + ... ) → sebutan: aider, openhands,
  open-interpreter, gpt-researcher, crewai, llm, oterm, gptme = 8; (codex/aichat
  lewat pkg).
- Install via `pkg` (Termux override): 2 (codex, aichat).
- Install via `cargo`: 1 (aichat, fallback kalau pkg tidak ada).

## Item kerja lintas-tool (dibuat sekali, dipakai semua)
- [x] `_common.sh` — helper lintas-platform: `detect_os`/`detect_pm` (Termux/Linux→pkg/apt, Mac→brew, Windows→WSL/Git Bash/winget/choco), `load_gateway_config` (baca `~/.aigate/aigate.db`, fallback default `http://localhost:8080/v1` + `aigate-local`), `have_cmd`, `ensure_installed` (idempoten via `command -v`), `log_msg`. Dibuat pertama kali bersama A1 (claude).
- [ ] Keputusan lokasi folder script (lihat pertanyaan PM ke user).
- [ ] (Opsional) `install-all.sh` / one-liner `curl ... | bash` master.

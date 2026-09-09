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
| A5 | antigravity | antigravity | `NO_INSTALL` (no-op) | — | unsupported (not_a_cli) | done |
| A6 | phi | phi | `NO_INSTALL` (no-op) | — | unsupported (install_unverified) | done |
| A7 | aider | aider | `pip install aider-chat` | python (pip) | verified | done |
| A8 | goose | goose | `NO_INSTALL` (no-op) | — | unsupported (no_binary) | done |
| A9 | amp | amp | `NO_INSTALL` (no-op) | — | unsupported (no_binary) | done |
| A10 | qwen | qwen | `npm i -g @qwen-code/qwen-code` | nodejs (npm) | verified | done |
| A11 | cline | cline | `npm i -g cline` | nodejs (npm) | verified | done |
| A12 | kilo | kilo | `npm i -g @kilocode/cli` | nodejs (npm) | verified | done |

> **A3 gemini = done (2026-09-09):** install idempoten `npm i -g @google/gemini-cli` (alt `brew install gemini-cli`). Launch **native Google mode** — TIDAK di-wire aigate: `cli_presets.py:175` mark gemini `LAUNCH_UNSUPPORTED`/`REASON_GEMINI_ONLY` (aigate hanya serve OpenAI `/v1/chat/completions` + Anthropic `/v1/messages`, no Google generateContent inbound). Script sadar ini → tidak set `ANTHROPIC_BASE_URL`/`OPENAI_API_BASE` palsu (gemini CLI mengabaikannya → no-op).
> **A4 codex = done (2026-09-09):** install idempoten `pkg install codex` (Termux, tur-repo bionic) / `npm i -g @openai/codex` (non-Termux; npm `@openai/codex` v0.153.4 ada optional dep `linux-arm64`). Launch **native OpenAI mode** + warning — TIDAK di-wire aigate: `cli_presets.py:180` mark codex `LAUNCH_UNSUPPORTED`/`REASON_RESPONSES_ONLY`. aigate punya inbound `/v1/responses` (`router.py:342`) tapi **non-streaming only** (`responses.py:227-233`: `stream:true` → tolak `responses_streaming_unsupported`), sedangkan codex CLI **wajib streaming** → tak bisa di-rute. Script sadar ini → tidak set env palsu ke aigate. Commit `7f22713`.
> **A5 antigravity = done (2026-09-09):** **NO_INSTALL** — script HANYA menampilkan pesan `antigravity: NO_INSTALL — tidak ada paket CLI terverifikasi` lalu `exit 0`, TIDAK memasang apa pun (no side-effect). Bukti `cli_presets.py:74` (`install: NO_INSTALL`) + `cli_presets.py:176` (`LAUNCH_UNSUPPORTED`/`REASON_NOT_A_CLI`); `TERMUX_INSTALL` tidak punya entry antigravity; npm registry `antigravity` = placeholder squat (v0.0.0), PyPI milik pihak lain, Homebrew 404 → tidak ada rute install resmi. Sesuai keputusan user untuk tool `NO_INSTALL`. Commit `2259c1c`.
> **A6 phi = done (2026-09-09):** **NO_INSTALL** — script HANYA menampilkan pesan `phi: NO_INSTALL — belum ada install terverifikasi di environment ini.` lalu `exit 0`, TIDAK memasang apa pun (no side-effect). Bukti `cli_presets.py:75` (`install: NO_INSTALL`) + `cli_presets.py:177` (`LAUNCH_UNSUPPORTED`/`REASON_INSTALL_UNVERIFIED`); `TERMUX_INSTALL` tidak punya entry phi; npm `phi` = squat lama (v0.0.2, 2013), PyPI `phi` = library functional programming (cgarciae, bukan CLI), Homebrew formula `phi` 404 → tidak ada rute install resmi. Sesuai keputusan user untuk tool `NO_INSTALL`. Commit `3135e32`.
> **A7 aider = done (2026-09-09):** install idempoten `python3 -m pip install aider-chat` (mirror `pip install aider-chat` di `cli_presets.py:76`); launch **OpenAI-compatible** — aider forward ke aigate `/v1/chat/completions` (wiring persis mirip `_aider_builder` di `cli_tools_router.py:355-369`: `aider --openai-api-base <base> --openai-api-key <key> [--model openai/<model>]`). Bukti `cli_presets.py:172` = `aider` = `LAUNCH_VERIFIED` (OpenAI-compatible). PyPI `aider-chat` 0.86.2 pure-python tapi butuh Python 3.10–3.12 (`requires_python` gagal resolve di 3.13+). `bash -n` clean; mode exec. Commit `5a960e7`.
> **A7 aider = BUGFIX (2026-09-09):** `pip install aider-chat` gagal di device (Python 3.14.6; aider `requires_python ">=3.10,<3.13"` per PyPI 0.86.2) → pip error `No matching distribution found for aider-chat==0.86.2` (ignore semua rilis 0.16.1–0.86.2 karena "require a different python version"). Skrip lama cuma `NOTE` Termux-only **setelah** `ensure_installed` → raw pip error ke user. Fix (commit `1d1a31c`): tambah version-guard **pre-install** (major.minor numerik; luar 3.10–3.12 → ERROR + saran `pkg install python3.11`/pyenv/venv + `exit 1`); hapus `NOTE` Termux-only lama; wiring launch utuh. `bash -n` clean; simulasi guard: 3.10/3.11/3.12 lanjut, 3.9/3.13/3.14/3.14.6/2.7/4.0 exit 1.
> **A8 goose = done (2026-09-09):** **NO_INSTALL** — script HANYA menampilkan pesan `goose: NO_INSTALL — belum ada install terverifikasi di environment ini.` lalu `exit 0`, TIDAK memasang apa pun (no side-effect). Bukti `cli_presets.py:77` (`install: NO_INSTALL`) + `cli_presets.py:178` (`LAUNCH_UNSUPPORTED`/`REASON_NO_BINARY`); `TERMUX_INSTALL` tidak punya entry goose; npm `goose` = tool Golang tak terkait (jiyinyiyong, v0.0.3), `@block/goose` 404; PyPI `goose` (Goose 1.0.0, Mike Steder) = SQL migration tool SQLAlchemy; Homebrew `goose` = pressly/goose (v3.28.0, `conflicts_with block-goose-cli`). Install resmi Block (curl release script) tak punya build aarch64-android/termux terverifikasi → TIDAK ada rute install resmi. Sesuai keputusan user untuk tool `NO_INSTALL`. Commit `414ea06`.
> **A9 amp = done (2026-09-09):** **NO_INSTALL** — script HANYA menampilkan pesan `amp: NO_INSTALL — belum ada install terverifikasi di environment ini.` lalu `exit 0`, TIDAK memasang apa pun (no side-effect). Bukti `cli_presets.py:78` (`install: NO_INSTALL`) + `cli_presets.py:179` (`LAUNCH_UNSUPPORTED`/`REASON_NO_BINARY`); `TERMUX_INSTALL` tidak punya entry amp; npm unscoped `amp` = library messaging tak terkait (tjholowaychuk/node-amp, v0.3.1), `@ampcode/cli` (eks `@sourcegraph/amp`) memang ADA tapi optional deps-nya HANYA darwin/linux/win32 — tidak ada build android/termux, sehingga `npm install -g @ampcode/cli` tidak menarik biner `amp` yang berfungsi di sini; PyPI `AMP` = parser matematika (Ini Oguntola); Homebrew `amp` = text editor terminal (amp.rs / jmacdonald) → TIDAK ada rute install resmi terverifikasi. Catatan: CLI resmi `@ampcode/cli` ada untuk mac/linux/win, tapi tetap TIDAK berlaku untuk Termux/android-arm64. Sesuai keputusan user untuk tool `NO_INSTALL`. Commit `446f78f`.
> **A10 qwen = done (2026-09-09):** install idempoten `npm i -g @qwen-code/qwen-code` (fakta `cli_presets.py:79`); launch **OpenAI-compatible** — qwen forward ke aigate `/v1/chat/completions` (wiring persis mirip `_qwen_builder` di `cli_tools_router.py:526-567`: set `OPENAI_API_BASE`+`OPENAI_API_KEY` + generate `.qwen/settings.json` (`modelProviders.openai` `baseUrl`=gateway, `envKey`=`OPENAI_API_KEY`, `security.auth.selectedType`=`openai`)). Bukti `cli_presets.py:181` = `qwen` = `LAUNCH_VERIFIED` (OpenAI-compatible). npm `@qwen-code/qwen-code` v0.23.1 pure-JS tapi butuh Node >=22. `bash -n` clean; mode exec. Commit `73478a0`.
> **A11 cline = done (2026-09-09):** install idempoten `npm i -g cline` (fakta `cli_presets.py:80`); launch **OpenAI-compatible** — cline forward ke aigate `/v1/chat/completions` (wiring persis mirip `_cline_builder` di `cli_tools_router.py:732-764`: flags `cline auth --provider openai-native --apikey <key> --modelid <model> --baseurl <base>` + set `OPENAI_API_BASE`+`OPENAI_API_KEY`). Bukti `cli_presets.py:182` = `cline` = `LAUNCH_VERIFIED` (OpenAI-compatible). npm `cline@3.0.61` TIDAK punya variant binary `android` → known-broken di Termux/aarch64 (terpasang tapi gagal jalan; bukan blocker, sama pola claude/codex/kilo/amp). `bash -n` clean; mode exec. Commit `d931921`.

> **A12 kilo = done (2026-09-09):** install idempoten `npm i -g @kilocode/cli` (fakta `cli_presets.py:81`); launch **OpenAI-compatible** — kilo forward ke aigate `/v1/chat/completions` (wiring persis mirip `_kilo_builder` di `cli_tools_router.py:616-729`: tulis trusted additive config `KILO_CONFIG`=`.kilo/aigate-kilo.json` dengan provider `aigate` via `npm: "@ai-sdk/openai-compatible"`, `options.baseURL`=gateway, `options.apiKey`=`{env:OPENAI_API_KEY}` — secret TIDAK ke disk; env `OPENAI_API_BASE`+`OPENAI_API_KEY`; flag `-m aigate/<model>` bila `AIGATE_MODEL` disetel). Bukti `cli_presets.py:183` = `kilo` = `LAUNCH_VERIFIED` (OpenAI-compatible). npm `@kilocode/cli@7.5.16` TIDAK punya variant binary `android` → known-broken di Termux/aarch64 (terpasang tapi gagal jalan; bukan blocker, sama pola claude/codex/cline/amp). `bash -n` clean; mode exec. Commit `2a194cc`.

> **GRUP A SELESAI (12/12):** seluruh 12 tool Grup A (`agentic_coding`) selesai — A1 claude, A2 opencode, A3 gemini, A4 codex, A5 antigravity, A6 phi, A7 aider, A8 goose, A9 amp, A10 qwen, A11 cline, A12 kilo. Lanjut Grup B (B1..B6) + Grup C (C1..C6).

## Grup B — Autonomous Software Agents (`autonomous_agents`)

| # | Tool | Binary | Install (pkg/PM) | Dep (pkg/PM) | Launch | Status |
|---|------|--------|------------------|--------------|--------|--------|
| B1 | openhands | openhands | `uv tool install openhands` (butuh Python 3.12) / `pip install openhands` (fallback) | python (uv/pip) | verified | done |
| B2 | swe-agent | swe-agent | `NO_INSTALL` (no-op) | — | unsupported (install_unverified) | done |
| B3 | open-interpreter | interpreter | `pip install open-interpreter` | python (pip) | verified | done |
| B4 | autogpt | autogpt | `NO_INSTALL` (no-op) | — | unsupported (install_unverified) | done |
| B5 | gpt-researcher | gpt-researcher | `pip install gpt-researcher` | python (pip) | unsupported (not_a_cli) | done |
| B6 | crewai | crewai | `pip install crewai` | python (pip) | unsupported (not_a_cli) | done |

> **B1 openhands = done (2026-09-09):** install pilih `uv` dulu (`uv tool install openhands`, butuh Python 3.12), fallback `ensure_installed` → `pip install openhands` (fakta `cli_presets.py:88` = `pip install openhands`). Launch **OpenAI-compatible** — openhands forward ke aigate `/v1/chat/completions` (wiring persis mirip `_openhands_builder` di `cli_tools_router.py:960-972`: set env `LLM_BASE_URL`+`LLM_API_KEY`+`LLM_MODEL=openai/<model>` ke gateway, flag `--override-with-envs`). Bukti `cli_presets.py:190` = `openhands` = `LAUNCH_VERIFIED` (OpenAI-compatible). PyPI `openhands` v1.16.0 pure-python tapi butuh **Python 3.12** (`requires_python` gagal resolve di 3.13+ → `uv`/`pip` gagal bila `python3` = 3.13+; butuh venv/pyenv 3.12) — known-broken di 3.13+, bukan blocker. `bash -n` clean; mode exec.
> **B2 swe-agent = done (2026-09-09):** **NO_INSTALL** — script HANYA menampilkan pesan `swe-agent: NO_INSTALL — belum ada install terverifikasi` lalu `exit 0`, TIDAK memasang apa pun (no side-effect). Bukti `cli_presets.py:89` (`install: NO_INSTALL`) + `cli_presets.py:216` (`LAUNCH_UNSUPPORTED`/`REASON_INSTALL_UNVERIFIED`); `TERMUX_INSTALL` tidak punya entry swe-agent; PyPI `swe-agent` = **404** (tidak ada paket), `sweagent` = **v0.0.1** tapi library butuh **Docker + conda** (tidak praktis di Termux), GitHub setup resmi berat → cross-check 3 sumber tidak ada install terverifikasi. **Bug yang sudah dibenerin:** versi awal pesan NO_INSTALL pakai backtick command-substitution yg mengeksekusi `pip install swe-agent`; sudah dibenerin jadi teks statis (aturan: pesan NO_INSTALL harus literal, jangan dibungkus backtick/`$()`). Sesuai keputusan user untuk tool `NO_INSTALL`. Commit `13a257c`.
> **B3 open-interpreter = done (2026-09-09):** install idempoten `python3 -m pip install open-interpreter` (fakta `cli_presets.py:90` = `pip install open-interpreter`, bin `interpreter`); launch **OpenAI-compatible** — open-interpreter forward ke aigate `/v1/chat/completions` (wiring persis mirip `_interpreter_builder` di `cli_tools_router.py:824-837`: `interpreter --api_base <base> --api_key <key> [--model openai/<model>]` + env `OPENAI_API_BASE`+`OPENAI_API_KEY`). Bukti `cli_presets.py:196` = `open-interpreter` = `LAUNCH_VERIFIED` (OpenAI-compatible). PyPI `open-interpreter` 0.4.3 pure-python, `requires_python ">=3.9,<4"` (install di Python 3.9–3.13; host 3.14.6 masih `<4` → resolver lolos, kontras openhands yang pin 3.12). **Catatan product drift (bukan blocker):** situs live `docs.openinterpreter.com` + repo GitHub sekarang nggarap produk **Rust/Codex-fork** yang TIDAK punya flag `--api_base`/`--api_key`; tapi paket `pip install open-interpreter` (0.4.3, Python line) yang dipasang preset **MASIH punya** flag `--api_base`/`--api_key` (terkonfirmasi dari PyPI 0.4.3 README + builder aigate). Script pakai flag Python package — benar per preset; JANGAN pakai `curl install.sh` dari situs live (itu produk Rust yang salah). `bash -n` clean; mode exec. Commit `31b9a04`.
> **B4 autogpt = done (2026-09-09):** **NO_INSTALL** — script HANYA menampilkan pesan `autogpt: NO_INSTALL — belum ada install terverifikasi di environment ini.` lalu `exit 0`, TIDAK memasang apa pun (no side-effect). Bukti `cli_presets.py:91` (`install: NO_INSTALL`) + `cli_presets.py:217` (`LAUNCH_UNSUPPORTED`/`REASON_INSTALL_UNVERIFIED`); `TERMUX_INSTALL` tidak punya entry autogpt; PyPI `autogpt` = **placeholder/squat tak terkait** (author "Shadow Walker", `0.0.1.dev0`, `requires_dist: ["torch"]` SAJA, TIDAK ada console script → TIDAK menghasilkan biner `autogpt`); GitHub resmi `Significant-Gravitas/AutoGPT` = **platform Docker-based** (self-host butuh Docker + config + API key sendiri, berat & tidak praktis di Termux/android-arm64) → cross-check 3 sumber tidak ada install terverifikasi. Sesuai keputusan user untuk tool `NO_INSTALL`. Commit `a5d1a91`.

> **B5 gpt-researcher = done (2026-09-09):** **NOT_A_CLI** — script HANYA menampilkan pesan penjelasan lalu `exit 0`, TIDAK memasang/menjalankan apa pun yang bisa di-spawn (no side-effect, idempoten). Bukti `cli_presets.py:92` (`install: _pip("gpt-researcher")` — paket ADA & RESMI, `pip install gpt-researcher`, PyPI `gpt-researcher` v0.16.0 oleh Assaf Elovic) + `cli_presets.py:197-204` (`LAUNCH_UNSUPPORTED`/`REASON_NOT_A_CLI`); PyPI `gpt-researcher` metadata TIDAK ada `console_scripts`/`[project.scripts]`/`entry_points` → `pip install` TIDAK menghasilkan biner `gpt-researcher`; docs resmi cuma `python cli.py "<query>"` (wajib query, tulis report lalu EXIT) + server mode `uvicorn main:app`/Docker — bukan CLI biner interaktif. aigate gak punya `_gpt_researcher_builder` di `_LAUNCH_BUILDERS` → `resolve()` 409. BUKAN murni `NO_INSTALL` (paketnya ada & resmi), tapi memang gak bisa di-launch sebagai CLI. Sesuai keputusan user: script pesan + `exit 0`, TIDAK install apa pun yang bisa di-spawn. Commit `cd346b4`.

> **B6 crewai = done (2026-09-09):** **NOT_A_CLI** — script HANYA menampilkan pesan penjelasan lalu `exit 0`, TIDAK memasang/menjalankan apa pun yang bisa di-spawn (no side-effect, idempoten). Bukti `cli_presets.py:93` (`install: _pip("crewai")` — paket ASLI & RESMI, `pip install crewai`, PyPI `crewai` v1.15.20 oleh crewAIInc) + `cli_presets.py:205-215` (`LAUNCH_UNSUPPORTED`/`REASON_NOT_A_CLI`); komentar asli aigate: console script `crewai` exists (wheel `entry_points.txt` `[console_scripts] crewai = crewai_cli.cli:crewai`), tapi itu framework project scaffolder/runner — `crewai run`/`chat` menjalankan Crew/Flow YANG DIDEKLARESIKAN DI PROYEK di CWD dan TIDAK menerima argumen model/base-url/prompt di launch; di direktori kosong keduanya error. aigate gak punya `_crewai_builder` di `_LAUNCH_BUILDERS` → `resolve()` 409. PyPI v1.15.20 punya `console_scripts` (install VALID, menghasilkan biner `crewai` di PATH) TAPI biner itu scaffolder/runner framework, bukan chat assistant; `requires_python ">=3.10,<3.14"`. Docs resmi (docs.crewai.com + github.com/crewAIInc/crewAI): `crewai create flow / install / run / chat / login / deploy` beroperasi pada PROYEK di CWD; konfigurasi LLM (OpenAI-compatible) ditulis di kode proyek atau env `OPENAI_API_KEY`/`OPENAI_API_BASE_URL` — BUKAN surface CLI. BUKAN murni `NO_INSTALL` (paketnya ada & resmi), tapi memang gak bisa di-launch sebagai CLI. Sesuai keputusan user: script pesan + `exit 0`, TIDAK install apa pun yang bisa di-spawn. Commit `150475f`.

> **GRUP B SELESAI (6/6):** seluruh 6 tool Grup B (`autonomous_agents`) selesai — B1 openhands, B2 swe-agent, B3 open-interpreter, B4 autogpt, B5 gpt-researcher, B6 crewai. Lanjut Grup C (C1..C6).

## Grup C — Chat & Shell Assistants (`chat_shell`)

| # | Tool | Binary | Install (pkg/PM) | Dep (pkg/PM) | Launch | Status |
|---|------|--------|------------------|--------------|--------|--------|
| C1 | llm | llm | `pip install llm` | python (pip) | verified | done |
| C2 | sgpt | sgpt | `NO_INSTALL` (no-op) | — | unsupported (install_unverified) | todo |
| C3 | mods | mods | `NO_INSTALL` (no-op) | — | unsupported (no_binary) | todo |
| C4 | oterm | oterm | `pip install oterm` | python (pip) | verified | todo |
| C5 | gptme | gptme | `pip install gptme` | python (pip) | verified | todo |
| C6 | aichat | aichat | `pkg install aichat` (override) / `cargo install aichat` | pkg (atau rust/cargo) | verified | todo |

> **C1 llm = done (2026-09-09):** install idempoten `pip install llm` (fakta `cli_presets.py:100` = `_pip("llm")` → `pip install llm`); launch **OpenAI-compatible** — llm forward ke aigate `/v1/chat/completions` (wiring persis mirip `_llm_builder` di `cli_tools_router.py:570-592`: `llm openai endpoint <base> [-m <model>] --key <key> --chat` (atau `--models` bila tanpa model) + env `OPENAI_API_BASE`+`OPENAI_API_KEY`). Bukti `cli_presets.py:219` = `llm` = `LAUNCH_VERIFIED` (OpenAI-compatible). PyPI `llm` 0.35 (simonw) butuh Python >=3.10. **Catatan Termux (known-broken, bukan blocker):** di Termux/aarch64 + Python 3.14, `pip install llm` gagal build `jiter` (tidak ada wheel Android, butuh `pkg install rust`) → install bisa gagal di perangkat ini. `bash -n` clean; mode exec.

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

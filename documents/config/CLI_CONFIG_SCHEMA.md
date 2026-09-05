# CLI Tool Presets & Plugin — Config Schema

Skema config untuk grouping tool CLI (PRD §2.6.1, FSD §2.6.1, UX §3). Runtime
config (grup & tool preset) disimpan di **DB** (tabel `CLIToolGroup` / `CLITool` per
ERD) — lihat ADR-010 (config di DB, bukan file). File YAML/JSON di bawah hanya
berlaku sebagai **format seed/import** (Roadmap §6), bukan sumber kebenaran.

Sumber seed sebenarnya: `src/backend/cli_presets.py` (`CLI_PRESETS`), yang
di-**upsert** ke DB setiap startup (baris preset disegarkan; `enabled` dan baris
buatan user tidak pernah disentuh).

> **Catatan verifikasi (2026-09-05):** string `install` di bawah sudah dicek ke
> registry npm/PyPI. Versi lama memakai `pip install <nama>` untuk semuanya dan
> sebagian besar menunjuk ke paket YANG BEDA: `pip install codex` = web server
> arsip komik, `pip install gemini` = framework DB genetika, `pip install
> claude-code` = stub "reserved", `pip install aichat` = proyek lain. Tool yang
> tidak punya paket terpasang untuk platform ini diberi `install: null` (UI
> menjalankan `echo` no-op, bukan memasang sampah).

## Schema (YAML)
```yaml
version: 1
groups:
  - id: agentic_coding        # Grup A
    label: "Agentic Coding Assistants"
    tools:
      - { name: claude,      binary: claude,      install: "npm install -g @anthropic-ai/claude-code", launch: unsupported }
      - { name: opencode,    binary: opencode,    install: "npm install -g opencode-ai",               launch: verified }
      - { name: codex,       binary: codex,       install: "npm install -g @openai/codex",             launch: unsupported }
      - { name: gemini,      binary: gemini,      install: "npm install -g @google/gemini-cli",        launch: unsupported }
      - { name: antigravity, binary: antigravity, install: null,                                        launch: unsupported }
      - { name: phi,         binary: phi,         install: null,                                        launch: unsupported }
      - { name: aider,       binary: aider,       install: "pip install aider-chat",                    launch: verified }
      - { name: goose,       binary: goose,       install: null,                                        launch: unsupported }
      - { name: amp,         binary: amp,         install: null,                                        launch: unsupported }
      - { name: qwen,        binary: qwen,        install: "npm install -g @qwen-code/qwen-code",      launch: verified }
      - { name: cline,       binary: cline,       install: "npm install -g cline",                      launch: pending }
      - { name: kilo,        binary: kilo,        install: "npm install -g @kilocode/cli",             launch: pending }
  - id: autonomous_agents     # Grup B
    label: "Autonomous Software Agents"
    tools:
      - { name: openhands,        binary: openhands,        install: "pip install openhands-ai",    launch: pending }
      - { name: swe-agent,        binary: swe-agent,        install: null,                          launch: unsupported }
      - { name: open-interpreter, binary: interpreter,      install: "pip install open-interpreter", launch: pending }
      - { name: autogpt,          binary: autogpt,          install: null,                          launch: unsupported }
      - { name: gpt-researcher,   binary: gpt-researcher,   install: "pip install gpt-researcher",  launch: pending }
      - { name: crewai,           binary: crewai,           install: "pip install crewai",          launch: pending }
  - id: chat_shell            # Grup C
    label: "Chat & Shell Assistants"
    tools:
      - { name: llm,    binary: llm,    install: "pip install llm",   launch: verified }
      - { name: sgpt,   binary: sgpt,   install: null,                launch: unsupported }
      - { name: mods,   binary: mods,   install: null,                launch: unsupported }
      - { name: oterm,  binary: oterm,  install: "pip install oterm", launch: pending }
      - { name: gptme,  binary: gptme,  install: "pip install gptme", launch: pending }
      - { name: aichat, binary: aichat, install: "cargo install aichat",          launch: verified }
```

## Field
- `groups[].id` unik, `label` tampilan.
- `tools[].name` id, `binary` perintah cek (`which`/`where`), `install` opsional.
- Minimal 5 tool per grup.
- `presets`/`default_flags` sengaja kosong: flag adalah bagian dari bentuk
  launch tool, dan bentuk launch hidup di builder yang terverifikasi — menaruh
  tebakan flag di preset itulah yang menghasilkan `claude openai-compatible`.

## Status launch (`launch:`)
Registry-nya di `cli_presets.LAUNCH_SUPPORT` (level kode, BUKAN kolom DB — status
ini berubah mengikuti builder, bukan data user), diekspos lewat `ToolDTO`
(`launch_mode` + `launch_reason`) dan dipakai UI + API:

| mode | arti | UI | `POST /resolve` |
|---|---|---|---|
| `verified` | builder launch ada + tool bicara format OpenAI gateway | normal | 200 + run_command |
| `pending` | tool bisa, bentuk launch belum ditulis/diverifikasi | dicoret | 409 `tool_unsupported` |
| `unsupported` | butuh format yang tidak di-serve gateway (Anthropic `/v1/messages`, Google `generateContent`), atau bukan CLI, atau tidak ada binary platform ini | dicoret | 409 `tool_unsupported` |

`launch_reason` = kode stabil (`anthropic_only`, `gemini_only`, `responses_only`,
`not_a_cli`, `no_binary`, `install_unverified`) yang diterjemahkan UI lewat
`cli.reason.*`. Tool tanpa entri registry dianggap `pending` (fail-closed).

### Catatan platform (Termux/aarch64) — hasil cek langsung di perangkat
- `process.platform` Node di Termux = **`android`**, jadi npm TIDAK pernah
  memasang optionalDependency `*-linux-arm64`. CLI Node yang binary-nya
  per-platform (claude, codex, cline, kilo, amp) lolos install tapi mati saat
  jalan (`Missing optional dependency ...`).
- Shebang `#!/usr/bin/env X` juga rusak di perangkat ini: `/usr/bin` tidak ada
  dan `libtermux-exec-*-ld-preload.so` versi terpasang tidak menulis ulang path
  itu (diuji: tetap `bad interpreter`). Semua script npm (`vitest`, `eslint`,
  dst.) kena — yang bisa jalan cuma yang punya shim bash bershebang absolut,
  contoh pola yang dipakai opencode di perangkat ini:
  `exec grun .../opencode-linux-arm64/bin/opencode`.
- Repo Termux (`pkg`) punya beberapa CLI asli: `codex` (tur-repo, 0.122.0),
  `aichat` (0.30.0 — sudah diverifikasi jalan end-to-end ke gateway).
  `goose` di repo Termux = tool migrasi DB, BUKAN agen Block — jangan tertipu nama.
- Bentuk launch aichat (dites langsung di 0.30.0): field confignya `clients:`
  (bukan `custom_providers:` / `providers:` — dua-duanya gagal load), tiap
  entri `type: openai-compatible` + `name` + `api_base` + `api_key` +
  `models: [{name: ...}]` (string polos ditolak serde: "expected struct
  ModelData"). Model dipanggil `aigate:<model>` dan file config-nya di-scope
  lewat env `AICHAT_CONFIG_FILE` biar `~/.config/aichat/config.yaml` user gak
  ketimpa.
- Codex diverifikasi live: 0.122.0 menolak `wire_api = "chat"`
  ("no longer supported", openai/codex discussion #7782) dan hanya menerima
  `responses` → butuh `/v1/responses` di gateway. Selama gateway belum
  meng-expose Responses API, codex = `unsupported`.

### Bentuk launch per tool (sumber: dokumen resmi upstream)
- **aider** — flag eksplisit: `--openai-api-base <base> --openai-api-key <key>
  --model openai/<model>`.
- **opencode** — tulis `opencode.json` (provider custom
  `@ai-sdk/openai-compatible`, `options.baseURL` + `apiKey`, `models` hasil
  discovery) + `model` default `aigate/<id>`, lalu buka TUI `opencode`
  (BUKAN `opencode run`, yang one-shot dan nunggu stdin).
- **aichat** — tulis YAML dengan field `clients:` (`type: openai-compatible`,
  `name: aigate`, `api_base`, `api_key`, `models: [{name: ...}]`), model
  `aigate:<id>`, di-scope pakai env `AICHAT_CONFIG_FILE`.
- **qwen** (Qwen Code) — tulis `.qwen/settings.json` PROJECT-scope (override
  `~/.qwen/settings.json` user, jadi config user gak disentuh):
  `modelProviders.openai[] = {id, name, baseUrl, envKey: OPENAI_API_KEY}`,
  `security.auth.selectedType = "openai"`, `model.name = <id>`, `env`
  berisi key. Auth type `openai` = protokol OpenAI-compatible (docs:
  `docs/users/configuration/auth.md`).
- **llm** — tidak perlu file config sama sekali: `llm openai endpoint <base>
  -m <model> --key <key> --chat` (docs: "Run against an endpoint without
  configuring it"). Tanpa model -> `--models` (daftar model dari gateway).
- **gemini** — dokumen resminya (docs/cli/model.md + settings.md) TIDAK
  mengenal provider OpenAI-compatible; hanya API Gemini → `unsupported`
  (`gemini_only`), bukan sekadar belum dikerjain.

## Plugin
File tambahan (YAML/JSON) bisa di-drop di folder `config/cli-plugins/` dan di-merge
ke tabel DB (`CLIToolGroup`/`CLITool`) saat startup (nama grup bebas asal `id` unik).

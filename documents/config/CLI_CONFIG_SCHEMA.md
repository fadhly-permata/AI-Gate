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
      - { name: cline,       binary: cline,       install: "npm install -g cline",                      launch: verified }
      - { name: kilo,        binary: kilo,        install: "npm install -g @kilocode/cli",             launch: verified }
  - id: autonomous_agents     # Grup B
    label: "Autonomous Software Agents"
    tools:
      - { name: openhands,        binary: openhands,        install: "pip install openhands-ai",    launch: pending }
      - { name: swe-agent,        binary: swe-agent,        install: null,                          launch: unsupported }
      - { name: open-interpreter, binary: interpreter,      install: "pip install open-interpreter", launch: verified }
      - { name: autogpt,          binary: autogpt,          install: null,                          launch: unsupported }
      - { name: gpt-researcher,   binary: gpt-researcher,   install: "pip install gpt-researcher",  launch: unsupported }
      - { name: crewai,           binary: crewai,           install: "pip install crewai",          launch: pending }
  - id: chat_shell            # Grup C
    label: "Chat & Shell Assistants"
    tools:
      - { name: llm,    binary: llm,    install: "pip install llm",   launch: verified }
      - { name: sgpt,   binary: sgpt,   install: null,                launch: unsupported }
      - { name: mods,   binary: mods,   install: null,                launch: unsupported }
      - { name: oterm,  binary: oterm,  install: "pip install oterm", launch: verified }
      - { name: gptme,  binary: gptme,  install: "pip install gptme", launch: verified }
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

> **Dasar verifikasi `verified`** (dicatat per tool, biar gak ketuker):
> - **dijalankan langsung di perangkat**: `aider`, `opencode`, `aichat`
>   (request-nya beneran nyampe gateway -> upstream -> jawaban).
> - **dokumen resmi upstream** (tool-nya gak bisa dipasang di Termux):
>   `qwen` (docs/users/configuration/auth.md), `llm` (docs/other-models.md),
>   `gptme` (gptme.org/docs/providers.html), `cline` (apps/cli/README.md).
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
- **gptme** — tanpa file config: `OPENAI_BASE_URL=<base> gptme -m local/<model>`
  (docs/providers.html bagian "Local"). Prefix `local/` WAJIB — model `openai/*`
  kelas GPT-5 otomatis dilewatin ke `/v1/responses` yang gak di-serve gateway;
  key lewat env `OPENAI_API_KEY` (bukan flag, jadi gak nongol di `ps`).
- **cline** — `cline auth --provider openai-native --apikey <key> --modelid
  <model> --baseurl <base> && cline` (apps/cli/README.md, "Quick provider
  setup"). Tanpa model: langkah setup dilewatin, `cline` doang (gak ngarang id).
- **kilo** (Kilo Code CLI, npm `@kilocode/cli`) — tulis file config MILIK kita
  sendiri, `.kilo/aigate-kilo.json`, lalu tunjukin lewat env yang dipercaya:
  `KILO_CONFIG=.kilo/aigate-kilo.json kilo -m aigate/<id>`. Isinya
  `provider.aigate = { npm: "@ai-sdk/openai-compatible", options: { baseURL,
  apiKey: "{env:OPENAI_API_KEY}" }, models: { <id>: { name } } }` +
  `model: "aigate/<id>"` (docs/ai-providers/openai-compatible.md tab "CLI" dan
  docs/code-with-ai/agents/custom-models.md — format `provider-id/model-id`).
  Kenapa BUKAN `.kilo/kilo.json` / `./kilo.json`: (1) itu path config user —
  nulis di situ = nimpa punya dia (docs/getting-started: "Project config:
  `kilo.jsonc` di root project, atau `.kilo/kilo.jsonc`"); (2) config project
  TIDAK dipercaya, jadi `{env:VAR}` ditolak dan key harus ditulis polos di disk
  (custom-models.md: reference cuma resolve di "trusted location: global config,
  a config passed via `KILO_CONFIG` / `KILO_CONFIG_CONTENT`, or managed config").
  `KILO_CONFIG` itu layer TAMBAHAN (tabel precedence di
  docs/contributing/architecture/cli-runtime.md: global dulu, baru explicit
  file) — config + auth user tetap jalan, key gak pernah nyentuh disk. Flag `-m`
  punya prioritas 1 di atas key `model` config (custom-models.md, "Model Loading
  Priority"), jadi pilihan aigate gak bisa kalah sama config user. `limit`
  sengaja gak ditulis: opsional per dokumen, ngarang context window = nebak.
  Tanpa model: config tetap nulis provider + semua model hasil discovery, TANPA
  key `model` dan TANPA `-m` -> TUI `kilo` biasa, user pilih lewat `/models`.
  DOCS-VERIFIED only (binary per-platform, gak ada build Termux — sama kayak
  cline).
- **open-interpreter** — flag resmi untuk paket PYTHON yang dipasang
  `pip install open-interpreter` (PyPI `open-interpreter` 0.4.3, rilis 2024-10-26):
  `interpreter --api_base <base> --api_key <key> --model openai/<model>` (docs
  fork komunitas `endolith/open-interpreter`: `docs/settings/all-settings.mdx`
  bagian "API Base"/"API Key"/"Model Selection" +
  `docs/language-models/local-models/lm-studio.mdx` — server OpenAI-compatible
  via `--api_base`, `llm.model = "openai/x"` = kirim format OpenAI; LiteLLM
  melepas prefix sebelum request jadi gateway terima id mentah / combo verbatim).
  `interpreter` tanpa prompt = chat interaktif (README "Interactive Chat").
  Tanpa model: bentuk LM-Studio TANPA `--model` (model default OI sendiri, gak
  ngarang id). **Catatan:** repo GitHub `OpenInterpreter/open-interpreter` sekarang
  berisi agen Rust BARU (fork Codex, install via curl) yang CLI-nya TIDAK punya
  `--api_base`/`--api_key` — preset ini menarget artefak pip (Python), jadi dasar
  verifikasinya dokumen Python + README PyPI, BUKAN dokumen Rust. DOCS-VERIFIED
  only (gak menjalankan installer / binary).
- **oterm** (ggozad/oterm, PyPI 0.24.0) — TIDAK ada flag CLI untuk
  model/base/key (source `cli/oterm.py`: cuma `--version/--upgrade/--config/
  --db/--data-dir`); satu-satunya rute terdokumentasi = file config: tulis
  `config.json` MILIK kita sendiri di direktori namespaced `.oterm-aigate/`,
  lalu tunjuk lewat env resminya: `OTERM_DATA_DIR=.oterm-aigate oterm`.
  Isinya blok `openaiCompatible.aigate = { base_url: <gateway>, api_key:
  "${OPENAI_API_KEY}" }` — endpoint bernama dengan `base_url` + `api_key`
  reference env (docs: ggozad.github.io/oterm/app_config/ bagian
  "openaiCompatible — custom OpenAI-compatible endpoints" + "Where config.json
  lives"; source: `providers/__init__.py` expand `${VAR}`, `agent.py`
  `openai-compat/<name>` → pydantic-ai `OpenAIChatModel` = wire
  chat-completions yang gateway serve). Key gak pernah nyentuh disk (pola
  kilo). Kenapa BUKAN `~/.local/share/oterm/config.json`: itu path user —
  nulis di situ = nimpa theme/keymap/mcpServers punya dia; efek samping yang
  dipilih sadar: chat history (`store.db` satu direktori) mulai fresh untuk
  launch ini. Model TIDAK bisa disuntik saat launch — dialog new-chat oterm
  yang milih/ketik; gateway expose `GET /v1/models` jadi suggestion live, dan
  ref aigate (`combo:<n>`, `provider:<n>:<id>`, id mentah) bisa diketik polos
  karena oterm meneruskan model apa adanya ke gateway. Akibatnya command
  IDENTIK untuk semua bentuk ref dan gak ada yang diarang. `oterm` tanpa
  argumen = TUI interaktif. DOCS-VERIFIED only (docs & source dibaca
  2026-09-05; gak install/jalankan).
- **gpt-researcher** — BUKAN CLI: `pip install gpt-researcher` (PyPI 0.16.0)
  memasang LIBRARY + backend web app saja, TIDAK ada console script
  `gpt-researcher` — `pyproject.toml` master tidak punya `[project.scripts]`
  dan `setup.py` tidak punya `entry_points` (dibaca 2026-09-05), jadi
  `command -v gpt-researcher` tidak akan pernah lolos dan branch install di
  PTY cuma muter-muter. Halaman "Run with CLI" di docs.gptr.dev pun
  mensyaratkan CLONE repo dulu: `python cli.py "<query>" --report_type <t>` —
  query POSISIONAL WAJIB, tulis file report lalu exit (one-shot, bukan chat
  interaktif — pelajaran `opencode run`). Route env gateway untuk library-nya
  memang terdokumentasi (`docs/…/llms/llms.md`: `OPENAI_BASE_URL` +
  `OPENAI_API_KEY` + `FAST_LLM=openai:<id>` — catatan: namanya `OPENAI_BASE_URL`,
  bukan `OPENAI_API_BASE` yang di-export launcher), tapi tidak ada binary yang
  bisa di-launch → `unsupported` (`not_a_cli`), bukan sekadar belum dikerjain.
- **gemini** — dokumen resminya (docs/cli/model.md + settings.md) TIDAK
  mengenal provider OpenAI-compatible; hanya API Gemini → `unsupported`
  (`gemini_only`), bukan sekadar belum dikerjain.

## Plugin
File tambahan (YAML/JSON) bisa di-drop di folder `config/cli-plugins/` dan di-merge
ke tabel DB (`CLIToolGroup`/`CLITool`) saat startup (nama grup bebas asal `id` unik).

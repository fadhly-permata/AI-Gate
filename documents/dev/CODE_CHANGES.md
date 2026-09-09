# Code Changes Register (code ↔ docs alignment)

## 2026-09-09 — feat: aigate Anthropic `/v1/messages` inbound (kayak litellm) — DONE (5 commit: `253aae5` `bb3b6c9` `7f330a1` `4986adc` `41d24f8`, branch `feat/anthropic-inbound`)

**Tujuan:** aigate serve Anthropic-compatible `POST /v1/messages` **native** (tanpa litellm di tengah) supaya `claude-code` bisa `ANTHROPIC_BASE_URL=<aigate>/v1/messages`. Referensi desain: `documents/architecture/anthropic-inbound-endpoint.md`.

### `src/backend/gateway/translator.py` (+445 baris)
- NEW `anthropic_messages_request_to_openai_chat(payload)` (L630): Anthropic Messages request → OpenAI chat payload. Tolak `stream:true` → `anthropic_streaming_unsupported`; tolak `thinking.enabled` → `anthropic_unsupported_field`; `system` (str|blocks) → leading system message; `messages` via `_anthropic_to_openai_messages` (L469); `tools` via `_anthropic_tools_to_openai_tools` (L576); `tool_choice` via `_anthropic_tool_choice_to_openai` (L597); inject default `max_tokens`; `temperature/top_p/top_k/stop_sequences` pass-through.
- NEW `openai_chat_response_to_anthropic_messages(chat_result, request_model)` (L718): OpenAI chat response → Anthropic Messages envelope (`type/role/model/content[text|tool_use]/stop_reason/usage`); `finish_reason`→`stop_reason` via `_anthropic_stop_reason` (L375) + `_openai_finish_to_anthropic` (L619); id→`msg_<base>`.
- NEW `class AnthropicMessagesRequest(_BaseModel)` (L828, Pydantic v1, `extra="allow"`): validasi shape (model/messages/max_tokens/stream).
- NEW helper inbound: `_anthropic_to_openai_messages` (L469), `_anthropic_system_to_text` (L561), `_anthropic_tools_to_openai_tools` (L576), `_anthropic_tool_choice_to_openai` (L597), `_anthropic_stop_reason` (L375), `_openai_finish_to_anthropic` (L619).
- EXTEND `_translate_request_anthropic` (L183): kini forward OpenAI `tools`/`tool_choice` ke upstream anthropic (double-translation round-trip) via NEW `_openai_tools_to_anthropic` (L233) + `_openai_tool_choice_to_anthropic` (L253); additif, behavior lama tetap.
- NEW konstanta kode stabil: `ANTHROPIC_STREAMING_UNSUPPORTED_CODE`, `ANTHROPIC_UNSUPPORTED_FIELD_CODE`, `ANTHROPIC_MISSING_MODEL_CODE`.

### `src/backend/gateway/router.py` (+230 baris)
- NEW `@router.post("/v1/messages")` → `messages_completions` (L500): B5.6 wrapper (timing + `_record_request_log_safe`) + render error berbentuk Anthropic (`_anthropic_error_response` L648 / `_anthropic_error_body` L643) — deviasi per-surface yang didokumentasi (§2.4 design).
- NEW `async def _handle_anthropic_messages(request, ctx)` (L549): mirror `_handle_responses`; parse → `anthropic_messages_request_to_openai_chat` → `resolve_target` (TargetNotFound→`model_not_found`) → combo/adapter → `_record_usage_safe` → `openai_chat_response_to_anthropic_messages`; reuse pipeline chat/responses tanpa duplikasi.
- NEW sibling routes (litellm parity): `@router.post("/v1/messages/count_tokens")` → `messages_count_tokens` (L658, estimasi heuristic UTF-8÷4, `output_tokens:0`) + `@router.post("/api/event_logging/batch")` → `event_logging_batch` (L696, stub `202 Accepted` + `{}`).
- Auth: terbuka spt chat/responses; terima **`Authorization: Bearer` ATAU `x-api-key`** (Decision 4.4); client `x-api-key` TIDAK diteruskan ke upstream (aigate punya egress cred sendiri).

### `src/backend/cli_presets.py`
- Flip `LAUNCH_SUPPORT["claude"]` (L171): `LAUNCH_UNSUPPORTED, REASON_ANTHROPIC_ONLY` → `LAUNCH_VERIFIED` (aigate kini serve inbound /v1/messages).
- Perbarui comment block (~L152–160): claude kini native Anthropic Messages via aigate (tanpa litellm); `gemini` tetap unsupported.

### `tests/backend/test_anthropic_messages.py` (BARU, 508 baris)
- 20 test: 11 pure-function (L50,67,78,106,125,148,160,172,181,202,233) + 9 route-level (L344,363,374,391,403,415,438,454,462).
- QA: 11 pure **PASSED**; 9 route **FAILED** murni gara-gara env mismatch `httpx 0.28.1` vs `starlette 0.27.0` (pre-existing, BUKAN regression — terkonfirmasi di `test_gateway.py` pre-existing yang sama persis gagal).

### `scripts/cli-tools/claude.sh` (−37/+32)
- Re-wire: buang chain litellm; `claude-code` diarahkan langsung ke aigate `/v1/messages` (`ANTHROPIC_BASE_URL` = gateway root dari `load_gateway_config`, `ANTHROPIC_API_KEY` = `AIGATE_KEY`). Reachability probe ke aigate `/v1/models` (bukan `/health/liveliness` litellm).

### `documents/architecture/anthropic-inbound-endpoint.md` (BARU) + `.opencode/reports/qa_anthropic_inbound_verification.md` (BARU)
- Desain (tech-architect) + laporan QA (status **LULUS**): py_compile bersih, 11/11 pure test passed, 0 regression translator (17/17), principle review R25 LULUS, R12 LULUS (0 `except: pass`); 9 route test gagal eksekusi murni env mismatch.

**Verifikasi PM (cepat, R14/R35):** `python -m py_compile src/backend/gateway/translator.py src/backend/gateway/router.py src/backend/cli_presets.py` → **clean**; `bash -n scripts/cli-tools/claude.sh` → **clean**. (Tidak jalanin suite penuh — batas sandbox; lihat QA report §6.)

**Open risk (bukan blocker):** 9 route-level integration test belum ke-cover runtime di sandbox gara-gara mismatch dep `httpx`/`starlette` (pre-existing). Rekomendasi: selaraskan `httpx<0.28` di `pyproject.toml`, lalu jalanin `pytest tests/backend/test_anthropic_messages.py` di env user agar jalur route handler + adapter anthropic sungguhan ter-cover (R20).

## 2026-09-09 — cli-tools install/launch scripts (branch `setup/cli-tools`) — IN PROGRESS

**Permintaan user:** buat install+launch script per CLI tool (24 tool, 3 grup) di `scripts/cli-tools/`,
wiring ke selected model/combo seperti aigate, cross-platform (Termux/Win/Linux/Mac), idempoten.

> Catatan PM: sesi ini PM sub-agent TIDAK punya Task tool, jadi `claude.sh` + `_common.sh` dikerjakan
> langsung oleh PM (deviasi R21, transparan) dalam scope ketat `scripts/cli-tools/`.

### `scripts/cli-tools/_common.sh` (BARU)
- Helper lintas-platform: `detect_os`/`detect_pm` (Termux/Linux→pkg/apt, Mac→brew, Windows→WSL/Git Bash/winget/choco),
  `load_gateway_config` (baca `~/.aigate/aigate.db` setting+endpoint, fallback `http://localhost:8080/v1` + `aigate-local`),
  `have_cmd`, `ensure_installed` (idempoten via `command -v`), `log_msg`.

### `scripts/cli-tools/claude.sh` (BARU)
- Install `npm i -g @anthropic-ai/claude-code` (idempoten). Launch **native** — claude = `anthropic_only`
  di aigate (`LAUNCH_SUPPORT`), tidak ada OpenAI-compatible builder, jadi TIDAK dipaksa wiring gateway
  (cerminkan behavior `resolve()` → 409). Catatan Termux/aarch64: npm tak pasang binary arm64 → bisa mati saat run.

### `scripts/cli-tools/opencode.sh` (BARU, 122 baris)
- Install+launch script untuk **opencode** (A2). Install via `npm i -g opencode-ai` (idempoten via `ensure_installed`).
- Launch: wiring `OPENAI_API_BASE` + `OPENAI_API_KEY` ke aigate `/v1/chat/completions` (dari `load_gateway_config`), generate `opencode.json` di CWD sebelum launch.
- Referensi sumber: `cli_presets.py:71` (preset opencode), `cli_tools_router.py:1082-1083` (wiring env vars), `cli_tools_router.py:417-431` (generate config).
- Known caveat Termux: npm registry `os` field tidak berisi `"android"` → binary musl bisa jalan native di Bionic tapi npm skip install optional deps per-platform.
- Verifikasi: `bash -n scripts/cli-tools/opencode.sh` → **clean**.

### `scripts/cli-tools/gemini.sh` (BARU, 114 baris)
- Install + launch script untuk **gemini** (A3). Install idempoten via `ensure_installed` → `npm i -g @google/gemini-cli` (alternatif `brew install gemini-cli` di macOS/Linux).
- Launch **native Google mode**: gemini CLI hanya bicara Google `generateContent` (auth `GEMINI_API_KEY`/`GOOGLE_API_KEY`/`GOOGLE_CLOUD_PROJECT`, atau interactive OAuth via browser). TIDAK di-wire ke aigate.
- Fakta kunci (cross-check R47/R48, ≥2 sumber): aigate HANYA serve OpenAI `/v1/chat/completions` + Anthropic `/v1/messages` — TIDAK ada inbound Google `generateContent` (`cli_presets.py:156-158`). Maka gemini di-mark `LAUNCH_UNSUPPORTED` / `REASON_GEMINI_ONLY` di `cli_presets.py:175`, dan tidak ada `_gemini_builder` di `cli_tools_router.py` (builder dimulai ~`:976`, hanya opencode dkk). Script sadar ini: TIDAK menyetel `ANTHROPIC_BASE_URL`/`OPENAI_API_BASE` palsu (gemini CLI mengabaikannya → no-op), melainkan launch native + warn.
- `GEMINI_MODEL` di-forward dari `AIGATE_MODEL` bila ada; reachability probe ke aigate `/v1/models` cuma warning (gemini tetap tidak dirutekan). Caveat Termux: bundle pure-JS (`bin=bundle/gemini.js`, node≥20) jalan di Bionic; optional `node-pty` tidak ada build arm64 → PTY degrade tapi CLI tetap launch.
- Verifikasi: `bash -n scripts/cli-tools/gemini.sh` → **clean**; `chmod` `-rwx------`.

### `scripts/cli-tools/codex.sh` (BARU, 136 baris)
- Install + launch script untuk **codex** (A4). Install: Termux → `pkg install codex`
  (`cli_presets.py:243`, tur-repo, bin bionic terverifikasi); non-Termux →
  `npm i -g @openai/codex` (`cli_presets.py:72`, portable string). npm registry
  `@openai/codex` v0.153.4 punya optional dep `linux-arm64`. Docs:
  github.com/openai/codex, learn.chatgpt.com/docs.
- Launch **native OpenAI mode** + warning: codex TIDAK di-wire ke aigate. Bukti
  `cli_presets.py:180` = `"codex": LaunchSupport(LAUNCH_UNSUPPORTED, REASON_RESPONSES_ONLY)`
  — aigate punya inbound `/v1/responses` (`router.py:342`) tapi **non-streaming only**
  (`responses.py:227-233`: `stream:true` → tolak `responses_streaming_unsupported`
  / `RESPONSES_STREAMING_TODO` / `STREAMING_UNSUPPORTED_CODE`), sedangkan codex CLI
  **wajib streaming** → tidak bisa di-rute. Script sadar ini: jalan native mode OpenAI
  + peringatan (sama pola gemini/claude yang unsupported), TIDAK set env palsu ke aigate.
- Verifikasi: `bash -n scripts/cli-tools/codex.sh` → **clean**; `chmod` `-rwx------`.

### `scripts/cli-tools/antigravity.sh` (BARU, 69 baris) — **A5 antigravity = NO_INSTALL (message + exit 0, no side-effect)**
- TIDAK memasang apa pun (sesuai keputusan user utk tool `NO_INSTALL`): script hanya
  menampilkan pesan lalu `exit 0` (no-op, idempoten, tanpa side-effect).
- Pesan: `antigravity: NO_INSTALL — tidak ada paket CLI terverifikasi di environment ini.`
- Fakta kunci (cross-check 3 sumber independen, R47/R48):
  - `cli_presets.py:74` → `{"name":"antigravity","binary":"antigravity","install": NO_INSTALL}`
    (NO_INSTALL didefinisikan di `cli_presets.py:45` = echo no-op).
  - `cli_presets.py:176` → `"antigravity": LaunchSupport(LAUNCH_UNSUPPORTED, REASON_NOT_A_CLI)`
    — aigate menandai antigravity BUKAN CLI yang bisa di-launch.
  - `TERMUX_INSTALL` map (`cli_presets.py:241-244`) HANYA berisi `aichat` + `codex` —
    TIDAK ada entry antigravity → di Termux pun tak ada rute install terverifikasi.
  - npm registry `antigravity` = placeholder squat (v0.0.0, "placeholder for the haters");
    `@anthropic/antigravity` 404; PyPI `antigravity` milik pihak lain (Fabien Schwob);
    Homebrew formula `antigravity` 404. Konklusi: TIDAK ada rute install resmi (npm/pip/brew).
- Script source `_common.sh` (read-only: `detect_os`/`detect_pm`/`load_gateway_config`
  + `log_msg`) lalu log pesan + `exit 0`. Tidak ada `ensure_installed`/install command.
- Verifikasi: `bash -n scripts/cli-tools/antigravity.sh` → **clean**; mode `-rwx------` (exec).

### `scripts/cli-tools/phi.sh` (BARU) — **A6 phi = NO_INSTALL (message + exit 0, no side-effect)**
- TIDAK memasang apa pun (sesuai keputusan user utk tool `NO_INSTALL`): script hanya
  menampilkan pesan lalu `exit 0` (no-op, idempoten, tanpa side-effect).
- Pesan: `phi: NO_INSTALL — belum ada install terverifikasi di environment ini.`
- Fakta kunci (cross-check 3 sumber independen, R47/R48):
  - `cli_presets.py:75` → `{"name":"phi","binary":"phi","install": NO_INSTALL}`
    (NO_INSTALL didefinisikan di `cli_presets.py:45` = echo no-op).
  - `cli_presets.py:177` → `"phi": LaunchSupport(LAUNCH_UNSUPPORTED, REASON_INSTALL_UNVERIFIED)`
    — aigate menandai phi BUKAN CLI yang bisa di-launch (install tidak terverifikasi).
  - `TERMUX_INSTALL` map (`cli_presets.py:241-244`) HANYA berisi `aichat` + `codex` —
    TIDAK ada entry phi → di Termux pun tak ada rute install terverifikasi.
  - npm `phi` = squat lama (v0.0.2, 2013, tak terkait); PyPI `phi` = library functional
    programming (cgarciae, bukan CLI); Homebrew formula `phi` 404. Konklusi: TIDAK ada
    rute install resmi (npm/pip/brew).
- Script source `_common.sh` (read-only: `detect_os`/`detect_pm`/`load_gateway_config`
  + `log_msg`) lalu log pesan + `exit 0`. Tidak ada `ensure_installed`/install command.
- Verifikasi: `bash -n scripts/cli-tools/phi.sh` → **clean**; mode `-rwx------` (exec);
  eksekusi langsung → `exit 0`, TIDAK memasang apa pun.

### `scripts/cli-tools/aider.sh` (BARU, 94 baris)
- Install + launch script untuk **aider** (A7). Install idempoten via `ensure_installed` → `python3 -m pip install aider-chat` (mirror `pip install aider-chat` per `cli_presets.py:76`).
- Launch **OpenAI-compatible** — aider bicara Chat Completions ke aigate (`/v1/chat/completions`). Wiring persis mirip `_aider_builder` (`cli_tools_router.py:355-369`): `aider --openai-api-base <base> --openai-api-key <key> [--model openai/<model>]` (aider menempelkan `/chat/completions` ke base URL otomatis).
- Env injection (setiap tool dapat ini, `cli_tools_router.py:1081-1084`): `OPENAI_API_BASE=<base>` + `OPENAI_API_KEY=<key>`; `AIGATE_MODEL` di-forward sebagai `--model openai/<AIGATE_MODEL>` bila disetel.
- Fakta kunci (cross-check): aider = `LAUNCH_VERIFIED` di `cli_presets.py:172`; PyPI `aider-chat` 0.86.2 pure-python (`py3-none-any`, lintas-platform), butuh Python 3.10–3.12 (`requires_python` gagal resolve di 3.13+). `_aider_builder` TIDAK emit config file → script juga pakai flags CLI (no `aider.conf.yml`).
- Reachability probe best-effort ke aigate `/v1/models` (warning bila gateway mati/ga reachable); aider akan gagal connect bila aigate belum nyala.
- Verifikasi: `bash -n scripts/cli-tools/aider.sh` → **clean**; mode `-rwx------` (exec).

### `scripts/cli-tools/goose.sh` (BARU, 104 baris) — **A8 goose = NO_INSTALL (message + exit 0, no side-effect)**
- TIDAK memasang apa pun (sesuai keputusan user utk tool `NO_INSTALL`): script hanya
  menampilkan pesan lalu `exit 0` (no-op, idempoten, tanpa side-effect).
- Pesan: `goose: NO_INSTALL — belum ada install terverifikasi di environment ini.`
- Fakta kunci (cross-check 5 sumber independen, R47/R48):
  - `cli_presets.py:77` → `{"name":"goose","binary":"goose","install": NO_INSTALL}`
    (NO_INSTALL didefinisikan di `cli_presets.py:45` = echo no-op).
  - `cli_presets.py:178` → `"goose": LaunchSupport(LAUNCH_UNSUPPORTED, REASON_NO_BINARY)`
    — aigate menandai goose BUKAN CLI yang bisa di-launch (biner `goose` TIDAK ada /
    tidak ada install terverifikasi untuk environment ini).
  - `TERMUX_INSTALL` map (`cli_presets.py:241-244`) HANYA berisi `aichat` + `codex` —
    TIDAK ada entry goose → di Termux pun tak ada rute install terverifikasi.
  - npm `goose` = tool Golang tak terkait (jiyinyiyong, v0.0.3, bin→bin/index.js);
    `@block/goose` 404; PyPI `goose` (Goose 1.0.0, Mike Steder) = SQL migration tool
    SQLAlchemy; Homebrew `goose` = pressly/goose (v3.28.0, `conflicts_with block-goose-cli`).
    Install resmi Block (curl release script) tak punya build aarch64-android/termux
    terverifikasi. Konklusi: TIDAK ada rute install resmi (npm/pip/brew) terverifikasi.
- Script source `_common.sh` (read-only: `detect_os`/`detect_pm`/`load_gateway_config`
  + `log_msg`) lalu log pesan + `exit 0`. Tidak ada `ensure_installed`/install command.
- Verifikasi: `bash -n scripts/cli-tools/goose.sh` → **clean**; mode `-rwx------` (exec);
  eksekusi langsung → `exit 0`, TIDAK memasang apa pun.

### `scripts/cli-tools/amp.sh` (BARU, 108 baris) — **A9 amp = NO_INSTALL (message + exit 0, no side-effect)**
- TIDAK memasang apa pun (sesuai keputusan user utk tool `NO_INSTALL`): script hanya
  menampilkan pesan lalu `exit 0` (no-op, idempoten, tanpa side-effect).
- Pesan: `amp: NO_INSTALL — belum ada install terverifikasi di environment ini.`
- Fakta kunci (cross-check 5 sumber independen, R47/R48):
  - `cli_presets.py:78` → `{"name":"amp","binary":"amp","install": NO_INSTALL}`
    (NO_INSTALL didefinisikan di `cli_presets.py:45` = echo no-op).
  - `cli_presets.py:179` → `"amp": LaunchSupport(LAUNCH_UNSUPPORTED, REASON_NO_BINARY)`
    — aigate menandai amp BUKAN CLI yang bisa di-launch (biner `amp` TIDAK ada /
    tidak ada install terverifikasi untuk environment ini).
  - `TERMUX_INSTALL` map (`cli_presets.py:241-244`) HANYA berisi `aichat` + `codex` —
    TIDAK ada entry amp → di Termux pun tak ada rute install terverifikasi.
  - npm unscoped `amp` = library messaging tak terkait (tjholowaychuk/node-amp, v0.3.1,
    "Abstract messaging protocol"); `@ampcode/cli` (eks `@sourcegraph/amp`) memang ADA
    tapi optional deps-nya HANYA darwin/linux/win32 — TIDAK ada build android/termux,
    sehingga `npm install -g @ampcode/cli` tidak menarik biner `amp` yang berfungsi di sini;
    PyPI `AMP` = parser matematika (Ini Oguntola); Homebrew `amp` = text editor terminal
    (amp.rs / jmacdonald). Konklusi: TIDAK ada rute install resmi terverifikasi.
- Script source `_common.sh` (read-only: `detect_os`/`detect_pm`/`load_gateway_config`
  + `log_msg`) lalu log pesan + `exit 0`. Tidak ada `ensure_installed`/install command.
- Verifikasi: `bash -n scripts/cli-tools/amp.sh` → **clean**; mode `-rwx------` (exec);
  eksekusi langsung → `exit 0`, TIDAK memasang apa pun.

### `scripts/cli-tools/qwen.sh` (BARU) — **A10 qwen = OpenAI-compatible (verified)**
- Install + launch script untuk **qwen** (A10). Install idempoten via `ensure_installed` → `npm i -g @qwen-code/qwen-code` (fakta `cli_presets.py:79`).
- Launch **OpenAI-compatible** — qwen bicara Chat Completions ke aigate (`/v1/chat/completions`). Wiring: `OPENAI_API_BASE` + `OPENAI_API_KEY` (dari `load_gateway_config`) + generate `.qwen/settings.json` (`modelProviders.openai` `baseUrl` = gateway, `envKey` = `OPENAI_API_KEY`, `security.auth.selectedType` = `openai`), endpoint `/v1/chat/completions`.
- Fakta kunci (cross-check): qwen = `LAUNCH_VERIFIED` (`cli_presets.py:181`); builder `_qwen_builder` (`cli_tools_router.py:526-567`). npm `@qwen-code/qwen-code` v0.23.1 pure-JS butuh Node >=22.
- Verifikasi: `bash -n scripts/cli-tools/qwen.sh` → clean; mode `-rwx------` (exec); commit `73478a0`.

### `scripts/cli-tools/cline.sh` (BARU) — **A11 cline = OpenAI-compatible (verified)**
- Install + launch script untuk **cline** (A11). Install idempoten via `ensure_installed` → `npm i -g cline` (fakta `cli_presets.py:80`).
- Launch **OpenAI-compatible** — cline bicara Chat Completions ke aigate (`/v1/chat/completions`). Wiring: flags `cline auth --provider openai-native --apikey <key> --modelid <model> --baseurl <base>` (builder `_cline_builder` di `cli_tools_router.py:732-764`) + env `OPENAI_API_BASE` + `OPENAI_API_KEY` (dari `load_gateway_config`).
- Fakta kunci (cross-check): cline = `LAUNCH_VERIFIED` (`cli_presets.py:182`); builder `_cline_builder` (`cli_tools_router.py:732-764`).
- Known-broken (bukan blocker): npm `cline@3.0.61` TIDAK punya variant binary `android` → terpasang tapi gagal jalan di Termux/aarch64 (sama pola claude/codex/kilo/amp). Script tetap memasang; tool bisa jadi tidak bisa dijalankan di perangkat ini.
- Verifikasi: `bash -n scripts/cli-tools/cline.sh` → clean; mode `-rwx------` (exec); commit `d931921`.

### `scripts/cli-tools/kilo.sh` (BARU) — **A12 kilo = OpenAI-compatible (verified)**
- Install + launch script untuk **kilo** (A12). Install idempoten via `ensure_installed` → `npm install -g @kilocode/cli` (fakta `cli_presets.py:81` = `_npm("@kilocode/cli")`, bin `kilo`).
- Launch **OpenAI-compatible** — kilo bicara Chat Completions ke aigate (`/v1/chat/completions`). Wiring TEPAT mirip `_kilo_builder` (`cli_tools_router.py:616-729`): tulis trusted, additive config `KILO_CONFIG`=`.kilo/aigate-kilo.json` (provider `"aigate"` via `npm: "@ai-sdk/openai-compatible"`, `options.baseURL`=gateway, `options.apiKey`=`{env:OPENAI_API_KEY}` — secret TIDAK ditulis ke disk, di-resolve dari env karena KILO_CONFIG = trusted location) + env `OPENAI_API_BASE`+`OPENAI_API_KEY` (dari `load_gateway_config`); bila `AIGATE_MODEL` disetel → config `model` key = `aigate/<model>` DAN flag `-m aigate/<model>` (priority tertinggi kilo: 1 flag, 2 config key, 3 last used, 4 first available).
- Fakta kunci (cross-check, R47/R48): kilo = `LAUNCH_VERIFIED` (`cli_presets.py:183`); builder `_kilo_builder` (`cli_tools_router.py:616-729`, terutama `:653` `_KILO_CONFIG_PATH`, `:654` `_KILO_CONFIG_ENV`, `:704-708` baseURL+apiKey, `:720-724` `-m` flag); catatan Termux no-android di `:687-689`. npm `@kilocode/cli@7.5.16`: bin `kilo`, `os:["darwin","linux","win32"]` (TIDAK ada `"android"`) → no Termux binary.
- Known-broken (bukan blocker): npm `@kilocode/cli` TIDAK punya variant binary `android` → gagal di Termux/aarch64 (sama pola claude/codex/cline/amp; builder mencatat di `cli_tools_router.py:687-689`). Script tetap memasang; tool bisa jadi tidak bisa dijalankan di perangkat ini.
- Verifikasi: `bash -n scripts/cli-tools/kilo.sh` → clean; mode `-rwx------` (exec); commit `2a194cc`.

### `scripts/cli-tools/openhands.sh` (BARU) — **B1 openhands = OpenAI-compatible (verified)**
- Install + launch script untuk **openhands** (B1). Install: pilih `uv` dulu (`uv tool install openhands`, butuh Python 3.12), fallback `ensure_installed` → `pip install openhands` (fakta `cli_presets.py:88` = `_pip("openhands")` → `pip install openhands`). Idempoten via `command -v`.
- Launch **OpenAI-compatible** — openhands bicara Chat Completions ke aigate (`/v1/chat/completions`). Wiring: env `LLM_BASE_URL` + `LLM_API_KEY` (dari `load_gateway_config`) + `LLM_MODEL=openai/<model>` ke aigate `/v1/chat/completions`, flag `--override-with-envs`.
- Fakta kunci (cross-check): openhands = `LAUNCH_VERIFIED` (`cli_presets.py:190`); builder `_openhands_builder` (`cli_tools_router.py:960-972`). PyPI `openhands` v1.16.0 pure-python tapi butuh **Python 3.12** (`requires_python` gagal resolve di 3.13+ → `uv`/`pip` gagal bila `python3` = 3.13+; butuh venv/pyenv 3.12). Script pilih `uv` dulu, fallback `pip`.
- Verifikasi: `bash -n scripts/cli-tools/openhands.sh` → clean; mode `-rwx------` (exec).

Status: A1 claude = done (script). A2 opencode = done (script). A3 gemini = done (script, native Google mode, unsupported by aigate). **A4 codex = done (script, native OpenAI mode, unsupported by aigate — butuh streaming Responses API yang belum ada).** **A5 antigravity = done (script, NO_INSTALL — message + exit 0, no side-effect).** **A6 phi = done (script, NO_INSTALL — message + exit 0, no side-effect).** **A7 aider = done (script, OpenAI-compatible via aigate `/v1/chat/completions`, verified — `LAUNCH_VERIFIED` at `cli_presets.py:172`).** **A8 goose = done (script, NO_INSTALL — message + exit 0, no side-effect).** **A9 amp = done (script, NO_INSTALL — message + exit 0, no side-effect).** **A10 qwen = done (script, OpenAI-compatible via aigate `/v1/chat/completions`, verified — `LAUNCH_VERIFIED` at `cli_presets.py:181`).** **A11 cline = done (script, OpenAI-compatible via aigate `/v1/chat/completions`, verified — `LAUNCH_VERIFIED` at `cli_presets.py:182`; install `npm i -g cline` + wiring `cline auth --provider openai-native --apikey --modelid --baseurl` + env `OPENAI_API_BASE`/`OPENAI_API_KEY`; npm `cline@3.0.61` gak punya variant android binary → known-broken di Termux, bukan blocker).** **A12 kilo = done (script, OpenAI-compatible via aigate `/v1/chat/completions`, verified — `LAUNCH_VERIFIED` at `cli_presets.py:183`; install `npm i -g @kilocode/cli` + wiring trusted config `KILO_CONFIG`=`.kilo/aigate-kilo.json` (provider `aigate` via `@ai-sdk/openai-compatible`, `apiKey`=`{env:OPENAI_API_KEY}` → secret TIDAK ke disk) + env `OPENAI_API_BASE`/`OPENAI_API_KEY` + flag `-m aigate/<model>`; npm `@kilocode/cli@7.5.16` gak punya variant android binary → known-broken di Termux, bukan blocker).** `_common.sh` = done. **B1 openhands = done (script, OpenAI-compatible via aigate `/v1/chat/completions`, verified — `LAUNCH_VERIFIED` at `cli_presets.py:190`; install uv→fallback pip `pip install openhands` + wiring `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL=openai/<model>` + flag `--override-with-envs`; PyPI `openhands` v1.16.0 butuh Python 3.12 → known-broken di 3.13+, bukan blocker).** Sisa B2..B6, C1..C6 menyusul per tool. **GRUP A SELESAI (12/12); B1 SELESAI (1/6).** (Progress: **13/24**.)


## 2026-09-08 — i18n: satu file per bahasa + 5 bahasa baru (ru, nl, ja, zh, zh-tw) — DONE (`f7beaf9` + `c1477eb`, branch `feat/i18n-locales`)

**Permintaan user:** "buatkan beberapa file bahasa berikut: Rusia, Belanda, Jepang, Cina"
→ pilih **opsi B (pecah per file)** + "kedua bahasa cina aja" (Simplified **dan** Traditional)
→ "biar gak kecampur bikin branch baru aja".

### `src/frontend/static/i18n.js` (793 → 150 baris, 34,7 KB → 6,6 KB)
- Tidak lagi berisi kamus. Jadi **registry 7 locale + loader + helper**
  (`applyLocale` / `setLocale` / `translate` / `hasLocale` / `ensureLocale`),
  `FALLBACK_LOCALE = "en"`.
- `window.LANGS`: en 🇺🇸, id 🇮🇩, ru 🇷🇺, nl 🇳🇱, ja 🇯🇵, zh 🇨🇳, zh-tw 🇹🇼.

### `src/frontend/static/i18n/` (BARU — satu file per bahasa, self-register)
- `en.js`, `id.js` = **pindah murni**: 379 kunci, nilai & urutan identik dengan sebelumnya
  (0 perubahan teks), hanya +5 kunci `lang.{ru,nl,ja,zh,zh-tw}`.
- `ru.js` (24,5 KB), `nl.js` (18,1 KB), `ja.js` (22,0 KB), `zh.js` (17,6 KB),
  `zh-tw.js` (18,0 KB) — masing-masing **379 kunci sama persis** dengan `en.js`
  (checker: hilang 0 / thừa 0 / kosong 0).
- Aturan terjemahan yang dipakai: placeholder `{n}` `{cli}` `%s` utuh; nama produk
  (`aigate`, `aigate Repo`), akronim (CLI/API/JSON/OAuth/PTY/TUI/HTTP/CSV), path
  (`/v1/chat/completions`), dan nama provider/model TIDAK diterjemahkan; `lang.<code>`
  = endonim (Русский, Nederlands, 日本語, 简体中文, 繁體中文).
- `zh` vs `zh-tw` ditulis sebagai dua varian berbeda (gaya Taiwan: 儲存/伺服器/資料/匯入),
  bukan konversi mesin.

### `src/frontend/static/index.html`
- Preloader inline di `<head>`: baca `localStorage["aigate.locale"]` (kunci yang SUDAH
  dipakai app.js) lalu `document.write` tag `<script src="i18n/<loc>.js?v=20260914">`
  **sebelum** `i18n.js`/`app.js` → hanya EN + bahasa aktif yang ter-load (opsi i).
  Kode non-locale (`../etc/passwd`, `</script><script>`, huruf besar, dsb) ditolak regex.
- Cache-buster `i18n.js` + `app.js` → `?v=20260914`.

### `src/frontend/static/app.js`
- `getStr()` delegasi ke `window.translate` (satu implementasi fallback, tidak dua sumber).
- `switchLocale()` + `populateLocaleOptions()`: dropdown bahasa di Settings dibangun dari
  `window.LANGS` (tambah bahasa baru tidak perlu sentuh app.js lagi).

### Tes
- `tests/i18n.test.js`: parity guard jadi **glob** (`static/i18n/*.js` wajib punya kunci sama
  persis dengan `en`) + tes registry, fallback saat kamus belum ada, dan perilaku preloader
  (4 → 30 tes). `tests/helpers/i18n-dicts.js` (baru) + `vitest.config.js setupFiles` supaya
  jsdom ikut memuat kamus. `tests/settings.test.js` +4 (opsi locale registry-driven),
  `tests/row-actions.test.js` pin `["en","id"]` → 7 kode.
- **Tidak ada tes yang dihapus/di-skip/dilonggarkan.**

### Verifikasi PM
- `node .opencode/tools/tests/i18n-parity-check.mjs ru nl ja zh zh-tw` → 5× `OK`, 379 kunci.
- Gate penuh sekali (R35): vitest **519 passed (23 file), Duration 10.60s**.
- Backend TIDAK diubah: `Setting locale` disimpan apa adanya
  (`settings_router.put_settings` → `set_setting(key, str(value))`, tanpa allowlist) →
  `ru/nl/ja/zh/zh-tw` lolos simpan. Static: `StaticFiles(directory=…/static, html=True)`
  sudah menyajikan subdirektori → `i18n/*.js` terhidrasi tanpa perubahan server.

### Item lanjutan (belum dikerjakan)
- 7 salinan `getStr` lokal di `combos/selfheal/clitools/analytics/endpoints/proxies/combobox`
  masih null-safe sendiri → kandidat tugas DRY tersendiri.
- Auto-detect bahasa browser: tidak diminta (YAGNI).
- Terjemahan dihasilkan agen — **belum ditinjau penutur asli**; label yang perlu dicek:
  `nav.group.operations` (zh `运维` vs zh-tw `維運`), `ja selfheal.title` (Latin `Self-Heal`
  vs katakana `セルフヒール`), `ja common.remove` vs `common.delete` (sama-sama `削除`).

## 2026-09-07 — Suite tes frontend: fixture DOM bersama + poller di-stop + maxForks 2 — DONE (commit `618f7d7`)

**Permintaan user:** "apa sih yang bikin lama? terutama pas jalanin vitest" → lalu
"ya udah, lu kerjain deh".

### Ukur dulu (R35/R37)
Sebelum: `484 passed (23 file), Duration 14.66s` dengan `collect 24.07s · tests 23.82s ·
environment 28.63s · transform 4.05s · prepare 6.06s` (kumulatif antar-worker).
Akar: (a) 9 file tes masang `readFileSync(index.html 63 KB)` + `new JSDOM(html)`
masing-masing; (b) 17 file meng-import `app.js`/`terminal.js` yang `init()` jalan saat
import; (c) Termux melapor `os.cpus().length === 0` → vitest fallback ke
`availableParallelism()` = **8 fork** di HP yang lagi di-throttle.

### Perubahan (semua di `src/frontend/**`, TIDAK menyentuh kode produksi)
- `tests/helpers/dom.js` (baru): baca + parse `index.html` **sekali per worker**;
  file read-only pakai hasil parse bersama, file yang mutasi DOM dapat salinan sendiri.
  NOTE di file: eksperimen `mountBody()` pakai `<template>`+`cloneNode` **5x lebih lambat**
  (1146ms vs 214ms) — clone pohon ~1.5k node lebih mahal dari HTML parser-nya.
- `tests/helpers/quiet.js` (baru, dipasang sebagai `setupFiles`): `afterEach` memanggil
  `stopLogAutoRefresh()` + `stopUsageAutoRefresh()`. Ini **beban kebenaran**, bukan hiasan:
  dengan `isolate:false` poller 3 detik itu hidup lintas file dalam worker yang sama dan
  menyenggol fetch-spy tes sebelah → flake `expected 1 to be +0` +
  `ReferenceError: fetch is not defined` begitu fork dinaikkan. Setelah: 3 run penuh hijau.
- `vitest.config.js`: `pool:"forks"`, `maxForks:2`, `minForks:1` (isolate:false tetap).
  Kurva terukur di box ini: 1 fork 12.6s · **2 fork 8.3s** · 4 fork 10.4s · 8 fork 12.2s.
  Komentar lama "os.cpus()=0 keeps it sequential" dikoreksi — ternyata TIDAK sekuensial.
- 11 file tes dimigrasi ke helper. Tidak ada tes yang dihapus / di-skip / dilonggarkan;
  `vi.resetModules()` di `terminal_exit`/`terminal_discard` TETAP (dibuktikan via run:
  tiap tes discard memang mensimulasikan reload halaman).
- Dibuang: `tests_orig/` + `vitest.orig.config.js` (artefak throwaway sesi sebelumnya;
  isinya salinan HEAD dan config-nya sendiri menulis "Delete after use").

### Angka sesudah
`collect 24.07s → 6.82s`, `environment 28.63s → 5.61s`, `tests 23.82s → 9.71s`,
`transform 4.05s → 1.86s`. Wall: **12.23s → 8.27s** saat box tidak di-throttle;
gate PM barusan **13.86s** saat box di-throttle (484 passed / 23 file).

### Catatan untuk nanti (bukan bug)
- `maxForks: 2` = tuning per-box. Pindah ke host multi-core sungguhan → naikkan.
- Guard `if (typeof fetch === "function")` di `app.js:1792` mengasumsikan lingkungan tes
  headless tanpa `fetch`, padahal Node modern selalu punya global itu → poller selalu nyala
  di tes. Kandidat penguatan kalau nanti mau dirapikan (keputusan PM/user, belum dikerjakan).

## 2026-09-07 — Sidebar: tautan Repository nempel di bawah — DONE (commit `86a5ef1`)

**Permintaan user:** "di sidemenu tambahin link repo aigate dong
(https://github.com/fadhly-permata/AI-Gate) buat posisinya sticky di bawah aja ya."

### `src/frontend/static/index.html`
- `<div class="sidebar-footer">` = anak terakhir `<aside class="sidebar">`, **di luar
  `<nav>`** → `.nav-section:last-child { border-bottom: 0 }` tetap berarti sama.
- Isinya `<a class="nav-item" target="_blank" rel="noopener noreferrer">` + ikon
  `fa-brands fa-github` + `<span class="nav-label" data-i18n="nav.repo">`;
  `aria-label`/`title` + `data-i18n-aria` supaya tetap terbaca saat sidebar di-collapse.
- Cache-buster dinaikkan ke `?v=20260912` untuk `styles.css`, `app.js`, `i18n.js`.

### `src/frontend/static/app.js` (4 baris)
- Handler klik navigasi sekarang `if (!item.hasAttribute("data-view")) return;` —
  tanpa itu tautan repo ikut di-`preventDefault()` dan gak ke mana-mana.

### `src/frontend/static/styles.css`
- `.sidebar` jadi `display:flex; flex-direction:column` (sebelumnya block) supaya
  footer bisa didorong ke bawah; `.nav` tidak diubah (min-height otomatis = tinggi
  konten → menu panjang overflow, `.sidebar` yang scroll).
- `.sidebar-footer`: `position:sticky; bottom:0` + `margin-top:auto` + `flex:0 0 auto`
  + `background:var(--sidebar-bg)` + `z-index:1` → dua mekanisme saling melengkapi
  (menu pendek → nempel bawah; menu panjang/scroll → tetap terlihat, item terakhir
  tetap terjangkau di akhir scroll). `body.sidebar-collapsed .sidebar-footer{padding:4px 0}`.
  Tanpa hex baru (token saja). Mobile tidak disentuh (`.sidebar` tetap `display:none`,
  `.bottom-nav` tetap 7 item).

### `src/frontend/static/i18n.js`
- `nav.repo`: EN `"Repository"`, ID `"Repositori"` (satu kunci = satu nilai, sesuai
  keputusan i18n 2026-09-06).

### `src/frontend/tests/views.test.js` (+115 baris, 8 tes)
- href persis + `target=_blank` + `rel` noopener/noreferrer; TIDAK punya `data-view`
  + guard binding `app.js` (regression lock); posisi wrapper (last child `.sidebar`,
  di luar `<nav>`, 4 `.nav-section` utuh); markup ulang pola nav (ikon + label +
  aria/title); mode collapsed (label tetap di DOM, disembunyikan CSS); kontrak CSS
  sticky ( assertion teks rule — jsdom tidak menjalankan layout); ponsel tidak berubah.

**Verifikasi PM:** `node node_modules/.bin/vitest run` → **484 passed (23 file),
Duration 14.66s**. Backend tidak disentuh (tanpa perubahan `src/backend/**`).

**KOREKSI label (user 2026-09-07, commit menyusul):** teks ditanya user =
`"aigate Repo"` (sebelumnya EN "Repository" / ID "Repositori"). Diubah di
`i18n.js` (EN + ID jadi sama — nama produk, bukan string bilingual campur),
`index.html` (label + `aria-label` + `title`), dan `views.test.js` (3 assertion).
Cache-buster `i18n.js` → `?v=20260913`. Tes tertarget: views + i18n = **25 passed**.

## 2026-09-07 — Log cleanup: hapus / retensi / tanda "selesai" (BE T1 + FE T2) — DONE (commit `86c4778` + `45206c0`)

**Permintaan user:** fitur bersihin log — 3 opsi: hapus manual, auto-hapus per umur,
dan tandai selesai supaya tidak terus nongol di daftar self-heal.

### Backend (`src/backend/config/logs_router.py`, `models.py`, `config/db.py`, `config/settings.py`, `server.py`)
- `DELETE /api/logs?severity=&before=` — filter severity sama persis dengan GET
  (ilike substring OR). Wipe-all TANPA filter wajib `confirm=all`; tanpa itu NO-OP
  `200 {"deleted":0,"error":"confirmation required"}` (DEVIASI dari handover yang
  minta HTTP 400 — dipilih 200+error supaya FE cuma punya satu bentuk respons).
  `before` non-ISO → `400 invalid 'before'` (destructive op: tidak pernah diam-diam
  memperlebar rentang hapus). Audit trail ditulis SETELAH commit
  (`log_event severity=info source=backend.config.logs_router`, "logs purged: deleted=N scope=…").
- Retensi: `Setting log_retention_days` (default `"7"`), `purge_expired_logs()`
  dipanggil di `server.py` lifespan setelah `ensure_seeded()`, dibungkus try/except
  (startup gak pernah crash), nilai invalid/<=0 → fallback 7 + `log_warning`.
- Kolom baru `LogEntry.resolved` (Boolean, NOT NULL, default False) + migrasi
  aditif berpola sama (`_ensure_log_entry_resolved_column`: PRAGMA table_info →
  guarded `ALTER TABLE`). GET `/api/logs` menyembunyikan baris resolved kecuali
  `show_resolved=true` (PERUBAHAN default yang disengaja: feed self-heal jadi
  hanya berisi baris yang masih bisa ditindaklanjuti).
- `POST /api/logs/{id}/resolve` dan bulk `POST /api/logs/resolve {"ids":[…]}` →
  `{"resolved":N}`; id tak dikenal → `{"resolved":0}` (DEVIASI dari handover:
  404 → bentuk idempoten, supaya FE tidak perlu dua cabang error).
- Integrasi self-heal: `current_issue()` + `_count_remaining()`
  (`src/backend/selfheal.py`) dapat `.filter(LogEntry.resolved == False)` → baris
  yang sudah ditandai selesai tidak lagi memblokir jalur "semua selesai → merge".
  Delete-on-success self-heal TIDAK diubah.
- Tests: `tests/backend/test_logs_router.py` (baru, 300 baris: delete berfilter,
  wipe-all+confirm, tanpa confirm, cutoff `before`, `before` invalid, resolve
  tunggal/bulk, GET default vs `show_resolved`, retensi + fallback Setting) +
  `tests/backend/test_db_migration.py` (+94: migrasi kolom `resolved` di DB lama,
  baris lama utuh + terbaca falsy) + `tests/backend/test_selfheal.py` (filter resolved).

### Frontend (`src/frontend/static/app.js`, `index.html`, `styles.css`, `i18n.js`)
- Tombol **Clear logs** + modal konfirmasi berisi pemilih lingkup
  (`warning,error` | `all`); `buildClearLogsQuery(severity)` diekspor ke
  `window.aigate` (wipe-all → `?confirm=all`, selain itu `?severity=<value>`).
- Tombol **Show resolved** (toggle `aria-pressed`, persist
  `localStorage aigate.logShowResolved`) → menambah `show_resolved=true` ke query GET.
- Baris resolved dirender redup (`.log-row-resolved td{opacity:.55}`) + badge
  `.log-resolved-badge`; tombol resolve per-baris (`.log-resolve-btn`, fa-check)
  HANYA untuk baris warning|error yang belum resolved; delegasi klik di
  `#logTableBody` (baris sering di-render ulang). Tombol **Resolve all (filtered)**
  mengirim id baris unresolved yang sedang tampil.
- i18n EN/ID lengkap untuk semua key baru (parity guard lolos).
- Cache-buster (PM-owned): `styles.css`, `app.js`, `combobox.js`, `i18n.js` →
  `?v=20260911`; `selfheal.js` `20260910` → `20260911`. Alasan: preseden
  terminal.js — kode yang benar tidak pernah ter-load karena browser pakai salinan lama.
- Tests: `src/frontend/tests/logwindow.test.js` +328 baris (query builder,
  render resolved + badge, tombol per-baris, alur clear dengan confirm mock,
  toggle show_resolved, resolve-all).

**Verifikasi PM:** backend **478 passed / 1 skipped**; frontend **476 passed (23 file)**.

## 2026-09-07 — Self-Heal: pemilih CLI/model + combobox grouped + gerbang false-done — DONE (commit `74fcb9e`)

**Permintaan user:** (a) bisa pilih agentic CLI + model buat self-heal dan lihat prosesnya;
(b) daftar model harus dikelompokkan per provider + Kombo; (c) dropdown harus bisa
diketik seperti dialog CLI Tools; (d) bug: heal bilang "issue done" padahal tidak ada
yang diproses (issue-64).

### Backend (`src/backend/selfheal.py`, `selfheal_router.py`)
- `build_heal_command()` untuk opencode diubah dari TUI
  `opencode --model hy3 --prompt "…"` → **`opencode run [-m <provider/model>] "$(cat file)"`**
  (`opencode run` tidak punya `--prompt`; pesan = argumen posisional).
- Gerbang marker: `&& { touch .done; echo …; } || touch .failed`;
  `wait_for_done(..., failedfile=)` return **False seketika** saat `.failed` muncul
  (sebelumnya `;` → `touch .done` jalan walau CLI exit non-zero = "done" palsu).
- `qualify_opencode_model()` baru: id mentah di-resolve lewat `opencode models`
  (unique → dipakai; ambigu → prefer provider `aigate/`; tidak ketemu → flag OMIT +
  warning; gagal total → fail-open). Setting lama `self_heal_model='hy3'` kini
  otomatis jadi `aigate/hy3`.
- `CLI_MODEL_FLAGS`: entri `opencode` dihapus (special-case `run`); entri lain tetap
  (status **unverified** — item terbuka, sengaja tidak dikerjakan user 2026-09-07).
- `list_self_heal_models()` → list dict `{value,label,group}` (grup = nama provider;
  anggota kombo = sentinel `__combos__`), dedup by `(value,group)`;
  `GET /api/self-heal/models` mengembalikan dict.
- Tests: `tests/backend/test_selfheal.py` +546 baris (bentuk command, gerbang exit
  code, kualifikasi model 4 kasus, filter resolved, list models bergrupa).

### Frontend (`src/frontend/static/selfheal.js`, `combobox.js`, `index.html`, `i18n.js`)
- `selfHealCli` / `selfHealModel` dari `<select>` native → `window.aigate.createCombobox`
  (CLI: `searchInside`, tanpa grup; model: `groupBy:"group"`, `subGroupBy:"prefix"`,
  `startExpanded`, grup Kombo di-pin ke atas via `setGroupOrder`).
- `combobox.js`: render opsi tanpa-grup + opsi `startExpanded`; sentinel `__combos__`
  dipetakan ke label terlokalisasi ("Kombo"/"Combos").
- Panel **live preview**: poll progress 2.5s + aliran log dari `/api/logs`
  (filter source `backend.selfheal`); i18n +22 key EN/ID.
- Tests: `src/frontend/tests/selfheal.test.js` +179, `tests/frontend/selfheal.test.js`
  +160 (mirror), i18n parity.

**Verifikasi PM:** backend 478 passed/1 skip; frontend 476 passed; dry-run shim live
exit 0/1 membuktikan `.done` tidak muncul saat CLI gagal.

## 2026-09-07 — Konfigurasi tes frontend: suite ~2x lebih cepat — DONE (commit `5c2459f`)

**Permintaan user:** "kenapa kalau testing sering lama — ada yang salah di konfigurasi,
kode, atau aturan?"

### Ukur dulu (bukan tebakan)
- `src/frontend/vitest.config.js` sebelumnya 4 baris: hanya `environment:"jsdom"`,
  `globals`, `include`. Efek: 23 file tes masing-masing membangun ulang jsdom →
  `environment 84.94s` kumulatif vs `tests 25.10s` (wall 32-34s, CPU 2m25s).
- `--no-isolate` → wall 15.5s, `environment 25.42s` **tapi 1 tes gagal**:
  `tests/terminal_exit.test.js > DoD 4 > shows #termEmpty…`.

### Akar masalah (murni di sisi tes, BUKAN bug aplikasi)
`terminal.js` meng-cache referensi DOM di closure saat `init()`
(`emptyEl = document.getElementById("termEmpty")`). Dengan registry modul yang dibagi
antar-file, `await import("../static/terminal.js")` = **cache HIT** → `init()` tidak
jalan ulang → `emptyEl` masih menunjuk node `#termEmpty` milik file tes sebelumnya
yang sudah jadi detached. `terminal.js` sendiri benar di runtime asli (init sekali
per page-load), jadi kode produksi TIDAK diubah.

### Perubahan
- `src/frontend/tests/terminal_exit.test.js`: `vi.resetModules()` sebelum re-import
  (paksa cache MISS → `init()` jalan terhadap DOM milik file ini) + komentar.
  Tidak ada tes yang dihapus/di-skip/dilonggarkan.
- `src/frontend/vitest.config.js`: `test.isolate:false` + komentar alasan, angka
  terukur, dan catatan "naikkan isolate lagi kalau ada tes yang butuh state segar".
  `environment`/`globals`/`include` tidak diubah.
- Ditolak: `poolOptions.threads.isolate` (pool aktif vitest 2.1.9 = forks → tidak
  ngefek), menaikkan fork/`fileParallelism` (`os.cpus()=0` di Termux; memaksa fork di
  HP ter-throttle = angka ngaco + membuka kontaminasi silang antar file), reset
  per-test di `beforeEach` (over-engineering).

**Verifikasi PM:** `node node_modules/.bin/vitest run` → **476 passed (23 file),
Duration 23.33s** (bandingkan 32-34s sebelumnya di box yang sama; di box tidak
ter-throttle ≈ 15s).

## 2026-09-07 — Provider test: probe host tak terjangkau jadi WARNING (tanpa traceback) — DONE (commit `f0c4e14`)
`src/backend/providers_router.py` `_run_provider_test`: cabang timeout & transport
turun dari `logger.error(..., exc_info=True)` → `logger.warning(...)` dan
`log_error_exc` → `log_warning_exc` (hasil probe yang diharapkan gagal koneksi bukan
server fault; traceback 5 frame httpx/httpcore selama ini menutupi log). Cabang
unexpected-error TETAP `error + exc_info`. Bentuk envelope return tidak diubah.
`pytest tests/backend/test_providers.py` = 16 passed.

## 2026-09-07 — Self-Heal progress terlihat: CLI jalan di tab terminal + run async — DONE (commit `68cc1bd`)


**Root cause:** `POST /api/self-heal/run` dulu SINKRON dan agentic CLI dijalankan via
`subprocess.run([cli, "--prompt", prompt])` — output tak pernah terlihat user; UI cuma
"Running…" lalu diam. Request user (2026-09-07): "untuk self heal progress gak jelas.
jadi buka aja terminal baru (dan fokus) agar progress self heal keliatan".

### Backend (`src/backend/selfheal.py`, `src/backend/selfheal_router.py`)
- CLI TIDAK lagi di-spawn sebagai subprocess tersembunyi. Orkestrasi jalan di
  sesi PTY terminal key **`self-heal`** (shell biasa via `get_or_create`; respawn
  bila mati; tak pernah kill sesi hidup milik user). Per issue: prompt (dari
  `LogEntry`) ditulis ke file temp `aigate-heal-<uuid>/issue-<id>.prompt`, lalu
  backend mengetik SATU baris ke PTY:
  `<cli> --prompt "$(cat '<promptfile>')"; touch '<donefile>'; echo "aigate: issue done"`
  — tanpa konten log di command line (anti shell-injection). Selesai terdeteksi via
  poll file `.done` (interval 2s, timeout per issue `HEAL_CLI_TIMEOUT_SECONDS=1800`
  → lanjut ke test; test yang memutuskan hapus LogEntry). Bila tab/shell mati di
  tengah jalan → run dihentikan, status `{"ok":true,"merged":false,"remaining":N}`.
  File temp dibersihkan di `finally`.
- Run jadi ASYNC: `start_self_heal()` (daemon thread + guard sudah-jalan),
  `POST /api/self-heal/run` → `200 {"ok":true,"started":true,"tab":"self-heal"}`,
  `409 {"ok":false,"reason":"already_running","tab":"self-heal"}` bila masih jalan;
  `run_self_heal()` tetap sync (kontrak & bentuk status lama utuh) sebagai thread
  target. Endpoint baru `GET /api/self-heal/status` → `{"running": bool, "last":
  <hasil|null>}`. TerminalTab row (title "Self-Heal") dibuat saat sesi pertama
  spawn (soft-fail → 0). Log R12 semua transisi (source `backend.selfheal.*`).
- Tests: `tests/backend/test_selfheal.py` +12 (command shape + anti-injection +
  cleanup, timeout, abort-on-death, start/status/409/500 lifecycle, DB tab row,
  registry reuse/drop). **Backend: 438 passed, 1 skipped.**

### Frontend (`src/frontend/static/selfheal.js`, `terminal.js`, `i18n.js`)
- `runSelfHeal()` async: 200 → pesan `selfheal.started` + buka & fokus tab
  `openTab("self-heal")` + pindah view terminal (pola precedent clitools launch);
  409 → pesan `selfheal.already_running` + tetap buka tab; keduanya mulai polling
  `GET /api/self-heal/status` (langsung sekali lalu tiap 5s, single-handle, berhenti
  saat `last` non-null + `running=false` → render `renderSelfHealStatus`, re-enable
  Run kecuali kind "ok"). Poll gagal → pesan sekali, polling lanjut.
- `terminal.js::tabTitle` → key `self-heal` berjudul tetap "Self-Heal"
  (`t("selfheal.title")`). i18n +2 key × 2 locale (en/id): `selfheal.started`,
  `selfheal.already_running` (parity-guard lolos).
- Tests: `src/frontend/tests/selfheal.test.js` + mirror `tests/frontend/selfheal.test.js`
  +8. **Frontend: 453 passed (23 files).**

### PM-owned
- `src/frontend/static/index.html`: cache-buster `selfheal.js?v=20260907`,
  `terminal.js?v=20260907`, `i18n.js?v=20260907` (pola precedent analytics/terminal).

### Docs sinkron
- FSD §2.8 (output + process flow Self-Heal: async run, tab `self-heal`, temp-file
  prompt, donefile poll, status endpoint), TSD §3.5 (Self-Heal: PTY key, async run,
  status), BRD US-2.8.5 (acceptance (3) tab dibuka+fokus live, (3b) async+polling).

### Catatan operasional
- BUTuh restart aigate + hard-refresh browser (cache-buster baru) agar berlaku (R32:
  user yang restart, bukan agent).


## 2026-09-07 — Request Log: kolom Model/Endpoint kosong (combo path + endpoint_name) — DONE

**Root cause (BE):** untuk model ref `combo:<name>`, resolver balikin marker
`ResolvedTarget(upstream_model="", combo_used=True)` (member asli diputuskan di
dalam `execute_combo`). `gateway/router.py` nimpa `ctx["model"] = target.upstream_model`
UNCONDITIONAL → `RequestLog.model = ''` untuk semua request combo. Kolom Endpoint
kosong = by-design (request model-based tanpa header `X-Aigate-Endpoint` →
`endpoint_id` NULL) — bukan bug, tapi FE merender id mentah (null → sel kosong).
Bukti DB: baris 21:28–21:29 `model=''` padahal body `"model":"combo:B.AI"`.

**Perubahan (delegasi be-dev → fe-dev, mode sekuensial):**
- `src/backend/gateway/router.py` — helper `_upgrade_ctx_model(ctx, upstream_model)`:
  upgrade `ctx["model"]` hanya bila value non-empty (tidak pernah terdegradasi jadi
  `''`; error path & fallback tetap bawa model ref). Dipakai di 6 situs:
  chat non-stream combo (upgrade dari envelope upstream `result.get("model")`,
  fallback combo ref), chat streaming combo (`member.upstream_model` dari
  `resolve_combo_stream_target`), responses path (identik chat),
  `_route_via_endpoint` provider binding + combo binding (stream & non-stream).
- `src/backend/analytics_router.py` — `RequestLogDTO` + field
  `endpoint_name: Optional[str]` (Pydantic v1); `_row_to_dto` populate dari
  `row.endpoint.name` di dalam session aktif; docstring kontrak module di-update.
- `src/frontend/static/analytics.js` — `orDash(v)` (null/undefined/"" → "—") +
  `reqlogEndpoint(r)` (`endpoint_name || endpoint_id || "—"`); kolom Model &
  Endpoint memakai fallback, semua value tetap di-`escapeHtml`.
- `src/frontend/static/index.html` — cache-buster `analytics.js?v=20260906`
  (pola sama dgn `terminal.js` — cegah stale copy post-update).
- Tests: `tests/backend/test_request_log.py` (+5: combo non-stream model terisi,
  envelope tanpa model → fallback combo ref, combo stream, endpoint_name di API,
  endpoint_name null utk model-based), `tests/backend/test_analytics.py` (DTO
  shape), `src/frontend/tests/analytics.test.js` (fixture DTO baru +3 test nama/
  fallback/dash + XSS escape; wiring test tahan `?v=` cache-buster).

**Verifikasi PM (re-run):** backend `pytest tests/backend` = **423 passed,
1 skipped** (skip = native PTY); frontend vitest = **445 passed (23 files)**.
Catatan: baris LAMA di DB (`model=''`) tidak di-backfill — hanya entri baru yang
benar; user perlu restart aigate agar kode BE aktif (R32 — user yang restart).

## 2026-09-07 — Terminal tab auto-close on shell exit + session-ended toast — DONE

Akar masalah "tab gak nutup": backend tidak pernah memberi tahu frontend saat shell
mati → tab jadi zombie view. (Plus: `terminal.js` ter-cache browser tanpa cache-buster,
sehingga perbaikan FE tidak ter-load.) BE terbukti benar via runtime (frame terkirim).

**Kontrak exit (sumber kebenaran):** server kirim TEXT frame `{"type":"exit","code":<int>}`
ke view yang sedang attached, LALU tutup WS (code 1000). Frame TIDAK masuk ring-buffer
replay. FE tangkap frame → tutup tab (tanpa kill-frame balasan, tanpa auto-open).

### `src/backend/terminal/pty.py`
- `PtyProcess` +properti `exit_status` (best-effort baca exit status child; guard).

### `src/backend/terminal/session.py`
- Sentinel `PtyExit(code)` (bukan output terminal) + `notify_exit()` (dorong SATU
  sentinel ke queue view aktif, at-most-once per view via `exit_view`), `resolved_exit_code()`
  / `read_exit_code()`, `close_view()`. Reader thread memanggil `notify_exit()` saat PTY
  mati. `try_reap`/`reap_idle` kini REAP sesi exited walau masih attached (tutup view);
  sesi hidup yang cuma detached tetap tidak disentuh (regression guard).

### `src/backend/terminal/router.py`
- `_pump()` kenali item `PtyExit` → kirim `exit_frame(code)` = `json.dumps({"type":"exit","code":int(code)})`
  lalu `websocket.close(1000)`. Handler reclaim sesi setelah exit.

### `tests/backend/test_terminal_exit.py` (baru)
- 17 test: exit → satu frame `{"type":"exit","code":N}` + close 1000; frame tidak
  ke-replay; reaper reap exited-but-attached; live-but-detached tetap aman.

### `src/frontend/static/terminal.js`
- `handleWsMessage`: guard `tab.userClosed`; cabang `info.type==="exit"` →
  `closeTab(tab.id,{exited:true})`. `closeTab(id,opts)`: `opts.exited` = TANPA kirim
  kill-frame + TANPA auto-open tab baru (empty state); `removeSavedTabId` dipanggil.

### `src/frontend/static/i18n.js`
- Key `term.session_ended` (EN + ID) untuk toast penanda sesi selesai.

### `src/frontend/static/styles.css`
- Gaya toast `term.session_ended`.

### `src/frontend/static/index.html`
- Cache-buster `?v=20260906` pada aset statik (terminal.js dkk) supaya versi baru
  selalu ter-load (akar bug: cache lama tanpa bust).

### `src/frontend/tests/terminal_exit.test.js` (baru)
- 14 test: exit frame → tab hilang, tanpa kill-frame, tanpa auto-open, forget id.

**Verification.** PM re-ran: backend terminal **65 passed / 1 skipped** (skip =
`test_terminal.py:59` native PTY dep); frontend **442 passed (24 files)**, no regresi.
Kontrak BE↔FE dicocokkan di kode nyata (frame dulu → close 1000). Belum di-exercise
end-to-end live di browser.

---

## 2026-09-06 — CLI Tools combobox: two-level (provider → model-prefix) grouping — DONE

### `src/frontend/static/combobox.js`
- Added `subGroupBy` (`null|prefix|group`). Options carry `_sub`; `setOptions` derives it (prefix → `familyOf(label)` unless `subGroup:false`; group → `m.subGroup`). `subGroup:false` opt-out keeps an option flat.
- Two-level render: main group header → flat items (`_sub==null`) directly under it → sub-group headers with nested items. New `collapsedSub`/`trackedSub` Sets (composite `group\u0001sub`) for per-sub collapse (default collapsed, persists across refresh, auto-expand while searching). `toggleSub(group,sub)`; click/Enter/Space on `.aigate-combo-subgroup` toggles.

### `src/frontend/static/clitools.js`
- `cliModelCtl()` adds `subGroupBy:"prefix"`. `fetchModels()` sets combo items `subGroup:false` (flat under `Kombo/Combos`); provider items auto sub-group by model-name prefix. Values stay full `provider:/combo:` ids.

### `src/frontend/static/styles.css`
- Added `.aigate-combo-subgroup` (indented header + caret) and `.aigate-combo-opt.aigate-combo-opt-sub` (44px indent).

### `src/frontend/tests/combobox.test.js`
- Added 6 tests: default-collapsed two-level, `Kombo/Combos` flat, provider→prefix sub-groups, expand-sub reveals items, keyboard toggle, search auto-expands.

**Verification.** PM re-ran vitest: **415 passed (21 files)**. No backend changes.

---

## 2026-09-06 — Model dropdown: indent + collapsible groups + fixed flexible positioning — DONE

### `src/frontend/static/combobox.js`
- Group child options indented (render unchanged; CSS does indent).
- Collapsible groups: `collapsed` Set, default all collapsed; click/Enter/Space on a `role="button"` group header toggles (keeps state across `setOptions` refreshes via a `tracked` Set). While a search query is active, all groups auto-expand so matches show. Headers always render (even when collapsed) so they stay expandable. `renderOptionsHtml()` iterates the full group list; `buildRenderGroups()` removed.
- `position()` rewritten to `position: fixed`, viewport-anchored to the input rect; opens below when there is room, above otherwise; `maxHeight` capped to `min(320, availableSpace)` so it never overflows. Adds `scroll`(capture)+`resize` listeners on open, removed on close/destroy. Fixes the panel being clipped by `.modal { overflow-y:auto }`.

### `src/frontend/static/styles.css`
- `.aigate-combo-list` now `position: fixed` (geometry set inline by JS).
- `.aigate-combo-opt` indented `padding-left: 28px`; `.aigate-combo-group` `cursor:pointer`, caret via `::before` (▾ expanded / ▸ collapsed).

### `src/frontend/tests/combobox.test.js` / `combos.test.js`
- Added tests: collapsed-by-default, click/keyboard toggle, auto-expand on search, persist across refresh, fixed positioning (above/below/cap/scroll-reposition/detach). `combos.test.js` updated for collapsed-default.

**Verification.** PM re-ran vitest: **409 passed (21 files)**. No backend changes.

---

## 2026-09-06 — Model dropdown: in-panel search + grouping — DONE

### `src/frontend/static/combobox.js`
- Added `searchInside` (search `<input>` as the FIRST panel `<li>`; two-way mirrored with the top value input; focused + cleared on open; committed value restored on cancel).
- Added `groupBy` (`none|prefix|group`) + `groupOrder` (pinned order, rest alpha). Prefix uses `familyOf()` (`deepseek-v1`+`deepseekv2`→`Deepseek`; `gpt-4o`→`Gpt`). Group headers are `role="presentation"`, skipped by keyboard nav.
- No-match + custom: appends a synthetic "Use \"%s\" as custom model" option so free text survives (ADR-011).

### `src/frontend/static/combos.js`
- `#comboMemberModel` combobox now `searchInside:true, groupBy:"prefix"` (Kombo page groups by model prefix).

### `src/frontend/static/clitools.js`
- `#cliModel` converted from native `<select>` to the combobox (`searchInside:true, groupBy:"group", groupOrder:["Kombo/Combos"]`).
- `fetchModels()` maps `/v1/models`: `combo:` → group `Kombo/Combos`; provider → group `owned_by`; value stays the full `provider:/combo:` id so `launch()` posts it verbatim.

### `src/frontend/static/index.html`
- Replaced `<select id="cliModel">` with combobox markup (`cliModel` input + `cliModelList` ul).

### `src/frontend/static/styles.css`
- Added `.aigate-combo-searchrow` (sticky top search row), `.aigate-combo-search`, `.aigate-combo-group` (non-selectable header).

### `src/frontend/static/i18n.js`
- Added `combobox.use_custom` + `combobox.group_combos` (en + id).

### `src/frontend/tests/combobox.test.js`
- Added 6 tests (prefix grouping, group+groupOrder pin, in-panel search filter+mirror, search focus/clear on open, no-match custom click, custom via Enter).

**Verification.** PM re-ran vitest: **401 passed (21 files)**. No backend changes.

---

## 2026-09-06 — Terminal toolbar icon-only main buttons — DONE

### `src/frontend/static/index.html`
- Removed visible Paste, Settings, and Full text from main dropdown buttons; submenu labels remain.

### `src/frontend/static/styles.css`
- Sized and centered icon-only main split buttons.

### `src/frontend/tests/terminal_toolbar.test.js`
- Added assertions for icon-only controls, accessibility labels, titles, and icon classes.

**Verification.** Vitest 395 passed (21 files); syntax and diff checks passed.

---

## 2026-09-06 — Terminal toolbar grouped dropdowns — DONE

### `src/frontend/static/index.html`
- Reordered terminal controls into three labeled dropdown groups: Paste, Settings, Full.
- Moved TUI Passthrough and Keep Screen On into Settings menu; retained two paste choices and two fullscreen choices.

### `src/frontend/static/terminal.js`
- Generalized dropdown setup and actions for Settings menu.
- Synchronized TUI, wake-lock, Full Page, and Fullscreen menu ARIA states.

### `src/frontend/static/i18n.js`
- Added labels for grouped toolbar controls and Paste normal action.

### `src/frontend/tests/terminal_layout.test.js`
- Verified exact three-group order and absence of standalone controls.

### `src/frontend/tests/terminal_toolbar.test.js`, `src/frontend/tests/views.test.js`
- Updated toolbar fixture IDs and behavior coverage.

**Verification.** Vitest 394 passed (21 files); syntax checks, diff check, and HTML artifact scan passed.

---

## 2026-09-06 — Tooltip lifecycle and independent fullscreen states — DONE

### `src/frontend/static/app.js`
- Icon popovers now auto-close 2 seconds after tap/click; timer is cleared on replacement and close events.

### `src/frontend/static/terminal.js`
- Added explicit `fullPageSelected` state and preserved it across true browser fullscreen entry/exit/failure.
- Synchronizes Full Page and true Fullscreen `aria-pressed`/`aria-checked` independently.

### `src/frontend/static/styles.css`
- Active blue styling applies only to controls with their own active ARIA state; caret has no active mode styling.

### `src/frontend/tests/terminal_toolbar.test.js`
- Added coverage for independent visual/accessibility states and request-failure restoration.

**Verification.** Vitest 394 passed (21 files), terminal toolbar 62 passed; syntax and diff checks passed.

---

**Purpose.** Every source-code change is logged here **per file** so the code and
the project documents never drift apart ("align"). This is the audit trail that
ties a running change back to the spec it implements.

**Rule.** Maintained per `documents/pm/OPERATING_RULES.md` **R22** — PM records each
verified code change here (newest section on top). Changes are logged AFTER they
are verified (tests run), not before. Environment tweaks outside the repo are
noted under "Environment (outside repo)". Not-yet-done work is marked **PENDING**
and completed when it lands.

---

## 2026-09-06 — Terminal toolbar markup repair — DONE ✅

**Goal.** Remove accidental tool-call text rendered beside the fullscreen icon and restore valid terminal toolbar HTML.

### `src/frontend/static/index.html`
- Replaced corrupted fullscreen split-button opening tag with valid `<span class="term-split" id="termFullscreenSplit">` markup.
- Preserved Keep Screen On control and `fa-mobile-screen-button` icon.

**Verification.** Final HTML read directly; frontend scan found no tool-call artifacts; `git diff --check` and JS syntax checks passed.

---

## 2026-09-06 — Side menu grouped by user needs — DONE ✅

**Goal.** Make sidebar navigation easier to scan by grouping items according to user needs without changing routes.

### `src/frontend/static/index.html`
- Grouped navigation into Gateway Setup, Operations, Insights, and System.
- Preserved all existing `data-view` values.
- Added accessible group labels and localized `aria-label` values for collapsed icon-only navigation.

### `src/frontend/static/styles.css`
- Added group headings and separators.
- Collapsed sidebar hides group text while retaining icon navigation.

### `src/frontend/static/i18n.js`
- Added EN/ID translations for four group headings.

### `src/frontend/tests/views.test.js`
- Added assertions for grouping order, route preservation, and localization keys.

**Verification.** Frontend Vitest: 21 files, 392 tests passed.

---

## 2026-09-05 — Terminal toolbar: Keep Screen On + Fullscreen/Paste dropdowns — DONE ✅

**Goal.** Three terminal-toolbar features: (1) a **Keep Screen On** toggle using
the Screen Wake Lock API so the tablet doesn't sleep mid-session (prevents the tab
freeze that drops the WS); (2) the **Fullscreen** button becomes a split-dropdown —
default stays "Full Page" (CSS), menu adds TRUE fullscreen (`requestFullscreen`,
F11-style); (3) the **Paste** button becomes a split-dropdown — default stays
normal paste, menu adds "Paste as Code Block" (wrap clipboard in a fenced block).

**Process note.** Two `fe-dev` spawns were interrupted by the flaky connection, but
the diffs landed (verified via markers + `git diff`). PM reviewed the code
line-by-line. A lingering `fe-dev` run (still alive after its receipt was cut) then
fixed the regex-literal typos (a missing closing `/` in `[^}]*\}` → `[^}]*\}/`) that
had desynced the esbuild/node lexer, and restored the "Dropdown CSS contract" block.
PM re-verified: the test file is now stable (md5 unchanged across checks, 0 live
writers). Feature tests authored by `fe-dev` (60 tests).

### `src/frontend/static/terminal.js` (+589, combined with the tab-id work below)
- **Keep Screen On:** `wakeLockSupported(nav)` (secure-context feature-detect),
  state `keepAwake={desired,sentinel,supported}`, `acquireKeepAwake()`,
  `releaseKeepAwakeSentinel()`, `toggleKeepAwake()`, `renderKeepAwake()` (disabled
  render when unsupported), `onVisibilityKeepAwake()` (re-acquire on return),
  `setupKeepAwake()`; intent persisted in `sessionStorage` key
  `aigate.term.keepAwake`.
- **True Fullscreen:** `fsElement()`, `fsSupported()`, `fsCall()`,
  `toggleTrueFullscreen()` (carries the full-page class while in, rolls back on
  exit via `fsRollbackCarried()`), `onFullscreenChange()`, `syncFullscreenMenu()`.
- **Paste as Code Block:** `wrapCodeBlock(text)` wraps the clipboard text between
  two triple-backtick fences with newlines — verbatim, NO added indentation, NO
  trailing newline; `pasteAsCodeBlock()`.
- **Shared dropdown:** `createTermMenu(caret,menu)` (tap-to-open, one-at-a-time,
  tap-outside + Esc + arrow-key focus, idempotent per node), `onDocTapClose`,
  `bindOnce`, `setupControlMenus()`.
- **Defaults preserved:** main `#termFullscreen` → `toggleFullscreen` (full page);
  main `#termPaste` → `pasteActive` (normal).
- **Exports:** test hooks added (`wrapCodeBlock`, `wakeLockSupported`, `_keepAwake`,
  `_toggleKeepAwake`, `_setupKeepAwake`, `_onVisibilityKeepAwake`,
  `_toggleFullscreen`, `_toggleTrueFullscreen`, `_onFullscreenChange`,
  `_fsSupported`, `_fsCarriedFullPage`, `_pasteActive`, `_pasteAsCodeBlock`,
  `_createTermMenu`, `_setupControlMenus`, `_openMenu`).

### `src/frontend/static/index.html` (+61)
- New `#termKeepAwake` toggle button; Fullscreen + Paste converted to split buttons
  with carets (`#termFullscreenCaret`/`#termPasteCaret`) and popover menus
  (`#termFullscreenMenu` → `#termMenuFullPage`/`#termMenuFullscreen`;
  `#termPasteMenu` → `#termMenuPaste`/`#termMenuPasteCode`), with
  `aria-haspopup`/`aria-expanded`/`role=menu`/`menuitemcheckbox`.

### `src/frontend/static/i18n.js` (+22)
- EN + ID keys: `term.full_page`, `term.exit_full_page`,
  `term.fullscreen_unsupported`, `term.fullscreen_menu`, `term.paste_code`,
  `term.keep_awake`, `term.keep_awake_on/off/unsupported/error`.

### `src/frontend/static/styles.css` (+92)
- `.term-split`, `.term-caret`, `.term-menu` (absolute popover, `pointer-events:auto`,
  z-index above the stage), `.term-menu-item` (≥40px touch target), checked +
  disabled states.

### `src/frontend/tests/terminal_toolbar.test.js` (NEW, 60 tests)
- wrapCodeBlock exact string; keep-awake feature-detect + acquire/release/
  re-acquire + disabled-when-unsupported; full-page default toggle; true-fullscreen
  enter/exit + fullscreenchange sync/rollback; paste normal vs fenced (exact);
  dropdown open/close (tap, outside, Esc).
- Includes a "Dropdown CSS contract" block (7 tests) — initially broken by a
  missing regex-closing `/` (lexer desync), fixed by the lingering `fe-dev` run.

### Verification (real, run in this env)
- `node --check src/frontend/static/terminal.js` → OK.
- `cd src/frontend && node node_modules/vitest/vitest.mjs run` → **21 files /
  390 tests passed** (330 prior + 60 new; no regression).
- **Not yet exercised in a real Chrome on the tablet** (R20 gap): wake-lock
  (needs http://localhost or HTTPS), true fullscreen, and the paste fence must be
  confirmed manually.

---

## 2026-09-05 — Terminal session persistence (survive Chrome tab DISCARD) — DONE ✅

**Goal.** The aigate web terminal survived a Chrome tab FREEZE (reconnect reuses
the in-memory `tab_id`) but LOST the session on a tab DISCARD: the renderer is
killed, the page reloads, and `openTab()` minted a fresh `crypto.randomUUID()` →
the backend treated it as a new session → fresh shell + orphaned PTY. Fix =
persist the terminal tab id(s) client-side so a reload REATTACHES to the same
backend PTY.

**Backend contract (unchanged, referenced for alignment).** WS
`/ws/terminal/{tab_id}`; the RAW `tab_id` string is the registry key; reconnect
with the SAME id reattaches + replays the ring buffer; a NEW id spawns a fresh
shell; disconnect ≠ kill (PTY survives up to `terminal_idle_reap_minutes`,
default 60); only `{"type":"close"}` kills. No backend file was touched.

### `src/frontend/static/terminal.js` (+123 / −18)
- **NEW persistence block (L46–102):** `TAB_IDS_KEY="aigate.term.tabIds"`,
  `readSavedTabIds()`, `writeSavedTabIds()`, `addSavedTabId()`,
  `removeSavedTabId()`, `mintTabId()`. Uses **`sessionStorage`** (per-tab;
  survives same-tab reload/discard-restore) — deliberately NOT `localStorage`
  (shared across browser tabs → two aigate tabs would collide on one PTY key).
- **`openTab(id)` (L451):** now takes an OPTIONAL id — reuses a given id
  (reattach), else mints a new one. Non-string arg (a click `Event`) is treated
  as "no id". Double-open guard: a live id → `activate(id)` + return existing.
  Registers the id via `addSavedTabId`. Returned tab shape unchanged.
- **`restoreTabs()` (NEW, L514):** opens one tab per saved id; returns true if
  ≥1 tab restored.
- **`closeTab(id)` (L590):** calls `removeSavedTabId(id)` (L616) AFTER
  `tabs.delete(id)` and BEFORE the last-tab `openTab()`, so a deliberately closed
  tab is never resurrected on reload and the replacement id is persisted.
- **`init()` (L828):** `newTabBtn` / `emptyNewTabBtn` click handlers wrapped so
  the click `Event` is never read as a tab id.
- **`onShow` (L909):** `if (activeId) refitActive(); else if (!restoreTabs()) openTab();`
  — restore-if-present, else first-load behavior. Lazy (no PTY/WS spawned for a
  user who never opens the Terminal view).
- **exports (L928):** added `_TAB_IDS_KEY`, `_readSavedTabIds`, `_restoreTabs`,
  `_mintTabId` (test/introspection hooks).
- **Untouched (verified):** WS protocol, `wireSocket`, `connectSocket`,
  `scheduleReconnect`, `checkLiveness`/`armLiveness`, ping/pong heartbeat,
  backoff, resize, close-frame, swipe/inertia, `launchInNewTab`.

### `src/frontend/tests/terminal_discard.test.js` (NEW, 16 tests)
Harness uses `vi.resetModules()` + re-import per test to simulate a real page
reload (fresh `tabs` Map + `activeId`). Covers:
- (a) `openTab()` persists its minted id; accumulates ids in order, deduped;
  `openTab(id)` reuses the given id; non-string arg still mints fresh.
- (b) restore opens the WS with the PERSISTED id (not a fresh uuid); does not
  also open a fresh tab; idempotent; empty/absent behaves like first load;
  corrupt stored values ignored; a restored tab keeps the FREEZE reattach path.
- (c) `closeTab(id)` removes exactly that id; keeps the "≥1 tab" invariant and
  persists the replacement; a user-closed tab is never resurrected by a reload.
- (d) `openTab()` returns a working tab when `sessionStorage` throws; a failing
  `setItem` (quota) still opens a working tab; without storage, behaves as before.

### Verification (real, run in this env)
- `node --check src/frontend/static/terminal.js` → OK.
- `cd src/frontend && node node_modules/vitest/vitest.mjs run` → **20 files /
  330 tests passed** (incl. `terminal_discard` 16, `terminal_reconnect` 24 — no
  regression). Re-run by PM independently.
- **Not yet exercised end-to-end in a real Chrome discard** (R20 gap) — the
  discard→reload reattach must be confirmed manually on the tablet.

### Environment (outside repo)
- `~/.bashrc` — added an idempotent `termux-wake-lock` auto-acquire block so the
  Termux-hosted aigate server (and its terminal PTYs) are not frozen by Android
  doze when the tablet screen is off. No package installed (binary already
  present). Wake lock also acquired live in the current session (exit 0).

---

## 2026-09-06 — codegraph bug patch (environment, outside repo) — DONE

### Environment (outside repo)
- **colbymchenry/codegraph v1.6.0** (npm global `@colbymchenry/codegraph`) — tool
  semantic code-graph (Rust kernel + bundled Node glibc). Di Termux/Android tool ini
  gagal out-of-the-box karena: (a) shim deteksi `process.platform='android'` → cari
  bundle `codegraph-android-arm64` yg TIDAK ada (404); (b) binary glibc butuh loader
  `/lib/ld-linux-aarch64.so.1` yg gak ada di Termux, padahal loader glibc WORKING ada
  di `/data/data/com.termux/files/usr/glibc/lib/ld-linux-aarch64.so.1` (libc.so.6 valid).
  Tiga patch diterapkan biar jalan:
  1. File global
     `/data/data/com.termux/files/usr/lib/node_modules/@colbymchenry/codegraph/npm-shim.js`
     — baris `var target = process.platform + '-' + process.arch;` diubah jadi
     `var target = 'linux-arm64';` (paksa download bundle linux-arm64 yg valid).
  2. Shebang shim `#!/usr/bin/env node` → `#!/data/data/com.termux/files/usr/bin/node`
     (Termux tidak punya `/usr/bin/env`).
  3. Launcher bundle `~/.codegraph/bundles/linux-arm64-1.6.0/bin/codegraph`: baris
     `exec "$DIR/node" ...` diubah jadi
     `exec /data/data/com.termux/files/usr/glibc/lib/ld-linux-aarch64.so.1 "$DIR/node" ...`
     agar node glibc dieksekusi lewat loader glibc yang ada.
  Tanpa patch ini `codegraph init` gagal total di Termux. Hasil: `codegraph init` di
  project → `.codegraph/codegraph.db`, 121 files / 2,851 nodes / 9,151 edges, 2.0s.
  CATATAN: (1)+(2) ada di global npm package — hilang kalau
  `npm i -g @colbymchenry/codegraph` diulang; (3) ada di cache bundle
  `~/.codegraph/bundles/linux-arm64-1.6.0` — hilang kalau dihapus. Bukan file repo;
  tidak ikut commit. (Catatan lama soal xnuinside/codegraph sudah tidak berlaku — itu
  tool salah yg sudah di-uninstall.)

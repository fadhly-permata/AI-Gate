# Code Changes Register (code ↔ docs alignment)

## 2026-09-09 — Harness tes FE: `localStorage` ke-mask global Node (PR #15, branch fix/fe-test-env) — DONE (DI-COMMIT 95d46e4, PR #15 open)

**Asal:** isu tertunda (#3) dari sesi bottom-nav ponsel — suite FE penuh merah **22 fail**
`window.localStorage`/`sessionStorage` undefined (`logwindow.test.js` 21 + `terminal_discard.test.js` 1),
repro walau satu file dijalankan sendirian.
**Akar (fe-dev, dibuktikan empiris):** **Node v26.4.0** (≥22.4) nyediain global webstorage
`globalThis.localStorage`/`sessionStorage` sendiri; getter-nya `undefined` tanpa `--localstorage-file`.
Vitest 2.1.9 nyalin properti storage jsdom ke global CUMA kalau namanya belum ada / masuk KEYS allow-list —
`localStorage` gak masuk → tes lihat stub Node. `sessionStorage` Node kebetulan jalan → pas 22 (pemakai
localStorage) yang kena. (BUKAN `npm ci`; hipotesis PM `environmentOptions.jsdom.url` = no-op — vitest udah
default url `http://localhost:3000`.)

### Perubahan (murni harness `src/frontend/**`; 0 tes dihapus/dilemahkan; 0 kode produksi; `package.json` tetap)
- `src/frontend/tests/helpers/jsdom-storage.js` (BARU, setupFile PERTAMA): re-point `globalThis.localStorage`/
  `sessionStorage` ke storage milik window jsdom (getter delegasi; `configurable:true` biar swap sessionStorage
  terminal_discard tetap jalan; no-op kalau `globalThis.jsdom` absen → gagal nyaring, bukan diem).
- `src/frontend/vitest.config.js`: `setupFiles` di-depan-in `./tests/helpers/jsdom-storage.js` (+ komentar).
  `isolate:false` + `maxForks:2` UTUH. Menghilangkan dependensi urutan file `isolate:false` (`settings.test.js`
  tadinya ikut gagal saat jalan sendiri, ke-mask stub tetangga).

### Verifikasi (PM jalanin ulang, R35)
- `node node_modules/.bin/vitest run` → **23 file / 523 tes PASS, 0 fail** (11.32s). Sebelum: 22 fail.
- CAVEAT: bergantung exposure semi-dokumentasi `globalThis.jsdom` (dijaga) — re-run gate tiap Node/vitest/isolate berubah.

## 2026-09-09 (lanjutan) — Bottom-nav ponsel: mirror 9 view + link Repo + separator grup — DONE (DI-COMMIT 6fb210b+26b087d, pushed, PR #14 MERGED a1777f1)

**Permintaan user (retest di HP):** (1) "menu bawah masih gak bisa digeser / ada item yang
di-hidden?" → ternyata `.bottom-nav` cuma punya **7** dari **9** view menu samping; `usage`
(Pemakaian & Kuota) + `analytics` (Analitik) **gak pernah di-render** di ponsel (bukan ketutup —
gak ada tombolnya). (2) "sekalian tambahin link Repo + separator buat tiap grup menu."

**Owner:** `fe-dev` (3 spawn iteratif: hamburger+scroll → tambah usage/analytics → repo+separator).
PM verifikasi tiap ronde + jalanin tes.

### Perubahan akhir (semua `src/frontend/**`; menimpa sebagian ronde-1 di bawah)
- `static/index.html` `.bottom-nav` (kini ~baris 1143-1170): **9 app view** urutan sama dgn
  sidebar + **1 link Repo** (icon-only `fa-brands fa-github`, `target=_blank rel=noopener`,
  **TANPA `data-view`** → guard `app.js:1679` biarin dia jadi link eksternal asli;
  `app.js:1464` tetap kasih tooltip; `syncBottomNav` guard `!!view` bikin dia gak pernah `.active`)
  = **10 `.bn-item`**. Ditambah **4 `<span class="bn-sep" aria-hidden="true">`** di batas grup:
  endpoints→terminal, cli→usage, analytics→settings, settings→repo (Gateway|Operasi|Wawasan|Sistem|Repo).
- `static/styles.css`: rule BARU `.bn-sep { flex:0 0 auto; width:1px; align-self:center;
  height:26px; margin:0 2px; background: var(--panel-border); }` setelah blok `.bn-item`
  (token-only → ikut tema gelap/terang). Deklarasi `.bottom-nav`/`.bn-item` ronde-1 UTUH
  (overflow-x:auto + justify-content:flex-start + `-webkit-overflow-scrolling:touch` + min-width:60px).
- cache-buster `index.html:17`: `styles.css?v=20260913` → **`?v=20260914`** (styles.css nambah rule nyata).
- `tests/views.test.js`: guard lama "repo TIDAK ada di bottom-nav / count=9" **dibalik** → repo
  HADIR (`.bn-item[href*="github"]`, href/target/rel/no-data-view benar), count **10**; parity test
  pakai `.bottom-nav .bn-item[data-view]` (9 view; repo non-data-view gak nyumbang `null`); scroll
  test `10 × 60 = 600 > 360`; **+ tes baru** `.bn-sep` count === 4 + cek tiap pembatas duduk di
  batas grup yg benar (pasangan `data-i18n-aria` tetangga) + kontrak CSS `.bn-sep`.

### Verifikasi (PM)
- `vitest run tests/views.test.js` → **25 pass** (hamburger-hidden, parity, scroll=10, sep=4).
- `git diff --check` bersih; `index.html` ke-parse jsdom tanpa error (0 artefak markup, R24).
- Tablet(>600px)/desktop gak kena: `.bottom-nav` base tetap `display:none`, sidebar + hamburger utuh.
- ⚠️ **Layout & horizontal-scroll browser-asli BELUM terbukti** — no browser di box, jsdom gak
  ngukur flex/`@media`. WAJIB pass manual di HP: geser menu bawah sampe ikon GitHub keliatan &
  kebuka, pastiin 4 garis tipis (separator) tampil, tap Pemakaian/Analitik/Repo berfungsi. (R20)
- Task susulan terpisah (masih terbuka, dari ronde-1): suite FE penuh merah 22 fail
  `localStorage`/`sessionStorage` (logwindow + terminal_discard) — lingkungan (npm ci vitest 2.1.9 +
  jsdom 25.0.1), BUKAN regresi UI.

## 2026-09-09 — Phone shell: hamburger disembunyikan + bottom-nav scroll horizontal — DONE (DI-COMMIT 6fb210b, pushed, PR #14 MERGED a1777f1)

**Permintaan user:** di ponsel (mode potret) tombol hamburger hide/show sidemenu nge-bug →
hilangkan saja; sidemenu yang pindah ke bawah bikin banyak menu gak bisa diakses → buat
scrollable ke samping. Pastikan tablet & desktop tidak terpengaruh.

**Owner:** `fe-dev` (perubahan CSS-only). Verifikasi: PM (audit diff + bukti stash).

### Perubahan (semua di `src/frontend/**`)
- `static/styles.css`:
  - `.bottom-nav` (rule BASE, ~baris 565): `justify-content: space-around` → `flex-start`,
    tambah `overflow-x: auto` + `-webkit-overflow-scrolling: touch`. Alasannya di rule base
    supaya KEDUA shell phone mewarisi seragam; di tablet/desktop `.bottom-nav` `display:none`
    → tidak kena. `flex-start` itu penting: baris `space-around`/centered yang overflow
    menumpahkan ke DUA sisi → item pertama ikut tak terjangkau.
  - `.bn-item` (base, ~baris 575): tambah `min-width: 60px` di atas `flex: 1 1 0` → 7 ikon
    mengisi rata saat muat, overflow→scroll saat tidak (7×60=420 > 360), tak pernah ke-squeeze/ke-clip.
  - blok `@media (max-width: 600px)` (phone shell, ~baris 645): tambah `#sidebarToggle { display: none; }`.
  - `body[data-device="phone"]` (~baris 671): tambah `#sidebarToggle { display: none; }` (mirror simulasi).
  - +3 komentar niat (d strip oleh helper `stylesCss()` di tes → tak mengganggu assert teks CSS).
- `static/index.html:17`: cache-buster `styles.css?v=20260912` → `?v=20260913`.
- `tests/views.test.js`: +`describe("phone shell — hamburger hidden, bottom nav scrollable")`
  (2 tes). jsdom tak mengevaluasi `@media`/layout flex, jadi tes meng-assert TEKS rule
  (konvensi sama dgn cek sticky-footer); ekstraksi blok `@media` pakai brace-matching supaya
  `#sidebarToggle{display:none}` NON-scoped tak bisa lolos sbg "didalam query". Guard positif:
  tepat 2 rule `#sidebarToggle` se-file, dan blok tablet `@media (max-width:960px)` tak boleh nyentuhnya.

### Verifikasi
- `vitest run tests/views.test.js` → **23 pass** (21 lama + 2 baru). Sapuan fe-dev 15 file yang
  membaca `styles.css` → **299 pass**. `git diff --check` bersih; working tree = 3 file itu saja.
- Gate PM (suite FE penuh) **merah 22 fail** `localStorage`/`sessionStorage` undefined di
  `logwindow.test.js` + `terminal_discard.test.js`. **Dibuktikan BUKAN efek perubahan ini:**
  ke-3 file di-`git stash` → pada tree bersih 2 file itu tetap gagal identik (22 fail / 29 pass).
  = regresi LINGKUNGAN: `src/frontend/node_modules` sempat kosong, `npm ci` menarik
  vitest 2.1.9 + jsdom 25.0.1; probe: jsdom butuh url ber-origin supaya `localStorage` tersedia.
  → TASK SUSULAN terpisah (qa/fe-dev infra) di luar scope UI ini.

### Open (keputusan user, belum dikerjakan)
- Chrome scrollbar non-overlay muncul saat simulasi phone di desktop (memakan tinggi baris 56px);
  di Android/iOS berupa overlay → tak terlihat. YAGNI, sengaja belum disembunyikan.
- Tak ada affordance bahwa nav bisa digeser (fade/peek/scroll-snap) — butuh keputusan desain.
- `#sidebarToggle` masih di DOM + handler `app.js:1611` masih bind/persist ke `SIDEBAR_KEY`
  (collapsed-state laten sampai user balik ke tablet/desktop) — kosmetik.
## 2026-09-09 — feat: catalog kompatibilitas per-tool × per-platform + tampilan `cli tools` (branch `setup/cli-tools`) — DONE

**Tujuan:** rancang & implementasi katalog kompatibilitas 24 CLI tool aigate across
Termux/Linux/Windows/macOS, lalu tampilkan di perintah `cli tools` (frontend CLI
Tools view) berupa badge status per platform dengan platform saat ini disorot +
warning merah bila tool tidak kompatibel di platform saat ini.

**Catatan proses (transparan, R29):** tool `Task`/spawn sub-agent TIDAK tersedia di
environment sesi ini (sama seperti sesi-sesi lalu, lihat `status.md`), sehingga PM
eksekusi langsung dengan batas file yang ketat (`src/backend/**` + `src/frontend/**`
+ `documents/pm/**` + `documents/dev/CODE_CHANGES.md` sesuai instruksi task). Bukan
pelanggaran fungsional R21/R29 — deviasi alat, dicatat di sini.

### `src/backend/cli_compat.py` (BARU)
- `CLI_COMPAT: dict[str, dict[str, dict]]` — `tool -> platform -> {status, note, source}`.
  Kolom `termux` di-seed dari fakta on-device (Termux aarch64, Py3.14.6, 2026-09);
  `linux`/`windows`/`macos` = `unknown` (user isi nanti).
- Status per Termux: verified=aichat (1); broken=claude,opencode,aider,qwen,cline,
  kilo,llm,oterm,gptme,openhands,open-interpreter (11); no_install=antigravity,phi,
  goose,amp,swe-agent,autogpt,sgpt,mods (8); not_a_cli=gpt-researcher,crewai (2);
  not_wired=gemini,codex (2).
- Konstanta: `PLATFORMS=("termux","linux","windows","macos")`, `WARN_STATUSES`,
  `STATUS_*`; helper `current_platform()` (reuse `backend.paths.is_termux`, lazy
  import) + `compat_for(name)`.
- Import `is_termux` **lazy** (di dalam `current_platform`) agar `import cli_compat`
  bebas dependency (jalankan dari `src/backend` maupun `src` dengan PYTHONPATH).

### `src/backend/cli_tools_router.py` (MODIFY)
- Import `from backend.cli_compat import compat_for, current_platform`.
- `ToolDTO` (+L64): tambah field `compat: Dict[str, dict] = {}`.
- `_tool_to_dto` (+L163): isi `compat=compat_for(tool.name)`.
- `list_cli_tools` (L1000): response jadi `{"object","data","current_platform": current_platform()}`.

### `src/frontend/static/clitools.js` (MODIFY)
- `loadCliTools` (+L174): ambil `data.current_platform`, teruskan ke `renderGroups`.
- Helpers baru: `COMPAT_PLATFORMS`, `COMPAT_WARN`, `platformLabel`, `statusLabel`,
  `renderCompatStrip` (4 badge per tool, platform saat ini `.cli-compat-current`),
  `renderCompatWarn` (warning merah bila status platform saat ini ∈ WARN_STATUSES),
  `renderCompatLegend` (legend sekali di atas grup).
- `renderGroups(groups, currentPlatform)` (+L257): tiap tool dibungkus `.cli-tool-cell`
  (button + strip badge + warning opsional); `.cli-tool` tetap di button sehingga
  test `clitools.test.js` tetap valid.

### `src/frontend/static/styles.css` (MODIFY, +L1599)
- Kelas baru: `.cli-tool-cell`, `.cli-compat`, `.cli-compat-chip`, `.cli-compat-current`,
  `.cli-compat-legend`, `.cli-compat-warn` (light + dark), dan `.cli-status-{verified,
  installable, broken, no_install, not_a_cli, not_wired, unknown}`.

### `src/frontend/static/i18n/{en,id,ja,nl,ru,zh,zh-tw}.js` (MODIFY)
- +13 key (`cli.compat.legend`, `cli.compat.warn_label`, `cli.platform.*`,
  `cli.status.*`). en/id diterjemahkan; 5 lain mirror EN (parity tetap hijau —
  cek `.opencode/tools/tests/i18n-parity-check.mjs` → semua locale 0 missing/0 extra/
  0 empty).

### `documents/pm/cli-tools-compatibility.md` (BARU)
- Mirror human-readable (tabel tool × platform + ringkasan + catatan sinkronisasi ke `cli_compat.py`).

**Verifikasi (R14/R35):**
- Backend: `python3 -m py_compile` bersih; `import cli_compat` (bare & `PYTHONPATH=src`)
  OK; `current_platform()`→`termux`; `list_cli_tools()` end-to-end (DB ada di device)
  balik `current_platform=termux` + per-tool `compat` (claude termux=`broken`).
- Frontend: `node --check clitools.js` OK; locale files tereksekusi bersih via parity
  checker; `clitools.test.js` assertions ditrace manual tetap valid (struktur DOM selamat).
  **Suite vitest penuh TIDAK dijalankan** (no `node_modules` di sandbox) — batas env.

## 2026-09-09 — BUGFIX: aider.sh guard Python 3.10–3.12 (branch `setup/cli-tools`) — DONE (commit `1d1a31c`)

**Bug:** user lapor `scripts/cli-tools/aider.sh` → `pip install aider-chat` error saat dijalankan di device ini.

**Root cause (terverifikasi fakta, R47/R48):**
- Device Python = **3.14.6** (`python3 --version`); pip 26.2.1.
- PyPI `aider-chat` latest = **0.86.2**, `requires_python = ">=3.10,<3.13"` (cross-check PyPI JSON `info.requires_python`). Rilis 0.16.1–0.86.2 semuanya "require a different python version" → pip tolak di 3.14.
- Error asli pip (`pip install --no-deps aider-chat==0.86.2`): `ERROR: Could not find a version that satisfies the requirement aider-chat==0.86.2 (from versions: 0.13.0 ... 0.16.0)` + `ERROR: No matching distribution found for aider-chat==0.86.2`. (Pada unpinned dry-run sebelumnya pip malah lanjut build aiohttp 3.8.4 sdist — native build juga gagal di 3.14; dua-duanya akar sama: Python di luar range aider.)
- Skrip lama HANYA punya catatan `NOTE` **Termux-only** yang dicetak **SETELAH** `ensure_installed` sudah mencoba install → user tetap dapet raw pip error. Tidak ada `exit 1` pre-install guard.

**Fix (`scripts/cli-tools/aider.sh`, +28/−12):**
- Tambah **version-guard SEBELUM** `ensure_installed`: deteksi `python3 --version` → major.minor; kalau di LUAR 3.10–3.12 → `log_msg "ERROR: aider needs Python 3.10–3.12; this device has Python <x.y>."` + saran (`pkg install python3.11` / pyenv / venv) lalu **`exit 1` TANPA menjalankan pip install**.
- Guard berlaku **semua platform** (bukan cuma Termux), pakai pengecekan numerik major/minor (robust utk "3.14.6" → 3.14).
- Hapus blok `NOTE` Termux-only lama (redundan + sudah jadi bug).
- Wiring launch (flags `--openai-api-base/--openai-api-key` + `--model openai/<m>`, env `OPENAI_API_BASE/KEY`, reachability probe) **tetap utuh**; idempoten via `ensure_installed`; `set -euo pipefail` + `_common.sh` tetap.

**Verifikasi PM (R14/R35):** `bash -n scripts/cli-tools/aider.sh` → **clean**; mode `-rwx------` (exec). Simulasi guard: 3.10/3.11/3.12 → lanjut install; 3.9/3.13/3.14/3.14.6/2.7/4.0 → `exit 1`. (Tidak jalanin install beneran — batas sandbox, sesuai brief.)

## 2026-09-09 — BUGFIX: openhands.sh guard Python 3.12 (branch `setup/cli-tools`) — DONE (commit `313a2c2`)

**Bug:** `scripts/cli-tools/openhands.sh` → `pip install openhands` (fallback route) error di device ini (Python 3.14.6; openhands `requires_python ==3.12.*` per PyPI 1.16.0) → pip tolak `"requires a different Python: 3.14.6 not in '==3.12.*'"`. Route utama `uv tool install openhands --python 3.12` mengelola 3.12 sendiri (gak peduli system python), TAPI device ini gak punya `uv` → pip route gagal.

**Fix (`scripts/cli-tools/openhands.sh`, +30 baris):** tambah **version-guard SEBELUM** `ensure_installed`:
- `if have_cmd uv` (= `command -v uv`) → lanjut (uv fetch managed 3.12 sendiri, gak peduli system python).
- `elif have_cmd python3` → parse major.minor (`sys.version_info[:2]`); kalau **bukan persis 3.12** → `log_msg "ERROR: openhands butuh persis Python 3.12 ..."` + saran (`pkg install python3.12`/pyenv/venv/uv) lalu **`exit 1` TANPA jalanin install**.
- `else` / parse-gagal → WARN (best-effort, tetap lanjut).
Guard cross-platform (parse `sys.version_info`), idempoten, `set -euo pipefail` + `_common.sh` tetap. Wiring launch (`LLM_BASE_URL`/`LLM_API_KEY` + `LLM_MODEL=openai/<m>` + flag `--override-with-envs`) **tetap utuh**.

**Verifikasi PM (R14/R35):** `bash -n scripts/cli-tools/openhands.sh` → **clean**; mode `-rwx------` (exec). Simulasi guard (uv absen): 3.12 → lanjut pip; 3.13/3.14/3.14.6/3.11/3.10/3.9/2.7/4.0 → `exit 1`. (Tidak jalanin install beneran — batas sandbox, sesuai brief.)

**Konfirmasi NOT_A_CLI (crewai.sh / gpt-researcher.sh):** di-READ SELURUHNYA — kedua script TIDAK menjalankan `pip install`/`uv tool install` (cuma `log_msg` + `exit 0`, status `LAUNCH_UNSUPPORTED`/`REASON_NOT_A_CLI`). Tidak ada install step yang bisa gagal versi → **version-guard TIDAK ditambahkan, TIDAK diubah**. (Hipotesis awal terbukti: openhands = install → butuh guard; crewai/gpt-researcher = NOT_A_CLI → guard gak relevan.)

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

### `scripts/cli-tools/swe-agent.sh` (BARU) — **B2 swe-agent = NO_INSTALL (message + exit 0, no side-effect)**
- TIDAK memasang apa pun (sesuai keputusan user utk tool `NO_INSTALL`): script hanya
  menampilkan pesan lalu `exit 0` (no-op, idempoten, tanpa side-effect).
- Pesan: `swe-agent: NO_INSTALL — belum ada install terverifikasi`
- Fakta kunci (cross-check 3 sumber independen, R47/R48):
  - `cli_presets.py:89` → `{"name":"swe-agent","binary":"swe-agent","install": NO_INSTALL}` (NO_INSTALL = echo no-op).
  - `cli_presets.py:216` → `"swe-agent": LaunchSupport(LAUNCH_UNSUPPORTED, REASON_INSTALL_UNVERIFIED)` — aigate menandai swe-agent BUKAN CLI yang bisa di-launch (install tidak terverifikasi).
  - `TERMUX_INSTALL` map (`cli_presets.py:241-244`) HANYA berisi `aichat` + `codex` — TIDAK ada entry swe-agent → di Termux pun tak ada rute install terverifikasi.
  - PyPI `swe-agent` = **404** (tidak ada paket sama sekali); `sweagent` (tanpa strip) = **v0.0.1** tapi library yang butuh **Docker + conda** (tidak praktis di Termux). GitHub setup swe-agent resmi **berat** (container/conda). Cross-check 3 sumber → TIDAK ada install terverifikasi di env ini.
- Script source `_common.sh` (read-only: `detect_os`/`detect_pm`/`load_gateway_config` + `log_msg`) lalu log pesan + `exit 0`. Tidak ada `ensure_installed`/install command.
- **Bug yang sudah dibenerin (lesson):** versi awal pesan NO_INSTALL ke-tulis pakai backtick command-substitution yang TIDAK sengaja mengeksekusi `pip install swe-agent` saat pesan di-render. Sudah dibenerin → pesan murni teks statis, TIDAK ada command-substitution di dalam pesan NO_INSTALL. **Aturan: pesan NO_INSTALL harus literal — jangan pernah dibungkus backtick/`$()` (bisa jadi eksekusi tak disengaja).**
- Verifikasi: `bash -n scripts/cli-tools/swe-agent.sh` → clean; mode `-rwx------` (exec); eksekusi langsung → `exit 0`, TIDAK memasang apa pun.

### `scripts/cli-tools/open-interpreter.sh` (BARU) — **B3 open-interpreter = OpenAI-compatible (verified)**
- Install + launch script untuk **open-interpreter** (B3). Install idempoten via `ensure_installed` → `python3 -m pip install open-interpreter` (fakta `cli_presets.py:90` = `_pip("open-interpreter")` → `pip install open-interpreter`, bin `interpreter`).
- Launch **OpenAI-compatible** — open-interpreter bicara Chat Completions ke aigate (`/v1/chat/completions`). Wiring TEPAT mirip `_interpreter_builder` (`cli_tools_router.py:824-837`): `interpreter --api_base <base> --api_key <key> [--model openai/<model>]` (model flag di-skip bila `--model`/`AIGATE_MODEL` kosong, sama seperti builder) + env `OPENAI_API_BASE`+`OPENAI_API_KEY` (dari `load_gateway_config`) ke `<base>/chat/completions`.
- Fakta kunci (cross-check): open-interpreter = `LAUNCH_VERIFIED` (`cli_presets.py:196`); builder `_interpreter_builder` (`cli_tools_router.py:824-837`). PyPI `open-interpreter` 0.4.3 pure-python, `requires_python ">=3.9,<4"` (install di Python 3.9–3.13; host ini 3.14.6 masih `<4` → resolver lolos, kontras openhands yang pin 3.12).
- Catatan product drift (bukan blocker, R47/R48 cross-check 3 sumber): situs live `docs.openinterpreter.com` + repo GitHub sekarang nggarap produk **Rust/Codex-fork** yang TIDAK punya flag `--api_base`/`--api_key`; tapi paket `pip install open-interpreter` (0.4.3, Python line) yang dipasang preset **MASIH punya** flag `--api_base`/`--api_key` (terkonfirmasi dari PyPI 0.4.3 README + builder aigate). Script pakai flag Python package — benar per preset. JANGAN pakai `curl install.sh` dari situs live (itu produk Rust yang salah).
- Verifikasi: `bash -n scripts/cli-tools/open-interpreter.sh` → clean; mode `-rwx------` (exec). Commit `31b9a04`.

### `scripts/cli-tools/autogpt.sh` (BARU) — **B4 autogpt = NO_INSTALL (message + exit 0, no side-effect)**

- TIDAK memasang apa pun (sesuai keputusan user utk tool `NO_INSTALL`): script hanya menampilkan pesan `autogpt: NO_INSTALL — belum ada install terverifikasi di environment ini.` + `exit 0` — TIDAK memasang apa pun (no side-effect, idempoten).
- Pesan: `autogpt: NO_INSTALL — belum ada install terverifikasi di environment ini.`
- Fakta kode (cross-check 3 sumber):
  - `cli_presets.py:91` → `{"name":"autogpt","binary":"autogpt","install": NO_INSTALL}` (NO_INSTALL = echo no-op).
  - `cli_presets.py:217` → `"autogpt": LaunchSupport(LAUNCH_UNSUPPORTED, REASON_INSTALL_UNVERIFIED)` — aigate menandai autogpt BUKAN CLI yang bisa di-launch (install tidak terverifikasi).
  - `TERMUX_INSTALL` map (`cli_presets.py:241-244`) HANYA berisi `aichat` + `codex` — TIDAK ada entry autogpt → di Termux pun tak ada rute install terverifikasi.
  - PyPI `autogpt` = **placeholder/squat tak terkait** (author "Shadow Walker" / shadowwalker2718, versi `0.0.1.dev0`, upload 2023-04-02, `requires_dist: ["torch"]` SAJA, TIDAK ada `[project.scripts]`/console script → `pip install autogpt` TIDAK menghasilkan biner `autogpt` di PATH). BUKAN AutoGPT resmi (Significant-Gravitas).
  - GitHub resmi `Significant-Gravitas/AutoGPT` kini berupa **PLATFORM** — di-host (berbayar) atau self-host butuh **Docker + konfigurasi + API key sendiri** (install via `install.sh` setup.agpt.co / Docker Compose). Berat & tidak praktis di Termux/android-arm64 → tidak ada biner CLI tunggal yang bisa di-spawn aigate di environment ini. Cross-check 3 sumber → TIDAK ada install terverifikasi di env ini.
- **Catatan transparan:** ada paket PyPI bernama `autogpt`, TAPI itu placeholder TAK TERKAIT (bukan AutoGPT resmi) dan tidak menghasilkan biner; AutoGPT asli butuh Docker. Sesuai keputusan user untuk tool `NO_INSTALL`: script HANYA menampilkan pesan lalu KELUAR — TIDAK memasang paket apa pun (aman, hindari pasang paket salah / placeholder / squat).
- Verifikasi: `bash -n scripts/cli-tools/autogpt.sh` → clean; mode `-rwx------` (exec); eksekusi langsung → `exit 0`, TIDAK memasang apa pun.

### `scripts/cli-tools/gpt-researcher.sh` (BARU) — **B5 gpt-researcher = NOT_A_CLI (message + exit 0, no side-effect)**
- gpt-researcher **pip-installable & resmi** (`pip install gpt-researcher`, `cli_presets.py:92`, PyPI `gpt-researcher` v0.16.0 oleh Assaf Elovic) — TAPI **TIDAK punya biner CLI**: PyPI metadata tidak ada `console_scripts`/`[project.scripts]`/`entry_points` → `pip install` tidak menghasilkan biner `gpt-researcher` di PATH; docs resmi cuma `python cli.py "<query>"` (wajib argumen query, tulis file report lalu EXIT) — bukan CLI interaktif yang bisa di-host PTY aigate. aigate **TIDAK punya `_gpt_researcher_builder`** di `_LAUNCH_BUILDERS` → `resolve()` mengembalikan 409 `tool_unsupported`. Jadi BUKAN murni `NO_INSTALL` (seperti autogpt/swe-agent), melainkan **bukan CLI yang bisa di-launch** — `LAUNCH_UNSUPPORTED` / `REASON_NOT_A_CLI` (`cli_presets.py:197-204`).
- Script: source `_common.sh` (read-only helpers: `detect_os`/`detect_pm`/`load_gateway_config` + `log_msg`) lalu log pesan penjelasan + `exit 0`. **TIDAK memasang/menjalankan apa pun** yang bisa di-spawn (no side-effect, idempoten). Sengaja TIDAK menjalankan `pip install` / `python cli.py` agar tidak memasang paket yang tak bisa di-launch atau menjalankan one-shot script wajib-query.
- Fakta kunci (cross-check ≥2 sumber, R47/R48):
  - `cli_presets.py:92` → `{"name":"gpt-researcher","binary":"gpt-researcher","install": _pip("gpt-researcher")}` — preset memang punya install string `pip install gpt-researcher` (paket ADA & RESMI, bukan `NO_INSTALL`).
  - `cli_presets.py:197-204` → `"gpt-researcher": LaunchSupport(LAUNCH_UNSUPPORTED, REASON_NOT_A_CLI)` — aigate menandai gpt-researcher BUKAN CLI yang bisa di-launch.
  - PyPI `gpt-researcher` v0.16.0: metadata TIDAK ada `[project.scripts]`/`console_scripts`/`entry_points` (0 hit regex) → `pip install` TIDAK menghasilkan biner `gpt-researcher`; dependensi (litellm, langchain, openai, fastapi, duckduckgo-search) mengonfirmasi ini library/agency paket, bukan CLI biner. `requires_python ">=3.12"`.
  - Docs resmi (github.com/assafelovic/gpt-researcher + docs.gptr.dev): pemakaian via `from gpt_researcher import GPTResearcher` (library); "Run with CLI" butuh `git clone` + `pip install -r requirements.txt` + `python cli.py <query> --report_type <type>` (wajib query, EXIT setelah tulis report); server mode butuh `python -m uvicorn main:app` / Docker — bukan biner tunggal. Env: `OPENAI_API_KEY` + `TAVILY_API_KEY`; base custom via `OPENAI_BASE_URL` (memang OpenAI-compatible, tapi tidak ada biner CLI untuk di-wire ke aigate `/v1/chat/completions`).
- Verifikasi: `bash -n scripts/cli-tools/gpt-researcher.sh` → clean; mode `-rwx------` (exec `100755`); eksekusi langsung → `exit 0`, TIDAK memasang apa pun.

### `scripts/cli-tools/crewai.sh` (BARU) — **B6 crewai = NOT_A_CLI (message + exit 0, no side-effect)**
- crewai **pip-installable & resmi** (`pip install crewai`, `cli_presets.py:93`, PyPI `crewai` v1.15.20 oleh crewAIInc) — TAPI **TIDAK bisa di-launch sebagai CLI aigate**: biner `crewai` (entry point `[console_scripts] crewai = crewai_cli.cli:crewai`) memang terpasang via pip, tapi itu **framework project scaffolder/runner**, bukan asisten CLI interaktif. `crewai run`/`crewai chat` butuh **proyek di CWD** (membaca config TOML crew di direktori tsb) dan **TIDAK menerima flag `--model`/`--base-url`/`--prompt`** di launch — konfigurasi LLM (OpenAI-compatible) ditulis di kode proyek (`LLM(model="openai/<id>", base_url=..., api_key=...)`) atau env `OPENAI_API_KEY`/`OPENAI_API_BASE_URL`, BUKAN surface CLI. Di direktori kosong keduanya error. aigate **TIDAK punya `_crewai_builder`** di `_LAUNCH_BUILDERS` (`cli_tools_router.py` ~:976-988) → `resolve()` mengembalikan 409 `tool_unsupported`. Jadi BUKAN murni `NO_INSTALL` (seperti autogpt/swe-agent), melainkan **bukan CLI yang bisa di-launch** — `LAUNCH_UNSUPPORTED` / `REASON_NOT_A_CLI` (`cli_presets.py:205-215`).
- Script: source `_common.sh` (read-only helpers: `detect_os`/`detect_pm`/`load_gateway_config` + `log_msg`) lalu log pesan penjelasan (pip-installable tapi NOT_A_CLI) + `exit 0`. **TIDAK memasang/menjalankan apa pun** yang bisa di-spawn (no side-effect, idempoten). Sengaja TIDAK menjalankan `pip install crewai` / `crewai run`/`chat` agar tidak memasang/scaffold proyek yang tak bisa di-launch, atau menjalankan perintah yang butuh proyek di CWD.
- Fakta kunci (cross-check ≥3 sumber, R47/R48):
  - `cli_presets.py:93` → `{"name":"crewai","binary":"crewai","install": _pip("crewai")}` — preset memang punya install string `pip install crewai` (paket ADA & RESMI, bukan `NO_INSTALL`).
  - `cli_presets.py:205-215` → `"crewai": LaunchSupport(LAUNCH_UNSUPPORTED, REASON_NOT_A_CLI)` — aigate menandai crewai BUKAN CLI yang bisa di-launch (komentar asli: console script exists, but it is a framework project scaffolder/runner; `crewai run`/`chat` run the Crew/Flow DEFINED BY THE PROJECT in CWD; neither takes model/base-url/prompt at launch; in empty dir both error out).
  - PyPI `crewai` v1.15.20: metadata wheel `entry_points.txt` punya `[console_scripts] crewai = crewai_cli.cli:crewai` → `pip install` MENGHASILKAN biner `crewai` di PATH (install VALID) — TAPI biner itu scaffolder/runner framework, bukan chat assistant; `requires_python ">=3.10,<3.14"`.
  - Docs resmi (docs.crewai.com Quickstart + github.com/crewAIInc/crewAI): perintah `crewai create flow / install / run / chat / login / deploy` beroperasi pada PROYEK di CWD; `crewai chat`/`run` membaca config crew di direktori tersebut dan TIDAK menerima argumen model/base-url/prompt di launch. Konfigurasi LLM (OpenAI-compatible) ditulis di kode proyek atau env `OPENAI_API_KEY`/`OPENAI_API_BASE_URL` — BUKAN surface CLI. Tidak ada biner chat interaktif generik untuk di-wire ke aigate `/v1/chat/completions`.
- Verifikasi: `bash -n scripts/cli-tools/crewai.sh` → clean; mode `-rwx------` (exec `100755`); eksekusi langsung → `exit 0`, TIDAK memasang apa pun.

### `scripts/cli-tools/llm.sh` (BARU) — **C1 llm = OpenAI-compatible (verified)**
- Install + launch script untuk **llm** (C1). Install idempoten via `ensure_installed` → `pip install llm` (fakta `cli_presets.py:100` = `_pip("llm")` → `pip install llm`).
- Launch **OpenAI-compatible** — llm bicara Chat Completions ke aigate (`/v1/chat/completions`). Wiring TEPAT mirip `_llm_builder` (`cli_tools_router.py:570-592`): `llm openai endpoint <base> [-m <model>] --key <key> --chat` (atau `--models` bila tanpa model) → `/v1/chat/completions`; env `OPENAI_API_BASE`+`OPENAI_API_KEY` di-inject dari `load_gateway_config`.
- Fakta kunci (cross-check): llm = `LAUNCH_VERIFIED` (`cli_presets.py:219`); builder `_llm_builder` (`cli_tools_router.py:570-592`). PyPI `llm` 0.35 (simonw), `requires_python >=3.10`.
- Catatan Termux (known-broken, bukan blocker): di Termux/aarch64 + Python 3.14, `pip install llm` gagal build `jiter` (tidak ada wheel Android, butuh `pkg install rust`) → install bisa gagal di perangkat ini; script tetap memasang, tool bisa jadi tidak bisa dijalankan.
- Verifikasi: `bash -n scripts/cli-tools/llm.sh` → clean; mode `-rwx------` (exec).

### `scripts/cli-tools/sgpt.sh` (BARU) — **C2 sgpt = NO_INSTALL (message + exit 0, no side-effect)**
- TIDAK memasang apa pun (sesuai keputusan user utk tool `NO_INSTALL`): script HANYA menampilkan pesan `sgpt: NO_INSTALL — belum ada install terverifikasi di environment ini.` + `exit 0` — TIDAK memasang apa pun (no side-effect, idempoten).
- Pesan literal (TIDAK ada command-substitution/backtick — lesson dari B2 swe-agent): `sgpt: NO_INSTALL — belum ada install terverifikasi di environment ini.`
- Fakta kode (cross-check):
  - `cli_presets.py:101` → `{"name":"sgpt","binary":"sgpt","install": NO_INSTALL}` (NO_INSTALL = echo no-op).
  - `cli_presets.py:224` → `"sgpt": LaunchSupport(LAUNCH_UNSUPPORTED, REASON_INSTALL_UNVERIFIED)` — aigate menandai sgpt BUKAN CLI yang bisa di-launch (install tidak terverifikasi).
  - `TERMUX_INSTALL` map (`cli_presets.py:241-244`) HANYA berisi `aichat` + `codex` — TIDAK ada entry sgpt → di Termux pun tak ada rute install terverifikasi.
  - Catatan registry: npm `sgpt` = **squat** tak terkait (author `peidayu`, deskripsi kosong, 218 byte — BUKAN CLI); PyPI `sgpt` = **404** (tidak ada package, `pip install sgpt` gagal); GitHub CLI chat sungguhan `tbckr/sgpt` (Go) TIDAK punya build Termux/android-arm64 terverifikasi → TIDAK ada install terverifikasi di env ini.
- Verifikasi PM: `bash -n scripts/cli-tools/sgpt.sh` → clean; mode `-rwx------` (exec); eksekusi langsung → `exit 0`, TIDAK memasang apa pun.

### `scripts/cli-tools/mods.sh` (BARU) — **C3 mods = NO_INSTALL (message + exit 0, no side-effect)**
- TIDAK memasang apa pun (sesuai keputusan user utk tool `NO_INSTALL`): script HANYA menampilkan pesan `mods: NO_INSTALL — belum ada install terverifikasi di environment ini.` + `exit 0` — TIDAK memasang apa pun (no side-effect, idempoten).
- Pesan literal (TIDAK ada command-substitution/backtick — lesson dari B2 swe-agent): `mods: NO_INSTALL — belum ada install terverifikasi di environment ini.`
- Fakta kode (cross-check):
  - `cli_presets.py:102` → `{"name":"mods","binary":"mods","install": NO_INSTALL}` (NO_INSTALL = echo no-op).
  - `cli_presets.py:225` → `"mods": LaunchSupport(LAUNCH_UNSUPPORTED, REASON_NO_BINARY)` — aigate menandai mods BUKAN CLI yang bisa di-launch (biner `mods` TIDAK ada / no binary).
  - `TERMUX_INSTALL` map (`cli_presets.py:241-244`) HANYA berisi `aichat` + `codex` — TIDAK ada entry mods → di Termux pun tak ada rute install terverifikasi.
  - Catatan registry: npm `mods` = **squat Node.js** tak terkait (BUKAN CLI `charmbracelet/mods`); PyPI `mods` = **404** (tidak ada package); GitHub CLI resmi `charmbracelet/mods` (Go) di-archive/sunset 2026-03-09 & binari resmi HANYA Linux/macOS/Windows — TIDAK ada build Termux/android-arm64 terverifikasi → TIDAK ada install terverifikasi di env ini.
- Verifikasi PM: `bash -n scripts/cli-tools/mods.sh` → clean; mode `-rwx------` (exec); eksekusi langsung → `exit 0`, TIDAK memasang apa pun.

### `scripts/cli-tools/oterm.sh` (BARU) — **C4 oterm = OpenAI-compatible (verified)**
- Install + launch script untuk **oterm** (C4). Install idempoten via `ensure_installed` → `pip install oterm` (fakta `cli_presets.py:103` = `_pip("oterm")` → `pip install oterm`).
- Launch **OpenAI-compatible** — oterm bicara Chat Completions ke aigate (`/v1/chat/completions`). Wiring TEPAT mirip `_oterm_builder` (`cli_tools_router.py:891-917`): tulis config `.oterm-aigate/config.json` blok `openaiCompatible.aigate` `{base_url=<gateway>/v1/chat/completions, api_key="${OPENAI_API_KEY}"}`, set `OTERM_DATA_DIR=.oterm-aigate` + env `OPENAI_API_BASE`+`OPENAI_API_KEY` (dari `load_gateway_config`).
- Fakta kunci (cross-check): oterm = `LAUNCH_VERIFIED` (`cli_presets.py:222`); builder `_oterm_builder` (`cli_tools_router.py:891-917`). PyPI `oterm` 0.24.0 butuh Python >=3.10.
- Catatan Termux (known-broken, bukan blocker): di Termux/aarch64 + Python 3.14, `pip install oterm` diprediksi gagal build `jiter` (tidak ada wheel Android) → script handle hint + `exit 1` (TIDAK memasang, pesan jelas).
- Verifikasi PM (R14/R35): `bash -n scripts/cli-tools/oterm.sh` → clean; mode `-rwx------` (exec); commit `aea87c3`.

### `scripts/cli-tools/gptme.sh` (BARU) — **C5 gptme = OpenAI-compatible (verified)**
- Install + launch script untuk **gptme** (C5). Install idempoten via `ensure_installed` → `pip install gptme` (fakta `cli_presets.py:104` = `_pip("gptme")` → `pip install gptme`).
- Launch **OpenAI-compatible** — gptme bicara Chat Completions ke aigate (`/v1/chat/completions`). Wiring: env `OPENAI_BASE_URL` (= gateway base; PENTING: gptme membaca `OPENAI_BASE_URL` BUKAN `OPENAI_API_BASE`) + `OPENAI_API_KEY` (dari `load_gateway_config`) + flag `-m local/<model>` ke `/v1/chat/completions`.
- Fakta kunci (cross-check): gptme = `LAUNCH_VERIFIED` (`cli_presets.py:223`); builder `_gptme_builder` (`cli_tools_router.py:595-612`). PyPI `gptme` 0.33.0 butuh Python `>=3.10,<3.15`.
- Catatan Termux (known-broken, bukan blocker): di Termux/aarch64 + Python 3.14, `pip install gptme` diprediksi gagal build `jiter` (tidak ada wheel Android) → script handle hint + `exit 1` (TIDAK memasang, pesan jelas).
- Verifikasi PM (R14/R35): `bash -n scripts/cli-tools/gptme.sh` → clean; mode `-rwx------` (exec); commit `16d36f9`.

### `scripts/cli-tools/aichat.sh` (BARU) — **C6 aichat = OpenAI-compatible (verified)**
- Install + launch script untuk **aichat** (C6). Install via `TERMUX_INSTALL` → `pkg install aichat` (fakta `cli_presets.py:242` = `TERMUX_INSTALL["aichat"]="pkg install aichat"`, "verified 0.30.0 runs" di Termux) dengan fallback `cargo install aichat` (fakta `cli_presets.py:105` = `_cargo("aichat")` → `cargo install aichat`). crates.io `aichat` 0.30.0 (Rust).
- Launch **OpenAI-compatible** — aichat bicara Chat Completions ke aigate (`/v1/chat/completions`). Wiring TEPAT mirip `_aichat_builder` (`cli_tools_router.py:469-511`): generate config `aichat-aigate.yaml` (client `aigate` openai-compatible, `api_base`=gateway, `api_key`), set env `AICHAT_CONFIG_FILE` + model `aigate:<raw>` ke `/v1/chat/completions`.
- Fakta kunci (cross-check): aichat = `LAUNCH_VERIFIED` (`cli_presets.py:226`); builder `_aichat_builder` (`cli_tools_router.py:469-511`). crates.io `aichat` 0.30.0 (Rust).
- Catatan Termux (terbukti WORKING, bukan blocker): `pkg install aichat` di Termux terbukti jalan (usable di Termux, "verified 0.30.0 runs") — rute install resmi via `pkg` (override `TERMUX_INSTALL`), fallback `cargo` kalau pkg tidak ada.
- Verifikasi PM (R14/R35): `bash -n scripts/cli-tools/aichat.sh` → clean; mode `-rwx------` (exec); commit `1c4e592`.

Status: **B4 autogpt = done (script, NO_INSTALL — message + exit 0, no side-effect).** A1 claude = done (script). A2 opencode = done (script). A3 gemini = done (script, native Google mode, unsupported by aigate). **A4 codex = done (script, native OpenAI mode, unsupported by aigate — butuh streaming Responses API yang belum ada).** **A5 antigravity = done (script, NO_INSTALL — message + exit 0, no side-effect).** **A6 phi = done (script, NO_INSTALL — message + exit 0, no side-effect).** **A7 aider = done (script, OpenAI-compatible via aigate `/v1/chat/completions`, verified — `LAUNCH_VERIFIED` at `cli_presets.py:172`).** **A8 goose = done (script, NO_INSTALL — message + exit 0, no side-effect).** **A9 amp = done (script, NO_INSTALL — message + exit 0, no side-effect).** **A10 qwen = done (script, OpenAI-compatible via aigate `/v1/chat/completions`, verified — `LAUNCH_VERIFIED` at `cli_presets.py:181`).** **A11 cline = done (script, OpenAI-compatible via aigate `/v1/chat/completions`, verified — `LAUNCH_VERIFIED` at `cli_presets.py:182`; install `npm i -g cline` + wiring `cline auth --provider openai-native --apikey --modelid --baseurl` + env `OPENAI_API_BASE`/`OPENAI_API_KEY`; npm `cline@3.0.61` gak punya variant android binary → known-broken di Termux, bukan blocker).** **A12 kilo = done (script, OpenAI-compatible via aigate `/v1/chat/completions`, verified — `LAUNCH_VERIFIED` at `cli_presets.py:183`; install `npm i -g @kilocode/cli` + wiring trusted config `KILO_CONFIG`=`.kilo/aigate-kilo.json` (provider `aigate` via `@ai-sdk/openai-compatible`, `apiKey`=`{env:OPENAI_API_KEY}` → secret TIDAK ke disk) + env `OPENAI_API_BASE`/`OPENAI_API_KEY` + flag `-m aigate/<model>`; npm `@kilocode/cli@7.5.16` gak punya variant android binary → known-broken di Termux, bukan blocker).** `_common.sh` = done. **B1 openhands = done (script, OpenAI-compatible via aigate `/v1/chat/completions`, verified — `LAUNCH_VERIFIED` at `cli_presets.py:190`; install uv→fallback pip `pip install openhands` + wiring `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL=openai/<model>` + flag `--override-with-envs`; PyPI `openhands` v1.16.0 butuh Python 3.12 → known-broken di 3.13+, bukan blocker).** **GRUP A SELESAI (12/12); GRUP B SELESAI (6/6): B1 openhands, B2 swe-agent, B3 open-interpreter, B4 autogpt, B5 gpt-researcher, B6 crewai; C1 llm = done (script, OpenAI-compatible via aigate `/v1/chat/completions`, verified — `LAUNCH_VERIFIED` at `cli_presets.py:219`).** (Progress keseluruhan cli-tools: **19/24**.)


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

## 2026-09-09 — fix 4 bug cli-tools (aichat/codex/oterm) — DONE

### Perubahan (scripts/cli-tools/)
- `aichat.sh:118` — `INSTALL_CMD=(pkg install aichat)` → `(pkg install -y aichat)` (hindari prompt konfirmasi `pkg` di shell non-interaktif yang abort).
- `aichat.sh:207` — `exec AICHAT_CONFIG_FILE=$AICHAT_CONFIG_FILE $BIN $@` (assignment di-quote utuh) → `export AICHAT_CONFIG_FILE` lalu `exec $BIN $@`. Old form: bash anggap assignment itu nama command → 'command not found' (exit 127). Var sudah di-set sejak line 124, export aman.
- `codex.sh:71` — `INSTALL_CMD=(pkg install codex)` → `(pkg install -y codex)` (tambah -y).
- `oterm.sh:175` — `exec OTERM_DATA_DIR=$OTERM_DATA_DIR $BIN $@` → `export OTERM_DATA_DIR` lalu `exec $BIN $@`. Kelas bug sama dgn aichat; `OTERM_DATA_DIR` sudah di-set di line 117 (.oterm-aigate), export aman.

### Verifikasi
- `bash -n` ketiga file → SYNTAX OK (clean).
- Re-test aichat (bukti exec fix): folder terisolasi `~/aichat-retest`, `bash .../aichat.sh --help` → `already installed: aichat` (skip install idempoten) → tulis `aichat-aigate.yaml` → `exec aichat --help` cetak usage → EXIT_CODE=0. Tanpa fix, exec lama gagal exit 127.
- codex/oterm: `bash -n` OK + pola `export VAR; exec $BIN` benar. Dynamic launch penuh TIDAK diverifikasi di Termux (codex butuh Google key/REPL; oterm pip native build gagal — by design, BUKAN bug).
- Cleanup: `rm -rf ~/aichat-retest` OK; `pkg uninstall -y aichat` gagal (exit 100) krn env read-only `/etc/apt` (upgrade hope2333-mirrorlist) — di luar script; binary aichat sdh hilang dari PATH.

### Catatan env (di luar repo, BUKAN bug script)
- `pkg` di env ini gagal tulis `/etc/apt` (Read-only file system) saat upgrade hope2333-mirrorlist → dpkg abort (exit 100) baik saat install maupun uninstall aichat. Tidak memengaruhi logika script.

Commit: `61d64337b686a8b5ee0f58d17d52807119922d0a`

## 2026-09-10 — perapian governance: rule v2 + kanal wajib-baca + gate (BUKAN kode produk) — DONE

### Perubahan (config & dokumen, nol `src/**` / `tests/**`)
- `documents/pm/archive/OPERATING_RULES-v1-52rules.md` — rename (git mv) dari `documents/pm/OPERATING_RULES.md`; teks v1 52 rule utuh 52.698 B.
- `documents/pm/OPERATING_RULES.md` — BARU v2: 50 rule / 10 tema A–J / 11.463 B (−78%). 8 rule duplikat dihapus dari sini (rumah tunggal `.opencode/rules/*`), sisanya ≤4 baris + sitatan `[R#]`. F4 ditambahkan (klaim ukuran wajib sebut alat+satuan).
- `AGENTS.md` — ditulis ulang: 4 ayat routing dipertahankan + blok "ALWAYS-ON RULES" 12 baris (pointer tema) + rujukan gate + aturan bahasa. 1.866 → 3.896 B (kanal auto-inject tiap sesi).
- `opencode.json` — += `"instructions": ["documents/pm/OPERATING_RULES.md"]` (kanal injeksi rule; skema diverifikasi ke https://opencode.ai/config.json → `Config.instructions: [string]`).
- `.opencode/rules/agent-boundaries.md` — PM WRITE += `.opencode/rules/**` (grant user 2026-09-10) + `pm-orchestration/**` + `AGENTS.md`; subseksi "Task reports" (K2: pelaksana tulis laporannya sendiri); baris `tech-architect` dipindah ke dalam tabel (sebelumnya tabel pecah).
- `.opencode/rules/{secrets,no-hallucination,commands,task-report,language}.md` — serap clause dari rule lama (R51/R47/R7/R23/R52).
- `.opencode/skills/pm-orchestration/SKILL.md` — §6 "Record Protocol" ditulis (dulu `ProjectManager.md:30` menunjuk skill `pm-postmortem` yang TIDAK ADA → pointer hantu).
- `.opencode/agents/ProjectManager.md` — pointer hantu dibetulkan: `pm-postmortem` → Record Protocol §6; `fullstack-skill` → `fullstack-dev-skill`; `docs/*` → `documents/*`.
- 39 baris rujukan `pm/...` dan `docs/...` di 15 berkas hidup → `documents/pm/...` / `documents/...`. Berkas laporan lama (`.opencode/reports/**`) TIDAK disentuh (provenance).
- `.opencode/tools/governance/rules-index.py` — BARU, gate 11 pemeriksaan (stdlib only).
- `documents/analysis/2026-09-10-rules-consolidation.md` — desain (tulisan system-analyst, bukan PM).

### Verifikasi
- `python3 .opencode/tools/governance/rules-index.py` → **LOLOS**, exit 0; 11 PASS (index 50 rule/10 tema; coverage mapped=52 unique=52 dup=[]; range R1..R52 tanpa celah; size 11.463 ≤ 20.480; themes 10 ≤ 10; rule_lines tidak ada >4; archive 52 rule/52.698 B; live_paths tidak ada rusak; no_stale_refs tidak ada `pm/` basi; citations_resolve 52 sitatan terselesaikan semua).
- `python3 .opencode/tools/governance/rules-index.py --json` → valid (keys: rules/themes/totals/checks/report_format_debt).
- `python3 -m py_compile .opencode/tools/governance/rules-index.py` → OK; `__pycache__` dihapus lagi (B5).
- `python3 -m json.tool opencode.json` → valid; `instructions` terbaca.
- `git diff --cached --check` bersih di tiap commit; tidak ada berkas `src/**`/`tests/**` yang berubah; `.env` tetap tak ter-track.
- Sisa utang TERBUKT (bukan gagal, dicatat): 14 berkas laporan tidak sesuai pola `[yyyymmdd]/[jenis]/[hhmm]_*.md` (K10); Graphify belum terpasang → C4 berkondisi; `documents/pm/**` belum dipindah (langkah ⑥).

### Catatan
Bukti "kode lama masih aktif" tidak berlaku: tidak ada proses produk yang disentuh. Perubahan config agen baru terasa setelah **user restart opencode** (aturan: config dimuat sekali saat start).

## 2026-09-10 — langkah ⑥+⑧: pindah berkas `documents/pm/**` + normalisasi folder laporan — DONE

### Pindah (semua `git mv`, isi tidak diubah)
- `documents/pm/cli-tools-install-backlog.md` → `documents/plan/cli-tools-install-backlog.md`
- `documents/pm/wiki-plan.md` → `documents/plan/wiki-plan.md` · `documents/pm/wiki-backlog.md` → `documents/plan/wiki-backlog.md`
- `documents/pm/cli-tools-compatibility.md` → `documents/config/cli-tools-compatibility.md`
- 4 handover root `documents/pm/handover-*.md` → `documents/pm/handovers/` (jadi 9 berkas satu folder)
- `documents/pm/status.md` 202.175 B → 11.018 B aktif; entri lama 191.477 B → `documents/pm/archive/status-2026-09-03_sampai_2026-09-08.md`
- `documents/pm/memory-bank.md` 51.882 B → 21.896 B aktif; Progress lama 25.740 B → `archive/memory-bank-progress-lama.md`; heading `## Decisions (arsip lama)` 4.660 B → `archive/memory-bank-decisions-lama.md` ( heading dobel 3x jadi 1 aktif + 1 penunjuk)
- Rujukan hidup ikut dibetulkan: `business-analyst.md:11`, `documents/plan/wiki-plan.md:4,100`, `documents/plan/wiki-backlog.md:4`, `memory-bank.md:423-424`, `state.md:8,15`. Histori (`CODE_CHANGES.md:139`, entri `status.md` lama) sengaja TIDAK ditulis ulang.

### Normalisasi laporan (⑧)
- `.opencode/reports/2026-09-03/{build,plan,qa,revise-docs,setup}/` → `.opencode/reports/20260903/…` (11 berkas `git mv`)
- `20260903/docs/revise_native_run.md` → `0627_revise_native_run.md` (waktu dari add-commit `92106bb` 06:27; isi dokumen tulis 07:00 — selisih dicatat)
- root `.opencode/reports/qa_anthropic_inbound_verification.md` → `20260909/qa/0718_qa_anthropic_inbound_verification.md` (waktu add-commit `41d24f8`; dokumen tidak memuat jam)
- Duplikat identik dihapus: `2026-09-03/qa/2026-09-03_b4_3_qa.md` == `qa/1350_b4_3_qa.md` (diff byte-identik; satu tetap tinggal)
- `task-report.md` diperbaiki: klausul "folder lama dibekukan" → "folder dinormalisasi `git mv`, asal jam tercatat"

### Verifikasi
- Total byte terpelihara: status 202.175 → 11.018 + 191.477 = 202.495 (+320 B header arsip). memory-bank 51.882 → 21.896 + 25.740 + 4.660 = 52.296 (+414 B header arsip).
- `git ls-files .opencode/reports` = 28 berkas; `git status` = 13 R + 1 D, nol isi berubah.
- `grep` sitatan path laporan lama di berkas ter-track = 0 (tidak ada rujukan putus).
- Gate: `python3 .opencode/tools/governance/rules-index.py` → LOLOS; utang format laporan **0** (sebelumnya 14).
- `documents/pm/` akhir: 8 entri (`OPERATING_RULES.md`, `state.md`, `status.md`, `memory-bank.md`, `bugs.md`, `handovers/`, `wiki-drafts/`, `archive/`) — `wiki-drafts/` TIDAK disentuh (R44 ayat 8 staging wajib).

## 2026-09-10 — langkah (e): coba pasang Graphify di Termux → DIBLOKIR environment — BLOCKED (bukan DONE)

### Yang dipasang (semua DI LUAR repo — nol berkas proyek berubah)
- `pkg install -y python-numpy tree-sitter` → `numpy 2.4.4` OK, CLI `tree-sitter 0.26.13` OK.
  (dpkg tetap error di paket tak terkait `hope2333-mirrorlist` = read-only /etc/apt, sudah tercatat di memory-bank.)
- venv terisolasi `~/tmp/graphify-venv` (`--system-site-packages` biar numpy kepakai) →
  `pip install tree-sitter>=0.23,<0.26 networkx rapidfuzz` → ketiganya import OK.
- `pip install --no-deps graphifyy` → **0.9.57** terpasang; entry `graphify` + `graphify-mcp` ADA;
  `graphify --help` → exit 0 (perintah: install/uninstall/path/explain/update/cluster-only/watch/clone/merge-*).

### Uji nyata (bukti, bukan asumsi)
- Fixture `~/tmp/grf-test/mod.py` (1 file .py) → `graphify update` exit 0 TAPI:
  `warning: 1 .py file(s) contributed nothing to the graph because a dependency is missing:
  tree_sitter_python not installed. (#1745)` → hasil **0 nodes / 0 edges / 0 communities**.
- Sebab: binding Python grammar gagal dimuat di Android/Termux:
  `ImportError: dlopen failed: cannot locate symbol
   "tree_sitter_python_external_scanner_create" ... _binding.abi3.so`
- Sudah dicoba: `tree-sitter-python` versi apa adanya (0.25.0) dan dipin `<0.26` (force-reinstall) → SAMA.
  Tersedia di Termux hanya grammar level-C (`tree-sitter-python`, `-javascript`, dst.) bukan binding Python-nya.
- Konsekuensi: untuk repo ini (Python 334 file + JS frontend) Graphify menghasilkan graf KOSONG → tidak bisa
  jadi kanal pencarian kode di HP ini sekarang.

### Versi terverifikasi identitas tool (2 sumber, sesuai F3)
- PyPI `graphifyy` 0.9.57, `requires_python >=3.10` (BUKAN 3.12 kaku seperti tertulis di graphify.net).
- GitHub `Graphify-Labs/graphify` → API: **Apache-2.0**, default branch `v8`; situs claiming **MIT** dan
  "3.7k+ stars". Dua angka di situs TIDAK cocok dengan API (API: Apache-2.0). Kalau nanti dipakai,
  cek ulang lisensinya sebelum masuk daftar pihak ketiga (`THIRD_PARTY_NOTICES.md`).

### Keputusan
- `OPERATING_RULES.md` C4 tetap **berkondisi** ("kanal graf hanya wajib bila terpasang"). Tidak menulis
  rule yang belum benar. R28 lama tetap arsip/mati.
- venv percobaan DIHAPUS (B5): `rm -rf ~/tmp/graphify-venv ~/tmp/grf-test`.
- Jalan yang tersisa (butuh keputusan user): (i) generate `graph.json` di mesin Linux/x86 lalu query
  lokal di HP (`graphify path/explain --graph <file>` jalan tanpa LLM/tanpa grammar),
  (ii) tetap tanpa graf (C4 berkondisi), (iii) coba build binding grammar lebih dalam (tidak dijamin).

## 2026-09-10 — Banner tujuan halaman (fitur `banner-halaman`, fe-dev, commit ini)
- `src/frontend/static/index.html` (+40): 8 blok `.page-banner` jadi anak pertama 8 view —
  settings :175, providers :280, combos :417, proxies :449, endpoints :481, usage :514,
  analytics :611, cli :792. welcome+terminal BERSIH (verifikasi per-section, bukan asumsi).
  fallback inline = teks EN (konvensi berkas). Ikon `fa-circle-info` — ada di FA 6.5.1 yang
  sudah dimuat (index.html:42; bukti: unduh + grep `fa-circle-info:before`).
- `src/frontend/static/styles.css` (+43, di :458–490): satu set `.page-banner` — flex, ikon
  `--accent`, kartu token (`--panel/--panel-border/--radius/--shadow/--fg`), none-fixed,
  @media 600px stack. Cahah/gelap otomatis (cuma variabel).
- `src/frontend/static/i18n/{en,id,ru,nl,ja,zh,zh-tw}.js` (+9/−1 per berkas): 8 kunci baru
  `page_desc.{settings,providers,combos,proxies,endpoints,usage,analytics,cli}` SERENTAK di 7
  kamus → 56 entri, tiap kamus 400 kunci, parity guard i18n.test.js lolos (35 tes).
  id = draf user-ACC verbatim; 6 bahasa lain = draf terjemahan (BELUM ditinjau penutur asli).
- Nol perubahan JS app (app.js dkk). Gate PM: vitest penuh 23 berkas/523 tes HIJAU (10,21 s,
  = baseline, 0 regresi) + render-check jsdom (applyLocale asli + kamus asli): 7/7 locale,
  8/8 banner terisi, welcome+terminal nihil → LULUS. Browser nyata TIDAK tersedia di Termux
  (playwright crash, tanpa biner) → visual masih butuh mata user sendiri. Laporan:
  `.opencode/reports/20260910/implementation/0405_banner-halaman-implementasi.md`.

## 2026-09-10 — Gerbang backend multi-akun 9router: review a237414 + tes (fitur `multiakun-9router`, peran be-dev in-session, commit 03d9b6e)
- `src/backend/oauth.py` (+20/−7): SKIP kredensial kosong — defect review: kontrak "skip yang
  unavailable" belum menangkap `api_key=""` (diteruskan mentah upstream). Jalur pin: kredensial
  kosong → log + fallback strategi (bukan return ""); jalur strategi: kandidat kosong → lanjut.
  Sekalian hapus variabel `account_id` ganda di pin (return langsung `pinned.id`). Docstring
  langkah-5 diperbarui. Bukti: oauth.py:404-419 (pin), :442-456 (strategi).
- `tests/backend/test_account_routing.py` BARUS (28 tes): mesin fill-first (prioritas asc, id asc
  tie-break, skip raise/kosong, fallback legacy, enum tak dikenal=fail-safe), round-robin STICKY
  (default 3; limit DARI KOLOM: 1/2; clamp 0→1; matriks clamp_sticky_limit; last_used_at persist;
  urutan bertahan restart; kandidat gagal tidak makan streak), pin x-connection-id (menang atas
  2 strategi; unknown/disabled/asing/token-gagal → fallback tanpa error; wrapper meneruskan pin;
  resolve_target → ResolvedTarget.account_id), parsing header (absen/kosong/non-int/valid), DTO
  rute provider/account (+validasi 400 invalid_fallback_strategy, clamp di PUT, PUT priority,
  404 account_not_found, urutan list), migrasi self-heal idempoten 2× pada DB skema-lama dengan
  default mendarat di baris lama.
- Gate: suite penuh `python3 -m pytest tests/backend -q` = 526 passed, 1 skipped, 0 failed (40,63 s).
  Laporan: `.opencode/reports/20260910/qa/1351_backend-gate-multiakun-9router.md` (+kontrak tahap-1).

## 2026-09-10 — Pembersihan 4 merah PRE-EXISTING suite cli-tools (fitur terpisah `cli-tools-preexisting-red`, commit f986d51)
- Bukti pre-existing: 4 gagal terulang IDENTIK di baseline c3a2241 (a237414~1, worktree terpisah)
  → bukan regresi WIP; milik pekerjaan anthropic-inbound/cli-compat yang lalu.
- `src/backend/cli_compat.py` (+9/−2): `except Exception: pass` di current_platform melanggar R12
  (ketahuan guard AST test_logging) → debug-log stdlib `logging` + `import logging` (modul tetap
  framework-free by design, TIDAK import backend.log).
- `src/backend/cli_tools_router.py` (+30): `_claude_builder` BARUS + registrasi `"claude"` —
  resolve in-app hanya inject OPENAI_* yang DIABAIKAN claude-code (gap nyata, ketahuan guard
  test_every_verified_preset). Form = meniru scripts/cli-tools/claude.sh:64-83 (terbukti jalan):
  ANTHROPIC_BASE_URL=root gateway (strip trailing slash + suffix /v1; CLI menambah /v1/messages
  sendiri) + ANTHROPIC_API_KEY + ANTHROPIC_MODEL/--model opsional; prefix env per-perintah (pola
  _openhands_builder), tidak persist config. Masking key di log tetap (replace ctx.key).
- `tests/backend/test_cli_tools.py` (+32/−2): ToolDTO += kunci `compat` (ditambah katalog 36b71ad);
  claude `("verified","")` (bukan unsupported/anthropic_only — flip sengaja pekerjaan inbound);
  hapus kasus param claude basi (refusal tetap dicakup codex/antigravity/gpt-researcher/crewai);
  + unit test `_claude_builder` (root-strip /v1, model-absen).
- Diverifikasi: test_cli_tools+test_logging hijau; suite penuh hijau (di atas). BELUM di-exercise:
  spawn claude-code sungguhan via terminal in-app (butuh biner + PTY live) — jujur di laporan.

## 2026-09-11 — UI strategi multi-akun TAHAP 2 (fe-dev; branch refactor/ui, BELUM push)

**Asal:** ACC user ("1") atas tahap-2 fitur adopsi 9router. Kontrak =
`.opencode/reports/20260910/qa/1351_backend-gate-multiakun-9router.md` §KONTRAK.
Eksekutor: `fe-dev` (Task tool, 2 putaran). Laporan:
`.opencode/reports/20260911/implementation/0633_ui-multiakun-tahap2-implementasi.md`.
Batas lingkup dijaga: **nol `src/backend/**`, nol `combos.js`** (keputusan user terkunci).

### Perubahan (14 berkas `src/frontend/**`)
- `static/index.html` (+155/−125): kartu detail provider dibersihkan (:311-328) — `#provDiscoverBtn`,
  `#provModelMsg`, `#provModelsTable`/`#provModelsBody`, dan subseksi akun DIHAPUS dari kartu;
  `#provModal` jadi ber-tab (tablist `#provTabList` :797, panel Provider + panel Akun :888-927,
  kontrol baru `#provStrategy`/`#provStickyRow`/`#provStickyLimit`, `#accPriority` :918-919,
  hint `#provTabHint`); Cancel keluar dari `<form>`; cache-buster `styles.css?v=20260914→20260915`.
- `static/app.js` (+266/−39): tab ARIA + roving tabindex + panah/Home/End (:858-960); `openAddModal` menonaktifkan
  tab Akun + hint (:962-981); `openEditModal` mengisi 2 field strategi, mengaktifkan tab Akun,
  memanggil discovery DIAM-DIAM (:983-1026); `saveProvider` mengirim `fallback_strategy` selalu dan
  `sticky_round_robin_limit` hanya saat `round-robin`, clamp ≥1/default 3 (:1073-1090);
  `openDetail(id, skipDiscover)` + `discoverModels(id,{quiet})` dengan penjaga balapan `discoverSeq`
  dan gagal senyap → `console.warn` (BUKAN `except: pass` — R12) (:1123-1198); `renderAccounts`
  += kolom Prioritas (input number, commit-on-change) + Terakhir dipakai (`never_used` bila null)
  (:1240-1323); `updateAccountPriority` = `PUT /api/accounts/{id}` body `{priority}` SAJA
  (:1327-1338); `addAccount` kirim `priority` default 0 (:1341-1383); sel Nama jadi tombol masuk
  detail `.prov-name-btn` (:786-808, pengganti aksi kebab `discover` yang dihapus); kebab = edit+delete.
- `static/styles.css` (+51): `.modal-tabs`, `.modal-tab`(+`is-active`/`aria-disabled`/`focus-visible`),
  `.prov-tabpanel[hidden]`, `.prov-name-btn`, `.acc-priority`, `.acc-never` (:1079-1131).
  **Nol warna hex baru** — semua token existing → mode gelap otomatis (dibuktikan `git diff | grep -c '#hex'` = 0).
- `static/i18n/{en,id,ru,nl,ja,zh,zh-tw}.js` (+11 @ 7): kunci baru `providers.tabs_label`,
  `providers.tab_provider`, `providers.tab_accounts`, `providers.strategy`,
  `providers.strategy_fill_first`, `providers.strategy_round_robin`, `providers.sticky_limit`,
  `accounts.priority`, `accounts.last_used`, `accounts.never_used`, `accounts.save_first`.
  Paritas 7/7: `i18n-parity-check.mjs zh` = 411 kunci, hilang 0, thừa 0.
- `tests/providers.test.js` (15→32 tes): muatan tablist, akun di panel modal, UI discovery hilang,
  enum select, kartu detail bersih, perilaku tab (klik + panah/Home/End + wrap), `saveProvider`
  (+2 field, omit saat fill-first, clamp), `openEditModal` memanggil `/discover` senyap tanpa
  pesan/tabel + gagal senyap tak mem-block, limit sticky tersembunyi saat fill-first, balapan
  respons basi, `discoverModels` legacy tetap dipertahankan.
- `tests/accounts.test.js` (8→17 tes): DTO += priority/last_used_at; kolom baru + colspan 6;
  PUT `{priority}` saja (tanpa `last_used_at`) + muat ulang; no-op tidak mengirim PUT; 404 inline;
  POST menyertakan `priority`.
- `tests/row-actions.test.js`: kebab kini `["edit","delete"]` + assert tombol nama.
- `e2e/b5_features.mjs` (tindak lanjut, DIDELEGASIKAN ULANG karena `fe-dev` melaporkan sendiri
  terpengaruh): jalur B5.1 ditulis ulang ke UI baru — detail via `.prov-name-btn.js-prov-detail`,
  akun via kebab `edit` → `#provModal` → `#provTabAccounts` → `#provPanelAccounts`, plus assert
  `#accPriority` (number, min 0) + `.acc-priority` per baris; komentar alur :13-19 diperbarui.
  `node --check` exit 0. `android.mjs`/`smoke.spec.js` terverifikasi tidak terpengaruh (level API).

### Gate PM (mandiri, bukan klaim sub-agent)
`node node_modules/.bin/vitest run` = **23 berkas / 547 tes LOLOS** (baseline 523 → +24);
`git diff --check` bersih; `git status --short` = 14 berkas semuanya `src/frontend/**`;
rujukan `provModelsTable|provDiscoverBtn|provModelsBody` di `static/**` = 0; banner
`page_desc.providers` utuh; `node --check` app.js + b5_features.mjs exit 0.

### Insiden lingkup (dilaporkan jujur oleh fe-dev, diverifikasi PM)
Satu suntingan sempat menyentuh komentar `static/app.js` (3 baris non-fungsional) di luar batas
"HANYA e2e" → dibatalkan ke teks persis tergates; PM memverifikasi ulang `node --check` + vitest
547 hijau. Nol dampak fungsional.

### Yang TIDAK diubah (keputusan PM, dicatat di laporan)
4 kunci i18n lama jadi tak terpakai (`providers.discover`, `providers.no_models`,
`providers.model_id`, `providers.model_name`) → DITAHAN, tidak di-purge (endpoint `/discover` masih
dipanggil diam-diam; purging = riuh 7 berkas tanpa nilai tes). Boleh dicabut user.

### BELUM diverifikasi
Aplikasi nyata (butuh muat ulang server oleh user — J6, keputusan user) + uji mata papan ketik/tab
di HP (G3); Playwright belum dijalankan; terjemahan 6 bahasa belum ditinjau penutur;
commit belum di-push; PR #17 masih terbuka.

## 2026-09-11 — OPSI A halaman rinci penyedia (tahap-3 UI multiakun; commit `6ede872`, BELUM push)

**Asal:** user menilai tahap-2 berantakan → PM audit (6 titik, bukti di blok 20260911-0645) → rule **D6**
(lembar desain + ACC sebelum fe-dev) → user pilih "coba dulu opsi a" → ACC ditekan pada lembar desain →
`fe-dev` spawned (sesi `ses_f721dd91bffeZOiRtn33N0XqnF`, 1 putaran, tanpa blocker).
Lembar desain: `documents/pm/handovers/handover-20260911-opsi-a-halaman-rinci-penyedia.md`.
Laporan: `.opencode/reports/20260911/implementation/1100_ui-halaman-rinci-penyedia-tahap3.md`.
Batas lingkup dijaga: **nol `src/backend/**`, nol `combos.js`, nol `usage.js`** (Kartu D pakai id lama).

### Perubahan (17 berkas `src/frontend/**`, +1527/−1149)
- `static/index.html` (+256/−183): `#provDetail` lama DIHAPUS (:311); view BARU `.view.provider-detail
  [data-view="provider-detail"]` (:316-465) = kepala (`#provDetailBackBtn` :332, judul+badge, Ubah/Hapus
  :341-347) + Kartu A profil baca-saja `<dl>` (:352-389, status `#pdModelStatus` :388) + Kartu B strategi
  (`#pdStrategy` :400-404, `#pdStickyRow`/`#pdStickyLimit` :407-410, `#pdStrategySaveBtn` :412,
  `#pdStrategyMsg` :415) + Kartu C akun (`#pdAccAddBtn`/`#provConnectOAuthBtn`/`#pdAccReloadBtn`,
  `#accList` DIV :443 — tabel 6 kolom hilang) + Kartu D pemakaian (:446-465); `#provModal` jadi profil-only
  (:901-976); modal BARU `#accModal` (:978-1018); cache-buster `20260915→20260916`.
- `static/app.js` (+497/−314): `navViewFor` + sorot nav Penyedia TANPA entri nav baru (:78-88,162-174);
  `openDetail`/`loadProviderDetail`/`backToProviders` (:1032-1136); `saveProvider` TIDAK lagi mengirim
  field strategi (:985-1030); `saveStrategy` PUT HANYA 2 field routing + clamp ≥1 + 400 inline di kartunya
  (:1138-1186); discovery senyap + baris status + `discoverSeq` + gagal `console.warn` (R12) (:1190-1237);
  akun dirender KARTU (posisi 1..n, kunci polos ber-`title`, ▲▼ `aria-disabled` beralasan) (:1259-1364);
  `moveAccount` tukar → normalisasi `0..n-1` → PUT hanya yang berubah → selalu baca ulang server, PUT
  berurutan (:1366-1412); modal akun (:1438-1528); `wireProviderUi()` terpadu (:1607-1668); ekspor
  `window.aigate` dipangkas.
- `static/styles.css` (+142/−32): hapus `.modal-tabs/.modal-tab/.prov-tabpanel/.acc-priority/.acc-never/
  .providers-detail` (0 rujukan tersisa); halaman rinci :1083-1156; kartu akun :1158-1238 (sentuh ▲▼
  44px di ponsel); **tambalan bug lama** :511-515 `.form-row[hidden]{display:none}` (`display:flex` penulis
  mengalahkan `[hidden]` peramban → baris "hidden" sebelumnya masih tampil). NOL warna hex baru.
- `static/i18n/{en,id,ru,nl,ja,zh,zh-tw}.js`: 10 kunci mati dicabut (`providers.tab_*`,
  `providers.tabs_label`, `providers.strategy`, `providers.sticky_limit`, `accounts.priority`,
  `accounts.last_used`, `accounts.never_used`, `accounts.save_first`, `accounts.none`), 27 kunci baru
  (`providers.models_hint|models_failed` + `provider_detail.*`) → **428 kunci/kamus**, paritas 7/7 lolos.
- `tests/provider_detail.test.js` BARU (40 tes): 4 kartu, Kembali, ▲▼ (2 PUT pada daftar 0..n-1; semua-0;
  batas aria-disabled; gagal → pesan inline + baca ulang), Kartu B satu-satunya pemilik strategi,
  modal akun POST `priority`, kosong-state, Kartu D menunjuk `loadProviderUsage`, 10 kunci dicabut tak
  menggantung, "app.js tidak punya logika tab tersisa".
- `tests/providers.test.js` 32→27 (tab→"profil-only"), `tests/accounts.test.js` 17→18 (kartu, bukan tabel),
  `tests/views.test.js` 25→27 (view baru TANPA entri nav), `tests/row-actions.test.js` 4→5 (tooltip Model),
  `tests/usage.test.js` (1 tes retarget id). Tabel pemindahan tes lama→baru lengkap di laporan §6.
- `e2e/b5_features.mjs` (+71/−43): alur B5.1 = `.prov-name-btn` → halaman rinci → kepala → `#pdApiKey`
  polos → `#pdStrategy`+simpan → `#accList .acc-card` (assert tanpa tabel) → `#accModal` → Kembali.
  `node --check` OK; BELUM dijalankan (nol browser di Termux).

### Gate PM (mandiri)
`node node_modules/.bin/vitest run` = **24 berkas / 586 tes LOLOS** (sebelum 23/547);
`i18n-parity-check.mjs` 7/7 kode = 428 kunci, hilang 0 thừa 0 kosong 0; grep sisa tab di `static/**` = 0;
grep 4 kunci dicabut di 7 kamus = 0; `git status --short` = 17 berkas semua `src/frontend/**`;
0 hex baru; `git diff --check` bersih; `node --check` app.js + e2e OK; `rules-index.py` LOLOS.

### Keputusan fe-dev di luar acuan (semua diterima PM)
Prioritas akun baru = jumlah akun (append) — **koreksi defect nyata**: default 0 bikin akun baru melompati
antrean; `accounts.none` ikut dicabut; PUT berurutan (bukan serentak) agar urutan server pasti;
`stopOAuthPoll()` saat berpindah penyedia; permukaan `window.aigate` dipangkas.

### BELUM diverifikasi
Belum di-exercise di aplikasi nyata (G3) — user wajib muat ulang server (J6) + uji mata kartu/▲▼ di HP dan
mode gelap; Playwright belum jalan; terjemahan 6 bahasa belum ditinjau penutur; halaman rinci tanpa rute
URL (tidak bisa di-bookmark, back peramban tak berlaku — diterima di lembar desain); ahead 8, PR #17 open.

## 2026-09-11 — TAHAP 4: masuk halaman rinci lewat menu ⋮ "Akun alternatif/sekunder" (fe-dev; commit BELUM push)

**Asal:** user mencoba hasil tahap-3 → "aneh kalo tap/klik di namanya gitu, bikin menu baru aja dengan nama
alternatif/sekunder akun ... digabung dengan menu dari tombol tiga titik di ujung kanan aja". Bentuk, nama,
dan letak ditentukan USER → rule D6 terpenuhi oleh user sendiri (PM hanya kunci 4 default kecil).
Laporan: `.opencode/reports/20260911/implementation/1222_menu-kebab-akun-alternatif-tahap4.md`.

### Perubahan (13 berkas `src/frontend/**`, +63/−55)
- `static/app.js:793-798`: sel Nama kembali TEKS POLOS — `button.prov-name-btn.js-prov-detail` DIHAPUS;
  listener delegasi `data-detail-wired` (:809-822) ikut dihapus (tak terpakai); `openDetail(id)` tetap ada,
  kini dipanggil dari item menu.
- `static/app.js:812-822`: menu ⋮ penyedia = TIGA item berurutan `accounts` → `edit` → `delete`; item akun =
  label `providers.accounts_menu`, ikon `fa-users`, bukan bahaya. Infrastruktur menu (`rowMenuCellHtml` :732-738,
  `wireRowMenu` :740-749) TIDAK diubah → tetap satu tombol ⋮ per baris.
- `static/styles.css`: rule `.prov-name-btn` (+`hover`/`focus-visible`) DIHAPUS (dicek 0 pemakaian tersisa);
  0 rule baru; 0 warna hex baru; sel Nama kini konsisten dengan tabel kombo/pool/endpoint.
- `static/i18n/{en,id,ru,nl,ja,zh,zh-tw}.js`: +1 kunci `providers.accounts_menu` (ID "Akun alternatif/sekunder",
  EN "Alternative/secondary accounts") → 429 kunci/kamus.
- `static/index.html`: cache-buster `V` + `styles.css?v=` + `i18n.js?v=` + `app.js?v=` naik serentak → `20260917`
  (penjaga `tests/i18n.test.js:307-316` minta ketiganya sama).
- `tests/row-actions.test.js:26-57` (urutan 3 item + label + ikon + non-danger + Nama bukan tombol);
  `tests/provider_detail.test.js:175-190,800-806` (masuk via ⋮ + penjaga negatif "klik nama tidak navigasi" +
  alur penuh 6 langkah); `e2e/b5_features.mjs:13-14,145-153` (⋮ dulu → `[data-action="accounts"]`, menu menempel
  di `<body>`). `views.test.js`/`providers.test.js` tidak berubah (0 rujukan tombol nama, dicek grep).

### Gate PM (mandiri)
`node node_modules/.bin/vitest run` = **24 berkas / 586 tes LOLOS** (identik baseline → nol pengurangan cakupan);
parity 429 kunci hilang 0 thừa 0 kosong 0 (en/id/zh-tw dicek langsung); `git status` = 13 berkas semua `src/frontend/**`;
grep `prov-name-btn` = 0 di seluruh `src/frontend`; 0 hex baru; `git diff --check` bersih; `node --check` e2e exit 0.
Glif `fa-users` dibuktikan ada di Font Awesome Free 6.5.1 yang di-load (`.fa-users:before{content:"\f0c0"}`).

### Temuan di luar cakupan (TIDAK disentuh)
Font Awesome dimuat dari **CDN cloudflare** (`index.html:42`) = utang lama WL.5 (ikon mati offline + permintaan
keluar) — butuh keputusan user, bukan bagian tugas ini.

### Default PM yang dikunci (user boleh veto)
(1) item akun membuka HALAMAN RINCI (bukan lompat ke kartu akun saja — halaman itu juga memuat strategi);
(2) label persis "Akun alternatif/sekunder"; (3) urutan akun → ubah → hapus; (4) ⋮ baris kombo/pool/endpoint tak disentuh.

### BELUM diverifikasi
Belum dilihat di peramban nyata (G3) — bagian tampilan dibaca ulang dari berkas tiap permintaan, jadi cukup
muat ulang halaman, tidak perlu memuat ulang server; jalur ⋮ → item belum dieksekusi sungguhan (nol browser);
terjemahan 6 bahasa belum ditinjau penutur.

## 2026-09-11 — TAHAP 5+6: ubah akun (backend+layar) + Font Awesome dilokalkan + label menu (commit `eea7504` `19df593` `15862bf` `b256064` `bb759e4`, BELUM push)

**Asal:** satu pesan user memuat tiga permintaan: "localin aja semua aset font atau icon" · "kenapa teks menunya
'Alternative/secondary accounts' itu kan cuma contoh. ganti jadi yang lebih representatif dong" · "kok gak ada tombol
edit ya di daftar secondary account? cuma ada tombol delete doang nih". Lanjutan: "lanjut dong tadi provider AI-nya error"
(spawn tahap-6 mati "upstream authentication failed" → handover sama diulang).
Laporan: `.opencode/reports/20260911/implementation/1850_ubah-ikon-lokal-label-tahap5-6.md`.
**Sebab-akibat:** tombol edit mustahil karena API lama hanya menerima `priority` (`1351:81`) → backend dulu, baru layar.

### Backend — `eea7504` (be-dev `ses_f70913524ffezKmxQV4LdzciV4`)
- `src/backend/accounts_router.py:7` docstring modul; `:67-89` `AccountUpdate` diperluas (`label`, `api_key`, `enabled`,
  `priority`); `:263-321` `update_account` ditulis ulang. Parsial pakai `req.dict(exclude_unset=True)` → **"absen" ≠
  "kosong"**: `label=""`/`api_key=""` sah ditulis sadar, `null` = no-op (kolom NOT NULL `models.py:110,113`).
  `auth_type` + `last_used_at` tidak bisa ditulis (diabaikan senyap, DTO kembalikan nilai asli; alasan oauth token lahir
  di callback ditulis di `:75-79`). SATU penolakan `:291-298`: `api_key` (termasuk `""`) ke akun oauth → 400
  `oauth_account_key_readonly`, dievaluasi SEBELUM menulis. Log `:317-320` hanya NAMA field.
- `tests/backend/test_account_routing.py:565-799` +11 tes: label-only, api_key-only, 404 untuk semua field,
  `api_key=""` → akun di-skip mesin (end-to-end ke `_select`), toggle `enabled` + mesin hanya lihat yang enabled,
  semua field sekaligus, **regression guard field absen tidak menimpa**, body kosong = no-op 200, `auth_type` diabaikan,
  oauth+api_key → 400, dan **log `LogEntry` tidak memuat nilai rahasia** (baca tabel log, assert `sk-super-secret` absen).
- `_seed` (:85-118) dibuat aditif (`auth_type`/`oauth_token`) → 28 tes lama tidak berubah.
- Gate PM sendiri: `python3 -m pytest tests/backend -q` = **537 passed, 1 skipped, 0 failed** (baseline 526 + 11).
- `GET /api/accounts` + `_account_to_dto` TIDAK disentuh → kontrak tahap-1 tetap sah kecuali `1351:81` yang kini usang (supersede di laporan).

### Frontend — `19df593` (fe-dev tahap-5 `ses_f7060031dffeFpTJlMt5NVXMTT`; tahap-6 sesi `ses_f6fd547b4ffee4lli1lcr0VIEO` setelah sesi pertama mati)
- `static/app.js:1313-1319` tombol `.acc-edit` (`fa-pen`, `aria-label`+`title`) sebelum `.acc-del`; `:1356-1359` cabang handler
  di listener delegasi `#accList` yang SUDAH ada (nol listener per kartu); `:1444-1571` `#accModal` dua mode
  (`accModalMode`/`accEditingId`, seed eksplisit mode tambah, `openAccountEditModal` baca `accountRows` tanpa fetch ulang,
  `setAccountModalChrome` satu tempat untuk semua beda mode, `closeAccountModal` reset ke mode tambah);
  `:1553-1560` `syncAccountKeyRow` memperluas → baris kunci TERSEMBUNYI + catatan oauth; `:1577-1615` `saveAccountEdit` →
  `PUT /api/accounts/{id}` HANYA `{label, api_key, enabled}` (akun kunci) / `{label, enabled}` (akun oauth) — ditegaskan tes
  `toEqual` + `not.toHaveProperty("auth_type"|"priority"|"last_used_at"|"provider_id")`.
- `static/index.html:991-1044` (`#accOauthNote`, `#accEnabledRow`+switch, id baris prioritas) — `enabled` hanya mode UBAH,
  `priority` hanya mode TAMBAH (satu pintu untuk satu urusan; mengurut sudah ▲▼).
- `static/styles.css:1204` ukuran tombol aksi kartu (0 warna hex baru).
- i18n +7 kunci × 7 kamus (`provider_detail.edit_account|edit_title|save_changes|enabled|oauth_key_note|edit_error|edit_missing`).
- **Vendoring (aturan G3 — CDN selama ini dipakai PRODUK):** `static/vendor/font-awesome/` 5 berkas **409.388 B**
  (`LICENSE.txt` 7.427 · `css/all.min.css` 102.641 · woff2 brands 117.372 / regular 25.452 / solid 156.496) diambil dari
  branch `docs/wiki` dengan `git restore --source=docs/wiki` (nol unduhan, TIDAK ikut ter-staging); PM mencocokkan
  **hash blob 5/5**. `index.html:43` = `href="vendor/font-awesome/css/all.min.css?v=20260919"`; tag cdnjs DIHAPUS;
  grep `cdnjs|cdn.jsdelivr|unpkg|@import url("http` pada `static/**` = **0**. `.ttf` (4 rujukan) + `fa-v4compatibility.woff2`
  sengaja tidak di-vendor (woff2 menang di rantai `src`; family legacy `"FontAwesome"` 0 pemakaian di luar `@font-face`).
- **Guard BARU** `tests/vendor_assets.test.js` (7 tes, 160 baris): scan STRUKTUR `static/**` (link/script/img/source/iframe/
  embed/object/video/audio/track + `@import`/`url()` CSS + `<style>` inline) menuntut nol aset eksternal + setiap `woff2`
  yang dirujuk `@font-face` wajib ada di disk; tautan "Repo" ke github = navigasi, dikecualikan dengan alasan tertulis.
  Ketajaman dibuktikan dengan sabotase sementara (sisip CDN → 3/7 gagal; singkirkan woff2 → 2/7 gagal; dipulihkan + hash dicocokkan).
- **Label menu:** `providers.accounts_menu` (kunci TETAP) EN "Alternative/secondary accounts" → **"Manage accounts"**,
  ID → **"Kelola akun"** (+ ru/nl/ja/zh/zh-tw setingkat). Perilaku item tidak berubah (`accounts|edit|delete`, `fa-users`, `openDetail`).
  Catatan: teks yang dikira user "contoh" itu nilai kamus EN — bahasa aplikasi sedang di-set Inggris.
- Cache-buster serentak `20260919` (V/styles/i18n/app — dijaga `tests/i18n.test.js:307-316`).
- Tes: `accounts.test.js` 18→27, `provider_detail.test.js` 40→47, +`vendor_assets.test.js` 7 → **25 berkas / 609 tes LOLOS**
  (gate PM sendiri; nol tes dihapus). Paritas 436 kunci × 7 kamus, hilang 0 thừa 0 kosong 0.
- `e2e/b5_features.mjs` diperluas (assert `.acc-edit`, chrome tambah vs ubah, auth_type read-only) — `node --check` OK, TIDAK dijalankan.

### Dokumen yang ikut diselaraskan (akibat vendoring — supaya sesi berikutnya tidak menulis fakta lama)
- `documents/architecture/TSD.md` §3.4 bullet Ikon + **ADR-015 "Aset front-end: vendor lokal, tanpa CDN"** (`b256064`,
  tech-architect; sensus `documents/architecture/**` = 1 klaim usang, `anthropic-inbound-endpoint.md` bersih).
- `documents/analysis/FSD.md:321` (rujuk ADR-015, tanpa duplikasi byte/path) + `:454` kebutuhan "dapat dipakai offline"
  tercatat TERBUKTI + versi spec 1.0→1.1 (`bb759e4`, system-analyst; sensus analisis = 1 klaim usang).
- `THIRD_PARTY_NOTICES.md` §2 ditulis ulang 118+/18− (`15862bf`, fullstack-dev — berkas root, di luar akar agen lain):
  tabel berkas + lapisan lisensi, kutipan `LICENSE.txt` per baris (CC BY :13-17 / OFL :21-31 / MIT :121-126 / atribusi :147-156 /
  syarat redistribusi :80-85), atribusi ditulis nyata, **provenance diakui jujur** ("6.5.1" hanya dari string header CSS,
  belum diverifikasi terhadap artefak rilis upstream), fallback tak di-vendor + penjaga tes disebut.
- `documents/plan/wiki-backlog.md`: **WL.5 dicentang SELESAI** (keputusan user = vendor lokal), **WL.4 diperluas** ke provenance FA.

### Keputusan agen di luar perintah (semua DITERIMA PM)
`enabled` hanya di mode ubah (POST tambah tetap byte-identik) · `auth_type` ditampilkan read-only, bukan disembunyikan ·
penolakan oauth+`api_key` berlaku termasuk string kosong (UI menyembunyikan kolomnya) · tanpa `log_warning` untuk 4xx
(meniru gaya modul; kalau mau semua 4xx dicatat = perubahan lintas modul, tugas terpisah) · `window.aigate.backToProviders`
diekspos + satu tes dibuat deterministik (bukan melemahkan assertion) · `?v=` ikut dipasang di berkas vendor baru.

### BELUM diverifikasi
Belum di-exercise di peramban nyata (G3) — cukup muat ulang HALAMAN (statis dibaca dari berkas), TIDAK perlu restart server;
**uji mata mode pesawat** (ikon harus tetap muncul) belum dilakukan; e2e/Playwright belum dijalankan; terjemahan non-EN belum
ditinjau penutur; provenance FA belum diverifikasi ke hulu (WL.4); `documents/analysis/FSD.md:7,19` masih merujuk path
`docs/business/BRD.md` yang tidak ada (temuan system-analyst, belum ditugaskan); ahead 19 BELUM push; PR #17 masih terbuka.

## 2026-09-13 — Perkakas uji e2e dibetuli (TERBUKTI belum pernah jalan) + favicon lokal (fe-dev; commit `ddf33df`)

**Asal:** perintah user "lanjut". PM menemukan Chromium 149 TERSEDIA di Termux (`chromium-browser --version`) padahal
laporan-laporan sebelumnya menulis "tidak ada browser di lingkungan ini" → QA + PM menjalankan uji nyata di instance
TERISOLASI (`run.py --port <acak>`, `AIGATE_DB_PATH` di luar repo, PID sendiri dimatikan; proses user 8080 tidak disentuh).
Laporan: `.opencode/reports/20260913/qa/0300_bukti-browser-nyata-dan-perbaikan-perkakas-uji.md`.

### Bug yang dibuktikan dulu, baru diperbaiki (semua dicek ulang PM)
- `e2e/b5_features.mjs:208` → `:268`: `pg.$$eval("#accList .acc-card:first-child", (card)=>card.querySelector(...))` —
  `$$eval` mengirim ARRAY → `TypeError: card.querySelector is not a function`. Runner ini mustahil lolos di browser mana pun;
  vitest/jsdom tidak pernah mengeksekusi berkas e2e, jadi 600+ tes hijau pun tidak menjangkaunya. → `$eval`.
- viewport tak pernah di-set (default 800×600) + Log Window bawaan terbuka menutupi tombol ⋮ (terukur: tombol `top 294..bottom 322`,
  panel log `top 219`, `elementFromPoint` = SPAN panel) → klik mendarat di panel, menu tak pernah muncul.
  Fix paling kecil TANPA mengubah produk: `VIEWPORT 1280×900` + set preferensi yang sudah ada (`aigate.logVisible="0"`) lewat
  `evaluateOnNewDocument`, plus jaring `ensureLogWindowClosed` (toggle produk); `force:true` sengaja tidak dipakai.
- `e2e/playwright.config.js:41` → `:68`: `testDir: "e2e"` relatif folder config = `e2e/e2e` → `Error: No tests found` → `testDir: HERE`.
- `e2e/playwright.config.js:50` → `:83`: `use.executablePath` BUKAN opsi Playwright Test (`test.d.ts`: 0 kemunculan) → diabaikan
  diam-diam lalu mencari headless_shell bawaan yang tak ada → pindah ke `use.launchOptions.executablePath` (kunci sah di
  `playwright-core/types/types.d.ts`).
- CLI Playwright crash saat import di Termux: `Unsupported platform: android` (`coreBundle.js:32822`, dihitung sebelum env dibaca)
  → runner BARU `e2e/run.mjs`: selalu kirim `--config` dan memasang shim `NODE_OPTIONS=--import=data:text/javascript,...`
  (`process.platform`→`linux`; properti terukur `configurable:true`). **`node_modules` tidak ditambal, tidak ada berkas temp.**
  `package.json` → `"test:e2e": "node e2e/run.mjs"` (diagnosa tambahan: CLI juga ikut mengumpulkan `tests/*.test.js` vitest
  kalau `--config` tidak dikirim → "Vitest failed to access its internal state").
- `GET /favicon.ico` = 404 (tidak ada rujukan favicon sama sekali) → BARU `static/favicon.svg` (325 B) + `static/favicon.ico`
  (4.286 B; container ICO 1 gambar 32×32 32bpp, dibuat pure-stdlib Python karena PIL/ImageMagick tidak ada) + rujukan di
  `index.html:46-48`. Semua LOKAL (aturan G3). Bentuk = tanda NETRAL (kotak warna `--accent` + "a" geometris), bukan logo merek.

### Penjaga BARU
`tests/e2e_tooling.test.js` (16 tes statis): larang pola `$$eval` dengan `.querySelector`, tuntut `$eval` untuk kartu,
viewport ≥1280×720 + pref `aigate.logVisible` + larangan `force`, `testDir: HERE`, `executablePath` hanya di `launchOptions`
(dibandingkan ke `test.d.ts`/`types.d.ts` asli), `run.mjs` mengirim `--config`, setiap skrip `test:e2e*` menunjuk berkas NYATA,
favicon dirujuk + ada + header ICO sah. **Divalidasi dengan mutasi:** 4 bug lama dikembalikan → 4 penjaga gagal; dipulihkan → hijau.

### Bukti di browser nyata (Chromium 149 headless, instance terisolasi)
`node e2e/b5_features.mjs` (runner ASLI, bukan salinan) → `B5.1/B5.5/B5.6/B5.7 OK` + `B5 E2E PASS`, exit 0 (diulang PM di port 8321: sama)
· `node e2e/run.mjs` → `2 passed` (smoke) · `GET /favicon.ico` = 200 (sebelum 404) · `GET /favicon.svg` = 200
· `vendor/font-awesome/css/all.min.css` + `webfonts/fa-solid-900.woff2` = 200 · audit `page.on('request')`: 55 permintaan,
host hanya `127.0.0.1:<port>`, nol permintaan keluar · `document.fonts.check('900 16px "Font Awesome 6 Free"')` = true,
`::before` = `U+F05A` (banner) dan `U+F0C0` (menu) · `#pdStickyRow`: `offsetHeight` 0 saat `fill-first` (input nonaktif) vs
34 saat `round-robin` → tambalan `display:flex` terbukti di peramban, bukan cuma di jsdom.
Gate reguler PM sendiri: `node node_modules/.bin/vitest run` = **26 berkas / 625 tes LOLOS** (sebelum 25/609).

### Fakta tambahan yang mengubah jawaban ke user
`GET :8080/openapi.json` kini = `AccountUpdate ['api_key','enabled','label','priority']` (pelayan = `python run.py` PID 15777,
berumur ±11 menit; pengukuran 11 menit sebelumnya = `['priority']` dengan PID 15400) → **aplikasi user sudah memuat API
ubah-akun**, jadi tidak ada lagi alasan "tombol Ubah tidak menyimpan". PM tidak menyentuh/mematikan proses apa pun (aturan restart = hak user).
Temuan lingkungan: `python3 run.py --port 8251` (PID 5934, ±1 hari 2 jam) masih hidup dari sesi lama — DILAPORKAN, tidak dibunuh.

### BELUM diverifikasi
Sentuhan layar asli / WebView ponsel (hanya chromium desktop-headless) · OAuth connect end-to-end ke penyedia eksternal ·
discovery model ke API sungguhan · hasil screenshot bukti (model PM tanpa masukan gambar; angka DOM yang dipakai) ·
bentuk favicon menunggu selera user · `trace/screenshot on-failure` masih menulis ke `<cwd>/test-results` (dibersihkan manual; `.gitignore` root bukan milik fe-dev).

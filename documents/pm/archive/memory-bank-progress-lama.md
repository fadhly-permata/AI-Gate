# Arsip Progress memory-bank (2026-09-10, dipindah tanpa buang isi)

Sumber: `documents/pm/memory-bank.md` seksi `## Progress`. Yang aktif = entri terbaru di berkas asal.

- 2026-09-07 (malam): **Suite tes FE 1,5x lebih cepat — DONE (`618f7d7`, fe-dev).**
  Akar TERNAKTA bukan parse HTML doang: Termux lapor `os.cpus().length===0` → vitest
  fallback **8 fork** di HP ter-throttle. Kurva nyata: 1 fork 12.6s · **2 fork 8.3s** ·
  4 fork 10.4s · 8 fork 12.2s. Fix: `tests/helpers/dom.js` (parse `index.html` sekali per
  worker), `tests/helpers/quiet.js` sbg `setupFiles` (stop poller log/usage tiap tes —
  menutup flake yang muncul begitu fork dinaikkan), `maxForks:2`. Gate PM: **484 passed,
  13.86s** (saat throttle; 8.27s saat tidak) — collect 24.07→6.82s, environment
  28.63→5.61s, tests 23.82→9.71s. Artefak throwaway `tests_orig/` + `vitest.orig.config.js`
  dibuang. Open: guard `typeof fetch` di `app.js:1792` selalu lolos → poller nyala saat tes.
- 2026-09-07 (malam): **Sidebar + tautan Repository sticky — DONE (`86a5ef1`, belum masuk `main`).**
  User minta link repo (`https://github.com/fadhly-permata/AI-Gate`) nempel di dasar menu
  samping. FE-only: `.sidebar-footer` di luar `<nav>` (jaga rule `.nav-section:last-child`),
  `app.js` skip item tanpa `data-view` (kalau tidak, klik luar di-block), `.sidebar` jadi
  flex column + footer `sticky;bottom:0`+`margin-top:auto`, i18n `nav.repo` EN/ID,
  cache-buster `v=20260912`, +8 tes `views.test.js`. Gate PM: vitest **484 passed, 14.66s**.
  **PR #5 sudah MERGED (`0e290ae`) tapi keburu sebelum commit ini** -> 1 commit ini butuh PR
  susulan. PELAJARAN PROSES: user protes lama ("buset, lama amat") -> handover PM kepanjangan;
  spawn pertama dibatalin user, spawn kedua ~20 baris dan langsung kelar.
- 2026-09-07 (sesi ini, akhir): **BERES-BERES — semua kerjaan numpuk di-commit rapi + suite hijau.**
  (1) **Fitur cleanup log** (BE T1 + FE T2, handover `documents/pm/handover-20260907-logs-{be,fe}.md`):
  `DELETE /api/logs` (severity/before, wipe-all wajib `confirm=all`), retensi startup
  `log_retention_days` (default 7, fallback aman), kolom `LogEntry.resolved` + migrasi aditif,
  GET sembunyi resolved kecuali `show_resolved=true`, resolve tunggal+bulk, self-heal
  `current_issue()/_count_remaining()` skip baris resolved. FE: tombol Clear + modal pemilih
  lingkup, toggle Show resolved (localStorage), baris resolved redup+badge, tombol resolve
  per-baris (warning|error saja), Resolve-all (filtered), i18n EN/ID, **cache-buster
  styles.css/app.js/combobox.js/i18n.js/selfheal.js → v=20260911** (gap yang ketemu PM:
  aset berubah tapi tanpa `?v=` = jebakan cache terminal.js). DEVIASI tercatat: wipe-all
  tanpa confirm → 200 `{deleted:0,error}` (bukan 400); id tak dikenal → `{resolved:0}`
  (bukan 404); FE pakai modal, bukan `window.confirm` (lebih bagus, konsisten app).
  (2) **Self-heal** (pemilih CLI/model, combobox grouped, gerbang false-done, kualifikasi
  model) = kerjaan sesi-sesi sebelumnya yang baru di-commit. (3) **Kecepatan tes FE**:
  `vitest.config.js` `isolate:false` + `vi.resetModules()` di `terminal_exit.test.js`
  → 32-34s jadi **23.3s** (476 pass). Akar: jsdom dibangun ulang per file (environment
  84.9s kumulatif) + 1 tes ngandelin cache ref DOM basi — BUKAN bug aplikasi.
  (4) **PR #4 ternyata SUDAH MERGED** (lihat Decisions) → 4 commit + kerjaan sesi ini
  sekarang menunggu PR baru ke `main`. ANGKA FINAL: BE **478 passed/1 skip**,
  FE **476 passed (23 file)**. Item yang user TOLAK kerjakan: verifikasi flag `--model`
  per CLI lain (tetap open item).
- 2026-09-07: **PR #4 `refactor/ui` → `main` = MERGED 2026-09-06T21:30:12Z** (merge commit
  `b278afe`, 59 file, +4574/−722, 14 commit + 1 merge). Catatan lama di Memory Bank
  ("belum merge") SUDAH TIDAK berlaku. Laporan detail perubahan:
  `.opencode/reports/20260907/review/1934_pr4-change-detail.md` (dibuat `qa-engineer`).
  KOREKSI buat PM: angka "73 file via `origin/main...origin/refactor/ui`" basi — setelah
  merge diff itu cuma menyisakan 4 commit pasca-merge (24 file). Temuan QA: **4 commit di
  `refactor/ui` belum masuk `main`** (`a17264c`, `0523a05`, `68cc1bd`, `1bc8fda`) dan
  **tidak ada PR terbuka** → butuh PR susulan. Klaim "duplikat rule R23→R29" tidak
  terkonfirmasi (nomor R1…R33 rapi, tanpa duplikat). Deviasi kualitas: rule **R24**
  disisipkan di dalam commit fitur UI `38e3743` (langgar atomicity/R22) — dicatat, tidak dibongkar.
- 2026-09-07 (now): **BUGFIX Self-Heal false-done (issue-64) — SELESAI (PM proxy be-dev, uncommitted).** User lapor heal "sukses" tapi tidak ada yang diproses. Root cause (terverifikasi): `build_heal_command` manggil TUI default `opencode --model hy3 --prompt ...` (bukan `opencode run`; `run` gak punya `--prompt`, `-m` minta `provider/model`), separator `;` bikin `touch .done` jalan walau CLI gagal (false done), dan `hy3` mentah ambigu (`aigate/hy3` vs `bai/hy3` — dari setting `self_heal_model`, value combobox = `model_id` mentah DB). Fix (scope be-dev saja): (1) opencode -> `opencode run[-m <qualified>] "$(cat file)"`; (2) gate `&& { touch done; echo } || touch failed` + `wait_for_done(failedfile=)` return False seketika; (3) `qualify_opencode_model()` via `opencode models` (unique->pakai; ambigu->prefer `aigate/`; none->omit flag + warning; fail-open). CLI lain tetap bentuk lama (unverified) tapi dapat gating. Verifikasi: pytest backend **458 passed/1 skip** (+7 test baru) + dry-run live shim exit 0/1 (`.done` gak muncul saat gagal ✓). Rule baru **R34**. DEVIASI: sesi ini TIDAK ada Task tool -> PM tidak bisa spawn be-dev; implementasi PM kerjakan sendiri strictly di write scope be-dev (dicatat di status.md). PENDING user: restart aigate (R32); setting lama `self_heal_model='hy3'` sekarang otomatis ter-kualifikasi ke `aigate/hy3` saat run.
- 2026-09-07 (now): **Self-Heal model list -> group by provider + combo — SELESAI (paralel BE→FE).** User mau grup kayak dialog CLI Tools. be-dev: `list_self_heal_models()` balikin dict `{value,label,group}` (provider=provider.name, combo=sentinel `__combos__`); endpoint `/api/self-heal/models` -> dict. fe-dev: model combo `groupBy:group, subGroupBy:prefix, startExpanded` + pin grup Kombo di atas (lokal "Kombo"/"Combos"); sentinel `__combos__` di-map ke localized. cache-buster `selfheal.js?v=20260910`. Verifikasi PM: BE **451 passed/1 skip**, FE **459 passed (23 file)**. PENDING: restart + hard-refresh (R32). BELUM di-commit.
- 2026-09-07 (now): **Self-Heal dropdown -> searchable + grouped combobox (match CLI Tools dialog) — SELESAI (fe-dev).** User nyinyir dropdown self-heal cuma native `<select>` (gak search/group) padahal app standar pakai `createCombobox`. fe-dev ganti `selfHealCli`/`selfHealModel` ke `window.aigate.createCombobox`: CLI `searchInside:true, groupBy:none`; model `searchInside:true, groupBy:prefix, startExpanded:true` (family grouping, tanpa BE change). Default "Auto"/"No model" = value "". `combobox.js` di-tweak render opsi tanpa grup + opt `startExpanded`. cache-buster `selfheal.js?v=20260909`. Verifikasi PM: vitest penuh **459 passed (23 file)**. PENDING: restart + hard-refresh (R32). BELUM di-commit.
- 2026-09-07 (now): **Self-Heal: pilihan agentic-CLI + model + live preview — SELESAI (paralel BE→FE, uncommitted).** User mau pilih CLI & model buat self-heal + lihat preview proses jalan (hipotesis: stuck gara2 tool/model). BE (be-dev): `list_agentic_clis()` + `list_self_heal_models()` (dari `provider_models`), setting `self_heal_cli`/`self_heal_model`, `run_self_heal(cli,model,...)` + `build_heal_command` append `--model` via `CLI_MODEL_FLAGS` (hanya CLI dikenal), state `progress` kaya (phase/cli/model/branch/iteration/current_issue_id/started_at/remaining) di `heal_status()`. Router: `GET /api/self-heal/clis`, `GET /api/self-heal/models`, `POST /api/self-heal/run` terima `{cli,model}`, `GET /api/self-heal/status` +`progress`. FE (fe-dev): dropdown CLI + model (default Auto/No-model), panel preview (progress poll 2.5s + log feed stream dari `/api/logs` filter `source` `backend.selfheal`), i18n +22 key (EN/ID, parity guard lolos), cache-buster `selfheal.js?v=20260908`. Verifikasi PM: **BE 451 passed/1 skip, FE 458 passed (23 file)**, 0 regresi. PENDING: user restart aigate (R32) + hard-refresh. Open: flag `--model` per-CLI lain (claude/opencode/aider sudah `--model`; codex/gemini/goose/amp/qwen/cline/kilo belum diverifikasi ke CLI asli — map bisa dikoreksi).
- 2026-09-07: **Self-Heal progress terlihat — SELESAI (sekuensial BE→FE, uncommitted).**
  Root cause: POST /api/self-heal/run sinkron + CLI via subprocess tersembunyi.
  Fix BE (be-dev): CLI jalan di PTY key `self-heal` (command diketik, prompt file
  temp anti-injection, donefile poll, timeout 1800s/issue, abort bila tab mati);
  run async (start_self_heal, 409 already_running) + GET /api/self-heal/status
  {running, last}. Fix FE (fe-dev): klik Run → buka+fokus tab "Self-Heal" +
  polling 5s; i18n +2 key. PM: cache-buster v=20260907 (selfheal/terminal/i18n),
  docs FSD/TSD/BRD sinkron, CODE_CHANGES.md. Verifikasi PM: **BE 438 passed/
  1 skipped, FE 453 passed (23 files)**. PENDING: user restart aigate + hard-refresh
  (R32); belum commit (menunggu approve). Open: FE poll max-age cutoff (opsional).
- 2026-09-07: **Request Log kolom Model/Endpoint kosong — SELESAI + DI-COMMIT
  `a17264c` + PUSH `origin/refactor/ui`.** Root cause: combo ref → resolver `upstream_model=""` →
  router nimpa `ctx["model"]` jadi `''` (RequestLog.model kosong utk semua request
  combo); Endpoint kosong = by-design (model-based, tanpa header
  `X-Aigate-Endpoint`). Fix: BE `_upgrade_ctx_model` helper (6 situs, upgrade
  hanya bila non-empty; combo → prefer model member dari envelope upstream,
  fallback combo ref) + DTO `endpoint_name` (Pydantic v1); FE `orDash`/
  `reqlogEndpoint` (nama → id → "—") + cache-buster `analytics.js?v=20260906`
  (pola precedent terminal.js, PM-owned 1 baris). Verifikasi PM: **BE 423 passed/
  1 skipped, FE 445 passed (23 files)**. Baris lama `model=''` tidak di-backfill.
  PENDING: user restart aigate (R32) + hard-refresh. Detail:
  `documents/dev/CODE_CHANGES.md` 2026-09-07.
- 2026-09-07: **Terminal tab auto-close on shell exit — SELESAI (uncommitted, mode
  sekuensial BE→FE).** Kontrak exit (sumber kebenaran): server kirim TEXT frame
  `{"type":"exit","code":<int>}` (code = exit status; -1 bila tak terbaca) ke view
  attached, LALU tutup WS (1000). Frame TIDAK masuk ring-buffer replay. FE tangkep →
  `closeTab(id,{exited:true})` (tanpa kill-frame, tanpa auto-open → empty state,
  forget saved id). BE: `pty.py` +`exit_status`; `session.py` `PtyExit` sentinel +
  `notify_exit()`/`resolved_exit_code()`/`read_exit_code()`/`close_view()` + reaper
  reap exited-walau-attached; `router.py` `_pump` → `exit_frame()` (json.dumps) lalu
  close 1000. TEST ASLI (PM re-run): backend terminal **64 passed, 1 skipped**
  (skip=test_terminal.py:59 native PTY dep); FE terminal_exit **14 passed**; FE full
  **436 passed (23 files)**, no regresi. Catatan env: `ruff` tak terpasang (lint gate
  tak jalan); vitest harus dipanggil via `node node_modules/.bin/vitest` (shebang env
  Termux rusak). AKAR MASALAH SESUNGGUHNYA (temuan akhir): tab gak nutup karena
  **`terminal.js` ke-cache browser tanpa cache-buster** — kode FE beneran gak ke-load
  versi baru. BE **terbukti benar via runtime** (frame exit + close 1000 terkirim).
  RESOLUSI FINAL: FE hardened (exit frame + close(1000) → tutup tab) + **toast
  `term.session_ended` (id+en)** + **cache-buster `?v=20260906` di index.html**.
  ANGKA FINAL (PM re-run): FE **442 passed**, BE **65 passed / 1 skipped**.
  **DI-COMMIT `a06ef9b` + PUSH `origin/refactor/ui`. PR #4 `refactor/ui`→`main`:**
  https://github.com/fadhly-permata/AI-Gate/pull/4 (belum merge; scope PR lebar =
  11 commit/49 file, terminal + seluruh UI-refactor branch — sudah dicatat di body). RULE BARU **R32**: dilarang nyuruh sub-agent kill/restart proses aigate
  (sesi opencode hidup DI DALAM aigate = bunuh diri); bukti kode lama aktif cukup
  bandingkan start-time vs mtime + laporkan, user yang restart.
- 2026-09-07: **Terminal tab auto-close on shell exit** — investigasi PM (read-only).
  Temuan: fitur ini SUDAH di-spec TSD §3.2 (frame `{"type":"exit","code":N}` + langkah
  "saat shell keluar, kirim kontrol exit, tutup WS") tapi BELUM diimplementasi.
  Gap: (BE) `session.py:353-356` reader thread cuma set `exited=True` + log, TIDAK
  notify client; `try_reap` skip session yang masih `attached` (`session.py:290-291`)
  → shell exit = tab nyangkut (zombie view). (FE) `terminal.js:374-387` `handleWsMessage`
  buang SEMUA control frame non-ping → gak ada jalur "exit". Perlu task be-dev + fe-dev.
- 2026-09-06: Header grup "Kombo" di model picker CLI Tools kini terlokalisasi penuh
  (EN "Combos" / ID "Kombo") lewat key `combobox.group_combos`; literal bilingual
  dihapus dari kode produksi; `combobox.js` dapat `setGroupOrder()` supaya grup yang
  di-pin ikut locale (controller dibuat lazy + di-cache, jadi pin lama bisa basi).
  Dikerjakan inline oleh main thread (PELANGGARAN → R29), lalu diaudit PM (diterima
  fungsional) dan di-hardening oleh `fe-dev` (parity guard + test re-pin + pembersihan
  fixture) dengan gate `qa-engineer`. Suite awal: 422 passed / 22 files.
- 2026-09-06: Toolbar terminal ditata ulang menjadi tiga dropdown berurutan: Paste (normal/code block), Settings (TUI passthrough/Keep Screen On), Full (Full Page/Fullscreen). Wiring, ARIA state, dan test fixture diselaraskan. Vitest 394 passed (21 files).
- 2026-09-06: Tooltip icon-only dibuat transient (tap auto-close 2 detik; Escape/outside/scroll/resize tetap menutup). State Full Page dan true Fullscreen dipisah eksplisit; hanya mode aktif yang biru, caret tidak aktif. Vitest 394 passed (21 files), terminal toolbar 62 passed.
- 2026-09-06: Terminal Keep Screen On dikembalikan dengan ikon perangkat yang lebih jelas (`fa-mobile-screen-button`). Popover tooltip global ditambahkan untuk kontrol ikon-only; mendukung hover, focus, tap, Escape, outside click, dan kontrol dinamis. Frontend Vitest 392 passed.
- 2026-09-09: **CLI Tools install scripts — progress 21/24 (A1 claude + A2 opencode + A3 gemini + A4 codex + A5 antigravity + A6 phi + A7 aider + A8 goose + A9 amp + A10 qwen + A11 cline + A12 kilo + B1 openhands done + B2 swe-agent done (NO_INSTALL) + B3 open-interpreter done (OpenAI-compatible, verified, `LAUNCH_VERIFIED` cli_presets.py:196, commit `31b9a04`) + B4 autogpt done (NO_INSTALL, pesan+exit, commit `a5d1a91`) + C1 llm done (OpenAI-compatible, verified, `LAUNCH_VERIFIED` cli_presets.py:219, `pip install llm` + wiring `llm openai endpoint ... --chat/--models`, commit ini)). **GRUP A SELESAI (12/12); B1 openhands = done (OpenAI-compatible, verified, `LAUNCH_VERIFIED` cli_presets.py:190).** Lanjut Grup B (B4..B6) + Grup C (C2..C6).** Branch `setup/cli-tools`. A8 (`goose.sh`) commit `414ea06`: **NO_INSTALL** — script HANYA pesan `goose: NO_INSTALL — belum ada install terverifikasi di environment ini.` + `exit 0`, TIDAK memasang apa pun (no side-effect). Bukti `cli_presets.py:77` (`install: NO_INSTALL`) + `cli_presets.py:178` (`LAUNCH_UNSUPPORTED`/`REASON_NO_BINARY`); `TERMUX_INSTALL` tidak punya entry goose; cross-check 5 sumber (npm `goose`=Golang tak terkait, `@block/goose` 404, PyPI `goose`=SQL migration, Homebrew `goose`=pressly/goose migrasi DB, install resmi Block curl script tak punya build aarch64-android/termux terverifikasi) → TIDAK ada install terverifikasi. **A9 (`amp.sh`) commit `446f78f`: NO_INSTALL — script HANYA pesan `amp: NO_INSTALL — belum ada install terverifikasi di environment ini.` + `exit 0`, TIDAK memasang apa pun (no side-effect). Bukti `cli_presets.py:78` (`install: NO_INSTALL`) + `cli_presets.py:179` (`LAUNCH_UNSUPPORTED`/`REASON_NO_BINARY`); `TERMUX_INSTALL` tidak punya entry amp; cross-check 5 sumber (npm unscoped `amp`=library messaging tak terkait tjholowaychuk/node-amp, `@ampcode/cli` ADA tapi optional deps HANYA darwin/linux/win32 — gak ada build android/termux, PyPI `AMP`=parser matematika, Homebrew `amp`=text editor terminal amp.rs) → TIDAK ada install terverifikasi. A1 (`claude.sh`) + `_common.sh` sudah commit sebelumnya. A7 (`aider.sh`) commit `5a960e7`: install `python3 -m pip install aider-chat` (mirror `cli_presets.py:76`), wiring `OPENAI_API_BASE`+`OPENAI_API_KEY` + flags `--openai-api-base`/`--openai-api-key` ke aigate `/v1/chat/completions`, model `--model openai/<m>`; fakta `cli_presets.py:172` (`LAUNCH_VERIFIED`) + `cli_tools_router.py:355-369` (`_aider_builder`). A2 (`opencode.sh`, 122 baris) commit `f8d9f0b`: install `npm i -g opencode-ai`, wiring `OPENAI_API_BASE`+`OPENAI_API_KEY` ke aigate `/v1/chat/completions`, generate `opencode.json` di CWD. A3 (`gemini.sh`, 114 baris) native Google mode: install `npm i -g @google/gemini-cli`, launch langsung dengan kredensial Google (GEMINI_API_KEY/GOOGLE_API_KEY/OAuth) — TIDAK di-wire aigate karena `cli_presets.py:175` mark gemini `LAUNCH_UNSUPPORTED`/`REASON_GEMINI_ONLY` (aigate hanya serve OpenAI `/v1/chat/completions` + Anthropic `/v1/messages`, no Google generateContent inbound). A4 (`codex.sh`, 136 baris) commit `7f22713`: native OpenAI mode, TIDAK di-wire aigate karena `cli_presets.py:180` mark codex `LAUNCH_UNSUPPORTED`/`REASON_RESPONSES_ONLY` (aigate `/v1/responses` non-streaming only, `responses.py:227-233`; codex CLI wajib streaming). A5 (`antigravity.sh`, 69 baris) commit `2259c1c`: **NO_INSTALL** — script HANYA pesan `antigravity: NO_INSTALL — tidak ada paket CLI terverifikasi` + `exit 0`, TIDAK memasang apa pun (no side-effect). Bukti `cli_presets.py:74` (`install: NO_INSTALL`) + `cli_presets.py:176` (`LAUNCH_UNSUPPORTED`/`REASON_NOT_A_CLI`); `TERMUX_INSTALL` tidak punya entry antigravity; npm/pip/brew tidak ada rute resmi. Install: Termux `pkg install codex` (`cli_presets.py:243`) / non-Termux `npm i -g @openai/codex`. Known caveat: Termux npm `os` field tanpa `"android"`. Sisa 19 tool menyusul.
- Inisialisasi PM agent + rules + skills selesai.
- 2026-09-03: Enhance PRD terminal — floating control, scroll/swipe natural,
  grouping CLI tools (agentic-first, 3 grup).
- 2026-09-03: Sequential doc creation SELESAI — BRD (documents/business/BRD.md),
  FSD+ERD (documents/analysis/FSD.md, ERD.md), TSD (documents/architecture/TSD.md).
  Spesialis business-analyst, system-analyst, tech-architect + skill-nya
  di-generate on-demand (belum terdaftar di sesi; pakai 'general' stand-in).
  Semua dokumen di `documents/` (R5).
- 2026-09-03: Execution docs SELESAI (mode sekuensial) — #1 Backlog
  (documents/plan/BACKLOG.md), #3 API Contract (documents/api/), #4 Test Plan
  (documents/qa/), #5 Dev Setup (documents/dev/), #6 Terminal UX (documents/ux/),
  #7 CLI Config Schema (documents/config/). ADR-007 & ADR-008 resolved.

- 2026-09-03: PRD diselaraskan ke 9router (R17 capture). Fitur adopsi baru (token
  saver, pelacak kuota, penerjemah format, multi-akun, OAuth refresh, export/import
  lokal) SUDAH di PRD tapi BELUM di BACKLOG & BELUM diimplementasi. Perlu backlog
  baru + /run-impl.

- 2026-09-05/06: CLI tool launcher — audit SEMUA 24 preset, satu per satu,
  1 tool = 1 commit, delegasi ke `be-dev` (R21). Hasil: **11 verified**
  (aider, opencode, aichat, qwen, cline, kilo, llm, gptme, open-interpreter,
  oterm, openhands), **13 unsupported** beralasan (claude/gemini = format
  bukan-OpenAI; codex = butuh /v1/responses; antigravity/gpt-researcher/crewai
  = bukan CLI launchable; goose/amp/mods/aichat-ish/sgpt = gak ada paket
  platform ini; phi/swe-agent/autogpt = nama paket gak ketemu), **0 pending**.
  Bug ikutan ketemu & dibenerin: install string salah paket (`openhands-ai`
  gak punya console script -> `openhands`; `aider` -> `aider-chat`; npm vs pip),
  preset gak pernah nyampe DB (seed skip) -> jadi upsert, UI nyoret tool yang
  belum verified + `resolve` balas 409 daripada ngarang command.
  Dasar verifikasi dicatat per tool di CLI_CONFIG_SCHEMA: dijalankan langsung
  di perangkat (aider, opencode, aichat) vs dokumen resmi (sisanya — npm/pip
   gak bisa dipasang di Termux, user larang install).
- 2026-09-05: Terminal stay-alive (sesi ini). Task1 env: `~/.bashrc` auto
  `termux-wake-lock` (tanpa install) biar server aigate gak di-freeze Android saat
  layar mati. Task2 (fe-dev, DONE+verif): persist `tab_id` via sessionStorage ->
  terminal survive Chrome tab DISCARD (`terminal.js` +123/-18, test baru
  `terminal_discard.test.js` 16; suite 330 passed). Task3 (fe-dev, DONE+verif):
  toolbar Keep Screen On (wake lock) + dropdown Fullscreen (full page/true FS) +
  dropdown Paste (normal/blok kode) -> 2 spawn ke-interupsi tapi diff mendarat; PM
  review + sisa fe-dev benerin typo regex tes; suite 390 passed (330+60), 0 regresi.
  RULE BARU **R22**: tiap perubahan kode dicatat per-file di
  `documents/dev/CODE_CHANGES.md` (code↔doc align).

- 2026-09-09: **CLI Tools — GRUP B SELESAI (6/6):** B1 openhands (OpenAI-compatible, verified) + B2 swe-agent/B4 autogpt (NO_INSTALL) + B3 open-interpreter (OpenAI-compatible, verified) + B5 gpt-researcher/B6 crewai (NOT_A_CLI). Progres keseluruhan cli-tools **21/24** (C1 llm done + C2 sgpt done + C3 mods done, keduanya NO_INSTALL). Lanjut Grup C (C4 oterm, C5 gptme, C6 aichat).
- 2026-09-09: **aider.sh BUGFIX — version-guard Python 3.10–3.12** (branch `setup/cli-tools`, commit `1d1a31c`): `pip install aider-chat` gagal di device (Python 3.14.6; aider `requires_python ">=3.10,<3.13"` per PyPI 0.86.2). Skrip lama cuma `NOTE` Termux-only post-install (setelah `ensure_installed` → raw pip error). Fix: guard pre-install + `exit 1`; hapus NOTE lama; wiring launch utuh. `bash -n` clean; simulasi guard lulus (3.10/3.11/3.12 lanjut, sisanya exit 1). Catatan: spawn tool sub-agent TIDAK tersedia di sesi ini → PM edit langsung dalam scope `scripts/cli-tools/aider.sh` (deviasi R21, transparan per R29).

- 2026-09-09: **openhands.sh BUGFIX — version-guard Python 3.12** (branch `setup/cli-tools`, commit `313a2c2`): `pip install openhands` (fallback) gagal di device (Python 3.14.6; openhands `requires_python ==3.12.*` per PyPI 1.16.0). Fix: guard pre-install — `have_cmd uv`→lanjut (uv fetch 3.12 sendiri); `elif python3` major.minor !=3.12→ERROR + `exit 1` TANPA install; parse-gagal→WARN. Wiring launch utuh; `bash -n` clean. **crewai.sh & gpt-researcher.sh di-VERIFIKASI = NOT_A_CLI (hanya pesan + `exit 0`, TIDAK ada `pip`/`uv install`) → version-guard TIDAK relevan, TIDAK diubah.** (R14/R35 verified.)

- 2026-09-09: **cli-tools C2 sgpt + C3 mods = done (NO_INSTALL, message + exit 0, no side-effect)** — `scripts/cli-tools/sgpt.sh` + `scripts/cli-tools/mods.sh` di-commit (commit ini). Bukti `cli_presets.py:101`/`cli_presets.py:224` (sgpt: `NO_INSTALL` + `LAUNCH_UNSUPPORTED`/`REASON_INSTALL_UNVERIFIED`) dan `cli_presets.py:102`/`cli_presets.py:225` (mods: `NO_INSTALL` + `LAUNCH_UNSUPPORTED`/`REASON_NO_BINARY`); `TERMUX_INSTALL` tidak punya entry sgpt/mods; registry npm `sgpt`/`mods` = squat tak terkait, PyPI 404, GitHub `tbckr/sgpt` (Rust) & `charmbracelet/mods` (Go) gak build Termux/android-arm64. `bash -n` clean, pesan literal (TIDAK ada backtick/`$()`). Progres keseluruhan cli-tools **21/24**.

- 2026-09-09: **cli-tools C4 oterm = done (OpenAI-compatible, verified)** — `scripts/cli-tools/oterm.sh` di-commit (`aea87c3`). Bukti `cli_presets.py:103` (`pip install oterm`) + `cli_presets.py:222` (`oterm` = `LAUNCH_VERIFIED`) + `cli_tools_router.py:891-917` (`_oterm_builder`: tulis `.oterm-aigate/config.json` blok `openaiCompatible.aigate` {base_url=gateway, api_key="${OPENAI_API_KEY}"}, set `OTERM_DATA_DIR=.oterm-aigate` + env `OPENAI_API_BASE`/`OPENAI_API_KEY` ke `/v1/chat/completions`). PyPI `oterm` 0.24.0 butuh Python >=3.10. Catatan Termux (known-broken, bukan blocker): `pip install oterm` di aarch64/Py3.14 diprediksi gagal build `jiter` (no Android wheel) → script handle hint + `exit 1`. `bash -n` clean; mode exec. Progres keseluruhan cli-tools **22/24**. Lanjut C5 gptme, C6 aichat.
- 2026-09-09: **cli-tools C5 gptme = done (OpenAI-compatible, verified)** — `scripts/cli-tools/gptme.sh` di-commit (`16d36f9`). Bukti `cli_presets.py:104` (`pip install gptme`) + `cli_presets.py:223` (`gptme` = `LAUNCH_VERIFIED`) + `cli_tools_router.py:595-612` (`_gptme_builder`: env `OPENAI_BASE_URL` = gateway base [gptme baca `OPENAI_BASE_URL` BUKAN `OPENAI_API_BASE`] + `OPENAI_API_KEY` + flag `-m local/<model>` ke `/v1/chat/completions`). PyPI `gptme` 0.33.0 butuh Python `>=3.10,<3.15`. Catatan Termux (known-broken, bukan blocker): `pip install gptme` di aarch64/Py3.14 diprediksi gagal build `jiter` (no Android wheel) → script handle hint + `exit 1`. `bash -n` clean; mode exec. Progres keseluruhan cli-tools **23/24**. Sisa: C6 aichat.
- 2026-09-09: **cli-tools C6 aichat = done (OpenAI-compatible, verified)** — `scripts/cli-tools/aichat.sh` di-commit (`1c4e592`). Bukti `cli_presets.py:105` (`cargo install aichat`) + `cli_presets.py:226` (`aichat` = `LAUNCH_VERIFIED`) + `cli_presets.py:242` (`TERMUX_INSTALL["aichat"]="pkg install aichat"`, "verified 0.30.0 runs" di Termux) + `cli_tools_router.py:469-511` (`_aichat_builder`: generate `aichat-aigate.yaml` client `aigate` openai-compatible {api_base=gateway, api_key}, set env `AICHAT_CONFIG_FILE`, model `aigate:<raw>` ke `/v1/chat/completions`). crates.io `aichat` 0.30.0 (Rust). Catatan Termux (terbukti WORKING, bukan blocker): `pkg install aichat` di Termux terbukti jalan (usable di Termux). `bash -n` clean; mode exec. **Progres keseluruhan cli-tools 24/24 (ALL DONE — A1–A12, B1–B6, C1–C6 SELESAI).**

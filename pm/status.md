# PM Status

## Spawned sub-agents (generated on demand)
- business-analyst (+skill) — dibuat saat doc creation (2026-09-03).
- system-analyst (+skill) — dibuat saat doc creation (2026-09-03).
- tech-architect (+skill) — dibuat saat doc creation (2026-09-03).
- be-dev (+skill) — dibuat 2026-09-03 (user arahkan siapkan semua spesialis
  implementasi di awal, override R1).
- fe-dev (+skill) — dibuat 2026-09-03.
- qa-engineer (+skill) — dibuat 2026-09-03.
- devops SUDAH dihapus 2026-09-03 (user: "hapus semua yg berkaitan devops").
- KEENAM di atas BELUM terdaftar di sesi berjalan (perlu restart opencode agar
  subagent_type terbaca). Jangan spawn sebelum restart → akan gagal
  "Unknown agent type".

## Rule log
- R1, R2, R3 added 2026-09-03 after user corrections (pre-creation of
  sub-agents and their skills, plus missing file boundaries).

## PRD edits (direct PM, no sub-agent)
- 2026-09-03 05:01: Tambah fitur terminal ke `documents/PRD.md`:
  - 2.5 Floating Control (toggle fullscreen + paste). 05:03: Paste juga
    mengembalikan fokus ke terminal aktif setelah menempel.
  - 2.5.1 Scroll & Swipe (trackpad/mouse; swipe→scroll, velocity-based, damping).
  - 2.6.1 Grouping tool CLI (Grup A agentic coding, Grup B autonomous agents,
    Grup C chat/shell), min 5 per grup, prioritas agentic.

## Doc creation plan (sequential, approved 2026-09-03)
- Mode: SEQUENTIAL (user pilih urut satu-satu).
- Urutan: (1) BRD -> business-analyst, (2) FSD+ERD -> system-analyst,
  (3) TSD -> tech-architect.
- Status: 2026-09-03 (1) BRD SELESAI, (2) FSD+ERD SELESAI, (3) TSD SELESAI
  (documents/architecture/TSD.md). KETIGA DOKUMEN SELESAI (mode sekuensial).
- Spesialis generated: business-analyst, system-analyst, tech-architect (+ skill).
  Belum terdaftar di sesi; pakai 'general' stand-in. Perlu reload utk pakai asli.
- Note: business-analyst agent file + skill SUDAH dibuat, tapi belum terdaftar
  di sesi berjalan (opencode perlu reload agar subagent_type terbaca). Fallback:
  pakai agen 'general' sebagai stand-in dengan brief & scope BA sampai reload.

## ADR resolusi (2026-09-03)
- ADR-007 (secrets): app lokal -> simpan di file biasa TANPA enkripsi, UI tanpa
  redaksi. RESOLVED.
- ADR-008 (proxy binding): level Endpoint; Endpoint -> Combo. RESOLVED.
- Tidak ada lagi ADR Proposed yang blokir implementasi.

## Doc creation plan 2 (execution docs)
- User pilih buat: #1 Backlog, #3 API Contract, #4 Test/QA Plan, #5 Dev Setup &
  Coding Standards, #6 Terminal UX Spec, #7 Config Schema. (#2 dicoret dari create
  karena sudah diputus jadi ADR resolusi, cukup dicatat di memory/status.)
- Mode: SEQUENTIAL (dipilih user). Eksekusi urut #1 -> #3 -> #4 -> #5 -> #6 -> #7.
- Status: 2026-09-03 #1 BACKLOG selesai; #3..#7 selesai dibuat (PM author,
  stand-in specialist; review via subagent asli setelah restart opencode).
-   Spesialis terkait: tech-architect (#3/#6/#7), qa-engineer (#4),
  business-analyst/PM (#1). Belum terdaftar di sesi; pakai 'general' stand-in
  atau minta user restart opencode.

## Implementation runner
- Command: `.opencode/commands/run-impl.md` -> `/run-impl [fresh|continue|status]`.
  `fresh` mulai B0.1; `continue` (default) lanjut task belum selesai; `status`
  tampilkan progres. Progres tersimpan di BACKLOG.md + pm/status.md supaya bisa
  dilanjut bila sesi terputus (batre/restart). Sesuai R9 (tanpa konfirmasi).
- **2026-09-03 (fresh):** aktif task = **B0.1** (Inisialisasi project). Mode fresh
  dijalankan setelah `/revise-docs` menambah desain UI AdminLTE (PRD §2.7, BRD §5.7,
  FSD §2.7, TSD §3.4, TEST_PLAN). Owner `be-dev`+`fe-dev`. Sub-agent SUDAH terdaftar
  di sesi berjalan (spawn langsung, bukan general stand-in).
- **2026-09-03 (fresh):** B0.1 SELESAI (be-dev: pyproject+server+test; fe-dev:
  src/frontend/static shell AdminLTE-like + sidebar collapse + tema + i18n EN/ID).
  Aktif task = **B0.2** (Config engine SQLite + skema ERD), owner `be-dev`.
  Lanjut otomatis tanpa konfirmasi (R9).
- **2026-09-03 (fresh):** B0.2 SELESAI (12 ERD entities + SQLAlchemy engine + init_db
  di lifespan). B0.3 SELESAI (config/secrets.py plaintext file store, ADR-007).
  FASE 0 SELESAI. **B1.1 sempat di-spawn lalu ter-cancel** (belum ada implementasi)
  — tetap pending. Setelah `/revise-docs` (dev mode/logging/self-heal), disisipkan
  **B0.4** (config di DB) & **B0.5** (logging infra) SEBELUM B1.1. Aktif task
  sekarang = **B0.4** (config storage di DB), owner `be-dev`. **PAUSED** by user
  2026-09-03 (user minta stop /run-impl) — tidak spawn task baru sampai user lanjut.
- **DECISION (ADR conflict resolve):** TSD §5.1 ms. Fernet encryption utk
  secret — TIDAK dipakai. ADR-007 SUDAH RESOLVED = secrets disimpan di file
  biasa TANPA enkripsi, UI tanpa redaksi (selaras BACKLOG B0.3 + SETUP.md).
  Semua sub-agent ikut resolved ADR-007, abaikan TSD §5.1. ADR-008 = binding
  ProxyPool di level Endpoint (FK proxy_pool_id) + override Combo.
- **2026-09-03 (user direction):** siapkan dulu spesialis implementasi
  (be-dev, fe-dev, qa) berdasarkan @documents/ — override R1 (jangan
  spawn `general`). Ketiga agent + skill SUDAH digenerate. devops dihapus
  (user: "hapus semua yg berkaitan devops"). Sesuai R3/R4, PM WAJIB minta
  user restart opencode agar terdaftar sebelum di-spawn.

## Doc revision 2026-09-03 (native run, no deployment)
- User request: "bisa gak semuanya berjalan secara native tanpa perlu
  deployment? kita pake python aja yang udah terbukti cross platform. Untuk
  frontend bebas lah"
- Keputusan: aigate dijalankan NATIVE sebagai aplikasi Python (cross-platform),
  TANPA deployment/container wajib, dan TANPA packaging single-binary. Frontend:
  kebebasan dev, baseline ADR-001 (Web UI lokal, vanilla JS SPA tanpa framework/build).
- ADR-009 (Native Python Execution) RESOLVED & ditambahkan ke TSD §2 + §8.
  ADR-005 (Packaging) DIHAPUS — packaging bukan scope project lagi.
- Docs di-update: PRD §5, BRD §4+§7, FSD §4, TSD (hapus ADR-005, tambah ADR-009
  + table), SETUP (install; hapus section Packaging), BACKLOG (B0.1 owner→be-dev+fe-dev,
  hapus B3.2). SKIP: ERD, API contract, TEST_PLAN, TERMINAL_UX, CLI_CONFIG.
- devops dihapus sepenuhnya (agent+skill+referensi). Folder infra/Dockerfile/.github/
  deploy tidak lagi jadi scope. aigate jalan tanpa itu.

## Revise-docs 2026-09-03 (AdminLTE UI shell) — SELESAI
- Request user: web UI bergaya AdminLTE; sidebar expand/collapse (collapse → ikon
  saja tanpa teks); switcher tema gelap/terang; multi-bahasa EN+ID (awal).
- UPDATE: PRD §2.7, BRD §5.7 (+§6 matrix), FSD §2.7 (+§5 matrix), TSD §3.4
  (+rekonsiliasi §5.1 & §8 ADR-007/ADR-008 → no-encryption, Accepted), TEST_PLAN
  (baris US-2.7.1/2.7.2/2.7.3).
- SKIP (alasan): ERD (preferensi UI di localStorage, tanpa entitas baru), API
  contract, Terminal UX (terminal-only), CLI config, Dev setup, Backlog.
- Keputusan default (R9): AdminLTE *ditiru secara visual* dengan vanilla CSS
  (tanpa Bootstrap/build) agar tetap memenuhi ADR-001. Ikon via Font Awesome CDN.
  Tema via CSS custom properties; i18n via kamus JS EN/ID; semua preferensi di
  localStorage (tanpa perubahan backend/DB).
- Laporan: `.opencode/reports/2026-09-03/revise-docs/0633_revise_docs_adminlte_ui.md`

## Revise-docs 2026-09-03 (Dev Mode, Logging & Self-Heal) — SELESAI
- Request user: run custom port + developer mode; dev-mode UI = simulasi perangkat
  (phone/tablet/desktop, phone BUKAN AdminLTE) + Log Window; Self-Heal di menu
  CLI-Tool (git branch + agentic CLI + fix/test loop dari log warning/error, popup
  bila tak ada CLI); aturan wajib logging (severity + stacktrace pd warn/err, DB,
  no empty catch) front+back; semua config di DB SQLite (bukan file).
- UPDATE (10): PRD §2.8, BRD §5.8 (+§6), FSD §2.8 (+§5), ERD (+LogEntry, +Setting),
  TSD §3.5 + ADR-010/011 (+ADR-007→DB plaintext), API contract (+/api/logs),
  SETUP (run cmd + config/secrets), CLI_CONFIG_SCHEMA (storage DB), TEST_PLAN
  (baris US-2.8.x), BACKLOG (+B0.4, +B0.5, +B1.5, +B1.6; B1.1 Dep→B0.5).
- SKIP: TERMINAL_UX (interaksi terminal tak berubah; self-heal flow ada di FSD/TSD).
- DEFAULT (R9): "config di DB" + "secret plain (ADR-007)" → secret plaintext di DB
  (kolom api_key dkk); file `secrets.json` B0.3 jadi legacy/opsional. No-empty-catch
  diberlakukan sebagai code-review gate (ADR-011).
- Laporan: `.opencode/reports/2026-09-03/revise-docs/0635_revise_docs_devmode_logging_selfheal.md`

## Revise-docs 2026-09-03 (Self-Heal: hapus LogEntry usai fix) — SELESAI
- Request user: "untuk proses self heal, setelah problem/bug/warning selesai dikerjakan
  langsung hapus row pada table log ya. jadi issue yang sama gak perlu di fix lagi."
- UPDATE: PRD §2.8 (self-heal (7) hapus LogEntry), BRD US-2.8.5 (acceptance (4)),
  FSD §2.8 (step 6b hapus LogEntry per-issue), TSD §3.5 (self-heal hapus LogEntry),
  TEST_PLAN (baris US-2.8.5 tambah penghapusan log).
- SKIP: ERD (tidak ada perubahan skema; penghapusan adalah perilaku runtime),
  API contract (penghapusan via DB internal self-heal, tak perlu endpoint baru),
  SETUP, CLI_CONFIG, TERMINAL_UX, BACKLOG.
- Aktif task tetap = **B0.4** (config di DB); B0.4 sempat 2x di-spawn lalu ter-cancel
  karena interupsi revise-docs — masih pending, akan di-spawn ulang.
- Laporan: `.opencode/reports/2026-09-03/revise-docs/0637_revise_docs_selfheal_delete_log.md`

## Revise-docs 2026-09-03 (Self-Heal: merge ke main + hapus branch) — SELESAI
- Request user: setelah self-heal pass, merge branch fixing ke main, switch ke main,
  hapus branch → next run pakai versi latest. (Lanjutan refine self-heal.)
- UPDATE: PRD §2.8 (self-heal (8) merge+checkout+delete), BRD US-2.8.5 (acc (5)),
  FSD §2.8 (step 7 merge/main/delete), TSD §3.5 (self-heal merge ke main + hapus
  branch), TEST_PLAN (baris US-2.8.5 tambah merge+hapus branch).
- SKIP: ERD (no schema change), API contract, SETUP, CLI_CONFIG, TERMINAL_UX,
  BACKLOG (task B1.6 sudah mencakup).
- STATUS RUN: /run-impl **PAUSED** by user 2026-09-03 — B0.4 tetap pending, tidak
  spawn hingga user lanjut.
- Laporan: `.opencode/reports/2026-09-03/revise-docs/0639_revise_docs_selfheal_merge_main.md`

## Testing Infra Setup 2026-09-03 — SELESAI (BE & FE, no CI)
- Request user: "BE & FE aja, CI gak perlu. langsung pasang dependency + bikin script test."
- BE (be-dev): `pyproject.toml` + dev extras (pytest, pytest-asyncio, respx, pytest-cov,
  factory-boy) + `[tool.pytest.ini_options]`; `tests/backend/conftest.py` (client +
  db_session fixtures), `test_health.py`, `test_respx_demo.py`, `test_gateway_pattern.py`
  (skipped placeholder for B1.1). Install: `uv pip install -e ".[dev]"`; run: `pytest tests/backend`.
- FE (fe-dev): `src/frontend/package.json` (vitest/jsdom/playwright devDeps + scripts),
  `vitest.config.js` (jsdom), `tests/i18n.test.js` (applyLocale EN/ID unit),
  `e2e/playwright.config.js` (webServer boots uvicorn :8080), `e2e/smoke.spec.js`.
  Install: `cd src/frontend && npm install` + `npx playwright install chromium`;
  run: `npm test` (vitest) / `npm run test:e2e` (playwright).
- CATATAN: sandbox ini tidak bisa `uv pip install`/`npm install` (no network /
  pydantic-core build) — config + script sudah siap; install dijalankan di env user.
- RUN STATUS: tetap **PAUSED** (user minta stop /run-impl). B0.4 masih pending.
- Laporan: `.opencode/reports/2026-09-03/setup/0640_setup_test_infra.md`

## Stack change 2026-09-03 (Termux-portable) — SELESAI
- Request user: "ganti stack biar jalan di semua platform termasuk Termux". User
  sempat nanya React Native/Expo → **ditolak** (Expo = native mobile app, bukan
  pengganti backend Python; tak ada PTY utk CLI). Solusi: buang `pydantic-core`
  (Rust) dengan pin `fastapi>=0.95,<0.100` + `pydantic>=1.10,<2` (Pydantic v1 pure
  Python). Semua dep inti jadi pure Python → nol compile Rust → jalan di Termux.
- Diedit: `pyproject.toml` (pin deps), TSD § ADR-002 (catatan portabilitas),
  memory-bank (risk resolved). Frontend TETAP vanilla JS + xterm.js (sudah portable).
- DEFAULT berikutnya: B1.1 (gateway) wajib pakai sintaks Pydantic **v1** (BaseModel
  v1) karena stack sekarang Pydantic v1. Catat di status agar sub-agent tidak pakai
  fitur v2.
- Status run: **FULL RESET** (backlog di-reset 2026-09-03, TANPA lock — semua
  task todo). next = **B0.1** (fresh dari awal). PAUSED sampai user bilang "lanjut".

## Zero-setup launcher + pywinpty 2026-09-03 — SELESAI
- Request user: tambah `pywinpty` (Windows) + bikin dep auto-install saat run agar user
  gak perlu repot. (Lanjutan dari keputusan stack Termux-portable.)
- be-dev: `pyproject.toml` + `"pywinpty; sys_platform=='win32'"`, `[project.scripts]
  aigate = "backend.launcher:main"`; `src/backend/launcher.py` (`main()` jalanin
  uvicorn dgn app, baca `--port`/env); `tests/backend/test_launcher.py` (monkeypatch
  uvicorn.run).
- PM: root `run.py` (shim) yg `ensure_deps()` → auto `pip install` tiap dep yg kurang
  (pywinpty otomatis di Windows), lalu panggil `backend.launcher:main`. SETUP.md
  di-update dgn opsi `python run.py` (zero-setup) + `aigate` console script.
- Catatan: first run butuh internet (download PyPI). Di env user, `pip install -e .`
  menyelesaikan versi dgn benar (sandbox punya mismatch pydantic/fastapi — bukan
  dari kode kita).
- Report: `.opencode/reports/2026-09-03/setup/0645_zero_setup_launcher.md`

## Pre-flight sebelum lanjut 2026-09-03 — SELESAI
- Fix kontradiksi doc: FSD §2.1 (masked/terenkripsi -> plaintext ADR-007) x4,
  BRD US-2.1.2 (masked/terenkripsi -> plaintext ADR-007/010) x1.
- Kodifikasi keputusan final jadi aturan tetap:
  R10 (Pydantic v1 / no Rust), R11 (secret+config DB plaintext), R12 (logging
  wajib ke DB, no empty catch), R13 (FE vanilla no-build), R14 (verifikasi
  sub-agent batas sandbox), R15 (jangan interupsi mid-run).
- Dampak: handover sub-agent jadi pendek & konsisten -> implementasi lebih cepat,
  lest error, gak perlu Q&A. Run siap dilanjut (B0.4).

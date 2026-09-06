# Memory Bank

## Project brief
(empty — diisi PM saat task pertama)

## Decisions
- 2026-09-03: Arsitektur agen PM + sub-agent spesialis (on-demand, scoped).

## Decisions
- 2026-09-07 (merge origin/main → refactor/ui, PR #4): konflik 5 file diselesaiin
  (merge commit `6000b2c`). (a) **Tabrakan rule nomor**: `main` nambah R23=routing, kita
  udah punya R23=reports → routing `main` udah dicakup **R29** kita, duplikat gak
  dimasukkan (no dobel nomor). (b) **Konflik fitur sidebar**: dua cabang bikin grouped-sidebar
  beda desain → **keep desain refactor/ui** (`nav-section`, lebih lengkap), versi `main`
  (`nav-group`) dibuang (redundan, fitur tetap ada). Dua-duanya DILAPORKAN ke user buat
  veto. Verifikasi: 0 marker, backend terminal 65/1skip, frontend 442 pass. PR #4 CLEAN.
- 2026-09-07 (R33 + relokasi Memory Bank): folder `pm/` DIHAPUS dari root → pindah ke
  **`documents/pm/`** (`git mv`, history ke-jejak). Alasan: root repo harus ramping;
  `documents/` = rumah mapan dokumen proyek (R5). 46 referensi `pm/` di 13 file
  (AGENTS.md, README.md, .opencode/agents/ProjectManager.md, .opencode/skills/
  pm-orchestration/SKILL.md, dokumen BACKLOG/TEST_PLAN/SETUP/CODE_CHANGES/BRD/TSD/FSD,
  + file pm itu sendiri) diselaraskan ke `documents/pm/`. src/** & tests/** = 0 referensi.
  Rule **R33** ditulis: dilarang bikin file/folder baru di root; artefak baru masuk folder
  per peruntukan; belum ada tempat → tanya user dulu.
- 2026-09-07 (R30): Kata "terminal" = fitur terminal aigate (multi-tab xterm + PTY WS),
  BUKAN terminal OS/emulator. Investigasi repo dulu sebelum jawab pertanyaan fitur.
- 2026-09-06 (i18n label policy): Label UI TIDAK boleh berupa string gabungan bilingual
  ("Kombo/Combos"). Satu key = satu nilai per locale. **Locale baru** cukup 3 hal, tanpa
  ubah kode: (1) blok kamus `window.I18N.<code>`, (2) entri registry `window.LANGS`
  `{code, flag, nameKey}` + key `lang.<code>`, (3) lengkapi key yang dipakai dinamis
  (mis. `combobox.group_combos`) — kelengkapan ini DIPAKSA oleh parity-guard test di
  `src/frontend/tests/`. Grup yang di-pin (`groupOrder`) selalu di-resolve ulang tiap
  fetch, jadi header ikut locale otomatis.
- 2026-09-06 (R29): SEMUA request user routing lewat PM; main thread dilarang
  implementasi. Kalau terlanjur dikerjakan di luar PM → PM audit diff, accept/re-work,
  delegasi re-work ke pemilik scope, baru catat + commit.

## Progress
- 2026-09-07: **Request Log kolom Model/Endpoint kosong — SELESAI (uncommitted,
  sekuensial BE→FE).** Root cause: combo ref → resolver `upstream_model=""` →
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
- 2026-09-06: Label teks tombol utama toolbar terminal dihapus; toolbar kini ikon-only dengan tooltip/ARIA, sedangkan label lengkap tetap di submenu. Vitest 395 passed (21 files).
- 2026-09-06: Toolbar terminal ditata ulang menjadi tiga dropdown berurutan: Paste (normal/code block), Settings (TUI passthrough/Keep Screen On), Full (Full Page/Fullscreen). Wiring, ARIA state, dan test fixture diselaraskan. Vitest 394 passed (21 files).
- 2026-09-06: Tooltip icon-only dibuat transient (tap auto-close 2 detik; Escape/outside/scroll/resize tetap menutup). State Full Page dan true Fullscreen dipisah eksplisit; hanya mode aktif yang biru, caret tidak aktif. Vitest 394 passed (21 files), terminal toolbar 62 passed.
- 2026-09-06: Terminal Keep Screen On dikembalikan dengan ikon perangkat yang lebih jelas (`fa-mobile-screen-button`). Popover tooltip global ditambahkan untuk kontrol ikon-only; mendukung hover, focus, tap, Escape, outside click, dan kontrol dinamis. Frontend Vitest 392 passed.
- 2026-09-06: Side menu dikelompokkan berdasarkan kebutuhan pengguna: Gateway Setup, Operations, Insights, System. EN/ID, aksesibilitas, dan test frontend diperbarui; Vitest 392 passed.
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

## Decisions
- 2026-09-06: Semua laporan wajib berada di `.opencode/reports/**`; root-level `reports/**` dihapus dan scope QA/agent diperbaiki sesuai R23.
- 2026-09-03: Terminal UX — swipe diubah jadi scroll (bukan navigasi TUI) karena
  TUI sering salah tangani swipe. Scroll velocity-based + damping agar natural.
  KOREKSI 2026-09-05: keputusan lama bikin swipe MATI di TUI (alt-buffer tidak
  punya scrollback, `term.scrollLines()` no-op di sana) dan terasa tidak natural
  di shell (arah dibalik + lompat per velocity). Sekarang swipe = event `wheel`
  sintetis ke elemen xterm -> xterm yang mapping: buffer normal scroll 1:1,
  alt-buffer kirim cursor key / mouse-wheel report ke aplikasi. Momentum rAF +
  friction. Tombol TUI jadi passthrough eksplisit (gesture mentah ke app).
  Doc diselaraskan: PRD §2.5.1, FSD §2.5.1, ux/TERMINAL_UX §2.
- 2026-09-03: CLI tool presets dikelompokkan; prioritas agentic CLI (claude, opencode, codex, gemini, antigravity, phi, aider, goose, amp, qwen, cline,
  kilo, dst). Dapat diperluas via YAML/JSON.
  KOREKSI 2026-09-05: (1) semua install pakai `pip install <nama>` padahal nama
  PyPI-nya milik proyek lain (codex=web server komik, gemini=framework DB
  genetika, claude-code=stub reserved, aichat=proyek lain) -> install string
  sekarang diverifikasi ke registry npm/PyPI (npm untuk CLI Node). (2) guard
  seed "skip kalau tabel sudah berisi" bikin semua fix preset jadi dead code ->
  jadi UPSERT idempoten (kolom preset disegarkan, `enabled` + baris user utuh).
  (3) flag tebakan (`claude openai-compatible`) dihapus: bentuk launch milik
  builder. (4) registry `LAUNCH_SUPPORT` (verified/pending/unsupported + reason
  code) = sumber kebenaran di kode, bukan kolom DB; UI mencoret nama yang belum
  verified, `resolve` menolak 409. Builder per-tool: satu per satu, 1 commit/tool.
- 2026-09-03 (TSD ADRs): GUI = web UI lokal (FastAPI static + xterm.js);
  PTY = ptyprocess/pywinpty + xterm.js via WebSocket; swipe exception =
  SwipeException registry + per-tab tui_mode.
  - ADR-007 (secrets): RESOLVED — app lokal, simpan di file biasa TANPA enkripsi,
    UI tidak perlu redaksi/masking. (putus 2026-09-03)
  - ADR-008 (proxy binding): RESOLVED — binding di level Endpoint; Endpoint
    menunjuk ke Combo (Endpoint -> Combo). (putus 2026-09-03)

- 2026-09-06: Semua input user diroute ke `@ProjectManager` sebagai entrypoint
  tunggal melalui `.opencode/rules/request-routing.md`; instruksi priority lebih
  tinggi tetap berlaku.
- 2026-09-06: Durable request-routing rule selesai dibuat. (Di `main` dinomori
  **R23**; di branch `refactor/ui` konsep yang sama = **R29** — lihat
  `documents/pm/OPERATING_RULES.md`. Saat merge #4, duplikat R23-routing `main`
  tidak dimasukkan karena sudah tercakup R29.)

## Open risks
- Agent file business-analyst / system-analyst / tech-architect SUDAH dibuat tapi
  belum terdaftar di sesi berjalan; perlu reload opencode agar bisa dipakai sbg
  subagent_type asli (selama ini pakai 'general' stand-in).
- ADR-007 & ADR-008 SUDAH RESOLVED (2026-09-03) — lihat Decisions. Tidak ada
  lagi ADR Proposed yang blokir implementasi.
- **Termux runtime risk:** RESOLVED (2026-09-03) — user pilih opsi (C): pin
  `fastapi>=0.95,<0.100` + `pydantic>=1.10,<2` (Pydantic v1 pure Python, tanpa
  pydantic-core/Rust). Semua dep inti pure Python → aigate jalan di Termux & semua
  platform tanpa compile Rust. Expo/React Native ditolak (bukan pengganti backend
   Python; tak kasih PTY utk CLI). Lihat TSD ADR-002.

## Tooling
- 2026-09-06: **codegraph = colbymchenry/codegraph (BUKAN xnuinside)**. User rujuk repo
  https://github.com/colbymchenry/codegraph. PM sempat salah pakai xnuinside/codegraph
  (v1.2.0 pip, se-nama) → di-uninstall & diganti yang benar (R27).
- Install (global, BUKAN dep project — R26): `npm i -g @colbymchenry/codegraph`
  (v1.6.0). `codegraph init` di project root → bangun indeks di `.codegraph/`
  (`codegraph.db` 11.3MB). Hasil: **121 files (80 py + 41 js), 2,851 nodes, 9,151
  edges** in 2.0s. `codegraph status` → "Index is up to date".
- **Termux/Android workaround (wajib, env luar repo):** tool ini Rust-kernel + bundled
  Node glibc; di Termux gak ada build `android-arm64` & binary glibc butuh loader yg
  gak ada. 3 patch (lihat CODE_CHANGES.md Environment): (1) force `target='linux-arm64'`
  di shim; (2) shebang shim → node absolut; (3) launcher bundle exec `node` lewat loader
  glibc `/usr/glibc/lib/ld-linux-aarch64.so.1` (loader glibc Termux ada & jalan).
  Tanpa patch `codegraph` gagal total di Termux. Patch di env global / cache bundle —
  hilang kalau npm reinstall / bundle dihapus.
- Catatan: 1 baris error pasca-init `error while loading shared libraries: -e:` (spawn
  daemon auto-sync gagal di Termux) — indeks tetap ke-build utuh & query-able. Auto-sync
  watcher mungkin gak jalan di Termux; rebuild manual via `codegraph init` bila perlu.
- RULE BARU **R28**: baca kode HARUS lewat codegraph dulu (dapet path + line) baru baca
  file yg bersangkutan — hemat token, hindari broad grep/Explore. Reinit via
  `codegraph init` kalau index usang. Berlaku utk PM + semua sub-agent.

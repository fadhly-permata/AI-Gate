# Code Changes Register (code ↔ docs alignment)

## 2026-09-09 (lanjutan) — Bottom-nav ponsel: mirror 9 view + link Repo + separator grup — DONE (BELUM di-commit)

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

## 2026-09-09 — Phone shell: hamburger disembunyikan + bottom-nav scroll horizontal — DONE (BELUM di-commit)

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

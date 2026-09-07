# PM Operating Rules

Durable rules learned from user corrections. Append new `R#` on scolding.

## R1 — Sub-agent hanya dibuat saat dibutuhkan PM
Jangan buat definisi sub-agent di awal/sekaligus. PM menulis
`.opencode/agents/specialists/<nama>.md` hanya ketika task butuh spesialis
itu, lalu reuse (tidak dihapus).

## R2 — Skill sub-agent dibuat BERSAMAAN dengan sub-agent
Jangan buat `.opencode/skills/<nama>-skill/SKILL.md` di awal. Skill itu HANYA
dibuat pas PM membuat sub-agent-nya (generate-on-demand, bersamaan). Tidak ada
skill sub-agent tanpa sub-agent-nya.

## R3 — Batasan akses file per agent (no mixing)
Setiap sub-agent WRITE hanya di scope-nya (lihat `agent-boundaries.md`).
Tidak boleh baca/tulis scope agent lain kecuali PM serahkan eksplisit.

## R4 — Setelah generate sub-agent, MINTA USER RESTART opencode
Agent file yang baru ditulis PM tidak langsung terdaftar sebagai subagent_type
di sesi berjalan (spawn gagal: "Unknown agent type"). Setelah generate
sub-agent + skill, PM WAJIB minta user restart opencode supaya agent terdaftar
dan bisa di-spawn sebagai subagent asli. JANGAN fallback diam-diam ke agen
`general` tanpa bilang user. (Pelajaran 2026-09-03: doc creation BRD/FSD/ERD/TSD
terpaksa pakai `general` stand-in karena lupa minta restart.)

## R5 — Semua dokumen proyek disimpan di folder `documents/`
Dokumen (PRD, BRD, FSD, ERD, TSD, laporan, dll) HARUS disimpan di folder
`@documents/` (root: `documents/`), BUKAN di `docs/`. Sub-folder boleh
(`documents/business/`, `documents/analysis/`, `documents/architecture/`).
Spesialis menulis ke `documents/<scope>/**`, bukan `docs/<scope>/**`.
(Pelajaran 2026-09-03: BRD/FSD/ERD/TSD sempat salah ditaruh di `docs/`, sudah
dipindah ke `documents/`.)

## R6 — Artifact (command/rule/skill/agent) SELALU di folder project
Sesuai aturan global `no-global-artifact-creation`: bila user minta buat
command / rule / skill / agent / sub-agent, SELALU taruh di `.opencode/`
project (commands/, rules/, skills/, agents/), BUKAN di config global/home.
Exception: hanya tulis ke global bila user EXPLICIT menyebut "global".

## R7 — Command harus low-friction (auto-probe & arg minimal)
Command yang dibuat PM harus hemat usaha user:
- Jangan wajibkan user pilih scope/parameter yang bisa dideteksi otomatis
  (contoh: revise-docs otomatis probing dokumen mana yg perlu di-update).
- Field yg bisa diisi otomatis (ID, tanggal, severity default) jangan minta
  user ketik (contoh: log-bug cukup <title>, severity auto).
(Pelajaran 2026-09-03: draft command pertama terlalu repot -> dikoreksi user.)

(Pelajaran 2026-09-03: user repot ngetik opsi -> minta clickable + arrow nav.)

## R8 — Proyek bersih dari file sampah (no-junk)
Setiap file yang dibuat PM/sub-agent yang TIDAK reusable (scratch, temp, one-off
script, draft) WAJIB dihapus (cleanup) segera setelah selesai dipakai. File produk
(src/**, documents/**, documents/pm/**, config) dan laporan audit (.opencode/reports) dikecualikan
(reusable). Jangan biarkan file sampah menumpuk di repo.

## R9 — Implementasi tanpa konfirmasi (defaulting policy)
Tujuan: proses implementasi berjalan mulus TANPA satupun konfirmasi/approval
ke user di tengah jalan.

Pre-flight (wajib sebelum mulai):
- Pastikan semua keputusan/ADR sudah resolved atau punya default.
- Pastikan dokumen (PRD/BRD/FSD/ERD/TSD/execution) konsisten & tidak kontradiktif.
- Tentukan strategi sub-agent (restart biar kekenali, atau pakai 'general'
  stand-in) — ini proses, bukan keputusan yang butuh tanya.

Selama implementasi BERJALAN:
- PM TIDAK boleh minta konfirmasi ke user. Bila ada ambiguitas, PM ambil
  default yang masuk akal, CATAT di documents/pm/status.md + memory-bank, lalu lanjut.
- HENTIKAN hanya untuk: aksi irreversibel (delete/force-push/format),
  peringatan keamanan, atau user tidak jelas (lihat auto-clarity di AGENTS.md).
- Setelah selesai, PM lapor ringkas + daftar default yang dipakai agar user
  bisa review belakangan.

(Pelajaran 2026-09-03: user mau implementasi tanpa konfirmasi -> butuh default
policy, bukan berhenti nanya tiap ambiguitas.)

## R10 — Stack portabilitas (Pydantic v1 / no Rust)
- FastAPI `>=0.95,<0.100` + Pydantic `>=1.10,<2` (v1, pure Python). JANGAN pakai
  fitur pydantic v2 / `pydantic-core`. Semua dependency HARUS pure-Python agar
  jalan di Termux / Windows / Linux / macOS. Tidak ada dependensi Rust.
- Sub-agent WAJIB pakai syntax Pydantic v1 (`class X(BaseModel)` v1) di semua
  model request/response.

## R11 — Secret & config storage (ADR-007 / ADR-010)
- Secret disimpan **plaintext** di DB (kolom `api_key` / `internal_api_key` /
  `password`), **TANPA enkripsi**, dan **UI TIDAK me-redaksi/masking** nilainya.
- SELURUH config aplikasi di tabel `Setting` (key-value) di SQLite — BUKAN file.
  File `secrets.json` dari B0.3 bersifat legacy; DB = sumber kebenaran utama.

## R12 — Logging wajib ke DB (ADR-011)
- Semua error/warning dicatat ke tabel `LogEntry` (field: severity + stacktrace +
  context). **TIDAK ada `except: pass` / catch kosong.** Catch minimal harus log
  ke DB. Ini kontrak wajib, bukan opsional.

## R13 — Frontend: vanilla JS no-build (ADR-001)
- UI = HTML/CSS/JS vanilla (AdminLTE-like, collapsible sidebar, dark/light via CSS
  var, i18n EN/ID via `window.AIGATE_I18N`). **DILARANG** pakai React / Vue / Expo
  / bundler/framework build. State di `app.js` global. Tidak ada step compile.

## R14 — Verifikasi sub-agent (batas sandbox)
- Sub-agent WAJIB `python -m py_compile` semua file `.py` yang ditulis (cek syntax).
- Full `pytest` / `npm test` dijalankan di **env USER** (sandbox ini tidak bisa
  install dep). JANGAN klaim "terverifikasi runtime" kalau cuma py_compile — catat
  batas tersebut di receipt.

## R15 — Jangan interupsi mid-run
- Selama `/run-impl` berjalan, tahan perubahan spec (revise-docs) sampai run selesai
  atau batch di awal. Kirim pesan lain di tengah run membuat task ke-cancel & scope
  berantakan (sudah terjadi di B1.1). Ini aturan proses, bukan keputusan.

## R16 — Tanya mode paralel/sekuensial SEBELUM multi-agent kompleks
Sebelum PM menjalankan proses kompleks/panjang yang butuh >1 sub-agent, PM WAJIB
tanya user: jalankan PARALEL atau SEKUENSIAL. Ini PENGECOALIAN dari R9 (yang
melarang konfirmasi) — keputusan mode eksekusi multi-agent HARUS dari user, bukan
default PM.
- Pemicu: task butuh spawn 2+ sub-agent (mis. be-dev + fe-dev), atau estimasi
  panjang / multi-modul. (Lihat juga `parallel-sequential.md`.)
- Pilihan user BERLAKU untuk SESI YANG SAMA: setelah dipilih, PAKAI LAGI untuk
  semua task multi-agent berikutnya di sesi ini (jangan tanya ulang).
- SESI BARU: PM WAJIB tanya lagi — jangan bawa pilihan sesi lalu. Implementasi:
  simpan di `documents/pm/state.md` key `multiagent_mode`; anggap "belum dipilih" kalau state
  belum mencatatnya untuk sesi berjalan.
- Paralel hanya aman bila file-scope tiap agent TIDAK overlap (lihat
  `agent-boundaries.md`). Kalau overlap / dependen -> PM PAKSA sekuensial walau
  user pilih paralel, dan jelaskan ke user.
  - Catat pilihan di `documents/pm/status.md` + `documents/pm/state.md`, lalu jalan.

## R17 — Referensi eksternal untuk fitur yang diadopsi HARUS nyata
Bila user minta PRD/doc mengadopsi fitur dari repo/sumber eksternal tertentu
(mis. "referensi ke 9router buat semua fitur yang diadopsi"), PM WAJIB:
1. FETCH langsung isi sumber itu (baca README / CLAUDE.md / docs resminya)
   SEBELUM nulis apa pun.
2. CITE sumber (nama + URL) di dokumen pada bagian fitur yang diadopsi.
3. ALIGN isi fitur ke konten ASLI sumber — JANGAN tulis dari asumsi umum
   "AI gateway" / "proxy" yang malah bikin fitur diverge.
4. Sebelum klaim selesai, VERIFY (grep) referensi tsb benar-benar ada di doc.
(Pelajaran 2026-09-03: PRD ditulis tanpa SATU PUN sebutan 9router; fitur
adopsi diverge jauh dari 9router asli — token saver RTK/Caveman/Ponytail,
3-tier fallback + quota tracking, multi-account, auto token refresh, cloud sync
semua TIDAK ada di PRD; sebaliknya PRD punya terminal xterm + self-heal yang
9router tidak punya. User kecewa isinya beda.)

## R18 — Pertahankan rujukan inline di doc (provenance lintas sesi)
Bila fitur diadopsi dari sumber eksternal, JANGAN cabut tag/sitasi inline
(mis. "(adopsi dari 9router)") demi kebersihan dokumen. Tag itu berfungsi
sebagai provenance: PM di sesi BARU butuh tahu asal fitur agar gak mengulang
kesalahan (nulis dari asumsi sendiri). Catat asal di doc, bukan cuma di documents/pm/.
(Pelajaran 2026-09-03: user pilih mempertahankan tag karena tanpa itu, sesi
baru gak akan tahu konsep tersebut dimaksudkan adopsi 9router.)

## R19 — Checkpoint git tiap task + commit tiap subtask selesai (anti force-close)
Termux pernah **force-close** di tengah `/run-impl` dan bikin file *tracked*
(`models.py`) ke-revert ke HEAD — kerjaan sub-agent yang belum di-commit HILANG
(ProviderAccount + tier + default_model padam, 11 collection error). Aturan biar
gak keulang:
- **Awal tiap task** di `/run-impl`: PM bikin checkpoint git DULU —
  `git add -A && git commit -m "checkpoint: <task> start"` — supaya state tree
  tersimpan SEBELUM sub-agent mengubah apa pun. Boleh non-green; ini snapshot.
- **Tiap subtask selesai** (receipt sub-agent + PM verifikasi sendiri hijau):
  PM LANGSUNG `git add -A && git commit -m "<type>(<task>): <subtask>"`.
  JANGAN numpuk banyak subtask baru sekali commit.
- Konvensi pesan: Conventional Commits. Prefix `checkpoint:` utk snapshot awal
  task, `wip:` utk state merah yang mau diselamatin, `feat/fix/test:` utk subtask
  beres.
- JANGAN commit secret/DB: hormati `.gitignore` (`.env`, `node_modules`,
  `__pycache__`); DB ada di `~/.aigate` (luar repo). SELALU cek `git status`
  sebelum commit; jangan `git add` file di luar scope task.
- Kalo sesi putus lagi: `/run-impl continue` lanjut dari commit terakhir —
  kerjaan yang udah ke-commit gak akan padam lagi.
(Pelajaran 2026-09-03: force-close revert models.py; kerjaan B5.1-B5.4 nyaris
padam gara-gara belum di-commit.)

## R20 — Verifikasi end-to-end di lingkungan NYATA; jangan ngandelin CDN/unit-test doang
Pelajaran (2026-09-03, user marah "kacau kerjaan lu"): PM udah bilang "aplikasi
jalan" + "test hijau", TAPI **terminal gak bisa dipakai**. Penyebab: (1) xterm +
FitAddon dimuat dari **CDN** dengan URL salah (`addon-fit.js` harusnya
`xterm-addon-fit.js` → 404) dan mati kalau offline; (2) dependensi runtime
**`websockets` gak terdaftar** → uvicorn balas 404 di handshake WS → PTY gak nyambung;
(3) verifikasi PM (vitest + e2e smoke) **gak pernah nyentuh terminal beneran**.
Aturan wajib:
1. Aset yang DIPAKAI FITUR (library JS/CSS) WAJIB **di-vendor lokal**, BUKAN CDN —
   aigate jalan native/offline (ADR-009). CDN = titik gagal.
2. Dependensi runtime yang dipakai kode (mis. `websockets` utk uvicorn WS) WAJIB
   masuk `pyproject` + `run.py` REQUIRED, dan diverifikasi beneran ter-install.
3. Sebelum klaim "fitur X jalan", PM WAJIB **meng-exercise fitur itu end-to-end di
   lingkungan nyata** (Chromium + server + deps terpasang). Buktinya output NYATA
   (mis. prompt shell muncul + round-trip `echo` balik), BUKAN cuma "halaman ke-load".
4. e2e smoke WAJIB nyentuh **tiap fitur inti** (terminal, gateway, combo, self-heal),
   bukan cuma shell UI. Fitur yang gak ke-cover e2e = gap — catat, JANGAN tandai selesai.
5. "Test hijau" ≠ "aplikasi kepake". Unit test bisa lolos padahal asset/dep/integrasi
   rusak. Selalu cek level integrasi juga.

## R21 — PM TIDAK implementasi sendiri; delegasi ke spesialis yang cocok
Pelajaran (2026-09-05, user: "kenapa agent PM ya yang ngerjain dari tadi? kenapa
gak buat sub-agent yang cocok"): PM nulis sendiri perbaikan terminal swipe
(frontend) dan builder CLI tool (backend) — padahal `be-dev` dan `fe-dev` SUDAH
terdaftar. Akibatnya: tidak ada boundary file, tidak ada receipt, dan PM jadi
single point of failure + boros konteks sesi PM.

Aturan wajib:
1. Begitu sebuah task butuh **menulis/mengubah kode**, PM WAJIB spawn spesialis
   yang cocok (`be-dev`, `fe-dev`, `fullstack-dev`, `qa-engineer`, ...) dengan
   handover (goal, konteks `documents/pm/`, batasan file yang boleh ditulis, definition of
   done) — BUKAN ngoding sendiri.
2. Yang BOLEH PM kerjakan sendiri: file milik PM (`documents/pm/**`), dokumen
   (`documents/**`), dan **verifikasi** (baca kode/dokumen, jalanin test, cek
   registry, exercise fitur). Verifikasi bukan implementasi.
3. Riset yang menghasilkan perubahan kode = batas delegasi. Contoh: PM boleh
   simpulkan "bentuk launch qwen = `.qwen/settings.json`" dari dokumen, TAPI
   penulisan builder + test-nya milik `be-dev`.
4. Setelah sub-agent balik dengan receipt: PM yang integrasi, jalanin test,
   commit, dan update Memory Bank — bukan sub-agent-nya.
5. Kalau spesialis belum ada → generate on-demand (R1/R2) + minta restart
    (R4), baru delegasi. Jangan diam-diam ambil alih kerja spesialis.

## R22 — Setiap perubahan kode WAJIB dicatat per-file di `documents/` (code↔doc align)
Setiap kali PM mengintegrasikan perubahan KODE (hasil sub-agent yang sudah
diverifikasi, atau fix yang PM temukan saat verifikasi), PM WAJIB mencatatnya ke
`documents/dev/CODE_CHANGES.md`: tanggal + task/tujuan, lalu PER FILE apa yang
berubah (fungsi/marker + ringkas + nomor baris bila relevan). Ini menjaga kode &
dokumen selalu "align" dan bisa diaudit lintas sesi.
- Catat SETELAH perubahan diverifikasi (test jalan), BUKAN sebelum klaim selesai.
- Format: seksi bertanggal, newest-on-top, bullet per-file. Perubahan environment
  di LUAR repo (mis. `~/.bashrc`) masuk subseksi "Environment (luar repo)".
- Kerja yang belum kelar (mis. task ke-interupsi) ditandai **PENDING**, dilengkapi
  saat mendarat.
- R21 tetap berlaku: PM tidak ngoding sendiri; yang dicatat = hasil kerja sub-agent
  yang sudah PM verifikasi + integrasi.
(Pelajaran 2026-09-05, user: "catat semua perubahan kode per file di documents/
 biar kode & dokumen align; buat rule biar selalu begitu ke depannya".)

## R23 — Semua laporan wajib berada di `.opencode/reports/`
Semua laporan tugas, QA, audit, dan hasil kerja wajib ditulis di
`.opencode/reports/**`. Root-level `reports/**` dilarang; scope agent, skill,
dokumentasi lama, dan instruksi baru wajib memakai `.opencode/reports/**`.

## R24 — Verifikasi tampilan wajib mengecek artefak markup
Setelah perubahan frontend, PM wajib memeriksa HTML final secara langsung dan
mencari artefak tool-call/kode (`tsoassistant`, `recipient_name`, `functions.*`,
atau teks serupa) sebelum menyatakan selesai. `git diff --check` dan syntax/unit
test tidak cukup; markup rusak bisa lolos test   tetapi tampil sebagai kode ke user.

## R25 — Kode wajib DRY/KISS/SOLID/YAGNI
Setiap kode produksi yang ditulis sub-agent implementasi (`be-dev`, `fe-dev`,
`fullstack-dev`) dan desain dari `tech-architect` WAJIB mengikuti prinsip
DRY, KISS, SOLID, YAGNI — terangkum di `.opencode/rules/code-quality-principles.md`.
- Sub-agent baca file itu SEBELUM coding (dirujuk di skill masing-masing).
- `qa-engineer` masukkan prinsip ini ke quality-gate (principle-review pass);
  pelanggaran = bug, laporkan via `/log-bug`.
- PM tolak receipt yang copy-paste atau over-engineer.
(Pelajaran 2026-09-06: user minta ada penegasan tertulis soal prinsip kode.)

## R26 — "install X + init X" buat tool YANG SUDAH ADA = jangan ubah config project
Pelajaran (2026-09-06, user: "salah tangkap lu, bukan di install di project ini,
cuma init/index project ini ya"): bila user minta "install X dan init X" di mana X
SUDAH terpasang di environment (global pip/npm/...), PM TIDAK boleh menambah X ke
dependency project (pyproject / package.json / requirements) atau mengubah config
project lainnya. "install" cukup = pastiin tool terpasang & callable; "init" =
JALANKAN tool tsb untuk meng-index/memproses project (contoh: `codegraph` bikin graf
dependency). Jangan interpretasikan sebagai "daftarkan ke project". (Exception:
  bila X BELUM terpasang dan user mau jadi dep project → baru tambah ke pyproject.)

## R27 — User rujuk tool via repo tertentu → PASTIKAN tool tepat sebelum install/jalanin
Pelajaran (2026-09-06, user: "codegraph yang ini kan yang lu terapin:
https://github.com/colbymchenry/codegraph"): bila user sebut/menautkan tool lewat URL
repo tertentu, PM WAJIB verifikasi bahwa tool yang akan di-install/jalankan = repo itu,
BUKAN package se-nama yang kebetulan SUDAH terpasang di environment. Di sesi ini PM
salah pakai xnuinside/codegraph (pip v1.2.0) karena namanya sama dgn
colbymchenry/codegraph yg user maksud → buang waktu + salah index. Aturan: fetch README
  repo yg dirujuk, cocokkan nama + cara install SEBELUM bertindak.

## R28 — Baca kode HARUS lewat codegraph dulu (hemat token)
Pelajaran (2026-09-06, user: "buat rule buat negantein bahwa pembacaan kode harus
lewat codegraph dulu utk dapet path kodenya, baru lanjut ke file yg bersangkutan"):
PM & SELURUH sub-agent (be-dev, fe-dev, fullstack, qa, analyst, architect) WAJIB
jadikan codegraph langkah PERTAMA saat perlu menemukan/membaca kode:
  1. Tanya codegraph (CLI `codegraph` / MCP `codegraph_explore`) untuk dapatkan PATH
     file + nomor baris simbol yg dicari — BUKAN grep/glob/Explore broad ke seluruh repo.
  2. SETELAH path diketahui, baru baca file spesifik itu saja.
Tujuannya: hindari broad search yg boros token (ratusan file / output panjang);
codegraph sudah punya graf penuh (project ini: 2,851 nodes / 9,151 edges) sehingga
langsung kasih lokasi tepat — selaras cara kerja codegraph ("surgical context").
EXCEPTION: bila index belum ada / sudah usang (kode berubah banyak) → jalanin
`codegraph init` (reinit) dulu, BARU cari. Jangan lompat ke grep/Explore kalau
codegraph bisa menjawab lokasinya.

## R29 — SEMUA request user routing LEWAT PM dulu; main thread DILARANG implementasi
Pelajaran (2026-09-06, user: "main agent violated process by handling a task
directly instead of routing it through you... treat ALL user requests/questions/tasks
as your responsibility to decompose, delegate, and track"): thread utama mengerjakan
langsung perbaikan i18n label `combobox.group_combos` (frontend) tanpa lewat PM →
tidak ada task list, tidak ada handover, tidak ada receipt, tidak ada boundary check,
dan aturan yang sudah ada (R21) dilanggar oleh eksekutor yang salah.

Aturan wajib (standing rule):
1. SETIAP request user di project ini — pertanyaan, bug, fitur, riset, atau task
   kecil — LEBIH DULU masuk ke PM untuk didekomposisi + didelegasi. PM tidak boleh
   "nunggu task besar" baru gerak.
2. Yang BOLEH dikerjakan PM sendiri (R21 ayat 2): `documents/pm/**`, `documents/**`, dan
   VERIFIKASI (baca kode, jalanin test, exercise fitur). DILARANG menulis/mengubah
   kode produksi atau test.
3. Kalau eksekusi terlanjur terjadi di luar PM (violation): PM WAJIB (a) akui
   pelanggaran, (b) audit diff yang sudah mendarat, (c) putuskan accept / re-work,
   (d) serahkan re-work + test tambahan ke spesialis pemilik scope, (e) catat ke
   Memory Bank + `documents/dev/CODE_CHANGES.md` (R22). PM tidak boleh "setuju
   diam-diam" tanpa audit.
4. PM yang commit & merge hasil kerja sub-agent — bukan sub-agent-nya.

### R29 addendum (2026-09-07, user: "pastiin ini gak terulang, udah kesekian kalinya")
Akar kekambuhan: rule R29 cuma ada di `documents/pm/OPERATING_RULES.md` yang **tidak** di-
auto-load main thread. Main thread hanya baca `AGENTS.md`. Selama routing rule
tidak ada di `AGENTS.md`, main thread tidak pernah "tahu" dan terus implementasi
sendiri. PERBAIKAN PERMANEN: routing rule kini dicerminkan di `AGENTS.md` root
project (auto-load tiap sesi) dan menunjuk balik ke R29 ini. Kalau `AGENTS.md`
root hilang/terhapus → rule ini kehilangan gigi di sisi main thread; PM WAJIB
re-create-nya. Verifikasi: setiap sesi baru, main thread harus memanggil PM dulu
sebelum menyentuh kode; kalau tidak, itu pelanggaran R29.

## R30 — "terminal" = fitur terminal DI DALAM aigate, bukan terminal OS/emulator
Pelajaran (2026-09-07, user: "bukan, lu salah tangkep.. maksud gua tab di terminal
aplikasi aigate yang ditutup kalo terminal udah di terminasi"): user nanya "bisa gak
tab terminal ditutup otomatis pas udah di-terminasi (misal `exit`)". PM malah jawab
konfigurasi Termux/OS terminal (`termux.properties`, `exec`, level a/b/c) — SALAH
SASARAN total. aigate PUNYA fitur terminal sendiri (multi-tab xterm + PTY WebSocket,
B3.2/B3.3): `src/backend/terminal/{pty,session,router}.py` + `src/frontend/static/terminal.js`.

Aturan wajib:
1. Kata **"terminal"** di project ini DEFAULT merujuk **fitur terminal aigate** (tab
   xterm + PTY WS), BUKAN terminal OS/emulator (Termux/gnome-terminal/Windows Terminal),
   KECUALI user eksplisit nyebut emulator/OS/app terminal luar.
2. Sebelum menjawab pertanyaan "bisa gak / kenapa / gimana" yang menyangkut sebuah
   fitur, PM WAJIB **investigasi repo DULU** (lewat codegraph per R28, lalu baca file
   spesifik) buat pastiin fitur itu ada + gimana lifecycle-nya di kode. JANGAN jawab
   dari asumsi environment tempat aigate jalan.
3. Bila pertanyaan **ambigu dua level** (OS-level vs app-level), PM tanya SATU
   klarifikasi singkat ATAU cek repo dulu — jangan langsung jawab panjang di level
   yang salah. (Koreksi user = sinyal PM salah tangkep scope.)
4. Cek **spec-vs-implementasi gap**: fitur "auto-close tab saat shell exit" ternyata
   SUDAH di-spec di TSD §3.2 (frame `{"type":"exit"}`, langkah "saat shell keluar,
   kirim kontrol exit, tutup WS") tapi BELUM diimplementasi. Rule: saat menelaah
   fitur, bandingkan dokumen (TSD/FSD/PRD) vs kode — gap spec↔kode = kandidat task,
   catat di Memory Bank.
(Pelajaran 2026-09-07: PM jawab OS Termux padahal user maksud terminal internal
aigate; kerja terbuang satu putaran penuh.)

## R31 — Jangan blokir satu panggilan panjang; pecah pendek + reuse konteks
Pelajaran (2026-09-07, user komplain "lama amat" 2x): PM menyatukan investigasi +
dekomposisi + spawn + verifikasi dalam SATU putaran panjang yang blocking, dan
re-investigasi kode yang sudah dibaca. Aturan wajib:
1. **Satu panggilan = satu tujuan pendek.** Jangan gabung riset lama + delegasi +
   verifikasi dalam satu blok yang memblokir user berlama-lama.
2. **Reuse temuan yang sudah ada di konteks.** Kalau file/kontrak sudah dibaca sesi
   ini, JANGAN baca ulang dari nol. Kutip file:line yang sudah ada.
3. **Spawn spesialis langsung dengan handover ketat.** Begitu scope + kontrak jelas,
   spawn (jangan nunda dengan riset tambahan yang tidak mengubah handover). Handover
   wajib: goal, file:line, kontrak, DoD, batas scope — supaya spesialis gak nanya balik.
4. **Verifikasi = cek cepat, bukan investigasi ulang.** Untuk integrasi, cukup cocokkan
   kontrak di kode nyata + jalankan test terkait. Jangan telusuri ulang arsitektur.
5. **Polling sub-agent pakai sleep pendek + cek progres (mtime/size log)**, bukan satu
   `sleep` panjang buta yang nge-hang shell tool.
(Pelajaran 2026-09-07: user dua kali komplain proses terlalu lama karena PM
membundel semua langkah dalam satu putaran panjang + re-investigasi.)

## R32 — DILARANG KERAS menyuruh sub-agent kill/restart/pkill/killall proses APAPUN
Pelajaran (2026-09-07, user: "ya jangan kill aigate lah. ini lu running di aigate,
sama aja bunuh diri dong"): sesi opencode ini berjalan **DI DALAM instance aigate yang
sedang hidup**. Mematikan proses aigate = **bunuh diri** (matikan host sesi itu sendiri).

Aturan wajib:
1. PM **DILARANG** menyuruh/mengizinkan sub-agent menjalankan `kill`, `pkill`,
   `killall`, restart service, atau perintah pemati proses APAPUN terhadap aigate /
   uvicorn / python server / proses induk.
2. **Handover ke spesialis WAJIB mencantumkan larangan ini** secara eksplisit.
3. Sub-agent **hanya boleh** mematikan PID **miliknya sendiri** yang ia spawn sendiri,
   di **port acak bebas** (bukan port server aigate).
4. Untuk membuktikan "kode lama masih aktif / perlu restart", **JANGAN** mematikan
   apa pun: cukup **BANDINGKAN waktu-mulai-proses vs mtime file** (mis. `ps -o lstart`
   vs `stat -c %y file`) lalu **LAPORKAN ke user**. **User yang memutuskan restart.**
(Pelajaran 2026-09-07: PM nyaris nyuruh restart/kill server aigate padahal sesi
opencode hidup di dalamnya → bunuh diri.)

## R33 — DILARANG bikin file/folder baru di ROOT repo; kelompokkan per peruntukan
Pelajaran (2026-09-07, user: "kenapa di root ada folder pm? jangan bikin berantakan
dengan sembarangan bikin file/folder, kelompokin berdasarkan peruntukkannya"): PM bikin
folder `pm/` di root repo (Memory Bank), menabrak konvensi struktur proyek. Root repo
harus tetap ramping.

Aturan wajib:
1. **DILARANG** membuat file ATAU folder baru di **root** repo.
2. Semua artefak baru WAJIB masuk folder per peruntukan yang SUDAH ada:
   `documents/**` (dokumen proyek: `documents/dev/`, `documents/architecture/`,
   `documents/pm/`, dst), `src/**` (kode), `tests/**` (test), `.opencode/**`
   (artefak agen/skill/rule/command/report).
3. Memory Bank PM kini di **`documents/pm/`** (bukan root `pm/`) — selaras R5
   (semua dokumen proyek di `documents/`).
4. Kalau sebuah artefak **belum punya tempat yang cocok**, PM **TANYA user dulu**
   sebelum bikin folder baru — jangan asal bikin.
(Pelajaran 2026-09-07: folder `pm/` di root dipindah ke `documents/pm/` + semua
referensi (46 di 13 file) diselaraskan; rule R33 dibuat biar gak keulang.)

## R34 — Self-Heal: WAJIB subcommand non-interaktif CLI + done-marker di-gate exit code
Pelajaran (2026-09-07, user lapor issue-64 "false done"): `build_heal_command` membangkitkan
`opencode --model hy3 --prompt "$(cat ...)"; touch <done>; echo done` — tiga bug sekaligus:
(1) `opencode` default command = TUI interaktif; non-interaktif itu `opencode run [message..]`
(yang TIDAK punya `--prompt`; message = positional). (2) separator `;` bikin `touch .done`
jalan TANPA SYARAT walau CLI gagal/print help → self-heal menandai issue DONE palsu.
(3) model id mentah (`hy3`) dari DB aigate ditolak opencode yang minta format
`provider/model` (dan `hy3` ambigu: ada `aigate/hy3` + `bai/hy3`).

Aturan wajib untuk perintah yang di-generate orchestrator:
1. CLI agentic dipanggil lewat **subcommand non-interaktif** yang sudah diverifikasi dari
   `--help` CLI terpasang (opencode 1.18.x: `opencode run -m provider/model "<msg>"`),
   BUKAN default/TUI command.
2. Marker sukses (`.done`) **hanya** dibuat kalau CLI exit 0 (`&&`); exit non-zero wajib
   membuat marker `.failed` (`||`) dan `wait_for_done` harus return False SEGERA saat
   `.failed` muncul (bukan burn timeout 30 menit).
3. Model id di-**kualifikasi dulu** sebelum spawn: sudah `provider/model` → lolos; mentah →
   resolve via `opencode models` (unique menang; ambigu → prefer provider `aigate` sendiri;
   tidak ketemu → OMIT flag + warning, JANGAN spawn dengan model yang pasti ditolak).
4. Perubahan bentuk command wajib diuji **live** (shim CLI exit 0/1 di temp dir) — bukan
   cuma assertion string — dan `--help` CLI asli dibaca sebelum klaim flag.

## R35 — Verifikasi hemat: tes tertarget saat iterasi, suite penuh SEKALI sebelum commit
Pelajaran (2026-09-07, user protes "kok lama amat" lalu "kenapa testing sering lama"):
PM menjalankan **suite penuh 2x dalam satu sesi** — yang kedua hanya untuk mengubah
baris cache-buster di HTML (tidak ada satu pun tes yang menyentuhnya). Pemborosan ini
berasal dari kebiasaan lama "Verifikasi PM (re-run sendiri) = suite penuh".

Aturan wajib untuk PM dan semua sub-agent:
1. Saat iterasi: jalankan **hanya file tes yang relevan** dengan perubahan
   (`pytest tests/backend/test_x.py`, `node node_modules/.bin/vitest run tests/x.test.js`).
2. Suite penuh **satu kali**, tepat sebelum commit, sebagai gate.
3. Perubahan yang TIDAK mungkin dites (markup/label/cache-buster/komentar/dokumen)
   → **tidak** perlu menjalankan suite; cukup verifikasi grep/visual.
4. Klaim kecepatan/kinerja wajib dari **pengukuran nyata** (`time`, angka `Duration`
   vitest, `--durations=10` pytest) — bukan perasaan. Kalau angka tidak bisa
   dibandingkan antar-sesi (Termux throttling), sebutkan eksplisit.
5. Konfigurasi tes ikut diaudit sebagai bagian "rapihin": `src/frontend/vitest.config.js`
   kini `isolate:false` (jsdom dibangun sekali, bukan 23x) → 32-34s jadi ~23s.
   Properti permanen ini dicatat di CODE_CHANGES 2026-09-07; kalau nanti ada tes baru
   yang butuh state segar, kasih `vi.resetModules()` + re-import (lihat
   `tests/terminal_exit.test.js`) JANGAN langsung naikkan isolate lagi.

## R36 — Commit per subtask (R19) dipecah per FITUR, bukan per lapisan; file bersama di-split per hunk
Pelajaran (2026-09-07): kerjaan 4 sesi numpuk uncommitted (23 file) dan 2 fitur
(self-heal + cleanup log) berbagi `index.html`, `i18n.js`, `settings.py`.
Cara yang jalan: `git add <file>` untuk file milik satu fitur, dan **split hunk**
untuk file bersama (`git diff -U3 -- <file>` → pilih hunk → `git apply --cached`),
lalu **urutan commit disusun supaya yang menambah kolom/API dulu, yang memakainya
belakang** (logs-BE → self-heal → logs-FE) supaya tiap commit antara tetap konsisten.
Dilarang: `git add -A` sekali jalan untuk kerjaan beda fitur (R19 dilanggar dua kali:
"checkpoint" dan mega-commit).

## R37 — Jalur "tiap shell" wajib bebas perintah blocking; ukur startup shell duluan
Pelajaran (2026-09-07, user: "kerja lu lama bangg kalo udah manggil/jalankan perintah
bash/shell. perbaiki dong"): akar masalahnya BUKAN di tes atau di repo, tapi
`~/.bashrc` memanggil `termux-wake-lock` **di setiap shell interaktif** = **1,2 detik**
dibayar sebelum perintah apa pun mulai jalan (Termux: tiap panggilan tool = shell baru).
Angka nyata sebelum/sesudah: `time bash -ic true` = **1,452s → 0,047s** (≈25x).

Aturan wajib:
1. Kalau user komplain "lama" dan penyebabnya perintah shell: **ukur dulu**
   (`time true`, `time bash -c true`, `time bash -ic true`, lalu `--durations=10` /
   angka `Duration` vitest). Jangan tebak.
2. DILARANG ada panggilan blocking (API Termux, jaringan, install, `sleep`) di jalur yang
   jalan **tiap shell** (`~/.bashrc`, `~/.profile`, `PROMPT_COMMAND`, hook tool).
   Kebutuhan yang harus tetap hidup (wake lock) → **cache state-file + interval +
   jalankan di background** (`( cmd >/dev/null 2>&1 & )`), bukan di depan tiap shell.
3. Perubahan environment di luar repo (`~/.bashrc` dll) wajib: (a) dikomentari alasan +
   angka ukurnya di file itu, (b) dicatat di Memory Bank bagian Tooling, (c) diverifikasi
   fungsinya masih jalan (bukan cuma jadi cepat).
4. Sumber lambat lain yang sudah diketahui di box ini: `npx` shebang rusak (pakai
   `node node_modules/.bin/<bin>`), `os.cpus()=0` bikin vitest 1 fork (sekuensial),
   throttling Android (angka antar-run bisa beda 1,5–2x — sebutkan bila membandingkan).

## R38 — Right-size handover: task kecil = handover pendek, tanpa dokumen tambahan
Pelajaran (2026-09-07, user: "buset, lama amat bikin item baru di sidemenu" — spawn
pertama untuk fitur 1 tautan gue cancel karena handover-nya 60+ baris):
1. Task ≤ 5 file / satu lapisan → handover **<= 25 baris**: permintaan user apa adanya,
   peta file + nomor baris, daftar pekerjaan, batasan, definition of done. Tanpa latar
   belakang panjang, tanpa template laporan.
2. PM tetap WAJIB kasih peta kode (R28: path + baris) supaya sub-agent gak eksplorasi buta —
   itu yang bikin cepat, bukan kalimat panjang.
3. Jangan minta sub-agent menulis file laporan `.md` untuk task kecil; laporan hanya untuk
   task besar/audit (aturan `.opencode/reports/**` tetap berlaku kalau memang ada laporan).
4. Gate tes mengikuti R35: sub-agent hanya tes tertarget; suite penuh sekali oleh PM.

## R39 — "Biar gak kecampur" = BRANCH baru, BUKAN repo baru; resource eksternal wajib dikonfirmasi bentuknya
Pelajaran (2026-09-08, user: "goblok, kenapa bikin repo baru? gua kan mintanya branch baru"):
user minta bikin dokumen wiki "biar gak kecampur" → PM menafsirkan "repo baru" secara harfiah
dan LANGSUNG bikin `AI-Gate-docs` (private) di GitHub + tes push wiki. Yang user mau = branch
baru di repo yang sudah ada. Akibat: resource publik/bernama tetap muncul tanpa perlu + perlu
cleanup manual.

Aturan wajib:
1. Niat "pemisahan" ("biar gak kecampur", "jangan campur sama kode", "bikin tempat sendiri",
   "buat versi lain") → **DEFAULT = branch baru di repo yang sudah ada** (`docs/<topik>`,
   `feat/<topik>`, `refactor/<topik>`). Repo baru BUKAN default, walau user ketik kata "repo".
2. R9 (implementasi tanpa konfirmasi) hanya berlaku untuk keputusan **di dalam** repo/lingkungan
   kerja. Aksi yang **membuat resource eksternal di luar workspace** — repo GitHub, organisasi,
   package registry, release, domain, akun, webhook — WAJIB diklarifikasi **bentuknya** dulu,
   cukup 1 kalimat ("repo baru atau branch saja?"). Salah bikin = jejak publik + penghapusan
   manual.
3. Kata user ambigu vs tafsir termurah: ambil tafsir yang **paling murah dibatalkan**
   (branch → tinggal hapus lokal; repo → harus dihapus di GitHub). Kalau ragu, tanya.
4. Kalau terlanjur bikin resource eksternal yang SALAH: **JANGAN langsung dihapus**
   (destruktif/ireversibel) — laporkan ke user + minta izin hapus, dan jangan dipakai/diisi.
5. Fakta teknis yang bikin repo baru makin tidak perlu: **wiki tiap repo GitHub sudah berupa
   repo git terpisah** (`<owner>/<repo>.wiki.git`) — file wiki tidak pernah tercampur dengan
   `src/**`. Jadi "gak kecampur" sudah terjamin tanpa repo baru.

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
(src/**, documents/**, pm/**, config) dan laporan audit (.opencode/reports) dikecualikan
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
  default yang masuk akal, CATAT di pm/status.md + memory-bank, lalu lanjut.
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
  simpan di `pm/state.md` key `multiagent_mode`; anggap "belum dipilih" kalau state
  belum mencatatnya untuk sesi berjalan.
- Paralel hanya aman bila file-scope tiap agent TIDAK overlap (lihat
  `agent-boundaries.md`). Kalau overlap / dependen -> PM PAKSA sekuensial walau
  user pilih paralel, dan jelaskan ke user.
  - Catat pilihan di `pm/status.md` + `pm/state.md`, lalu jalan.

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
kesalahan (nulis dari asumsi sendiri). Catat asal di doc, bukan cuma di pm/.
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

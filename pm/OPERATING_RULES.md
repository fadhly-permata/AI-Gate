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

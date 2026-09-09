# Laporan Tugas: Perapian Lapisan Governance Proyek

## Informasi Dasar
- Tanggal: 2026-09-10
- Jenis Tugas: refactor (dokumen governance, bukan kode produksi)
- Waktu Mulai: 01:20
- Mode Eksekusi: sekuensial (keputusan pengguna, sesuai R16)
- Pelaksana: ProjectManager; pekerjaan desain struktur didelegasikan ke spesialis (R21)

## Permintaan Pengguna
Permintaan awal: "intinya rapihin semua, tapi pastikan lu gak akan pernah nabrak rule lagi".
Rincian yang pengguna sampaikan:
1. `OPERATING_RULES.md` dibuat oleh PM; pengguna tidak mengetahui isi dan kegunaannya.
2. Pengguna hanya memberi instruksi melalui `rules/`, `skills/`, dan `commands/`.
3. Pengguna tidak mengetahui guna berkas-berkas di `documents/pm/`.
4. Pertanyaan: mengapa tidak disatukan dalam satu folder.
5. Pertanyaan: mengapa tidak memakai gaya caveman ultra.
6. Tindak lanjut: mode eksekusi sekuensial; pertanyaan mengenai plugin dan Graphify dijawab
   lebih dahulu, lalu pengguna menyetujui langkah (a) dengan syarat PM tidak lagi melanggar aturan.

## Rule yang Mengikat Tugas Ini
Dibaca penuh sebelum bertindak (11 berkas `.opencode/rules/*.md`, 229 baris; indeks 51 rule
`documents/pm/OPERATING_RULES.md`):
- `language.md:2-4` — berkas `.opencode` bergaya caveman ultra; laporan `.opencode/reports/*`
  berbahasa Indonesia formal; percakapan dengan pengguna bahasa Indonesia casual tanpa singkatan.
- `task-report.md` + R23 — tugas wajib punya laporan, ditulis di awal, lokasi `.opencode/reports/`.
- `agent-boundaries.md` — PM menulis `documents/pm/**` dan hasil merge akhir; spesialis hanya
  menulis skopenya.
- `agent-generation.md` R1-R3 — sub-agent/skill dibuat sesuai kebutuhan; setelah generate wajib
  meminta pengguna restart opencode.
- `parallel-sequential.md` (R16) — pilihan mode dicatat di `pm/state.md` dan `pm/status.md`.
- `no-hallucination.md` + R47/R48 — klaim wajib bersumber fakta terverifikasi.
- R5 (dokumen di `documents/`), R6 (artefak di folder proyek), R33 (dilarang menambah berkas di
  root), R18 (rujukan inline wajib dipertahankan), R22 (perubahan dicatat per berkas),
  R38 (right-size: jangan tambah dokumen untuk pekerjaan kecil), R21 (PM tidak implementasi
  sendiri), R46 (typo pengguna wajib dikoreksi), R28 (codegraph wajib sebagai langkah pertama
  membaca kode — saat ini tidak dapat dipenuhi, lihat Temuan).

## Rencana Pekerjaan
1. **(a) Sensus dan peta target** — daftar seluruh berkas governance beserta ukuran, kegunaan,
   dan rujukan yang mengarah kepadanya; usulkan struktur target yang lebih kecil.
2. **(b) Pemangkasan dan penggabungan rule** — 51 rule dikelompokkan per tema, duplikat dilebur,
   konflik ditandai; indeks satu layar yang dibangkitkan otomatis dari judul rule.
3. **(c) Penempatan rule wajib-baca** — memindahkan aturan kritis ke kanal yang benar-benar
   ter-inject otomatis (`AGENTS.md`); plugin opencode hanya bila masih diperlukan.
4. **(d) Gaya keluaran** — menerapkan caveman ultra pada keluaran PM dan berkas `.opencode`.

## Realisasi Pekerjaan
- [01:20] langkah 0 — membaca seluruh rule sebelum bertindak → selesai. Fakta tercatat:
  `.opencode/rules/` 11 berkas / 9.929 byte; `OPERATING_RULES.md` 51 rule / 51.493 byte;
  `documents/pm/` 19 berkas / 427 KB (53 persen dari total `documents/`); `status.md` sendiri
  195.166 byte.
- [01:20] temuan konsistensi laporan: `.opencode/reports/` memakai dua format nama folder
  (`2026-09-03` dan `20260903`); aturan mewajibkan `[yyyymmdd]`. 27 berkas laporan sudah ada.
- [01:20] temuan R28 mati: `codegraph` tidak ada di PATH, tidak ada blok `mcp` pada
  `opencode.json` maupun konfigurasi global, tidak ada skill/command terkait. Aturan wajib sejak
  2026-09-06 tetapi tidak dapat dipenuhi.
- [01:20] langkah (a) — sensus dan peta target disusun → selesai (lihat bagian Peta Target).
- Keputusan pengguna untuk langkah (b) sampai (d) masih ditunggu.

## Peta Target (hasil langkah a)
Kondisi saat ini dan nasib tiap berkas diusulkan sebagai berikut.

| Berkas | Ukuran | Usulan |
|---|---|---|
| `documents/pm/status.md` | 195 KB | dipangkas: 30 hari terakhir; sisanya `archive/status-2026Q3.md` |
| `documents/pm/OPERATING_RULES.md` | 51 KB | direstrukturisasi per tema (langkah b), isian tidak dihapus |
| `documents/pm/memory-bank.md` | 49 KB | dipisah: brief + keputusan aktif tetap tinggal, riwayat ke `archive/` |
| `documents/pm/state.md` | 7 KB | dipertahankan, format ditegaskan (satu checkpoint aktif) |
| `documents/pm/cli-tools-install-backlog.md` | 27 KB | dipindah ke `documents/plan/` (bukan wewenang PM) |
| `documents/pm/cli-tools-compatibility.md` | 5 KB | dipindah ke `documents/config/` (sumber data, dirujuk kode) |
| `documents/pm/wiki-plan.md`, `wiki-backlog.md` | 13 KB | dipindah ke `documents/plan/` |
| `documents/pm/bugs.md` | 4 KB | digabung ke `.opencode/reports/` alur `/log-bug` |
| `documents/pm/handover-*.md` (2 di root pm) + `handovers/` (5) | 29 KB | satu folder `documents/pm/handovers/`, isi selesai ke `archive/` |
| `.opencode/rules/` (11 berkas) | 10 KB | digabung menjadi 4 berkas tema (perilaku agen, batasan, kualitas, keluaran) |

Catatan yang wajib dijaga: berkas `documents/{analysis,architecture,api,config}/**` dirujuk
langsung oleh kode (mis. `src/backend/models.py:5`, `src/backend/gateway/errors.py:8`), sehingga
tidak boleh dipindah tanpa memperbaiki rujukan tersebut (R18, R22).

## Status Akhir
Sebagian — langkah (a) selesai dan laporan dibuat lebih dahulu sesuai `task-report.md`.
Langkah (b) sampai (d) menunggu persetujuan pengguna karena bersifat merusak (memangkas,
menggabungkan, dan memindahkan dokumen governance).

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
- [01:35] keputusan user dicatat: R28 → Graphify; peleburan rule dibolehkan (arsip utuh);
  langkah (c) diserahkan ke PM (putusan: kanal wajib-baca = `AGENTS.md`, plugin ditunda);
  gaya tulis `.md` = caveman ultra, komunikasi ke user = bahasa normal (jadi R52).
- [01:54] langkah (b) DESAIN — didelegasikan ke `system-analyst` (R21; hanya menulis di
  `documents/analysis/**`) → selesai. Hasil: `documents/analysis/2026-09-10-rules-consolidation.md`
  (37.789 B): peta lama→baru 52 rule (0 hilang, 0 ganda), 10 tema A–J, 49 rule baru ≤4 baris,
  target `OPERATING_RULES.md` v2 = 10.533 B (−80%), 10 konflik K1–K10 dengan usulan penengah,
  shortlist `AGENTS.md` 12 baris, rencana pindah 19 berkas, spesifikasi skrip pemeriksa
  `.opencode/tools/governance/rules-index.py`. Commit `40ae85e`.
- [01:54] koreksi sensus langkah (a): berkas rule sekarang **52** rule / 52.698 B (R52 bertambah
  setelah sensus); ukuran nyata `documents/pm/` = **403.321 B** — angka 427 KB tadi berasal dari
  `du` yang membulatkan blok.
- [01:54] temuan terpenting: **definisi agen PM menunjuk objek yang tidak ada** —
  `ProjectManager.md:30` skill `pm-postmortem` (tidak ada di `.opencode/skills/`), `:76` nama skill
  `fullstack-skill` (nyata `fullstack-dev-skill`), `:85,93,110` write root `docs/analysis/**`
  bertentangan dengan `agent-boundaries.md:23-27` (`documents/...`) dan R5; ditambah 17 rujukan
  `pm/...` basi di 6 berkas hidup. Kandidat akar pelanggaran berulang: instruksi menunjuk path
  dan skill hantu.
- [01:54] urutan aman usulan (sekuensial): ① perbaiki rujukan basi → ② sepakati pemilik tulis
  `.opencode/rules/**` → ③ tulis arsip v1 → ④ pasang rule v2 → ⑤ gerbang skrip pemeriksa →
  ⑥ pindahkan berkas → ⑦ perbarui `AGENTS.md` → ⑧ normalisasi folder laporan.
- Keputusan user untuk ① dan ② masih ditunggu; eksekusi (b) belum dimulai.

- [02:05] langkah ① (rujukan basi) → selesai. 39 baris di 15 berkas config diperbaiki:
  `pm/...` -> `documents/pm/...`, `docs/...` -> `documents/...`, skill mati `pm-postmortem` ->
  rujukan nyata ke §6 Record Protocol, `fullstack-skill` -> `fullstack-dev-skill`. Berkas laporan
  lama tidak diubah (provenance). Verifikasi: `grep` sisa rujukan basi = 0 di berkas hidup.
  Commit `b0b81b3`.
- [02:05] langkah ② (pemilik tulis `.opencode/rules/**`) → user menunjuk PM. Dicatat di
  `agent-boundaries.md` (beserta perluasan: playbook PM sendiri + kanal `AGENTS.md`).
- [02:10] berkas kanonik `.opencode/rules/{secrets,no-hallucination,commands,task-report,language}.md`
  diperluas untuk menampung clause yang sebelumnya dobel di OPERATING_RULES (R51, R47, R7, R23, R52).
  §6 "Record Protocol" ditulis ke `pm-orchestration/SKILL.md` (sebelumnya pointer menunjuk skill
  yang tidak pernah ada). Total `.opencode/rules/` 9.929 -> 12.669 byte. Commit `1c4d4d4`.
- [02:15] langkah ③+④ → selesai. v1 diarsipkan utuh lewat `git mv` (52.698 byte, 52 rule, riwayat
  git tetap kebaca); `OPERATING_RULES.md` v2 dipasang: 50 rule / 10 tema A–J / 11.463 byte
  (−78% dari v1), tiap rule ≤4 baris, sitatan `[R#]` menunjuk arsip. F4 ditambahkan (klaim ukuran
  wajib menyebut alat dan satuan — akibat salah sensus `du` vs `wc -c`).
- [02:20] langkah ⑤ (gerbang) → selesai. Skrip `.opencode/tools/governance/rules-index.py`
  (stdlib saja) menulis 11 pemeriksaan dan **LOLOS** `exit 0`: indeks 50 rule/10 tema; cakupan
  `mapped=52 unique=52 dup=[] missing=[]`; rentang R1–R52 tanpa celah; ukuran 11.463 ≤ 20.480;
  tema 10 ≤ 10; tidak ada rule >4 baris; arsip utuh 52 rule; tidak ada path mati; tidak ada rujukan
  `pm/` basi; 52 sitatan `R#` terselesaikan; 14 laporan tercatat sebagai utang format (peringatan).
  `py_compile` bersih; `__pycache__` dihapus. Commit `8e59d87` + `c82d567`.
- [02:25] langkah ⑦ (kanal wajib-baca) → selesai. `AGENTS.md` ditulis ulang: 12 aturan always-on
  bergaya caveman ultra + pointer tema + rujukan gerbang (1.866 -> 3.896 byte). `opencode.json`
  ditambah `"instructions": ["documents/pm/OPERATING_RULES.md"]` supaya 50 rule ikut ter-inject;
  bentuk field diverifikasi ke skema resmi https://opencode.ai/config.json sebelum menulis
  (`Config.instructions` = array of string) dan `python3 -m json.tool` lolos. Commit `223c83b`.
- [02:30] pencatatan → `documents/dev/CODE_CHANGES.md` (per berkas, H3), `memory-bank.md`
  (keputusan + beresnya heading `## Decisions` dobel), `status.md` (blok Record Protocol),
  `state.md` (`mode: governance-cleanup`, checkpoint v2, `rules_ref` v2).
- BELUM dikerjakan (sengaja, menunggu): ⑥ pemindahan 19 berkas `documents/pm/**` (butuh ACC karena
  memutus rujukan `BACKLOG.md:101`, `CODE_CHANGES.md:139`, `business-analyst.md:11` bila tidak
  dibetulkan bersamaan); ⑧ normalisasi 14 berkas laporan; (e) instalasi Graphify (prasyarat `uv`
  belum ada; Python lokal 3.14.6 vs permintaan 3.12); push 8 commit ke `origin/refactor/ui`.
- Syarat wajib: **user restart opencode** supaya `AGENTS.md`, `opencode.json`, agent/skill/rule yang
  baru dimuat — sesi yang sedang berjalan masih memakai konfigurasi lama.
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
Sebagian — langkah (a) selesai (sensus + peta target), laporan dibuat lebih dahulu sesuai
`task-report.md`. Langkah (b) baru pada tahap **desain** (`system-analyst`, berkas
`documents/analysis/2026-09-10-rules-consolidation.md`, commit `40ae85e`): 52 rule terpetakan ke
10 tema tanpa kehilangan isi, 10 konflik tercatat dengan usulan penengah, dan urutan eksekusi
①–⑧ diajukan. Eksekusi (b) menunggu putusan pengguna untuk ① (pemilik tulis `.opencode/rules/**`)
dan ② (setuju rujukan basi dibetulkan lebih dulu), karena menyentuh konfigurasi agen.

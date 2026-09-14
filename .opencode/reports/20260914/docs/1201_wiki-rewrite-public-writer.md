# Laporan Tugas: Penulisan Ulang Dokumen Wiki oleh Spesialis Public Writer

## Informasi Dasar
- Tanggal: 2026-09-14
- Jenis Tugas: docs
- Waktu Mulai: 10:50 (pilihan mode) — eksekusi 10:55 s.d. 12:01
- Cabang kerja: `docs/wiki` (checkpoint awal `17e0101`)
- Eksekutor: sub-agen **public-writer** (sesi `ses_f61faa11fffeobPweNZWiz8zm5`, dipakai ulang untuk 6 halaman)
- Verifikator & penyusun laporan: ProjectManager

## Permintaan Pengguna
1. "tulis ulang dokumen wiki dengan menggunakan spesialis agent yang baru dong"
2. Pertanyaan paralel vs sekuensial → jawaban: **"sekuen"**
3. Setelah halaman 3 disajikan untuk review → **"lakukan yang terbaik aja"** (keputusan review dilimpahkan ke PM)

## Rencana Pekerjaan
1. Tetapkan cakupan: 6 halaman yang belum di-ACC (Interfaces, Configuration-and-Keys, CLI-Tools,
   OpenAI-API, Terminal, Providers-and-Combos). `Home.md` + `Quick-Start.md` **tidak disentuh**
   (sudah di-ACC user dan sudah tayang di GitHub wiki).
2. Verifikasi ulang fakta ke kode terkini sebelum menulis (draf lama dibuat 2026-09-08; UI/gerbang
   berubah banyak sejak saat itu).
3. Terbitkan handover per halaman ke `documents/pm/handovers/`, spawn public-writer **sekuensial**.
4. Audit tiap hasil: gerbang konten (R44/R42/R23/R45) + cek fakta mandiri ke `file:line`.
5. Koreksi temuan PM atas naskah, catat progress, tulis laporan.

## Realisasi Pekerjaan
- 10:55 rencana + cakupan ditetapkan (default dicatat: halaman ACC tidak dirombak).
- 10:58 bukti dikumpulkan: lembar fakta lama A/B/C dibaca, lalu **di-audit ulang ke kode** —
  ketemu beberapa poin lembar fakta sudah basi (rincian di bawah).
- 11:00–11:05 6 handover ditulis: `handover-20260914-wiki-rewrite-1-interfaces.md` s.d. `-6-providers-combos.md`.
- 11:05–11:20 halaman 3 `Interfaces.md` → selesai, gerbang lolos (296 kata prosa).
- 11:25 halaman 4 `Configuration-and-Keys.md` → selesai (447 kata). PM menjawab keraguan penulis:
  CSV laporan **tidak** memuat kunci (`analytics_export.py:85-110` hanya baris totals/by_group/buckets);
  yang memuat kunci hanyalah JSON setelan (`export.py:64-75` mengekspor tabel `providers`).
  Draf lama salah di titik ini, kini dibetulkan.
- 11:40 halaman 5 `CLI-Tools.md` → selesai (393 kata). Self-Heal **ditambahkan** ke halaman ini
  (kartunya memang hidup di layar alat coding, `index.html:866-880`) dengan risiko ditulis jujur.
- 11:50 halaman 6 `OpenAI-API.md` → selesai (395 kata). Draf lama ternyata **salah**: menyatakan
  "there are no other endpoints", padahal `/v1/messages` (Anthropic) sudah ada (`gateway/router.py:528`).
- 11:55 halaman 7 `Terminal.md` → selesai (394 kata).
- 12:00 halaman 8 `Providers-and-Combos.md` → selesai (477 kata).
- 12:01 gerbang final 6 file: **SEMUA PASS**.

### Koreksi fakta yang keluar dari proses ini (penting, jangan sampai hilang)
1. **Tidak ada "split view / pecah layar" di terminal.** Toolbar sekarang: tab baru, Paste +
   Paste as Code Block, Settings (TUI Passthrough, Keep Screen On), Full Page vs Fullscreen,
   gugus kontrol mengambang (`index.html:775-835`). Kelas CSS `term-split` = tombol split
   (tombol utama + caret menu), **bukan** layar terpisah. Lembar fakta A/C (2026-09-08) keliru di
   titik ini dan sudah menyebar ke draf lama halaman 3 + 7.
2. **3 pilihan teknis (logging detail per request, umur simpan log, batas sesi terminal lepas)
   TIDAK tampil di layar setelan.** Layar hanya Port, mode developer, tema, bahasa
   (`index.html:195-290`, id `setPort`/`setDevMode`/`setTheme`/`setLocale`). Naskah lama halaman 4
   menjanjikan ketiganya ada di layar → dibetulkan jadi "di balik layar".
3. **Jalur Anthropic inbound sudah hidup** (`/v1/messages`, `/v1/messages/count_tokens`), dan
   claude kini berstatus terverifikasi untuk diluncurkan (`cli_presets.py:174`). Halaman 5 & 6 diperbarui.
4. **Strategi combo ada 5** (`fallback`, `load_balance`, `latency_cost`, `three_tier`, `round_robin`,
   `index.html:1102-1106` + `combo_routing.py:275-305`) — draf lama hanya tahu sebagian.
5. **Nama model polos (bare model) tidak menunjuk "penyedia aktif"** — resolver mencari semua penyedia
   aktif yang menawarkan model itu, dan kalau lebih dari satu cocok yang dipakai adalah penyedia yang
   ditandai sebagai yang dipakai (`gateway/resolver.py:218-270`). Kalimat naskah diluruskan.
6. Port **11434** (Ollama) hanya muncul di satu docstring contoh (`cli_tools_router.py:606`) →
   angka itu pengetahuan eksternal, bukan fakta aplikasi; disebutannya di halaman 8 digeneralisasi.
7. Klaim pembuka halaman 8 "the stutter never reaches you" terlaluoptimistis — klien tetap menunggu
   selama retry berlangsung. Diturunkan jadi "waits a beat — and usually nothing worse happens".
8. "working offline stays possible" (halaman 8) diklaim terlalu tegas → dilunakkan.
9. Batas "sesi terminal dilepas setelah ±60 menit" tidak diekspos sebagai pilihan layar →
   di halaman 7 ditulis "about an hour" tanpa janji "adjustable in settings".

### Status kutu-kutu lama yang ikut terselesaikan
Koreksi lama #1 (endpoint bukan port kedua), #2 (putus koneksi ≠ proses mati), #3 (tidak ada combo
bawaan `default`) **dipertahankan** dan justru diperkuat di naskah baru.

## Gerbang Verifikasi
- Mesin: pemindaian token terlarang per file (path `src/`/`documents/`, `this repo`, `MIT`,
  `untested`/`experimental`, `seven`, `ADR-###`, `R#`, `TODO-VERIFY`, id DOM, nama kolom/tabel DB,
  nama modul `.py`/`.js`, kelas CSS) → **0 temuan** di 6 file. Pengecualian sah: `run.py`
  (perintah yang diketik user, wiki-plan §2).
- Taut internal: seluruh target ada di antara 8 nama halaman wiki → 0 rusak.
- Kredit `Made with ❤️ by Fadhly Permata` di baris terakhir → 6/6.
- `aigate` huruf kecil → lolos.
- Batas kata per halaman (296 / 447 / 393 / 395 / 394 / 477) → semua di dalam rentang handover.
- Kepemilikan berkas (A3): penulis naskah = public-writer (write root `documents/pm/wiki-drafts/**`);
  PM hanya menulis `documents/pm/handovers/**`, `documents/pm/state.md`, laporan ini, dan mengoreksi
  4 baris naskah hasil audit fakta. Nol tulis `src/**` / `tests/**` (A2).

## Status Akhir
**Berhasil (draft)** — 6 halaman wiki ditulis ulang oleh spesialis public-writer, semua gerbang lolos,
fakta diperbarui ke kondisi aplikasi hari ini, 9 koreksi fakta tercatat.

Belum selesai / wewenang user:
- Review user atas 6 halaman ini (belum ada yang di-ACC).
- Commit + publish ke GitHub wiki (D1: tidak dilakukan tanpa perintah). Wiki publik masih berisi
  hanya `Home` + `Quick Start`.
- WP.1 (cek versi Python di `run.py`) masih antre.
- Tahap 2 (Sidebar/Footer, terjemahan, halaman lanjutan, Pages) masih ditahan sampai 8 halaman ACC.

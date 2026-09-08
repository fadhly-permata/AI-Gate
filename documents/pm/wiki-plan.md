# Wiki Plan — aigate (halaman 1–8)

**Dibuat:** 2026-09-08 · **Diperbarui:** 2026-09-08 · **Branch kerja:** `docs/wiki`
**Backlog task:** `documents/pm/wiki-backlog.md` · **Aturan konten:** `OPERATING_RULES.md` R44

---

## 1. Keputusan yang sudah jatuh (jangan ditanya ulang)

| # | Keputusan | Putusan | Sumber |
|---|-----------|---------|--------|
| 1 | Cakupan | **Halaman 1–8 saja.** Halaman 9–14 (Data Model, Architecture, plain-language spec, Testing & QA, Roadmap) DITAHAN — isinya terlalu dalam | user 2026-09-08 |
| 2 | Isi `documents/` | **TIDAK dipublish.** Tidak disalin, tidak dikutip, tidak di-link | user 2026-09-08 → R44 |
| 3 | Bahasa | **Inggris**, intonasi kasual. Belum diterjemahkan | user 2026-09-08 |
| 4 | Pembaca | **Awam.** Kalimat natural & ringan; istilah teknis langsung dijelaskan di tempat | user 2026-09-08 |
| 5 | Emoji | **Boleh**, biar ceria. Secukupnya, jangan jadi_confetti | user 2026-09-08 |
| 6 | Cara kerja | **Satu per satu.** Satu halaman jadi → user review → baru halaman berikutnya | user 2026-09-08 → R17 |
| 7 | Hubungan wiki ↔ `documents/` | **Dua sumber terpisah, BUKAN cermin.** Wiki = apa yang user lihat & lakukan. `documents/` = internal, tetap di repo privat-secara-fungsi | diturunkan dari putusan #2 — **konfirmasi user** |
| 8 | Tempat draft | `documents/pm/wiki-drafts/` (area staging PM). **Wiki asli TIDAK disentuh** sampai user buka izin | user 2026-09-08 (larangan tulis wiki masih berlaku) |

## 2. Aturan konten per halaman (R44 — wajib lolos sebelum draft ditunjukkan)

**Boleh ditulis** (semuanya boleh di-publish):
- Apa yang user lihat di layar, apa yang user ketik, apa yang terjadi setelahnya.
- Perintah menjalankan, opsi konfigurasi, alamat/port, format request API.
- Nama fitur & istilah produk (combo, provider, preset, self-heal).
- Batas yang benar-benar dirasakan user (key tersimpan teks biasa → aman asal fisik aman).

**DILARANG muncul:**
- Isi/alkus/tautan ke file apa pun di `documents/` (BRD, PRD, FSD, ERD, TSD, ADR, TEST_PLAN,
  BACKLOG, CLI_CONFIG_SCHEMA, OPENAI_COMPATIBLE_CONTRACT, TERMINAL_UX, CODE_CHANGES, memory-bank).
- Path/nama file sumber (`src/backend/...`, `run.py` di luar konteks perintah yang memang diketik user).
- Nama tabel database, nama kolom, skema relasi.
- Nomor keputusan internal (ADR-001, R#, §) dan penugasan tim.
- Detail implementasi: library, nama modul, fungsi, class, alasan desain.
- Hal yang belum pernah diverifikasi dari perilaku nyata aplikasi.

## 3. Halaman & cara pembuktiannya

Setiap halaman **wajib** dibuktikan dari **perilaku aplikasi**, bukan dari dokumen internal:
(a) kode dibaca read-only oleh sub-agent → (b) angka/nama/fitur dicatat dari apa yang benar-benar
ada → (c) klaim tak terbukti ditandai `TODO-VERIFY: <cara cek>`, DILARANG nebak.

| # | File draft | Isi (user-facing) | Sumber bukti |
|---|-----------|-------------------|--------------|
| 1 | `Home.md` | Peta jalan: apa aigate itu, buat siapa, mulai dari mana | README (sudah ACC user) + fakta terkonfirmasi |
| 2 | `Quick-Start.md` | Pasang sampai jalan di Linux / Windows / Android-Termux | `run.py` + deps di kode; **perbaiki 3 bug README** |
| 3 | `Interfaces.md` | Ada berapa cara memakai aigate + link ke halaman tiap cara | route/menu frontend yang benar-benar ada |
| 4 | `Configuration-and-Keys.md` | Pasang API key, atur provider, ganti port, di mana setting disimpan | halaman config + tabel setting yang terlihat user |
| 5 | `CLI-Tools.md` | 24 tool, cara menyambungkannya, apa yang berubah di tool itu | preset nyata di kode (12+6+6) |
| 6 | `OpenAI-API.md` | Alamat lokal + contoh request dari program sendiri | endpoint yang benar-benar di-resolve server |
| 7 | `Terminal.md` | Tab, fullscreen, paste, scroll/swipe, log window, apa yang terjadi saat tool gagal | kontrol yang muncul di UI |
| 8 | `Providers-and-Combos.md` | Model mental: provider → combo → mana yang dipakai duluan, apa yang terjadi saat gagal | perilaku routing yang terlihat user |

### 3 bug pada README yang harus dibenerin di halaman 2
1. `pip install -r requirements.txt` → file itu **tidak ada** di repo.
2. `AIGATE_SIMULATE_DEVICE=1` → variabel itu **tidak ada di kode**; yang nyata `AIGATE_DEV=1`.
3. `pip install -e .` → setelah itu command `aigate` hilang (perintah mana yang benar belum diverifikasi).

## 4. Definisi selesai per halaman

- [ ] Ditulis oleh sub-agent yang tepat, bukan oleh PM (R21).
- [ ] Lolos semua larangan bagian 2 (audit PM baris per baris).
- [ ] Semua fakta terbukti dari kode/perilaku; sisanya ditandai `TODO-VERIFY` + cara cek.
- [ ] Nada: natural, ringan, kasual, pembaca awam, emoji secukupnya.
- [ ] Link internal pakai nama file wiki (`Quick-Start`, bukan `Quick Start`).
- [ ] Tidak ada path/nama file sumber di teks.
- [ ] PM membaca hasil akhir sendiri sebelum menampilkan (R43 poin 5).
- [ ] Ditampilkan ke user → **tunggu ACC** → baru halaman berikutnya (R17).

## 5. Yang masih terbuka (tanya user saat bangun)

1. Putusan #7 (wiki bukan cermin) — benar begitu, atau wiki memang harus tetap bisa ditelusuri
   balik ke dokumen internal?
2. ~~Perlu halaman sendiri?~~ **TERJAWAL:** tidak. Cukup satu bagian singkat di halaman 4 (Configuration) + disebut di halaman 8. Fakta: kolam per endpoint, rotasi bergantian, status & latensi tercatat, dan memang dipakai sebagai jalur keluar (egress) oleh gerbang. Sampai sekarang baru disebut di README; istilah
   itu bisa berarti dua hal (pool penyedia model vs proxy jaringan). Belum diverifikasi.
3. Halaman 6 (API): boleh menyebut format request itu "kompatibel OpenAI"? (istilah itu perlu
   buat orang luar menemukan kita — tapi jelaskan singkat.)
4. Setelah 8 halaman ACC: terjemahkan ke 7 bahasa sekalian, atau tunggu stabil dulu?
6. ~~LISENSI~~ **TERJAWAL — user memilih MIT** (2026-09-08). `LICENSE` sudah merge ke `main`
   (`785845a`), label MIT sudah kebaca di GitHub. Larangan kata "free / open source" DICABUT dan
   sudah disebar ke README + 7 varian. Utang tersisa: WL.3 (tinjau ulang sebelum rilis publik /
   sebelum kontribusi luar masuk) dan WL.4 (versi xterm.js yang di-vendor tidak tercatat di repo).
7. ~~Self-Heal dibuka atau tidak~~ **TERJAWAL SENDIRI: ternyata SUDAH PUBLIK.** `README.md` yang
   sudah di-ACC user menyebutnya lengkap dengan alurnya ("makes a branch, runs an agent in a live
   tab, fixes warning after warning, and merges back when things pass") + kegagalan karena
   "out of quota". Jadi larangan menyebut Self-Heal di wiki **DICABUT** — yang tetap dilarang
   cuma ngarang detail yang belum diverifikasi (R23). Konsekuensi: **halaman 7 wajib** menjelaskan
   fitur ini apa adanya + risikonya (dia menulis kode dan menggabungkan branch). Untuk **halaman
   depan** tetap jangan jadi bintang utama: dia butuh proyek + agen yang sudah terpasang, sedangkan
   cerita halaman depan sekarang adalah keterbatasan perangkat.
8. Konfirmasi rumusan privasi: "nothing talks/reports back to us" BENAR untuk telemetri milik kita
   (nol alamat non-provider di backend), TAPI Font Awesome masih dimuat dari CDN cloudflare
   → bukan nol request pihak ketiga. User belum memutuskan: (a) terima rumusan sempit, (b) vendor ikon.
   pilih sendiri" — sudah benar secara teknis, tapi user yang punya hak menyatakan.
5. Kapan izin tulis ke wiki turun, dan mau otomatis lewat script publisher atau manual?

## 6. Urutan kerja (R17: sekuensial, satu per satu)

`1 Home` → review → `2 Quick Start` → review → `3 Interfaces` → review → `4 Config & Keys`
→ review → `5 CLI Tools` → review → `6 API` → review → `7 Terminal` → review → `8 Providers & Combos`
→ review → **baru** pikirkan publish + terjemahan.

Progress live ada di `documents/pm/wiki-backlog.md`. Kalau sesi putus, baca file itu + `state.md`.

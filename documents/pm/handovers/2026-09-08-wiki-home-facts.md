# Handover — Wiki `Home.md` (fakta terverifikasi)

**Dari:** PM · **Untuk:** business-analyst · **Tanggal:** 2026-09-08
**Tugas:** tulis halaman depan wiki aigate untuk pembaca awam.
**Tulis ke:** `documents/pm/wiki-drafts/Home.md` (satu file ini saja — timpa isinya).
**Aturan utama:** R44. **Jangan baca file lain di `documents/`** (BRD/PRD/FSD/ERD/TSD/SETUP/dll) —
wiki tidak boleh jadi cerminan dokumen internal. Sumber fakta lu = **lembar ini saja**.

---

## 1. Fakta TERBUKTI (boleh ditulis apa adanya)

**Produk**
- `aigate` — huruf kecil semua, termasuk di judul. Ini nama resmi.
- Jalan sebagai aplikasi Python di perangkat sendiri (Linux, Windows, Android/Termux —
  termasuk distro Linux penuh di HP). Tidak perlu server, tidak perlu container, tidak perlu akun.
- Dijalankan dengan `python run.py` → layanannya muncul di browser lewat alamat lokal.
- Mode developer memakai `AIGATE_DEV=1`. Setelah proyek dipasang sebagai paket, ada perintah
  `aigate`. (Detail pemasangan masuk halaman lain — di sini cukup sebut bisa jalan lokal.)
- Tidak ada akun aigate, tidak ada pendaftaran, tidak ada laporan senyuan ke server kita.
  Lalu lintas keluar hanya ke penyedia AI yang **user sendiri** daftarkan (mis. untuk masuk
  akun/authorize).
  → **Cara menulis klaim privasi (PENTING, biar tidak bohong):** jangan menulis "your prompts
  never leave your device". Yang benar: data hanya pergi ke penyedia AI yang kamu pilih sendiri,
  bukan lewat layanan perantara milik orang lain.
- **DILARANG menulis "free" atau "open source"** — file LICENSE belum ada di repo (ditemukan PM
  2026-09-08). Tulis saja bahwa kode sumbernya terbuka untuk dibaca/diunduh di GitHub; kata "open
  source" menunggu keputusan lisensi dari user.

**Yang bisa dilakukan (semua terbukti di kode)**
- **Giliran otomatis saat satu penyedia bermasalah.** Namanya *strategy* pada sebuah *combo*:
  `fallback` (coba anggota urut prioritas, lanjut ke berikutnya saat error, kalau semua gagal
  error terakhir yang muncul), `load_balance` (dipilih acak berbobot), `latency_cost`
  (pilih yang paling ringan biayanya). Untuk halaman depan: cukup tulis "kalau satu penyedia
  sedang bermasalah, aigate bisa berpindah ke penyedia lain yang kamu siapkan".
- **Catatan pemakaian + taksiran biaya.** Tiap request tercatat: berapa token masuk/keluar,
  taksiran biayanya, dan bisa dilihat per pengelompokan; ada juga ekspor CSV. Angka biaya adalah
  **taksiran** → tulis begitu, jangan tulis "tagihan".
- **Terminal sungguhan di dalam browser**: banyak tab (ada tombol `+`), layar penuh, tempel
  clipboard yang fokusnya otomatis balik ke terminal, scroll/swipe ala trackpad, riwayat 5000 baris.
- **Menyambung ke alat coding CLI** yang sudah dipakai orang. Saat ini **24** preset.
  Daftarnya masih terus bertambah (wajib ada catatan ini, satu kali saja).
- Ada fitur pertolongan otomatis saat alat belum pas settingnya (nama di UI: Self-Heal) —
  cukup **disebut sekilas**, detailnya masuk halaman lain.
- Ada API dengan alamat lokal yang bisa dipakai program/bahasa apa pun.
- Kredit terakhir: "Made with ❤️ by Fadhly Permata".
- Wiki: `https://github.com/fadhly-permata/AI-Gate/wiki`

## 2. Nada & gaya (WAJIB)
- Bahasa **Inggris**, intonasi **kasual**, kalimat **natural dan ringan** — seperti teman yang
  ngajarin, bukan dokumentasi perusahaan.
- Pembaca dianggap **awam**: tiap istilah langsung dijelaskan pakai kata sehari-hari, jangan
  gantung, jangan pakai jargon tanpa penjelasan.
- Emoji **boleh**, di judul seksi, secukupnya (biar ceria, bukan pesta emoji).
- Satu kalimat = satu makna. Hindari pasif kaku, subjek hilang, kalimat >2 klausa, reduplikasi
  palsu, dan calque. (R43 berlaku juga buat gaya.)
- Jangan menyebut jumlah baris kode / commit / file repo — cepat basi.
- Heading dimulai dari `#` (judul halaman), lalu `##` untuk seksi.
- Panjang: halaman depan = **peta jalan**, bukan manual. ± 250–400 kata di luar kode.

## 3. DILARANG muncul (R44)
- Path/nama file mana pun: `documents/...`, `src/...`, nama modul/fungsi/class.
- Nama tabel database, nama kolom, nomor seksi dokumen internal, nomor keputusan desain (ADR-00x).
- Kutipan/salinan/parafrase dari dokumen internal mana pun.
- Kata "untested", "experimental", "belum diverifikasi", "TODO" di teks publik.
- Link ke halaman wiki yang belum ada **di luar daftar 8 halaman ini**: Home, Quick-Start,
  Interfaces, Configuration-and-Keys, CLI-Tools, OpenAI-API, Terminal, Providers-and-Combos.
  (Tautan internal wiki pakai nama file bertanda-hubung, mis. `[Quick Start](Quick-Start)`.)

## 4. Struktur yang disetujui user (jaga kerangkanya, kalimatnya bebas kamu rombak)
1. Judul + 1 kalimat pembuka siapa untuk siapa.
2. Paragraf "apa ini & kenapa beda" (privasi ditulis benar, lihat §1).
3. `## What you can do with it` — 4–6 bullet hasil, bukan fitur mentah.
4. `## Pick your starting point` — tabel "I want to… / Read this", 4 baris.
5. `## How it works, in one paragraph` — model provider → combo → alamat lokal.
6. Penutup singkat + kredit.

## 5. Definisi selesai
- [ ] Hanya `documents/pm/wiki-drafts/Home.md` yang berubah.
- [ ] Tidak ada larangan §3 yang muncul.
- [ ] Semua kalimat fakta ada di §1 — tidak ada yang lu karang.
- [ ] Nada §2 lolos dibaca keras-keras oleh orang awam.
- [ ] Kembalikan struk ini: file yang ditulis, keputusan gaya, hal yang lu rasa masih lemah.

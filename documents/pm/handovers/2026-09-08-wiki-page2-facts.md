# Handover — Wiki `Quick-Start.md` (lembar fakta)

**Dari:** PM · **Untuk:** business-analyst · **Tanggal:** 2026-09-08
**Tugas:** tulis halaman "cara pasang sampai jalan" untuk pembaca awam.
**Tulis ke:** `documents/pm/wiki-drafts/Quick-Start.md` (satu file ini saja).
**Sumber fakta = lembar ini saja.** DILARANG membaca file lain di `documents/` (R44).

Halaman 1 (`Home.md` v4) **sudah di-ACC user** — baca file-nya buat nyamain suara:
`documents/pm/wiki-drafts/Home.md`. Tema yang sudah disetujui: orang yang pengen ngoding pakai AI
tapi perangkatnya seadanya. Halaman 2 ini lanjutan praktisnya: dari belum punya apa-apa sampai jalan.

---

## 1. Fakta yang TERBUKTI dari kode (boleh ditulis apa adanya)

**Prasyarat**
- Satu-satunya prasyarat: **Python 3.10 atau lebih baru**. Tidak ada yang lain.
- **TIDAK butuh** GPU, laptop khusus, compiler, build tools, Docker, atau akun cloud.
- **TIDAK perlu membayar apa pun ke kami.** Yang mungkin berbayar adalah akun penyedia AI yang
  user pakai sendiri — itu di luar aigate, dan beberapa penyedia punya tingkat gratis.
  → tulis begini, JANGAN menulis "gratis total".

**Cara kerja pemasangannya (ini bagian yang bikin halaman ini beda dari README)**
- Menjalankan satu perintah sudah cukup: `python run.py`.
- Perintah itu **memasang sendiri** dependency Python yang belum ada lewat pip, lalu langsung jalan.
  **Tidak ada file daftar dependency yang perlu dipasang secara manual** — siapa pun yang menyuruh user
  menjalankan `pip install -r requirements.txt` itu salah: file itu memang tidak pernah ada.
- Setelah jalan, layanannya muncul di alamat lokal **`http://localhost:8080`**.
  Browser **TIDAK terbuka otomatis** — user buka alamatnya sendiri. Wajib ditulis, ini penyebab
  bingung nomor satu.
- Port sibuk? `AIGATE_PORT=9090 python run.py`.

**Pilihan tambahan yang nyata (jangan ditulis kalau user belum butuh)**
| Yang diinginkan | Caranya | Fakta |
|---|---|---|
| jalanin sebagai perintah biasa setelah dipasang sebagai paket | `pip install -e .` lalu perintah `aigate` | nyata; ada di konfigurasi paket |
| jalanin lewat manajer paket Python modern | `uv` (buat lingkungan lalu jalankan) | opsional, bukan satu-satunya cara |
| fitur khusus developer (jendela log, alat bantu) | `AIGATE_DEV=1 python run.py` | hanya 3 variabel lingkungan yang dikenal aplikasi |
| pindah lokasi penyimpanan | `AIGATE_DB_PATH=...` | secara default sudah di folder sendiri di direktori rumah user |

- **Cuma ada 3** variabel lingkungan yang dibaca aplikasi: port, mode developer, lokasi penyimpanan.
  Variabel lain yang pernah disebut di dokumen lama **tidak ada di kode** (mis. flag simulasi
  perangkat) → DILARANG muncul di halaman ini.

**Per platform**
- **Linux:** cukup punya Python 3.10+; perintah yang sama.
- **Windows:** sama; dukungan terminal khusus Windows ikut terpasang otomatis saat pertama jalan.
- **Android:** pasang lewat **Termux**, lalu jalankan perintah yang sama seperti di laptop.
  Bagian yang lebih ribet di HP bukan aigate-nya, tapi **alat coding**-nya — Android resolve paket
  beda dari desktop, dan aigate tahu kapan dia jalan di Termux lalu menawarkan perintah pasang yang
  cocok. Detail alat coding itu masuk halaman lain, cukup ditunjuk.
- Sudah diuji maintainer di Linux, Windows, dan Android/Termux — termasuk distro Linux penuh di HP.
  DILARANG menulis "belum diuji/eksperimen" untuk ini (R42).
- **Tidak perlu server, tidak perlu container, tidak perlu deployment.** Ini aplikasi Python biasa.

**Setelah nyala, 3 langkah pertama**
1. Buka alamat lokalnya.
2. Masukkan kunci/akun penyedia AI yang user punya.
3. Pilih penyedia itu buat dipakai. Baru setelah itu alat coding / terminal / API-nya kepake.
(Ini urutan nyata; jangan ditambahin langkah yang belum diverifikasi.)

## 2. Koreksi terhadap README lama (JANGAN diulang di wiki)
1. `pip install -r requirements.txt` → perintah itu **tidak pernah perlu**; file-nya tidak ada.
2. Flag simulasi perangkat (`AIGATE_SIMULATE_DEVICE`) → **tidak ada di kode**; yang ada mode developer.
3. Menyuruh `pip install -e .` sebagai cara utama → bikin orang salah paham; cara utama tetap
   `python run.py`. Perintah paket itu jalur **alternatif** bagi yang mau.

## 3. Nada & bentuk (sama seperti halaman 1 yang sudah di-ACC)
- Inggris kasual, natural, ringan; pembaca **awam**; emoji di judul seksi secukupnya.
- R46: tetap ada **gerak** — tapi di halaman praktis ini geraknya bukan cerita, melainkan
  **"belum ada apa-apa → satu baris → udah jalan"**. Jangan jadi tabel spesifikasi.
- Perintah ditulis dalam blok `bash`. Satu per satu, jangan digabung dalam satu baris panjang.
- Panjang 300–420 kata (di luar blok kode).
- Nama produk `aigate` huruf kecil. Jangan tulis nama file sumber, path modul, atau nama tabel DB.
- Kalau nunjuk lokasi penyimpanan, sebut "folder sendiri di direktori rumah kamu", jangan nama file.
- DILARANG: `documents/**`, `src/**`, nama modul/fungsi, nomor internal/ADR, kata "MIT" (cukup
  "free and open source"), "this repo" (URL absolut — R45), "untested/experimental".
- Tautan internal hanya ke: Home, Quick-Start, Interfaces, Configuration-and-Keys, CLI-Tools,
  OpenAI-API, Terminal, Providers-and-Combos.
- Kredit terakhir tetap: "Made with ❤️ by Fadhly Permata".

## 4. Susunan yang gue saranin (bebas kamu rombak selama urut)
1. Satu kalimat: apa yang kamu dapet di akhir halaman ini.
2. `## What you need 🧰` — Python 3.10+, sisanya gak.
3. `## Get it running ▶️` — satu perintah + apa yang terjadi + buka alamatnya manual.
4. `## On your phone 📱` — Termux, perintah sama, catetan soal alat coding.
5. `## Port busy / on a shared network 🔌` — ganti port + **peringatan singkat**: alamatnya
   sengaja bisa diakses dari jaringan sekitar, jadi jangan dibiarin terbuka di tempat umum.
6. `## Your first three minutes ✨` — kunci → pilih → jalan.
7. `## When something goes wrong 🧯` — 3 hal paling umum, singkat, bukan daftar panjang.

## 5. Definisi selesai
- [ ] Hanya `Quick-Start.md` yang ditulis.
- [ ] Tidak ada satu pun perintah di luar §1.
- [ ] Tiga bug §2 gak muncul.
- [ ] Nada nyambung sama `Home.md` yang sudah di-ACC.
- [ ] Struk balik: naskah + hal yang kamu rasa masih kurang jelas buat orang awam.

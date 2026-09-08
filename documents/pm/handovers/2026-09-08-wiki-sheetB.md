# Lembar fakta B — halaman 5 `CLI-Tools.md` & halaman 6 `OpenAI-API.md`
**PM → business-analyst · 2026-09-08.** Sumber fakta = file INI SAJA (R44). Branch `docs/wiki`.
Tulis 2 file: `documents/pm/wiki-drafts/CLI-Tools.md` dan `documents/pm/wiki-drafts/OpenAI-API.md`.
Baca dulu `Home.md` + `Quick-Start.md` di `documents/pm/wiki-drafts/` buat nyamain suara.

# HALAMAN 5 — `CLI-Tools.md`
Fungsi: orang buka halaman ini karena mau alat coding yang SUDAH mereka pakai jalan di model pilihan
mereka. Tulis dari sudut itu, bukan dari sudut "fitur".

## Fakta
- **24 alat**, dikelompokkan 3 macam: **asisten coding agentik** (12), **agen software otonom** (6),
  **asisten chat & shell** (6). WAJIB ada catatan: daftarnya masih terus bertambah, dan sebagian
  jalur pasang belum ada di semua platform.
- Nama alat yang nyata ada (sebut sebagai contoh, jangan daftarin semua 24): claude, opencode,
  codex, gemini, aider, goose, amp, qwen, cline, kilo, openhands, open-interpreter, gptme, aichat, llm, sgpt, mods, oterm. Sisanya (antigravity, phi, swe-agent,
  autogpt, gpt-researcher, crewai) juga nyata.
- Alur pakai: buka area alat coding → pilih alat → pilih penyedia/model → alatnya **dibuka di tab
  terminal baru** dengan setelan yang udah disiapin.
- Cara penyetelannya **beda per alat**, dan ini penting ditulis buat orang yang penasaran: sebagian
  ditulisin ke **berkas konfigurasi alatnya**, sebagian lagi lewat **variabel lingkungan di depan
  perintah** (mis. alamat dasar + nama model). Jangan menyebut nama berkas spesifik.
- Aplikasi **ngerti kapan dia jalan di Termux** dan menawarkan perintah pasang yang cocok buat
  Android (berbeda dari desktop).
- Alat yang belum kepasang: aplikasinya **ngasih lihat perintah pasang**, bukan masang sendiri.
  Jangan klaim auto-install.
- Ada juga alat yang **gak bisa** diluncurin lewat fitur ini → aplikasi menandainya. Jangan bilang
  semua bisa.
- Setelah alatnya nyala: dia manggil alamat lokal aigate, jadi pemindahan penyedia/model keliatan
  dari dalam alatnya sendiri.

Panjang 320–430 kata. Sertai bagian "kalau alatnya protes" 2–3 poin pendek (belum dipilih
penyedia/model; perintah pasang belum dijalankan; alat-nya bukan jalur yang didukung).

# HALAMAN 6 — `OpenAI-API.md`
Fungsi: halaman buat developer yang mau manggil aigate dari program sendiri. Tetap awam di pembuka,
boleh teknis di badan.

## Fakta (semua dari kode)
- Alamat dasar: **`http://localhost:8080/v1`** (layar dan API = aplikasi & port yang sama; port bisa
  diganti lewat `AIGATE_PORT`).
- Titik layanan yang benar-benar ada: `GET /v1/models`, `POST /v1/chat/completions`,
  `POST /v1/responses`. **Jangan** nulis endpoint lain.
- Isi permintaan mengikuti format OpenAI: `model`, `messages`, `stream`, `temperature`, `max_tokens`.
  `stream: true` didukung (jawaban mengalir); respons non-stream juga didukung.
- Cara **memilih tujuan** lewat field `model`:
  - `combo:<nama>` → sebuah kombinasi penyedia yang udah disetel (kalau kombinasinya berisi beberapa
    anggota, yang dipakai duluan anggota prioritas teratas),
  - `<penyedia>:<model>` → satu penyedia spesifik,
  - **model polos tanpa awalan** → jalur yang dikenali sebagai OpenAI (alamat dasar milik
    penyedia yang lagi aktif).
- Kunci akses: kalau user menyalakan pembatasan akses pada endpoint-nya, kirim
  `Authorization: Bearer <kunci>`. Kalau **mati**, API ini terbuka buat siapa pun yang bisa nyentuh
  port-nya → peringatan wajib ditulis (jaringan sekitar!).
- Balikan biaya/pemakaian dicatat otomatis per permintaan (lihat halaman analisis), jadi API-nya
  bukan jalur "liar" yang gak ketrace.
- Sertakan **satu contoh curl** yang nyata:
  ```bash
  curl http://localhost:8080/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model":"combo:default","messages":[{"role":"user","content":"hello"}]}'
  ```
  (contoh memakai `combo:default` = nama kombinasi bawaan; kalau ragu nama itu ada, tulis
  `combo:<your-combo>` dan jelaskan).
- Satu contoh Python singkat memakai pustaka OpenAI resmi dengan `base_url` diarahkan ke alamat
  lokal boleh ditulis, **asal** diberi catatan bahwa itu pustaka pihak ketiga.

Panjang 380–500 kata (boleh paling panjang dari semua halaman karena halaman rujukan).

## Batas dua halaman (berlaku semua)
Inggris kasual, awam di pembuka; emoji di heading; heading `#` lalu `##`; produk `aigate` kecil.
DILARANG: path `src/**`/`documents/**`, nama fungsi/modul/tabel/kolom, nomor internal/ADR, "MIT",
"this repo" (R45), "untested/experimental" (R42). Jangan menyebut jumlah baris kode/commit/file.
Tautan internal hanya ke: Home, Quick-Start, Interfaces, Configuration-and-Keys, CLI-Tools,
OpenAI-API, Terminal, Providers-and-Combos. Kredit terakhir: "Made with ❤️ by Fadhly Permata".
JANGAN git commit/push.

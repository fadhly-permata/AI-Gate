# Handover — Wiki Rewrite, halaman 6 `OpenAI-API.md` (owner: public-writer)

**PM → public-writer · 2026-09-14 · branch `docs/wiki` · SEKUENSIAL (ke-4 dari 6).**

## Tugas
Tulis ULANG `documents/pm/wiki-drafts/OpenAI-API.md`. Sudut: programmer yang mau kirim request dari
**programnya sendiri** ke aigate. Buka dari keuntungan itu, bukan dari "fitur endpoint".

## Baca (READ, urutan)
1. `Home.md` + `Quick-Start.md` → suara ACC. JANGAN ubah.
2. `documents/pm/wiki-drafts/OpenAI-API.md` → draf lama.
3. `documents/pm/handovers/2026-09-08-wiki-sheetB.md` bagian "HALAMAN 6" → lembar fakta.
4. `documents/plan/wiki-plan.md` §2 → konten TERLARANG.
5. (opsional, read-only) `src/backend/gateway/router.py` untuk cek rute & bentuk request.

## Fakta (terverifikasi PM dari kode HARI INI)
- **Satu alamat lokal, satu port** (bawaan `8080`, bisa diganti). Bukan port kedua; endpoint cuma nama
  jalur yang dituju. (Koreksi #1.)
- Rute yang NYATA ada di gerbang (bukti `gateway/router.py`):
  - `POST /v1/chat/completions` (:139)
  - `POST /v1/responses` (:369)
  - `POST /v1/messages` (:528) — **Anthropic Messages** (dulu TIDAK ada; sekarang SUDAH). Terjemahkan
    ke jalur chat biasa → hasil dibalikin dalam bentuk Anthropic. **Non-streaming** (Stage 1).
  - `POST /v1/messages/count_tokens` (:688)
  - `GET /v1/models` (:737) — daftar model dibangun dari penyedia + combo (bukan daftar statis).
- Jadi: format request **kompatibel OpenAI** DAN format Anthropic sama-sama diterima di alamat yang
  sama. Boleh pakai istilah "OpenAI-compatible" (user sudah ACC istilah ini dipakai; wiki-plan §5 #3)
  — tapi **jelaskan singkat** dalam kalimat awam.
- **Kunci akses**: gerbang menerima `Authorization: Bearer <key>` ATAU header `x-api-key`
  (bukti `router.py:1183-1191`), dicek per endpoint kalau kunci endpoint dinyalakan.
  Kalau mati → siapa pun di jaringan itu bisa ikut pakai. Jujur soal ini.
- Contoh request: pakai `curl` ke `http://localhost:8080/v1/chat/completions` dengan `model` =
  **nama combo** (placeholder, JANGAN `default` — koreksi #3) dan `messages` singkat. Sertakan 1
  respons mini. Nilai `model` yang benar = nama combo / penyedia yang user bikin sendiri.
- Yang balik ke pemanggil: jawaban model + catatan token. Request yang gagal di satu anggota combo
  dicoba ke anggota berikutnya (lihat `Providers-and-Combos`) — cukup disebut 1 kalimat.
- Alamat bisa dipakai alat apa pun di jaringan yang sama → ingatkan lagi jangan di kafe/bandara.

## Yang harus berubah dari draf lama
- Tambah jalur **Anthropic** (`/v1/messages`) — draf lama kemungkinan belum tahu (dibuat sebelum fitur
  ini). Ini perbedaan nyata.
- Pembuka story motion; 1 ide 1 kalimat; contoh kode kecil, bukan referensi API lengkap.

## Larangan keras (sama halaman sebelumnya)
Path `src/**`/`documents/**`, nama file sumber, tabel/kolom DB, ADR/R#, "MIT", "this repo",
"untested/experimental", jumlah baris/komit. Rute HTTP & bentuk request **boleh** (memang diketik user).
`TODO-VERIFY` kalau ragu. `aigate` kecil. Taut cuma 8 nama halaman. Baris terakhir:
`Made with ❤️ by Fadhly Permata`. **JANGAN** git/commit/push/publik.

## Panjang
340–460 kata (badan), termasuk 1–2 blok kode pendek.

## DoD + Receipt
Format sama halaman 3. Peta klaim→bukti wajib menyebut `gateway/router.py:<line>` untuk tiap rute.

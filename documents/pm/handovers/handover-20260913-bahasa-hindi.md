# Handover — Tambah bahasa Hindi (`hi`) ke aigate

**Owner:** fe-dev (scope `src/frontend/**`, termasuk `src/frontend/tests/**`).
**Tanggal:** 2026-09-13. **Mode:** sekuensial, satu spesialis.
**Default ambigu yang PM ambil (D2, dicatat):** kode `hi`, nama endonim `हिन्दी`, bendera `🇮🇳` (Hindi standar, aksara Devanagari). Bukan Hindi romanisasi / Hinglish.

## Tujuan
Pemilih bahasa di Settings menampilkan Hindi; user bisa memilihnya dan seluruh UI tampil berbahasa Hindi.

## Fakta arsitektur i18n (baca sebelum edit)
- Satu berkas kamus per bahasa: `src/frontend/static/i18n/<code>.js`, self-register: `window.I18N = window.I18N || {}; window.I18N.<code> = { "kunci": "teks", ... }`.
- Registry tunggal: `window.LANGS` di `src/frontend/static/i18n.js:28-36`. Menambah bahasa = tambah 1 baris.
- Setiap kamus berisi **444 kunci identik** (dijaga paritas oleh `src/frontend/tests/i18n.test.js:88-101`, glob `static/i18n/*.js` — bahasa baru otomatis ditagih kunci sama persis dengan `en`).
- Nama bahasa = endonim (ditulis dalam bahasa itu sendiri), kunci `lang.<code>`, **ada di SEMUA kamus** (contoh: `en.js` menyimpan `"lang.ja": "日本語"`). Jadi tambah `hi` ⇒ kunci baru `lang.hi` WAJIB masuk ke 8 kamus (en, id, ru, nl, ja, zh, zh-tw, hi), bukan cuma hi.js.

## Yang harus dikerjakan (DEFINITION OF DONE)
1. **Buat `src/frontend/static/i18n/hi.js`** — salin struktur `en.js`, terjemahkan **semua 444 kunci** ke Hindi Devanagari yang natural.
   - Jaga kunci non-teks/placeholder teknis: `app.title` tetap `"aigate"`, `nav.repo` tetap `"aigate Repo"` (dijaga test `i18n.test.js:217-220`), jangan terjemahkan nama produk/merek.
   - Tambah `"lang.hi": "हिन्दी"` di file ini juga.
2. **Registry** `src/frontend/static/i18n.js:28-36`: tambah baris `{ code: "hi", flag: "🇮🇳", nameKey: "lang.hi" }` (pilih posisi — sarankan setelah `id` atau di akhir; konsisten dengan test EXPECTED di bawah).
3. **Kunci `lang.hi` ke 7 kamus lain** (en, id, ru, nl, ja, zh, zh-tw): tambahkan `"lang.hi": "हिन्दी"` (nilai endonim sama di semua kamus, konvensi berjalan). Tanpa ini paritas gagal.
4. **Update test registry** `src/frontend/tests/i18n.test.js:104-112`: array `EXPECTED` + nama tes "seven locales" → tambah `["hi","🇮🇳"]` (8 baris) sesuai posisi di LANGS. Test `keeps zh...` (130-133) biarkan.
5. **Cache-buster** `src/frontend/static/index.html`: naikkan `V` di :20 dan kedua tag `i18n.js?v=` (:1436) + `app.js?v=` (:1446) ke nilai 8-digit baru (mis. `20260924`). Invarian dijaga `i18n.test.js:307-316`: `I18N_VER == app.js?v == i18n.js?v`. (i18n.js berubah ⇒ wajib bump.)

## Verifikasi (WAJIB jalan sendiri sebelum balik)
- `node ./node_modules/.bin/vitest run src/frontend/tests/i18n.test.js` → semua hijau, termasuk paritas hi (444 kunci) + registry 8 bahasa.
- Lalu suite FE penuh: `node ./node_modules/.bin/vitest run` → tak ada regresi (baseline 27 berkas / 685 tes).
- `git diff --check` bersih.
- **JANGAN commit / push** — PM yang audit + gate + commit.

## Batasan scope
- Tulis HANYA di `src/frontend/**`. Jangan sentuh `src/backend/**`, `documents/pm/**`, atau berkas agent/skill.
- Receipt wajib: daftar berkas berubah, jumlah kunci hi.js (harus 444), hasil vitest (i18n + penuh), keputusan posisi LANGS, dan flag hasil test registry.

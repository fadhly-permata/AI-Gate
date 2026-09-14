# Handover — Wiki Rewrite, halaman 4 `Configuration-and-Keys.md` (owner: public-writer)

**PM → public-writer · 2026-09-14 · branch `docs/wiki` · SEKUENSIAL (halaman 3 sudah, ini ke-2 dari 6).**

## Tugas
Tulis ULANG `documents/pm/wiki-drafts/Configuration-and-Keys.md` pakai suara & standar Public Writer.
Baca draf lama sebagai bahan mentah. Jangan salin.

## Baca (READ, urutan)
1. `documents/pm/wiki-drafts/Home.md` + `Quick-Start.md` → suara ACC (patokan). JANGAN ubah.
2. `documents/pm/wiki-drafts/Configuration-and-Keys.md` → draf lama.
3. `documents/pm/handovers/2026-09-08-wiki-sheetA.md` bagian "HALAMAN 4" → lembar fakta resmi.
4. `documents/plan/wiki-plan.md` §2 → konten TERLARANG.

## Fakta yang BOLEH dipakai (terverifikasi PM dari kode hari ini, branch `docs/wiki`)
Lokasi bukti PM (boleh baca read-only): `src/backend/config/settings.py`, `src/frontend/static/index.html`
(setting view ~baris 200–280), `src/backend/config/db.py`.
- **Penyedia** ("Provider") menyimpan: nama; jenis (`openai`, `anthropic`/`claude`, `gemini`, `ollama`,
  `openrouter`, `litellm`, `openai-compatible`, `cursor`, `kiro`, `vertex`, `antigravity`, `other`;
  yang tak dikenal = jalur OpenAI → aman); alamat dasar (`base_url`, **boleh `http://`/`localhost`** →
  model lokal masuk tanpa fitur tambahan); kunci API; nyala/mati; tingkat layanan (bawaan "subscription");
  batas kuota + jangka; header tambahan; model bawaan. Tulis sebagai kalimat — **jangan** sebut nama field.
- **Kunci disimpan tanpa enkripsi** di basis data folder `.aigate` di direktori rumah user (sebut
  sekadarnya `aigate.db` biar user tahu mau dicadangkan ke mana). Alat ini untuk perangkat sendiri;
  kalau perangkat ilang/dipegang orang lain, siapa pun yang baca file itu baca kuncinya. Saran: jangan di
  perangkat bersama.
- Penyedia tertentu bisa **masuk pakai akun** (OAuth) bukan cuma tempel kunci; arahkan ke layarnya,
  jangan jelaskan langkah OAuth detail.
- **Di mana disimpan**: semua setelan + catatan masuk = satu file DB di `.aigate`. Bisa dipindah via
  variabel lingkungan `AIGATE_DB_PATH`. Cuma **3** variabel lingkungan yang dikenal app:
  `AIGATE_PORT`, `AIGATE_DEV`, `AIGATE_DB_PATH`.
- **Ekspor** setelan jadi JSON unduhan (pindah/cadangan antar perangkat), dan **ekspor laporan** CSV.
  Peringatkan: file JSON unduhan itu berisi kunci → jangan di-commit.
- **Alamat & port**: layar + API = **satu aplikasi di satu port** (bawaan `8080`; ganti dari layar
  setelan pilihan "Port", atau via `AIGATE_PORT`).
  ⚠️ **KOREKSI FAKTA #1**: field host/port pada endpoint **TIDAK membuka port baru** — tak ada kode
  yang pakai nilainya untuk listen. Jangan tulis "set endpoint ke 127.0.0.1 biar cuma dari perangkat".
  Yang benar: satu-satunya pembuka akses nyata = alamat dengar aplikasi (`0.0.0.0` → kelihatan dari
  jaringan sekitar) + **kunci akses per endpoint** yang ditegakkan di gerbang.
- Alamat disodorkan ke alat coding = `http://localhost:8080/v1` (bawaan); satu nilai setelan, bisa diganti.
- **Setelan di layar** (terverifikasi hari ini, `settings.py`): Port, Mode Developer, Tema (terang/gelap),
  Bahasa. Juga: pencatatan detail per request (MATI bawaan), umur simpan catatan log (bawaan 7 hari),
  batas waktu sesi terminal yang lepas (bawaan 60 menit). Tulis sebagai kalimat, jangan nama field.
- **Proxy keluar** (request ke penyedia) opsional: satu kolam per endpoint, anggota host+port+protokol,
  rotasi bawaan bergantian, status/kelambatan tiap anggota tercatat. Fitur lanjutan — tulis singkat.
- Jumlah bahasa aplikasi = **delapan (8)**: English, Indonesian, Chinese, Traditional Chinese, Japanese,
  Russian, Dutch, Hindi. Jangan tulis "seven".

## Yang harus berubah dari draf lama
- Pembuka wajib story motion (character → want → obstacle → action → changed result).
- Penutup wajib ada 1 langkah: "setelah isi kunci, pilih penyedia mana yang dipakai" (gerbang ke halaman berikutnya).
- 1 ide 1 kalimat; hindari brosur ("powerful", "seamless").
- Nol rujukan self-relative (R45).

## Larangan keras (R44/R42/R23/R45)
Sama seperti halaman 3 (path `src/**`/`documents/**`, nama file sumber, tabel/kolom DB, ADR/R#,
"MIT", "this repo", "untested/experimental", nama field apa adanya, jumlah baris/komit). Jangan
nebak — `TODO-VERIFY: <cara cek>` kalau ragu. `aigate` kecil. Taut internal cuma 8 nama halaman.
Baris terakhir: `Made with ❤️ by Fadhly Permata`. **JANGAN** git/commit/push/publik.

## Panjang
340–460 kata (badan).

## Definition of done + Receipt
Sama format halaman 3 (lihat `handover-20260914-wiki-rewrite-1-interfaces.md`). Berikan peta
klaim→bukti (rujuk lembar fakta A / draf lama / `file:line`), beda vs draf lama, `TODO-VERIFY`,
titik review, pengakuan jujur.

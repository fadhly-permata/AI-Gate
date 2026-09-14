# Handover — Wiki Rewrite, halaman 3 `Interfaces.md` (owner: public-writer)

**PM → public-writer · 2026-09-14 · branch `docs/wiki` · mode: SEKUENSIAL (satu halaman, stop untuk review user).**

## Goal
Tulis ULANG (`rewrite`) halaman wiki "Interfaces" memakai suara & standar Public Writer. Naskah lama
ada — baca sebagai bahan mentah, bukan untuk disalin. Hasil akhir: satu halaman yang bikin pembaca
awam tahu **lewat mana saja aigate bisa dipakai** dan harus klik apa.

## Target file (WRITE)
- `documents/pm/wiki-drafts/Interfaces.md` — timpa isi file ini saja.
- DILARANG menyentuh 7 file lain di `wiki-drafts/`, `README.md`, `documents/readme-variants/**`,
  `src/**`, `tests/**`, `documents/pm/**` (kecuali baca).

## Baca ini dulu (READ — urutan wajib)
1. `documents/pm/wiki-drafts/Home.md` + `Quick-Start.md` → **suara yang sudah di-ACC user**. Ini
   patokan gaya. Jangan ubah 2 file itu.
2. `documents/pm/wiki-drafts/Interfaces.md` → draf lama (fakta sudah terverifikasi PM).
3. `documents/pm/handovers/2026-09-08-wiki-sheetA.md` bagian "HALAMAN 3" → lembar fakta resmi
   halaman ini (satu-satunya sumber fakta, R44).
4. `documents/plan/wiki-plan.md` §2 → daftar konten yang DILARANG muncul di wiki.

## Fakta yang boleh dipakai (sudah diverifikasi PM — jangan lebih, jangan kurangi jadi ngarang)
Empat cara memakai aigate, semuanya **satu aplikasi di satu alamat lokal yang sama**:
1. **Layar di browser** — `http://localhost:8080` setelah `python run.py` (browser TIDAK terbuka
   sendiri). Area kerja yang nyata ada di aplikasi: welcome (layar pertama), providers, combos,
   endpoints, proxies, cli (alat coding), terminal, usage, analytics, settings.
   → Sebut dalam kalimat natural. **DILARANG** bilang "ada N view/menu", **DILARANG** bikin tabel mentah.
2. **Terminal di dalam browser** — tab jamak, layar penuh, pecah layar, tahan-nyala, kontrol
   mengambang → taut ke `Terminal`.
3. **Satu alamat lokal yang bisa dipakai program apa pun** → taut ke `OpenAI-API`.
4. **Alat coding yang sudah dipakai user**, diluncurkan dari dalam aplikasi dengan model sudah
   disetel; daftar alat masih bertambah → taut ke `CLI Tools`.
- **Endpoints** = nama jalur yang dituju + bisa dikunci akses sendiri; **bukan** port kedua
  (fact koreksi #1 — jangan tulis bahwa host/port endpoint membuka port baru).
- **Proxy Pools** = kolam proxy keluar, fitur lanjutan, cukup disebut satu frasa.
- Bisa dibuka dari HP/laptop lain di jaringan sama → itu sebabnya peringatan "jangan di kafe"
  di Quick Start ada.
- Semua aset UI lokal, nol permintaan ke internet **selain** ke penyedia yang user pilih
  (vendor Font Awesome lokal sudah terverifikasi; fakta ini boleh ditulis).
- Jumlah bahasa aplikasi = **delapan (8)**. Jangan tulis "seven".

## Yang harus berubah dari draf lama
- Pembuka **wajib** pakai story motion (character → want → obstacle → action → changed result),
  bukan kalimat klaim doang. Pembuka draf lama sudah接近 — pertajam konfliknya, bikin lebih spesifik.
- Satu ide per kalimat; kalimat pendek; hindari frasa brosur ("powerful", "seamless", "effortless").
- Jangan ada rujukan self-relative ("this repo", "the link above", "see file") — R45.
- Heading pakai emoji secukupnya; `#` lalu `##`.

## Batas keras (R44 / R42 / R23 / R45)
- DILARANG muncul: path `src/**` atau `documents/**`, nama berkas/folder sumber, nama tabel/kolom
  DB, nomor internal (ADR-###, R#, §), kata "MIT", "this repo", "untested/experimental/belum
  diverifikasi", nama field konfigurasi apa adanya (`base_url`, `AIGATE_PORT`, dsb. → tulis sebagai
  kalimat).
- DILARANG menulis jumlah baris/komit/file repo.
- Klaim yang tidak ada di lembar fakta → tandangi **`TODO-VERIFY: <cara cek>`**. NEBAK = gagal.
- Produk ditulis `aigate` huruf kecil. Nama halaman lain di file wiki pakai tanda hubung persis:
  `Home`, `Quick-Start`, `Interfaces`, `Configuration-and-Keys`, `CLI-Tools`, `OpenAI-API`,
  `Terminal`, `Providers-and-Combos`. Taut internal hanya ke 8 nama itu.
- Baris terakhir wajib: `Made with ❤️ by Fadhly Permata`.
- **JANGAN** git add / commit / push. **JANGAN** menulis ke GitHub wiki asli (publik). Ini draft.

## Panjang
220–320 kata (badan halaman, di luar judul & kredit). Jangan gembungkan.

## Definition of done
- [ ] `documents/pm/wiki-drafts/Interfaces.md` ditulis ulang total, suara sama dengan Home/Quick-Start.
- [ ] Semua fakta berasal dari lembar fakta A / draf lama yang sudah diverifikasi; sisanya `TODO-VERIFY`.
- [ ] Nol kata & pola terlarang (cek sendiri daftar di atas, baris per baris).
- [ ] 4 cara pakai tersaji + tautan ke halaman masing-masing; link internal valid.
- [ ] Kredit utuh di baris terakhir; `aigate` kecil; nama file wiki persis.
- [ ] Tidak ada file lain yang berubah.

## Receipt yang PM minta (balas dalam satu pesan)
1. File yang diubah (harus cuma 1).
2. **Peta klaim → bukti**: tiap fakta di naskah baru → rujuk ke baris mana di lembar fakta A /
   draf lama / `file:line` kode kalau kamu memang membaca kode.
3. Beda utama vs draf lama (3–6 poin): apa yang diubah dan kenapa lebih enak dibaca.
4. `TODO-VERIFY` yang tersisa (kalau ada) + cara cek-nya.
5. Pertanyaan terbuka buat PM/user.

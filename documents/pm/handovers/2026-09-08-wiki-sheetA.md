# Lembar fakta A — halaman 3 `Interfaces.md` & halaman 4 `Configuration-and-Keys.md`
**PM → business-analyst · 2026-09-08.** Sumber fakta = file INI SAJA (R44). Branch `docs/wiki`.
Tulis 2 file: `documents/pm/wiki-drafts/Interfaces.md` dan `documents/pm/wiki-drafts/Configuration-and-Keys.md`.
Suara = sama dengan `Home.md`/`Quick-Start.md` yang sudah di-ACC (baca 2 file itu dulu).

## Konteks yang berubah sejak halaman 1
UI sekarang **100% lokal**: tidak ada satu pun aset yang diambil dari internet. Yang keluar cuma
request ke penyedia AI yang user pilih sendiri. Boleh ditulis sebagai fakta.

# HALAMAN 3 — `Interfaces.md`
Fungsi: peta "lewat mana aja aigate bisa dipake", supaya pembaca tau mana yang harus diklik.
Tautkan ke halaman yang ngelindungin tiap cara. **Jangan** jadi 6 halaman kecil — cukup 4 cara:

1. **Layar di browser** (`http://localhost:8080`, dibuka sendiri setelah `python run.py`).
   Isinya 10 area kerja yang nyata ada di aplikasi:
   `welcome` (layar pertama), `providers`, `combos`, `endpoints`, `proxies`, `cli` (alat coding),
   `terminal`, `usage`, `analytics`, `settings`.
   Sebut namanya dalam kalimat natural (jangan tabel mentah, jangan bilang "ada 10 view").
   Bisa diakses dari HP maupun laptop di jaringan yang sama → itu sebabnya peringatan jaringan
   di Quick Start ada.
2. **Terminal di dalam browser** → banyak tab, layar penuh, pecah layar, tahan-nyala (layar gak
   tidur), control mengambang. Detail: [Terminal](Terminal).
3. **Satu alamat API yang bisa dipakai program lain** ([OpenAI API](OpenAI-API)).
4. **Alat coding yang sudah lu kenal** — diluncurin dari dalam aplikasi, modelnya udah disetel
   ([CLI Tools](CLI-Tools)).

Panjang 220–320 kata. Jangan klaim fitur yang gak ada di daftar atas.

# HALAMAN 4 — `Configuration-and-Keys.md`
Fungsi: dari nol sampai kunci terpasang, + di mana semuanya disimpan + batas keamanannya jujur.

## Yang disimpan per penyedia (ini isi "Provider")
Nama · jenis (`openai`, `anthropic`/`claude`, `gemini`, `ollama`, `openrouter`, `litellm`,
`openai-compatible`, `cursor`, `kiro`, `vertex`, `antigravity`, `other` — **yang tidak dikenal
dianggap jalur OpenAI**, jadi aman) · alamat dasar (`base_url`, **boleh `http://`, boleh localhost**
→ di sinilah model lokal masuk tanpa fitur tambahan) · kunci API · nyala/matikan · tingkat layanan
(default "subscription") · batas kuota + jangkaunya · header tambahan · model bawaan.
JANGAN menulis nama field-nya apa adanya — tulis dalam kalimat ("alamat tempat penyedia menjawab").

## Kunci & akun
- Kunci disimpan **tanpa enkripsi** di file datanya. Fakta wajib + alasannya: alat ini untuk
  perangkat milik sendiri; kalau perangkatnya kepakai orang lain / ilang, siapa pun yang bisa baca
  file itu bisa baca kuncinya. Sarankan: jangan taruh di perangkat bersama.
- Penyedia tertentu bisa **masuk pakai akun** (alur OAuth tersedia), bukan cuma tempel kunci.
  Jangan jelaskan langkah OAuth detail-detail — arahkan ke layarnya.

## Di mana semuanya disimpan
- Semua pengaturan & catatan masuk **satu file basis data di folder `.aigate` di direktori rumah
  user**. Nama file boleh disebut sekadarnya (`aigate.db`) karena user perlu tau mau dicadangkan
  kemana; JANGAN sebut path modul/src.
- Bisa dipindah lewat variabel lingkungan `AIGATE_DB_PATH`.
- **Cuma ada 3** variabel lingkungan yang dikenal aplikasi: `AIGATE_PORT`, `AIGATE_DEV`,
  `AIGATE_DB_PATH`. Jangan bikin variabel baru.
- Ada **ekspor** setelan jadi satu berkas JSON unduhan (buat mindahin ke perangkat lain / cadangan),
  dan **ekspor laporan** jadi CSV. Peringatan: berkas unduhan itu berisi kunci → jangan di-commit.

## Alamat & port
- Layar + API = **aplikasi yang sama, port yang sama** (bawaan `8080`, diganti `AIGATE_PORT`).
- Alamat dengar aplikasi `0.0.0.0` → kelihatan dari jaringan sekitar. Untuk yang mau dibatasi ke
  perangkat saja, itu ada di pengaturan endpoint (tiap endpoint bisa diset host lokal
  `127.0.0.1` dan port sendiri, bawaan `8000`).
- Endpoint bisa dilengkapi **kunci akses sendiri** (nyala/matikan + satu kunci internal). Kalau
  mati, siapa pun di jaringan itu bisa pakai. Jujur soal ini.
- Proxy keluar (untuk request ke penyedia) itu **opsional**: satu kolam per endpoint, anggotanya
  host+port+protokol, rotasi bawaan bergantian, dan aplikasi nyatetin status/kelambatan tiap
  anggota. Tulis singkat sebagai fitur lanjutan; jangan digarang lebih.

Panjang 340–460 kata. Sertai 1 langkah "setelah kamu isi kunci, pilih penyedia mana yang dipakai"
karena itu gerbang kehalaman berikutnya.

## Batas dua halaman (berlaku semua)
Inggris kasual, awam, emoji di heading, heading `#` lalu `##`. Produk `aigate` kecil. DILARANG:
path `src/**`/`documents/**`, nama field tabel/kolom, nomor internal/ADR, kata "MIT",
"this repo" (R45), "untested/experimental" (R42), nama file sumber. Tautan internal hanya ke:
Home, Quick-Start, Interfaces, Configuration-and-Keys, CLI-Tools, OpenAI-API, Terminal,
Providers-and-Combos. Kredit terakhir: "Made with ❤️ by Fadhly Permata". JANGAN git commit/push.

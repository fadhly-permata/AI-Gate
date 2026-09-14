# Handover — Wiki Rewrite, halaman 8 `Providers-and-Combos.md` (owner: public-writer)

**PM → public-writer · 2026-09-14 · branch `docs/wiki` · SEKUENSIAL (ke-6 & terakhir dari 6).**

## Tugas
Tulis ULANG `documents/pm/wiki-drafts/Providers-and-Combos.md`. Ini halaman **model mental**: provider
→ combo → mana yang dipakai duluan, apa yang terjadi kalau satu gagal/kehabisan kuota. Tulis awam,
satu ide satu kalimat, contoh ringan.

## Baca (READ, urutan)
1. `Home.md` + `Quick-Start.md` → suara ACC. JANGAN ubah.
2. `documents/pm/wiki-drafts/Providers-and-Combos.md` → draf lama.
3. `documents/pm/handovers/2026-09-08-wiki-sheetC.md` bagian "HALAMAN 8" → lembar fakta.
4. `documents/plan/wiki-plan.md` §2 → konten TERLARANG.
5. (read-only) `src/backend/combo_routing.py`, `src/backend/providers.py`/`providers_router.py`,
   `src/frontend/static/index.html` (kartu provider-detail KARTU A/B, ~baris 300–430; combo form
   ~1090–1110).

## Fakta (terverifikasi PM dari kode HARI INI)
- **Provider** = satu layanan AI (openai, anthropic/claude, gemini, ollama, openrouter, litellm,
  openai-compatible, cursor, kiro, vertex, antigravity, other; yang tak dikenal = jalur OpenAI).
  Satu provider boleh punya **beberapa akun** (multi-akun). Urutan akun = **priority**; ada metode
  rotasi akun per provider (lihat bawah).
- **Combo** = grup provider/akun yang kau susun; tiap combo memberi **satu alamat lokal rapi**.
  Mana provider yang jawab = urusan aigate, bukan user. **TIDAK ada combo bawaan bernama `default`**
  (KOREKSI #3) → semua contoh pakai **placeholder nama** (mis. "My Combo"), jangan tulis `default`.
- **Strategi combo** (pilihannya nyata ada di UI, `index.html:1100-1107`; mesin `combo_routing.py`):
  - `fallback` (**bawaan**) — coba anggota berurutan **priority naik**; kalau satu gagal/error, lanjut
    ke berikutnya. Satu percobaan, tanpa ulang.
  - `load_balance` — pilih acak **berbobot** (bobot `weight` > 0).
  - `latency_cost` — pilih **bobot terendah** (biaya relatif), seri dilawan priority naik.
  - `three_tier` — urut per **tingkat layanan** (subscription → murah → gratis) lalu priority naik.
  - `round_robin` — satu anggota bergiliran (cursor priority naik, berputar), abaikan bobot; maju tiap
    dipakai. (Bila perlu, optional batas "pakai N kali per akun sebelum giliran" ada di level rotasi akun.)
- **Rotasi akun per provider** (kartu provider-detail, `index.html:401-424`): metode `fill-first`
  (isi akun pertama sampai habis lalu lanjut) atau `round-robin` + **batas sticky** ("uses per account
  before rotating"). Tulis awam: "jalanin akun sampai kuota habis, lalu pindah".
- **Saat satu anggota gagal / kena kuota**: aigate pindah ke anggota berikutnya **tanpa kirim ulang**
  request (draf lama bilang "without a resend" — benar, pertahankan). User nggak perlu repot ganti apa pun.
- **Endpoint** (lihat `Configuration-and-Keys` / `OpenAI-API`): satu combo → satu alamat; tiap endpoint
  bisa punya **kunci akses sendiri** + boleh pakai **Proxy Pool** keluar (kolam host+port+protokol,
  rotasi bawaan bergantian, status/kelambatan tiap anggota tercatat). Singkat, awam.
- Jangan bikin contoh JSON/skema; pakai satu contoh kalimat: "kumpulkan 3 provider jadi satu combo,
  panggil lewat satu alamat, biarkan aigate yang giliran".

## Yang harus berubah dari draf lama
- Strategi sekarang 5 pilihan (bukan cuma fallback) — draf lama kemungkinan hanya tahu 2–3. Update.
- Buang segala rujukan combo `default`.
- Pembuka story motion (provider mati di tengah kerja → aigate sudah pindah sendiri).

## Larangan keras (sama halaman sebelumnya)
Path `src/**`/`documents/**`, nama file/id DOM, tabel/kolom DB, ADR/R#, "MIT", "this repo",
"untested/experimental", nama field setelan apa adanya (→ kalimat), jumlah baris/komit.
`TODO-VERIFY` kalau ragu. `aigate` kecil. Taut cuma 8 nama halaman. Baris terakhir:
`Made with ❤️ by Fadhly Permata`. **JANGAN** git/commit/push/publik.

## Panjang
380–480 kata (badan).

## DoD + Receipt
Format sama halaman 3. Peta klaim→bukti wajib `file:line` (`combo_routing.py`, `index.html`) untuk tiap
strategi yang ditulis. Sebut eksplisit kalau kamu membuang `default`.

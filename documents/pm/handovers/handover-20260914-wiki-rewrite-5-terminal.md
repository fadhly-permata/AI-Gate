# Handover — Wiki Rewrite, halaman 7 `Terminal.md` (owner: public-writer)

**PM → public-writer · 2026-09-14 · branch `docs/wiki` · SEKUENSIAL (ke-5 dari 6).**

## Tugas
Tulis ULANG `documents/pm/wiki-drafts/Terminal.md`. Terminal di dalam browser itu fitur yang paling
bikin orang kagok ("bisa gitu?") — jual **geraknya**: dulu butuh SSH / aplikasi terpisah, sekarang
satu tab.

## Baca (READ, urutan)
1. `Home.md` + `Quick-Start.md` → suara ACC. JANGAN ubah.
2. `documents/pm/wiki-drafts/Terminal.md` → draf lama.
3. `documents/pm/handovers/2026-09-08-wiki-sheetC.md` bagian "HALAMAN 7" → lembar fakta.
4. `documents/plan/wiki-plan.md` §2 → konten TERLARANG.
5. (read-only, WAJIB buat koreksi) `src/frontend/static/index.html` baris ~773–850 (toolbar terminal)
   dan `src/frontend/static/terminal.js`.

## ⚠️ KOREKSI PENTING (lembar fakta C sudah basi — jangan ditelan mentah)
PM ukur dari kode hari ini:
- **TIDAK ADA "pecah layar" / split view.** Kontrol yang nyata ada (bukti `index.html:789-835`):
  - tab jamak + tombol **tab baru** (`termNewTab` :781)
  - **Paste** biasa DAN **Paste as Code Block** (menu kecil, :804-805)
  - menu **Settings**: **TUI Passthrough** (:818) dan **Keep Screen On** (:819)
  - **Full Page** (:830) dan **Fullscreen** (:831) — dua hal beda, tulis sebagai kalimat awam
  - gugus **kontrol mengambang** di pojok (`termFloating` :789)
  → Jadi JANGAN tulis "split screen/pecah layar". Tulis yang ada di atas.
- **Riwayat gulir = 5000 baris** (`terminal.js:575` `scrollback: 5000`). Boleh disebut sebagai angka.
- Konek ulang otomatis ada (backoff, `terminal.js` `computeBackoffDelay`); "hidup" sesi dicek lewat
  ping ±15 detik, socket dianggap mati setelah 3 ping hilang (`terminal.js:396` LIVENESS_MS 45000).
  Cukup ditulis "kalau koneksi sempat putus, tab menyambung lagi sendiri" — jangan sebut angka teknis.
- Halaman dibuka ulang: tab yang tadi hidup dipulihkan (`terminal.js:617` — Chrome discarded tab).
  Boleh disebut singkat: "tutup-buka halaman, tab-nya balik".

## Fakta lain yang masih berlaku (sheet C)
- Terminal **sungguhan**: tiap tab = sesi nyata di perangkat itu (bukan gambar terminal).
- **Tempel**: isi clipboard disuntik ke sesi aktif, fokus **balik otomatis** ke terminal.
- **Gulir & usap**: roda mouse + gestur usap trackpad/jari jalan. Pada aplikasi TUI (vim/htop/less),
  usap diterjemahkan jadi input gulir aplikasi itu; arah natural; lepas jari ikut 1:1.
- **Kegagalan tool**: kalau perintah/alat nggak ada atau gagal, yang muncul pesan yang bisa dibaca
  (bukan crash). Kalau user butuh, aigate menyodorkan perintah pasang yang cocok perangkat (Termux).
- **Sesi tidak dibunuh saat koneksi putus**: view lepas, proses tetap jalan + menampung keluaran
  (KOREKSI #2 dari sheet lama — ini penting). Sesi dihapus hanya kalau ditutup sendiri, atau lepas DAN
  tanpa keluaran; batas idle bawaan 60 menit (`terminal_idle_reap_minutes`). Tulis awam: "putus
  koneksi ≠ pekerjaanmu berhenti".
- Batas: ini shell di perangkat tempat aigate jalan — bukan mesin lain.

## Yang harus berubah dari draf lama
- Buang "pecah layar" + sebut kontrol yang benar (paste-as-code, TUI passthrough, keep-screen-on,
  full page/fullscreen, kontrol mengambang).
- Pembuka story motion (mobilitas: kerja di HP, satu tab, bukan SSH).

## Larangan keras (sama halaman sebelumnya)
Path `src/**`/`documents/**`, nama file sumber/id DOM, tabel/kolom DB, ADR/R#, "MIT", "this repo",
"untested/experimental", nama variabel setelan apa adanya (→ kalimat), jumlah baris/komit.
`TODO-VERIFY` kalau ragu. `aigate` kecil. Taut cuma 8 nama halaman. Baris terakhir:
`Made with ❤️ by Fadhly Permata`. **JANGAN** git/commit/push/publik.

## Panjang
400–500 kata (badan). Jangan balik ke 555.

## DoD + Receipt
Format sama halaman 3. Peta klaim→bukti wajib `file:line` (terminal.js / index.html) untuk tiap kontrol
yang ditulis. Sebutkan eksplisit kalau kamu memang membuang "split view".

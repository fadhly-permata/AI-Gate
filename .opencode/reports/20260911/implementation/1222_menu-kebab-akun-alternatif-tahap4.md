# Laporan Tugas: Tahap-4 — Masuk Halaman Rinci Penyedia Lewat Menu Tiga Titik

## Informasi Dasar
- Tanggal: 2026-09-11
- Jenis Tugas: build (frontend) — koreksi akses hasil tahap-3
- Waktu Mulai: 12:10 · Selesai: 12:25
- Eksekutor: sub-agent `fe-dev` (Task tool, sesi `ses_f7120e2ccffem9h33yJ4YyLUwl`), satu putaran
- Pencatat: ProjectManager (akar tulis `fe-dev` hanya `src/frontend/**` — tabrakan aturan `task-report.md`
  vs `agent-boundaries.md` masih menunggu putusan user)

## Permintaan Pengguna
Setelah mencoba tampilan hasil tahap-3 user menulis: "oh disitu aksesnya... aneh kalo tap/klik di namanya
gitu, bikin menu baru aja dengan nama alternatif/sekunder akun. dan menu itu digabung dengan menu dari
tombol tiga titik di ujung kanan aja".

Aturan D6 (lembar desain + ACC sebelum kode) dianggap TERPENUHI oleh user sendiri: bentuk, nama, dan
letak menu ditentukan user secara eksplisit, bukan oleh PM. PM hanya mengunci 4 default kecil (lihat §Realisasi).

## Rencana Pekerjaan
1. PM memverifikasi infrastruktur menu baris (`rowMenuCellHtml` `app.js:732-738`, `wireRowMenu` `:740-749`)
   agar permintaan "digabung dengan menu tiga titik" tidak melahirkan tombol kedua.
2. Handover pendek (aturan E2/E3: task kecil = handover pendek) ke `fe-dev`: 6 butir pekerjaan + batas tulis + definisi selesai.
3. Gate PM mandiri, lalu commit terpisah (kode vs dokumen).

## Realisasi Pekerjaan
- 12:12 langkah 1 selesai. Menu baris sudah generik (satu tombol ⋮ per baris, isi dari daftar aksi) →
  permintaan user bisa dipenuhi tanpa mengubah infrastruktur.
- 12:20 langkah 2 selesai. 13 berkas `src/frontend/**` diubah (+63/−55):
  - `static/app.js:793-798` — sel Nama kembali TEKS POLOS; `button.prov-name-btn.js-prov-detail` dihapus;
    listener delegasi `data-detail-wired` (:809-822) ikut dihapus karena tak terpakai; `openDetail(id)` tetap ada
    dan kini dipanggil dari item menu (`:813-821`).
  - `static/app.js:812-822` — menu ⋮ penyedia kini TIGA item berurutan: `accounts` (label `providers.accounts_menu`
    = "Akun alternatif/sekunder", ikon `fa-users`, bukan bahaya) → `edit` → `delete`. Satu tombol ⋮, bukan dua.
  - `static/styles.css` — rule `.prov-name-btn` (+`hover`/`focus-visible`) DIHAPUS setelah dicek 0 pemakaian
    tersisa; 0 rule baru; 0 warna hex baru. Sel Nama kini polos seperti tabel kombo/pool/endpoint (konsistensi).
  - `static/i18n/{en,id,ru,nl,ja,zh,zh-tw}.js` — +1 kunci `providers.accounts_menu` (EN "Alternative/secondary
    accounts") → 428 → **429 kunci per kamus**.
  - `static/index.html` — cache-buster `V`/`styles.css?v=`/`i18n.js?v=`/`app.js?v=` naik serentak ke `20260917`
    (penjaga `tests/i18n.test.js:307-316` menuntut ketiganya sama).
  - `tests/row-actions.test.js:26-57` — assert urutan tiga item + label + ikon + non-bahaya + Nama bukan tombol.
  - `tests/provider_detail.test.js:175-190, 800-806` — jalur masuk lewat ⋮ → item akun; plus penjaga negatif:
    mengklik nama TIDAK membuka halaman; alur penuh 6 langkah disesuaikan langkah pertamanya.
  - `e2e/b5_features.mjs:13-14,145-153` — alur ⋮ dulu lalu `[data-action="accounts"]` (menu menempel di `<body>`,
    bukan di baris) + assert Nama bukan tombol. `node --check` exit 0; TIDAK dijalankan (nol browser).
  - `tests/views.test.js` + `tests/providers.test.js` — 0 rujukan ke tombol nama, jadi tidak diubah (diperifikasi grep).
- 4 default ambigu yang PM kunci (dicatat, user boleh veto): (1) item akun membuka HALAMAN RINCI (bukan lompat ke
  kartu akun saja) karena halaman itu juga memuat strategi pergiliran; (2) label persis "Akun alternatif/sekunder";
  (3) urutan akun → ubah → hapus; (4) menu ⋮ di baris kombo/pool/endpoint tidak disentuh.
- 12:22 langkah 3 — GATE PM MANDIRI: `node node_modules/.bin/vitest run` = **24 berkas / 586 tes LOLOS**
  (identik baseline → nol pengurangan cakupan, nol merah); `i18n-parity-check.mjs` (en/id/zh-tw diperiksa
  langsung) = 429 kunci, hilang 0, thừa 0, kosong 0; `git status --short` = 13 berkas semuanya `src/frontend/**`
  (nol `src/backend/**`, nol `combos.js`, nol `usage.js`); grep `prov-name-btn` di seluruh `src/frontend` = **0**;
  0 warna hex baru; `git diff --check` bersih; `node --check` berkas e2e exit 0.
- BUKTI GLIF: `fa-users` diverifikasi ada di Font Awesome Free 6.5.1 yang benar-benar di-load aplikasi
  (unduhan CSS yang sama, aturan `.fa-users:before{content:"\f0c0"}`).
- TEMUAN (di luar cakupan, tidak disentuh): Font Awesome dimuat dari **CDN cloudflare** (`index.html:42`) —
  utang lama WL.5 yang sudah tercatat (ikon mati saat offline, permintaan keluar). Perlu keputusan user.

## Status Akhir
**BERHASIL di tingkat tes.** Akses ke halaman rinci penyedia sekarang lewat menu tiga titik dengan nama
"Akun alternatif/sekunder", persis permintaan user; nama penyedia tidak lagi bisa diklik.
BELUM diverifikasi (jujur): belum dilihat di peramban nyata (aturan G3) — bagian tampilan dibaca ulang dari
berkas tiap permintaan sehingga TIDAK perlu memuat ulang server, cukup muat ulang halaman di peramban;
jalur ⋮ → item menu belum pernah dieksekusi sungguhan (nol browser di lingkungan ini); terjemahan 6 bahasa
non-Inggris belum ditinjau penutur. Repo lokal `refactor/ui` ahead 9 → akan jadi 10 setelah commit dokumen ini;
PR #17 masih terbuka; push menunggu perintah user.

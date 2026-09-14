# Laporan Tugas: Tahap-5 & 6 — Ubah Akun, Ikon Dilokalkan, Label Menu Diperbaiki

## Informasi Dasar
- Tanggal: 2026-09-11
- Jenis Tugas: build (backend + frontend) + penyelarasan dokumen legal/spesifikasi
- Waktu Mulai: 18:20 (perintah user) — laporan disusun 18:50
- Eksekutor: `be-dev` (sesi `ses_f70913524ffezKmxQV4LdzciV4`), `fe-dev` (sesi `ses_f7060031dffeFpTJlMt5NVXMTT` tahap-5;
  tahap-6 terbagi: sesi `ses_f70051dc0ffegXmj0p7mlMI2He` **GAGAL di tengah jalan karena error autentikasi model**,
  dilanjutkan sesi `ses_f6fd547b4ffee4lli1lcr0VIEO`), `fullstack-dev` (sesi `ses_f6fbd4142ffe8jkbqRCG6Qh0A3`),
  `tech-architect` (sesi `ses_f6fadd87cffet4sblA2PVWdzrL`), `system-analyst` (sesi `ses_f6fa4c8cbffeWyxQeWTkUvYS6u`)
- Pencatat: ProjectManager (tabrakan aturan `task-report.md` vs `agent-boundaries.md` masih menunggu putusan user —
  sub-agent tidak punya akar tulis untuk laporannya sendiri)

## Permintaan Pengguna
Satu pesan, tiga hal: (1) "localin aja semua aset font atau icon"; (2) "kenapa teks menunya 'Alternative/secondary
accounts' itu kan cuma contoh. ganti jadi yang lebih representatif dong"; (3) "kok gak ada tombol edit ya di daftar
secondary account? cuma ada tombol delete doang nih".
Pesan lanjutan: "lanjut dong tadi provider AI-nya error" → spawn tahap-6 yang gagal diulang.

## Rencana Pekerjaan
1. be-dev perluas `PUT /api/accounts/{id}` (tanpa itu tombol edit mustahil — API hanya menerima `priority`).
2. fe-dev tahap-5: tombol "Ubah" per kartu akun + `#accModal` dua mode sesuai kontrak baru.
3. fe-dev tahap-6: vendor Font Awesome lokal + hapus CDN + guard tes anti-CDN + label menu baru.
4. fullstack-dev: `THIRD_PARTY_NOTICES.md` §2 (berkas root, di luar akar agen lain).
5. tech-architect + system-analyst: hapus klaim "ikon via CDN" di spesifikasi (`TSD`, `FSD`) supaya dokumen tidak menipu sesi berikutnya.
6. Gate PM mandiri di tiap lapisan + commit terpisah per berkas/fitur + register.

## Realisasi Pekerjaan
### (3) Backend — commit `eea7504`
- `src/backend/accounts_router.py:7` (docstring modul), `:67-89` (`AccountUpdate` diperluas), `:263-321` (`update_account` ditulis ulang).
- Parsial sungguhan: `req.dict(exclude_unset=True)` → "absen" ≠ "dikirim kosong", jadi `label=""`/`api_key=""` bisa ditulis sadar
  (perhatikan: ini **membalik** pola lama `if req.priority is not None`, dan `null` eksplisit = no-op karena kolom NOT NULL).
- `auth_type` + `last_used_at` tetap tidak bisa ditulis (diabaikan senyap, DTO mengembalikan nilai asli).
- SATU penolakan: `api_key` (termasuk `""`) ke akun oauth → 400 `oauth_account_key_readonly` (`:291-298`), dievaluasi SEBELUM menulis.
- Log hanya NAMA field, tidak pernah nilai kunci/token — ada tes yang membaca tabel `LogEntry` untuk membuktinya.
- `GET /api/accounts` + `_account_to_dto` tidak berubah → kontrak tahap-1 tetap sah, kecuali satu baris lama yang kini usang
  (`1351_...md:81` "HANYA menerima priority") → PM catat supersede di Memory Bank.
- **Gate PM sendiri:** `python3 -m pytest tests/backend -q` = **537 passed, 1 skipped, 0 failed** (baseline 526 + 11 tes baru).

### (2) Frontend tahap-5 — ikut commit `19df593`
- `app.js:1313-1319` tombol `.acc-edit` (ikon `fa-pen`, `aria-label`+`title`) dipasang SEBELUM `.acc-del`, satu tingkat;
  `:1356-1359` cabang handler di listener delegasi `#accList` yang sudah ada (nol listener per kartu).
- `:1444-1571` `#accModal` dua mode: `accModalMode`/`accEditingId`, seed eksplisit mode tambah, `openAccountEditModal(id)`
  membaca `accountRows` (tanpa fetch ulang), `setAccountModalChrome` satu tempat untuk semua beda mode,
  `closeAccountModal` mengembalikan ke mode tambah (nol nilai nyangkut), `syncAccountKeyRow` memperluas: baris kunci
  TERSEMBUNYI + catatan oauth (menekan 400 dari sisi UI), `submitAccountForm` merutekan.
- `:1577-1615` `saveAccountEdit` → `PUT /api/accounts/{id}` berisi HANYA `{label, api_key, enabled}` (akun kunci) atau
  `{label, enabled}` (akun oauth) — ditegaskan oleh tes dengan `toEqual` + `not.toHaveProperty` (`auth_type`, `priority`,
  `last_used_at`, `provider_id` tidak pernah ikut).
- `index.html:991-1044` (`#accOauthNote`, `#accEnabledRow`, id untuk baris prioritas), `styles.css:1204` (ukuran tombol aksi kartu),
  i18n +7 kunci × 7 kamus.
- Tes: `accounts.test.js` 18 → 27; `provider_detail.test.js` 40 → 47; **nol tes dihapus**.

### (1)+(2) Frontend tahap-6 — ikut commit `19df593` (label) + vendor
- **Insidien:** spawn pertama (`ses_f70051dc...`) mati di tengah ("upstream authentication failed"). PM mengulang dengan
  handover yang sama; sesi kedua melaporkan working tree sudah berisi sebagian pekerjaan → **sesi kedua mengaudit ulang
  semuanya dari nol** (hash, grep, jalankan tes) dan mengoreksi 1 komentar guard yang salah fakta (klaim "0 aturan content
  menyentuh kodepoint v4compat" → sebenarnya 63/36; alasan yang benar = family legacy tidak pernah dipakai selector).
- Vendor: `src/frontend/static/vendor/font-awesome/` 5 berkas **409.388 B**, didapat dari branch `docs/wiki` lewat
  `git restore --source=docs/wiki` (TANPA men-staging); PM mencocokkan **hash blob 5/5 identik** — bukan unduhan baru.
- `index.html:43` kini `vendor/font-awesome/css/all.min.css?v=20260919`; grep `cdnjs|cdn.jsdelivr|unpkg|@import url("http`
  di `src/frontend/static/**` = **0**.
- Guard BARU `src/frontend/tests/vendor_assets.test.js` (7 tes, scan struktural `static/**` — bukan daftar hitam host):
  menuntut nol rujukan aset eksternal + setiap `woff2` yang dirujuk `@font-face` ada di disk. Ketajamannya dibuktikan dengan
  sabotase sementara (sisip CDN → 3/7 gagal; singkirkan `fa-solid-900.woff2` → 2/7 gagal; dipulihkan + hash dicocokkan ulang).
- Label menu ⋮: kunci TETAP `providers.accounts_menu`, nilai diubah → ID "Kelola akun", EN "Manage accounts"
  (+ ru/nl/ja/zh/zh-tw setingkat). Perilaku item tidak berubah (`accounts|edit|delete`, `fa-users`, `openDetail`).
  **Catatan untuk user:** teks yang dilihat user bukan contoh/komentar, melainkan nilai kamus **EN** — bahasa aplikasi sedang
  di-set Inggris; nilai ID-nya "Akun alternatif/sekunder". Tetap diganti karena memang kaku di bahasa mana pun.
- Cache-buster serentak `20260919` (V/styles/i18n/app — dijaga `tests/i18n.test.js:307-316`).

### (4) Legal — commit `15862bf`
`THIRD_PARTY_NOTICES.md` §2 ditulis ulang (118+/18−): judul jadi "vendored in this repository", tabel berkas + lapisan lisensi,
kutipan `LICENSE.txt` per baris (CC BY 4.0 :13-17, OFL 1.1 :21-31, MIT :121-126, atribusi :147-156, syarat redistribusi :80-85),
atribusi ditulis nyata (bukan "requests attribution"), fallback yang sengaja tidak di-vendor + alasannya, dan **provenance
dicatat jujur**: "6.5.1" hanya dari string header CSS — belum diverifikasi terhadap artefak rilis upstream (utang, sejajar `WL.4`).

### (5) Spesifikasi yang menipu — commit `b256064` + `bb759e4`
- `documents/architecture/TSD.md`: bullet ikon (§3.4) dikoreksi + **ADR-015 "Aset front-end: vendor lokal, tanpa CDN"** (Accepted,
  mengikat aset baru; alternatif CDN+fallback dan unduh-saat-build ditolak; penegakan = tes, bukan niat reviewer). Sensus arsitektur:
  1 klaim usang (yang ini); `anthropic-inbound-endpoint.md` bersih.
- `documents/analysis/FSD.md:321` dikoreksi (rujuk ADR-015, tanpa duplikasi detail) + `:454` mencatat kebutuhan "dapat dipakai
  offline" kini TERBUKTI terpenuhi; versi spec 1.0 → 1.1. Sensus analisis: hanya 1 klaim usang; `rules-consolidation.md` sudah benar.

### (6) Gate PM mandiri (bukan klaim sub-agent)
- backend: `python3 -m pytest tests/backend -q` → 537 passed, 1 skipped, 0 failed.
- frontend: `node node_modules/.bin/vitest run` → **25 berkas / 609 tes LOLOS** (acuan sesi 24/602 → +7 dari guard vendor).
- paritas i18n 7/7 kode → 436 kunci, hilang 0, thừa 0, kosong 0.
- hash vendor 5/5 cocok `docs/wiki`; `du -sh` = 423K; grep CDN = 0; `git diff --check` bersih; lingkup tiap agen cocok (nol lintas akar).

## Status Akhir
**BERHASIL di tingkat tes** untuk tiga permintaan user + dokumen yang dulu menipu sudah diselaraskan.
**BELUM diverifikasi (jujur):**
1. **Belum di-exercise nyata** (G3): belum ada peramban di lingkungan ini. Yang bisa dikerjakan user tanpa restart proses:
   muat ulang halaman (aset dibaca ulang dari berkas). Uji mata: tombol Ubah di tiap kartu, modal dua mode, ikon tetap muncul
   saat pesawat-mode.
2. Provenance Font Awesome: 5/5 blob = `docs/wiki`, TAPI `docs/wiki` sendiri tidak menyimpan catatan rilis/checksum unduhan
   → asal-usul versi 6.5.1 belum terverifikasi ke hulu. Usulan: pin + catat sumber (perluas `WL.4`).
3. `e2e/b5_features.mjs` belum dijalankan (nol browser); hanya `node --check`.
4. Terjemahan non-EN (termasuk label baru) belum ditinjau penutur.
5. Item tertunda hasil sensus: `documents/plan/wiki-backlog.md` WL.5 (selesai, harus dicoret — PM yang catat) dan
   `FSD.md:7,19` merujuk path `docs/business/BRD.md` yang tidak ada (seharusnya `documents/business/BRD.md`) — belum ditugaskan.
6. Kontrak tahap-1 lama (laporan `1351`: "`PUT /api/accounts/{id}` HANYA menerima priority") sudah digantikan laporan ini;
   berkas laporan lama TIDAK diedit (arsip titik-waktu) — supersede dicatat di Memory Bank.
7. Repo: 19 commit ahead dari `origin/refactor/ui` (BELUM push); PR #17 masih terbuka.

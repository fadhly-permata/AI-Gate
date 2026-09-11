# Laporan Tugas: Opsi A — Halaman Rinci Penyedia (tahap-3 UI multi-akun)

## Informasi Dasar
- Tanggal: 2026-09-11
- Jenis Tugas: build (frontend) + pembongkaran hasil tahap-2
- Waktu Mulai: 07:05 (perintah user) — selesai dicatat 11:00
- Eksekutor: sub-agent `fe-dev` (Task tool, sesi `ses_f721dd91bffeZOiRtn33N0XqnF`), satu putaran
- Pencatat: ProjectManager (aturan `task-report.md` vs `agent-boundaries.md` masih bertabrakan —
  akar tulis `fe-dev` hanya `src/frontend/**`, jadi laporan ini disusun PM dari receipt)

## Permintaan Pengguna
Setelah menilai hasil tahap-2 berantakan ("desain multi akun berantakan amat") dan menerima tiga
arah perbaikan dari PM, user memilih: "kita coba dulu opsi a", lalu menegaskan kembali
"coba dulu yang a kita kerjain" setelah PM menayangkan lembar desain (aturan D6: desain di-ACC
terlebih dahulu, baru kode disentuh). Opsi A = halaman rinci sendiri per penyedia.

## Rencana Pekerjaan
1. PM menerbitkan lembar desain + menunggu ACC (sudah berjalan di blok sebelumnya).
2. Handover ke `fe-dev`: acuan = lembar desain + kontrak tahap-1 + peta `file:line` hasil `d1ff215`
   yang harus dibongkar + batas tulis (termasuk larangan `usage.js`, `combos.js`, `src/backend/**`)
   + definisi selesai.
3. Realisasi: view baru `provider-detail`, kartu akun, prioritas ▲▼, strategi di kartu sendiri,
   discovery dengan status teks, pembongkaran tab + pencabutan kunci i18n mati, tes, e2e.
4. Gate PM mandiri (bukan klaim sub-agent).
5. Commit terpisah (kode vs dokumen) + pencatatan Memory Bank/register.

## Realisasi Pekerjaan
- 07:05 langkah 1–2 selesai; `fe-dev` spawned (agen + skill reuse, nol generasi).
- 10:5x langkah 3 selesai, satu putaran, TANPA blocker: `usage.js` ternyata tidak perlu disentuh
  (Kartu D memakai id lama `provUsageMsg`/`provUsageTotals`/`provUsageModelBody`, hanya pindah rumah).
- Realisasi (17 berkas, semua `src/frontend/**`; +1527/−1149):
  - `static/index.html` (+256/−183): `#provDetail` lama DIHAPUS (:311); view BARU
    `section.view.provider-detail[data-view="provider-detail"]` (:316-465) — kepala (`#provDetailBackBtn`
    :332, judul + badge, Ubah/Hapus :341-347), Kartu A profil baca-saja `<dl>` (:352-389 + status
    `#pdModelStatus` :388), Kartu B strategi (`#pdStrategy` :400-404, `#pdStickyRow`/`#pdStickyLimit`
    :407-410, `#pdStrategySaveBtn` :412, `#pdStrategyMsg` :415), Kartu C akun (`#pdAccAddBtn`,
    `#provConnectOAuthBtn`, `#pdAccReloadBtn`, `#accList` DIV :443 — tabel hilang), Kartu D pemakaian
    (:446-465); `#provModal` jadi profil-only (:901-976); modal BARU `#accModal` (:978-1018);
    cache-buster `20260915→20260916` (styles/i18n/app + `I18N_VER`).
  - `static/app.js` (+497/−314): `navViewFor` + sorot nav Penyedia (:78-88, 162-174) TANPA entri nav baru;
    `openDetail`/`loadProviderDetail`/`backToProviders` (:1032-1136); `saveProvider` TIDAK lagi mengirim
    `fallback_strategy`/`sticky_round_robin_limit` (:985-1030); `saveStrategy` mengirim HANYA 2 field
    routing + clamp ≥1 + pesan 400 inline di kartunya (:1138-1186); discovery senyap + baris status +
    penjaga balapan `discoverSeq`, gagal = teks + `console.warn` (R12) (:1190-1237); akun dirender KARTU
    dengan posisi 1..n, kunci polos ber-`title`, ▲▼ `aria-disabled` beralasan (:1259-1364);
    `moveAccount` = tukar → normalisasi `0..n-1` → PUT hanya yang berubah → SELALU baca ulang dari server
    (:1366-1412); modal akun `openAccountModal`/`submitAccountForm` (:1438-1528); wiring dipadukan
    `wireProviderUi()` (:1607-1668); ekspor `window.aigate` dipangkas ke yang benar-benar dipakai.
  - `static/styles.css` (+142/−32): `.modal-tabs`/`.modal-tab`/`.prov-tabpanel`/`.acc-priority`/
    `.acc-never`/`.providers-detail` DIHAPUS (0 rujukan tersisa); blok halaman rinci :1083-1156; kartu
    akun :1158-1238 (area sentuh ▲▼ 34px → 44px di ponsel/media sempit); **tambalan bug lama** :511-515
    `.form-row[hidden] { display:none }` — `display:flex` penulis mengalahkan aturan `[hidden]` milik
    peramban, jadi baris "tersembunyi" sebelumnya masih terlihat.
  - `static/i18n/{en,id,ru,nl,ja,zh,zh-tw}.js`: 10 kunci mati tahap-2 DICABUT (termasuk `accounts.none`
    yang jadi mati karena kosong-state baru — di luar daftar 9 PM, disetujui PM), 27 kunci baru
    (`providers.models_hint|models_failed`, `provider_detail.*`), total 411 → **428 kunci per kamus**.
  - `tests/provider_detail.test.js` BARU (40 tes, 876 baris) + penyesuaian `providers.test.js` (32→27),
    `accounts.test.js` (17→18), `views.test.js` (25→27), `row-actions.test.js` (4→5), `usage.test.js`
    (1 tes retarget). Tes tab tahap-2 DIPINDAH menjadi tes perilaku nyata (tabel pemetaan lengkap di
    receipt §6) — nol penghapusan cakupan tanpa pengganti.
  - `e2e/b5_features.mjs` (+71/−43): alur B5.1 ke UI baru (nama → halaman rinci → kartu → modal akun →
    Kembali). `node --check` lolos; TIDAK dijalankan (nol browser).
- 11:00 langkah 4 GATE PM MANDIRI: `node node_modules/.bin/vitest run` = **24 berkas / 586 tes LOLOS**
  (sebelum 23/547); `i18n-parity-check.mjs` untuk **ketujuh** kode = 428 kunci, hilang 0, thừa 0, kosong 0;
  `git status --short` = 17 berkas semuanya `src/frontend/**` (nol `src/backend/**`, nol `combos.js`,
  nol `usage.js`); grep sisa tab (`provTabList|provTabAccounts|provPanelAccounts|modal-tab|prov-tabpanel|
  wireProvTabs`) di `static/**` = **0**; grep 4 kunci dicabut di 7 kamus = **0**; warna hex baru di
  `styles.css` = **0**; `git diff --check` bersih; `node --check` `app.js` + `b5_features.mjs` OK.
- 11:02 langkah 5: commit kode `6ede872` (TIDAK push) + dokumen PM terpisah.

## Keputusan `fe-dev` di luar acuan (semua DITERIMA PM)
1. 27 kunci baru (bukan 12–14) — tiap permukaan butuh label sendiri; semuanya terpacu pada rujukan nyata.
2. `accounts.none` ikut dicabut (korban kosong-state baru) — konsisten dengan "nol kunci mati".
3. Prioritas akun BARU = jumlah akun saat ini (append di akhir), bukan 0. **Ini koreksi defect**:
   dengan default 0, akun baru akan melompati seluruh antrean (angka kecil = lebih dulu).
4. Pertukaran pada daftar yang semuanya `0` dengan n lebih dari 3 mengirim n−1 PUT (bukan 2) karena urutan server
   ambigu saat nilai sama; daftar rapi `0..n-1` selalu 2 PUT. PUT dijalankan BERURUTAN, bukan serentak,
   supaya urutan di server pasti.
5. `stopOAuthPoll()` saat berpindah penyedia — poll OAuth tidak boleh menulis kartu penyedia lain.

## Status Akhir
**BERHASIL di tingkat tes.** Layout Opsi A terpasang penuh, tab tahap-2 dibongkar bersih, kontrak
tahap-1 tidak dilanggar, nol sentuh backend/kombo/usage. BELUM diverifikasi (jujur):
1. **Belum dilihat di aplikasi nyata** (aturan G3): tidak ada browser di Termux; user harus memuat ulang
   server (aturan J6 — keputusan restart ada di user) lalu memeriksa mata, terutama kartu akun + tombol
   ▲▼ di layar sempit dan mode gelap.
2. Playwright/e2e belum dijalankan — hanya sintaks + pencocokan selektor ke markup.
3. Terjemahan 6 bahasa non-Inggris belum ditinjau penutur asli (lolos parity guard saja).
4. Batasan diterima dari lembar desain: halaman rinci tanpa rute URL → tidak bisa di-bookmark dan tombol
   back peramban tidak berlaku.
5. Repo lokal `refactor/ui` ahead 8 — belum di-push; PR #17 masih terbuka.

# Lembar Desain — Opsi A: Halaman Rinci Penyedia (UI multi-akun, rework tahap-3)

- Tanggal: 2026-09-11 · Penulis: ProjectManager (rule **D6**: lembar desain + ACC user SEBELUM spawn fe-dev)
- Status: **DRAF — MENUNGGU ACC USER.** Belum ada kode yang disentuh untuk desain ini.
- Acuan kontrak data: `.opencode/reports/20260910/qa/1351_backend-gate-multiakun-9router.md` §KONTRAK (tidak berubah).
- Hasil tahap-2 yang diganti: commit `d1ff215` (modal ber-tab). Backend: nol sentuh. Combo: nol sentuh.

## 1. Tujuan & masalah yang diatasi

Masalah tahap-2 (dibuktikan audit PM, `documents/pm/status.md` blok 20260911-0645): satu penyedia punya dua
permukaan (tab modal vs kartu detail), modal induk menampung CRUD sub-entitas (form 5 baris + tabel 6 kolom),
prioritas = angka telanjang, tab mati saat tambah, discovery terlalu diam, kolom Models tanpa panel.

Tujuan: **satu permukaan per pekerjaan.** Daftar = pilih. Halaman rinci = urus semua hal tentang SATU penyedia.
Modal = isian singkat saja.

## 2. Denah blok — layar 1: Daftar Penyedia (tetap, cuma dirapikan)

```
[ banner tujuan halaman ]
[ kartu: "Penyedia"                         ( + Tambah Penyedia ) ]
[ tabel: Nama(klik->halaman rinci) | Tipe | URL | Aktif | Model(badge+tooltip) | ⋮(Ubah|Hapus) ]
```

- Kolom Model TETAP ADA, tapi jadi badge kecil + `title`/`aria` menjelaskan "jumlah model yang dikenali dari
  pencarian otomatis" (menambal titik lemah no.6).
- Menu kebab tetap `edit` + `delete` (tahap-2 sudah begitu).

## 3. Denah blok — layar 2: Halaman Rinci Penyedia (BARU, `data-view="provider-detail"`)

```
[ ← Kembali ke Penyedia ]        (tombol, bukan link URL — SPA tanpa route)
[ judul: <nama penyedia>  (badge Aktif/Nonaktif)        ( Ubah ) ( Hapus ) ]

+--------------------------------------------------------------+
| KARTU A — Profil singkat                                     |
|  Tipe · Base URL · Model bawaan · Kunci API · Header kustom  |
|  (baca-saja; ubah lewat tombol "Ubah" di kepala halaman)     |
+--------------------------------------------------------------+
| KARTU B — Pergiliran akun                                    |
|  Strategi: ( isi-sampai-habis  ▾ / gilir-bergantian )        |
|  [ saat gilir: ] Pemakaian per akun sebelum pindah: [ 3 ]    |
|  ( Simpan strategi )   pesan: "tersimpan" / 400invalid       |
+--------------------------------------------------------------+
| KARTU C — Akun                        ( + Tambah akun )      |
|  ( OAuth )      ( muat ulang )                               |
|  ┌ baris-kartu per akun ────────────────────────────────┐    |
|  │ #1  label            jenis  kunci(teks, potong)      │    |
|  │     [▲][▼]  prioritas · terakhir dipakai: 2 mnt lalu │    |
|  │     ( Hapus )                                         │    |
|  └──────────────────────────────────────────────────────┘    |
|  kosong? -> "Belum ada akun. Penyedia memakai kunci API-nya  |
|            sendiri sampai ada akun."                         |
+--------------------------------------------------------------+
| KARTU D — Pemakaian hari ini (B5.5, pindah dari kartu lama)  |
+--------------------------------------------------------------+
```

- **Tabel 6 kolom DIHILANGKAN.** Tiap akun = satu kartu baris vertikal → aman di layar sempit; kunci API panjang
  dipotong CSS (`text-overflow: ellipsis`, tetap teks polos sesuai J3/ADR-007 — tidak di-mask).
- Urutan kartu = urutan prioritas mesin (`GET /api/accounts` sudah terurut `priority` asc, id asc → tinggal render).
- Kartu-kartu disusun **satu kolom vertikal** (bukan grid 2 kolom) supaya di HP tidak patah; di layar lebar
  dibatasi `max-width` yang sama dengan `.view` lain.

## 4. Alur (flow)

1. Daftar → klik nama (`#provTableBody .prov-name-btn`) → `showView("provider-detail")` + `setActiveNav(nav "providers")`
   (menu samping tetap menyorot Penyedia; TIDAK ada entri nav/bottom-nav baru → `views.test.js` paritas nav tidak diapa-apakan).
2. Halaman rinci memuat: `GET /api/providers/{id}` (profil+strategi) · `GET /api/accounts?provider_id=` ·
   `usage.loadProviderUsage(id)` · `POST /api/providers/{id}/discover` **di belakang layar** (isi opsi combobox modal
   + badge jumlah model; lihat no.7).
3. "← Kembali" → `showView("providers")` + `loadProviders()` (angka model/badge ikut segar).
4. "Ubah" → modal profil TANPA tab (isian singkat + hapus 2 kontrol strategi dari modal — strategi hidup di Kartu B).
   "Simpan" di modal = `PUT /api/providers/{id}` (profil saja; TIDAK mengirim `fallback_strategy`, biar tidak menimpa Kartu B).
5. "Tambah akun" → **modal kecil khusus akun** (label, jenis akses, kunci, prioritas) → `POST /api/accounts` → kartu baru muncul.
   Tidak ada lagi "tab mati harus simpan dulu": provider-nya sudah punya id di halaman ini.
6. "Hapus" penyedia → konfirmasi → balik otomatis ke daftar.

## 5. Prioritas: angka → tombol naik/turun (menambal no.3)

- Tiap kartu akun menampilkan **posisi 1..n** (bukan angka mentah DB) + tombol ▲ ▼.
- ▲/▼ = **normalisasi lalu tukar**: posisi i dan i+1 ditukar → daftar dihitung ulang jadi `priority = 0,1,2,…`
  → `PUT /api/accounts/{id}` `{priority}` **hanya untuk akun yang nilainya berubah** (kasus default semua `0`
  → tukar pertama mengirim 2 PUT, bukan n).
- Batas: ▲ di posisi 1 dan ▼ di posisi terakhir = nonaktif (`aria-disabled`), tidak error bisu.
- Gagal simpan → pesan inline di Kartu C + muat ulang urutan dari server (tidak meninggalkan tampilan bohong).
- Tidak ada geser-seret (drag) — ramah HP tapi rawan tabrakan gulir di Termux; tombol lebih pasti.

## 6. Yang DIHAPUS dari hasil tahap-2

- Tab modal provider: `#provTabList`, `#provPanelAccounts`, `#provTabHint`, logika `wireProvTabs/selectProvTab/setAccountsTabEnabled`.
- Blok akun di dalam `#provForm` (pindah ke halaman rinci + modal akun).
- Tes tab (diganti tes halaman rinci — jumlah tes boleh turun-naik asalkan **nol penurunan cakupan** atas perilaku nyata).
- Kunci i18n yang jadi mati: `providers.tab_provider`, `providers.tab_accounts`, `providers.tabs_label`,
  `providers.strategy`, `providers.sticky_limit`, `accounts.priority`, `accounts.last_used`, `accounts.never_used`,
  `accounts.save_first` → **DIPINDAHKAN namanya** ke kunci halaman rinci, bukan dibiarkan menggantung
  (kunci tahap-2 yang belum sempat dipakai user, jadi aman dicabut; paritas 7 kamus wajib tetap lolos).

## 7. Discovery: diam tapi tidak bisu (menambal no.5)

- Combobox model di modal profil: baris status kecil di bawahnya — "sedang memuat model…" → "N model dikenali" →
  gagal = "daftar model gagal diambil, boleh diketik manual" (teks i18n, bukan tabel).
- Badge kolom Model di daftar = jumlah model; tooltip menjelaskan asalnya (otomatis).
- Kegagalan discovery TETAP tidak mem-block form; jalur `console.warn` (R12) dipertahankan.

## 8. Kunci i18n baru (perkiraan 12–14, wajib serentak 7 kamus: en id ru nl ja zh zh-tw)

`provider_detail.back`, `provider_detail.title`, `provider_detail.profile`, `provider_detail.strategy_card`,
`provider_detail.strategy_help`, `provider_detail.save_strategy`, `provider_detail.strategy_saved`,
`provider_detail.accounts_card`, `provider_detail.add_account`, `provider_detail.account_modal_title`,
`provider_detail.no_accounts`, `provider_detail.position`, `provider_detail.move_up`, `provider_detail.move_down`,
`providers.models_hint` (tooltip badge). Nama final = keputusan fe-dev asal konsisten + parity guard lolos.

## 9. Batas tulis & cakupan tes

- Tulis: `src/frontend/static/{index.html,app.js,styles.css}`, `src/frontend/static/i18n/*.js` (7),
  `src/frontend/tests/**`, `src/frontend/e2e/b5_features.mjs`. DILARANG: `src/backend/**`, `combos.js`, `usage.js`
  (Kartu D memanggil `window.aigate.usage.loadProviderUsage` yang SUDAH ADA — `usage.js:365`; kalau ternyata butuh
  perubahan di `usage.js`, fe-dev STOP + lapor PM, jangan sunting sendiri).
- Tes wajib baru/diubah: view `provider-detail` ada + tidak punya entri nav (paritas nav utuh), kepala halaman
  (Ubah/Hapus/Kembali), Kartu B mengirim strategi saja + pesan 400, Kartu C merender kartu akun (bukan tabel) +
  ▲/▼ menghasilkan PUT bernomor benar (kasus default semua-0 → 2 PUT), modal akun mengirim `priority`,
  kosong → teks `no_accounts`, discovery memunculkan status teks (bukan tabel), Kembali memanggil `loadProviders`,
  tes tab lama dihapus, `views.test.js` + `row-actions.test.js` disesuaikan.
- Gate PM: `node node_modules/.bin/vitest run` hijau penuh (acuan angka saat ini 23 berkas / 547 tes), paritas i18n
  7 kamus (`i18n-parity-check.mjs`), `git diff --check` bersih, nol di luar `src/frontend/**`, 0 warna hex baru.

## 10. Risiko & batasan yang diterima (jujur)

1. SPA ini tanpa route URL → halaman rinci tidak bisa di-bookmark / tidak ada tombol back browser. Diterima
   (butuh hash-router = perubahan sentral; boleh jadi tugas tersendiri nanti).
2. Pindah prioritas = beberapa PUT sekaligus → potensi sebagian gagal; ditangani dengan muat ulang dari server + pesan.
3. Termux: tanpa browser → **belum terbukti mata** sampai user muat ulang server + lihat HP (G3/J6).
4. Kerja ini MENGHAPUS tab yang baru saja dibuat di `d1ff215` → ada riwuh riwayat; alternatif: rework di atasnya
   (dipilih, karena strukturnya yang salah, bukan detailnya).

## 11. Definisi selesai (sebelah sini)

Semua bagian 3–7 terpasang; bagian 6 bersih (nol markup/kunci mati); gate bagian 9 hijau; laporan + register
`documents/dev/CODE_CHANGES.md` diisi; commit terpisah (kode vs dokumen PM); TIDAK push tanpa perintah.

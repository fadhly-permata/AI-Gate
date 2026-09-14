# Laporan Tugas: Banner Tujuan Halaman — Inventarisasi (Fase 0) dan Proposal (Fase 1)

## Informasi Dasar
- Tanggal: 2026-09-10
- Jenis Tugas: research (inventarisasi + proposal; TIDAK ada implementasi)
- Waktu Mulai: 03:24

## Permintaan Pengguna
"pada setiap halaman (kecuali home dan terminal) kasih banner penjelasan tujuan halaman tersebut dong. text nya bakal di kasih per halaman."

Batasan yang diikat: teks banner akan disediakan pengguna per halaman (belum diberikan);
halaman home dan terminal dikecualikan; dilarang mengarang teks final.

## Rencana Pekerjaan
1. Inventarisasi read-only frontend: daftar halaman, rute, komponen, titik sisip.
2. Identifikasi home dan terminal serta buktinya.
3. Periksa layout bersama yang ada dan dua opsi pemasangan banner + trade-off.
4. Periksa rumah i18n/konstanta untuk copy per halaman.
5. Susun proposal dan daftar isian teks untuk pengguna; hentikan sebelum kode.

## Realisasi Pekerjaan
- [03:24] langkah 1–4 selesai (baca tertarget: index.html, app.js, styles.css, i18n.js,
  i18n/en.js, tests/i18n.test.js; tanpa grep acak ke seluruh repo)
- [03:24] langkah 5 selesai — laporan ditulis, implementasi TIDAK dijalankan

## Temuan Arsitektur (semua terverifikasi file:line)

1. Frontend adalah SPA vanilla JS dengan SATU berkas HTML:
   `src/frontend/static/index.html` (1.242 baris). Bukti: pencarian berkas `*.html`
   di seluruh repo (tanpa node_modules/vendor) hanya mengembalikan berkas itu.
2. "Halaman" = elemen `<section class="view" data-view="...">` di dalam
   `<main class="workspace">` (index.html:162). Perpindahan view dilakukan
   `showView()` (src/frontend/static/app.js:144–152); visibilitas murni CSS:
   `.view { display: none; }` dan `.view.is-active { display: block; }`
   (src/frontend/static/styles.css:421–422).
3. TIDAK ada routing per URL: pencarian `location.hash`, `history.pushState`,
   `hashchange` pada `src/frontend/static/*.js` = 0 hasil. Seluruh halaman memakai
   URL yang sama (`/`). Kolom "Rute" pada tabel di bawah karena itu bernilai `/`
   untuk semua baris.
4. Total 10 view. Dua dikecualikan:
   - **home** = view `welcome` — section index.html:164, satu-satunya view berstatus
     `is-active` sejak awal, komentar default-nya index.html:163, `showView` jatuh
     kembali ke welcome bila target tidak ada (app.js:146), dan inisialisasi
     "Start on the welcome view" (app.js:1833). Tidak ada kandidat home lain.
   - **terminal** = view `terminal` — section index.html:676, item nav index.html:117.
     Catatan regel R30: "terminal" = fitur terminal aigate (multi-tab xterm + PTY WS),
     bukan terminal OS. View ini adalah flex column pas-ukuran penuh
     (komentar index.html:673–675; `.terminal-view` styles.css:1048) — elemen banner
     tidak boleh merusaknya.
5. `device.js` dan `selfheal.js` BUKAN halaman: device.js helper validasi token
   perangkat (device.js:1–5); selfheal.js kartu "Self-Heal" yang menempel di dalam
   view `cli` (index.html:764).
6. i18n: registri 7 bahasa di `src/frontend/static/i18n.js` (window.LANGS, baris
   30–38); kamus satu berkas per bahasa di `src/frontend/static/i18n/{en,id,ru,nl,
   ja,zh,zh-tw}.js`; urutan resolusi locale → English → kunci itu sendiri
   (i18n.js:57–62); **key-parity guard** memaksa semua berkas kamus memiliki set
   kunci yang sama (src/frontend/tests/i18n.test.js:81–88).
7. Belum ada kunci deskripsi halaman mana pun: pencarian `_desc|description` pada
   `src/frontend/static/i18n/en.js` = 0 hasil. Rumah alami untuk copy banner =
   kunci baru `page_desc.<view>` di ketujuh kamus.

## a) Tabel Halaman

| No | Halaman | data-view | Section (index.html) | Elemen judul (index.html) | Modul JS | Eksoalusi? |
|----|---------|-----------|----------------------|----------------------------|----------|------------|
| 1 | Home / Welcome | `welcome` | :164 | `h1.welcome-title` :166 | — (hanya app.js showView) | **YA — home** (bukti butir 4) |
| 2 | Settings | `settings` | :174 | `h2.settings-title` :176 | app.js `loadSettings` (app.js:1678) | tidak |
| 3 | Providers | `providers` | :274 | `h2.providers-title` :278 | app.js `loadProviders` (app.js:1679) | tidak |
| 4 | Combos | `combos` | :406 | `h2.providers-title` :409 | combos.js | tidak |
| 5 | Proxy Pools | `proxies` | :433 | `h2.providers-title` :436 | proxies.js | tidak |
| 6 | Endpoints | `endpoints` | :460 | `h2.providers-title` :463 | endpoints.js | tidak |
| 7 | Usage & Quota | `usage` | :488 | `h2.providers-title` :492 | usage.js | tidak |
| 8 | Analytics | `analytics` | :580 | `h2.providers-title` :584 | analytics.js | tidak |
| 9 | Terminal | `terminal` | :676 | (toolbar :681, tanpa judul) | terminal.js | **YA — terminal** (permintaan user; bukti butir 4) |
| 10 | CLI Tools (+Self-Heal) | `cli` | :756 | `h2.cli-title` :758 (kartu kedua Self-Heal :764–765) | clitools.js, selfheal.js | tidak |

Titik sisip banner (opsi rekomendasi): sebagai anak pertama tiap `<section>`, yaitu
tepat setelah baris section yang tercantum pada tabel (mis. Settings: sisip setelah
index.html:174). Rute semua halaman = `/` (SPA, butir 3).

## b) Bentuk Implementasi — Dua Opsi

**Opsi B — elemen banner per section + kunci i18n (DIREKOMENDASIKAN)**
- 8 blok markup seragam: `<div class="page-banner" ...>` anak pertama tiap section
  target; teks lewat `data-i18n="page_desc.<view>"`.
- Copy tinggal di ketujuh kamus i18n (8 kunci × 7 berkas = 56 entri); parity guard
  (i18n.test.js:81) otomatis memastikan tidak ada bahasa yang bolong.
- Satu kelas CSS baru (token warna mengikuti `--panel-border` dsb, seperti
  `.settings-msg`/card yang ada).
- Nol perubahan JavaScript: visibilitas mengikuti `.view.is-active`
  (styles.css:421–422) — banner ikut tampil/sembunyi bersama halamannya.
- Plus: banner = bagian konten halaman (scroll natural, kontrol posisi per halaman,
  aman untuk layout flex terminal). Minus: 8 titik sisip + entri kamus berlipat
  bahasa (mekanis, tetap satu sumber kebenaran per locale).

**Opsi A — satu elemen banner bersama + peta konfigurasi per view**
- Satu elemen di atas konten workspace, ditampilkan/diisi oleh hook terpusat
  `showView()` (app.js:144) dengan daftar pengecualian (welcome, terminal).
- Plus: satu titik pemasangan. Minus: menyentuh logika sentral app.js (risiko ke
  alur init app.js:1833 dan flex `.terminal-view` styles.css:1048), teks tetap harus
  ditambatkan ke i18n agar tidak menyalahi kebijakan "satu kunci = satu nilai per
  locale" (keputusan 2026-09-06), dan posisi banner di luar scroll tiap halaman
  memerlukan verifikasi browser nyata. Tidak lebih baik kecuali diminta banner
  yang selalu tampak saat scroll (tidak diminta).

## c) Penempatan dan Perilaku Visual (level tinggi)
- Banner duduk paling atas di dalam halaman, sebelum judul/kartu pertama, lebar
  penuh area konten.
- Gaya informatif tenang (ikon info + paragraf pendek), bukan alert merah; token
  warna mengikuti tema (light/dark sudah ada via `themeToggle`).
- Statis (tidak bisa ditutup) sampai user meminta lain.
- Ponsel (≤600px): tetap elemen pertama halaman, ikut scroll, tidak menutupi
  bottom-nav (bottom-nav punya stacking sendiri).
- View `welcome` dan `terminal`: tidak ada elemen banner sama sekali (bukan
  disembunyikan lewat CSS per-view — tidak dipasang).

## d) Daftar Isian Teks untuk Pengguna (delapan pertanyaan bernomor)
1. **Settings** — tujuan banner?
2. **Providers** — tujuan banner?
3. **Combos** — tujuan banner?
4. **Proxy Pools** — tujuan banner?
5. **Endpoints** — tujuan banner?
6. **Usage & Quota** — tujuan banner?
7. **Analytics** — tujuan banner?
8. **CLI Tools (termasuk bagian Self-Heal di halaman yang sama)** — tujuan banner?

Boleh dijawab satu pesan, format bebas bernomor 1–8.

## e) Ambiguitas dan Default yang Dipilih
1. **Bahasa teks**: user kemungkinan memberi satu teks (Indonesia). Karena fallback
   i18n adalah locale → **en** → key (i18n.js:57–62), teks hanya-di-id akan membuat
   user bahasa lain melihat raw key. **Default**: salin teks yang diberikan ke
   ketujuh kamus (parity guard lolos); terjemahan layak menyusul. Alternatif bila
   user mau: sediakan terjemahan per bahasa sekaligus.
2. **Satuan "halaman" untuk view multi-kartu** (`cli` memuat Self-Heal; `usage`
   memuat Quota + summary; `analytics` memuat dashboard + request log).
   **Default**: satu banner per view (di atas semua kartu), bukan per kartu.
3. **Judul lama**: banner menambah paragraf tujuan; judul `h2` yang ada tetap.
   **Default**: tidak menghapus/memindahkan judul lama.
4. **Home** ditafsirkan = view `welcome` (satu-satunya kandidat home; butir 4).
   **Sudah terkonfirmasi oleh kode, bukan asumsi.**

## Status Akhir
Sebagian (sesuai desain tugas) — Fase 0 inventarisasi dan Fase 1 proposal SELESAI.
Implementasi DITAHAN: menunggu (i) teks banner per halaman dari user dan (ii)
persetujuan opsi B. Belum ada sub-agent yang diturunkan; belum ada berkas
src/** yang diubah. Checkpoint git awal: branch `refactor/ui` @ `e8ce6ae`,
working tree bersih.

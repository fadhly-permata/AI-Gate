# Handover — WO.1: buat UI aigate jalan 100% tanpa internet

**Dari:** PM · **Untuk:** fe-dev · **Tanggal:** 2026-09-08
**Keputusan user:** "ya udah kita bikin bisa full offline aja deh" → aset pihak ketiga WAJIB lokal.

## Kenapa sekarang (fakta yang sudah PM verifikasi)
- Seluruh frontend **cuma punya 1 referensi eksternal**: baris 42 `src/frontend/static/index.html`
  → `https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css`.
- Link `https://github.com/fadhly-permata/AI-Gate` di sidebar itu **hyperlink biasa**, bukan aset →
  JANGAN disentuh.
- `xterm.js` sudah lokal (`src/frontend/static/vendor/xterm/`).
- Tidak ada pengunduhan aset saat runtime di backend; font teks UI memakai font bawaan sistem
  (Menlo/Consolas/Segoe UI/Roboto) → tidak perlu di-vendor.
- Konsekuensi sekarang: tanpa internet ikon UI hilang, dan tiap buka halaman ada request ke Cloudflare.
  Itu menabrak janji privasi di README/wiki.

## WRITE SCOPE
- `src/frontend/static/vendor/font-awesome/**` (baru)
- `src/frontend/static/index.html` — **HANYA** baris tautan CSS Font Awesome itu (1 baris).
- `THIRD_PARTY_NOTICES.md` — ganti bagian Font Awesome (alnya sekarang didistribusikan, lihat §LISENSI).
JANGAN sentuh file kode lain. JANGAN menjalankan git add/commit/push (PM yang commit).

## Yang harus dikerjakan
1. Unduh dari paket resmi Font Awesome Free **6.5.1** lewat jsDelivr npm (struktur foldernya sama
   dengan paket resminya):
   - `https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.1/css/all.min.css`
     → `src/frontend/static/vendor/font-awesome/css/all.min.css`
   - folder `webfonts/`: **cukup** `fa-solid-900.woff2`, `fa-regular-400.woff2`, `fa-brands-400.woff2`
     → `src/frontend/static/vendor/font-awesome/webfonts/`
     (total ±300 KB; `.ttf` dan `fa-v4compatibility` TIDAK usah diunduh)
2. Ganti `href` di `index.html:42` jadi `vendor/font-awesome/css/all.min.css` (relatif, sama pola
   dengan tautan `vendor/xterm/xterm.css` di baris 46).
3. **Verifikasi jalur font**: file CSS menunjuk `../webfonts/…`. Karena kamu menaruh CSS di `css/`
   dan font di `webfonts/` sebagai saudara, jalurnya harusnya sudah benar. Daftar SEMUA URL font yang
   direferensikan CSS (regex `url\(...`), lalu pastikan tiap berkas yang dibutuhkan **ada** — dan
   laporkan berkas mana yang hilang (mis. `.ttf` yang memang sengaja tidak diambil; jelaskan apakah
   ada fallback).
4. Salin juga berkas lisensi resmi ke `src/frontend/static/vendor/font-awesome/`:
   `LICENSE.txt` dan `css/LICENSE.md` dari paket yang sama (jangan menulis teks lisensi dari ingatan).
5. Perbarui `THIRD_PARTY_NOTICES.md` bagian Font Awesome: sekarang **didistribusikan**, bukan lewat
   CDN. Fakta yang benar ditulis: CSS = MIT (notisnya dari `LICENSE.txt` resmi), berkas font =
   SIL OFL 1.1 dengan Reserved Font Name "Font Awesome"; **CC BY 4.0 tidak ikut** karena tidak ada
   ikon SVG/JS yang diunduh. Simpan notisnya apa adanya.
6. Jangan menulis angka byte/jumlah file di berkas materi publik apa pun.

## Definition of done (yang akan PM periksa)
- [ ] `grep` di `src/frontend/**` tidak menemukan SATU PUN `https://` yang dipakai sebagai
      `src=`/`href=` **aset** (hyperlink repo/GitHub boleh tetap ada).
- [ ] `index.html` berubah tepat 1 baris (`git diff --numstat` membuktikan).
- [ ] Semua `url(...)` di CSS yang diperlukan tersedia secara lokal; yang tidak tersedia dilaporkan
      jujur, tidak ditutup-tutupi.
- [ ] Berkas lisensi resmi ikut ke-vendor dan `THIRD_PARTY_NOTICES.md` sesuai kenyataan.
- [ ] Tidak ada `git commit/push`.

Kembalikan struk: berkas yang dibuat/diubah, ukuran total, daftar URL font yang masih meleset, dan
cara tercepat buat buktiin "halaman ini ke-render bener tanpa internet".

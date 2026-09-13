# Handover — Settings: responsif + rapihin layout + device-sim → modal (Opsi A)

**Tanggal:** 2026-09-13 · **Owner:** fe-dev · **Mode:** sekuensial
**Scope (STRICT):** `src/frontend/**` saja. Terminal hanya dibaca buat bukti, tidak diubah.

---

## 0. Koreksi diagnosis (PENTING)
Diagnosis lama ("settings lemot / re-render 26 CSS rule + terminal reflow") = **FABRIKASI**:
user TIDAK pernah bilang "lemot". Kata user: *"halaman setting kok gak responsif ya, dan desain ui nya
juga terasa aneh"* + *"berantakan"*. Di UI-web id: **"gak responsif" = layout tidak adaptif ke ukuran
layar** (responsive-design), BUKAN performa/lag. **"aneh/berantakan" = layout berantakan / hierarki
visual jelek**. Root-cause sebenarnya = CSS layout, bukan CPU/jank. (Rule baru F5.)

---

## 1. Peta masalah ASLI (bukti `file:line`)

### A. "Gak responsif" — form settings tidak pernah stacking di layar sempit
- `styles.css:503-509` `.form-row { display:flex; justify-content:space-between; gap:16px }` — selalu
  label+input sejajar 2 kolom di SEMUA lebar.
- `@media (max-width:600px)` `styles.css:692-716` dan `body[data-device="phone"]` `styles.css:718-741`
  hanya melebarin `.settings-card` ke `max-width:100%` — **TIDAK pernah** ubah `.form-row` jadi
  label-di-atas-input. Jadi di HP 375px (nyata maupun simulasi) label+input tetap terhimpit berdampingan.
- Sudah ada helper `.form-row-stack { margin-bottom:8px }` di `styles.css:867-872` (label di atas) tapi
  **tidak dipakai** di settings.
- `styles.css:522-524` `.form-input { width:240px; max-width:60% }` → di HP label cuma kebagian 40%,
  makin sempit. Override ≥960 (`styles.css:684`) jadi 200px/100% tapi tetap side-by-side.

**Fix A:** di `@media (max-width:600px)` + `body[data-device="phone"]`, `.settings-card .form-row`
jadi `flex-direction:column; align-items:stretch` dan `.form-input { width:100%; max-width:100% }`
(reuse token `--radius`/`--panel-border`, jangan hardcode hex). Boleh pakai `.form-row-stack`.

### B. "Berantakan / aneh" — baris Backup & Restore tidak konsisten
- `index.html:259-264` baris Export: `<span class="form-label">` + `<a class="btn">` (link tombol) sbg
  kontrol — bukan input. `<a class="btn">` (inline-flex, padding 9px 18px, `styles.css:575-590`) jauh
  lebih tinggi/lebar dari `<select>` → baris ini gak sejajar dgn baris input di atasnya → terlihat
  berantakan / hierarki visual putus.
- `index.html:266-283` baris Import (Mode select + file input) ikut pakai `.form-row` tapi bentuknya
  beda dari baris Port/Theme di atasnya.

**Fix B:** samakan ritme. Opsi: (1) baris Export jadikan full-width button di bawah label (label di atas,
button block), atau (2) pakai `.form-row-stack` konsisten untuk semua baris settings + backup. Pakai
token existing; jangan ubah struktur `.btn` global (dipakai view lain).

### C. Kontrol device-sim dipindah keluar settings (Opsi A — fitur)
- Sekarang di `index.html:227-238` (`#setDevice` `<select>` + `#setDeviceNote`).
- Pindah ke baris kecil **DI ATAS link GitHub**:
  - desktop: `.sidebar-footer` (`index.html:162`, sebelum `<a>` repo).
  - mobile: `.bottom-nav` **di atas** item Repo (`index.html:1381`, sebelum `<a class="bn-item" href=github>`).
- Klik kontrol → buka **modal** reuse `.modal-overlay`+`.modal` (`index.html:917`):
  - Tambah `#deviceModal` dengan `role="dialog" aria-modal="true" aria-labelledby`.
  - **Wajib:** focus-trap (fokus ke elemen pertama, Tab sirkulasi, Shift+Tab balik) + ESC tutup + klik
    overlay luar tutup + restore fokus ke trigger. (Belum ada helper global; buat di app.js atau device.js.)
  - Modal isi preview **iframe same-origin ke app sendiri** di 3 ukuran: phone 375×667 / tablet 768×1024 /
    desktop 1280×800. Pilih satu mode → `applyDevice(mode)` (`app.js:63-72`) set `body[data-device]`.
- Hapus: block `#setDevice` (`index.html:227-238`) + listener `app.js:2244-2251` + sync `sel.value`
  di `applyDevice` (`app.js:66-67`) + `document.getElementById("setDevice")` di test
  (`src/frontend/tests/provider_detail.test.js:257-258`).

### D. TEST yang akan terdampak (fe-dev OWNER, sesuaikan)
- `src/frontend/tests/views.test.js:295` assert `.bottom-nav .bn-item` length === **10** (paritas nav↔bn).
  Kalau kontrol device di bottom-nav pakai class `.bn-item` → count jadi 11 → merah. **Solusi:** pakai
  elemen bukan `.bn-item` (mis. `<button class="bn-device">`) atau sesuaikan assertion + komentar paritas.
- `src/frontend/tests/provider_detail.test.js:253-258` pakai `#setDevice` → pindah ke trigger/kontrol baru
  atau hapus baris yang memanipulasi `#setDevice`.
- `src/frontend/tests/views.test.js:278-295` (repo di bottom-nav) → pastikan repo tetap ada & kontrol
  device di ATASnya.

---

## 2. Definition of Done (G3 + gate)
1. Fitur di-**exercise di browser NYATA** (Chromium 149 ada di Termux — lihat status 0310):
   - Settings di lebar 360 / 768 / 1280 → form-row stacking benar, nol overflow, hierarki rapi.
   - Kontrol device di sidebar (desktop) & bottom-nav (mobile) terlihat; klik → modal; focus-trap + ESC
     jalan; iframe preview 3 ukuran benar; pilih mode → layout berubah.
   - **Before/after** tiap ruang dicatat (G3) — tulis di receipt.
2. `vitest` hijau (test yang diubah di-repair, bukan dihapus buta). `git diff --check` bersih.
3. Hanya `src/frontend/**` yang disentuh. Nol hex baru (pakai token `--*`).
4. Cache-buster `?v=` di-bump di `index.html` untuk `styles.css`/`app.js`/`device.js` (pelajaran G3 lalu).
5. Receipt: file berubah, keputusan (elemen kontrol bottom-nav), bukti before/after, test hijau.

## 3. Larangan
- JANGAN sentuh luar scope settings layout + device-modal. JANGAN ubah backend/terminal.
- JANGAN bilang "lemot"/performa — ini bukan isu performa.

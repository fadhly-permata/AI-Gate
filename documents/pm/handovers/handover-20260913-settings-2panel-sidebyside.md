# Handover — Settings: dua panel sejajar (kiri-kanan) di layar besar, numpuk di layar kecil

**Tanggal:** 2026-09-13 · **Owner:** fe-dev · **Mode:** sekuensial
**Scope (STRICT):** `src/frontend/static/styles.css` + cache-buster di `src/frontend/static/index.html`.
Tidak ada JS/HTML-structure yang diubah (hanya 1 baris `?v=` di index.html). Terminal hanya dibaca buat bukti.

---

## 0. Koreksi makna (F5)
"Gak responsif" = **layout tidak adaptif terhadap ukuran layar** (responsive-design), BUKAN performa/lemot
(aturan F5 sudah permanen). Jangan diagnosis performa. Jangan karang akar performa.

---

## 1. Peta masalah (bukti `file:line`)

### "2 panel" yang dimaksud user = dua `.card.settings-card` di view Settings
- **Panel 1 (form Settings utama):** `index.html:201` `<div class="card settings-card">` → berisi
  `.settings-form` (`index.html:203-244`): Port, Developer Mode, Theme, Language, Save.
- **Panel 2 (Backup & Restore):** `index.html:250` `<div class="card settings-card backup-card">`
  (`index.html:250-284`): Mode, Choose file, Export/Import button bar.
- Keduanya anak langsung `<section class="view" data-view="settings">` (`index.html:195`), tepat setelah
  `.page-banner` (`index.html:196-199`). Tidak ada panel ketiga di view ini.

### Layout SEKARANG (ini inti "gak responsif" di layar besar)
- `.view.is-active { display: block; }` (`styles.css:422`) → section adalah block; anak-anak mengalir
  **vertikal**. Jadi dua panel MENUMPUK (atas-bawah) meski layar lebar.
- `.settings-card { max-width: 540px; }` (`styles.css:493`) → tiap panel di-cap 540px, rata kiri.
  Di layar 1280/1440 ada ruang kosong lebar di kanan → terlihat "gak responsif" (user mau dua panel
  sejajar kiri-kanan).
- `.backup-card { margin-top: 18px; }` (`styles.css:668`) → jarak vertikal antar panel.

### Yang HARUS tetap jalan (jangan regresi — lihat §4)
- `.form-row` stacking di layar sempit: `@media (max-width:600px)` (`styles.css:854-863`) +
  `body[data-device="phone"]` (`styles.css:888-895`). Ini fix kemarin, KEEP.
- Kontrol device-sim di atas link GitHub (`.sidebar-footer` / `.bottom-nav`) — bukan di panel settings,
  jadi otomatis tidak tersentuh.
- Modal device-preview tidak kepotong (`430f33b`): `.modal.device-modal`/`styles.css:738`,
  `.device-preview`/`styles.css:779`, `.device-frame-wrap` — tidak disentuh.
- Halaman asli utuh saat preview (F6): ini fix murni CSS, nol JS → invarian F6 aman.
- Aksesibilitas (focus-trap/ESC/kontras): tidak disentuh.

---

## 2. Rancang fix (reuse breakpoint + token repo, NOL hex baru)

### Breakpoint yang dipilih: pakai **960px yang SUDAH ada** di repo
Repo pakai konvensi **desktop-first** dengan `@media (max-width: ...)`:
- `max-width: 960px` = tablet (pengetatan AdminLTE, `styles.css:822-828`).
- `max-width: 600px` = phone (`styles.css:834-867`).
- `max-width: 480px` = tweak kecil di combo (`styles.css:1238`).
Tidak ada query `min-width` di repo → jangan bikin angka baru. "Layar besar" = **> 960px** (desktop,
sidebar masih ada). "Layar kecil" = **≤ 960px** (tablet + phone). Jadi: base = 2 kolom; collapse ke 1
kolom di `max-width: 960px` (reuse block yang sudah ada di `styles.css:823`).

### Precedents yang dipakai (bukan karangan)
- Override display per-view sudah ada: `.view[data-view="terminal"].is-active { display:flex }`
  (`styles.css:1441`). Kita mirip: `.view[data-view="settings"].is-active { display:grid }`.
- Grid 2 kolom aman (cegah blowout dari lebar input tetap): `.combo-member-fields { grid-template-columns:
  repeat(2, minmax(0, 1fr)); gap: 12px }` (`styles.css:1062-1066`). Pakai pola `minmax(0,1fr)` yang sama.

### CSS yang ditulis (taruh di blok "Settings panel" dekat `styles.css:493`)

Base (desktop > 960px) — dua panel sejajar kiri-kanan:
```css
/* Settings: dua panel sejajar di layar besar (user 2026-09-13).
   Reuse breakpoint 960px repo; collapse ke numpuk di <=960 (lihat @media max-width:960 di bawah).
   Grid pattern mirror .combo-member-fields (styles.css:1062). Token only, no new hex. */
.view[data-view="settings"].is-active {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 18px;          /* 18px = ritme antar-panel repo (banner mb 18 / backup mt 18) */
  row-gap: 0;
  align-items: start;        /* panel pendek (Backup) tdk stretch; konten atas-align */
}
.view[data-view="settings"] .page-banner { grid-column: 1 / -1; }  /* banner full-width di atas */
.view[data-view="settings"] .backup-card { margin-top: 0; }        /* jarak horizontal ditangani column-gap */
```

Collapse (tambahkan ke `@media (max-width: 960px)` yang SUDAH ada, `styles.css:823-828`) — kembalikan
tampilan numpuk persis seperti sekarang (no regression):
```css
  .view[data-view="settings"].is-active { display: block; }
  .view[data-view="settings"] .page-banner { grid-column: auto; }
  .view[data-view="settings"] .backup-card { margin-top: 18px; }
```

### Catatan lebar kolom (biar fe-dev tau ukur apa)
- Di > 960px, tiap kolom = `(lebarKonten - 18) / 2`. Konten = viewport - sidebar(230 `:19`) - ws-pad(36).
  Di 1280 → ~498px/kolom (forms nyaman). Di 961 → ~338px/kolom (agak sempit tapi OK: `.form-input`
  `max-width:60%` `:524` mengecilkan input; label terpanjang "Developer Mode" ~110px muat).
- Band 961–1100 agak rapat; itu BUKAN regresi (hari ini di 961 sudah numpuk 1 kolom 540). Verifikasi
  di §3 (ukur 961/1000/1100), pastikan nol overflow horizontal. JANGAN tambah breakpoint baru untuk
  band ini — andalkan `minmax(0,1fr)` + `max-width:60%` yang sudah menyerap.

---

## 3. Definition of Done (G3 + gate)
1. **Exercise di Chromium NYATA** (ada di Termux, `chromium-browser` 149 — lihat status 0310). Instance
   terisolasi (port acak + `AIGATE_DB_PATH` tmp + PID sendiri; proses user `:8080` TIDAK disentuh, J6).
   Ukur **before/after** di lebar viewport: **1440, 1280, 1100, 961, 960, 768, 600, 375**.
   Untuk tiap lebar, assert (via `offsetTop`/`offsetLeft`):
   - **≥ 961px:** `card1.offsetTop ≈ card2.offsetTop` (sejajar) DAN `card1.offsetLeft < card2.offsetLeft`
     (kiri-kanan). `document.documentElement.scrollWidth ≤ clientWidth` (nol overflow horizontal).
   - **≤ 960px:** `card2.offsetTop > card1.offsetTop` (numpuk) DAN `card1.offsetLeft ≈ card2.offsetLeft`.
   - **Device-sim iframe:** desktop(1280) → sejajar; tablet(768)/phone(375) → numpuk (media-query di
     iframe nyala dari lebar iframe, cocok F6).
2. `.form-row` stacking di ≤600px & `body[data-device="phone"]` tetap jalan (ulangi cek 375px nyata +
   simulasi phone).
3. `vitest` hijau (`node ./node_modules/vitest/vitest.mjs run` — settings.test.js/jsdom tdk hitung layout,
   jadi praktis nol risiko; jangan hapus/disable test). `git diff --check` bersih.
4. **Hanya** `src/frontend/static/styles.css` + 1 baris cache-buster `index.html:61`
   (`styles.css?v=20260924` → `20260925`). Nol hex baru, pakai token `--*`.
   (Bukan invarian i18n: `app.js?v`/`i18n.js?v`/`I18N_VER` tetap `20260923` — styles.css independen,
   precedent `430f33b`.)
5. Receipt fe-dev: file berubah, bukti before/after per lebar, vitest hijau, cache-buster bump.

---

## 4. Larangan
- JANGAN sentuh luar `styles.css` + cache-buster `index.html`. JANGAN ubah `index.html` structure,
  `app.js`, `device.js`, backend, terminal.
- JANGAN bikin breakpoint/media-query baru (pakai 960px yang sudah ada). JANGAN hardcode hex.
- JANGAN regresi: `.form-row` stacking (`:860-863`/`:892-895`), modal device-preview clip fix,
  F6 (halaman asli utuh saat preview), aksesibilitas.
- JANGAN bilang "lemot"/performa — ini layout, bukan CPU.

## 5. Out-of-scope (catat, tanya user kalau mau lanjut)
- "Panel-panel lain banyak yang gak responsif": view Settings HANYA punya 2 panel ini. Kalau user maksud
  panel di **view lain** (providers/combos/proxies/endpoints/usage/analytics/cli), itu task terpisah —
  scope handover ini = halaman Settings saja. Laporkan ke PM bila user mau audit page lain.

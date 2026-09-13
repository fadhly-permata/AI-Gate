# Handover — Device-SIM "preview" harus TERISOLASI di dalam iframe (F6)

**Tanggal:** 2026-09-13 15:35 · **Owner:** fe-dev · **Scope:** `src/frontend/**` SAJA
(edit: `static/app.js`, `static/styles.css`, `static/index.html`, `tests/device_modal.test.js`,
`tests/provider_detail.test.js` komentar). **JANGAN** sentuh `src/backend/**`, `documents/**`,
`.opencode/**`, atau file di luar `src/frontend/**`.

---

## 1. AKAR MASALAH (bukti `file:line` nyata)
Modal dinamai "preview" tapi **mengubah halaman asli**. Dua cacat:

- **(A) Mutasi halaman luar.** `deviceSelectMode(app.js:156-160)` -> `setDevicePreference(app.js:149-154)`
  -> `applyDevice(norm)` di `app.js:151` menulis `document.body.dataset.device = norm` pada **dokumen
  luar** = halaman nyata ikut berubah. Plus `app.js:152 write(DEVICE_KEY, norm)` simpan ke localStorage,
  sehingga `init()` (`app.js:2330` + `app.js:2334 applyDevice`) men-re-apply ke halaman luar tiap reload.
- **(B) Scale-down bikin kecil.** `deviceRenderPreview(app.js:116-132)` pasang
  `deviceFrame.style.transform = "scale(" + scale + ")"` (`app.js:126`), scale = `min(1, availW/dims[0],
  availH/dims[1])`. Kotak preview fixa `.device-preview{height:340px}` (`styles.css:765-775`) +
  `.device-modal{max-width:620px}` (`styles.css:731`). Phone: scale~0.477 -> SELURUH HP termasuk
  bottom-nav 56px->26px dirender ~48% = "kecil + berantakan".

**KEY INSIGHT (dari user):** preview 100% harus di dalam iframe. Di dalam iframe, lebar iframe (375/768/1280)
sudah memicu media-query yang ada (`@media (max-width:600px)` phone `styles.css:796`, `@media (max-width:960px)`
tablet `styles.css:785`). Ditambah 31 rule `body[data-device="phone"]` (`styles.css:831-860,1203,1360,...`)
harus NYALA di dalam dokumen iframe — bukan di luar. Jadi nol `applyDevice` boleh menyentuh dokumen luar.

---

## 2. PERUBAHAN YANG DIMINTA (exact map)

### 2.1 `static/app.js` — `deviceSelectMode` (156-160): stop mutating outer doc
- HAPUS `setDevicePreference(mode)` dari `deviceSelectMode`. Ganti dengan fungsi preview lokal:
  - `deviceSetActiveMode(norm)` — tandai tombol aktif (UI modal, aman, bukan halaman luar).
  - `deviceRenderPreview(norm)` — ukur modal + iframe ke dimensi perangkat (lihat 2.2).
  - **Terapkan device KE DALAM iframe saja:** setelah iframe termuat,
    `deviceFrame.contentWindow.aigate.applyDevice(norm)` (dalam konteks iframe, `document` =
    dokumen iframe -> isolasi total). Guard dengan try/catch + cek `contentWindow.aigate` ada.
    Terapkan juga di `onload` iframe (mode awal) dan saat ganti mode setelah load.
- `setDevicePreference` (149-154) + `applyDevice` (63-70) + ekspor `window.aigate.setDevice` (436) /
  `window.aigate.applyDevice` (437) + `init()` (2330/2334) **BIARKAN** (dipakai boot + test
  `provider_detail.test.js:261`). Modal tidak lagi memanggilnya -> jalur mutasi halaman luar mati.
- `openDeviceModal` (162-197): default mode aktif jangan baca `document.body.dataset.device` luar
  (`app.js:166`) — pakai `DEFAULT_DEVICE` atau variabel sesi lokal (BUKAN localStorage, BUKAN body luar).
  Setelah iframe load, terapkan mode tsb ke dalam iframe.
- **Tambah** `window.addEventListener("resize", ...)` untuk refit modal saat jendela/rotasi berubah
  (cacat sekunder: `deviceRenderPreview` tdk terdaftar di resize list).
- Perbaiki komentar salah fakta: `app.js:87-93` ("Selecting a mode calls applyDevice(mode) so the live
  page + the preview both react") dan `app.js:2393-2397` ("selecting a mode calls applyDevice()") ->
  ganti jadi "preview scoped to the iframe only; the live page is never touched".

### 2.2 `static/app.js` — `deviceRenderPreview` (116-132): KILL transform:scale
- HAPUS `transform`, `scale`, dan logika reserve-scaled-wrap.
- Ukuran modal ke dimensi perangkat, **di-cap ke viewport viewer** biar tdk overflow di layar kecil:
  - phone 375x667 · tablet 768x1024 · desktop 1280x800 (`DEVICE_SIZES` app.js:94).
  - iframe `width:dims[0]px; height:dims[1]px` (konten ukuran ASLI, nol shrink).
  - modal box = `min(dims[0]px, 92vw)` x `min(dims[1]px, 80vh)` dengan `overflow:auto` -> kalau
    perangkat lebih besar dari viewer, scroll DI DALAM kotak (bukan dikecilkan 48%).
  - Bisa lewat CSS custom property `--dev-w`/`--dev-h` yang diset JS di `.device-modal` per mode.

### 2.3 `static/styles.css`
- `.device-modal{ max-width:620px }` (`styles.css:731`) -> ganti jadi ukuran dinamis:
  `width:var(--dev-w,1280px); max-width:92vw; max-height:80vh; overflow:auto;` (box = device-sized).
- `.device-preview{ height:340px; overflow:hidden }` (`styles.css:765-775`) -> `display:flex;
  justify-content:center; overflow:auto;` (scroll container, nol tinggi fixa).
- `.device-frame{ transform-origin:top left; ... }` (`styles.css:777-782`) -> `transform:none;
  width:var(--dev-w); height:var(--dev-h);` (iframe ukuran perangkat, nol scale).
- `.device-frame-wrap` (`styles.css:776`) -> boleh dihapus/dibiarkan (sudah tak dipakai JS).
- Visual: kotak polos bersih cukup (bezel opsional, bukan syarat). `<small>` dimensi di tombol
  (`index.html:1365/1370/1375`) sudah cocok, jangan diubah.

### 2.4 `static/index.html` — cache-buster
- `styles.css?v=20260922` (`:61`) -> `?v=20260923`.
- `app.js?v=20260922` (`:1446`) -> `?v=20260923`.
- JANGAN ubah markup `#deviceModal` (1355-1387), trigger (164/1419), atau `data-device-trigger/mode`.

### 2.5 Tests (repair, JANGAN hapus buta)
- `tests/device_modal.test.js:84-91` ("selecting a mode applies + persists body[data-device]") ->
  **INVERT**: memilih mode HARUS TIDAK mengubah `document.body.dataset.device` luar DAN TIDAK menulis
  `localStorage.getItem("aigate.device")`; yang terjadi = iframe di-resize ke dimensi perangkat + tombol
  aktif. Update juga komentar header `:5-6`.
- `tests/device_modal.test.js:63` (`document.body.dataset.device = "desktop"`) — biarkan sebagai
  precondition; assertion baru cek tetap "desktop" setelah pilih phone (bukti halaman luar tak berubah).
- `tests/provider_detail.test.js:253-265` tetap HIJAU (panggil `setDevice` langsung = uji resync
  bottom-nav via `applyDevice`, path luar yg masih sah). Hanya perbaiki komentar `:258` ("mode buttons
  ... share setDevice()") -> jelaskan modal sudah tak share path itu (preview di-isolate ke iframe).

---

## 3. DEFAULT PM (user: "jangan tanya lagi" — dokumentasikan di receipt)
1. Perangkat oversize: modal = ukuran perangkat, **di-cap ke viewport viewer + internal scroll**,
   TIDAK di-shrink brutal 48%. Phone selalu terbaca (render 100%, scroll bila perlu).
2. Visual: kotak device-sized polos cukup, bersih. Bezel tidak wajib.
3. Halaman asli: **utuh 100%** saat modal terbuka MAUPUN setelah ditutup (nol `applyDevice` luar,
   nol `write(DEVICE_KEY)` dari modal).
4. Aksesibilitas tetap: focus-trap, ESC, click-outside, restore focus (app.js:176-210) — jangan regresi.
5. Penempatan kontrol di atas link GitHub (sidebar desktop `index.html:164` / bottom-nav `index.html:1419`)
   — jangan regresi.

---

## 4. DEFINITION OF DONE (G3 — exercise di Chromium NYATA)
- [ ] `git diff --check` bersih; hanya `src/frontend/**` yang berubah.
- [ ] `vitest` (tests/device_modal.test.js + tests/provider_detail.test.js) HIJAU; suite penuh frontend HIJAU.
- [ ] Chromium nyata (headless, instance terisolasi port acak + `AIGATE_DB_PATH` di luar repo, PID sendiri,
      JANGAN sentuh proses user `:8080`):
  - Buka halaman asli -> cek `document.body` **TIDAK punya `data-device`** dari preview (sebelum pilih mode).
  - Pilih Phone -> modal jadi ~375px lebar, konten iframe ukuran ASLI (bottom-nav proporsional, TIDAK 26px),
    `document.body` luar tetap TANPA `data-device`.
  - Pilih Tablet -> modal ~768px; Desktop -> ~1280px (di-cap ke viewport bila viewer kecil, scroll internal).
  - Tutup modal -> `document.body` luar TETAP tanpa `data-device`; reload halaman asli -> tetap tidak berubah.
  - Inside iframe: `contentDocument.body.dataset.device === <mode>` (31 rule phone shell nyala).
- [ ] Cache-buster `index.html` `?v=20260923` ke-bump (app.js + styles.css).
- [ ] Receipt: file yang diubah, keputusan default, bukti Chromium per mode (sebelum/sesudah), status vitest.

## 5. Bukan scope (jangan kerjakan)
- Hapus `applyDevice`/`setDevicePreference`/ekspor/boot-init (masih dipakai test + boot).
- Ubah responsif halaman asli, bottom-nav, atau trigger placement.
- Backend / dokumen / skill / rule.

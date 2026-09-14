# Handover — Device-SIM preview kepotong KIRI & KANAN (akar: flexbox centering overflow)

**Tanggal:** 2026-09-13 18:35 · **Owner:** fe-dev · **Scope:** `src/frontend/**` SAJA
(edit: `static/styles.css` + `static/index.html` cache-buster + (opsional) `tests/device_modal.test.js` penjaga statis).
**JANGAN** sentuh `src/backend/**`, `documents/**` (kecuali dibaca), `.opencode/**`, `app.js`
(diagnosis menunjuk fix murni-CSS; `app.js` sudah benar — lihat §3).

Follow-up bug BARU dari fitur commit `735d9e2` (branch `refactor/ui`, PR #23). Ini cacat **berbeda**
dari isu "scale 48%" / "preview ubah halaman asli" yang sudah ditutup — itu sudah mati; transform kini
`none` (terukur). Yang tersisa: **sisi kiri (dan kanan) konten preview terpotong & sisi kiri tidak bisa
dicapai scroll.**

---

## 1. AKAR MASALAH — TERBUKTI dengan ukur Chromium nyata (rule F5 + F3), bukan hipotesis

### 1.1 Metode ukur (PM sudah jalankan; fe-dev WAJIB ulangi sebagai DoD)
Instance aigate TERISOLASI (port acak, `AIGATE_DB_PATH` di luar repo, PID sendiri; user `:8080` TIDAK
disentuh — J6). Chromium 149 headless via CDP (`Emulation.setDeviceMetricsOverride` = lebar viewer nyata;
Node 24 global `WebSocket`, tanpa npm). Ukur `.device-preview` (kontainer scroll) vs `#deviceFrame`
(iframe). Metrik kunci per sel (mode × lebar viewer):
- `cont.clientWidth` vs `cont.scrollWidth` (=overflow horizontal).
- posisi `iframe.getBoundingClientRect().left` saat `scrollLeft=0` vs tepi-kiri-isian kontainer
  (`cont.left + paddingLeft`). **left < tepi-kiri = sisi kiri iframe DI LUAR jangkauan** (scrollLeft tak bisa
  negatif). → `leftUnreach`.
- `maxScrollLeft = scrollWidth - clientWidth`; apakah tepi kanan iframe tercapai di `scrollLeft=max`. → `rightUnreach`.
- `computed transform` (harus `none`), `data-device` dokumen LUAR, dan apakah header/Close ada di viewport.

### 1.2 ANGKA BEFORE (kode saat ini, `refactor/ui` @ `735d9e2`) — bug TERREPRODUKSI
`justify-content:center` = **`true`** di semua sel; `transform` = **`none`** di semua sel (bukan isu scale).

| mode @ viewer | cont.clientW | scrollW | iframeW | iframe.left @scrollLeft=0 | **leftUnreach** | maxScrollLeft |
|---|---|---|---|---|---|---|
| phone   @360  | 267   | 330  | 375  | −15    | **54**    | 65 |
| tablet  @360  | 267   | 527  | 768  | −211.5 | **250.5** | 262 |
| desktop @360  | 267   | 783  | 1280 | −467.5 | **506.5** | 518 |
| phone   @768  | 314   | 354  | 375  | (center)| **30.5** | 42 |
| tablet  @768  | 645.5 | 716  | 768  | −7.5   | **61.2**  | 72 |
| desktop @768  | 645.5 | 972  | 1280 | −263.5 | **317.2** | 328 |
| phone   @1280 | 314   | 354  | 375  | (center)| **30.5** | 42 |
| tablet  @1280 | 707   | 747  | 768  | 248.5  | **30.5**  | 42 |
| desktop @1280 | 1116.6| 1207 | 1280 | −7.5   | **81.7**  | 92 |

**`leftUnreach > 0` di 9/9 sel** → persis gejala "kepotong kanan & kiri". Kenapa kiri tak tercapai: kontainer
`.device-preview` (`display:flex; justify-content:center; overflow:auto`) di-overflow oleh child
`.device-frame-wrap` (lebar = `--dev-w`, mis. 1280) yang **lebih lebar dari kontainernya**; `justify-content:center`
menumpuk overflow **simetris** kiri+kanan, dan `scrollLeft` **tidak bisa negatif** → setengah overflow di sisi KIRI
secara permanen tak terjangkau. Bahkan saat perangkat **muat** di viewer (phone 375 di layar 1280, baris phone@1280 & phone@768)
tetap kepotong **30.5px** tiap sisi, karena `.modal.device-modal{ width:var(--dev-w) }` membuat kotak = lebar
perangkat + `padding` modal (22px×2) + `padding` preview (10px×2) **makan ruang**, memaksa overflow 41px yang lalu
di-center.

### 1.3 Cacat SEKUNDER yang ikut muncul saat ukur (mandat #4 — jangan regresi)
Di baseline, pada viewer pendek modal TIDAK muat vertikal: **tombol Close terdorong ke luar viewport**
(`closeIn=false`) karena `.modal.device-modal{ overflow:auto }` membuat SELURUH modal (header+tombol+Close)
yang scroll, bukan cuma area preview. Perbaikan wajib memastikan header/mode-buttons/Close **selalu** dalam
viewport dan **hanya `.device-preview`** yang scroll.

### 1.4 Kenapa diagnosis alternatif GUE (hipotesis user) TEPAT SEBAGIAN & mana yang salah
- ✅ Benar: jebakan `justify-content:center` + overflow simetris + kiri tak tercapai — TERBUKTI angka §1.2.
- ✅ Benar: `width:var(--dev-w)` pada modal + padding makan ruang → bahkan perangkat yang muat pun kepotong.
- ❌ Bukan: `overflow:hidden` warisan — `.device-modal` = `auto`, `.device-preview` = `auto` (terukur, bukan hidden).
- ❌ Bukan: `max-width:92vw` memotong konten — cap viewport itu benar; masalahnya overflow internal, bukan 92vw.
- ❌ Bukan: sisa `transform:scale` — `transform:none` di semua sel (isu 48% sudah mati di `735d9e2`).

---

## 2. FIX — sudah DIVALIDASI PM 12/12 sel di Chromium (before→after terukur)
Ganti geometri: **kotak modal = `fit-content`** (hug perangkat, bukan dipaksa `var(--dev-w)`), **modal = flex
kolom yang TIDAK scroll**, **hanya `.device-preview` yang scroll**, dan **"safe-center"**:
`justify-content:flex-start` + `margin-inline:auto` pada child. Saat perangkat muat → tampil penuh, ter-center,
tanpa scroll. Saat tidak muat → tepi KIRI & KANAN sama-sama tercapai (scroll, bukan di-zoom-out).

### 2.1 `static/styles.css` — `.modal.device-modal` (baris 738–743)
```
.modal.device-modal {
  width: fit-content;          /* was: var(--dev-w,620px) -> jangan paksa kotak=lebar perangkat */
  max-width: 92vw;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;            /* was: auto -> modal tak scroll; yang scroll hanya .device-preview */
}
```
### 2.2 `static/styles.css` — anak-anak modal jangan ikut mengecil (tambah SETELAH blok 2.1)
```
.modal.device-modal > .modal-title,
.modal.device-modal > .settings-dev-note,
.modal.device-modal > .device-modes,
.modal.device-modal > .form-actions { flex: 0 0 auto; }
```
### 2.3 `static/styles.css` — `.device-preview` (baris 779–788): **INI INTI BUG**
```
.device-preview {
  flex: 0 1 auto;
  min-height: 0;               /* WAJIB: izinkan menyusut supaya scroll INTERNAL, bukan dorong Close keluar */
  display: flex;
  justify-content: flex-start; /* was: center -> HILANGKAN tumpukan overflow simetris (sebab kiri tak tercapai) */
  align-items: flex-start;
  padding: 10px;
  background: var(--bg);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius);
  overflow: auto;
}
```
### 2.4 `static/styles.css` — `.device-frame-wrap` (baris 789): safe-center
```
.device-frame-wrap { flex: 0 0 auto; margin-inline: auto; }
```
(`margin-inline:auto` pada flex child = center HANYA saat ada ruang bebas; saat overflow margin runtuh ke 0 → tepi
kiri tetap di `scrollLeft=0`, tercapai.)
### 2.5 `static/index.html` — cache-buster
- `styles.css?v=20260923` (baris 61) → `?v=20260924`. **Hanya `styles.css`** yang di-bump (tak ubah `app.js`/
  `i18n.js`/`I18N_VER`) → invarian `i18n.test.js:307-315` (`app.js?v == i18n.js?v == I18N_VER`) TETAP utuh di
  `20260923`, tidak tersentuh. JANGAN sentuh markup `#deviceModal`.

### 2.6 ANGKA AFTER (target PM, terukur — ini yang harus fe-dev reproduksi)
Semua 12 sel (phone/tablet/desktop × viewer 360/768/1280/1280×480-pendek): **leftUnreach=0, rightUnreach=0,
title/modes/close IN-viewport, modalScrolls=false, transform=none.** Contoh representative:

| mode @ viewer | target: leftUnreach | rightUnreach | maxScroll | fitsNoScroll | close in view |
|---|---|---|---|---|---|
| phone   @360  | 0 | 0 | 130  | false (scroll, kedua tepi capai) | ✅ |
| desktop @360  | 0 | 0 | 1035 | false | ✅ |
| phone   @768  | 0 | 0 | 0    | **true (muat penuh, nol-scroll)** | ✅ |
| phone   @1280 | 0 | 0 | 0    | **true** | ✅ |
| desktop @1280 | 0 | 0 | 185  | false (scroll kanan+kiri capai) | ✅ |
| tablet  @1280 | 0 | 0 | 0    | **true** | ✅ |

---

## 3. Kenapa `app.js` TIDAK diubah (biar fe-dev tidak "ngoprek" yang sudah benar)
`deviceRenderPreview` (`app.js:123-129`) men-set `--dev-w`/`--dev-h` di `.device-modal` → cascade ke
`.device-frame{ width:var(--dev-w) }` (`styles.css:790-793`). Itu sudah bikin iframe = lebar perangkat ASLI +
`transform:none`. Bug-nya **murni** di cara `.device-preview` men-center & cara modal mengukur kotak-nya
(CSS), bukan di JS. `--dev-w` tetap dipakai (untuk lebar iframe); yang berubah cuma: modal tak lagi memaksakan
`width:var(--dev-w)` (jadi `fit-content`), dan preview tak lagi `justify-content:center`.

---

## 4. DEFINITION OF DONE (G3 — exercise di Chromium NYATA, instance terisolasi; J6 jangan sentuh `:8080`)
- [ ] `git diff --check` bersih; HANYA `src/frontend/**` berubah (`styles.css` + `index.html` baris 61; opsional test).
- [ ] `vitest` (suite penuh frontend) HIJAU; `device_modal.test.js` tetap hijau (kontrak `--dev-w/--dev-h` +
      body luar tak berubah + tombol aktif — tak tersentuh fix ini).
- [ ] **Reproduksi ukur §1.1** pada minimal 3×3 (phone/tablet/desktop × viewer 360/768/1280) + 1 viewer pendek
      (mis. 1280×480):
  - [ ] **leftUnreach == 0** dan **rightUnreach == 0** di SEMUA sel (kiri & kanan tercapai; tak ada sisi "hilang").
  - [ ] `scrollWidth` kontainer saat perangkat **muat** (phone@≥ 500px, tablet/desktop@1280): overflow nol →
        konten penuh tanpa scroll.
  - [ ] `transform` iframe = `none`; `data-device` dokumen LUAR tidak berubah karena preview (F6 utuh).
  - [ ] Header (`#deviceModalTitle`), `.device-modes`, dan tombol `#deviceModalClose` **semua** dalam viewport
        pada viewer normal DAN viewer pendek (1280×480); **hanya `.device-preview`** yang scroll (modal sendiri tidak).
- [ ] Aksesibilitas TIDAK regresi: focus-trap 2 arah, ESC tutup + restore fokus, click-outside (logika `app.js`
      tak berubah — cukup verifikasi masih jalan di Chromium).
- [ ] Penempatan kontrol tetap di atas link GitHub (sidebar desktop / bottom-nav mobile) — tak berubah.
- [ ] Halaman asli tetap 100% (F6): buka→phone→tablet→desktop→tutup→reload, body luar identik, `localStorage.aigate.device` null.
- [ ] Cache-buster `styles.css?v=20260924` (index.html:61); app.js/i18n.js/I18N_VER **TETAP** `20260923`.
- [ ] Receipt: file diubah, angka after tiap sel, status vitest, konfirmasi Close selalu in-view.

## 5. Opsional (nilai tambah, bukan syarat lolos) — penjaga regresi STATIS
Jsdom tak mengukur layout, jadi cacat ini tak tertangkap unit test. Tambahkan di `tests/device_modal.test.js`
satu assertion statis pada isi `styles.css`: blok `.device-preview` **tidak** lagi memakai
`justify-content:center`, dan `.modal.device-modal` memakai `overflow:hidden` (bukan `auto`). Menjaga agar
"centering overflow" tidak kembali. (Kalau ditambah, tetap jaga invarian cache-buster §2.5.)

## 6. Bukan scope
- Ubah `app.js`, `device.js`, markup `#deviceModal`, responsif halaman asli, bottom-nav, atau placement kontrol.
- Backend / dokumen / rule / skill. Hapus `applyDevice`/`setDevicePreference`/boot.
- Ubah `max-width:92vw`/`max-height:80vh` (cap viewport benar — jangan disentuh).

## 7. Catatan integrasi (milik PM, bukan fe-dev)
Landed di branch `refactor/ui` yang PR-nya (#23) masih TERBUKA → commit fix ini ikut memperbarui PR #23
(setelah push). PM yang audit diff + jalankan gerbang vitest + reproduksi ukur Chromium + commit + push.

# Handover — Lebar Panel Settings dalam Persen (50% layar besar / 100% layar kecil)

- **Tanggal**: 2026-09-14 • **PM** • Owner: **fe-dev** (spawn oleh user) • Scope tulis: **HANYA `src/frontend/**`**
- **Lanjutan dari**: `c495d68` (dua panel sejajar) — user lapor: "kok ukuran width panelnya gak kayak 50% yak waktu di layar besar. dan gak kayak 100% waktu di layar kecil (ponsel)"
- **Aturan kerja**: D2 (sudah diperintahkan = kerjakan), F5 (jangan salah tafsir / jangan karang akar), F3 (klaim butuh bukti), A2 (PM nol tulis `src/`), J6 (`:8080` user tak disentuh).

## 0. RINGKASAN HASIL UKUR (Chromium 149 NYATA, instance terisolasi — bukan hipotesis)

Harness: `node /data/data/com.termux/files/usr/tmp/opencode/spw-aigate/spw_measure.mjs` (env `CDP_PORT=51784 SRV_ORIGIN=http://127.0.0.1:51783`; server `python3 run.py --port 51783` + `AIGATE_DB_PATH` di tmp luar repo; output mentah `spw-aigate/out.json`). Diulang saat verifikasi pakai port acak sendiri.

**Patokan "100%" = `clientWidth` `<section data-view="settings">`** (area konten tempat kartu hidup; sudah dikurangi sidebar + padding workspace).

### 0.1 Layar besar (grid side-by-side, ≥961px) — GEJALA USER BENAR
| viewport | section clientWidth | kolom grid resolved | lebar kartu | **rasio kartu/section** | ruang mati per kolom |
|---|---|---|---|---|---|
| 1440 | 1174 | 578 + 578 (gap 18) | **540** (cap) | **46.0%** | 38px |
| 1280 | 1014 | 498 + 498 | 498 | 49.1% | 0 |
| 1100 | 834 | 408 + 408 | 408 | 48.9% | 0 |
| 961 | 695 | 338.5 + 338.5 | 339 | 48.8% | 0 |
| **1920** | 1654 | 818 + 818 | **540** (cap) | **32.6%** | **278px** |

→ Cap 540px mulai memakan kolom sejak kolom > 540 ⟺ section > 1098px ⟺ **viewport ≳1364px**. Di 1440 sudah kelihatan (46%, kartu tak menyentuh tepi kolom), di ≥1536 makin parah (1920 = 32.6%). Di 961–1360 sebenarnya sudah ≈49% (tidak rusak). Overflow horizontal **0 di semua lebar** (`scrollWidth==clientWidth`, dokumen & workspace).

### 0.2 Layar kecil numpuk (≤960, display:block) — bagian "ponsel" PERLU KEJUJURAN
| viewport | section clientWidth | lebar kartu | rasio | max-width menang |
|---|---|---|---|---|
| 960 | 717 | **540** (cap) | **75.3%** | `.settings-card` :493 |
| 900 | 657 | **540** (cap) | **82.2%** | :493 |
| 800 | 557 | **540** (cap) | 96.9% | :493 |
| 768 | 525 | 525 | 100% | (container sudah < cap) |
| 700 | 457 | 457 | 100% | (container sudah < cap) |
| 600 | 561 | 561 | **100%** | `.settings-card,.welcome-card{max-width:100%}` :880 |
| 375 | 336 | 336 | **100%** | :880 |

→ **Ponsel portrait nyata (≤600px = 375/600) FAKTANYA SUDAH 100%.** Tidak ada cacat di sana pada HEAD `c495d68` — rule `styles.css:880` (di `@media (max-width:600px)`) sudah menang atas cap :493 (dikonfirmasi computed style + matched rules CDP). **Zona yang benar-benar bolong = 781–960** (HP landscape mis. iPhone Pro Max 932px CSS px, jendela sempit/desktop di-kecilkan): kartu mentok 540 rata-kiri → 75–97%, bukan 100%. Kemungkinan besar inilah yang user lihat sebagai "ponsel gak 100%", atau dia melihat sebelum refresh versi lama. Jangan tulis fix seolah 375 rusak — angka bilang tidak.

### 0.3 Jalur device-sim (modal @ viewer 1280, iframe same-origin, diukur dari contentDocument)
| mode | innerW iframe | section clientWidth | kartu | rasio/section | rasio/viewport-iframe |
|---|---|---|---|---|---|
| phone 375 | 373 | 334 | 334 | **100%** | 89.5% (sisa = padding workspace 12×2 + scrollbar — normal, semua webpage begitu) |
| tablet 768 | 766 | 523 | 523 | **100%** | 68.3% |
| desktop 1280 | 1278 | 997 | 490 | 49.1% | 38.3% |

→ Device-sim phone/tablet = 100% dari area konten. Yang layak diperbaiki di sim = **mode desktop** (ikut aturan grid besar).

## 1. AKAR MASALAH (terbukti, satu rule untuk SEMUA sisa gejala)

- **`.settings-card { max-width: 540px }` — `src/frontend/static/styles.css:493`.** CDP `CSS.getMatchedStylesForNode` pada kartu pertama @1440: selector menang `.settings-card`, nilai `540px`, `style.range.startLine = 492` (0-based) = **baris 493**, tanpa media query. Rule ini warisan era pra-grid (satu kolom 540) dan TIDAK ikut dinetralkan `c495d68`.
  - Di grid ≥961: kartu tak boleh tumbuh > 540 walau kolom 578–818 → rasio 46%/32.6% ≠ 50%.
  - Di blok 781–960: kartu 540 < container 553–732 → bukan 100%.
- Bukan `grid-template-columns` (resolved benar `repeat(2, minmax(0,1fr))`), bukan margin (computed `0 auto` tidak muncul; rect.left kartu = rect.left kolom → nol margin eater), bukan overflow (0 semua lebar).

## 2. FIX SIAP-EKSEKUSI (per-baris)

### 2.1 `src/frontend/static/styles.css` — SATU rule, di dalam blok settings yang sudah ada
Setelah baris 513 (`.view[data-view="settings"] .backup-card { margin-top: 0; }`), masih di blok yang sama, tambah:

```css
/* The 540px cap (line 493, warisan era satu-kolom) still clamps each card INSIDE
   the wider grid columns → 46% @1440, 32.6% @1920 (user: "gak kayak 50%"), and
   75–97% in the 781–960 stacked band (user: "gak 100% di layar kecil"). Inside the
   Settings view only, drop the cap: grid items then fill their column (≈50% minus
   half the 18px gap) and stacked cards fill the container (100%). Specificity
   (0,2,0) beats `.settings-card` :493 (0,1,0) and the ≤600 `max-width:100%` rule
   (:880) — `none` there is equivalent, so phones keep the proven 100%. No new
   breakpoint, no colors, no other view touched (.welcome-card cap stays). */
.view[data-view="settings"] .settings-card { max-width: none; }
```

**Scopenya CUMA di dalam section settings** — jangan hapus/ubah baris 493 (grep `settings-card` di `index.html` = HANYA :201 dan :250, dua-duanya anak section settings → override scoped cukup; cap global dibiarkan utuh untuk pemakaian lain di masa depan).
- Nol breakpoint baru (aturan cukup di semua zona lewat satu selector descendant).
- `minmax(0,1fr)` (`:507`) sudah melindungi kolom dari input melebar → `max-width:none` tidak bisa bikin overflow; tetap wajib diassert (lihat §3).

### 2.2 `src/frontend/static/index.html` — cache-buster
Baris 61: `styles.css?v=20260925` → `styles.css?v=20260926`. HANYA link styles.css. app.js/i18n.js/`I18N_VER` TETAP `20260923` (invarian `i18n.test.js:307-315`).

### 2.3 Yang DILARANG ikut berubah (no-regression list)
- `.settings-card{max-width:540px}` :493 — biarkan utuh (kita override scoped, bukan cabut global).
- Grid block `c495d68` :505–513 (selain 1 rule tambahan §2.1) + collapse `@media(max-width:960px)` :851–853 — utuh.
- `.page-banner` `grid-column:1/-1` — utuh. `@media(max-width:600px)` :880 + `.form-row` stacking :886–889 + `body[data-device="phone"]` :914–921 — utuh.
- Fix clip preview device-sim `430f33b` (`.device-modal`/`.device-preview`/`.device-frame`) — jangan sentuh; `device_modal.test.js` (13 tes) wajib hijau.
- `app.js`, `i18n.js`, `I18N_VER`, markup form/backup/banner — nol sentuh (murni CSS; F6: halaman asli tetap utuh saat preview).
- Kontrol device-sim tetap DI ATAS link GitHub (sidebar-footer/bottom-nav) — tak boleh bergeser.
- Nol warna hex baru; nol file baru; scope HANYA 2 berkas di atas.

## 3. DEFINITION OF DONE (angka terukur, WAJIB repro Chromium nyata seperti §0)

Jalankan harness (buat ulang/ pakai `spw_measure.mjs`; server isolated port acak + DB tmp luar repo + chromium `--user-data-dir` tmp + PID sendiri; `:8080` tak disentuh; AFTER = working tree fe-dev). Target dengan fix §2.1:

1. **≥961 (uji 961,1024,1100,1280,1440,1920)**: `lebar kartu == gridTemplateColumns[0] resolved` (ruang mati/kolom **0 ±1px**) dan **rasio kartu/section = (secW−18)/(2·secW)** → 1440: 578/1174 = **49.2%** · 1920: 818/1654 = **49.5%** · 961: **48.8%** · semua **≥48.5%** dan **<50%** secara matematis (gap 18px memang ruang antar-panel, bukan "kosong"; ini ≈50%-nya).
2. **≤960 (uji 960,900,800,768,700,600,375)**: `offsetWidth kartu == section clientWidth` **±1px → 100.0%** di SEMUA lebar ini (termasuk band 781–960 yang tadinya 75–97%).
3. **Nol overflow horizontal** semua lebar: `documentElement.scrollWidth−clientWidth == 0` dan `.workspace` sama 0.
4. **Geometri c495d68 tak berubah**: ≥961 sejajar (Δtop<2, left beda); ≤960 numpuk (left sama, top kartu2 > kartu1); banner selebar section.
5. **Device-sim**: phone 373 → 100% · tablet 766 → 100% · desktop 1278 → rasio section **49.1%** (490→489.5, kartu = kolom), nol overflow, preview tidak kepotong (regresi `430f33b`), modal close/title/kontrol in-view.
6. `node ./node_modules/vitest/vitest.mjs run` hijau penuh (baseline 27 berkas/685 tes) + `git diff --check` bersih.
7. `.form-row` tetap stacking di 600/375 (`flex-direction:column` computed) + `body[data-device=phone]` tetap menyetir shell phone.
8. Cache-buster §2.2 terpasang; receipt cantumkan angka BEFORE (tabel §0) vs AFTER per lebar + salinan rule menang CDP (`max-width` → `.view[data-view="settings"] .settings-card none`).
9. **JANGAN commit** — PM yang audit + commit + push setelah verifikasi mandiri.

## 4. CATATAN UNTUK USER (lapor jujur, F5/F3)
- Keluhan **layar besar BENAR** dan akar tunggal = cap 540px (`styles.css:493`): 46% @1440, 32.6% @1920.
- Keluhan **ponsel ≤600 TIDAK terbukti rusak** — terukur sudah 100% di viewport nyata DAN device-sim phone (rule :880 sudah menang). Yang nyata bolong = **band 781–960** (HP landscape / jendela desktop sempit / sisi tabletnya modal) = 75–97%. Fix §2.1 sekaligus menutup band ini. Kalau di HP portrait tetap terlihat sempit setelah ini: hard-refresh sekali (index.html & styles.css dilayani tanpa `Cache-Control`, cuma ETag/Last-Modified — browser bisa sajikan varian lama sebelum expired heuristik; cache-buster §2.2 memaksa URL CSS baru).
- Angka 89.5% "rasio terhadap viewport iframe phone" di §0.3 bukan cacat: sisanya padding workspace 12px×2 + scrollbar, sama seperti semua halaman web.

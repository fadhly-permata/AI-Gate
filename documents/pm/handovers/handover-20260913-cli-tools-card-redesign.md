# Handover — Redesign CLI Tools jadi Card + Logo Platform (Responsif)

**Tanggal:** 2026-09-13
**Mode:** sekuensial (R16, sesi ini user pilih sekuensial)
**Eksekutor:** fe-dev (frontend-only)
**Branch:** `refactor/ui`

## GOAL
Redesign tampilan daftar CLI Tools supaya tiap tool tampil sebagai **card** yang enak
dipandang (bukan sekadar tombol berteks). Untuk platform, pakai **logo platform saja**
(ikon Font Awesome brand, lokal — tanpa CDN), bukan teks label. Seluruh view harus
**responsif** (phone/tablet/desktop) dan rapi di light + dark theme.

## CONTEXT (bukti file:line)
- Root view: `src/frontend/static/index.html:855` `<section data-view="cli">`,
  container `#cliGroups`; banner `.page-banner` di atasnya (jangan disentuh).
- Logika render: `src/frontend/static/clitools.js`
  - `loadCliTools` :174 — fetch `GET /api/cli-tools`, panggil `renderGroups(list, current_platform)`.
  - `COMPAT_PLATFORMS` :187 = `["termux","linux","windows","macos"]`.
  - `renderGroups` :257 — bangun DOM per grup + grid `.cli-tools`.
  - `renderCompatStrip` :200 — 4 chip teks per platform (INI yang mau diganti jadi logo).
  - `renderCompatWarn` :219 — baris warning merah bila platform saat ini tidak bisa.
  - `renderCompatLegend` :231 — legenda 4 chip di atas grup.
  - `unsupportedNote` :249 — teks alasan tool tidak launchable.
  - Klik :305-308 — `launch_mode==="verified"` → `openLaunchModal(g, tool)`;
    selain itu → `setCliMsg(unsupportedNote(tool), "warn")`. **Pertahankan persis.**
- Shape data `ToolDTO`: `compat` = `Dict[str, {status,note,source}]` key termux/linux/
  windows/macos; `launch_mode` (verified|pending|unsupported); `current_platform` dari response.
- Styling sekarang: `src/frontend/static/styles.css:1836-1925`
  - `.cli-tools` grid `repeat(auto-fill, minmax(140px,1fr))` :1867-1871
  - `.cli-tool` tombol teks doang :1872-1877
  - `.cli-compat-chip` pil teks :1890-1894; status color :1907-1913
  - `.cli-tool-unsupported` line-through :1882-1886 (penyebab "tembok coret")
- i18n (PAKAI untuk aria-label, JANGAN ubah value): `i18n/en.js:142-145`
  `cli.platform.{termux:Termux, linux:Linux, windows:Windows, macos:macOS}`;
  status `cli.status.*` :146-152.
- Font Awesome: **vendored lokal** (`vendor/font-awesome/css/all.min.css` +
  `webfonts/fa-brands-400.woff2`), sudah dilink di `index.html:51`. Glyph brand
  TERBUKTI ada: `fa-linux`(\f17c) `fa-apple`(\f179) `fa-windows`(\f17a) `fa-android`(\f17b).
  Pakai class `fa-brands fa-<glyph>` (brand butuh prefix `fa-brands`/`fab`).
  Pemetaan: termux→`fa-android`, linux→`fa-linux`, windows→`fa-windows`, macos→`fa-apple`.
  **JANGAN pakai CDN.**
- Responsif project: auto-fill grid + `@media (max-width:…)` (styles.css :487/607/681/
  692/1081/1235/1265/1702/1728; titik 480/600/960) + `body[data-device="phone|tablet|desktop"]`
  (device.js). Pakai idiom yang sama.

## SCOPE (fe-dev WRITE roots — KETAT)
- `src/frontend/static/clitools.js`
- `src/frontend/static/styles.css`
- `src/frontend/static/index.html` — **HANYA** dua nilai `?v=` cache-buster:
  `styles.css?v=20260913` (line 61) dan `clitools.js?v=20260920` (line 1418),
  di-bump tiap kali file pasangannya berubah. (Pelajaran PM: lupa bump = fix gak sampai
  ke browser karena asset di-cache.)

READ: `documents/pm/**`, `src/frontend/static/i18n/*.js` (reuse key, jangan edit value),
file lain di `src/frontend/static/*` untuk referensi konvensi.
**JANGAN** edit `src/backend/**`, value kunci i18n, atau markup view lain.

## DESIGN REQUIREMENTS
1. **Card per tool**: rounded (~10–12px), border tipis + shadow lembut, padding nyaman,
   terpisah jelas antar card. Hover/focus: lift (`translateY`) + shadow lebih kuat,
   transisi halus. Hormati `[data-theme="dark"]` lewat CSS var (--bg,--fg,--panel-border,
   --accent,--warn-*). Reuse token `.card` yang ada.
2. **Isi card**:
   - Atas: nama tool (bold) + penanda status launch kecil. Jangan coret nama.
     Untuk `launch_mode != "verified"` pakai treatment "muted/disabled" yang sopan
     (opacity turun + badge info/soon pakai kelas `.badge` yang ada) — BUKAN tembok coret.
     Alasan tetap di `title` + aria.
   - Baris logo platform: tepat 4 platform sebagai ikon FA brand (ukuran konsisten
     ~18–20px), **tanpa teks label** (sesuai permintaan). Status per-platform ditunjukkan
     via warna/opacity ikon pakai palet status existing (:1907-1913): verified=hijau,
     installable=biru, broken=merah, no_install=amber, not_a_cli=slate, not_wired=ungu,
     unknown=abu. Unsupported/unknown → diredupkan (opacity ~0.4). Platform saat ini
     (`current_platform`) → di-highlight (ring/outline, reuse konsep `.cli-compat-current`).
     Tiap ikon punya `aria-label` = nama platform lokal (`getStr("cli.platform."+code)`)
     dan `title` = `"<Platform>: <statusLabel> — <note>"`.
   - Legenda/hint: `renderCompatLegend` boleh jadi legenda ikon (logo + 1 baris note) atau
     di-drop demi kebersihan — terserah, tapi jaga learnability.
   - Baris warning merah (`renderCompatWarn`) untuk platform saat ini tidak bisa tetap ada,
     tapi style dalam card secara halus (kecil, tidak mengganggu).
3. **Grid/responsif**: pakai idiom auto-fill grid. Pilih min nyaman di desktop
   (mis. `minmax(220px,1fr)`) supaya card punya ruang; di phone (`body[data-device="phone"]`
   atau `@media (max-width:600px)`) turunkan ke ~150–160px dan pastikan baris logo platform
   tidak wrap jagged (flex wrap + gap, ikon tetap 1 baris atau wrap rapi). Verifikasi visual
   di ~360px (phone), ~768px (tablet), ≥1024px (desktop). Tidak ada horizontal overflow.
4. **Pertahankan behavior persis**:
   - card verified diklik → `openLaunchModal(g, tool)`
   - card unsupported diklik → `setCliMsg(unsupportedNote(tool), "warn")` (gagal TERTUTUP,
     jangan jalankan perintah tebakan)
   - `aria-disabled` di unsupported, tetap bisa di-focus keyboard.
5. **Tidak ada** framework/dependency/CDN baru. Tetap vanilla JS + `createElement`.
   Kunci i18n tetap utuh.

## DEFINITION OF DONE
- Tiap cli-tool tampil sebagai card menarik (nama + status + 4 logo platform + warning opsional),
  bukan tombol teks.
- Platform tampil sebagai logo ikon saja; status via warna/opacity ikon; platform saat ini
  highlight; accessible (aria-label + title).
- Sepenuhnya responsif di phone/tablet/desktop: grid reflow, wrap ikon rapi, tidak ada
  scroll horizontal, legible di dark+light.
- Klik/launch + warning lama tetap jalan; tidak ada JS error.
- `clitools.js` lolos `node --check`; gate lint project (jika ada) lolos.
- Cache-buster `?v=` untuk `clitools.js` (line 1418) & `styles.css` (line 61) di-bump;
  `index.html` cuma berubah di dua baris itu.
- Tidak ada edit backend / kunci i18n; view lain tidak rusak.

## CONSTRAINTS
- Mode sekuensial — implementasi fokus tunggal, tanpa sub-pekerjaan paralel.
- JANGAN kill/restart aplikasi; JANGAN commit/push/PR (user yang putus). Kembalikan receipt.

## RECEIPT (wajib dari fe-dev)
- File berubah + line ref.
- Keputusan (legenda dipertahankan/di-drop, lebar min card dipilih, dst).
- Open question / hal yang butuh keputusan user.
- Cara verifikasi (node --check + alasan visual).
- Kunci i18n yang menurutmu kurang (jangan tambah sendiri, laporkan).

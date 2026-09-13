# Laporan Verifikasi PM — Device-Sim Preview Terisolasi di iframe + Modal Seukuran Perangkat

- **Tanggal/waktu:** 2026-09-13 16:25 WIB (sesi verifikasi PM)
- **Branch / commit fitur:** `refactor/ui` @ `735d9e2` — `fix(ui): isolate device-sim preview ke iframe + modal device-sized`
- **Handover acuan:** `documents/pm/handovers/handover-20260913-device-preview-isolasi.md`
- **Pelaksana:** fe-dev · **Integrasi & verifikasi:** ProjectManager
- **Aturan terkait:** F6 (preview wajib terisolasi), F3 (klaim butuh bukti), G3 (exercise nyata), J6 (jangan sentuh proses user), H1–H3 (commit per fitur + catatan per berkas), B1–B5.

## 1. Ruang lingkup perubahan (audit diff)
Lima berkas, semuanya di `src/frontend/**` — sesuai scope handover; tidak ada berkas di luar scope;
`git diff --check` bersih (exit 0); tidak ada nilai hex warna baru pada diff.

| Berkas | Isi perubahan |
|---|---|
| `static/app.js` | `deviceSelectMode` tidak lagi memanggil `setDevicePreference`; mode disimpan di variabel sesi `devicePreviewMode`; fungsi baru `deviceApplyInFrame` menerapkan device HANYA di dalam iframe (`contentWindow.aigate.applyDevice`, guarded try/catch); `deviceRenderPreview` menghapus `transform:scale` dan menyetel `--dev-w`/`--dev-h`; `openDeviceModal` memakai default sesi (bukan body luar/localStorage); listener `load` iframe + `resize` jendela ditambahkan; tiga blok komentar salah fakta dikoreksi. |
| `static/styles.css` | `.modal.device-modal` = device-sized (`width:var(--dev-w)`, cap `92vw`/`80vh`, `overflow:auto`); `.device-preview` jadi scroll container ( tinggi fixa 340px dihapus); `.device-frame` tanpa transform, ukuran px perangkat. Selector dua-kelas diperlukan agar tidak kalah oleh `.modal{max-width:540px}` (baris 1235). |
| `static/index.html` | Cache-buster `20260922 → 20260923` untuk `I18N_VER`, `styles.css`, `i18n.js`, `app.js`. |
| `tests/device_modal.test.js` | Kontrak DI-INVERT: memilih mode harus TIDAK mengubah `body[data-device]` luar dan TIDAK menulis `localStorage`; assertion baru memeriksa `--dev-w/--dev-h` + tombol aktif. |
| `tests/provider_detail.test.js` | Hanya komentar; jalur `window.aigate.setDevice` (hook halaman luar) tetap sah dan hijau. |

## 2. Verifikasi mandiri PM (bukan menelan receipt)
1. **Vitest** dijalankan PM sendiri: 27 berkas / **681 tes LOLOS** (termasuk 9 tes `device_modal` kontrak baru).
2. **`git diff --check`**: bersih, exit 0.
3. **Spot-check per titik klaim** (file:line hasil baca langsung): `app.js:102` (`devicePreviewMode`), `:123-131` (`deviceRenderPreview` tanpa scale), `:134-145` (`deviceApplyInFrame`), `:171-178` (`deviceSelectMode` tanpa `setDevicePreference`), `:187` (default sesi), `:251-263` (load + resize), `styles.css:738-746` (`.modal.device-modal`) vs `:1235-1245` (`.modal` base). Semua cocok dengan receipt.
4. **Chromium nyata (G3):** harness fe-dev `verify_device_preview.mjs` dijalankan ULANG oleh PM terhadap server terisolasi (port acak 43669, DB di tmp luar repo, PID sendiri): **22/22 PASS, exit 0.** Sorotan bukti:
   - Halaman luar: `data-device="desktop"` (nilai boot) KONSTAN sejak boot → buka modal → phone → tablet → desktop → tutup → reload; `localStorage.aigate.device` tetap `null` di semua titik. Keluhan inti ("preview mengubah halaman asli") terbukti MATI.
   - Ukuran nyata: box 375/768/1280 px; iframe `transform:none`; viewport dalam frame 373–375 px saat phone (media query + 31 rule `body[data-device=phone]` menyala DI DALAM frame); bottom-nav dalam frame tinggi asli 56px (sebelumnya terscale ±26px).
   - Viewer kecil (820px): modal di-cap 754px (≤92vw) sementara iframe TETAP 1280px dengan scroll internal — sesuai default PM §3.1 (bukan shrink 48%).
   - Proses aplikasi user di `:8080` (`python run.py`, PID 25956) tidak disentuh sebelum/selama/sesudah (J6). Satu PID uvicorn sisa (31592) teridentifikasi sebagai server terisolasi sesi fe-dev sebelumnya, bukan aplikasi user; hilang sendiri setelah harness selesai.

## 3. Keputusan PM atas open question
- **OQ#1 — nuansa "boot default": DINYATAKAN CUKUP, tanpa tindakan kode pada scope ini.**
  Inti keluhan user adalah halaman asli berubah saat memakai modal; terverifikasi halaman asli identik
  sebelum dan sesudah modal (dan setelah reload). Sisa nuansa — `init()` men-stempel
  `body[data-device="desktop"]` sejak boot — tidak berdampak: tidak ada satu pun rule CSS untuk nilai
  `desktop` (grep = 0), dan responsivitas ponsel asli digerakkan `@media` berdasarkan lebar viewport,
  bukan atribut itu. Opsional, perlu tanya user dulu: menghapus stempel boot agar atribut tidak ada sama
  sekali, atau mode preview ringan `?preview=1`.
- **OQ#2 — bump cache-buster tambahan (`i18n.js` + `I18N_VER`): SAH dan PERLU, bukan scope creep.**
  `tests/i18n.test.js:307-315` menetapkan invarian `app.js?v == i18n.js?v == I18N_VER`; menaikkan
  `app.js` sendirian akan menjatuhkan suite. `device.js` dibiarkan `20260922` karena berkasnya tidak
  berubah dan tidak terikat invarian.

## 4. Status akhir & sisa pekerjaan
- **Selesai & terverifikasi; ter-commit `735d9e2` di `refactor/ui`. Belum di-push, belum dibuatkan PR**
  (menunggu perintah user).
- Sisa pekerjaan yang masih terbuka:
  1. Uji mata dan sentuhan layar langsung oleh user di ponsel (headless desktop tidak mewakili WebView/sentuhan).
  2. Terjemahan `common.close` untuk 6 bahasa belum ditinjau penutur (warisan `161bcaf`).
  3. Follow-up opsional (butuh keputusan user): hapus stempel `data-device` boot; mode preview ringan.

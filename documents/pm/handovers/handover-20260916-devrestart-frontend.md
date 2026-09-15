# Handover — DEV-RESTART frontend: tombol Settings (be-dev selesaikan backend dulu)

Tanggal: 2026-09-16 | Owner: **fe-dev** | PM: ProjectManager
Backend SUDAH jadi & terverifikasi: `POST /api/dev/restart` → 200 `{"status":"restarting"}` kalau Developer Mode ON, 403 `{"error":{...,"code":"dev_mode_required"}}` kalau OFF (gate fail-closed di server). `GET /api/health` sudah ada (server.py:145) untuk polling. Pakai kontrak ini.

## Tujuan
Tombol **"Restart aigate"** di halaman Settings, **HANYA tampil saat Developer Mode ON** (sesuai perintah user). Klik → konfirmasi → panggil endpoint → server restart in-process (lewat `os.execv`, sudah di-backend) → setelah hidup lagi, halaman reload otomatis.

## Fakta FE (PM verifikasi)
- Pusat gate dev-only: `applyDevMode(bool)` di app.js (line ~2154: "dev_mode false => hide the 3 dev-only surfaces (Log Window, Device ...)"); tombol ikut mekanisme ini → pakai kelas/atribut `dev-only` yang sudah dipakai Log Window/Device Sim, jangan bikin gate sendiri.
- Settings view: `index.html:207 <section data-view="settings">`, kartu `settings-card` (213), checkbox Developer Mode (223–225 `setDevMode`). Letakkan tombol restart di kartu terpisah SETELAH developer-mode, TETAPI beri penanda dev-only (hidden saat dev_mode false).
- `/api/settings` GET balikin `{..., dev_mode: "true"|"false", ...}`; PUT simpan. `/api/health` GET = dipakai polling (Cek bentuk body-nya di server.py:145 — anggap "up" = respons 2xx).
- Cache-buster invarian (tests/i18n.test.js ~307–315): `app.js?v` == `i18n.js?v` == `window.I18N_VER`. Karena kamu ubah app.js + i18n.js, **bump ketiganya serentak** ke tanggal baru (mis. `20260929`).

## Cakupan
- `index.html`: kartu/button "Restart aigate" di settings, ber-penanda dev-only; `aria-label` + `data-i18n-aria`.
- `app.js`: handler tombol → `confirm()` (pesan data-i18n) → `fetch POST /api/dev/restart` → tampilkan status "Restarting…" → `setInterval` poll `GET /api/health` tiap 500ms (timeout ~30x) → begitu ok → `location.reload()`. Tangani 403 (jarang, karena tombol hidden saat off) → tampilkan pesan error. Pastikan tombol disembunyikan saat `applyDevMode(false)`.
- `i18n/*`: 8 kamus tambah `settings.dev_restart` (label tombol), `settings.dev_restart_confirm` (teks konfirm), `settings.restarting` (status). `en`+`id` diterjemahkan benar; 6 lain mirror EN. Cek `node .opencode/tools/tests/i18n-parity-check.mjs`.
- `tests/chat.test.js`? TIDAK — tambah `tests/restart.test.js` (atau sesuaikan) yang mengecek: (a) tombol tersembunyi saat dev_mode false, tampil saat true; (b) klik → fetch POST dipanggil, health ok → `location.reload` dipanggil (mock `fetch` + `location.reload`). Jangan benar-benar restart apa pun.

## Aturan keras
- Vanilla JS, SPA, TANPA framework/CDN (R13). Product name `aigate` kecil.
- Aksesibilitas: tombol punya label, konfirmasi lewat dialog standar, status `aria-live`.
- JANGAN ubah backend, JANGAN ubah `window.I18N_VER` tanpa menyesuaikan 2 token cache-buster lainnya.
- `git diff --check` bersih.

## Definition-of-done
- `node ./node_modules/vitest/vitest.mjs run` HIJAU termasuk parity + cache-buster + test baru (nol regresi).
- Cache-buster 3 token konsisten & baru.
- Tombol terbukti HANYA muncul saat dev mode ON (cek views/visibility test).
- Alur simulasi: klik → confirm → POST → status → poll → reload (dibuktikan via mock, tanpa restart nyata).
- Receipt: file berubah, token cache-buster akhir, hasil vitest, open question (jika ada). JANGAN commit/push.

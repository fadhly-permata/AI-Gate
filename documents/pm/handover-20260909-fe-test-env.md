# Handover — Task #3: perbaiki environment tes Frontend (suite merah) — 2026-09-09

**Owner:** `fe-dev` (yang boleh ditulis = `src/frontend/**`: `vitest.config.js`, `tests/helpers/**`, `package.json`/`package-lock.json`).
**Status asal:** temuan PM di sesi bottom-nav ponsel; sudah dibuktikan BUKAN regresi UI.

## Gejala
Suite FE penuh: **22 tes gagal** — cuma di `tests/logwindow.test.js` + `tests/terminal_discard.test.js`,
semua error `window.localStorage` / `window.sessionStorage` **undefined**
(`localStorage.clear()` → "Cannot read properties of undefined (reading 'clear')", dsb).
- Gagal **walau file itu dijalankan sendirian** (`vitest run tests/logwindow.test.js`) → bukan bocoran lintas-file.
- File lain yang PAKAI storage (`settings`, `terminal_toolbar`, `i18n`) **lolos**.
- Baseline lama "484 passed" terjadi SEBELUM `node_modules` FE kehapus; di-reinstall `npm ci`
  → **vitest 2.1.9 + jsdom 25.0.1** (`package.json`: `vitest ^2.1.0`, `jsdom ^25.0.0`).

## Cara repro (workdir `src/frontend`)
```
node node_modules/.bin/vitest run tests/logwindow.test.js
```
Pakai `node node_modules/.bin/vitest` (BUKAN `npx` — shebang `npx` rusak di Termux, R37).
Catatan: `esbuild` postinstall bisa diblok npm `allowScripts` (tidak terkait storage).

## Hipotesis (uji empiris; pilih fix minimal & tahan-lama)
1. **Paling mungkin:** environment jsdom pada vitest 2.x tidak menyetel origin → `window.localStorage`
   tidak dibuat. FIX: tambah ke `vitest.config.js`:
   ```
   environmentOptions: { jsdom: { url: "http://localhost:3000/" } }
   ```
   (PM sudah probe: jsdom 25.0.1 MENYEDIAKAN `localStorage` kalau url = origin.)
2. Helper `tests/helpers/dom.js` / `quiet.js` (setupFiles, `isolate:false`) mungkin mengganggu; tapi
   kegagalan "sendirian" menjauhkan hipotesis ini. Kalau #1 belum cukup, baru selidiki sini.
3. Alternatif: naikkan/turunkan versi vitest/jsdom ke pasangan yang terbukti hijau (ubah `package.json`
   + reinstall + `package-lock.json`). Pakai ini HANYA kalau #1/#2 gagal — utamakan fix config kecil.

## Batasan
- Tulis HANYA di `src/frontend/**`. DILARANG menghapus / men-skip / melonggarkan tes apa pun.
- DILARANG mengubah kode produksi (`src/frontend/static/**`) — ini urusan harness tes.
- `npm install`/`ci` di `src/frontend` boleh (gitignored). Jangan `kill`/restart proses (R32).
- Pertahankan tuning kecepatan `isolate:false` + `maxForks:2` KECUALI fix benar-benar menentangnya.

## Definition of done
- Suite FE PENUH hijau sekali: `node node_modules/.bin/vitest run` → ~486 pass, **0 fail** (gate R35).
- `logwindow.test.js` + `terminal_discard.test.js` hijau; semua tes storage tetap utuh.
- Fix minimal + alasannya ditulis di receipt; kalau deps berubah, `package.json`+`package-lock` ikut diperbarui.

## RESOLVED (fe-dev; PM re-verif) — 2026-09-09
Akar masalah BUKAN `npm ci`/versi-jsdom dan BUKAN origin-url (hipotesis #1 di atas **GUGUR** —
vitest 2.1.9 sudah default jsdom url `http://localhost:3000`, jadi `environmentOptions.jsdom.url` = no-op).
Penyebab asli: **Node v26.4.0** (≥22.4) punya global `globalThis.localStorage`/`sessionStorage` (webstorage)
sendiri; getter-nya balikin `undefined` tanpa `--localstorage-file`. Vitest cuman nyalin properti window jsdom
ke global KALAU namanya belum ada di global / masuk KEYS allow-list — `localStorage` gak masuk → tes lihat stub Node.
`sessionStorage` Node kebetulan jalan → makanya pas 22 yang kena (pemakai localStorage).

FIX: `tests/helpers/jsdom-storage.js` (setupFile PERTAMA) re-point `globalThis.localStorage`/`sessionStorage`
ke storage window jsdom (delegating getter, `configurable:true`, no-op kalau `globalThis.jsdom` absen) +
`vitest.config.js` setupFiles prepend (+ komentar). Nol tes dihapus/dilemahkan; nol kode produksi; `package.json`
gak berubah. `settings.test.js` tadinya ikut gagal pas jalan sendiri (ke-mask urutan file `isolate:false`) — ikut kelar.
GATE PM: `node node_modules/.bin/vitest run` → **23 file / 523 tes PASS, 0 fail**.
Commit `95d46e4` di branch `fix/fe-test-env`; **PR #15** `fix/fe-test-env -> main` terbuka:
https://github.com/fadhly-permata/AI-Gate/pull/15. CAVEAT: ngandelin `globalThis.jsdom` (semi-dokumentasi, dijaga) —
re-run gate tiap Node/vitest/isolate berubah.

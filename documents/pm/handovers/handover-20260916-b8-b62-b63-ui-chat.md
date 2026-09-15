# Handover — B8.B6.2 + B6.3 UI Chat Playground (fe-dev)

Tanggal: 2026-09-16 | Owner: **fe-dev** | PM: ProjectManager
Satu sesi untuk dua task backlog: **B6.2** (halaman Chat inti) + **B6.3** (polish: system prompt, temperature, rename, stop-generation, i18n, responsif). Backend (B6.1) SUDAH selesai & di-commit — kontrak di bawah resmi.

## Spesifikasi
`documents/PRD.md` §2.9 + `documents/analysis/ERD.md` (ChatSession/ChatMessage). Backend = `src/backend/chat_router.py` (jangan diubah; baca saja untuk kontrak).

## Kontrak backend (dari receipt be-dev — pakai PERSIS ini)
```
GET    /api/chat/sessions            -> {"object":"list","data":[{id,title,model,provider_id,combo_id,updated_at}]}  (updated_at desc)
POST   /api/chat/sessions            body {title?, provider_id?, combo_id?, model?, system_prompt?, temperature?} -> full session
GET    /api/chat/sessions/{id}       -> session + {"messages":[{id,role,content,tokens_in,tokens_out,created_at}]}  (asc kronologis)
PUT    /api/chat/sessions/{id}       body {title?, system_prompt?, temperature?} -> full session
DELETE /api/chat/sessions/{id}       -> {"object":"chat.session.deleted","id":..,"deleted":true}  (cascade)
POST   /api/chat/sessions/{id}/complete  body {content}  -> SSE text/event-stream (delta OpenAI)
```
- **Model ref**: `session.model` = string `provider:<namaProvider>:<modelId>` ATAU `combo:<namaCombo>`. SEBELUM finalisasi picker, **verifikasi format persis** di `src/backend/gateway/resolver.py` (`resolve_target`) — jangan tebak; format salah = complete gagal.
- Setelah kirim `/complete` (SSE), FE WAJIB `GET /api/chat/sessions/{id}` ulang untuk ambil pesan assistant yang sudah tersimpan di DB (stream meneruskan byte SSE verbatim, tak memuat id assistant).
- `tokens_in/out` bisa `null` (usage tak tersedia) → tampil sebagai "—"/unknown, JANGAN tampilkan 0.
- Endpoint untuk picker: `GET /api/providers` + `GET /api/combos` (list tersedia).

## Cara integrasi ke SPA (pola nyata app)
- Tambah `<section class="view" data-view="chat">` (contoh pola: section `data-view="usage"` / `combos`).
- Tambah entri nav: `<a class="nav-item" data-view="chat" ...>` di sidebar (dekat baris nav lain ~117–158) DAN `<a class="bn-item" data-view="chat" ...>` di `.bottom-nav` (~1446+) supaya bisa diakses mobile. `showView(name)` app.js:336 sudah generik (cari `.view[data-view=...]`), jadi view baru otomatis jalan; cukup daftarkan item nav + handler klik mengikuti pola `.nav-item` yang ada.
- Layout: sidebar daftar sesi (buat/pilih/nama/hapus) + panel thread pesan + composer + picker provider/model/combo.

## Aturan keras (jangan dilanggar — ini yang bikin tes gagal kalau luput)
1. **Vanilla JS, satu-file SPA, TANPA framework, TANPA CDN** (R13 + vendor lokal). Aset ikon lokal.
2. **Cache-buster invarian** (`src/frontend/tests/i18n.test.js` ~307–315): `app.js?v` == `i18n.js?v` == `window.I18N_VER`. Kalau kamu ubah app.js/i18n.js, **bump KETIGANYA serentak** ke tanggal baru (mis. `20260927`→`20260928`). Ubah styles.css saja → bump `styles.css?v` saja (tak terikat invarian).
3. **i18n parity**: setiap kunci baru WAJIB ada di SEMUA 8 kamus (`i18n/en.js,id.js,ru.js,nl.js,ja.js,zh.js,zh-tw.js,hi.js`). en/id diterjemahkan benar; 6 sisanya boleh mirror EN (utang review penutur asli SUDANG DICABUT user — tak perlu reviewer). Cek dengan `node .opencode/tools/tests/i18n-parity-check.mjs`.
4. **views.test.js pin `.bn-item` = 10** (mobile nav). Menambah `bn-item` chat → ubah ke 11 di test itu (mekanis, jangan hapus penjaga lain).
5. Aksesibilitas: nav baru perlu `aria-label` + `data-i18n-aria` (pola item lain); dialog rename/penghapusan pakai pola modal `.modal-overlay/.modal` + focus-trap + ESC + restore fokus (sudah ada di app, reuse).

## Cakupan B6.2 (inti)
- Halaman Chat: render daftar sesi (GET list), buat sesi baru (POST), pilih sesi (GET {id} → tampilkan messages), composer kirim pesan (simpan user lalu POST /complete, render SSE streaming ke bubble assistant bertahap), hapus sesi (DELETE + konfirmasi).
- Picker target: pilih provider+model ATAU combo → isi `model` ref yang benar ke sesi.
- Render pesan: user/assistant/system, markdown-ringan/whitespace terjaga, auto-scroll, kosong-state.

## Cakupan B6.3 (polish)
- Kontrol per sesi: `system_prompt` + `temperature` (input di panel sesi, simpan via PUT).
- Rename sesi (PUT title).
- **Stop-generation**: tombol Stop → `AbortController` batalkan fetch SSE; simpan sebagian? — cukup hentikan render (DB sudah simpan assistant saat stream selesai; bila dibatalkan sebelum selesai, asisten tak tersimpan — itu diterima).
- Responsif/mobile: dua kolom → kolom tunggal di layar sempit (pakai pola `@media` + `body[data-device]` yang sudah ada); bottom-nav tetap proporsional; NOL overflow horizontal.
- i18n: semua teks UI lewat kunci (lihat aturan 3).

## Batas berkas (STRICT)
- WRITE: `src/frontend/static/index.html`, `src/frontend/static/app.js`, `src/frontend/static/styles.css`, `src/frontend/static/i18n/*.js` (8 kamus), `src/frontend/tests/*.test.js` (perbarui penjaga: views.test.js bn-item, tambah chat.test.js bila perlu).
- READ: `src/backend/chat_router.py` + `gateway/resolver.py` (kontrak), `documents/pm/**`, `documents/PRD.md`, `documents/analysis/ERD.md`.
- DILARANG: ubah `src/backend/**`, tambah dependensi/CDN, tulis `documents/pm/**` (milik PM), kill/restart server (J6).

## Definition of done
- `node ./node_modules/vitest/vitest.mjs run` (suite FE) **HIJAU** termasuk penjaga i18n parity + cache-buster + views.test.js (yang kamu update), **nol regresi**.
- `git diff --check` bersih.
- Cache-buster di-bump benar (kalau app.js/i18n.js disentuh, ketiga token sama & baru).
- Alur inti terbukti: buat sesi → pilih target → kirim → respons streaming muncul → refresh halaman → riwayat masih ada (sesi+pesan tersimpan di DB).
- **G3**: jalankan app nyata (instance TERISOLASI: port own + `AIGATE_DB_PATH` tmp di luar repo, JANGAN sentuh `:8080` user; kill HANYA PID sendiri) dan ukur before/after di beberapa lebar viewport (desktop/tablet/phone). Kalau butuh provider sungguhan untuk complete, mock/pakai provider apa pun yang sudah ada; laporkan jujur apa yang bisa & tak bisa dibuktikan headless.

## Receipt yang diminta
File berubah + alasan; daftar kunci i18n baru (× 8 kamus); token cache-buster akhir; hasil vitest (jumlah pass) + `git diff --check`; hasil exercise headless (viewport mana yang diuji, apa yang terbukti, keterbatasan); open question. JANGAN commit/push (PM merge).

# Bug Tracker — aigate

Auto-filled by PM via `/log-bug`. Severity & status assigned automatically;
user only supplies the title (and optional detail). ID = BUG-<yyymmdd>-<n>.

| ID | Date | Title | Severity | Status | Reporter |
|----|------|-------|----------|--------|----------|
| BUG-260903-1 | 2026-09-03 | Provider: tak ada pilihan model & tombol test koneksi | medium | fixed (verified) | user |
| BUG-260903-2 | 2026-09-03 | CLI Tools view kosong — perlu diisi | medium | fixed (verified) | user |
| BUG-260903-3 | 2026-09-03 | User temukan error di log aplikasi — perlu investigasi | medium | fixed (verified) | user |
| BUG-260903-4 | 2026-09-03 | Provider save/list 500 — kolom default_model gak ke-migrasi | medium | fixed (verified) | user |
| BUG-260916-1 | 2026-09-16 | Halaman chat berantakan + usulan perapihan UI (acuan Gemini) | low | fixed (full redesign landed; awaiting G3 browser verify) | user |

---

## BUG-260903-1
- **Title:** Provider: tak ada pilihan model & tombol test koneksi
- **Severity:** medium (UX/usability gap — tidak ada crash/blocker)
- **Status:** open
- **Reporter:** user
- **Date:** 2026-09-03
- **Detail (user):** "Dimana gua bisa nentuin model yang mau dipake? dan setiap
  buat provider gak ada tombol test ya? user gak tau dong settingan dia udah
  bener atau belum."
- **Reproduction:** Buka halaman Providers -> Add/Edit provider. Tidak ada field
  untuk memilih model default, dan tidak ada tombol "Test Connection" untuk
  verifikasi konfigurasi (api_key / base_url) sebelum disimpan.
- **Expected:** User bisa menentukan model yang dipakai per provider, dan punya
  tombol test untuk memastikan setting sudah benar.
- **Actual:** Tidak ada pilihan model maupun tombol test di form provider.
- **Environment:** aigate UI (http://localhost:8080/), evaluasi pengguna.

## BUG-260903-2
- **Title:** CLI Tools view kosong — perlu diisi
- **Severity:** medium (fungsional gap — halaman tampil tapi kosong)
- **Status:** open
- **Reporter:** user
- **Date:** 2026-09-03
- **Detail (user):** "Cli tools kenapa kosong? tambahin dong."
- **Reproduction:** Buka menu CLI Tools -> tampilan kosong / tidak ada daftar tool.
- **Expected:** CLI Tools menampilkan daftar tool (preset grup A/B/C) yang bisa
  di-launch.
- **Actual:** View CLI Tools kosong.
- **Environment:** aigate UI (http://localhost:8080/), evaluasi pengguna.

## BUG-260903-3
- **Title:** User temukan error di log aplikasi — perlu investigasi
- **Severity:** medium (user melaporkan "error" di log; belum dikonfirmasi
  apakah crash/blocker — PM akan naikkan ke high bila terbukti blocking)
- **Status:** open
- **Reporter:** user
- **Date:** 2026-09-03
- **Detail (user):** "lu udah bisa cek log? udah ada nemu error tuh gua"
- **Reproduction:** Periksa `/api/logs` (severity=error/warning) saat aplikasi
  berjalan.
- **Expected:** Log bersih dari error yang belum tertangani.
- **Actual:** User melaporkan ada error di log (perlu PM cek & triage).
- **Environment:** aigate runtime (server jalan di port 8080).

## BUG-260903-4
- **Title:** Provider save/list 500 — kolom default_model gak ke-migrasi
- **Severity:** medium (blocker fitur Provider di DB lama)
- **Status:** fixed (verified)
- **Reporter:** user
- **Date:** 2026-09-03
- **Detail (user):** "kenapa gua gak bisa save provider baru? dan http 500 di halaman
  provider itu buat apa ya?"
- **Root cause:** `default_model` ditambah ke model `Provider`, tapi `create_all`
  TIDAK menambah kolom ke tabel `providers` yang sudah ada -> `GET/POST /api/providers`
  -> `OperationalError: no such column: providers.default_model` -> HTTP 500. (500
  bukan fitur, tapi symptom bug ini.)
- **Fix:** (1) PM langsung `ALTER TABLE providers ADD COLUMN default_model TEXT` ke DB
  lama -> server langsung bisa save (verified GET 200 / POST 201). (2) be-dev tambah
  migrasi idempoten di `init_db()` (`_ensure_provider_default_model_column`) yg jalan
  tiap startup -> self-heal kalau DB belum punya kolom. Backend **117 passed, 1 skipped**.
- **Verifikasi:** GET/POST /api/providers 200/201; test row dihapus. Tidak perlu restart
  server (DB sudah dimigrasi; kode migrasi siap kalau nanti restart).

## BUG-260916-1
- **Title:** Halaman chat desainnya berantakan + usulan perapihan UI (acuan Gemini)
- **Severity:** low — AUTO. Klasifikasi: kosmetis/UX (tata letak "berantakan", relokasi
  kontrol, preferensi tampilan). Tidak ada indikasi crash / blocker / data-loss sehingga
  tidak naik ke high. Catatan PM: poin "model bisa switch langsung" adalah gap fungsional
  kecil (parity dengan BUG-260903-1 yang sudah fixed di sisi provider) — tetap low karena
  chat tetap bisa dipakai.
- **Status:** fixed (code landed; awaiting G3 real-browser verify per rule G3)
- **Reporter:** user
- **Date:** 2026-09-16
- **Detail (user):** "halaman chat desainnya berantakan banget. trus system prompt dan
  temperatur mending ditaro di popjp dialog aja, biar lebih ringkas. model kalo bisa dibuat
  bisa switch langsung, title di buat otomatis aja, panel daftar session dibuat bisa
  expand/collapse. pake acuan kaya ini https://gemini.google.com/app"
- **Poin-poin user (5):**
  1. Tata letak halaman chat berantakan → perlu perapihan visual.
  2. System prompt & temperature → pindah ke popup dialog (lebih ringkas).
  3. Model → bisa switch langsung dari halaman chat.
  4. Title chat → dibuat otomatis.
  5. Panel daftar session → bisa expand/collapse.
  - Acuan desain: https://gemini.google.com/app
- **Reproduction:** Buka halaman Chat di aigate (http://localhost:8080/). Perhatikan layout,
  letak kontrol system prompt/temperature, cara ganti model, pembuatan title, dan panel
  daftar session. Bandingkan dengan referensi Gemini.
- **Expected:** Halaman chat rapi dan ringkas ala Gemini: kontrol lanjutan (system prompt,
  temperature) tersembunyi di popup dialog, model bisa diganti langsung, title terbentuk
  otomatis, panel session bisa expand/collapse.
- **Actual:** Layout berantakan; system prompt & temperature tampil di area utama (tidak
  ringkas); model tidak bisa switch langsung; title tidak otomatis; panel session tanpa
  expand/collapse.
- **Environment:** aigate UI (http://localhost:8080/), evaluasi visual pengguna.
- **Resolusi (2026-09-16):** Kerja frontend (fe-dev) + 1 baris backend (be-dev).
  - fe-dev: layout chat dirapikan; `#chatSettings` (system prompt + temperature) dipindah ke
    modal dialog (tombol gear di `.chat-bar-actions`); switcher model in-chat pakai
    `window.aigate.createCombobox` (PUT `{model}`); auto-title dari pesan pertama (flag
    `titleAuto`, manual rename mematikan auto); sidebar session collapsible + localStorage.
  - be-dev: `SessionUpdate` (`src/backend/chat_router.py:88`) ditambah `model:
    Optional[str] = None` — sebelumnya PUT `{model}` diam-diam di-drop (Extra.ignore), jadi
    pergantian model gak ke-simpan pas reload.
  - Bukti tes: FE vitest 750/750 (chat 35/35, +13 tes baru); BE pytest chat `14 passed`;
    `node --check` bersih; cache-buster `app.js`/`styles.css`/`i18n.js`/`V` = `20260930`.
  - BELUM di-commit (hak user). G3: perlu lu buka browser & uji nyata (model switch reload,
    auto-title, collapse).
- **Resolusi ronde-2 (2026-09-16, FULL REDESIGN):** user tetap menolak ("semuanya gak suka
  gua, redesign aja"). Ronda-1 cuma relokasi kontrol → layout gak berubah. fe-dev bongkar
  total view chat (bukan geser control): `.chat-layout#chatLayout` = rail `.chat-rail`
  (230px→56px collapse) + kolom baca terpusat (~820px) `.chat-main`; banner+chrome card
  DIHAPUS; pesan assistant = teks polos (line-height 1.6), user = bubble lembut
  `--chat-user-bg` (#f1f3f4); composer = satu permukaan membulat radius 24px; model pill +
  gear ghost di bar; settings modal + Cancel. ID lama dipertahankan (35+ ditest). CSS chat
  section diganti penuh; token `--chat-user-bg` baru (light+dark); responsive cuma nest di
  blok @media EKSISTING (jumlah blok real 960px tetap 1). app.js: `autoGrowComposer`,
  empty-state, `#chatSettingsCancel`. Cache-buster → **20261001**.
    - Gerbang PM (re-run): vitest **757 passed** (chat 42, views 30, i18n 36 — 0 regresi);
    `node --check` bersih; cache-buster lockstep 20261001; **server live serve markup baru**
    (curl: chatLayout/chat-rail/chat-composer-wrap + app.js?v=20261001) → UI TIDAK butuh
    restart, cukup hard-refresh browser.
  - TAHAN commit. G3: user hard-refresh & nilai visual (gw gak bisa render — Playwright
    unsupported di Android/Termux).
- **Resolusi ronde-3 (2026-09-16, New-chat flow ala Gemini):** user protes "New chat masih
  pake dialog title + pilih model". PM cek kontrak backend: `create_session` boleh tanpa
  model; `complete` balas 400 `no_model` kalau `chat.model` kosong (user msg tetep kesimpan)
  → arah: hapus `#chatNewModal` + prompt judul, `#chatNewBtn` = draft baru langsung, model
  switcher `#chatModelSwitch` dipindah dari bar ke `.chat-composer-model` (deket kotak
  ketik), kirim-pertama = create session + set model + auto-title, tanpa model = inline
  hint `chat.model_required` (bukan modal). Spawn pertama kepotong (HTML modal dihapus tapi
  app.js masih `openNewChatModal`→`setChatNewMsg` undefined, 3 tes fail) → PM TIDAK nyerahin
  "selesai", spawn resume fe-dev dgn bukti baris → bersih. Cache-buster → 20261002.
  - Gerbang PM (re-run): vitest **757 passed** (chat 42, 0 regresi), `node --check` bersih,
    grep sisa-modal di app.js = 0, curl live server = tanpa chatNewModal + ada
    chat-composer-model → cukup hard-refresh (UI, gak perlu restart).
  - TAHAN commit. G3: user hard-refresh & coba New chat (langsung ngetik + model inline).

# Bug Tracker — aigate

Auto-filled by PM via `/log-bug`. Severity & status assigned automatically;
user only supplies the title (and optional detail). ID = BUG-<yyymmdd>-<n>.

| ID | Date | Title | Severity | Status | Reporter |
|----|------|-------|----------|--------|----------|
| BUG-260903-1 | 2026-09-03 | Provider: tak ada pilihan model & tombol test koneksi | medium | fixed (verified) | user |
| BUG-260903-2 | 2026-09-03 | CLI Tools view kosong — perlu diisi | medium | fixed (verified) | user |
| BUG-260903-3 | 2026-09-03 | User temukan error di log aplikasi — perlu investigasi | medium | fixed (verified) | user |
| BUG-260903-4 | 2026-09-03 | Provider save/list 500 — kolom default_model gak ke-migrasi | medium | fixed (verified) | user |

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

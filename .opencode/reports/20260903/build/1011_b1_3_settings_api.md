# Laporan Tugas: B1.3 — Settings UI Backend API (/api/settings)

## Informasi Dasar
- Tanggal: 2026-09-03
- Jenis Tugas: build (backend API)
- Waktu Mulai: 10:11

## Permintaan Pengguna
Buat backend API untuk task B1.3 (Settings UI): endpoint HTTP baca/tulis config
`Setting` (port, dev_mode, theme, locale, dst) agar panel frontend bisa persist.
Repo `config/settings.py` sudah ada; hanya tambah endpoint.

## Rencana Pekerjaan
1. Buat `src/backend/config/settings_router.py` (APIRouter Pydantic v1) dengan
   GET /api/settings, PUT /api/settings (single + bulk), GET /api/settings/{key}.
2. Daftarkan router di `server.py` (mount /api).
3. Tulis `tests/backend/test_settings_api.py` (in-memory SQLite hermetik + TestClient).
4. Pastikan import app bersih & log error ke LogEntry (R12).

## Realisasi Pekerjaan
- 10:11 buat settings_router.py (Pydantic v1 BaseModel `SettingUpdate`, dukung
  single {key,value} dan bulk {settings:{...}}, koersi scalar->str).
- 10:11 wiring di server.py (include_router(settings_router)).
- 10:11 tulis test_settings_api.py (5 test, StaticPool agar :memory: share koneksi).
- 10:11 temukan bug di settings.py: `log_error_exc("...%r", key, source=...)` ->
  `key` ke-bond ke param `source` (TypeError, melanggar R12). Diperbaiki jadi
  f-string + tambah `logger.error(..., exc_info=True)` di 4 except block agar
  error selalu tercatat (stdlib + LogEntry).
- 10:11 `import backend.server` bersih; 3 route terdaftar.
- 10:11 pytest: 5/5 test settings API lulus; test_settings_repo 7/7 lulus; total
  backend 41 passed (3 failure gateway sisa = pre-existing B2.x, bukan dari task ini).

## Status Akhir
Berhasil — GET/PUT /api/settings jalan & baca/tulis tabel Setting; Pydantic v1;
error di-log ke LogEntry. Tests lulus di environment dengan dep terpasang.

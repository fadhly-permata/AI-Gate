# Handover — DEV-RESTART backend: endpoint self-restart (be-dev)

Tanggal: 2026-09-16 | Owner: **be-dev** | PM: ProjectManager
Fitur baru (permintaan user): tombol "Restart" di Settings, HANYA tampil saat Developer Mode ON. FE (fe-dev) menyusul; kamu bikin kontrak + mekanismenya.

## Keputusan desain PM (sudah dikunci, jangan diubah)
**Self-restart in-process via `os.execv`** — BUKAN wrapper/supervisor. Alasannya: paling mudah buat user (cara nyalain `python run.py` nggak berubah) + nol dependensi.

## Fakta kode terverifikasi PM
- Server dijalankan DALAM SATU PROSES: `run.py` (`__main__` → `ensure_deps()` → `backend.launcher.main()`) dan `launcher.py` memanggil `uvicorn.run(app, ...)` **in-process**. Jadi proses yang melayani request = proses `python run.py` itu sendiri → `os.execv` pada proses ini = restart penuh (ulangi `run.py`, auto-pip idempoten, kode baru ke-load).
- Cara rekonstruksi perintah: `[sys.executable, *sys.argv]`. `sys.argv[0]` bisa relatif (`run.py`) — **RESOLVE ke path absolut** (cwd saat eksekusi = folder proyek, tapi aman-nya pakai `run.py` absolut; ambil dari lokasi modul launcher/`HERE`). Pertahankan argumen tambahan user (`--port` dll.) lewat `sys.argv[1:]`.
- Health endpoint SUDAH ADA: `GET /api/health` (`server.py:142`) → FE akan polling ini utk tahu server udah balik. Kamu TIDAK perlu bikin; cukup pastikan tak berubah.
- Developer mode disimpan sebagai Setting key **`dev_mode`** (default `"false"`, lihat `src/backend/config/settings.py:35`; dibaca/dipersist `settings_router`). Gate endpoint dengan membaca setting ini DI SERVER (bukan cuma UI) → kalau bukan `"true"` → **403**.

## Kontrak yang harus dibuat
`POST /api/dev/restart` (file baru `src/backend/admin_router.py`):
1. Baca Setting `dev_mode`. Kalau BUKAN `"true"` → kembalikan `JSONResponse(403, {"error":{"message":"developer mode is off","type":"invalid_request_error","code":"dev_mode_required"}})` dan **JANGAN** restart.
2. Kalau ON:
   - Susun `argv = [sys.executable, <absolut run.py>, *sys.argv[1:]]`.
   - Kembalikan **dulu** `JSONResponse(200, {"status":"restarting"})` supaya klien menerima respons SEBELUM proses diganti.
   - Jadwalkan restart SETELAH respons terkirim: `threading.Timer(0.6, _do_restart)` dengan `daemon=True`, di mana `_do_restart` memanggil `os.execv(argv[0], argv)`. (Timer daemon agar request bisa selesai & socket sempat flush; execv mengganti image proses → restart penuh.)
   - Guard: kalau sudah dijadwalkan, jangan jadwal ganda.
   - (Opsional) tulis `LogEntry` "aigate restart requested (dev mode)" buat jejak — jangan bikin start-up crash kalau log gagal.
3. Kalau `os.execv` gagal (jarang), raise/log jelas (jangan silent).

## Cara daftar
- `server.py`: `from backend.admin_router import router as admin_router` + `app.include_router(admin_router)`.

## Test (`tests/backend/test_admin_restart.py`)
- **WAJIB MOCK `os.execv`** (mis. `monkeypatch.setattr("os.execv", spy)`) — JANGAN benar-benar restart apa pun (J6 + jangan bunuh proses tes).
- **Pakai `httpx.ASGITransport(app=app)`, BUKAN `TestClient`** — di lingkungan ini `TestClient` starlette 0.27 rusak dgn httpx 0.28 (TypeError) → pola ini sudah dipakai di `test_chat_router.py`; ikut gaya itu.
- DB terisolasi: `AIGATE_DB_PATH` ke file tmp. Set `dev_mode` lewat API/store untuk test.
- Cover: (a) dev_mode OFF → 403 & execv TIDAK dijadwalkan; (b) dev_mode ON → 200 `{"status":"restarting"}` & timer/execv dijadwalkan (assert argv diawali `sys.executable` + memuat `run.py` absolut); (c) guard anti-jadwal-ganda.
- Set `Timer` interval bisa di-mock/diperpendek agar tes tak nunggu; assert execv dipanggil lewat timer yang kamu picu manual di test.
- Jalankan `python -m pytest tests/backend/test_admin_restart.py -q` → hijau; lalu suite penuh `python -m pytest tests/backend -q` → pastikan **nol regresi baru** vs baseline (lingkungan ini sudah merah ~235 sejak awal karena TestClient; yang penting jumlah fail/error tidak bertambah & tes barumu lolos).

## Batas berkas (STRICT)
- WRITE: `src/backend/admin_router.py` (baru), `src/backend/server.py` (mount), `tests/backend/test_admin_restart.py` (baru). Kalau perlu helper kecil, di file itu juga.
- READ: `src/backend/**` (khususnya `config/settings*`, `server.py`, `launcher.py`, `run.py`), `documents/pm/**`.
- DILARANG: ubah frontend, ubah kontrak `/api/health`/`/v1/*`, tambah dependensi, **benar-benar memanggil execv/restart di tes atau di lingkungan ini**, kill/restart server user (`:8080`). JANGAN commit/push.

## Receipt
File berubah + alasan; kontrak akhir (path + skema 200/403 + perilaku Timer/execv); hasil pytest (baru + delta baseline); open question (mis. cara FE polling/UX reload — serahkan ke fe-dev). Laporkan juga keputusan soal resolusi path `run.py`.

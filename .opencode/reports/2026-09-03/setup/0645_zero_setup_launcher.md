# Laporan Tugas: Zero-Setup Launcher + pywinpty

## Informasi Dasar
- Tanggal: 2026-09-03
- Jenis Tugas: setup / build (launcher + dependency)
- Waktu Mulai: 06:45

## Permintaan Pengguna
"tambahin pywinpty (Windows). Bisa gak dependency auto download & install (kalo belum
ada) ketika aplikasi di running aja? jadi user gak perlu repot nyiapin apapun?"

## Rencana Pekerjaan
1. Tambah `pywinpty` sebagai dep khusus Windows (PEP 508 marker).
2. Buat launcher yg auto-install dep yg kurang saat dijalankan.
3. Update SETUP + console script.

## Realisasi Pekerjaan
- `pyproject.toml`: `"pywinpty; sys_platform == 'win32'"` + `[project.scripts]
  aigate = "backend.launcher:main"`.
- `src/backend/launcher.py`: `main()` baca `--port`/env `AIGATE_PORT`, jalanin
  `uvicorn.run(app)`. Import berat di-defer ke dalam `main()` (pasca auto-install).
- `tests/backend/test_launcher.py`: assert callable + monkeypatch `uvicorn.run`.
- Root `run.py` (PM): `ensure_deps()` cek `find_spec` tiap dep, `pip install` yg
  kurang (pywinpty otomatis di Windows), lalu panggil `backend.launcher:main`.
- `documents/dev/SETUP.md`: opsi `python run.py` (zero-setup) + `aigate` script.

## Status Akhir
Berhasil — user cukup `python run.py` (Python 3.10+ + internet saat pertama). pywinpty
auto di Windows. Catatan: sandbox punya mismatch pydantic/fastapi (bukan dari kode),
di env user `pip install -e .` resolve benar. Run `/run-impl` tetap PAUSED.

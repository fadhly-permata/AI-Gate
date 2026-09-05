# Dev Environment & Coding Standards — aigate

## Prerequisites
- Python 3.10+
- `uv` atau `pip` + `venv`

## Install & run
```
# Zero-setup (cukup punya Python; dependency otomatis ter-install saat pertama jalan):
python run.py                 # buka http://localhost:8080
AIGATE_DEV=1 python run.py   # mode developer (Log Window, simulasi perangkat, Self-Heal)
# pywinpty otomatis di-install di Windows; ptyprocess di POSIX/Termux.

# Atau, install dulu lalu jalankan via uvicorn / console script:
uv venv && uv pip install -e .
uv run uvicorn backend.server:app --host 0.0.0.0 --port "${AIGATE_PORT:-8080}"
# Mode developer:
AIGATE_DEV=1 uv run uvicorn backend.server:app --port "${AIGATE_PORT:-8080}"
# Setelah `pip install -e .` juga tersedia perintah `aigate` (console script).
# Tidak perlu deployment/container: aigate jalan native sebagai app Python.
```
UI (web lokal) otomatis serves static + xterm.js lewat server yang sama.
Jalankan native — tidak ada langkah deploy/container (lihat TSD ADR-009).

## Struktur repo
```
src/backend/      # gateway, routing, provider adapter, proxy
src/frontend/     # UI (jika native) atau static xterm.js
documents/        # semua dokumen spesifikasi (PRD, BRD, FSD, ERD, TSD, plan, api, qa, dev, ux, config)
pm/               # memory bank & status PM
tests/            # test (unit/integration/e2e)
```

## Standards
- Bahasa: Python, type hints wajib.
- Format: `ruff format`, lint `ruff check`.
- Konvensi commit: Conventional Commits.
- Branch: `feat/`, `fix/`, `chore/`; PR wajib CI hijau + 1 review.
- Module boundary: be-dev tulis `src/backend/**`, fe-dev `src/frontend/**`,
  jangan campur (lihat agent-boundaries).

## Secrets & Config (ADR-007 + ADR-010)
- Secret (API key, internal key, proxy password) disimpan **plaintext di SQLite DB**
  (kolom `api_key` / `internal_api_key` / `password`), **tanpa enkripsi**. UI tidak
  me-redaksi nilai.
- SELURUH konfigurasi aplikasi (port default, mode, toggle fitur, preset CLI)
  disimpan di tabel `Setting` (SQLite) — **bukan file terpisah** (ADR-010). File
  `.env` tidak lagi jadi sumber kebenaran.
- Jangan commit file `.env` maupun DB lokal (`~/.aigate/*.db`) — keduanya sudah di
  `.gitignore`.
- Log operasional disimpan di tabel `LogEntry` (ADR-011); di mode developer bisa
  dilihat via Log Window / `GET /api/logs`.

## Proxy binding (ADR-008)
- Proxy diikat di level **Endpoint**; Endpoint menunjuk ke **Combo**.
- Implementasi ikuti `documents/api/OPENAI_COMPATIBLE_CONTRACT.md`.



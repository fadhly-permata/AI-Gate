# Dev Environment & Coding Standards — aigate

## Prerequisites
- Python 3.10+
- `uv` atau `pip` + `venv`

## Install & run
```
uv venv && uv pip install -e .
uv run uvicorn aigate.server:app --host 0.0.0.0 --port 8080
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

## Secrets (ADR-007)
- API key & internal key disimpan di **file biasa** (mis. `.env` / config JSON),
  **tanpa enkripsi**. UI **tidak** me-redaksi nilai.
- Jangan commit file `.env` (sudah di `.gitignore`).

## Proxy binding (ADR-008)
- Proxy diikat di level **Endpoint**; Endpoint menunjuk ke **Combo**.
- Implementasi ikuti `documents/api/OPENAI_COMPATIBLE_CONTRACT.md`.



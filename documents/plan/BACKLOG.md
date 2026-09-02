# Implementation Backlog — aigate

## Tujuan
Pecah fitur dari PRD / FSD / ERD / TSD menjadi task implementasi berurutan
lengkap dengan penanggung jawab, dependensi, dan status. PM pakai ini untuk
mendelegasikan ke sub-agent (be-dev / fe-dev / qa) secara rapi.

## Konvensi
- Status: `todo` | `in_progress` | `done`
  - Owner: `be-dev` | `fe-dev` | `qa` | `PM`
- `Dep`: task yang harus selesai duluan.
- Semua keputusan merujuk ADR di TSD: ADR-007 (secrets = file biasa, tanpa
  enkripsi, tanpa redaksi UI) dan ADR-008 (proxy binding di level Endpoint,
  Endpoint -> Combo).

## Fase 0 — Fondasi
- [ ] **B0.1** Inisialisasi project (FastAPI + UI: web UI lokal) — `be-dev` + `fe-dev` — Dep: -
- [ ] **B0.2** Config engine SQLite (SQLAlchemy) + buat skema dari `documents/analysis/ERD.md` — `be-dev` — Dep: B0.1
- [ ] **B0.3** Penyimpanan secrets di file biasa tanpa enkripsi (ADR-007) — `be-dev` — Dep: B0.2

## Fase 1 — Gateway & Routing
- [ ] **B1.1** Endpoint OpenAI-compatible `/v1/chat/completions` + `/v1/models` (lihat `documents/api/OPENAI_COMPATIBLE_CONTRACT.md`) — `be-dev` — Dep: B0.2
- [ ] **B1.2** Proxy Pools (HTTP/HTTPS/SOCKS5) + rotasi (RR/Random/Failover) + health check — `be-dev` — Dep: B0.2
- [ ] **B1.3** Combos (fallback / load-balance / latency-cost) — `be-dev` — Dep: B1.1
- [ ] **B1.4** Binding proxy di level Endpoint, Endpoint -> Combo (ADR-008) — `be-dev` — Dep: B1.2, B1.3

## Fase 2 — Terminal
- [ ] **B2.1** PTY bridge (`ptyprocess`/`pywinpty`) + `xterm.js` via WebSocket — `be-dev` — Dep: B0.1
- [ ] **B2.2** Multi-tab terminal UI — `fe-dev` — Dep: B2.1
- [ ] **B2.3** Floating control (toggle fullscreen + paste + auto-return focus) — `fe-dev` — Dep: B2.2
- [ ] **B2.4** Scroll & swipe (velocity-based, swipe->scroll, damping, whitelist TUI) — `fe-dev` — Dep: B2.2
- [ ] **B2.5** CLI auto-launcher + grouping A/B/C (lihat `documents/config/CLI_CONFIG_SCHEMA.md`) — `be-dev` + `fe-dev` — Dep: B1.1

## Fase 3 — QA & Polish
- [ ] **B3.1** Eksekusi rencana test (lihat `documents/qa/TEST_PLAN.md`) — `qa` — Dep: semua Fase 1–2


## Catatan
- Urutan di atas sudah mempertimbangkan dependensi; jangan mulai Fase 2 sebelum
  B0.2 (skema DB) siap.
- Tiap task selesai wajib di-update statusnya di file ini + di `pm/status.md`.

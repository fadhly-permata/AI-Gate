# Implementation Backlog — aigate

## Tujuan
Pecah fitur dari `@documents/` (PRD, FSD, ERD, TSD, API contract) menjadi task
implementasi berurutan lengkap dengan owner, dependensi, dan status. PM pakai
ini untuk delegasikan ke sub-agent (be-dev / fe-dev / qa) secara rapi.

## Konvensi
- Status: `todo` | `in_progress` | `done`
  - Owner: `be-dev` | `fe-dev` | `qa` | `PM`
- `Dep`: task yang harus selesai duluan.
- **Aturan wajib (lihat `pm/OPERATING_RULES.md`):**
  - R10 Stack: FastAPI `<0.100` + Pydantic **v1** (pure Python, no Rust).
  - R11 Secret + config = **plaintext di DB** (tanpa enkripsi, tanpa masking UI).
  - R12 Logging **wajib ke `LogEntry`** (severity+stacktrace); dilarang `except: pass`.
  - R13 Frontend = **vanilla JS no-build** (AdminLTE-like); React/Vue/Expo dilarang.
  - R9 Implementasi jalan tanpa konfirmasi; ambigu -> PM ambil default + catat.
- Referensi ADR (TSD): ADR-001 vanilla JS, ADR-002 stack, ADR-003 PTY,
  ADR-007 secret plaintext, ADR-008 proxy binding di Endpoint, ADR-010 config di
  DB, ADR-011 logging wajib, ADR-012 pure-Python (Termux).

## Fase 0 — Fondasi
- [x] **B0.1** Inisialisasi project (FastAPI + server + `/api/health` + UI shell
       AdminLTE-like, collapsible sidebar, dark/light, i18n EN/ID) — `be-dev` + `fe-dev`
- [x] **B0.2** DB engine SQLite (SQLAlchemy) + 12 entity dari `analysis/ERD.md`
       (`models.py`, `config/db.py`) — `be-dev`
- [x] **B0.3** Penyimpanan secrets plaintext tanpa enkripsi (ADR-007) — `be-dev`

## Fase 1 — Config & Logging
- [x] **B1.1** Config-in-DB: model `Setting` + repo `config/settings.py`
       (get/set/ensure_seeded) (ADR-010/011, R11) — `be-dev` — Dep: B0.2
- [x] **B1.2** Logging infra: model `LogEntry` + helper logger (severity+stacktrace+
       context) + enforce no-empty-catch di seluruh backend (ADR-011, R12) — `be-dev`
      — Dep: B0.2
- [x] **B1.3** Settings UI: panel port / dev-mode / theme baca-tulis `Setting`
       (vanilla JS, R13) — `be-dev` + `fe-dev` — Dep: B1.1

## Fase 2 — Gateway & Routing
- [x] **B2.1** Endpoint OpenAI-compatible `/v1/chat/completions` + `/v1/models`
      (ikuti `api/OPENAI_COMPATIBLE_CONTRACT.md`); tiap method wajib log (ADR-011);
      pakai Pydantic v1 (R10) — `be-dev` — Dep: B1.2, B0.2
- [x] **B2.2** Provider CRUD + model auto-discovery + key management
      (`analysis/FSD.md` §2.1–§2.2) — `be-dev` + `fe-dev` — Dep: B2.1, B1.1
- [x] **B2.3** Proxy Pools (HTTP/HTTPS/SOCKS5) + rotasi (RR/Random/Failover) +
      health check (`FSD` §2.3) — `be-dev` — Dep: B0.2
- [x] **B2.4** Combos (fallback / load-balance / latency-cost) (`FSD` §2.4) —
      `be-dev` — Dep: B2.1
- [x] **B2.5** Binding proxy di level Endpoint, Endpoint -> Combo (ADR-008) —
      `be-dev` — Dep: B2.3, B2.4

## Fase 3 — Terminal & Execution
- [x] **B3.1** Terminal UI (collapsible, log window) (vanilla JS, R13) —
      `fe-dev` — Dep: B0.1
- [x] **B3.2** PTY backend: `ptyprocess` (POSIX/Termux) + `pywinpty` (Win) wiring
      (ADR-003) — `be-dev` — Dep: B0.1
- [x] **B3.3** Multi-tab terminal + floating control (fullscreen/paste/focus) +
       scroll & swipe (velocity, whitelist TUI) — `fe-dev` — Dep: B3.1, B3.2
- [x] **B3.4** CLI tool management + preset grup A/B/C (ikuti
       `config/CLI_CONFIG_SCHEMA.md`) — `be-dev` + `fe-dev` — Dep: B2.1

## Fase 4 — Self-Heal & Polish
- [x] **B4.1** Self-Heal (menu CLI-Tool): git branch `aigate/self-heal-*` + launch
       agentic CLI terinstall + loop fix/test dari `LogEntry` warning/error; **delete**
       row yg sudah ke-resolve; merge ke `main` + hapus branch (PRD §2.8 / FSD §2.8) —
       `be-dev` + `fe-dev` — Dep: B1.2, B1.3
- [x] **B4.2** i18n EN/ID lengkap + dark/light + responsif & simulasi perangkat
       (phone non-AdminLTE) (`FSD` §2.5, §2.7) — `fe-dev` — Dep: B0.1
- [x] **B4.3** QA: eksekusi `qa/TEST_PLAN.md` (pytest + vitest + playwright) —
       `qa` — Dep: semua Fase 1–3

## Fase 5 — Adopsi 9router (fitur baru dari PRD ter-align)
- [x] **B5.1** Multi-akun per provider + login OAuth + token diperbarui otomatis
       (PRD §2.1, adopsi 9router) — `be-dev` + `fe-dev` — Dep: B2.2
- [x] **B5.2** Combos fallback 3 tingkat (langganan→murah→gratis) + cadangan antar-akun
       + routing sadar kuota (PRD §2.3, adopsi 9router) — `be-dev` — Dep: B2.4, B5.1, B5.5
- [x] **B5.3** Engine penerjemah format (OpenAI↔Claude↔Gemini↔Cursor↔Kiro↔Vertex↔
       Antigravity↔Ollama) (PRD §2.4, adopsi 9router) — `be-dev` — Dep: B2.1
- [ ] **B5.4** Penghemat Token: RTK (padatkan tool_result), mode Caveman, Ponytail —
       toggle per endpoint (PRD §2.4.1, adopsi 9router) — `be-dev` — Dep: B2.1
- [x] **B5.5** Pelacak Kuota & Pemakaian real-time + estimasi biaya (PRD §2.4.2,
       adopsi 9router) — `be-dev` + `fe-dev` — Dep: B2.2
- [ ] **B5.6** Log Permintaan (debug) + Dashboard Usage Analytics (PRD §2.4.3,
       adopsi 9router) — `be-dev` + `fe-dev` — Dep: B1.2
- [ ] **B5.7** Export/Import Setting lokal (file JSON) — pengganti cloud sync
       (PRD §2.4.4, request user) — `be-dev` + `fe-dev` — Dep: B1.1

## Catatan
- Urutan mempertimbangkan dependensi; jangan mulai Fase 2 sebelum B0.2 siap.
- Tiap task selesai: update status di file ini + log ke `pm/status.md`.
- Implementasi berjalan tanpa konfirmasi (R9); PM catat default yg dipakai.

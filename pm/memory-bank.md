# Memory Bank

## Project brief
(empty — diisi PM saat task pertama)

## Decisions
- 2026-09-03: Arsitektur agen PM + sub-agent spesialis (on-demand, scoped).

## Progress
- Inisialisasi PM agent + rules + skills selesai.
- 2026-09-03: Enhance PRD terminal — floating control, scroll/swipe natural,
  grouping CLI tools (agentic-first, 3 grup).
- 2026-09-03: Sequential doc creation SELESAI — BRD (documents/business/BRD.md),
  FSD+ERD (documents/analysis/FSD.md, ERD.md), TSD (documents/architecture/TSD.md).
  Spesialis business-analyst, system-analyst, tech-architect + skill-nya
  di-generate on-demand (belum terdaftar di sesi; pakai 'general' stand-in).
  Semua dokumen di `documents/` (R5).
- 2026-09-03: Execution docs SELESAI (mode sekuensial) — #1 Backlog
  (documents/plan/BACKLOG.md), #3 API Contract (documents/api/), #4 Test Plan
  (documents/qa/), #5 Dev Setup (documents/dev/), #6 Terminal UX (documents/ux/),
  #7 CLI Config Schema (documents/config/). ADR-007 & ADR-008 resolved.

## Decisions
- 2026-09-03: Terminal UX — swipe diubah jadi scroll (bukan navigasi TUI) karena
  TUI sering salah tangani swipe. Scroll velocity-based + damping agar natural.
- 2026-09-03: CLI tool presets dikelompokkan; prioritas agentic CLI (claude,
  opencode, codex, gemini, antigravity, phi, aider, goose, amp, qwen, cline,
  kilo, dst). Dapat diperluas via YAML/JSON.
- 2026-09-03 (TSD ADRs): GUI = web UI lokal (FastAPI static + xterm.js);
  PTY = ptyprocess/pywinpty + xterm.js via WebSocket; swipe exception =
  SwipeException registry + per-tab tui_mode.
  - ADR-007 (secrets): RESOLVED — app lokal, simpan di file biasa TANPA enkripsi,
    UI tidak perlu redaksi/masking. (putus 2026-09-03)
  - ADR-008 (proxy binding): RESOLVED — binding di level Endpoint; Endpoint
    menunjuk ke Combo (Endpoint -> Combo). (putus 2026-09-03)

## Open risks
- Agent file business-analyst / system-analyst / tech-architect SUDAH dibuat tapi
  belum terdaftar di sesi berjalan; perlu reload opencode agar bisa dipakai sbg
  subagent_type asli (selama ini pakai 'general' stand-in).
- ADR-007 & ADR-008 SUDAH RESOLVED (2026-09-03) — lihat Decisions. Tidak ada
  lagi ADR Proposed yang blokir implementasi.
- **Termux runtime risk:** RESOLVED (2026-09-03) — user pilih opsi (C): pin
  `fastapi>=0.95,<0.100` + `pydantic>=1.10,<2` (Pydantic v1 pure Python, tanpa
  pydantic-core/Rust). Semua dep inti pure Python → aigate jalan di Termux & semua
  platform tanpa compile Rust. Expo/React Native ditolak (bukan pengganti backend
  Python; tak kasih PTY utk CLI). Lihat TSD ADR-002.

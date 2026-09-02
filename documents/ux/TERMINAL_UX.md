# Terminal UX Interaction Spec — aigate

Spesifikasi interaksi terminal, merujuk PRD §2.5, §2.5.1, §2.6.1, FSD §2.5/§2.6,
dan TSD (terminal architecture). Tujuannya de-risk fitur baru sebelum kode.

## 1. Floating Control
- Ikon mengambang di pojok area terminal.
- **Toggle Fullscreen**: perbesar terminal menutupi area kerja; klik lagi normal.
- **Paste**: suntik clipboard ke PTY aktif, lalu **fokus otomatis balik ke
  terminal** (user bisa lanjut ketik tanpa klik ulang).

## 2. Scroll & Swipe (trackpad / mouse)
- Scroll vertikal (dan horizontal bila tersedia) via roda / gesture trackpad.
- **Swipe -> Scroll** (bukan navigasi TUI): event swipe diubah menjadi proses
  scroll pada buffer terminal, karena banyak TUI salah tangani swipe.
- **Velocity-based**: swipe cepat = scroll layar cepat (bisa loncat beberapa
  layar); swipe lambat = scroll halus baris-per-baris; diberi easing.
- **Damping**: berhenti halus di ujung buffer.
- **Whitelist TUI**: aplikasi TUI yang butuh swipe khusus bisa dikecualikan per
  tab (`tui_mode`), lewat registry `SwipeException` (ADR-006 TSD).

## 3. CLI Tool Grouping
- Daftar tool dikelompokkan: Grup A (agentic coding), Grup B (autonomous
  agents), Grup C (chat/shell). Minimal 5 per grup (lihat
  `documents/config/CLI_CONFIG_SCHEMA.md`).
- Klik tool -> cek binary -> bila belum ada, buka tab & install -> bila ada,
  tampil picker Provider/Combo+Model -> suntik env (`OPENAI_API_BASE`,
  `OPENAI_API_KEY`) & jalankan di tab baru.

## Acceptance (untuk QA)
- Paste+focus, fullscreen toggle, swipe->scroll velocity, grouping A/B/C harus
  lulus e2e (lihat `documents/qa/TEST_PLAN.md`).

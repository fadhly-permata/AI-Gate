# Terminal UX Interaction Spec — aigate

Spesifikasi interaksi terminal, merujuk PRD §2.5, §2.5.1, §2.6.1, FSD §2.5/§2.6,
dan TSD (terminal architecture). Tujuannya de-risk fitur baru sebelum kode.

## 1. Floating Control
- Ikon mengambang di pojok area terminal.
- **Toggle Fullscreen**: perbesar terminal menutupi area kerja; klik lagi normal.
- **Paste**: suntik clipboard ke PTY aktif, lalu **fokus otomatis balik ke
  terminal** (user bisa lanjut ketik tanpa klik ulang).

## 2. Scroll & Swipe (trackpad / mouse / touch)
- Scroll vertikal (dan horizontal bila tersedia) via roda / gesture trackpad.
- **Swipe == Wheel**: gesture swipe diubah menjadi event `wheel` sintetis pada
  elemen xterm, lalu xterm yang menerjemahkannya sesuai aplikasi yang berjalan:
  buffer biasa -> scroll viewport 1:1 dengan jari; buffer *alternate* (TUI) ->
  input scroll aplikasi (Up/Down cursor key, atau mouse-wheel report bila app
  minta tracking). `term.scrollLines()` tidak berpengaruh di alt-buffer, jadi
  jalur wheel inilah yang membuat swipe di TUI berfungsi.
- **Arah natural**: jari digeser ke atas = konten terbaru, sama dengan perilaku
  touch bawaan xterm (bukan dibalik).
- **Velocity-based**: drag mengikuti jari 1:1 (tanpa kurva velocity); lepas jari
  menghasilkan *momentum* (loop rAF dengan friction) sampai velocity habis atau
  mentok ujung buffer.
- **Damping**: berhenti halus di ujung buffer (edge stop + bubble ke halaman).
- **Passthrough TUI**: tombol TUI pada toolbar menandai tab sebagai pengecualian
  — gesture mentah diteruskan ke aplikasi (drag-select, tap-hold), tidak diubah
  jadi wheel. Whitelist per-aplikasi tetap lewat registry `SwipeException`
  (ADR-006 TSD).

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

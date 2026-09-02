# Laporan Tugas: Pembuatan Rule Global & Command (revise-docs, log-bug)

## Informasi Dasar
- Tanggal: 2026-09-03
- Jenis Tugas: rules + commands
- Waktu Mulai: ~05:30

## Permintaan Pengguna
1. Buat command untuk revisi semua `@documents/` agar ter-update berdasarkan request user.
2. Buat command untuk pencatatan bug.
3. Koreksi: jangan pernah buat command/rule/skill di luar folder project (global).
   Buat aturan ini secara global biar tidak terulang.

## Rencana Pekerjaan
1. Buat rule global `no-global-artifact-creation` di `~/.config/opencode/rules/`.
2. Reinforce di `pm/OPERATING_RULES.md` (R6).
3. Buat `revise-docs.md` & `log-bug.md` di project `.opencode/commands/`.
4. Laporan.

## Realisasi Pekerjaan
- Global rule ditulis: `~/.config/opencode/rules/no-global-artifact-creation.md`.
- R6 ditambah di `pm/OPERATING_RULES.md`.
- Command dibuat di project: `.opencode/commands/revise-docs.md`, `.opencode/commands/log-bug.md`.

## Status Akhir
Berhasil — aturan global + 2 command project dibuat. Command dibuat di project
(sesuai R6), bukan global, agar tidak melanggar aturan yang sama.

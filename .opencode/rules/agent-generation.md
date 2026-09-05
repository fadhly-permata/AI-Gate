---
name: agent-generation
description: >
  Rules preventing premature creation of sub-agents and their skills. Both
  must be generated on demand by the PM, together, never pre-created.
---

# Agent Generation Rules

These rules exist because the assistant previously broke them. Do NOT repeat.

## R1 — Jangan buat sub-agent sebelum waktunya
Sub-agent (Back-end, Front-end, Fullstack, System Analyst, Business Analyst,
QA, Architect, dst) HANYA dibuat saat PM benar-benar membutuhkannya
untuk sebuah task. Jangan buat definisi sub-agent di awal / sekaligus semua.
Definisi sub-agent hidup di `.opencode/agents/specialists/<nama>.md` dan baru
ditulis oleh PM saat dibutuhkan, lalu di-reuse (tidak dihapus).

## R2 — Skill sub-agent dibuat BERSAMAAN dengan sub-agent-nya
Jangan buat skill sub-agent (`.opencode/skills/<nama>-skill/SKILL.md`) di
awal. Skill tersebut HANYA dibuat pada saat yang sama PM membuat sub-agent
tersebut (lihat Generator di `ProjectManager.md`). Tidak ada skill sub-agent yang
dibuat tanpa sub-agent-nya.

## R3 — Setelah generate, minta user restart opencode
File `.opencode/agents/specialists/<nama>.md` yang baru dibuat PM tidak langsung
dikenali sebagai subagent_type oleh sesi yang sedang jalan; spawn akan gagal
("Unknown agent type"). Setelah PM generate sub-agent + skill-nya, WAJIB minta
user restart opencode agar agent terdaftar. Jangan ganti silently dengan agen
lain (`general`/dsb) tanpa sepengetahuan user.

## Enforcement
- Sebelum menulis file apa pun ke `agents/specialists/` atau
  `skills/*-skill/`, pastikan itu bagian dari generate-on-demand PM, bukan
  inisiatif di luar kebutuhan task.
- Setelah generate, langkah wajib berikutnya: minta user restart opencode
  (bukan langsung spawn).
- Jika ragu, tanyakan user, jangan langsung buat.

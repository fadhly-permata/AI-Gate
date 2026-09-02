# Laporan Tugas: Buat Agent Project Manager + Sub-Agent Spesialis On-Demand

## Informasi Dasar
- Tanggal: 2026-09-03
- Jenis Tugas: build
- Waktu Mulai: 04:00

## Permintaan Pengguna
1. Buat agent "Project Manager" (cari skill-nya via Context7).
2. PM dapat generate/spawn/summon sub-agent spesialis (BE, FE, Fullstack,
   System Analyst, Business Analyst, dll) — hanya dibuat saat dibutuhkan,
   tapi tidak dihapus setelah selesai.
3. Sub-agent yang dibuat wajib pakai skill yang cocok dengan spesialisasinya
   (cari juga skill-nya).
4. Tambah rule: task besar/lama → tawarkan proses paralel atau sekuensial.
5. (Koreksi) Sub-agent jangan dibuat sekarang; only on demand. Tambah batasan
   akses file per agent (jangan nyampur).
6. (Koreksi) Skill sub-agent jangan dibuat sekarang; dibuat bersamaan saat
   sub-agent dibuat.
7. (Koreksi) Jadikan 2 kesalahan tadi sebagai rule biar tak terulang.

## Rencana Pekerjaan
1. Cari skill PM via Context7 → ketemu "Agentic Project Management".
2. Buat PM agent (`.opencode/agents/pm.md`) dengan generator on-demand.
3. Buat 8 skill spesialis — (DIBATALKAN: skill dibuat bersama sub-agent).
4. Buat rule: agent-generation, agent-boundaries, parallel-sequential.
5. Buat pm-orchestration skill untuk PM.
6. Init pm/ memory bank + operating rules + state + status.
7. Tulis laporan.

## Realisasi Pekerjaan
- 04:05 cari skill Context7 → Agentic PM (Manager+Impl Agents+Memory Bank+Handover).
- 04:10 buat `pm.md` dengan roster 8 spesialis + generator (agent+skill on-demand).
- 04:15 buat 8 skill spesialis lalu DIHAPUS (koreksi user: jangan pre-create).
- 04:20 rewrite `pm.md`: generator buat agent+skill bersamaan on-demand.
- 04:25 buat `pm-orchestration/SKILL.md` (PM sendiri).
- 04:30 buat rule `agent-generation.md` (R1 pre-create agent, R2 pre-create skill).
- 04:35 buat rule `agent-boundaries.md` (scope per agent, no mixing).
- 04:38 buat rule `parallel-sequential.md` (tawar paralel/sekuensial).
- 04:40 init `pm/OPERATING_RULES.md` (R1,R2,R3), `state.md`, `status.md`, `memory-bank.md`.
- 04:42 tulis laporan ini.

## Status Akhir
Berhasil — PM agent + 3 rule + pm-orchestration skill + pm/ state siap.
Sub-agent & skill-nya tidak dibuat sekarang; akan di-generate PM saat dibutuhkan
(agent + skill bersamaan), persisten, berbatas scope ketat.

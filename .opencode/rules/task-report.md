# TASK REPORT
Task-type work need report. Git commit/push exempt.
Store `.opencode/reports/[yyyymmdd]/[task_type]/[hhmm]_[judul_task].md`.
Report hold: title, user request, plan, actual, final status.
Write early (grab plan). Update after done (fill actual). Plan many step -> log each step done.

## REPORT TEMPLATE
```
# Laporan Tugas: [Judul Task]

## Informasi Dasar
- Tanggal: YYYY-MM-DD
- Jenis Tugas: [build / research / refactor / docs / lainnya]
- Waktu Mulai: HH:MM

## Permintaan Pengguna
[apa yang diminta user, ditulis apa adanya]

## Rencana Pekerjaan
1. [langkah pertama]
2. [langkah kedua]
3. [langkah ketiga]

## Realisasi Pekerjaan
[diisi sambil jalan, tiap langkah selesai langsung dicatat]
- [HH:MM] langkah 1 -> selesai
- [HH:MM] langkah 2 -> selesai

## Status Akhir
[Berhasil / Gagal / Sebagian] - [penjelasan singkat]
```

## Ownership & path hygiene (absorbs old R23; K2 mediation 2026-09-10; OWNER = PM-only per user ruling 2026-09-11)
**Only the PM writes report files.** A sub-agent's paperwork is its in-session **receipt** (changed files, `file:line`,
decisions, open questions) — never a `.md` under `.opencode/reports/`. PM reads the receipt, verifies independently,
then writes the report and names the executor + session id inside it.
Do NOT ask a specialist to create a report file and do NOT widen its write root "just for paperwork" — the boundary
rule and this rule used to collide; the user settled it in favor of PM-only reports.
Path root `.opencode/reports/` holds no loose file: every report lives at `[yyyymmdd]/[task_type]/[hhmm]_[slug].md`.
Report folders use `[yyyymmdd]` (no dashes). Legacy folders were normalized on 2026-09-10 by `git mv`
(history kept; every file already had a `[hhmm]_` prefix except two, renamed to their recorded time:
`20260903/docs/0627_revise_native_run.md` from the report body's own start time, and
`20260909/qa/0718_qa_anthropic_inbound_verification.md` from that file's git add-commit time).
One identical duplicate report (`2026-09-03/qa/2026-09-03_b4_3_qa.md` == `qa/1350_b4_3_qa.md`) removed.
Gate: `python3 .opencode/tools/governance/rules-index.py` lists non-conforming reports (0 now).

---
description: Run aigate implementation with fresh / continue / status modes; progress survives session restarts
---
Run the aigate implementation. Action = first arg.

Args: $ARGUMENTS

If first arg in `help` / `info` / `information` / `?` -> print usage, stop.

Usage: /run-impl [mode]
  fresh    = mulai dari awal (B0.1). Catat di pm/status.md bahwa sesi fresh;
             isi BACKLOG.md tetap (jangan di-reset manual).
  continue = lanjut dari task belum selesai pertama (DEFAULT bila arg kosong).
  status   = tampilkan progres (todo / in_progress / done), lalu stop.

Procedure (PM executes):
1. Load progress:
   - Baca `documents/plan/BACKLOG.md` (task + tanda `[ ]` / `[x]`).
   - Baca `pm/status.md` untuk penanda "task aktif" (jika ada).
2. Mode:
   - `fresh`: set penanda task aktif = B0.1 di pm/status.md.
   - `continue` (default): cari task pertama yang belum `[x]` = task aktif.
   - `status`: cetak tabel progres, stop.
3. **CHECKPOINT GIT (R19)** — sebelum eksekusi task aktif: `git status` (cek
   bersih/ada sisa), lalu `git add -A && git commit -m "checkpoint: <task> start"`
   supaya state tree tersimpan SEBELUM sub-agent mengubah apa pun. Skip commit
   kalau working tree sudah bersih. Jangan commit `.env`/DB (hormati .gitignore).
4. Eksekusi task aktif sesuai R9 (TANPA konfirmasi; ambiguitas -> default + log
   di pm/status.md + memory-bank). Pakai sub-agent sesuai owner
    (be-dev / fe-dev / qa); bila belum terdaftar di sesi, pakai 'general'
   stand-in, atau subagent asli bila opencode sudah di-restart.
5. **COMMIT TIAP SUBTASK (R19)** — begitu satu subtask selesai (receipt sub-agent
   + PM verifikasi sendiri: pytest/vitest hijau), LANGSUNG
   `git add -A && git commit -m "<type>(<task>): <subtask>"`. Jangan numpuk.
   Kalau subtask selesai tapi tes masih merah -> commit `wip:` (selamatin kerja),
   JANGAN tandai [x].
6. Setelah task selesai: tandai `[x]` di BACKLOG.md, update pm/status.md
   (task aktif = berikutnya), commit `docs(<task>): mark done`, lalu lanjut task
   berikutnya sampai habis.
7. Bila sesi terputus (batre habis / force-close): di sesi baru cukup jalankan
   `/run-impl continue` -> lanjut OTOMATIS dari task belum selesai. Kerjaan yang
   sudah ke-commit (R19) tidak padam; tidak perlu ulang dari nol.

Definition of done:
- Implementasi jalan berurutan dari Backlog; progres tersimpan di BACKLOG.md +
  pm/status.md DAN di git (checkpoint awal task + commit tiap subtask, R19)
  sehingga bisa dilanjutkan tanpa mengulang walau sesi terputus.

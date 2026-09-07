# Handover — Self-Heal: perbaiki command opencode + gate done-marker (2026-09-07)

**Owner scope:** be-dev (`src/backend/selfheal.py`, `tests/backend/test_selfheal.py`).
**Catatan eksekusi:** sesi ini tidak punya Task tool -> PM tidak bisa spawn be-dev.
PM proxy-implementasi strictly dalam write scope be-dev. Deviation dicatat di status.md.

## Goal
Self-heal tidak lagi (a) memanggil TUI interaktif `opencode` dengan `--prompt`,
(b) menandai issue DONE saat CLI gagal, (c) mengirim model id mentah (`hy3`)
yang ditolak opencode (butuh `provider/model`).

## Context (hasil investigasi, terverifikasi)
- Bug: `src/backend/selfheal.py` `build_heal_command()` L385-407 —
  L404 `f"{cli}{model_flag} --prompt \"$(cat '{promptfile}')\"; "` (TUI default
  command + `--prompt`), L404-406 separator `;` -> `touch done` jalan tanpa syarat.
- opencode 1.18.22 (terverifikasi via `opencode run --help` / `opencode --help`):
  - `opencode run [message..]` = non-interactive; TIDAK punya `--prompt`;
    punya `-m, --model` format `provider/model`.
  - `--prompt` + `--model` = opsi TUI default (`opencode [project]`) — interaktif,
    salah untuk automasi. `opencode --model hy3 --prompt x` menggantung/exit tanpa
    memproses (help printed) tapi rc diabaikan karena `;`.
- Model `hy3`: DB `~/.aigate/aigate.db` settings `self_heal_model='hy3'`,
  `self_heal_cli='opencode'`. Nilai combobox = `model_id` mentah dari
  `list_self_heal_models()` (selfheal.py L220-229). `opencode models` punya
  `aigate/hy3` DAN `bai/hy3` -> ambigu; provider project = `aigate`
  (opencode.json repo).
- Completion: `wait_for_done()` (L410-446) poll existence `<prompt>.done`;
  dipakai `_drive_cli_in_terminal()` (L475) -> `run_self_heal()` (L795).

## Definition of done
1. opencode -> `opencode run[-m <qualified>] "$(cat '<promptfile>')"` satu baris.
2. Done-sentinel hanya di-touch saat rc=0 (`&&`); rc!=0 touch `<...>.failed`;
   `wait_for_done` return False segera saat failed-sentinel muncul (bukan nunggu
   timeout 30 menit).
3. Model qualification opencode: sudah `provider/model` -> lolos; mentah -> resolve
   via `opencode models` (unique suffix; ambigu -> prefer prefix `aigate/`;
   no-match -> None = flag di-omit + warning). Fail-open kalau subprocess gagal.
4. CLI lain (claude/aider/...) tetap bentuk lama (belum diverifikasi — open item),
   TAPI tetap dapat gating `&&`/failed.
5. `tests/backend/test_selfheal.py` disesuaikan + test baru untuk (1)-(3);
   `pytest tests/backend` hijau tanpa regresi.

## Constraints
- Jangan sentuh router/FE (kontrak API tidak berubah).
- Jangan ubah semantik timeout/progress keys.
- Satu baris shell, diakhiri `\n` ( diketik ke PTY bash).

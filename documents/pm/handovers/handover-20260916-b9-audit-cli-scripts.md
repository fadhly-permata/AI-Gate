# Handover — B9: Audit mendalam skrip install CLI (fullstack-dev)

Tanggal: 2026-09-16 | Owner: **fullstack-dev** | PM: ProjectManager
Sasaran: `scripts/cli-tools/*.sh` (24 skrip tool + `_common.sh`). User lama melaporkan "masih ada bug" tapi BELUM menyebut tool/gejala spesifik. PM sudah scan statis awal: **25/25 lolos `bash -n`**, backtick hanya di komentar, pola `set -e` memang tidak dipakai (by-design idempotent). Jadi cari defect LOGIKA/RUNTIME yang bisa dibuktikan, bukan syntax.

## Tugas
Audit tiap skrip untuk defect nyata, dan PERBAIKI hanya yang bisa dibuktikan:
1. **Source `_common.sh` benar** (path `BASH_SOURCE`, double-source guard jalan).
2. **Pesan literal aman**: tidak ada command-substitution/backtick yang TEREKSEKUSI dalam string pesan (pola bug swe-agent dulu — `pip ...` ikut jalan). Cek SEMUA skrip, bukan cuma swe-agent.
3. **`NO_INSTALL` / `NOT_A_CLI` benar-benar no-op**: hanya echo + `exit 0`, TIDAK memanggil pkg/npm/pip/cargo apa pun (no side-effect).
4. **Idempoten + path-independent**: jalan dari direktori mana pun; re-run aman; tidak hardcode repo root.
5. **Konsistensi gateway vs backend**: env/flag yang dipasang skrip SELARAS dengan builder di `src/backend/cli_presets.py` + `src/backend/cli_tools_router.py` (contoh: nama var, bentuk ref model). Beda = kandidat bug.
6. **Version-guard**: untuk tool dengan pin Python (aider 3.10–3.12, openhands 3.12) guard PRÉ-install masih benar & tidak lolos di luar rentang.

## Cara aman (WAJIB — jangan pernah memasang/mengubah sistem)
- JANGAN jalankan install asli (npm/pip/pkg/cargo sungguhan). Untuk dry-run, shim PATH/fungsi supaya `command -v`, `pkg`, `npm`, `pip` jadi no-op/stub, atau set `AIGATE_OS`/pakai `--check-only` bila skrip mendukung. Tujuan: AMATI perilaku, bukan meng-install.
- Kerjakan di scratch di luar repo; JANGAN sentuh `~/.aigate`, JANGAN sentuh `:8080` user (J6), JANGAN install dependensi.

## Batas berkas (STRICT)
- WRITE: `scripts/cli-tools/*.sh` (HANYA bila ada defect terbukti), dan report di `.opencode/reports/[yyyymmdd]/...`.
- READ: `src/backend/cli_presets.py`, `src/backend/cli_tools_router.py`, `documents/plan/cli-tools-install-backlog.md`, `documents/pm/**`.
- DILARANG: ubah skrip tanpa bukti defect; ubah `src/backend/**`; menyentuh sistem user; `git add -A`.

## Definition-of-done
- Tiap temuan disertai **bukti repro yang aman** (sebelum/sesudah) — bukan dugaan.
- Kalau ADA defect: perbaiki + tunjukkan diff + dry-run membuktikan perbaikan + `bash -n` tetap 0.
- Kalau TIDAK ada defect yang terbukti: laporkan **BERSIH** dengan bukti scan (jangan mengarang fix).
- Pisahkan jelas: (a) defect statis/eksplisit yang kamu temui & perbaiki; (b) hal yang butuh **gejala runtime dari user** untuk direproduksi.

## Receipt
Temuan per skrip (bug / bersih), bukti, diff bila ada fix, dan daftar pertanyaan spesifik untuk user (mis. "tool mana, pesan error apa, langkah mana gagal"). JANGAN commit/push.

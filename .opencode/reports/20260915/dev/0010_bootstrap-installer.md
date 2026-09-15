# Laporan Tugas: Bootstrap Installer Cold-Start (scripts/bootstrap.sh + scripts/bootstrap.ps1)

## Informasi Dasar
- Tanggal: 2026-09-15
- Jenis Tugas: build
- Waktu Mulai: 00:10
- Eksekutor: fullstack-dev
- Rujukan: `documents/pm/handovers/handover-20260915-bootstrap-installer.md`
- Branch kerja: `main` (working tree; TIDAK ada branch baru, TIDAK ada commit/push/PR — hak user, aturan D1/H1)

## Permintaan Pengguna
Menyediakan satu perintah "just work" untuk cold-start pada mesin yang belum memiliki
apa pun (bahkan tanpa Python). Bootstrap harus: (1) memastikan interpreter Python >= 3.10
tersedia — native package manager lebih dulu, fallback ke userspace `uv`; (2) memeriksa
`git` dan hanya memperingatkan bila tidak ada; lalu (3) menyerahkan eksekusi ke `run.py`
yang sudah menangani dependensi pip. Keputusan user sudah dikunci oleh PM (Q1 semua
platform; Q2 native lalu uv; Q3 skrip terpisah tanpa butuh Python; Q4 Python+pip+cek-git).
`run.py` dan seluruh isi `src/**`, `tests/**`, `pyproject.toml`, `README.md` tidak boleh
disentuh. Sertakan mode `--check-only` / `-CheckOnly` untuk gerbang QA yang mendeteksi
tanpa memasang dan tanpa meluncurkan.

## Rencana Pekerjaan
1. Membaca handover, `run.py`, `pyproject.toml`, `README.md`, `scripts/cli-tools/_common.sh` (house-style), serta rules `.opencode/rules/*.md`.
2. Verifikasi fakta eksternal mekanisme fallback `uv` (installer userspace, `uv python install <ver>`, `uv python find <ver>`) dari dokumentasi resmi (sumber kedua, di luar handover).
3. Memetakan batasan shell lingkungan: interpreter (Termux/Android aarch64), ketersediaan alat, dan mana bashism yang lolos `dash -n`.
4. Menulis `scripts/bootstrap.sh` (POSIX/bash) sesuai 10 ketentuan isi handover.
5. Menulis `scripts/bootstrap.ps1` (Windows PowerShell 5.1 + 7) sebagai padanan.
6. Menjalankan seluruh gerbang Definition-of-Done, menangkap output mentah.
7. Menyusun receipt untuk PM.

## Realisasi Pekerjaan
- [00:10] langkah 1 -> selesai. Fakta `run.py:18-21,24-46,52-70` dan `pyproject.toml:11` (= ">=3.10") dikonfirmasi; konstanta versi pada bootstrap diberi komentar rujukan ke sumber kebenaran itu (menghindari dua sumber kebenaran).
- [00:12] langkah 2 -> selesai. Sumber kedua: https://docs.astral.sh/uv/getting-started/installation/ (installer `curl -LsSf https://astral.sh/uv/install.sh | sh` memasang ke `~/.local/bin`, tanpa root) dan https://docs.astral.sh/uv/concepts/python-versions/ (`uv python install 3.12` memasang CPython ter-manajeman ke user dir; `uv python find 3.12` mengembalikan path interpreter). Konsisten dengan handover.
- [00:15] langkah 3 -> selesai. Temuan: `dash -n` menolak array bash (`A=(x)` => syntax error) tetapi TIDAK memvalidasi `set -o pipefail` saat parse (`dash -n` lolos; hanya gagal saat dash MENJALANKAN, sedangkan gerbang menjalankan dengan bash). Konsekuensi: skrip ditulis TANPA array bash, `local` dipakai, `BASH_SOURCE:-$0` dipakai agar portable. `pwsh`/`powershell` TIDAK tersedia di lingkungan ini.
- [00:30] langkah 4 -> selesai. 252 baris. Deteksi platform termux/linux/mac; reuse interpreter >= 3.10 sebelum memasang; urutan native (pkg/brew/root-only apt/dnf/yum/pacman/zypper) lalu fallback uv; cek-git hanya memperingatkan; serah terima `exec "$PY" run.py "$@"`; `--check-only` deteksi-saja.
- [00:45] langkah 5 -> selesai. 244 baris. Padanan Windows: winget per-user non-interaktif lalu fallback uv (installer ps1 + `uv python find`); refresh PATH sesi dari registry; `-CheckOnly` deteksi-saja. Dikoreksi saat review: probe versi memakai `>=` (bukan operator PowerShell `-ge`); splat memakai variabel lokal `$a` (bukan `@script:` scope-qualified) dan param `$CmdArgs` (menghindari bayangan `$Args` otomatis).
- [00:55] langkah 6 -> selesai (lihat Status Akhir). Gerbang POSIX dieksekusi; gerbang Windows hanya validasi struktural karena tidak ada PowerShell di sini.
- [01:00] langkah 7 -> selesai.

## Gerbang Selesai — Hasil NYATA
- `bash -n scripts/bootstrap.sh` -> exit 0.
- `dash -n scripts/bootstrap.sh` (POSIX-sh strict, interpreter = dash) -> exit 0. `sh -n` -> exit 0.
- `bash scripts/bootstrap.sh --check-only` (Termux/Linux, lingkungan ini) -> exit 0; output: platform `termux`, interpreter `/data/data/com.termux/files/usr/bin/python3`, git `present`, run.py `found`; tidak memasang, tidak meluncurkan. Idempoten: dijalankan ulang -> sama. Path-independen: dijalankan dari direktori lain -> hasil sama.
- `bash scripts/bootstrap.sh --help` -> exit 0.
- `pwsh ... -CheckOnly` -> TIDAK DIEKSEKUSI (PowerShell tidak tersedia di lingkungan ini). Sebagai gantinya validasi struktural manual: brace 52/52, paren 73/73, bracket 17/17, paritas kutip seimbang, semua fungsi terdefinisi & terpakai, tidak ada operator PowerShell di dalam probe Python, tidak ada `@script:` scope-splat. JALUR WINDOWS BELUM DIEKSEKUSI — perlu reviewer Windows.
- `git diff --check` -> exit 0.
- `git status --porcelain` -> hanya berkas baru `scripts/bootstrap.sh`, `scripts/bootstrap.ps1` (dan laporan ini di `.opencode/reports/**`). NOL perubahan pada `run.py`/`src`/`tests`/`pyproject`/`README`.

## Status Akhir
Berhasil (sebagian terverifikasi). Bootstrap POSIX (`bootstrap.sh`) lolos seluruh gerbang yang dapat dieksekusi di lingkungan ini, termasuk `--check-only` nyata, `bash -n`, `dash -n`, dan `sh -n`, tanpa efek samping (tidak memasang uv, tidak menyentuh port 8080). Bootstrap Windows (`bootstrap.ps1`) selesai dan lolos validasi struktural, tetapi jalur pemasangan Windows BELUM dieksekusi karena PowerShell tidak tersedia; jalur `winget`, installer `uv` ps1, dan serah terima `py`/`python` perlu diverifikasi reviewer di mesin Windows nyata. Tidak ada commit, push, atau PR.

## Keputusan (default) & Alternatif
- Root di Linux: hanya mencoba native PM bila `id -u`==0; selain itu langsung ke `uv`. Ini menjamin TIDAK ADA sudo diam-diam/prompt password. Alternatif: memanggil `sudo -n` (ditolak — melanggar ketentuan 4).
- Versi yang diminta saat memasang: 3.12 (per handover) — bukan 3.10 minimum, agar punya kepala ruang.
- Interpreter uv diambil lewat `uv python find <ver>` (path absolut) alih-alih mengandalkan PATH yang diubah uv. Alternatif: `--default` (eksperimental) untuk mendapat `python3`.
- `exec "$PY" run.py "$@"` (POSIX) / `& $cmd @a $RunPy @RestArgs` lalu `exit $LASTEXITCODE` (PS) sebagai bentuk serah terima.
- Bahasa pesan: netral, tanpa emoji di alur error, tanpa membocorkan path internal repo (hanya menampilkan path interpreter sistem, bukan path sumber).

## Open Questions (untuk PM)
1. Konvensi serah-terima uv di Windows PATH: setelah winget/uv memasang, interpreter baru mungkin belum terlihat pada sesi shell yang sama. Skrip sudah memanggil `Update-SessionPath` dari registry, tetapi perilaku aktual `py`/`python` shim (App Execution Alias Microsoft Store) pada Windows nyata perlu uji reviewer.
2. `uv python install 3.12` memasang executable ber-versi (`python3.12`), bukan `python3`. Skrip POSIX mengandalkan `uv python find 3.12` untuk path konkret — sudah benar, namun distribusi python-build-standalone di arsitektur tertentu (mis. aarch64 Termux) belum diuji nyata di lingkungan ini (uv tidak ada di sini).

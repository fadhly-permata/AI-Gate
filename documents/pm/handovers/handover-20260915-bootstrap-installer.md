# Handover — Bootstrap installer (cold-start dependency + Python)

**PM → fullstack-dev** · 2026-09-15 · branch kerja: `main` (kerjakan di working tree, JANGAN bikin branch sendiri; PM yang atur git).

## Tujuan
Satu perintah "just work" untuk **cold start**: user yang belum punya apa-apa (bahkan Python) cukup jalankan satu skrip.
Skrip memastikan Python tersedia (≥ 3.10) + cek `git` (peringatan saja), lalu serahkan ke `run.py` yang SUDAH menangani
dependensi pip. Hasil: `python run.py` tidak lagi jadi chicken-and-egg di mesin kosong.

## Keputusan user (SUDAH DIKUNCI — jangan tanya ulang, jangan ubah arah)
- **Q1 = semua platform** termasuk Windows → Termux, Linux, macOS, Windows.
- **Q2 = native package manager dulu, fallback ke `uv` kalau gagal** (native = `pkg` Termux / `apt-get`/`dnf`/`pacman`/`zypper` Linux / `brew` macOS / `winget` Windows).
- **Q3 = skrip bootstrap cold-start terpisah** yang TIDAK butuh Python untuk jalan. `run.py` TIDAK diubah.
- **Q4 = Python + pip deps (via run.py) + cek git** — git cuma **diperingatkan** kalau belum ada, TIDAK dipaksa install.

## Fakta repo yang PM sudah cek (jangan cek ulang)
- `run.py` = entry launcher. `run.py:24-46` gate Python ≥ 3.10 (`MIN_PYTHON=(3,10)`). `run.py:52-70` `ensure_deps()` pip-install
  yang hilang (fastapi/pydantic/uvicorn/websockets/sqlalchemy/ptyprocess/httpx + pywinpty di win32). **Semua ini sudah beres —
  jangan sentuh `run.py`.** Bootstrap cuma perlu memanggilnya.
- `pyproject.toml:11` → `requires-python = ">=3.10"` = sumber kebenaran angka. Bootstrap boleh hardkode `(3, 10)` tapi WAJIB komentar
  rujukan ke `pyproject.toml` (hindari dua sumber kebenaran — preseden persis di `run.py:18-21`).
- **Frontend TIDAK butuh Node saat runtime.** `src/frontend/package.json` isinya HANYA `devDependencies` (vitest/playwright/puppeteer-core).
  FastAPI meng-serve static. Jadi bootstrap TIDAK install Node.js.
- `scripts/` SUDAH ADA di repo (berisi `scripts/cli-tools/*.sh` — skrip install/launch 24 CLI tool pihak-ketiga, BUKAN dependency aigate).
  Jangan tertukar: tugas ini bootstrap **aplikasi aigate sendiri**, bukan tool-list.

## Aturan tata letak (PENTING — aturan B1)
DILARANG bikin berkas baru di **root** repo. Simpan bootstrap di folder `scripts/` yang sudah ada:
- `scripts/bootstrap.sh`   (POSIX: Termux + Linux + macOS)
- `scripts/bootstrap.ps1`  (Windows PowerShell 5.1 + PowerShell 7)
Akses via `bash scripts/bootstrap.sh` / `pwsh scripts/bootstrap.ps1` (documentasikan; README diurus PM belakangan, JANGAN kamu sentuh).

## Batas tulis (STRIK)
- **WRITE hanya:** `scripts/bootstrap.sh`, `scripts/bootstrap.ps1`.
- **READ:** `run.py`, `pyproject.toml`, `README.md` (untuk gaya pesan pengguna saja), `scripts/cli-tools/_common.sh` (contoh house-style POSIX di Termux — boleh ditiru pola guard-nya), `documents/pm/**`.
- **DILARANG tulis:** `run.py` (cukup dipanggil, jangan diubah), `src/**`, `tests/**`, `documents/**` (kecuali report-mu sendiri di `.opencode/reports/**`), `README.md`, `pyproject.toml`, berkas/folder lain di root, `scripts/cli-tools/**`.
- Murni dua berkas skrip. NOL dependensi ke file aigate selain `run.py`.

## Ketentuan isi
1. **Deteksi platform** (POSIX): Termux (env `$PREFIX` / `$IS_TERMS` / path `com.termux`) → Linux (`/etc/os-release`, ambil `ID`/`ID_LIKE`) → macOS (`uname` = `Darwin`). Bedakan Termux dari Linux reguler (pkg vs apt).
2. **Cari interpreter** Python ≥ 3.10 yang SUDAH ada sebelum install apa pun: coba `python3`, `python`, `py -3` (Windows). Ketemu & cukup → **lompat install**, langsung serahkan.
3. **Bila perlu install** (Q2 = native dulu → fallback uv):
   - Termux: `pkg install -y python`.
   - Linux: pilih dari `apt-get` / `dnf` / `yum` / `pacman` / `zypper` (yang tersedia).
   - macOS: `brew install python@3.12` (kalau `brew` ada).
   - Windows: `winget install -e --id Python.Python.3.12` (non-interaktif: `--accept-package-agreements --accept-source-agreements`).
   - **Fallback:** native gagal / tidak ada / perlu sudo interaktif → **userspace `uv`** lalu `uv python install 3.12`. Inilah jalur **tanpa sudo** — utamakan ini kalau native-PM butuh hak root.
4. **HAK ROOT / sudo** (CRITICAL, user.privacy + safe): skrip TIDAK PERNAH memanggil `sudo` diam-diam atau prompt password sendiri. Di Linux, kalau paket sistem butuh root dan sudo tak tersedia non-interaktif → **langsung fallback ke uv (userspace)**. Sertakan komentar eksplisit.
5. **Cek git** (Q4): kalau `git` tak ada → cetak **peringatan** saja (fitur Self-Heal git-based tak akan jalan), lalu lanjut normal. JANGAN install git, JANGAN exit.
6. **Serahkan** ke `run.py` pakai interpreter yang baru dipasang/ditemukan (bootstrap TIDAK duplikasi logic pip). POSIX: `exec "$PY" run.py "$@"` (bawa arg user). Windows: `& $py run.py @args`.
7. **Mode uji tanpa副作用:** flag `--check-only` (POSIX) / `-CheckOnly` (Windows) = deteksi platform + interpreter + git, **TIDAK install / TIDAK launch** — lalu exit. Ini yang QA pakai di gerbang.
8. **Idempoten:** jalan 2× = jalan 1× di mesin sudah siap (skip install). **Non-interaktif** (aman di CI/pipe). `set -euo pipefail` (POSIX) + `$ErrorActionPreference='Stop'` (PS).
9. **Bahasa pesan:** netral, jelas, **tanpa bocor path internal repo**, tanpa emoji di alur error. Ikut gaya `run.py` (human message + exit code).
10. **JANGAN hardcode path repo**; pakai `$(dirname "${BASH_SOURCE[0]}")/..` (POSIX) / `$PSScriptRoot\..` (PS) biar bisa dijalankan dari folder mana pun.

## Gerbang selesai (kamu jalankan sendiri, laporkan hasil NYATA)
- [ ] `bash -n scripts/bootstrap.sh` → exit 0.
- [ ] `dash -n scripts/bootstrap.sh` (POSIX-sh strict) → exit 0. (kalau `dash` tak ada, pakai `sh -n` dan sebut interpreter-nya)
- [ ] POSIX di lingkungan INI (Termux/Linux): `bash scripts/bootstrap.sh --check-only` → deteksi platform benar + interpreter benar + exit rapi, **TANPA install, TANPA launch server**. Tangkap outputnya.
- [ ] Windows: `pwsh -NoProfile -Command "& { $ErrorActionPreference='Stop'; . scripts/bootstrap.ps1 -CheckOnly }"` kalau `pwsh` tersedia. Kalau TIDAK tersedia di lingkungan ini → **jujur**: validasi struktural manual (keseimbangan `{}`, block, pipeline) + tandai "jalur Windows belum dieksekusi (perlu reviewer Windows)". JANGAN klaim sudah diuji kalau belum.
- [ ] `git diff --check` → exit 0.
- [ ] `git status --porcelain` → HANYA dua berkas baru `scripts/bootstrap.sh` + `scripts/bootstrap.ps1` (+ report-mu di `.opencode/reports/**`). NOL perubahan di `run.py`/`src`/`tests`/`pyproject`/`README`.
- [ ] JANGAN start server asli, JANGAN pip install, JANGAN sentuh port 8080 (aturan J6).

## Receipt yang PM minta
1. Isi kedua skrip (path + baris +/-).
2. Output MENTAH tiap gerbang di atas (perintah + hasil, bukan klaim).
3. **Peta platform → native PM → perintah install → cara fallback uv** dalam tabel singkat.
4. Verbatim pesan error yang akan dibaca user awam (per skrip).
5. Cara kamu menjamin TIDAK ada sudo diam-diam + klaim jujur soal mana yang **belum** bisa dieksekusi di lingkungan ini.
6. Keputusan ambigu yang kamu ambil + alasan + alternatifnya (PM catat default di atas).
7. **JANGAN commit, JANGAN push, JANGAN bikin PR** (hak user, aturan D1).

## Catatan
- README update ("just work" jadi `bash scripts/bootstrap.sh`) = PM koordinasikan ke `public-writer` **setelah** skrip ACC. JANGAN kamu sentuh.
- Kalau ada keputusan arsitektur yang di luar kendali (mis. urutan fallback lintas-OS yang ambigu): sebut sebagai open-question di receipt, PM escalate ke user. Jangan bikin keputusan besar sepihak.

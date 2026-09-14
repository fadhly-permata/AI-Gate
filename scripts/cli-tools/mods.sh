#!/usr/bin/env bash
# mods.sh — NO_INSTALL no-op launcher for aigate (Grup C / Chat & Shell Assistants).
#
# ===========================================================================
# HASIL RISET (fact-based, R47+R48 — >=2 sumber independen, TIDAK ASUMSI):
# ---------------------------------------------------------------------------
# SUMBER 1 — KODE aigate (src/backend/cli_presets.py):
#   * cli_presets.py:45  -> NO_INSTALL didefinisikan sebagai
#       "echo 'aigate: no verified install command for this tool'".
#   * cli_presets.py:102 -> {"name":"mods","binary":"mods","install": NO_INSTALL}
#     => aigate menandai mods sebagai tool TANPA perintah install terverifikasi
#        (Grup C / Chat & Shell Assistants).
#   * cli_presets.py:225 -> "mods": LaunchSupport(LAUNCH_UNSUPPORTED,
#                            REASON_NO_BINARY)
#     => aigate sendiri menandai mods sebagai LAUNCH_UNSUPPORTED karena TIDAK
#        ada biner (no_binary) untuk environment ini.
#   * cli_presets.py:162-166 -> komentar eksplisit: "goose / amp / mods / sgpt /
#     swe-agent / autogpt / phi -> no installable package for this platform
#     under that name (PyPI names belong to unrelated projects; npm ships no
#     android build, ...)".
#   * TERMUX_INSTALL map (cli_presets.py:241-244) hanya berisi "aichat" +
#     "codex" — TIDAK ada entry mods. Jadi di Termux pun tak ada rute
#     install terverifikasi.
#   * Cross-check backlog: documents/pm/cli-tools-install-backlog.md
#     menempatkan mods (C3) dalam grup NO_INSTALL (antigravity, phi, goose,
#     amp, swe-agent, autogpt, sgpt, mods) — konsisten dengan kode di atas.
#
# SUMBER 2 — Registry GitHub / npm / PyPI (https://github.com/charmbracelet/mods,
#   https://registry.npmjs.org/mods, https://pypi.org/pypi/mods/json):
#   * GitHub charmbracelet/mods -> INI CLI resmi "AI for the command line,
#     built for pipelines" (biner Go). NUANSA penting: repo di-ARCHIVE /
#     di-sunset pada 2026-03-09 (fokus beralih ke Crush). Rute install resmi:
#       brew install charmbracelet/tap/mods
#       winget install charmbracelet.mods
#       yay -S mods            (Arch)
#       nix-shell -p mods
#       apt (repo.charm.sh) / yum (repo.charm.sh)
#       cd /usr/ports/sysutils/mods && make install   (FreeBSD)
#       go install github.com/charmbracelet/mods@latest
#     Binari resmi hanya tersedia untuk Linux / macOS / Windows — TIDAK ada
#     build Termux / Android.
#   * npm registry 'mods' (registry.npmjs.org/mods) -> SQUAT / paket TAK
#     TERKAIT: "Module management system for Node.js" oleh Denis Olshin
#     (latest 1.2.2), BUKAN CLI charmbracelet. `npm install -g mods` akan
#     memasang paket salah.
#   * PyPI 'mods' (pypi.org/pypi/mods/json) -> 404, TIDAK ADA project.
#     `pip install mods` akan gagal.
#
# SUMBER 3 — Dokumentasi resmi (README GitHub charmbracelet/mods, bagian
#   Installation): rute install di atas dikonfirmasi di docs resmi; disebutkan
#   "Binaries are available for Linux, macOS, and Windows" — TIDAK menyebut
#   Android/Termux. Jadi tidak ada build resmi untuk environment ini.
#
# CROSS-CHECK: ketiga sumber konsisten — aigate menandai mods NO_INSTALL +
#   LAUNCH_UNSUPPORTED(REASON_NO_BINARY), dan TERMUX_INSTALL tidak punya entry
#   ini; GitHub mengonfirmasi mods = CLI Go resmi (namun di-archive 2026-03-09,
#   binari hanya Linux/macOS/Windows, tidak ada build Termux/Android); npm
#   'mods' adalah squat Node.js tak terkait & PyPI 'mods' = 404. Konklusi: mods
#   memang TIDAK punya install terverifikasi di environment ini. NUANSA: ada
#   binari resmi (Go via brew/go/apt/yum) untuk macOS/Linux, TAPI tidak
#   menyediakan build Termux/Android dan nama npm-nya disquat paket tak terkait
#   -> tidak ada perintah install aman & terverifikasi untuk environment ini.
#   Sesuai keputusan user untuk tool NO_INSTALL: script HANYA menampilkan pesan
#   lalu KELUAR — tidak memasang paket apa pun (aman, hindari pasang paket
#   salah / squat / tak terkait).
# ===========================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

detect_os
detect_pm
load_gateway_config   # aigate gateway base (AIGATE_BASE) + internal key (AIGATE_KEY)

set -euo pipefail

BIN="mods"

# --- NO_INSTALL: tidak ada install terverifikasi, keluar dengan aman ---------
log_msg "os=$AIGATE_OS pm=$AIGATE_PM"
log_msg "mods: NO_INSTALL — belum ada install terverifikasi di environment ini."
log_msg "  (aigate cli_presets.py:102 menandainya NO_INSTALL; cli_presets.py:225"
log_msg "   LAUNCH_UNSUPPORTED / REASON_NO_BINARY; TERMUX_INSTALL map tidak punya"
log_msg "   entry ini.)"
log_msg "  GitHub charmbracelet/mods: CLI Go resmi, TAPI di-archive/sunset 2026-03-09"
log_msg "   & binari resmi hanya Linux/macOS/Windows (tidak ada build Termux/Android)."
log_msg "  Registry: npm 'mods' = paket Node.js TAK TERKAIT (squat); PyPI 'mods' = 404."
log_msg "   Jadi 'npm install -g mods' / 'pip install mods' akan memasang paket salah."
log_msg "  PERINGATAN: script ini TIDAK memasang paket apa pun (menghindari"
log_msg "   pemasangan paket salah / squat / tak terkait). Jika Anda punya cara"
log_msg "   install resmi mods di Linux/macOS (mis. 'brew install charmbracelet/tap/mods'"
log_msg "   atau 'go install github.com/charmbracelet/mods@latest') dan ingin"
log_msg "   menjalankannya, pasang + jalankan secara manual — jangan andalkan"
log_msg "   script ini untuk install di Termux/android."

# Idempoten, tanpa side-effect. Keluar 0 (no-op sesuai desain, bukan error).
exit 0

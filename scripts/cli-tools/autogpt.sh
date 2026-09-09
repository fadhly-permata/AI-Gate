#!/usr/bin/env bash
# autogpt.sh — NO_INSTALL no-op launcher for aigate (Grup B / B4).
#
# ===========================================================================
# HASIL RISET (fact-based, R47+R48 — >=2 sumber independen, TIDAK ASUMSI):
# ---------------------------------------------------------------------------
# SUMBER 1 — KODE aigate (src/backend/cli_presets.py):
#   * cli_presets.py:45  -> NO_INSTALL didefinisikan sebagai
#       "echo 'aigate: no verified install command for this tool'".
#   * cli_presets.py:91  -> {"name":"autogpt","binary":"autogpt",
#                            "install": NO_INSTALL}
#     => aigate menandai autogpt sebagai tool TANPA perintah install
#        terverifikasi (Grup B / Autonomous Agents).
#   * cli_presets.py:217 -> "autogpt": LaunchSupport(LAUNCH_UNSUPPORTED,
#                            REASON_INSTALL_UNVERIFIED)
#     => aigate sendiri menandai autogpt sebagai LAUNCH_UNSUPPORTED karena
#        install-nya TIDAK terverifikasi untuk environment ini.
#   * cli_presets.py:162 -> komentar eksplisit: "goose / amp / mods / sgpt /
#     swe-agent / autogpt / phi -> no installable package for this platform
#     under that name (PyPI names belong to unrelated projects; npm ships no
#     android build, ...)".
#   * TERMUX_INSTALL map (cli_presets.py:241-244) hanya berisi "aichat" +
#     "codex" — TIDAK ada entry autogpt. Jadi di Termux pun tak ada rute
#     install terverifikasi.
#   * Cross-check backlog: documents/pm/cli-tools-install-backlog.md
#     menempatkan autogpt (B4) dalam grup NO_INSTALL (antigravity, phi,
#     goose, amp, swe-agent, autogpt, sgpt, mods) — konsisten dengan kode di
#     atas.
#
# SUMBER 2 — PyPI (https://pypi.org/pypi/autogpt/json, nama biner persis):
#   * Paket bernama 'autogpt' MEMANG ADA di PyPI, TAPI bukan AutoGPT resmi
#     dan bukan CLI yang bisa di-launch:
#       - author/maintainer: "Shadow Walker" (shadowwalker2718),
#         author_email kosong.
#       - version: 0.0.1.dev0 (pre-release dev, upload 2023-04-02).
#       - summary/description: cuma "# autogpt" (placeholder kosong).
#       - requires_dist: ["torch"] — hanya dependensi torch, TIDAK ada
#         [project.scripts] / console_script -> 'pip install autogpt' TIDAK
#         menghasilkan biner 'autogpt' di PATH.
#       - ukuran wheel hanya ~1.1 KB -> jelas placeholder / squat tak
#         terkait, BUKAN agent resmi Significant-Gravitas.
#     Jadi memasang 'autogpt' dari PyPI = memasang sampah/placeholder, bukan
#     AutoGPT asli.
#
# SUMBER 3 — GitHub resmi (https://github.com/Significant-Gravitas/AutoGPT,
#   README):
#   * AutoGPT resmi kini berupa PLATFORM: di-host (managed, berbayar) ATAU
#     self-host. Self-hosting resmi BUTUH Docker + konfigurasi + API key
#     sendiri (install via 'install.sh' dari setup.agpt.co / Docker Compose,
#     bukan pip/binom tunggal).
#   * "AutoGPT Classic" (agent standalone asli) ada di subfolder 'classic/'
#     — di-build via Forge / di-benchmark via 'agbenchmark' (PyPI
#     'agbenchmark'), bukan 'pip install autogpt' yang menghasilkan biner
#     'autogpt'.
#   * Docker + setup berat TIDAK praktis di Termux/aarch64 (Docker tidak
#     tersedia di Android, ARM build berat) -> sesuai klaim aigate "no
#     installable package for this platform under that name". Tidak ada
#     biner CLI tunggal yang bisa di-spawn aigate di environment ini.
#
# CROSS-CHECK: ketiga sumber konsisten — aigate menandai autogpt NO_INSTALL
#   + LAUNCH_UNSUPPORTED(REASON_INSTALL_UNVERIFIED), dan TERMUX_INSTALL tidak
#   punya entry ini; PyPI dengan nama 'autogpt' memang ADA tapi berupa
#   placeholder/squat tak terkait (author Shadow Walker, 0.0.1.dev0, hanya
#   torch, tanpa console script -> tidak menghasilkan biner 'autogpt');
#   GitHub resmi AutoGPT adalah platform Docker-based (self-host butuh Docker
#   + config + own API keys) yang tidak praktis di Termux/android-arm64.
#   Konklusi: autogpt memang TIDAK punya install terverifikasi di
#   environment ini -> sesuai grup NO_INSTALL. CATATAN transparan: ada paket
#   PyPI bernama 'autogpt', TAPI itu placeholder TAK TERKAIT (bukan AutoGPT
#   resmi) dan tidak menghasilkan biner; AutoGPT asli butuh Docker. Sesuai
#   keputusan user untuk tool NO_INSTALL: script HANYA menampilkan pesan
#   lalu KELUAR — tidak memasang paket apa pun (aman, hindari pasang paket
#   salah / placeholder / squat).
# ===========================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

detect_os
detect_pm
load_gateway_config   # aigate gateway base (AIGATE_BASE) + internal key (AIGATE_KEY)

set -euo pipefail

BIN="autogpt"

# --- NO_INSTALL: tidak ada install terverifikasi, keluar dengan aman ---------
log_msg "os=$AIGATE_OS pm=$AIGATE_PM"
log_msg "autogpt: NO_INSTALL — belum ada install terverifikasi di environment ini."
log_msg "  (aigate cli_presets.py:91 menandainya NO_INSTALL; cli_presets.py:217"
log_msg "   LAUNCH_UNSUPPORTED / REASON_INSTALL_UNVERIFIED; TERMUX_INSTALL map"
log_msg "   tidak punya entry ini.)"
log_msg "  Registry PyPI: paket bernama 'autogpt' MEMANG ADA, TAPI adalah placeholder"
log_msg "   tak terkait (author 'Shadow Walker', versi 0.0.1.dev0, 2023-04-02, hanya"
log_msg "   dependensi 'torch', tanpa [project.scripts] -> tidak menghasilkan biner"
log_msg "   'autogpt' di PATH). BUKAN AutoGPT resmi (Significant-Gravitas)."
log_msg "  GitHub resmi: AutoGPT kini berupa PLATFORM — di-host (berbayar) atau"
log_msg "   self-host butuh Docker + konfigurasi + API key sendiri (install via"
log_msg "   'install.sh' setup.agpt.co / Docker Compose). Berat & tidak praktis di"
log_msg "   Termux/android-arm64; tidak menghasilkan biner CLI tunggal untuk gateway."
log_msg "  PERINGATAN: script ini TIDAK memasang paket apa pun (menghindari pemasangan"
log_msg "   paket salah / placeholder / squat). Jika Anda punya cara install resmi"
log_msg "   AutoGPT (self-host Docker di Linux/macOS), pasang + jalankan secara manual"
log_msg "   — jangan andalkan script ini untuk install di Termux/android."

# Idempoten, tanpa side-effect. Keluar 0 (no-op sesuai desain, bukan error).
exit 0

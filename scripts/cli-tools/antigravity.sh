#!/usr/bin/env bash
# antigravity.sh — NO_INSTALL no-op launcher for aigate (Grup A / A5).
#
# ===========================================================================
# HASIL RISET (fact-based, R47+R48 — >=2 sumber independen, TIDAK ASUMSI):
# ---------------------------------------------------------------------------
# SUMBER 1 — KODE aigate (src/backend/cli_presets.py):
#   * cli_presets.py:74  -> {"name":"antigravity","binary":"antigravity",
#                            "install": NO_INSTALL}
#     (NO_INSTALL didefinisikan di cli_presets.py:45 =
#      "echo 'aigate: no verified install command for this tool'").
#   * cli_presets.py:176 -> "antigravity": LaunchSupport(LAUNCH_UNSUPPORTED,
#                            REASON_NOT_A_CLI)
#     => aigate sendiri menandai antigravity sebagai BUKAN CLI yang bisa
#        di-launch, dan TIDAK punya perintah install terverifikasi.
#   * TERMUX_INSTALL map (cli_presets.py:241-244) hanya berisi "aichat" +
#     "codex" — TIDAK ada entry antigravity. Jadi di Termux pun tak ada
#     rute install terverifikasi.
#
# SUMBER 2 — npm registry (https://registry.npmjs.org/antigravity):
#   * Package "antigravity" ADA tapi adalah SQUAT/placeholder:
#       description: "placeholder for the haters"
#       version: "0.0.0", readme: "WIP. Teaching python folks javascript."
#     Bukan CLI resmi Antigravity (Google). Memasangnya = sampah.
#   * @anthropic/antigravity -> 404 (tidak ada paket resmi ber-namespace itu).
#
# SUMBER 3 — PyPI (https://pypi.org/pypi/antigravity/json) + Homebrew:
#   * PyPI "antigravity" ADA tapi milik Fabien Schwob
#     (home_page http://fabien.schwob.org/antigravity/) — tidak terkait
#     CLI Antigravity Google.
#   * Homebrew formula "antigravity" -> 404 (https://formulae.brew.sh).
#   => Tidak ada rute install terverifikasi (npm / pip / brew) untuk CLI
#      Antigravity di environment ini.
#
# Cek silang (CROSS-CHECK): ketiga sumber di atas konsisten dengan backlog
#   documents/pm/cli-tools-install-backlog.md:38 (A5 antigravity = NO_INSTALL,
#   todo) dan ringkasan baris 76-77 (8 tool NO_INSTALL termasuK antigravity).
#   Konklusi: antigravity memang TIDAK punya install terverifikasi di
#   environment ini. Sesuai keputusan user sebelumnya untuk tool NO_INSTALL:
#   script HANYA menampilkan pesan lalu KELUAR — tidak memasang paket apa pun
#   (aman, hindari pasang paket salah/squatted).
# ===========================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

detect_os
detect_pm
load_gateway_config   # aigate gateway base (AIGATE_BASE) + internal key (AIGATE_KEY)

set -euo pipefail

BIN="antigravity"

# --- NO_INSTALL: tidak ada install terverifikasi, keluar dengan aman ---------
log_msg "os=$AIGATE_OS pm=$AIGATE_PM"
log_msg "antigravity: NO_INSTALL — tidak ada paket CLI terverifikasi di environment ini."
log_msg "  (aigate cli_presets.py:74 menandainya NO_INSTALL; cli_presets.py:176"
log_msg "   LAUNCH_UNSUPPORTED/REASON_NOT_A_CLI; TERMUX_INSTALL map tidak punya entry ini.)"
log_msg "  Registry: npm 'antigravity' adalah placeholder squat (v0.0.0),"
log_msg "   PyPI 'antigravity' milik pihak lain, Homebrew 404 — tidak ada rute resmi."
log_msg "  PERINGATAN: script ini TIDAK memasang paket apa pun (menghindari"
log_msg "   pemasangan paket salah / squatted). Jika Anda yakin punya"
log_msg "   cara install resmi Antigravity, pasang secara manual lalu jalankan"
log_msg "   biner '$BIN' langsung — jangan andalkan script ini untuk install."

# Idempoten, tanpa side-effect. Keluar 0 (no-op sesuai desain, bukan error).
exit 0

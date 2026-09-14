#!/usr/bin/env bash
# phi.sh — NO_INSTALL no-op launcher for aigate (Grup A / A6).
#
# ===========================================================================
# HASIL RISET (fact-based, R47+R48 — >=2 sumber independen, TIDAK ASUMSI):
# ---------------------------------------------------------------------------
# SUMBER 1 — KODE aigate (src/backend/cli_presets.py):
#   * cli_presets.py:75  -> {"name":"phi","binary":"phi","install": NO_INSTALL}
#     (NO_INSTALL didefinisikan di cli_presets.py:45 =
#      "echo 'aigate: no verified install command for this tool'").
#   * cli_presets.py:177 -> "phi": LaunchSupport(LAUNCH_UNSUPPORTED,
#                            REASON_INSTALL_UNVERIFIED)
#     => aigate sendiri menandai phi sebagai LAUNCH_UNSUPPORTED karena
#        install-nya BELUM TERVERIFIKASI (bukan karena bukan CLI).
#   * cli_presets.py:162 -> komentar eksplisit: "goose / amp / mods / sgpt /
#     swe-agent / autogpt / phi -> no installable package for this platform
#     under that name" (PyPI names belong to unrelated projects; npm ships no
#     android build, dst).
#   * TERMUX_INSTALL map (cli_presets.py:241-244) hanya berisi "aichat" +
#     "codex" — TIDAK ada entry phi. Jadi di Termux pun tak ada rute install
#     terverifikasi.
#   * Cross-check backlog: documents/pm/cli-tools-install-backlog.md menempatkan
#     phi (A6) dalam grup NO_INSTALL (antigravity, phi, goose, amp, swe-agent,
#     autogpt, sgpt, mods) — konsisten dengan kode di atas.
#
# SUMBER 2 — npm registry (https://registry.npmjs.org/phi):
#   * Package "phi" ADA tapi adalah SQUAT/placeholder tak terkait:
#       author/maintainer: "Defrag" <tim.defrag@gmail.com>
#       description: "phi ===" (readme cuma "phi\n==="), terbaru v0.0.2
#         (di-upload 2013-03-23), dependencies: uglify-js, engines node >=0.6.
#     Bukan CLI resmi mana pun — murni squat lama. Memasangnya = sampah.
#   * Tidak ada varian @anthropic/phi / @vendor/phi yang merujuk CLI resmi.
#
# SUMBER 3 — PyPI (https://pypi.org/pypi/phi/json) + Homebrew:
#   * PyPI "phi" ADA tapi milik Cristian Garcia (cgarciae), "Phi library for
#     functional programming in Python" (DSL + combinator, `pip install phi`),
#     versi terbaru 0.6.7 (upload terakhir 2018). BUKAN CLI AI-agent; memasang
#     paket ini tidak menghasilkan biner `phi` yang bisa di-launch sebagai
#     coding assistant.
#   * Homebrew formula "phi" -> 404 (https://formulae.brew.sh/api/formula/phi.json
#     tidak ditemukan). Tidak ada formula resmi.
#   => Tidak ada rute install terverifikasi (npm / pip / brew) untuk CLI `phi`
#      di environment ini.
#
# Cek silang (CROSS-CHECK): ketiga sumber di atas konsisten — aigate menandai
#   phi NO_INSTALL + LAUNCH_UNSUPPORTED(REASON_INSTALL_UNVERIFIED), npm hanya
#   punya squat tak terkait, PyPI punya library FP tak terkait, dan brew 404.
#   Konklusi: phi memang TIDAK punya install terverifikasi di environment ini.
#   Sesuai keputusan user sebelumnya untuk tool NO_INSTALL: script HANYA
#   menampilkan pesan lalu KELUAR — tidak memasang paket apa pun (aman,
#   hindari pasang paket salah / squatted).
# ===========================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

detect_os
detect_pm
load_gateway_config   # aigate gateway base (AIGATE_BASE) + internal key (AIGATE_KEY)

set -euo pipefail

BIN="phi"

# --- NO_INSTALL: tidak ada install terverifikasi, keluar dengan aman ---------
log_msg "os=$AIGATE_OS pm=$AIGATE_PM"
log_msg "phi: NO_INSTALL — belum ada install terverifikasi di environment ini."
log_msg "  (aigate cli_presets.py:75 menandainya NO_INSTALL; cli_presets.py:177"
log_msg "   LAUNCH_UNSUPPORTED / REASON_INSTALL_UNVERIFIED; TERMUX_INSTALL map"
log_msg "   tidak punya entry ini.)"
log_msg "  Registry: npm 'phi' adalah squat/placeholder lama (v0.0.2, 2013, tak"
log_msg "   terkait); PyPI 'phi' = library functional programming cgarciae"
log_msg "   (bukan CLI); Homebrew formula 'phi' 404 — tidak ada rute resmi."
log_msg "  PERINGATAN: script ini TIDAK memasang paket apa pun (menghindari"
log_msg "   pemasangan paket salah / squatted). Jika Anda yakin punya"
log_msg "   cara install resmi CLI phi, pasang secara manual lalu jalankan"
log_msg "   biner '$BIN' langsung — jangan andalkan script ini untuk install."

# Idempoten, tanpa side-effect. Keluar 0 (no-op sesuai desain, bukan error).
exit 0

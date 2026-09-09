#!/usr/bin/env bash
# amp.sh — NO_INSTALL no-op launcher for aigate (Grup A / A9).
#
# ===========================================================================
# HASIL RISET (fact-based, R47+R48 — >=2 sumber independen, TIDAK ASUMSI):
# ---------------------------------------------------------------------------
# SUMBER 1 — KODE aigate (src/backend/cli_presets.py):
#   * cli_presets.py:45  -> NO_INSTALL didefinisikan sebagai
#       "echo 'aigate: no verified install command for this tool'".
#   * cli_presets.py:78  -> {"name":"amp","binary":"amp",
#                            "install": NO_INSTALL}
#     => aigate menandai amp sebagai tool TANPA perintah install terverifikasi.
#   * cli_presets.py:179 -> "amp": LaunchSupport(LAUNCH_UNSUPPORTED,
#                            REASON_NO_BINARY)
#     => aigate sendiri menandai amp sebagai LAUNCH_UNSUPPORTED karena biner
#        `amp` TIDAK ada (tidak ada install terverifikasi untuk environment ini).
#   * cli_presets.py:162 -> komentar eksplisit: "goose / amp / mods / sgpt /
#     swe-agent / autogpt / phi -> no installable package for this platform
#     under that name (PyPI names belong to unrelated projects; npm ships no
#     android build, ...)".
#   * TERMUX_INSTALL map (cli_presets.py:241-244) hanya berisi "aichat" +
#     "codex" — TIDAK ada entry amp. Jadi di Termux pun tak ada rute install
#     terverifikasi.
#   * Cross-check backlog: documents/pm/cli-tools-install-backlog.md menempatkan
#     amp (A9) dalam grup NO_INSTALL (antigravity, phi, goose, amp, swe-agent,
#     autogpt, sgpt, mods) — konsisten dengan kode di atas.
#
# SUMBER 2 — npm registry (https://registry.npmjs.org/amp):
#   * Package "amp" (unscoped) ADA tapi adalah MESSAGING LIBRARY tak terkait:
#       author/maintainer: tjholowaychuk (visionmedia/node-amp),
#       description: "Abstract messaging protocol", latest v0.3.1 (2013-2022),
#       keywords: amp, actor, message, messaging, zmq, zeromq.
#     `npm install -g amp` memasang library codec messaging Node.js, BUKAN CLI
#     coding agent. Memasangnya = sampah.
#   * Catatan penting: CLI coding-agent resmi (dulu @sourcegraph/amp, sekarang
#     @ampcode/cli — "Renamed to @ampcode/cli") memang ADA di npm (929 versi,
#     bin -> "amp", homepage https://ampcode.com). TAPI optionalDependencies-nya
#     HANYA: @ampcode/cli-darwin-arm64, -darwin-x64, -linux-arm64, -linux-x64,
#     -win32-x64 — TIDAK ADA @ampcode/cli-android-*. Artinya `npm install -g
#     @ampcode/cli` tidak menarik binary build aarch64-android/termux, jadi
#     gagal/tanpa biner `amp` yang berfungsi di environment ini. Ini persis yang
#     dimaksud komentar aigate "npm ships no android build".
#
# SUMBER 3 — PyPI (https://pypi.org/pypi/AMP/json, name "AMP"):
#   * PyPI "AMP" (v1.1.4, Ini Oguntola) = "Automatic Mathematical Parser",
#     library parsing matematika Python 2.7. `pip install AMP` -> library parser
#     matematika, BUKAN CLI. Tidak menghasilkan biner `amp`.
#
# SUMBER 4 — Homebrew (https://formulae.brew.sh/api/formula/amp.json):
#   * Homebrew formula "amp" (v0.7.1, homepage https://amp.rs,
#     jmacdonald/amp) = "Text editor for your terminal" (Rust, GPL-3.0).
#     BUKAN coding agent Sourcegraph/ampcode. Formula cask "amp" -> 404.
#   * Homebrew hanya untuk macOS/Linux (bukan Termux/aarch64).
#
# SUMBER 5 — GitHub (https://github.com/sourcegraph/amp):
#   * Repo github.com/sourcegraph/amp -> 404 (api.github.com/repos/sourcegraph/amp
#     juga 404). Nama repo resmi sudah bergeser ke ampcode (lihat SUMBER 2:
#     @sourcegraph/amp "Renamed to @ampcode/cli"). Tidak ada rute install
#     terverifikasi untuk Termux/aarch64 (binary release tidak ada build android).
#
# CROSS-CHECK: kelima sumber konsisten — aigate menandai amp NO_INSTALL +
#   LAUNCH_UNSUPPORTED(REASON_NO_BINARY); npm unscoped "amp" = messaging library
#   tak terkait; CLI resmi (@ampcode/cli, eks @sourcegraph/amp) memang ADA tapi
#   tidak punya build android/termux (optional deps hanya darwin/linux/win32)
#   sehingga tidak terverifikasi untuk environment ini; PyPI "AMP" = parser
#   matematika; Homebrew "amp" = text editor terminal. Konklusi: amp memang TIDAK
#   punya install terverifikasi di environment ini -> sesuai grup NO_INSTALL.
#   CATATAN transparan: ada install resmi (@ampcode/cli) untuk macOS/Linux/Win,
#   tapi tetap TIDAK berlaku untuk Termux/android-arm64. Sesuai keputusan user
#   untuk tool NO_INSTALL: script HANYA menampilkan pesan lalu KELUAR — tidak
#   memasang paket apa pun (aman, hindari pasang paket salah / squat / tak
#   terkait).
# ===========================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

detect_os
detect_pm
load_gateway_config   # aigate gateway base (AIGATE_BASE) + internal key (AIGATE_KEY)

set -euo pipefail

BIN="amp"

# --- NO_INSTALL: tidak ada install terverifikasi, keluar dengan aman ---------
log_msg "os=$AIGATE_OS pm=$AIGATE_PM"
log_msg "amp: NO_INSTALL — belum ada install terverifikasi di environment ini."
log_msg "  (aigate cli_presets.py:78 menandainya NO_INSTALL; cli_presets.py:179"
log_msg "   LAUNCH_UNSUPPORTED / REASON_NO_BINARY; TERMUX_INSTALL map"
log_msg "   tidak punya entry ini.)"
log_msg "  Registry: npm unscoped 'amp' = library messaging tak terkait"
log_msg "   (tjholowaychuk/node-amp, v0.3.1); CLI resmi @ampcode/cli (eks"
log_msg "   @sourcegraph/amp) memang ada tapi optional deps-nya HANYA"
log_msg "   darwin/linux/win32 — tidak ada build android/termux, sehingga npm"
log_msg "   tidak menarik biner 'amp' yang berfungsi di sini; PyPI 'AMP' = parser"
log_msg "   matematika (Ini Oguntola); Homebrew 'amp' = text editor terminal"
log_msg "   (amp.rs / jmacdonald)."
log_msg "  PERINGATAN: script ini TIDAK memasang paket apa pun (menghindari"
log_msg "   pemasangan paket salah / squat / tak terkait). Jika Anda yakin punya"
log_msg "   cara install resmi CLI amp (mis. 'npm install -g @ampcode/cli' di"
log_msg "   macOS/Linux/Win) dan ingin menjalankannya, pasang secara manual lalu"
log_msg "   jalankan biner '$BIN' langsung — jangan andalkan script ini untuk"
log_msg "   install di Termux/android."

# Idempoten, tanpa side-effect. Keluar 0 (no-op sesuai desain, bukan error).
exit 0

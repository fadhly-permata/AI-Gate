#!/usr/bin/env bash
# goose.sh — NO_INSTALL no-op launcher for aigate (Grup A / A8).
#
# ===========================================================================
# HASIL RISET (fact-based, R47+R48 — >=2 sumber independen, TIDAK ASUMSI):
# ---------------------------------------------------------------------------
# SUMBER 1 — KODE aigate (src/backend/cli_presets.py):
#   * cli_presets.py:77  -> {"name":"goose","binary":"goose",
#                            "install": NO_INSTALL}
#     (NO_INSTALL didefinisikan di cli_presets.py:45 =
#      "echo 'aigate: no verified install command for this tool'").
#   * cli_presets.py:178 -> "goose": LaunchSupport(LAUNCH_UNSUPPORTED,
#                            REASON_NO_BINARY)
#     => aigate sendiri menandai goose sebagai LAUNCH_UNSUPPORTED karena
#        biner `goose` TIDAK ada (tidak ada install terverifikasi), bukan
#        karena bukan CLI (tool-nya ada, rute install-nya yang tak terverifikasi
#        untuk environment ini).
#   * cli_presets.py:162 -> komentar eksplisit: "goose / amp / mods / sgpt /
#     swe-agent / autogpt / phi -> no installable package for this platform
#     under that name (PyPI names belong to unrelated projects; npm ships no
#     android build, and Termux's `goose` is a DB migration tool, not Block's
#     agent)."
#   * TERMUX_INSTALL map (cli_presets.py:241-244) hanya berisi "aichat" +
#     "codex" — TIDAK ada entry goose. Jadi di Termux pun tak ada rute
#     install terverifikasi.
#   * Cross-check backlog: documents/pm/cli-tools-install-backlog.md menempatkan
#     goose (A8) dalam grup NO_INSTALL (antigravity, phi, goose, amp, swe-agent,
#     autogpt, sgpt, mods) — konsisten dengan kode di atas.
#
# SUMBER 2 — npm registry (https://registry.npmjs.org/goose):
#   * Package "goose" ADA tapi adalah tool GOLANG TAK TERKAIT:
#       author: "jiyinyiyong", description: "Goose is a command which adds
#       brackets for golang", latest v0.0.3 (2012-2022), bin -> bin/index.js.
#     `npm install -g goose` memasang tool penambah kurung Go, BUKAN CLI
#     agentik Block. Memasangnya = sampah.
#   * @block/goose -> 404 (https://registry.npmjs.org/@block/goose tidak ada;
#     tidak ada paket npm resmi ber-namespace Block untuk goose).
#
# SUMBER 3 — GitHub resmi (github.com/block/goose -> aaif-goose/goose):
#   * goose Block sekarang di bawah Agentic AI Foundation / Linux Foundation
#     (repo aaif-goose/goose, Rust, desktop app + CLI + API).
#   * Rute install resmi di README: 
#       curl -fsSL https://github.com/aaif-goose/goose/releases/download/\
#         stable/download_cli.sh | bash
#     Ini download binary release via script, BUKAN npm/pip/brew ber-versi
#     dengan build aarch64-android (Termux) yang terverifikasi. aigate secara
#     sadar memilih NO_INSTALL karena tidak ada string install terverifikasi
#     untuk environment ini (npm tidak mengirim build android; binary release
#     belum divalidasi di Termux/aarch64).
#
# SUMBER 4 — PyPI (https://pypi.org/pypi/goose/json):
#   * PyPI "goose" (Goose 1.0.0, Mike Steder) = SQL database migration tool
#     berbasis SQLAlchemy. `pip install goose` -> tool migrasi DB, BUKAN
#     agent AI. Tidak ada biner `goose` agentik yang dihasilkan.
#
# SUMBER 5 — Homebrew (https://formulae.brew.sh/api/formula/goose.json):
#   * Homebrew formula "goose" = pressly/goose, CLI migrasi DB Go (v3.28.0),
#     BUKAN agent Block. Catatan: formula ini `conflicts_with: ["block-goose-cli"]`
#     ("both install `goose` binaries") — artinya Block punya formula TERPISAH
#     `block-goose-cli`. Formula `block-goose-cli` hanya untuk macOS/Linux
#     (bukan Termux/aarch64) dan tidak terverifikasi di environment ini.
#
# CROSS-CHECK: kelima sumber konsisten — aigate menandai goose NO_INSTALL +
#   LAUNCH_UNSUPPORTED(REASON_NO_BINARY); npm "goose" = tool Golang tak
#   terkait & @block/goose 404; PyPI "goose" = migrasi DB; Homebrew "goose" =
#   migrasi DB (Block ada di formula terpisah block-goose-cli, tak terverifikasi
#   Termux); install resmi Block (curl release script) tak punya build
#   aarch64-android terverifikasi. Konklusi: goose (agent Block) memang TIDAK
#   punya install terverifikasi di environment ini -> sesuai grup NO_INSTALL.
#   Sesuai keputusan user: script HANYA menampilkan pesan lalu KELUAR — tidak
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

BIN="goose"

# --- NO_INSTALL: tidak ada install terverifikasi, keluar dengan aman ---------
log_msg "os=$AIGATE_OS pm=$AIGATE_PM"
log_msg "goose: NO_INSTALL — belum ada install terverifikasi di environment ini."
log_msg "  (aigate cli_presets.py:77 menandainya NO_INSTALL; cli_presets.py:178"
log_msg "   LAUNCH_UNSUPPORTED / REASON_NO_BINARY; TERMUX_INSTALL map"
log_msg "   tidak punya entry ini.)"
log_msg "  Registry: npm 'goose' adalah tool Golang tak terkait (jiyinyiyong,"
log_msg "   v0.0.3); @block/goose 404; PyPI 'goose' = migrasi DB (Mike Steder);"
log_msg "   Homebrew 'goose' = pressly/goose (migrasi DB, conflicts_with"
log_msg "   block-goose-cli). Install resmi Block (curl release script) tak punya"
log_msg "   build aarch64-android/termux terverifikasi."
log_msg "  PERINGATAN: script ini TIDAK memasang paket apa pun (menghindari"
log_msg "   pemasangan paket salah / squat / tak terkait). Jika Anda yakin punya"
log_msg "   cara install resmi CLI goose Block, pasang secara manual lalu jalankan"
log_msg "   biner '$BIN' langsung — jangan andalkan script ini untuk install."

# Idempoten, tanpa side-effect. Keluar 0 (no-op sesuai desain, bukan error).
exit 0

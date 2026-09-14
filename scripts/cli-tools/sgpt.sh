#!/usr/bin/env bash
# sgpt.sh — NO_INSTALL no-op launcher for aigate (Grup C / C2).
#
# ===========================================================================
# HASIL RISET (fact-based, R47+R48 — >=2 sumber independen, TIDAK ASUMSI):
# ---------------------------------------------------------------------------
# SUMBER 1 — KODE aigate (src/backend/cli_presets.py):
#   * cli_presets.py:45  -> NO_INSTALL didefinisikan sebagai
#       "echo 'aigate: no verified install command for this tool'".
#   * cli_presets.py:101 -> {"name":"sgpt","binary":"sgpt",
#                            "install": NO_INSTALL}
#     (di grup chat_shell). => aigate menandai sgpt sebagai tool TANPA
#     perintah install terverifikasi.
#   * cli_presets.py:224 -> "sgpt": LaunchSupport(LAUNCH_UNSUPPORTED,
#                            REASON_INSTALL_UNVERIFIED)
#     => aigate sendiri menandai sgpt LAUNCH_UNSUPPORTED karena install-nya
#        TIDAK terverifikasi untuk environment ini (bukan karena bukan CLI).
#   * cli_presets.py:162 -> komentar eksplisit: "goose / amp / mods / sgpt /
#     swe-agent / autogpt / phi -> no installable package for this platform
#     under that name (PyPI names belong to unrelated projects; npm ships no
#     android build, ...)".
#   * TERMUX_INSTALL map (cli_presets.py:241-244) hanya berisi "aichat" +
#     "codex" — TIDAK ada entry sgpt. Jadi di Termux pun tak ada rute install
#     terverifikasi.
#   * Cross-check backlog: documents/pm/cli-tools-install-backlog.md:92
#     (C2 sgpt = NO_INSTALL, status todo) + baris 105 (sgpt termasuk 8 tool
#     NO_INSTALL: antigravity, phi, goose, amp, swe-agent, autogpt, sgpt,
#     mods) — konsisten dengan kode di atas.
#
# SUMBER 2 — npm registry + PyPI (https://registry.npmjs.org/sgpt,
#   https://pypi.org/pypi/sgpt/json):
#   * npm "sgpt" ADA tapi adalah SQUAT/placeholder tak terkait:
#       author/maintainer "peidayu" <932422338@qq.com>, description KOSONG,
#       dist-tags latest 0.0.1, versi 0.0.1 (2023-03-28) & 1.0.0, unpackedSize
#       cuma 218 byte, readme "ERROR: No README data found!".
#     Bukan CLI resmi mana pun — murni squat. Memasangnya = sampah.
#   * PyPI "sgpt" -> 404 (https://pypi.org/pypi/sgpt/json mengembalikan
#     status non-2xx/404). Artinya TIDAK ADA package PyPI bernama persis
#     'sgpt'; `pip install sgpt` GAGAL (atau menarik squat tak terkait).
#
# SUMBER 3 — GitHub (https://api.github.com/search/repositories?q=sgpt):
#   * Banyak repo bernama 'sgpt', NAMUN beragam fungsi & bukan "the" sgpt
#     chat assistant yang tunggal:
#       - k8sgpt-ai/k8sgpt  -> tool Kubernetes (8.1k bintang, Go), tak terkait.
#       - Muennighoff/sgpt  -> riset "GPT Sentence Embeddings" (Jupyter,
#         MIT, 872 bintang), BUKAN CLI chat interaktif.
#       - tbckr/sgpt        -> CLI chat/query sungguhan (Go, MIT, 464 bintang):
#         "command-line tool ... interact with OpenAI models, generate shell
#         commands and produce code directly from the terminal." Ini satu-satunya
#         repo 'sgpt' yang memang CLI chat assistant.
#       - malonaz/sgpt, charlesxu90/sgpt, dll -> fork/kloning kecil, tak resmi.
#   * CATATAN TRANSPAREN: repo tbckr/sgpt memang CLI chat sungguhan dan BISA
#     di-install di platform lain (mis. 'go install github.com/tbckr/sgpt@latest'
#     atau unduh binary release). TAPI aigate cli_presets.py:224 MENANDAINYA
#     REASON_INSTALL_UNVERIFIED (belum ada rute install terverifikasi untuk
#     environment ini / Termux-aarch64), dan backlog C2 menetapkannya
#     NO_INSTALL. Sesuai keputusan user untuk tool NO_INSTALL: script HANYA
#     menampilkan pesan lalu KELUAR — tidak memasang paket apa pun (aman,
#     hindari pasang paket salah / squat / tak terkait), meski CLI resmi ada.
# ===========================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

detect_os
detect_pm
load_gateway_config   # aigate gateway base (AIGATE_BASE) + internal key (AIGATE_KEY)

set -euo pipefail

BIN="sgpt"

# --- NO_INSTALL: tidak ada install terverifikasi, keluar dengan aman ---------
log_msg "os=$AIGATE_OS pm=$AIGATE_PM"
log_msg "sgpt: NO_INSTALL — belum ada install terverifikasi di environment ini."
log_msg "  (aigate cli_presets.py:101 menandainya NO_INSTALL; cli_presets.py:224"
log_msg "   LAUNCH_UNSUPPORTED / REASON_INSTALL_UNVERIFIED; TERMUX_INSTALL map"
log_msg "   tidak punya entry ini; backlog cli-tools-install-backlog.md:92 C2 = NO_INSTALL.)"
log_msg "  Registry: npm 'sgpt' adalah squat tak terkait (author peidayu, deskripsi"
log_msg "   kosong, 218 byte) — BUKAN CLI; PyPI 'sgpt' = 404 (tidak ada package,"
log_msg "   'pip install sgpt' gagal). GitHub ada repo 'sgpt' macam-macam (k8sgpt ="
log_msg "   tool Kubernetes; Muennighoff/sgpt = riset embedding) — satu-satunya CLI"
log_msg "   chat sungguhan adalah tbckr/sgpt (Go), tapi aigate belum verifikasi rute"
log_msg "   install-nya untuk platform ini, sehingga tetap NO_INSTALL per keputusan user."
log_msg "  PERINGATAN: script ini TIDAK memasang paket apa pun (menghindari"
log_msg "   pemasangan paket salah / squatted). Jika Anda ingin menjalankan CLI"
log_msg "   chat resmi tbckr/sgpt, pasang secara manual (mis. 'go install"
log_msg "   github.com/tbckr/sgpt@latest' / unduh binary release) lalu jalankan"
log_msg "   biner 'sgpt' langsung — jangan andalkan script ini untuk install."

# Idempoten, tanpa side-effect. Keluar 0 (no-op sesuai desain, bukan error).
exit 0

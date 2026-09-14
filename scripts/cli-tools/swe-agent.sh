#!/usr/bin/env bash
# swe-agent.sh — NO_INSTALL no-op launcher for aigate (Grup B / B2).
#
# ===========================================================================
# HASIL RISET (fact-based, R47+R48 — >=2 sumber independen, TIDAK ASUMSI):
# ---------------------------------------------------------------------------
# SUMBER 1 — KODE aigate (src/backend/cli_presets.py):
#   * cli_presets.py:45  -> NO_INSTALL didefinisikan sebagai
#       "echo 'aigate: no verified install command for this tool'".
#   * cli_presets.py:89  -> {"name":"swe-agent","binary":"swe-agent",
#                            "install": NO_INSTALL}
#     => aigate menandai swe-agent sebagai tool TANPA perintah install
#        terverifikasi (Grup B / Autonomous Agents).
#   * cli_presets.py:216 -> "swe-agent": LaunchSupport(LAUNCH_UNSUPPORTED,
#                            REASON_INSTALL_UNVERIFIED)
#     => aigate sendiri menandai swe-agent sebagai LAUNCH_UNSUPPORTED karena
#        install-nya TIDAK terverifikasi untuk environment ini.
#   * cli_presets.py:162 -> komentar eksplisit: "goose / amp / mods / sgpt /
#     swe-agent / autogpt / phi -> no installable package for this platform
#     under that name (PyPI names belong to unrelated projects; npm ships no
#     android build, ...)".
#   * TERMUX_INSTALL map (cli_presets.py:241-244) hanya berisi "aichat" +
#     "codex" — TIDAK ada entry swe-agent. Jadi di Termux pun tak ada rute
#     install terverifikasi.
#   * Cross-check backlog: documents/pm/cli-tools-install-backlog.md
#     menempatkan swe-agent (B2) dalam grup NO_INSTALL (antigravity, phi,
#     goose, amp, swe-agent, autogpt, sgpt, mods) — konsisten dengan kode di
#     atas.
#
# SUMBER 2 — PyPI (https://pypi.org/pypi/swe-agent/json, nama biner persis):
#   * "swe-agent" (dengan tanda hubung) -> 404, TIDAK ADA sebagai project
#     PyPI. Jadi `pip install swe-agent` GAGAL / malah bisa menarik paket
#     squat tak terkait.
#   * NUANSA: paket resmi Princeton memang ADA, tapi nama PyPI-nya
#     `sweagent` (TANPA tanda hubung): https://pypi.org/pypi/sweagent/json
#     - author "John Yang" (johny-nlp), homepage https://swe-agent.com,
#       summary "The official SWE-agent package".
#     - HANYA satu rilis yg pernah dipublikasikan: v0.0.1 (2024-04-02),
#       sejak itu tidak diperbarui di PyPI (SWE-agent sekarang sudah 1.0+ &
#       pengembangan utama bergeser ke mini-swe-agent).
#     - requires_dist menyertakan `docker` + `swebench>=1.0.1` + `openai>=1.0`
#       + `anthropic` dll — TIDAK ada console_script / [project.scripts] yang
#       menghasilkan biner `swe-agent`. Paket ini adalah LIBRARY (jalankan
#       via `python run.py`), BUKAN CLI biner. `pip install sweagent` tidak
#       memberi perintah `swe-agent` di PATH.
#
# SUMBER 3 — GitHub resmi (https://github.com/SWE-agent/SWE-agent, README):
#   * Cara install resmi BERAT & butuh environment khusus:
#       1. Install Docker, lalu jalankan Docker lokal.
#       2. Install Miniconda, lalu `conda env create -f environment.yml`.
#       3. `conda activate swe-agent`.
#       4. `./setup.sh` untuk membangun image docker `intercode-swe`.
#       5. Isi `keys.cfg` (OPENAI_API_KEY / ANTHROPIC_API_KEY / GITHUB_TOKEN).
#     Jalankan via `python run.py --model_name gpt4 --data_path <github issue>`
#     — yaitu skrip Python, BUKAN biner CLI `swe-agent`.
#   * Docker + conda TIDAK praktis di Termux/aarch64 (Docker tidak tersedia,
#     conda berat di ARM Android). Sesuai dengan klaim aigate "no installable
#     package for this platform under that name".
#   * Catatan: README menyatakan mini-swe-agent sudah menggantikan SWE-agent
#     sebagai rekomendasi utama — pengembangan aktif SWE-agent 1.0 bergeser ke
#     sana.
#
# CROSS-CHECK: ketiga sumber konsisten — aigate menandai swe-agent NO_INSTALL
#   + LAUNCH_UNSUPPORTED(REASON_INSTALL_UNVERIFIED), dan TERMUX_INSTALL tidak
#   punya entry ini; PyPI dengan nama biner persis `swe-agent` = 404 (squat/
#   tidak ada), sedangkan paket resmi `sweagent` memang ADA tapi hanya v0.0.1
#   (2024) berupa LIBRARY berat (butuh Docker+conda, tidak menghasilkan biner
#   `swe-agent`); README GitHub mengonfirmasi setup Docker+conda yang tidak
#   praktis di Termux/android-arm64. Konklusi: swe-agent memang TIDAK punya
#   install terverifikasi di environment ini -> sesuai grup NO_INSTALL.
#   CATATAN transparan: ada paket PyPI resmi (`sweagent`, library) untuk
#   ekosistem Python umum, TAPI itu BUKAN CLI biner `swe-agent` dan butuh
#   Docker/conda -> tetap TIDAK terverifikasi untuk Termux/android-arm64.
#   Sesuai keputusan user untuk tool NO_INSTALL: script HANYA menampilkan
#   pesan lalu KELUAR — tidak memasang paket apa pun (aman, hindari pasang
#   paket salah / squat / tak terkait).
# ===========================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

detect_os
detect_pm
load_gateway_config   # aigate gateway base (AIGATE_BASE) + internal key (AIGATE_KEY)

set -euo pipefail

BIN="swe-agent"

# --- NO_INSTALL: tidak ada install terverifikasi, keluar dengan aman ---------
log_msg "os=$AIGATE_OS pm=$AIGATE_PM"
log_msg "swe-agent: NO_INSTALL — belum ada install terverifikasi di environment ini."
log_msg "  (aigate cli_presets.py:89 menandainya NO_INSTALL; cli_presets.py:216"
log_msg "   LAUNCH_UNSUPPORTED / REASON_INSTALL_UNVERIFIED; TERMUX_INSTALL map"
log_msg "   tidak punya entry ini.)"
log_msg "  Registry PyPI: nama biner persis 'swe-agent' -> 404 (tidak ada project;"
log_msg "   'pip install swe-agent' akan gagal / menarik squat tak terkait). Paket"
log_msg "   resmi Princeton benar-benar ADA tapi bernama 'sweagent' (tanpa hubung):"
log_msg "   hanya v0.0.1 (2024-04-02), berupa LIBRARY (jalankan via 'python"
log_msg "   run.py'), butuh Docker + conda, dan TIDAK menghasilkan biner 'swe-agent'"
log_msg "   di PATH. GitHub README resmi: install butuh Docker + Miniconda + conda"
log_msg "   env + ./setup.sh image docker -> berat & tidak praktis di Termux/aarch64."
log_msg "  PERINGATAN: script ini TIDAK memasang paket apa pun (menghindari"
log_msg "   pemasangan paket salah / squat / tak terkait). Jika Anda punya cara"
log_msg "   install resmi SWE-agent (mis. pip install sweagent + setup Docker/conda"
log_msg "   di Linux/macOS) dan ingin menjalankannya, pasang + jalankan secara manual"
log_msg "   (via 'python run.py ...') — jangan andalkan script ini untuk install di"
log_msg "   Termux/android."

# Idempoten, tanpa side-effect. Keluar 0 (no-op sesuai desain, bukan error).
exit 0

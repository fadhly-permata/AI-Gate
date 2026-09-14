#!/usr/bin/env bash
# crewai.sh — UNSUPPORTED (NOT_A_CLI) no-op launcher for aigate (Grup B / B6).
#
# ===========================================================================
# HASIL RISET (fact-based, R47+R48 — >=2 sumber independen, TIDAK ASUMSI):
# ---------------------------------------------------------------------------
# SUMBER 1 — KODE aigate (src/backend/cli_presets.py + cli_tools_router.py):
#   * cli_presets.py:93  -> {"name":"crewai","binary":"crewai",
#                            "install": _pip("crewai")}
#     => aigate memang punya perintah install terverifikasi: "pip install
#        crewai". Ini BUKAN NO_INSTALL seperti autogpt/swe-agent.
#   * cli_presets.py:205-215 -> "crewai": LaunchSupport(LAUNCH_UNSUPPORTED,
#                            REASON_NOT_A_CLI). Komentar asli aigate:
#        "NOT A LAUNCHABLE ASSISTANT: the `crewai` console script exists
#         (lib/crewai/pyproject.toml [project.scripts]), but it is a framework
#         project scaffolder/runner: `crewai run` runs the Crew/Flow DEFINED BY
#         THE PROJECT in the CWD (docs: 'Make sure to run these commands from
#         the directory where your CrewAI project is set up'), and `crewai chat`
#         is an interactive session with THAT crew (crew_chat.run_chat ->
#         read_toml() + load_crew_and_name()). Neither takes a
#         model/base-url/prompt at launch — the OpenAI-compatible route
#         (LLM(model='openai/<id>', base_url=...)) is Python code inside the
#         generated project, not a CLI surface. In an empty directory both
#         error out."
#     => aigate sendiri menandai crewai LAUNCH_UNSUPPORTED karena BUKAN CLI yang
#        bisa di-spawn sebagai asisten (alasan NOT_A_CLI), bukan karena tidak
#        terinstall.
#   * cli_tools_router.py -> _LAUNCH_BUILDERS (baris ~976-988) TIDAK punya entry
#     "crewai" dan TIDAK ada _crewai_builder. (Diverifikasi via grep: satu-
#     satunya kemunculan "crewai" di src/** adalah di cli_presets.py
#     baris 93/205-215.) Maka resolve_cli_tool() (baris ~1059-1066) memasuki
#     cabang support.mode != LAUNCH_VERIFIED dan mengembalikan 409
#     tool_unsupported — aigate MENOLAK membangun perintah launch apa pun.
#   * Karena tidak ada builder, env {OPENAI_API_BASE, OPENAI_API_KEY} (router
#     baris ~1081-1084, base default http://localhost:8080/v1) TIDAK PERNAH
#     sampai ke crewai. Konklusi kode: crewai tidak di-launch.
#
# SUMBER 2 — PyPI (https://pypi.org/pypi/crewai/json, metadata resmi):
#   * name: crewai ; version: 1.15.20 ; summary: "Cutting-edge framework for
#     orchestrating role-playing, autonomous AI agents." ; requires_python:
#     ">=3.10,<3.14" ; project_urls.Repository: github.com/crewAIInc/crewAI.
#   * Wheel crewai-1.15.20-py3-none-any.whl -> dist-info/entry_points.txt:
#        [console_scripts]
#        crewai = crewai_cli.cli:crewai
#     => "pip install crewai" memasang PAKET ASLI & menghasilkan biner "crewai"
#        di PATH (install _pip("crewai") dari aigate VALID). Ini framework +
#        CLI project scaffolder, bukan asisten CLI interaktif yang bisa di-host
#     sebagai PTY oleh gateway aigate.
#   => PyPI setuju: paket ASLI & terinstall via pip, menghasilkan biner
#      "crewai" (sejalan dengan _pip("crewai")), TAPI biner itu adalah
#      scaffolder/runner framework, bukan chat assistant.
#
# SUMBER 3 — Dokumentasi resmi + GitHub (docs.crewai.com Quickstart,
#   github.com/crewAIInc/crewAI):
#   * Quickstart: "Prerequisites ... the CrewAI CLI (see installation)". Perintah
#     CLI proyek: "crewai create flow <nama>", "crewai install", "crewai run",
#     "crewai chat", "crewai login", "crewai deploy create" dll.
#   * "crewai run" mengeksekusi Flow/Crew YANG DIDEKLARESIKAN DI PROYEK di CWD;
#     "crewai chat" adalah sesi interaktif dengan crew proyek tersebut (membaca
#     config TOML di CWD). Keduanya TIDAK menerima argumen model/base-url/
#     prompt di launch — konfigurasi LLM (OpenAI-compatible) ditulis di Python
#     kode proyek via LLM(model="openai/<id>", base_url=..., api_key=...) atau
#     env OPENAI_API_KEY / OPENAI_API_BASE_URL, BUKAN surface CLI.
#   * Env (dokumentasi): OPENAI_API_KEY + SERPER_API_KEY (web search); model
#     provider di-set di kode proyek, bukan flag CLI.
#   => Dokumentasi resmi mengonfirmasi: crewai memang punya CLI biner, TAPI CLI
#      itu adalah framework project scaffolder/runner yang butuh proyek di CWD
#      dan menaruh konfigurasi model di kode — tidak ada surface CLI interaktif
#      generik yang bisa di-wire ke gateway aigate (/v1/chat/completions).
#
# CROSS-CHECK: ketiga sumber KONSISTEN — aigate menandai crewai
#   LAUNCH_UNSUPPORTED/REASON_NOT_A_CLI dan resolve() 409 (tidak ada builder di
#   router); PyPI membenarkan paket asli v1.15.20 terinstall via "pip install
#   crewai" dan menghasilkan biner "crewai" (entry_points console_scripts), TAPI
#   biner itu scaffolder/runner framework; docs resmi menunjukkan perintah
#   "crewai create/install/run/chat/deploy" yang beroperasi pada proyek di CWD
#   dengan konfigurasi model di kode, bukan CLI chat interaktif generik.
#   Konklusi: sesuai task, untuk kasus NOT_A_CLI -> tampilkan pesan + exit 0
#   (tidak memasang/meluncurkan apa pun). CATATAN transparan: berbeda dengan
#   autogpt/swe-agent (yang NO_INSTALL), crewai PUNYA install terverifikasi
#   (pip, menghasilkan biner "crewai"), namun tetap tidak bisa di-launch karena
#   sifatnya framework scaffolder/runner (NOT_A_CLI). Script ini sengaja TIDAK
#   menjalankan "pip install crewai" atau "crewai run/chat" agar tidak
#   memasang/menjalankan sesuatu yang tidak bisa di-host sebagai CLI aigate.
# ===========================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

detect_os
detect_pm
load_gateway_config   # aigate gateway base (AIGATE_BASE) + internal key (AIGATE_KEY)

set -euo pipefail

BIN="crewai"

# --- UNSUPPORTED / NOT_A_CLI: ada biner, tapi bukan CLI yang bisa di-launch ---
log_msg "os=$AIGATE_OS pm=$AIGATE_PM"
if have_cmd "$BIN"; then
  log_msg "crewai: biner 'crewai' TERDETEKSI di PATH (hasil 'pip install crewai')."
else
  log_msg "crewai: biner 'crewai' BELUM terpasang (install terverifikasi: pip install crewai)."
fi
log_msg "crewai: UNSUPPORTED (REASON_NOT_A_CLI) — bukan CLI asisten yang bisa di-launch di aigate."
log_msg "  (aigate cli_presets.py:93 menandainya install _pip('crewai') — install VALID; tapi"
log_msg "   cli_presets.py:205-215 menandainya LAUNCH_UNSUPPORTED / REASON_NOT_A_CLI; router"
log_msg "   cli_tools_router.py TIDAK punya _crewai_builder di _LAUNCH_BUILDERS, sehingga"
log_msg "   resolve() mengembalikan 409 tool_unsupported — aigate sendiri menolak launch.)"
log_msg "  PyPI: paket crewai ASLI & terinstall via 'pip install crewai' (v1.15.20,"
log_msg "   requires_python >=3.10,<3.14, repo github.com/crewAIInc/crewAI). Wheel"
log_msg "   entry_points.txt: '[console_scripts] crewai = crewai_cli.cli:crewai' -> pip"
log_msg "   install menghasilkan biner 'crewai' di PATH. TAPI biner itu adalah framework"
log_msg "   project scaffolder/runner, bukan chat assistant."
log_msg "  Docs resmi (docs.crewai.com Quickstart + github.com/crewAIInc/crewAI): perintah"
log_msg "   'crewai create flow / install / run / chat / login / deploy' beroperasi pada"
log_msg "   PROYEK di CWD; 'crewai chat'/'run' membaca config crew di direktori tersebut dan"
log_msg "   TIDAK menerima argumen model/base-url/prompt di launch. Konfigurasi LLM"
log_msg "   (OpenAI-compatible) ditulis di kode proyek via LLM(model='openai/<id>',"
log_msg "   base_url=..., api_key=...) atau env OPENAI_API_KEY / OPENAI_API_BASE_URL — BUKAN"
log_msg "   surface CLI. Tidak ada biner chat interaktif generik untuk di-wire ke gateway"
log_msg "   aigate ($AIGATE_BASE)."
log_msg "  PERINGATAN: script ini TIDAK memasang/menjalankan apa pun (menghindari pasang"
log_msg "   paket/scaffold proyek yang tak bisa di-launch, atau menjalankan 'crewai run/chat'"
log_msg "   yang butuh proyek di CWD). Jika ingin pakai CrewAI sbg framework, pasang +"
log_msg "   jalankan manual di luar aigate: 'pip install crewai', lalu 'crewai create flow"
log_msg "   <nama>', 'crewai install', 'crewai run' di dalam direktori proyek Anda (set"
log_msg "   OPENAI_API_KEY / base_url di kode LLM). Gateway aigate siap di $AIGATE_BASE bila"
log_msg "   nanti ada wrapper CLI resmi yang bisa di-host sebagai PTY interaktif."

# Idempoten, tanpa side-effect. Keluar 0 (no-op sesuai desain, bukan error).
exit 0

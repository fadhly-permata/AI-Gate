#!/usr/bin/env bash
# gpt-researcher.sh — UNSUPPORTED (NOT_A_CLI) no-op launcher for aigate (Grup B / B5).
#
# ===========================================================================
# HASIL RISET (fact-based, R47+R48 — >=2 sumber independen, TIDAK ASUMSI):
# ---------------------------------------------------------------------------
# SUMBER 1 — KODE aigate (src/backend/cli_presets.py + cli_tools_router.py):
#   * cli_presets.py:92  -> {"name":"gpt-researcher","binary":"gpt-researcher",
#                            "install": _pip("gpt-researcher")}
#     => aigate memang punya perintah install terverifikasi: "pip install
#        gpt-researcher". Ini BUKAN NO_INSTALL seperti autogpt/swe-agent.
#   * cli_presets.py:197-204 -> "gpt-researcher": LaunchSupport(LAUNCH_UNSUPPORTED,
#                            REASON_NOT_A_CLI). Komentar asli:
#        "NOT A CLI: pip install gpt-researcher ships a library + web-app backend
#         only — no console script (pyproject [project] has no [project.scripts],
#         setup.py has no entry_points; README's pip section shows
#         'import GPTResearcher' usage only). The docs' 'Run with CLI' page is a
#         repo-checkout script (python cli.py "<query>" --report_type ...),
#         requires a query and exits after writing a report file — no binary to
#         spawn and no interactive chat."
#     => aigate sendiri menandai gpt-researcher LAUNCH_UNSUPPORTED karena BUKAN
#        CLI yang bisa di-spawn (alasan NOT_A_CLI), bukan karena tidak terinstall.
#   * cli_tools_router.py -> _LAUNCH_BUILDERS (baris ~976-988) TIDAK punya entry
#     "gpt-researcher" dan TIDAK ada _gpt_researcher_builder. (Diverifikasi via
#     grep: satu-satunya kemunculan "gpt-researcher" di src/** adalah di
#     cli_presets.py baris 92/197/204.) Maka resolve_cli_tool() (baris ~1059-1066)
#     memasuki cabang support.mode != LAUNCH_VERIFIED dan mengembalikan 409
#     tool_unsupported — aigate MENOLAK membangun perintah launch apa pun.
#   * Karena tidak ada builder, env {OPENAI_API_BASE, OPENAI_API_KEY} (router
#     baris ~1081-1084, base default http://localhost:8080/v1) TIDAK PERNAH
#     sampai ke gpt-researcher. Konklusi kode: gpt-researcher tidak di-launch.
#
# SUMBER 2 — PyPI (https://pypi.org/pypi/gpt-researcher/json, metadata resmi):
#   * name: gpt-researcher ; version: 0.16.0 ; author: Assaf Elovic
#     (home https://github.com/assafelovic/gpt-researcher).
#   * requires_python: ">=3.12".
#   * Metadata TIDAK mengandung console_scripts / [project.scripts] /
#     entry_points (pencarian regex "console_scripts|entry_points|EntryPoint|
#     [project.scripts]" pada JSON PyPI = 0 hit). Artinya "pip install
#     gpt-researcher" memasang LIBRARY dan TIDAK menghasilkan biner
#     "gpt-researcher" di PATH. Dependensi-nya (litellm, langchain, openai,
#     fastapi, duckduckgo-search, dll) mengonfirmasi ini paket Python agen,
#     bukan CLI biner.
#   => PyPI setuju: paket ASLI & terinstall, TAPI tanpa biner CLI.
#
# SUMBER 3 — Dokumentasi resmi + GitHub (github.com/assafelovic/gpt-researcher,
#   README + docs.gptr.dev):
#   * README "Run as PIP package": "pip install gpt-researcher" lalu pemakaian
#     via "from gpt_researcher import GPTResearcher" (LIBRARY, bukan CLI).
#   * README env vars: "export OPENAI_API_KEY=..." dan "export TAVILY_API_KEY=..."
#     ; untuk custom OpenAI-compatible API: "export OPENAI_BASE_URL=...".
#     Server mode butuh "git clone" + "python -m uvicorn main:app --reload"
#     (atau Docker "docker-compose up --build") — BUKAN biner tunggal.
#   * docs.gptr.dev/docs/gpt-researcher/gptr/pip-package: sama — "from
#     gpt_researcher import GPTResearcher", env OPENAI_API_KEY / TAVILY_API_KEY.
#   * docs.gptr.dev/docs/gpt-researcher/getting-started/cli ("Run with CLI"):
#     butuh "git clone" + "pip install -r requirements.txt", lalu
#     "python cli.py <query> --report_type <report_type>" — wajib argumen query
#     POSISIONAL, menulis file report ke direktori outputs lalu EXIT. BUKAN
#     chat interaktif yang bisa di-host PTY aigate.
#   => Dokumentasi resmi mengonfirmasi: gpt-researcher memang OpenAI-compatible
#      (OPENAI_API_KEY + OPENAI_BASE_URL), TAPI bentuknya library + one-shot
#      script + web-app backend — tidak ada biner CLI interaktif untuk di-wire
#      ke gateway aigate (/v1/chat/completions).
#
# CROSS-CHECK: ketiga sumber KONSISTEN — aigate menandai gpt-researcher
#   LAUNCH_UNSUPPORTED/REASON_NOT_A_CLI dan resolve() 409 (tidak ada builder di
#   router); PyPI membenarkan paket asli v0.16.0 terinstall via pip TAPI tanpa
#   console script (tidak ada biner gpt-researcher); docs resmi menunjukkan
#   pemakaian library (import GPTResearcher) + one-shot python cli.py yang butuh
#   query & exit, bukan CLI interaktif. gpt-researcher memang OpenAI-compatible,
#   TAPI TIDAK punya biner CLI yang bisa di-spawn aigate di environment ini.
#   Konklusi: sesuai task, untuk kasus NO_INSTALL/UNSUPPORTED -> tampilkan pesan
#   + exit 0 (tidak memasang/meluncurkan apa pun). CATATAN transparan: berbeda
#   dengan autogpt/swe-agent (yang NO_INSTALL), gpt-researcher PUNYA install
#   terverifikasi (pip), namun tetap tidak bisa di-launch karena sifatnya
#   library/one-shot (NOT_A_CLI). Script ini sengaja TIDAK menjalankan
#   "pip install" atau "python cli.py" agar tidak memasang/menjalankan sesuatu
#   yang tidak bisa di-host sebagai CLI aigate.
# ===========================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

detect_os
detect_pm
load_gateway_config   # aigate gateway base (AIGATE_BASE) + internal key (AIGATE_KEY)

set -euo pipefail

BIN="gpt-researcher"

# --- UNSUPPORTED / NOT_A_CLI: tidak ada biner CLI yang bisa di-launch ---------
log_msg "os=$AIGATE_OS pm=$AIGATE_PM"
log_msg "gpt-researcher: UNSUPPORTED (REASON_NOT_A_CLI) — bukan CLI yang bisa di-launch di aigate."
log_msg "  (aigate cli_presets.py:204 menandainya LAUNCH_UNSUPPORTED / REASON_NOT_A_CLI; router"
log_msg "   cli_tools_router.py TIDAK punya _gpt_researcher_builder di _LAUNCH_BUILDERS, sehingga"
log_msg "   resolve() mengembalikan 409 tool_unsupported — aigate sendiri menolak launch.)"
log_msg "  PyPI: paket gpt-researcher ASLI & terinstall via 'pip install gpt-researcher'"
log_msg "   (v0.16.0, author Assaf Elovic, requires_python >=3.12). Metadata PyPI TIDAK punya"
log_msg "   [project.scripts]/console_scripts/entry_points -> pip install TIDAK menghasilkan"
log_msg "   biner 'gpt-researcher' di PATH. Ini LIBRARY: pemakaian via"
log_msg "   'from gpt_researcher import GPTResearcher'."
log_msg "  Docs resmi (github.com/assafelovic/gpt-researcher + docs.gptr.dev): 'Run with CLI'"
log_msg "   butuh 'git clone' + 'pip install -r requirements.txt' + 'python cli.py <query>"
log_msg "   --report_type <type>' — wajib argumen query, menulis file report lalu EXIT (bukan"
log_msg "   chat interaktif). Server mode butuh 'python -m uvicorn main:app' / Docker."
log_msg "  Env (bila dipakai sbg library): OPENAI_API_KEY + TAVILY_API_KEY; base URL custom via"
log_msg "   OPENAI_BASE_URL. Memang OpenAI-compatible, TAPI tidak ada biner CLI untuk di-wire ke"
log_msg "   gateway aigate ($AIGATE_BASE)."
log_msg "  PERINGATAN: script ini TIDAK memasang/menjalankan apa pun (menghindari pasang paket"
log_msg "   yg tak bisa di-launch, atau menjalankan one-shot script yg wajib argumen query)."
log_msg "   Jika ingin pakai gpt-researcher sbg library/web-app, pasang + jalankan manual di luar"
log_msg "   aigate (pip install gpt-researcher, lalu import GPTResearcher atau python -m uvicorn"
log_msg "   main:app). Gateway aigate siap di $AIGATE_BASE bila nanti ada wrapper CLI resmi."

# Idempoten, tanpa side-effect. Keluar 0 (no-op sesuai desain, bukan error).
exit 0

#!/usr/bin/env bash
# open-interpreter.sh — install + launch Open Interpreter (Grup B / B3) for aigate.
#
# Source of truth: documents/pm/cli-tools-install-backlog.md (B3);
# aigate preset:  src/backend/cli_presets.py
#                   - line 90 : install _pip("open-interpreter") -> `pip install open-interpreter`
#                               binary "interpreter"
#                   - line 196: "open-interpreter": LaunchSupport(LAUNCH_VERIFIED)
# launch builder: src/backend/cli_tools_router.py _interpreter_builder (line 824)
#
# =============================== FACT-BASED (R47/R48) ===============================
# Every claim below is cross-checked across >=2 independent sources.
#
# [S1] aigate code (authoritative for the launch form):
#   - src/backend/cli_presets.py:90  -> name "open-interpreter", binary "interpreter",
#                                      install = `pip install open-interpreter`
#   - src/backend/cli_presets.py:196 -> open-interpreter = LAUNCH_VERIFIED
#                                      (NOT NO_INSTALL, NOT LAUNCH_UNSUPPORTED)
#   - src/backend/cli_tools_router.py:767-837 -> the launch builder is
#     `_interpreter_builder` (registered under binary_name "interpreter" at line 985).
#     It emits EXACTLY:
#       interpreter --api_base <base> --api_key <key> [ --model openai/<raw_model> ]
#     where:
#       <base> = gateway base url (also injected as OPENAI_API_BASE; default
#                http://localhost:8080/v1 — see DEFAULT_GATEWAY_BASE)
#       <key>  = plaintext internal key (also injected as OPENAI_API_KEY; default
#                "aigate-local" — PLACEHOLDER_API_KEY when no access-controlled
#                Endpoint exists; gateway ignores it while access control is off)
#       --model is OPTIONAL: skipped when no raw model is chosen (mirrors the
#       documented LM-Studio form `interpreter --api_base "..." --api_key "fake_key"`
#       WITHOUT --model).
#     The env injected for every tool (cli_tools_router.py:1081-1084) is
#       OPENAI_API_BASE=<base>   OPENAI_API_KEY=<key>
#   - Cross-check inside [S1]: cli_tools_router.py:1079-1084 confirm the gateway
#     exposes an OpenAI-compatible endpoint; the gateway's /v1/chat/completions is
#     what `--api_base` points at, and /v1/models is served (reachability probe).
#
# [S2] PyPI registry (https://pypi.org/pypi/open-interpreter/json, fetched):
#   - name=open-interpreter, version=0.4.3, summary="Let language models run code"
#   - requires_python = "<4,>=3.9"  -> installs on Python 3.9-3.13 incl. THIS host's
#     3.14.6 (3.14 < 4). The frozen Python release (the repo has since moved on to a
#     different, Rust/Codex-fork product — see KNOWN-BROKEN below).
#   - README (the Python project's own 0.4.3 README, embedded in the PyPI JSON)
#     CONFIRMS the same launch form:
#       `pip install open-interpreter`  +  run `interpreter`
#       `interpreter --api_base "http://localhost:1234/v1" --api_key "fake_key"`
#         (any OpenAI-compatible server — LM Studio example)
#       `interpreter --model gpt-3.5-turbo`  (+ claude-2, command-nightly...)
#       `interpreter.llm.model = "openai/x"`  # "Tells OI to send messages in
#                                              # OpenAI's format"
#     => exactly the `--api_base` / `--api_key` / `--model` flags [S1] uses, with the
#        `openai/<id>` model prefix the builder prepends.
#
# [S3] Official Open Interpreter docs / GitHub (docs.openinterpreter.com):
#   - CAVEAT: the LIVE docs site (and the openinterpreter/open-interpreter GitHub
#     repo) have been REWRITTEN for a NEW Rust/Codex-fork product ("built on top of
#     Codex", no --api_base/--api_key flags, `curl` installer). That is NOT the
#     `pip install open-interpreter` Python package this preset installs. [S1]'s own
#     comment (cli_tools_router.py:770-772, 774) documents this divergence and
#     verifies the Python launch form against the Python project's docs + the PyPI
#     0.4.3 README. We therefore treat [S2] (PyPI README = the Python project's own
#     docs for 0.4.3) as the upstream external confirmation, and DO NOT trust the
#     rewritten live site for the Python-package flags.
#   - The [S1] comment further records the alternate (current Rust) route, which we
#     deliberately do NOT use: the aigate preset installs the Python package, so the
#     Python `--api_base/--api_key` form is the contract.
#
# CROSS-CHECK RESULT: open-interpreter in aigate = VERIFIED (LAUNCH_VERIFIED),
#   NOT NO_INSTALL and NOT UNSUPPORTED. It is OpenAI-compatible (the gateway's
#   /v1/chat/completions), wired via `--api_base`/`--api_key` flags (plus the
#   OPENAI_API_BASE/OPENAI_API_KEY env) to the aigate gateway base/key. No
#   anthropic-only / responses-only / not-a-cli blocker.
#
# =============================== INSTALL (verified) ===============================
# `python3 -m pip install open-interpreter`  [S1 preset / S2 PyPI]
#   Pure-Python wheel (py3-none-any class), requires_python <4,>=3.9 — installs on
#   Termux / Linux / macOS / Windows(WSL). Binary lands as `interpreter`.
#   Pin 0.4.3 implicitly (last Python release); `pip install open-interpreter` pulls
#   it. The `--upgrade` is omitted on purpose so an existing install is idempotent
#   (ensure_installed short-circuits when `interpreter` is already on PATH).
#
# =============================== KNOWN-BROKEN CAVEAT (with evidence) ===============================
# * Product drift (NOT a platform bug, but must be known): the live
#   docs.openinterpreter.com + the openinterpreter/open-interpreter GitHub repo now
#   describe a DIFFERENT Rust/Codex-fork product (no --api_base/--api_key). The
#   `pip install open-interpreter` package (0.4.3, Python) is the frozen community
#   Python line. Evidence: [S3] live site copy ("built on top of Codex") vs [S1]
#   cli_tools_router.py:770-772 comment + [S2] PyPI 0.4.3 README (Python flags).
#   This script installs the Python package and uses its flags — correct per the
#   aigate preset. Do NOT follow the live site's `curl install.sh`; that fetches the
#   wrong (Rust) product.
# * Python version: PyPI requires_python = "<4,>=3.9" [S2]. THIS host is Python
#   3.14.6 (`python3 -V` => Python 3.14.6), which satisfies `<4`, so the pip resolver
#   succeeds here (contrast openhands which pins ==3.12.* and fails on 3.14). No
#   version blocker on this device.
# * Heavy optional deps: open-interpreter pulls a large dependency tree (litellm,
#   pandas, playwright, etc.); a fresh `pip install` can be slow on Termux/arm64 but
#   is not a hard failure. The script installs on demand; if a transitive build fails
#   the launch aborts with a clear message (ensure_installed returns non-zero).
#
# Configure via env (defaults from aigate gateway config via _common.sh):
#   AIGATE_MODEL   optional; forwarded to interpreter as --model openai/<AIGATE_MODEL>
#                  (must match a gateway-served model id). Without it, interpreter
#                  launches with its own default model; base+key still point at aigate.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

detect_os
detect_pm
load_gateway_config   # aigate gateway base (AIGATE_BASE) + internal key (AIGATE_KEY)

BIN="interpreter"

log_msg "os=$AIGATE_OS pm=$AIGATE_PM gateway_base=$AIGATE_BASE"

# --- Idempotent install (never reinstalls when already present) ------------------
# Faithful to the aigate preset (cli_presets.py:90) and the PyPI package [S2].
INSTALL_CMD=(python3 -m pip install open-interpreter)

if ! ensure_installed "$BIN" "${INSTALL_CMD[@]}"; then
  log_msg "could not install $BIN on this platform; aborting launch."
  log_msg "HINT: requires_python is <4,>=3.9 (PyPI [S2]); ensure a Python 3.9-3.13+"
  log_msg "      interpreter is active and pip can reach the index. Do NOT use the"
  log_msg "      live docs' curl installer — it installs the unrelated Rust product."
  exit 1
fi

# pip user installs land in ~/.local/bin (or $XDG_BIN_HOME / $HOME/.cargo/bin on
# some setups); make sure that dir is on PATH before the launch check / exec.
for _d in "${HOME:-}/.local/bin" "${HOME:-}/.cargo/bin"; do
  case ":$PATH:" in
    *":$_d:"*) ;;
    *) [ -d "$_d" ] && PATH="$_d:$PATH" ;;
  esac
done
export PATH
# Re-validate now that PATH may include the install dir.
if ! have_cmd "$BIN"; then
  log_msg "WARN: $BIN not found on PATH after install (install dir may differ); launch may fail."
fi

# --- open-interpreter -> aigate wiring (OpenAI-compatible via --api_base/--api_key) ----
# Best-effort reachability check (tolerate missing curl). aigate exposes a
# non-auth GET /v1/models; only a hard connect/timeout failure warns.
if have_cmd curl; then
  if ! curl -fsS -o /dev/null --max-time 3 "${AIGATE_BASE}/models" 2>/dev/null; then
    rc=$?
    if [ "$rc" -eq 7 ] || [ "$rc" -eq 28 ]; then
      log_msg "WARN: aigate not reachable at $AIGATE_BASE (check gateway_base_url / is aigate running?);"
      log_msg "      open-interpreter will fail to connect. Start aigate first if it is not running."
    fi
  fi
fi

# Env injection every tool gets (cli_tools_router.py:1081-1084).
export OPENAI_API_BASE="$AIGATE_BASE"
export OPENAI_API_KEY="$AIGATE_KEY"

# Model flag — mirrors _interpreter_builder (cli_tools_router.py:824-837) EXACTLY:
#   --model openai/<raw>  when a model is chosen; omitted otherwise (the documented
#   LM-Studio / OpenAI-compatible form runs fine without --model).
AIGATE_MODEL="${AIGATE_MODEL:-}"
MODEL_FLAG=()
if [ -n "$AIGATE_MODEL" ]; then
  MODEL_FLAG=(--model "openai/${AIGATE_MODEL}")
  log_msg "preselected model: openai/${AIGATE_MODEL}"
fi

log_msg "launching $BIN via aigate (OpenAI-compatible endpoint ${AIGATE_BASE}/chat/completions)"
# Bare `interpreter` opens the interactive Terminal chat (PyPI README [S2]; the
# aigate builder emits no positional prompt either).
exec "$BIN" --api_base "$AIGATE_BASE" --api_key "$AIGATE_KEY" "${MODEL_FLAG[@]}" "$@"

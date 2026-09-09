#!/usr/bin/env bash
# aider.sh — install + launch aider (Grup A / A7) for aigate.
#
# Source of truth: documents/pm/cli-tools-install-backlog.md (A7);
# launch builder: src/backend/cli_tools_router.py _aider_builder (line 355).
#
# INSTALL: pip install aider-chat   (idempotent via have_cmd; wrapped as
#          `python3 -m pip install aider-chat` for portability across shells).
#   Package facts (verified on PyPI, aider-chat 0.86.2):
#     * Wheel is `aider_chat-0.86.2-py3-none-any.whl` -> pure-python,
#       platform-independent (py3-none-any). Installs with `pip install
#       aider-chat` on Termux / Linux / macOS / Windows(WSL).
#     * requires_python = ">=3.10,<3.13". On Python 3.13+ the resolver FAILS
#       (no compatible wheel). The script now refuses to install on Python
#       <3.10 or >=3.13 (see the version guard near the top) and exits 1 with a
#       clear message instead of a raw pip error. Use a venv / pyenv on 3.10-3.12.
#
# LAUNCH WIRING: aider speaks OpenAI-compatible Chat Completions. aigate serves
#   it natively at /v1/chat/completions (aider appends /chat/completions to the
#   base URL automatically). Chain:
#     aider -> aigate(/v1/chat/completions) -> backend
#
#   Mirrors _aider_builder (cli_tools_router.py:355-369) EXACTLY:
#     aider [flags] --openai-api-base <base> --openai-api-key <key> \
#           [--model openai/<raw_model>]
#   plus the env injection every tool receives (cli_tools_router.py:1081-1084):
#     OPENAI_API_BASE=<base>   OPENAI_API_KEY=<key>
#   The `openai/` model prefix (aider docs, "OpenAI compatible APIs") makes aider
#   accept an arbitrary model name and forward it to aigate, which bare-resolves
#   it (see _aider_builder docstring). aider refuses to start with an empty
#   --openai-api-key (cli_tools_router.py:54,204); load_gateway_config always
#   supplies a key (default "aigate-local"), so this never happens.
#
#   _aider_builder does NOT emit a config file (it uses CLI flags only), so we
#   mirror that here — aider.conf.yml generation is unnecessary.
#
# Configure via env (defaults come from the aigate gateway config via _common.sh):
#   AIGATE_MODEL   optional; forwarded to aider as --model openai/<AIGATE_MODEL>

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

detect_os
detect_pm
load_gateway_config   # aigate gateway base (AIGATE_BASE) + internal key (AIGATE_KEY)

# --- aider / Python version guard (runs BEFORE any pip install) ---
# aider-chat is pure-python but its PyPI requires_python is ">=3.10,<3.13"
# (verified: aider-chat 0.86.2). On Python 3.13+ pip cannot resolve a compatible
# release, and building old pinned deps (e.g. aiohttp 3.8.4 sdist) also fails on
# 3.14. Refuse early with a clear message instead of handing the user a raw pip error.
if have_cmd python3; then
  pyver="$(python3 -c 'import sys;print("%d.%d" % sys.version_info[:2])' 2>/dev/null || true)"
  py_maj="${pyver%%.*}"
  py_min="${pyver#*.}"; py_min="${py_min%%[!0-9]*}"
  if [ -n "$py_maj" ] && [ -n "$py_min" ]; then
    # Supported: Python 3.10, 3.11, 3.12 only.
    if [ "$py_maj" -lt 3 ] || [ "$py_maj" -gt 3 ] || \
       { [ "$py_maj" -eq 3 ] && { [ "$py_min" -lt 10 ] || [ "$py_min" -gt 12 ]; }; }; then
      log_msg "ERROR: aider needs Python 3.10–3.12; this device has Python ${pyver}."
      log_msg "       Install a compatible interpreter (e.g. 'pkg install python3.11',"
      log_msg "       pyenv, or a venv on 3.10–3.12) and re-run this script inside it."
      exit 1
    fi
  else
    log_msg "WARN: could not parse 'python3 --version' (got '${pyver}'); attempting install anyway."
  fi
else
  log_msg "WARN: python3 not found; cannot check Python version before pip install."
fi

BIN="aider"
INSTALL_CMD=(python3 -m pip install aider-chat)

log_msg "os=$AIGATE_OS pm=$AIGATE_PM gateway_base=$AIGATE_BASE"

# Idempotent install (never reinstalls when already present).
if ! ensure_installed "$BIN" "${INSTALL_CMD[@]}"; then
  log_msg "could not install aider on this platform; aborting launch."
  exit 1
fi

# --- aider -> aigate wiring (OpenAI Chat Completions) ----
# Best-effort reachability check (tolerate missing curl). aigate exposes a
# non-auth GET /v1/models (router.py:478); only a hard connect/timeout failure warns.
if have_cmd curl; then
  if ! curl -fsS -o /dev/null --max-time 3 "${AIGATE_BASE}/models" 2>/dev/null; then
    rc=$?
    if [ "$rc" -eq 7 ] || [ "$rc" -eq 28 ]; then
      log_msg "WARN: aigate not reachable at $AIGATE_BASE (check gateway_base_url / is aigate running?);"
      log_msg "      aider will fail to connect. Start aigate first if it is not running."
    fi
  fi
fi

# Env injection (every tool gets these; aider docs confirm the env vars work).
export OPENAI_API_BASE="$AIGATE_BASE"
export OPENAI_API_KEY="$AIGATE_KEY"

AIGATE_MODEL="${AIGATE_MODEL:-}"
MODEL_FLAG=()
if [ -n "$AIGATE_MODEL" ]; then
  MODEL_FLAG=(--model "openai/${AIGATE_MODEL}")
fi

log_msg "launching aider via aigate (openai-compatible endpoint ${AIGATE_BASE}/chat/completions)"
# Mirror _aider_builder: aider --openai-api-base <base> --openai-api-key <key> [--model openai/<model>]
exec "$BIN" --openai-api-base "$AIGATE_BASE" --openai-api-key "$AIGATE_KEY" "${MODEL_FLAG[@]}" "$@"

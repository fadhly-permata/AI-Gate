#!/usr/bin/env bash
# llm.sh — install + launch llm (Grup C / C1) for aigate.
#
# Source of truth:
#   aigate preset:  src/backend/cli_presets.py
#                     - line 100 : install _pip("llm") -> `pip install llm`, bin `llm`
#                     - line 219 : "llm": LaunchSupport(LAUNCH_VERIFIED)
#   launch builder: src/backend/cli_tools_router.py _llm_builder (line 570)
#
# =============================== FACT-BASED (R47/R48) ===============================
# Every claim below is cross-checked across >=2 independent sources.
#
# [S1] aigate code (authoritative for the launch form):
#   - src/backend/cli_presets.py:100 -> install = `pip install llm`, binary = `llm`
#   - src/backend/cli_presets.py:219 -> llm = LAUNCH_VERIFIED (NOT NO_INSTALL/UNSUPPORTED)
#   - src/backend/cli_tools_router.py:570-592 (_llm_builder) -> the documented
#     one-shot form for ANY OpenAI-compatible endpoint:
#       llm openai endpoint <base_url> -m <model> --key <key> --chat
#       (no model chosen -> `llm openai endpoint <base_url> --models`)
#   - src/backend/cli_tools_router.py:1081-1084 -> resolve() injects every tool with
#     env OPENAI_API_BASE=<base>  and  OPENAI_API_KEY=<key>  (ADR-007 plaintext key).
#   - Cross-check: the gateway serves OpenAI-compatible /v1/chat/completions AND
#     /v1/models, which is exactly what `llm openai endpoint <base>` talks to.
#
# [S2] PyPI registry (https://pypi.org/pypi/llm/json, fetched):
#   - name=llm, version=0.35, summary="CLI utility and Python library for interacting
#     with Large Language Models ... OpenAI, Anthropic and Gemini plus local models".
#     This IS Simon Willison's llm (homepage/docs point at github.com/simonw/llm and
#     llm.datasette.io) — NOT an unrelated squatter.
#   - requires_python = ">=3.10"; wheel = llm-0.35-py3-none-any.whl (pure-python,
#     platform-independent).
#   - repo pyproject.toml: [project.scripts] llm = "llm.cli:cli" -> installs binary `llm`.
#
# [S3] Official llm docs (llm.datasette.io, "Other models > Run against an endpoint
#     without configuring it", read 2026-09-09):
#   - `llm openai endpoint https://example.com/v1 -m model-id --key KEY "prompt"` —
#     one-shot, registers nothing, logs nothing.
#   - "This command does not send your configured OpenAI API key to the endpoint.
#     Use --key to explicitly provide a key" -> so the gateway key is passed via --key
#     (matches _llm_builder passing ctx.key through --key).
#   - `llm openai endpoint <base> --models` lists IDs the endpoint advertises
#     (requests <base>/models — the gateway serves GET /v1/models).
#   - `llm openai endpoint <base> -m model-id --chat` starts an interactive chat.
#   => CONFIRMS [S1]'s launch form EXACTLY.
#
# CROSS-CHECK RESULT: llm in aigate = VERIFIED (LAUNCH_VERIFIED), OpenAI-compatible,
#   wired via `llm openai endpoint <AIGATE_BASE> -m <model> --key <AIGATE_KEY> --chat`
#   (or `--models` when no model is chosen). No anthropic-only / responses-only /
#   not-a-cli blocker. The launch form is the upstream-documented OpenAI-compatible
#   endpoint form, not a guessed flag.
#
# =============================== INSTALL (verified) ===============================
# aigate preset [S1] = `pip install llm`. We run it as `python3 -m pip install llm`
# (portable across shells, same convention as aider.sh). Binary `llm` [S2].
#
# =============================== KNOWN-BROKEN CAVEAT (with evidence) ===============================
# * On THIS device (Termux 0.118.3, aarch64, Python 3.14.6) `pip install llm` FAILS.
#   Evidence (a `pip install --dry-run llm` run here): the transitive dependency
#   `jiter` (Rust-based, pulled in via llm's tree) has NO prebuilt wheel for the
#   Termux SOABI cpython-314-aarch64-linux-android (PyPI jiter 0.16.0 publishes 104
#   wheels incl. cp314 manylinux_aarch64, but ZERO android wheels), so pip falls back
#   to the sdist and tries to compile Rust:
#       Target triple not supported by rustup: aarch64-unknown-linux-android
#       Rust not found, installing into a temporary directory
#       ERROR: Failed to build 'jiter' ... maturin
#   `rust`/`rustup`/`cargo` are NOT installed here (command -v returned nothing).
#   Workaround: install a Rust toolchain (pkg install rust / rustup) so the wheel can
#   build, OR run llm from a manylinux environment. This is a platform/wheel
#   availability issue (Android SOABI), NOT a problem with the llm package itself.
# * requires_python >=3.10 [S2] is satisfied by Python 3.14.6, so the Python VERSION
#   is NOT the blocker (unlike openhands ==3.12.*); the blocker is the missing Rust
#   build of jiter for the Android target.
#
# Configure via env (defaults from aigate gateway config via _common.sh):
#   AIGATE_MODEL   optional; forwarded to llm as -m <AIGATE_MODEL> (a gateway-known
#                  model id, e.g. a bare id or a combo: ref). Without it, the script
#                  launches `llm openai endpoint <base> --models` to list what the
#                  gateway advertises. Must match a model the gateway serves.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

detect_os
detect_pm
load_gateway_config   # aigate gateway base (AIGATE_BASE) + internal key (AIGATE_KEY)

BIN="llm"
# Faithful to the aigate preset (`pip install llm`); `python3 -m pip` is portable.
INSTALL_CMD=(python3 -m pip install llm)

log_msg "os=$AIGATE_OS pm=$AIGATE_PM gateway_base=$AIGATE_BASE"

# --- Idempotent install (never reinstalls when already present) -------------------
if ! ensure_installed "$BIN" "${INSTALL_CMD[@]}"; then
  log_msg "could not install $BIN on this platform; aborting launch."
  if [ "$AIGATE_OS" = "termux" ]; then
    log_msg "HINT (Termux aarch64): pip install llm pulls the Rust-based wheel 'jiter'"
    log_msg "      which has no prebuilt wheel for cpython-3.14-aarch64-linux-android;"
    log_msg "      the sdist build fails (no rust/rustup). Install rust or use a python"
    log_msg "      with a manylinux wheel, or run llm from another environment."
  fi
  exit 1
fi

# --- llm -> aigate wiring (OpenAI Chat Completions via `openai endpoint`) ---------
# Best-effort reachability check (tolerate missing curl). aigate exposes a
# non-auth GET /v1/models; only a hard connect/timeout failure warns.
if have_cmd curl; then
  if curl -fsS -o /dev/null --max-time 3 "${AIGATE_BASE}/models" 2>/dev/null; then
    : # gateway reachable
  else
    rc=$?
    if [ "$rc" -eq 7 ] || [ "$rc" -eq 28 ]; then
      log_msg "WARN: aigate not reachable at $AIGATE_BASE (check gateway_base_url / is aigate running?);"
      log_msg "      llm will fail to connect. Start aigate first if it is not running."
    fi
  fi
fi

# Env injection every tool gets (cli_tools_router.py:1081-1084). llm's `openai
# endpoint` does NOT forward the configured OpenAI key, so the key is also passed
# explicitly via --key below (per docs [S3]); both routes mirror the router.
export OPENAI_API_BASE="$AIGATE_BASE"
export OPENAI_API_KEY="$AIGATE_KEY"

AIGATE_MODEL="${AIGATE_MODEL:-}"

if [ -n "$AIGATE_MODEL" ]; then
  log_msg "launching $BIN via aigate (OpenAI-compatible endpoint ${AIGATE_BASE}/chat/completions, model=$AIGATE_MODEL)"
  # Mirror _llm_builder: llm openai endpoint <base> -m <model> --key <key> --chat
  # --key carries the gateway key (docs: command does not send the configured key).
  # Trailing "$@" lets an operator append a prompt or extra flags; with none, the
  # PTY tab keeps the interactive --chat session open.
  exec "$BIN" openai endpoint "$AIGATE_BASE" -m "$AIGATE_MODEL" --key "$AIGATE_KEY" --chat "$@"
else
  log_msg "launching $BIN via aigate (OpenAI-compatible endpoint ${AIGATE_BASE}/chat/completions; listing models)"
  # No model selected -> --models (docs [S3] + _llm_builder). Lists IDs the gateway
  # advertises at GET /v1/models; the operator picks one for a later chat.
  exec "$BIN" openai endpoint "$AIGATE_BASE" --models "$@"
fi

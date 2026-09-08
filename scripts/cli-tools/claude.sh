#!/usr/bin/env bash
# claude.sh — install + launch Claude Code (Grup A / A1) for aigate.
#
# Source of truth: documents/pm/cli-tools-install-backlog.md (A1).
# Install: npm i -g @anthropic-ai/claude-code   (idempotent via have_cmd)
# Launch : Claude Code speaks the *Anthropic Messages* API, not OpenAI-compatible.
#          aigate's cli_tools_router has NO launch builder for claude and returns
#          409 tool_unsupported on resolve() (LAUNCH_SUPPORT: anthropic_only).
#          We therefore launch claude NATIVELY (its own Anthropic config from the
#          user environment) and print a short note — we do NOT fabricate an
#          OpenAI-compatible wiring that does not exist. This mirrors aigate's
#          actual behaviour.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

detect_os
detect_pm
load_gateway_config

BIN="claude"
INSTALL_CMD=(npm i -g @anthropic-ai/claude-code)

log_msg "os=$AIGATE_OS pm=$AIGATE_PM gateway_base=$AIGATE_BASE"

# Idempotent install (never reinstalls when already present).
if ! ensure_installed "$BIN" "${INSTALL_CMD[@]}"; then
  log_msg "could not install claude on this platform; aborting launch."
  exit 1
fi

# Platform caveat: on Termux/aarch64, npm (process.platform == "android") does not
# install the *-linux-arm64 binary, so claude can be installed yet die at runtime.
# We still install (per request) but warn so a runtime crash is not a surprise.
if [ "$AIGATE_OS" = "termux" ]; then
  log_msg "NOTE: on Termux/aarch64 npm may install claude without the arm64 binary;"
  log_msg "      if 'claude' crashes on launch, that is the known npm/Android cause."
fi

# Launch native. The aigate OpenAI gateway is not applicable to claude, so we do
# not export OPENAI_API_BASE / OPENAI_API_KEY to it. Pass any extra args through.
log_msg "launching claude natively (anthropic_only: aigate OpenAI gateway N/A)"
if "$BIN" "$@"; then
  exit 0
else
  status=$?
  log_msg "claude exited with code $status (Termux/arm64 caveat above may apply)"
  exit "$status"
fi

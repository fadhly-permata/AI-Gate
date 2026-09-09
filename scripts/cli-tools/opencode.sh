#!/usr/bin/env bash
# opencode.sh — install + launch opencode (Grup A / A2) for aigate.
#
# Source of truth: documents/pm/cli-tools-install-backlog.md (A2);
# launch builder: src/backend/cli_tools_router.py _opencode_builder (line 377).
#
# INSTALL: npm i -g opencode-ai   (idempotent via have_cmd)
#   Package facts (verified on npm registry, opencode-ai@1.18.29):
#     * Ships NATIVE Go binaries via optionalDependencies, incl.
#       opencode-linux-arm64 and opencode-linux-arm64-musl.
#     * The npm "os" field is ["darwin","linux","win32"] — it does NOT list
#       "android". On Termux, npm reports process.platform == "android", so
#       npm may warn or skip optional deps. The postinstall.mjs script handles
#       binary selection. If npm install fails or the binary is missing after
#       install, the user needs to download the binary directly from GitHub
#       releases (https://github.com/sst/opencode/releases).
#     * Unlike claude-code (which is glibc-linked), opencode ships both glibc
#       and musl variants. The musl variant (opencode-linux-arm64-musl) works
#       on Termux's Bionic libc without proot-distro.
#
# LAUNCH WIRING: opencode speaks OpenAI-compatible Chat Completions via a
#   custom provider configured in opencode.json (see _opencode_builder at
#   cli_tools_router.py:377). aigate serves this natively at /v1/chat/completions.
#
#   The backend builder writes an opencode.json with:
#     - provider "aigate" using npm package @ai-sdk/openai-compatible
#     - options.baseURL = gateway base URL (e.g. http://localhost:8080/v1)
#     - options.apiKey = internal_api_key
#     - model = "aigate/<model_id>"
#
#   This shell script mirrors that wiring via env vars (OPENAI_API_BASE,
#   OPENAI_API_KEY) and generates a minimal opencode.json before exec.
#   Chain: opencode -> aigate(/v1/chat/completions) -> backend
#
# Configure via env (defaults come from the aigate gateway config via _common.sh):
#   AIGATE_MODEL   optional; set as default model in generated opencode.json

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

detect_os
detect_pm
load_gateway_config   # aigate gateway base (AIGATE_BASE) + internal key (AIGATE_KEY)

BIN="opencode"
INSTALL_CMD=(npm i -g opencode-ai)

log_msg "os=$AIGATE_OS pm=$AIGATE_PM gateway_base=$AIGATE_BASE"

# Idempotent install (never reinstalls when already present).
if ! ensure_installed "$BIN" "${INSTALL_CMD[@]}"; then
  log_msg "could not install opencode on this platform; aborting launch."
  exit 1
fi

# Factual Termux/arm64 caveat (npm registry verified):
#   The npm package os field is ["darwin","linux","win32"] — no "android".
#   npm on Termux reports platform=android, so optional deps may be skipped.
#   However, opencode ships musl variants (opencode-linux-arm64-musl) which
#   work on Bionic libc if the binary IS installed. If npm fails, grab the
#   binary from https://github.com/sst/opencode/releases directly.
if [ "$AIGATE_OS" = "termux" ]; then
  log_msg "NOTE (Termux/arm64): opencode-ai npm package lists os=[darwin,linux,win32]"
  log_msg "      but not android. If install succeeded, the musl binary works on Bionic."
  log_msg "      If it failed, download from https://github.com/sst/opencode/releases"
fi

# --- opencode -> aigate wiring (OpenAI Chat Completions via opencode.json) ----
# Mirrors _opencode_builder (cli_tools_router.py:377-438).
# opencode reads opencode.json from CWD. We generate one pointing at aigate.

# Best-effort reachability check (tolerate missing curl). aigate exposes a
# non-auth GET /v1/models (router.py:478); only a hard connect/timeout failure warns.
if have_cmd curl; then
  if ! curl -fsS -o /dev/null --max-time 3 "${AIGATE_BASE}/models" 2>/dev/null; then
    rc=$?
    if [ "$rc" -eq 7 ] || [ "$rc" -eq 28 ]; then
      log_msg "WARN: aigate not reachable at $AIGATE_BASE (check gateway_base_url / is aigate running?);"
      log_msg "      opencode will fail to connect. Start aigate first if it is not running."
    fi
  fi
fi

# Export env vars as belt-and-suspenders (the builder also sets apiKey in JSON).
# cli_tools_router.py:1081-1084 injects OPENAI_API_BASE + OPENAI_API_KEY for all tools.
export OPENAI_API_BASE="$AIGATE_BASE"
export OPENAI_API_KEY="$AIGATE_KEY"

AIGATE_MODEL="${AIGATE_MODEL:-}"

# Build the model id for opencode.json (provider/model format).
# cli_tools_router.py:423 -> f"{provider_id}/{raw_model}"
MODEL_JSON=""
if [ -n "$AIGATE_MODEL" ]; then
  MODEL_JSON=$(printf ',\n  "model": "aigate/%s"' "$AIGATE_MODEL")
fi

# Generate opencode.json mirroring _opencode_builder (cli_tools_router.py:417-431).
# Uses single-quoted heredoc so nothing is expanded by the shell.
# The provider uses @ai-sdk/openai-compatible (documented at opencode.ai/docs/providers).
log_msg "writing opencode.json for aigate provider (base=$AIGATE_BASE)"
cat > opencode.json <<AIGATE_EOF
{
  "\$schema": "https://opencode.ai/config.json"${MODEL_JSON},
  "provider": {
    "aigate": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "aigate",
      "options": {
        "baseURL": "${AIGATE_BASE}",
        "apiKey": "${AIGATE_KEY}"
      },
      "models": {}
    }
  }
}
AIGATE_EOF

log_msg "launching opencode via aigate (openai-compatible endpoint ${AIGATE_BASE}/chat/completions)"
exec "$BIN" "$@"

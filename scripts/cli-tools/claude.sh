#!/usr/bin/env bash
# claude.sh — install + launch Claude Code (Grup A / A1) for aigate.
#
# Source of truth: documents/pm/cli-tools-install-backlog.md (A1).
#
# INSTALL: npm i -g @anthropic-ai/claude-code   (idempotent via have_cmd)
#   Package facts (verified on npm registry, @anthropic-ai/claude-code@2.1.265):
#     * Ships a NATIVE binary via optionalDependencies, incl.
#       @anthropic-ai/claude-code-linux-arm64 (os:linux, cpu:arm64, libc:glibc)
#       and a linux-arm64-musl variant. So `npm i -g` SUCCEEDS on Termux/arm64
#       (npm sees linux/arm64 and fetches the arm64 optional dep).
#     * But the installed `claude` binary is glibc-linked, while Termux's
#       userspace is Bionic libc -> it will NOT execute on a STOCK Termux install
#       without a glibc layer (proot-distro Ubuntu, termux-exec, or a chroot).
#     * engines.node >= 22 required.
#   The old caveat ("npm may install without the arm64 binary") was inaccurate:
#   npm DOES install the arm64 binary; the real blocker is the libc mismatch.
#
# LAUNCH WIRING: Claude Code speaks the *Anthropic Messages* API (POST /v1/messages),
# not OpenAI. aigate's gateway (src/backend/gateway/router.py) exposes ONLY OpenAI
# endpoints: /v1/chat/completions, /v1/responses, /v1/models. There is NO inbound
# /v1/messages route — its Anthropic translator (translator.py _translate_request_anthropic,
# provider_adapter.py:80-86) is OUTBOUND only (aigate as a *client* to an Anthropic
# upstream). So ANTHROPIC_BASE_URL cannot point at aigate (claude would POST to
# <aigate>/v1/messages -> 404), and aigate exposes no "anthropic endpoint/token".
# The only workable wire for Claude Code is an Anthropic-compatible proxy in front:
# litellm (which serves /v1/messages and translates to OpenAI). Chain:
#     claude-code -> litellm(/v1/messages) -> aigate(/v1/chat/completions) -> backend
# which matches the user's "claude -> litellm -> backend" stack.
#
# Therefore this script wires Claude Code to litellm (NOT native, NOT aigate).
# Configure via env (defaults assume litellm on localhost:4000):
#   AIGATE_LITELLM_BASE_URL  default http://localhost:4000   (root, no trailing /v1)
#   AIGATE_LITELLM_API_KEY   default sk-aigate
#   AIGATE_LITELLM_MODEL     optional; passed as Claude Code --model / ANTHROPIC_MODEL

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

detect_os
detect_pm
load_gateway_config   # informational only (aigate has no anthropic endpoint)

BIN="claude"
INSTALL_CMD=(npm i -g @anthropic-ai/claude-code)

log_msg "os=$AIGATE_OS pm=$AIGATE_PM gateway_base=$AIGATE_BASE"

# Idempotent install (never reinstalls when already present).
if ! ensure_installed "$BIN" "${INSTALL_CMD[@]}"; then
  log_msg "could not install claude on this platform; aborting launch."
  exit 1
fi

# Factual Termux/arm64 caveat (npm registry verified):
#   install OK, but the native binary is glibc-linked; stock Termux (Bionic) cannot
#   run it without a glibc compat layer. Node >= 22 also required.
if [ "$AIGATE_OS" = "termux" ]; then
  log_msg "NOTE (Termux/arm64): claude installs, but its native binary is glibc-linked"
  log_msg "      while Termux uses Bionic libc — run it inside a glibc env"
  log_msg "      (proot-distro Ubuntu / termux-exec / chroot). Needs Node >= 22."
fi

# --- Claude Code -> litellm wiring (Anthropic-compatible proxy) -------------
# aigate has no /v1/messages server endpoint, so we route through litellm.
LITELLM_BASE="${AIGATE_LITELLM_BASE_URL:-http://localhost:4000}"
LITELLM_KEY="${AIGATE_LITELLM_API_KEY:-sk-aigate}"
LITELLM_MODEL="${AIGATE_LITELLM_MODEL:-}"

# Normalize: strip a trailing /v1 so claude-code builds <base>/v1/messages correctly.
LITELLM_BASE="${LITELLM_BASE%/v1}"
LITELLM_BASE="${LITELLM_BASE%/}"

# Best-effort reachability check (tolerate missing curl). litellm serves
# /health/liveliness without auth; only a hard connect/timeout failure warns.
if have_cmd curl; then
  if ! curl -fsS -o /dev/null --max-time 3 "${LITELLM_BASE}/health/liveliness" 2>/dev/null; then
    rc=$?
    if [ "$rc" -eq 7 ] || [ "$rc" -eq 28 ]; then
      log_msg "WARN: litellm not reachable at $LITELLM_BASE (check AIGATE_LITELLM_BASE_URL);"
      log_msg "      claude will fail to connect. Start litellm first if it is not running."
    fi
  fi
fi

export ANTHROPIC_BASE_URL="$LITELLM_BASE"
export ANTHROPIC_API_KEY="$LITELLM_KEY"
[ -n "$LITELLM_MODEL" ] && export ANTHROPIC_MODEL="$LITELLM_MODEL"

log_msg "launching claude via litellm (anthropic endpoint $LITELLM_BASE); aigate has no /v1/messages"
if [ -n "$LITELLM_MODEL" ]; then
  exec "$BIN" --model "$LITELLM_MODEL" "$@"
else
  exec "$BIN" "$@"
fi

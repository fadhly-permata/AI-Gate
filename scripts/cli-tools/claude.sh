#!/usr/bin/env bash
# claude.sh — install + launch Claude Code (Grup A / A1) for aigate.
#
# Source of truth: documents/pm/cli-tools-install-backlog.md (A1);
# re-wire design: documents/architecture/anthropic-inbound-endpoint.md §7.
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
# not OpenAI. aigate's gateway NOW serves that endpoint natively (inbound) at
# /v1/messages (router.py:499), accepting either `Authorization: Bearer` or
# `x-api-key` as the aigate credential (ADR-007 plaintext internal_api_key). So
# claude-code points directly at aigate — NO litellm (or any Anthropic proxy) in
# the middle. Chain:
#     claude-code -> aigate(/v1/messages) -> backend
# claude-code appends "/v1/messages" to ANTHROPIC_BASE_URL itself, so the base
# URL must be the aigate gateway ROOT (gateway_base_url with the "/v1" suffix
# stripped). The aigate key comes from load_gateway_config (AIGATE_KEY), which
# reads internal_api_key from the endpoint table (ADR-007 plaintext).
#
# Configure via env (defaults come from the aigate gateway config via _common.sh):
#   AIGATE_MODEL   optional; forwarded to Claude Code as --model / ANTHROPIC_MODEL

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

detect_os
detect_pm
load_gateway_config   # aigate gateway base (AIGATE_BASE) + internal key (AIGATE_KEY)

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

# --- Claude Code -> aigate wiring (Anthropic Messages, native /v1/messages) ----
# aigate serves /v1/messages natively (no litellm). claude-code appends
# "/v1/messages" to ANTHROPIC_BASE_URL, so we pass the gateway ROOT.
AIGATE_ROOT="${AIGATE_BASE%/}"     # strip any trailing slash first
AIGATE_ROOT="${AIGATE_ROOT%/v1}"   # then strip the /v1 suffix from gateway_base_url

# Best-effort reachability check (tolerate missing curl). aigate exposes a
# non-auth GET /v1/models (router.py:478); only a hard connect/timeout failure warns.
if have_cmd curl; then
  if ! curl -fsS -o /dev/null --max-time 3 "${AIGATE_BASE}/models" 2>/dev/null; then
    rc=$?
    if [ "$rc" -eq 7 ] || [ "$rc" -eq 28 ]; then
      log_msg "WARN: aigate not reachable at $AIGATE_BASE (check gateway_base_url / is aigate running?);"
      log_msg "      claude will fail to connect. Start aigate first if it is not running."
    fi
  fi
fi

export ANTHROPIC_BASE_URL="$AIGATE_ROOT"
export ANTHROPIC_API_KEY="$AIGATE_KEY"
AIGATE_MODEL="${AIGATE_MODEL:-}"
[ -n "$AIGATE_MODEL" ] && export ANTHROPIC_MODEL="$AIGATE_MODEL"

log_msg "launching claude via aigate (anthropic endpoint ${AIGATE_ROOT}/v1/messages); aigate serves /v1/messages natively"
if [ -n "$AIGATE_MODEL" ]; then
  exec "$BIN" --model "$AIGATE_MODEL" "$@"
else
  exec "$BIN" "$@"
fi

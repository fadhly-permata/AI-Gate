#!/usr/bin/env bash
# codex.sh — install + launch Codex CLI (Grup A / A4) for aigate.
#
# Source of truth: documents/pm/cli-tools-install-backlog.md (A4);
# aigate launch support: src/backend/cli_presets.py:180 (LAUNCH_UNSUPPORTED /
# REASON_RESPONSES_ONLY) + comment at cli_presets.py:159-161; install string at
# cli_presets.py:72; Termux override at cli_presets.py:243 (TERMUX_INSTALL).
#
# INSTALL:
#   * Default (non-Termux): npm i -g @openai/codex
#       (aigate CLI_PRESETS at cli_presets.py:72 -> _npm("@openai/codex")).
#   * Termux: pkg install codex  (tur-repo; TERMUX_INSTALL at cli_presets.py:243).
#   Package facts (verified on npm registry latest @openai/codex@0.153.4):
#     * bin: {"codex":"bin/codex.js"} — a thin launcher; the real binary is the
#       Rust core pulled by per-platform optionalDependencies, incl.
#       @openai/codex-linux-arm64 (the registry lists linux-x64, linux-arm64,
#       darwin-x64/arm64, win32-x64/arm64 variants). So a linux-arm64 build DOES
#       exist (unlike the gemini precedent which had no arm64 node-pty).
#     * engines.node >= 16.
#   Alt verified installs (official README, not used here to stay faithful to
#   aigate's CLI_PRESETS): `brew install --cask codex`, or the official installer
#   `curl -fsSL https://chatgpt.com/codex/install.sh | sh`.
#
# WIRING (CRITICAL CROSS-CHECK — see receipt, R47+R48; CONFLICT FOUND):
#   aigate's gateway now DOES expose POST /v1/responses (gateway/router.py:342,
#   gateway/responses.py). BUT it is NON-STREAMING ONLY:
#     * responses.py:227-233 -> `stream:true` is refused with 400
#       `responses_streaming_unsupported`.
#     * responses.py:236-243 -> tools/functions/reasoning/state/structured-output
#       fields are refused with 400 `responses_unsupported_field`.
#   Codex CLI speaks ONLY the OpenAI Responses API. The official config reference
#   (learn.chatgpt.com/docs/config-file/config-reference.md) documents
#   model_providers.<id>.wire_api as type "responses" — "`responses` is the only
#   supported value, and it is the default when omitted." Codex's interactive
#   agentic loop REQUIRES streaming (SSE/WebSocket deltas), so every turn would
#   hit aigate's `responses_streaming_unsupported` 400.
#   => aigate therefore marks codex LAUNCH_UNSUPPORTED / REASON_RESPONSES_ONLY
#      (cli_presets.py:180) and ships NO _codex_builder (cli_tools_router.py:976-988
#      _LAUNCH_BUILDERS has no "codex" entry -> resolve() would 409 tool_unsupported).
#   => NEITHER opencode-style (OPENAI_API_BASE -> /v1/chat/completions) NOR
#      claude-style (ANTHROPIC_BASE_URL -> /v1/messages) wiring applies:
#      codex hits /v1/responses, which aigate serves non-streaming only.
#   (Extra evidence the opencode-style var is wrong: codex's base-URL knob is the
#   config.toml key `openai_base_url`, NOT an OPENAI_API_BASE env var — so even
#   setting OPENAI_API_BASE would be ignored by codex.)
#   Per _common.sh's own contract ("aigate itself returns 409 tool_unsupported
#   for them, so we mirror that behaviour"), this script does NOT route codex
#   through the aigate gateway. It launches codex in its NATIVE OpenAI mode (using
#   the user's own OPENAI_API_KEY / ChatGPT login) and warns loudly that aigate
#   wiring is impossible. This mirrors gemini.sh (REASON_GEMINI_ONLY).
#
#   NOTE / CONFLICT: the explanatory comment at cli_presets.py:159-161 says codex
#   "needs /v1/responses" as if aigate lacks that endpoint — that comment is now
#   STALE: aigate HAS /v1/responses (router.py:342) but only the non-streaming
#   subset, which is insufficient for codex. The REASON_RESPONSES_ONLY mark is
#   still correct; the comment's rationale is out of date vs the gateway code.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

detect_os
detect_pm
load_gateway_config   # aigate gateway base (AIGATE_BASE) + internal key (AIGATE_KEY)

BIN="codex"
# Termux: tur-repo build (verified, bionic-compatible). Else: npm global per
# aigate CLI_PRESETS (cli_presets.py:72).
if [ "$AIGATE_OS" = "termux" ]; then
  INSTALL_CMD=(pkg install codex)
else
  INSTALL_CMD=(npm i -g @openai/codex)
fi

log_msg "os=$AIGATE_OS pm=$AIGATE_PM gateway_base=$AIGATE_BASE"

# Idempotent install (never reinstalls when already present).
if ! ensure_installed "$BIN" "${INSTALL_CMD[@]}"; then
  log_msg "could not install codex on this platform; aborting launch."
  exit 1
fi

# Termux/arm64 caveat (npm registry verified, @openai/codex@0.153.4):
#   `npm` reports process.platform == "android" on Termux and SKIPS the
#   linux-arm64 optional dependency, so `npm i -g @openai/codex` can install but
#   then fail at runtime ("Missing optional dependency ..."). The tur-repo
#   `pkg install codex` path (used above on Termux) is the verified working route.
if [ "$AIGATE_OS" = "termux" ]; then
  log_msg "NOTE (Termux/arm64): use 'pkg install codex' (tur-repo, bionic-compatible)."
  log_msg "      'npm i -g @openai/codex' here skips the linux-arm64 optional dep"
  log_msg "      (process.platform=android) and may die at runtime."
fi

# Best-effort reachability check (tolerate missing curl). aigate exposes a
# non-auth GET /v1/models; only a hard connect/timeout failure warns. codex is
# NOT routed through aigate regardless, so this is informational only.
if have_cmd curl; then
  if ! curl -fsS -o /dev/null --max-time 3 "${AIGATE_BASE}/models" 2>/dev/null; then
    rc=$?
    if [ "$rc" -eq 7 ] || [ "$rc" -eq 28 ]; then
      log_msg "WARN: aigate not reachable at $AIGATE_BASE (check gateway_base_url / is aigate running?);"
      log_msg "      this is informational — codex is NOT wired to aigate anyway (see wiring note below)."
    fi
  fi
fi

# --- codex -> aigate wiring: NOT POSSIBLE (cross-check finding) --------------
# aigate marks codex LAUNCH_UNSUPPORTED / REASON_RESPONSES_ONLY (cli_presets.py:180);
# no _codex_builder (cli_tools_router.py:976-988) so resolve() 409s. Codex speaks
# the Responses API (wire_api="responses" only, per the official config reference)
# and REQUIRES streaming, but aigate's /v1/responses is non-streaming only
# (responses.py:227-233 stream:true -> 400 responses_streaming_unsupported).
# We do NOT set ANTHROPIC_BASE_URL / OPENAI_API_BASE / *_KEY to aigate values
# (they would be ignored by codex or hit the wrong/unsupported wire format).
# Instead we launch codex natively with the user's own OpenAI credentials.
if [ -n "${OPENAI_API_KEY:-}" ]; then
  log_msg "launching codex in NATIVE OpenAI mode (OPENAI_API_KEY present)."
  log_msg "NOT WIRED to aigate: codex speaks OpenAI Responses API (needs streaming);"
  log_msg "  aigate serves /v1/responses non-streaming only (cli_presets.py:180 unsupported)."
else
  log_msg "launching codex (native OpenAI auth). It is NOT wired to aigate:"
  log_msg "  - aigate marks codex LAUNCH_UNSUPPORTED / REASON_RESPONSES_ONLY (cli_presets.py:180);"
  log_msg "  - codex speaks OpenAI Responses API with required streaming; aigate's /v1/responses"
  log_msg "    is non-streaming only (responses.py:227-233), so codex would 400 on every turn."
  log_msg "  - no _codex_builder exists (cli_tools_router.py:976-988); resolve() returns 409."
  log_msg "  - no OPENAI_API_KEY set: codex will prompt for ChatGPT login / API key (browser)."
fi

# Forward an explicit model via AIGATE_MODEL for a consistent launch form.
AIGATE_MODEL="${AIGATE_MODEL:-}"
if [ -n "$AIGATE_MODEL" ]; then
  exec "$BIN" --model "$AIGATE_MODEL" "$@"
else
  exec "$BIN" "$@"
fi

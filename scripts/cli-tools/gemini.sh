#!/usr/bin/env bash
# gemini.sh — install + launch Gemini CLI (Grup A / A4) for aigate.
#
# Source of truth: documents/pm/cli-tools-install-backlog.md (A4);
# aigate launch support: src/backend/cli_presets.py:175 (LAUNCH_UNSUPPORTED /
# REASON_GEMINI_ONLY) + comment at cli_presets.py:156-158; install string at
# cli_presets.py:73.
#
# INSTALL: npm i -g @google/gemini-cli   (idempotent via have_cmd)
#   Package facts (verified on npm registry, @google/gemini-cli@0.59.0):
#     * bin: {"gemini": "bundle/gemini.js"} — a PURE-JS bundle run by Node
#       (no native binary, unlike claude-code's glibc binary / opencode's Go binary).
#     * engines.node >= 20.
#     * os / cpu / libc: ALL None — npm imposes no platform restriction, so
#       `npm i -g` SUCCEEDS on Termux/arm64 (no "Missing optional dependency").
#     * optionalDependencies include @lydell/node-pty-* for linux-x64 / darwin /
#       win only — NO linux-arm64 variant. node-pty is OPTIONAL; if it fails to
#       build on Termux the PTY features degrade but the CLI still launches.
#   Alternate verified install (macOS/Linux): `brew install gemini-cli`
#   (see github.com/google-gemini/gemini-cli README "Quick Install").
#
# WIRING (CRITICAL CROSS-CHECK — see receipt, R47+R48):
#   aigate's gateway serves ONLY OpenAI /v1/chat/completions and (now) Anthropic
#   /v1/messages inbound. It has NO Google generateContent inbound surface
#   (cli_presets.py:156-158; the gemini code in gateway/translator.py:19,177,273
#   is UPSTREAM translation, not a client-facing endpoint). aigate therefore
#   marks gemini LAUNCH_UNSUPPORTED / REASON_GEMINI_ONLY (cli_presets.py:175) and
#   ships NO _gemini_builder (cli_tools_router.py has _LAUNCH_BUILDERS at :976
#   but no gemini entry; only _opencode_builder at :377 etc.).
#   The Gemini CLI itself speaks ONLY the Google Gemini API (generateContent):
#   official auth is GEMINI_API_KEY (AI Studio), GOOGLE_API_KEY +
#   GOOGLE_GENAI_USE_VERTEXAI=true (Vertex AI), or GOOGLE_CLOUD_PROJECT (Code
#   Assist) — see gemini CLI authentication docs. It honours NEITHER
#   ANTHROPIC_BASE_URL NOR OPENAI_API_BASE / OPENAI_API_KEY.
#   => NEITHER the claude-style (ANTHROPIC_BASE_URL -> /v1/messages) NOR the
#      opencode-style (OPENAI_API_BASE -> /v1/chat/completions) wiring applies.
#   Per _common.sh's own contract ("aigate itself returns 409 tool_unsupported
#   for them, so we mirror that behaviour"), this script does NOT route gemini
#   through the aigate gateway. It launches gemini in its NATIVE Google mode
#   (using the user's own GEMINI_API_KEY / GOOGLE_API_KEY, else interactive
#   OAuth) and warns loudly that aigate wiring is impossible. This is the
#   fact-faithful behaviour; faking ANTHROPIC_*/OPENAI_* vars would be a no-op.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

detect_os
detect_pm
load_gateway_config   # aigate gateway base (AIGATE_BASE) + internal key (AIGATE_KEY)

BIN="gemini"
INSTALL_CMD=(npm i -g @google/gemini-cli)

log_msg "os=$AIGATE_OS pm=$AIGATE_PM gateway_base=$AIGATE_BASE"

# Idempotent install (never reinstalls when already present).
if ! ensure_installed "$BIN" "${INSTALL_CMD[@]}"; then
  log_msg "could not install gemini on this platform; aborting launch."
  exit 1
fi

# Termux/arm64 caveat (npm registry verified, @google/gemini-cli@0.59.0):
#   gemini is a pure-JS Node bundle (bin=bundle/gemini.js, engines.node >= 20),
#   so it RUNS on Termux/Bionic — unlike claude-code (glibc native) which needs
#   a glibc layer. The only risk is the optional native node-pty (no linux-arm64
#   build), which only degrades PTY features; the CLI still launches.
if [ "$AIGATE_OS" = "termux" ]; then
  log_msg "NOTE (Termux/arm64): gemini is a pure-JS Node bundle (bin=bundle/gemini.js,"
  log_msg "      node>=20) — it RUNS on Bionic libc. Optional node-pty (no arm64 build)"
  log_msg "      may be skipped; PTY features degrade but the CLI launches. Needs Node >= 20."
fi

# Best-effort reachability check (tolerate missing curl). aigate exposes a
# non-auth GET /v1/models (router.py:478); only a hard connect/timeout failure warns.
if have_cmd curl; then
  if ! curl -fsS -o /dev/null --max-time 3 "${AIGATE_BASE}/models" 2>/dev/null; then
    rc=$?
    if [ "$rc" -eq 7 ] || [ "$rc" -eq 28 ]; then
      log_msg "WARN: aigate not reachable at $AIGATE_BASE (check gateway_base_url / is aigate running?);"
      log_msg "      gemini is NOT routed through aigate regardless (see wiring note below)."
    fi
  fi
fi

# --- gemini -> aigate wiring: NOT POSSIBLE (cross-check finding) --------------
# aigate has no gemini inbound surface and gemini CLI only speaks Google's
# generateContent. We do NOT set ANTHROPIC_BASE_URL / OPENAI_API_BASE / *_KEY to
# aigate values (they would be ignored by the gemini CLI). Instead we launch
# gemini natively with the user's Google credentials (if any). Non-interactive
# runs (`gemini -p "..."`) need GEMINI_API_KEY or GOOGLE_API_KEY; otherwise
# gemini will prompt for Google OAuth via a browser.
if [ -n "${GEMINI_API_KEY:-}" ] || [ -n "${GOOGLE_API_KEY:-}" ]; then
  log_msg "launching gemini in NATIVE Google mode (GEMINI_API_KEY/GOOGLE_API_KEY present)."
  log_msg "NOT WIRED to aigate: gemini speaks Google generateContent; aigate serves only"
  log_msg "  OpenAI /v1/chat/completions + Anthropic /v1/messages (cli_presets.py:175 unsupported)."
else
  log_msg "launching gemini (native Google auth). It is NOT wired to aigate:"
  log_msg "  - aigate marks gemini LAUNCH_UNSUPPORTED / REASON_GEMINI_ONLY (cli_presets.py:175);"
  log_msg "  - gemini CLI only speaks Google generateContent (GEMINI_API_KEY / GOOGLE_API_KEY),"
  log_msg "    not ANTHROPIC_BASE_URL nor OPENAI_API_BASE (no _gemini_builder in cli_tools_router.py)."
  log_msg "  - no GEMINI_API_KEY/GOOGLE_API_KEY set: gemini will prompt for Google OAuth (browser)."
fi

# Forward an explicit model via GEMINI_MODEL if the operator set AIGATE_MODEL,
# so the launch form is consistent with claude/opencode scripts.
AIGATE_MODEL="${AIGATE_MODEL:-}"
if [ -n "$AIGATE_MODEL" ]; then
  export GEMINI_MODEL="$AIGATE_MODEL"
  exec "$BIN" --model "$AIGATE_MODEL" "$@"
else
  exec "$BIN" "$@"
fi

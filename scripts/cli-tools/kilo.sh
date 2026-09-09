#!/usr/bin/env bash
# kilo.sh — install + launch Kilo Code CLI (Grup A / A12) for aigate.
#
# Source of truth: documents/pm/cli-tools-install-backlog.md (A12);
# aigate preset:  src/backend/cli_presets.py
#                   - line 81  : install _npm("@kilocode/cli")
#                                 -> `npm install -g @kilocode/cli`, bin `kilo`
#                   - line 183 : "kilo": LaunchSupport(LAUNCH_VERIFIED)
# launch builder: src/backend/cli_tools_router.py _kilo_builder (lines 616-729)
#
# INSTALL: npm install -g @kilocode/cli   (idempotent via have_cmd)
#   Package facts (verified on npm registry, @kilocode/cli@7.5.16):
#     * bin: `kilo` (and alias `kilocode`) -> bin/kilo.
#     * os:  ["darwin","linux","win32"]  (NO "android" => no Termux binary)
#     * cpu: ["arm64","x64"]; ships PREBUILT NATIVE binaries via optionalDependencies
#       (@kilocode/cli-linux-x64/-arm64, -darwin-*, -windows-*, plus -musl /
#       -baseline variants). There is NO @kilocode/cli-android-* package, so on
#       Termux (process.platform == "android") npm installs the JS wrapper but
#       skips every platform binary and `kilo` is never placed on PATH. This
#       matches the _kilo_builder note at cli_tools_router.py:687-689.
#     * engines.node: not declared (no Node version gate); a `postinstall` script
#       runs `node ./postinstall.mjs` (so a working node is needed at install).
#     * license: MIT. Repo: github.com/Kilo-Org/kilocode (matches preset name).
#   The npm install form is exactly the aigate preset; no divergence.
#
# LAUNCH WIRING: Kilo speaks OpenAI Chat Completions and aigate serves that
#   natively at /v1/chat/completions. Chain (mirrors _kilo_builder EXACTLY):
#     kilo -> aigate(/v1/chat/completions) -> backend
#
#   The builder registers a custom OpenAI-compatible provider ("aigate") through
#   a TRUSTED, ADDITIVE config file (KILO_CONFIG=`.kilo/aigate-kilo.json`):
#     - provider "aigate": npm "@ai-sdk/openai-compatible" (the OpenAI Chat
#       Completions protocol package), options.baseURL = gateway base,
#       options.apiKey = "{env:OPENAI_API_KEY}" (resolved because KILO_CONFIG is
#       a trusted location), and a `models` map.
#     - the gateway key reaches kilo as the exported OPENAI_API_KEY (injected by
#       the launcher for every tool, cli_tools_router.py:1081-1084); the secret
#       is never written to disk.
#     - when a model is chosen: config `model` key = "aigate/<model>" AND the
#       highest-priority `-m aigate/<model>` flag (kilo Model Loading Priority:
#       1 flag, 2 config key, 3 last used, 4 first available).
#   Env injected every launch (mirrors resolve(), cli_tools_router.py:1081-1084):
#     OPENAI_API_BASE=<base>   OPENAI_API_KEY=<key>   KILO_CONFIG=<config file>
#
#   No model chosen (AIGATE_MODEL unset) -> the config still registers the
#   gateway (empty `models` map) but no `model` key and no `-m` flag; kilo's
#   OpenAI-compatible provider auto-fetches models from aigate's /v1/models
#   endpoint (per docs) and the TUI opens for manual /models selection.
#
# Configure via env (defaults from the aigate gateway config via _common.sh):
#   AIGATE_MODEL   optional; forwarded to kilo as -m aigate/<AIGATE_MODEL>.
#                  Without it, kilo launches and you pick the model in the TUI.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

detect_os
detect_pm
load_gateway_config   # aigate gateway base (AIGATE_BASE) + internal key (AIGATE_KEY)

BIN="kilo"
INSTALL_CMD=(npm install -g @kilocode/cli)

log_msg "os=$AIGATE_OS pm=$AIGATE_PM gateway_base=$AIGATE_BASE"

# Idempotent install (never reinstalls when already present).
if ! ensure_installed "$BIN" "${INSTALL_CMD[@]}"; then
  log_msg "could not install kilo on this platform; aborting launch."
  exit 1
fi

# Known-broken on Termux/arm64 (npm registry verified): @kilocode/cli ships
# prebuilt native binaries via optionalDependencies for darwin/linux/win32 on
# arm64/x64 only; there is no android variant, so on Termux npm skips them all
# and `kilo` is never placed on PATH (ensure_installed above will have failed).
if [ "$AIGATE_OS" = "termux" ]; then
  log_msg "NOTE (Termux/arm64): @kilocode/cli publishes no android binary; npm"
  log_msg "      skips the native optional deps on Termux, so 'kilo' is not"
  log_msg "      installed here. Use kilo on a desktop Linux / macOS / Windows host."
fi

# --- kilo -> aigate wiring (OpenAI-compatible via KILO_CONFIG override) ----
# Best-effort reachability check (tolerate missing curl). aigate exposes a
# non-auth GET /v1/models; only a hard connect/timeout failure warns.
if have_cmd curl; then
  if ! curl -fsS -o /dev/null --max-time 3 "${AIGATE_BASE}/models" 2>/dev/null; then
    rc=$?
    if [ "$rc" -eq 7 ] || [ "$rc" -eq 28 ]; then
      log_msg "WARN: aigate not reachable at $AIGATE_BASE (check gateway_base_url / is aigate running?);"
      log_msg "      kilo will fail to connect. Start aigate first if it is not running."
    fi
  fi
fi

# Write the trusted, additive kilo config (.kilo/aigate-kilo.json) relative to
# CWD — mirrors _kilo_builder (cli_tools_router.py:653,716-719). The gateway key
# is referenced as {env:OPENAI_API_KEY} (NOT written to disk); only the base URL
# is embedded. The provider id "aigate" is arbitrary (docs: "any name you like").
KILO_CFG=".kilo/aigate-kilo.json"
mkdir -p "$(dirname "$KILO_CFG")"

MODEL_KEY=""
MODEL_FLAG=""
MODELS_BLOCK=""
if [ -n "${AIGATE_MODEL:-}" ]; then
  MODEL_KEY="  \"model\": \"aigate/${AIGATE_MODEL}\","
  MODEL_FLAG="-m aigate/${AIGATE_MODEL}"
  MODELS_BLOCK="        \"${AIGATE_MODEL}\": { \"name\": \"${AIGATE_MODEL}\" }"
fi

cat > "$KILO_CFG" <<EOF
{
  "\$schema": "https://app.kilo.ai/config.json",
${MODEL_KEY}
  "provider": {
    "aigate": {
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "baseURL": "$AIGATE_BASE",
        "apiKey": "{env:OPENAI_API_KEY}"
      },
      "models": {
${MODELS_BLOCK}
      }
    }
  }
}
EOF

# Env injection (every tool gets these; cli_tools_router.py:1081-1084).
# KILO_CONFIG points kilo at our trusted additive provider file.
export OPENAI_API_BASE="$AIGATE_BASE"
export OPENAI_API_KEY="$AIGATE_KEY"
export KILO_CONFIG="$KILO_CFG"

log_msg "launching kilo via aigate (openai-compatible -> ${AIGATE_BASE}/chat/completions${AIGATE_MODEL:+; model=$AIGATE_MODEL})"
exec "$BIN" $MODEL_FLAG "$@"

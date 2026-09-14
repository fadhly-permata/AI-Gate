#!/usr/bin/env bash
# qwen.sh — install + launch Qwen Code (Grup A / A10) for aigate.
#
# Source of truth: documents/pm/cli-tools-install-backlog.md (A10);
# aigate preset:  src/backend/cli_presets.py
#                   - line 79  : install _npm("@qwen-code/qwen-code")
#                                 -> `npm install -g @qwen-code/qwen-code`, bin `qwen`
#                   - line 181 : "qwen": LaunchSupport(LAUNCH_VERIFIED)
# launch builder: src/backend/cli_tools_router.py _qwen_builder (line 526)
#
# INSTALL: npm i -g @qwen-code/qwen-code   (idempotent via have_cmd)
#   Package facts (verified on npm registry, @qwen-code/qwen-code@0.23.1):
#     * bin: `qwen` (cli-entry.js). Pure-JS package (main cli.js); package.json
#       declares NO `os`/`cpu`/`libc` restriction -> installs cross-platform,
#       INCLUDING Termux (no native binary to fail on Bionic libc, unlike
#       claude-code / opencode native binaries).
#     * engines.node >= 22.0.0 required.
#   README (github.com/QwenLM/qwen-code) also documents Homebrew
#   (`brew install qwen-code`) + a standalone install script; npm is the most
#   portable route and matches the aigate preset exactly.
#
# LAUNCH WIRING: Qwen Code speaks OpenAI-compatible Chat Completions via its
#   `openai` auth type (docs/users/configuration/model-providers.md: "OpenAI
#   compatible APIs (OpenAI, Azure OpenAI, local inference servers like
#   vLLM/Ollama)"). aigate serves this natively at /v1/chat/completions.
#   Qwen Code resolves settings in layers and the project file
#   <cwd>/.qwen/settings.json OVERRIDES the user's ~/.qwen/settings.json, so
#   aigate writes a project-scoped file instead of touching user config.
#
#   Mirrors _qwen_builder (cli_tools_router.py:526-567) EXACTLY:
#     .qwen/settings.json =
#       { "modelProviders": { "openai": [ {id,name,baseUrl:AIGATE_BASE,
#                                          envKey:"OPENAI_API_KEY"} ] },
#         "security": { "auth": { "selectedType": "openai" } },
#         "model":    { "name": "<AIGATE_MODEL>" },
#         "env":      { "OPENAI_API_KEY": "<AIGATE_KEY>" } }
#   plus the env injection every tool receives (cli_tools_router.py:1081-1084):
#     OPENAI_API_BASE=<base>   OPENAI_API_KEY=<key>
#   The `openai` provider's envKey reads OPENAI_API_KEY (exported by the
#   launcher); the file also embeds the key under env.OPENAI_API_KEY
#   (belt-and-suspenders; the gateway ignores the key while access control is
#   off, exactly like every other verified tool). Chain:
#     qwen -> aigate(/v1/chat/completions) -> backend
#
# Configure via env (defaults come from the aigate gateway config via _common.sh):
#   AIGATE_MODEL   optional; the model id aigate should serve (e.g. a provider
#                  model id or a bare id aigate resolves). Preselected in the
#                  generated .qwen/settings.json. Without it, qwen launches and
#                  you choose the model inside the CLI (qwen-oauth default).

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

detect_os
detect_pm
load_gateway_config   # aigate gateway base (AIGATE_BASE) + internal key (AIGATE_KEY)

BIN="qwen"
INSTALL_CMD=(npm i -g @qwen-code/qwen-code)

log_msg "os=$AIGATE_OS pm=$AIGATE_PM gateway_base=$AIGATE_BASE"

# Idempotent install (never reinstalls when already present).
if ! ensure_installed "$BIN" "${INSTALL_CMD[@]}"; then
  log_msg "could not install qwen on this platform; aborting launch."
  exit 1
fi

# Factual Node caveat (npm registry engines.node verified >= 22.0.0).
# qwen is pure-JS with no os/cpu/libc restriction, so it installs on Termux too
# (unlike claude/opencode native binaries). Node 22+ is still required to run.
if have_cmd node; then
  node_major="$(node -v 2>/dev/null | tr -d 'v' | cut -d. -f1)"
  if [ -n "$node_major" ] && [ "$node_major" -lt 22 ]; then
    log_msg "NOTE: qwen requires Node.js >= 22 (npm registry engines.node verified >=22.0.0)."
    log_msg "      Current node is v${node_major}; install Node 22+ if launch fails."
  fi
else
  log_msg "NOTE: qwen requires Node.js >= 22 but node was not found on PATH; install Node 22+."
fi

# --- qwen -> aigate wiring (OpenAI-compatible via .qwen/settings.json) ----
# Mirrors _qwen_builder (cli_tools_router.py:526-567). Qwen Code reads
# .qwen/settings.json from the CWD (project scope overrides user scope).

# Best-effort reachability check (tolerate missing curl). aigate exposes a
# non-auth GET /v1/models; only a hard connect/timeout failure warns.
if have_cmd curl; then
  if ! curl -fsS -o /dev/null --max-time 3 "${AIGATE_BASE}/models" 2>/dev/null; then
    rc=$?
    if [ "$rc" -eq 7 ] || [ "$rc" -eq 28 ]; then
      log_msg "WARN: aigate not reachable at $AIGATE_BASE (check gateway_base_url / is aigate running?);"
      log_msg "      qwen will fail to connect. Start aigate first if it is not running."
    fi
  fi
fi

# Export env vars as belt-and-suspenders. The `openai` provider's envKey reads
# OPENAI_API_KEY, and the settings file below also embeds it under env.
# cli_tools_router.py:1081-1084 injects these for every tool.
export OPENAI_API_BASE="$AIGATE_BASE"
export OPENAI_API_KEY="$AIGATE_KEY"

AIGATE_MODEL="${AIGATE_MODEL:-}"

# Build the project-scoped settings.json mirroring _qwen_builder.
# Single-quoted heredoc delimiter NOT used here because we WANT bash to expand
# AIGATE_BASE / AIGATE_KEY / AIGATE_MODEL (same as opencode.sh's opencode.json).
mkdir -p .qwen
SETTINGS=".qwen/settings.json"
if [ -n "$AIGATE_MODEL" ]; then
  log_msg "writing $SETTINGS (provider=openai base=$AIGATE_BASE model=$AIGATE_MODEL)"
  cat > "$SETTINGS" <<AIGATE_EOF
{
  "modelProviders": {
    "openai": [
      {
        "id": "${AIGATE_MODEL}",
        "name": "${AIGATE_MODEL}",
        "baseUrl": "${AIGATE_BASE}",
        "envKey": "OPENAI_API_KEY"
      }
    ]
  },
  "security": {
    "auth": {
      "selectedType": "openai"
    }
  },
  "model": {
    "name": "${AIGATE_MODEL}"
  },
  "env": {
    "OPENAI_API_KEY": "${AIGATE_KEY}"
  }
}
AIGATE_EOF
else
  # No model chosen: mirror the builder's no-model branch exactly (no
  # modelProviders / no security block, just the env key). qwen launches and the
  # user picks a model inside the CLI.
  log_msg "writing $SETTINGS (no model selected; set AIGATE_MODEL to preselect a model)"
  cat > "$SETTINGS" <<AIGATE_EOF
{
  "env": {
    "OPENAI_API_KEY": "${AIGATE_KEY}"
  }
}
AIGATE_EOF
fi

log_msg "launching qwen via aigate (openai-compatible endpoint ${AIGATE_BASE}/chat/completions)"
exec "$BIN" "$@"

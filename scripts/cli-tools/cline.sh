#!/usr/bin/env bash
# cline.sh — install + launch Cline CLI (Grup A / A11) for aigate.
#
# Source of truth: documents/pm/cli-tools-install-backlog.md (A11);
# aigate preset:  src/backend/cli_presets.py
#                   - line 80  : install _npm("cline")
#                                 -> `npm install -g cline`, bin `cline`
#                   - line 182 : "cline": LaunchSupport(LAUNCH_VERIFIED)
# launch builder: src/backend/cli_tools_router.py _cline_builder (line 732)
#
# INSTALL: npm i -g cline   (idempotent via have_cmd)
#   Package facts (verified on npm registry, cline@3.0.61):
#     * bin: `cline` (bin/cline). The package ships a PREBUILT NATIVE binary for
#       the platform via optionalDependencies (`@cline/cli-linux-arm64`,
#       `@cline/cli-linux-x64`, `@cline/cli-darwin-arm64/x64`,
#       `@cline/cli-windows-arm64/x64`), so no Node/Bun/Zig runtime is needed at
#       install time. README (github.com/cline/cline, apps/cli/README.md):
#       "The `cline` package resolves the correct binary for your platform via
#       optional dependencies, so no Node, Bun, or Zig runtime is required."
#     * engines.node: NOT declared (no Node version gate). You still need npm
#       present to run `npm i -g`.
#     * NO android/termux binary: the optional deps list no `android` variant,
#       so on Termux (`process.platform == "android"`) npm skips every optional
#       dep and `cline` is never placed on PATH -> install effectively fails
#       there. (Cross-checked with the README: "Platform binaries are published
#       for macOS, Linux, and Windows on arm64 and x64".) This matches the
#       _cline_builder note at cli_tools_router.py:744-746.
#   README also documents the same `npm install -g cline`, so the aigate preset
#   matches upstream exactly.
#
# LAUNCH WIRING: Cline ships an OpenAI-compatible provider (`openai-native`) that
#   points at any OpenAI /v1/chat/completions endpoint. aigate serves that
#   natively at /v1/chat/completions. Chain:
#     cline -> aigate(/v1/chat/completions) -> backend
#
#   Mirrors _cline_builder (cli_tools_router.py:732-764) EXACTLY — the upstream
#   "Quick provider setup" form:
#     cline auth --provider openai-native \
#           --apikey <AIGATE_KEY> --modelid <AIGATE_MODEL> \
#           --baseurl <AIGATE_BASE>
#   chained to a bare `cline` (interactive mode — cline's documented default when
#   no prompt is given). README confirms the verbatim flag form:
#     cline auth --provider openai-native --apikey sk-... --modelid gpt-5 \
#           --baseurl https://api.example.com/v1
#   README documents the bare `cline` (interactive) default separately: "Run
#   interactively: `cline`". `openai-native` is cline's OpenAI-compatible
#   provider id, so the gateway is registered as a plain OpenAI endpoint.
#
#   Plus the env injection every tool receives (cli_tools_router.py:1081-1084):
#     OPENAI_API_BASE=<base>   OPENAI_API_KEY=<key>
#   README lists `OPENAI_API_KEY` as the env for the OpenAI provider, so exporting
#   it is belt-and-suspenders alongside the explicit `--apikey` flag.
#
#   No model chosen (AIGATE_MODEL unset) -> mirror the builder's no-model branch:
#   the `cline auth` setup step is SKIPPED entirely (inventing a model id would
#   only make `cline` fail later) and a plain `cline` is launched so the user can
#   configure the provider/model inside the CLI.
#
# Configure via env (defaults come from the aigate gateway config via _common.sh):
#   AIGATE_MODEL   optional; forwarded to cline as --modelid <AIGATE_MODEL>.
#                  Without it, cline launches and you choose the model inside the CLI.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

detect_os
detect_pm
load_gateway_config   # aigate gateway base (AIGATE_BASE) + internal key (AIGATE_KEY)

BIN="cline"
INSTALL_CMD=(npm i -g cline)

log_msg "os=$AIGATE_OS pm=$AIGATE_PM gateway_base=$AIGATE_BASE"

# Idempotent install (never reinstalls when already present).
if ! ensure_installed "$BIN" "${INSTALL_CMD[@]}"; then
  log_msg "could not install cline on this platform; aborting launch."
  exit 1
fi

# Factual Termux/arm64 caveat (npm registry verified): the `cline` package ships
# prebuilt native binaries as optionalDependencies for linux/darwin/windows
# arm64/x64 only. On Termux (process.platform == "android") npm skips all of
# them, so `cline` is never placed on PATH and the install above fails. Run
# cline on a desktop Linux/macOS/Windows host instead.
if [ "$AIGATE_OS" = "termux" ]; then
  log_msg "NOTE (Termux/arm64): cline publishes no android binary; npm skips the"
  log_msg "      native optional deps on Termux, so 'cline' is not installed here."
  log_msg "      Use cline on a desktop Linux / macOS / Windows host instead."
fi

# --- cline -> aigate wiring (OpenAI-compatible via `cline auth openai-native`) ----
# Best-effort reachability check (tolerate missing curl). aigate exposes a
# non-auth GET /v1/models; only a hard connect/timeout failure warns.
if have_cmd curl; then
  if ! curl -fsS -o /dev/null --max-time 3 "${AIGATE_BASE}/models" 2>/dev/null; then
    rc=$?
    if [ "$rc" -eq 7 ] || [ "$rc" -eq 28 ]; then
      log_msg "WARN: aigate not reachable at $AIGATE_BASE (check gateway_base_url / is aigate running?);"
      log_msg "      cline will fail to connect. Start aigate first if it is not running."
    fi
  fi
fi

# Env injection (every tool gets these; cline README lists OPENAI_API_KEY for the
# OpenAI provider, and `cline auth --apikey` is passed explicitly below).
export OPENAI_API_BASE="$AIGATE_BASE"
export OPENAI_API_KEY="$AIGATE_KEY"

AIGATE_MODEL="${AIGATE_MODEL:-}"

# Mirror _cline_builder (cli_tools_router.py:732-764):
#   model chosen -> `cline auth --provider openai-native --apikey <key> \
#                       --modelid <model> --baseurl <base>` then bare `cline`
#   no model     -> bare `cline`
# (Sequential statements instead of `&&` so a failed `cline auth` makes the
# script exit non-zero under `set -e` rather than silently falling through.)
if [ -n "$AIGATE_MODEL" ]; then
  log_msg "launching cline via aigate (openai-native -> ${AIGATE_BASE}/chat/completions, model=$AIGATE_MODEL)"
  cline auth --provider openai-native \
        --apikey "$AIGATE_KEY" \
        --modelid "$AIGATE_MODEL" \
        --baseurl "$AIGATE_BASE"
  exec "$BIN" "$@"
else
  log_msg "launching cline via aigate (openai-native -> ${AIGATE_BASE}/chat/completions); set AIGATE_MODEL to preselect a model"
  exec "$BIN" "$@"
fi

#!/usr/bin/env bash
# aichat.sh — install + launch aichat (Grup C / C6, tool terakhir) for aigate.
#
# Source of truth:
#   aigate preset:  src/backend/cli_presets.py
#                     - line 105 : install = `cargo install aichat`, bin `aichat`
#                     - line 226 : "aichat": LaunchSupport(LAUNCH_VERIFIED)
#                     - line 242 : TERMUX_INSTALL["aichat"] = "pkg install aichat"
#   launch builder: src/backend/cli_tools_router.py _aichat_builder (line 469)
#
# =============================== FACT-BASED (R47/R48) ===============================
# Every claim below is cross-checked across >=3 independent sources.
#
# [S1] aigate code (authoritative for the launch form):
#   - src/backend/cli_presets.py:105 -> aichat install `cargo install aichat`, binary `aichat`.
#   - src/backend/cli_presets.py:226 -> aichat = LAUNCH_VERIFIED (NOT NO_INSTALL/UNSUPPORTED).
#   - src/backend/cli_presets.py:242 -> TERMUX_INSTALL["aichat"] = "pkg install aichat"
#     (comment: "termux-main, verified 0.30.0 runs").
#   - src/backend/cli_tools_router.py:441-448 -> _AICHAT_CLIENT_NAME="aigate",
#     _AICHAT_CONFIG_FILE="aichat-aigate.yaml".
#   - src/backend/cli_tools_router.py:469-511 (_aichat_builder) -> the VERIFIED
#     openai-compatible launch form: write a YAML config containing a `clients:` list
#     entry `type: openai-compatible`, `name: aigate`, `api_base: <base>`,
#     `api_key: <key>`, optional `models:` list, plus a top-level `model:
#     aigate:<raw_model>`. Then launch as
#     `AICHAT_CONFIG_FILE=aichat-aigate.yaml aichat`.
#     Docstring: verified on-device, aichat 0.30.0 `--dry-run` resolves
#     `aigate:<model>` and a real call reached the gateway (only error came from the
#     upstream provider). aichat has NO `custom_providers`/`providers` key (both fail
#     to load) — the field is `clients:` (a list of internally-tagged client configs).
#   - src/backend/cli_tools_router.py:1079-1084 -> resolve() injects every launched
#     tool with env OPENAI_API_BASE=<base> and OPENAI_API_KEY=<key> (ADR-007).
#   - Cross-check: the gateway serves OpenAI-compatible /v1/chat/completions AND
#     /v1/models at gateway_base_url (default http://localhost:8080/v1,
#     cli_tools_router.py:50).
#
# [S2] crates.io registry (https://crates.io/api/v1/crates/aichat):
#   - name=aichat, max_version=0.30.0, description="All-in-one LLM CLI Tool",
#     repository=github.com/sigoden/aichat. Confirms `cargo install aichat` yields the
#     `aichat` binary at version 0.30.0 (matches [S1]'s binary + the aigate comment).
#
# [S3] Official aichat docs + GitHub (github.com/sigoden/aichat, read 2026-09-09):
#   - README "Install": `cargo install aichat`, `brew install aichat`, `pacman -S
#     aichat`, `scoop install aichat`, AND `pkg install aichat` (Android Termux Users);
#     pre-built binaries for macOS/Linux/Windows. => Confirms BOTH the cargo route
#     ([S1] portable preset) AND the Termux `pkg` route ([S1] TERMUX_INSTALL override).
#   - Wiki Configuration-Guide: config is YAML at `<user-config-dir>/aichat/config.yaml`;
#     `clients:` is a list of typed client configs; "Add client for openai-compatible
#     API provider" shows EXACTLY:
#       clients:
#         - type: openai-compatible
#           name: ollama
#           api_base: http://localhost:11434/v1
#           api_key: xxx
#           models:
#             - name: deepseek-r1
#     Model format `model: openai:gpt-4o` (client-name:model) is also documented.
#   - Wiki Environment-Variables: `AICHAT_CONFIG_FILE` = "Customize the location of
#     the config.yaml file." (the exact env var the aigate builder sets). `AICHAT_MODEL`
#     overrides the `model` config item.
#   => CONFIRMS [S1] EXACTLY: aichat is configured via a `clients:` openai-compatible
#      block + `AICHAT_CONFIG_FILE`, and model ids are `<client>:<model>`.
#
# CROSS-CHECK RESULT: aichat in aigate = VERIFIED (LAUNCH_VERIFIED), NOT NO_INSTALL
#   and NOT UNSUPPORTED. It is OpenAI-compatible (the gateway's /v1/chat/completions),
#   wired via a generated `aichat-aigate.yaml` (client `aigate`, openai-compatible,
#   api_base=AIGATE_BASE, api_key=AIGATE_KEY) + env `AICHAT_CONFIG_FILE=aichat-aigate.yaml
#   aichat`. The form is the upstream-documented openai-compatible client route ([S3]),
#   identical to aigate's verified _aichat_builder ([S1]). No anthropic-only /
#   responses-only / not-a-cli blocker. The model id is `aigate:<raw>` where <raw> is
#   the aigate model ref reduced per cli_tools_router.py:_raw_model_for_ref.
#
# =============================== INSTALL (verified) ===============================
# Termux -> `pkg install aichat` ([S1] TERMUX_INSTALL + [S3] README "Android Termux
#   Users", verified 0.30.0 runs). Non-Termux -> `cargo install aichat` ([S1] preset +
#   [S2]/[S3]); cargo compiles from source and needs a Rust toolchain.
#
# =============================== KNOWN-BROKEN CAVEAT (with evidence) ===============================
# * Termux: the `pkg install aichat` route is VERIFIED-WORKING per aigate
#   (cli_presets.py:242 "termux-main, verified 0.30.0 runs"). No known breakage on
#   this platform.
# * Non-Termux via cargo: `cargo install aichat` compiles the crate from source, so a
#   Rust toolchain (cargo/rustc) MUST be present. If `command -v cargo` is empty the
#   install fails — the script reports it and exits 1 with a hint (rustup / pre-built
#   binary / brew / pacman from [S3]). A source build is also slow and may need a C
#   toolchain for native deps; the pre-built binary route is faster where available.
# * aichat speaks the OpenAI Chat Completions wire; the gateway serves
#   /v1/chat/completions + /v1/models. If aigate is not running, `aichat` opens but
#   chat fails — the best-effort probe below warns when the gateway is unreachable.
# * We write a SEPARATE `aichat-aigate.yaml` (never the user's
#   ~/.config/aichat/config.yaml) and only point AICHAT_CONFIG_FILE at it for THIS
#   launch (kilo-pattern, as in the aigate builder), so the user's own aichat config
#   is never touched.
#
# Configure via env (defaults from aigate gateway config via _common.sh):
#   AIGATE_MODEL   optional; forwarded as the aichat model `aigate:<reduced-ref>`
#                  (a gateway-known model id). `provider:NAME:ID` -> `ID`;
#                  `combo:NAME` / bare `ID` kept verbatim; `provider:NAME` alone ->
#                  no model preselected (same reduction as _raw_model_for_ref).
#                  Without it, aichat opens its interactive REPL and you pick/type the
#                  model there. Must match a model the gateway serves.
#   AIGATE_DB_PATH optional override of the aigate SQLite DB path (see _common.sh).

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

detect_os
detect_pm
load_gateway_config   # aigate gateway base (AIGATE_BASE) + internal key (AIGATE_KEY)

BIN="aichat"
# Faithful to aigate preset + aichat upstream: Termux uses the packaged `pkg` route
# (aigate TERMUX_INSTALL, aichat README "Android Termux Users"); everywhere else
# `cargo install aichat` (aigate preset, crates.io, aichat README).
if [ "$AIGATE_OS" = "termux" ]; then
  INSTALL_CMD=(pkg install -y aichat)
else
  INSTALL_CMD=(cargo install aichat)
fi

# Generated, namespaced config (mirrors cli_tools_router.py:448 _AICHAT_CONFIG_FILE).
AICHAT_CONFIG_FILE="aichat-aigate.yaml"

log_msg "os=$AIGATE_OS pm=$AIGATE_PM gateway_base=$AIGATE_BASE"

# --- Idempotent install (never reinstalls when already present) -------------------
if ! ensure_installed "$BIN" "${INSTALL_CMD[@]}"; then
  log_msg "could not install $BIN on this platform; aborting launch."
  if [ "$AIGATE_OS" != "termux" ]; then
    log_msg "HINT (non-Termux): cargo install aichat compiles from source and needs a Rust"
    log_msg "      toolchain (cargo/rustc). Install Rust via 'curl https://sh.rustup.rs -sSf | sh',"
    log_msg "      or grab a pre-built binary / use brew / pacman from the aichat README."
  fi
  exit 1
fi

# --- aichat -> aigate wiring (OpenAI Chat Completions via openai-compatible client) -
# Best-effort reachability check (tolerate missing curl). aigate exposes a
# non-auth GET /v1/models; only a hard connect/timeout failure warns.
if have_cmd curl; then
  if ! curl -fsS -o /dev/null --max-time 3 "${AIGATE_BASE}/models" 2>/dev/null; then
    rc=$?
    if [ "$rc" -eq 7 ] || [ "$rc" -eq 28 ]; then
      log_msg "WARN: aigate not reachable at $AIGATE_BASE (check gateway_base_url / is aigate running?);"
      log_msg "      aichat will open but chat will fail. Start aigate first."
    fi
  fi
fi

# Reduce an aigate model ref to the raw id aichat sends upstream, matching
# cli_tools_router.py:_raw_model_for_ref (provider:NAME:ID -> ID; combo:NAME /
# bare ID kept verbatim; provider:NAME -> none).
AIGATE_MODEL="${AIGATE_MODEL:-}"
RAW_MODEL=""
if [ -n "$AIGATE_MODEL" ]; then
  case "$AIGATE_MODEL" in
    provider:*:*) RAW_MODEL="${AIGATE_MODEL#provider:*:}" ;;
    provider:*)   RAW_MODEL="" ;;
    *)            RAW_MODEL="$AIGATE_MODEL" ;;
  esac
fi

# Escape for a YAML double-quoted scalar (mirrors _yaml_str in the backend builder):
# backslash and double-quote. Pure parameter expansion — NO command substitution,
# so nothing in the gateway base/key/model can be reinterpreted by the shell.
esc() { local s="$1"; s="${s//\\/\\\\}"; s="${s//\"/\\\"}"; printf '%s' "$s"; }
ESC_BASE="$(esc "$AIGATE_BASE")"
ESC_KEY="$(esc "$AIGATE_KEY")"
ESC_MODEL="$(esc "$RAW_MODEL")"

# Write the namespaced aichat YAML config (openai-compatible client -> aigate).
# Built with printf + args (NOT a heredoc) so the base/key/model values are emitted
# as literal data — no shell expansion / command-substitution can occur (avoids the
# swe-agent.sh backtick/`$()` bug). This mirrors cli_tools_router.py:_aichat_builder.
log_msg "writing $AICHAT_CONFIG_FILE (client 'aigate' openai-compatible -> $AIGATE_BASE)"
{
  if [ -n "$RAW_MODEL" ]; then
    printf 'model: "aigate:%s"\n' "$ESC_MODEL"
  fi
  printf 'clients:\n'
  printf '  - type: openai-compatible\n'
  printf '    name: "aigate"\n'
  printf '    api_base: "%s"\n' "$ESC_BASE"
  printf '    api_key: "%s"\n' "$ESC_KEY"
  if [ -n "$RAW_MODEL" ]; then
    printf '    models:\n'
    printf '      - name: "%s"\n' "$ESC_MODEL"
  fi
} > "$AICHAT_CONFIG_FILE"

# Env injection every tool gets (cli_tools_router.py:1081-1084). aichat's `aigate`
# client reads api_base/api_key from the config above (not these envs), but the
# export matches the router contract and is harmless.
export OPENAI_API_BASE="$AIGATE_BASE"
export OPENAI_API_KEY="$AIGATE_KEY"

if [ -n "$RAW_MODEL" ]; then
  log_msg "launching $BIN via aigate (OpenAI-compatible endpoint ${AIGATE_BASE}/chat/completions, model=aigate:${RAW_MODEL})"
else
  log_msg "launching $BIN via aigate (OpenAI-compatible endpoint ${AIGATE_BASE}/chat/completions; interactive REPL — pick model there)"
fi
# AICHAT_CONFIG_FILE scopes our config to this launch only (matches the backend
# builder). "$@" passes through any extra flags the operator appends. Bare `aichat`
# opens the interactive REPL (no model flag needed — the config carries it).
export AICHAT_CONFIG_FILE
exec "$BIN" "$@"

#!/usr/bin/env bash
# oterm.sh — install + launch oterm (Grup C / C4) for aigate.
#
# Source of truth:
#   aigate preset:  src/backend/cli_presets.py
#                     - line 103: install _pip("oterm") -> `pip install oterm`, bin `oterm`
#                     - line 222: "oterm": LaunchSupport(LAUNCH_VERIFIED)
#   launch builder: src/backend/cli_tools_router.py _oterm_builder (line 891)
#
# =============================== FACT-BASED (R47/R48) ===============================
# Every claim below is cross-checked across >=3 independent sources.
#
# [S1] aigate code (authoritative for the launch form):
#   - src/backend/cli_presets.py:103 -> install = `pip install oterm`, binary = `oterm`.
#   - src/backend/cli_presets.py:222 -> oterm = LAUNCH_VERIFIED (NOT NO_INSTALL/UNSUPPORTED);
#     the inline comment (lines 220-221) cites ggozad.github.io/oterm app_config.md v0.24.0.
#   - src/backend/cli_tools_router.py:891-917 (_oterm_builder) -> the documented
#     OpenAI-compatible form: write a config.json containing an `openaiCompatible`
#     block with a named endpoint ("aigate") whose `base_url` = gateway base and
#     `api_key` = "${OPENAI_API_KEY}" (resolved by oterm from the exported env).
#     The config lives in a NAMESPACED data dir `.oterm-aigate/` and is scoped to
#     the launch via `OTERM_DATA_DIR=.oterm-aigate oterm`. The oterm CLI has NO
#     model/base/key flags (src/oterm/cli/oterm.py), so the command is identical
#     for every model ref and nothing is invented — the user types/picks the
#     gateway model id in oterm's new-chat dialog.
#   - src/backend/cli_tools_router.py:1081-1084 -> resolve() injects every tool with
#     env OPENAI_API_BASE=<base>  and  OPENAI_API_KEY=<key>  (ADR-007 plaintext key).
#   - Cross-check: the gateway serves OpenAI-compatible /v1/chat/completions AND
#     /v1/models; oterm's `openaiCompatible` provider points at the gateway base
#     url and, when /v1/models is exposed, suggests model ids as you type.
#
# [S2] PyPI registry (https://pypi.org/pypi/oterm/json, fetched):
#   - name=oterm, version=0.24.0, summary="The terminal client for Ollama, OpenAI,
#     Anthropic, and any pydantic-ai-supported provider."  (matches aigate's v0.24.0).
#   - requires_python = ">=3.10"  (pure-python; py3-none-any wheels).
#   - requires_dist includes pydantic==2.13.5 -> pydantic-core -> `jiter` (a
#     Rust-based wheel) as a TRANSITIVE dependency. This is the same Rust dep that
#     llm.sh proved has no prebuilt wheel for cpython-3.14-aarch64-linux-android
#     on this exact device (see the KNOWN-BROKEN caveat below).
#   - homepage/repo = github.com/ggozad/oterm, docs = ggozad.github.io/oterm — the
#     genuine ggozad project, NOT an unrelated squatter.
#
# [S3] Official oterm docs + GitHub (ggozad.github.io/oterm, read 2026-09-09):
#   - installation page: `pip install oterm` is a documented install method
#     (alongside uvx/brew/yay/nix/pkg); the binary is `oterm` (run `oterm`, or
#     `uvx oterm`, or `oterm --data-dir` to print the resolved data dir).
#   - app_config page: config is a JSON `config.json`; the directory is
#     OS-specific (~/.local/share/oterm on Linux), honours XDG_DATA_HOME, and can
#     be OVERRIDDEN ENTIRELY by setting `OTERM_DATA_DIR`.
#   - `openaiCompatible` config block: named endpoints with `base_url` (required)
#     + `api_key` (optional; "Reference an environment variable with ${VAR}").
#     "When configured, an OpenAI Compatible provider appears in the provider
#     dropdown. Select it, choose your endpoint, and type the model name. If the
#     endpoint exposes /v1/models, suggestions appear as you type."
#   - Model is chosen in the new-chat UI, never via a launch flag (confirmed by
#     [S1]'s reading of src/oterm/cli/oterm.py).
#   => CONFIRMS [S1]'s launch form EXACTLY.
#
# CROSS-CHECK RESULT: oterm in aigate = VERIFIED (LAUNCH_VERIFIED), OpenAI-compatible,
#   wired via a NAMESPACED `.oterm-aigate/config.json` (`openaiCompatible.aigate`
#   with base_url = AIGATE_BASE, api_key = "${OPENAI_API_KEY}") + env
#   OTERM_DATA_DIR=.oterm-aigate, then a bare `oterm` (interactive TUI). No
#   anthropic-only / responses-only / not-a-cli blocker. The form is the upstream-
#   documented openaiCompatible config route, not a guessed flag.
#
# =============================== INSTALL (verified) ===============================
# aigate preset [S1] = `pip install oterm`. We run it as `python3 -m pip install
# oterm` (portable across shells, same convention as llm.sh / openhands.sh).
# Binary `oterm` [S2]/[S3]. There is NO Termux override in cli_presets.TERMUX_INSTALL
# (only aichat + codex are listed), so this pip route is used on every OS.
#
# =============================== KNOWN-BROKEN CAVEAT (with evidence) ===============================
# * On THIS device (Termux 0.11x, aarch64, Python 3.14.6) `pip install oterm` is
#   EXPECTED TO FAIL, but for a reason that is NOT specific to oterm: oterm
#   transitively depends on `jiter` (via pydantic 2.13.5 -> pydantic-core), a
#   Rust-based wheel. llm.sh, on this SAME device, already proved the failure with
#   a real `pip install --dry-run llm` run:
#       Target triple not supported by rustup: aarch64-unknown-linux-android
#       Rust not found, installing into a temporary directory
#       ERROR: Failed to build 'jiter' ... maturin
#   PyPI jiter 0.16.0 publishes 104 wheels incl. cp314 manylinux_aarch64 but ZERO
#   android wheels, so pip falls back to the sdist and tries to compile Rust.
#   Evidence on THIS host: `command -v rustc`/`command -v cargo`/`command -v rustup`
#   all return nothing (no Rust toolchain), and `python3 --version` => Python 3.14.6.
#   Workaround: install a Rust toolchain (pkg install rust / rustup) so the jiter
#   sdist can build, OR run oterm from a manylinux/non-Android environment. This is a
#   platform/wheel-availability issue (Android SOABI), NOT a defect in oterm itself.
# * The gateway base url is the ONLY thing oterm needs to reach aigate (the key is
#   referenced via ${OPENAI_API_KEY}, resolved at runtime). If aigate is not running,
#   the `oterm --data-dir` TUI opens but model suggestions / chat will fail — the
#   best-effort probe below warns when the gateway is unreachable.
# * Chat history (store.db) lives inside OTERM_DATA_DIR; because aigate scopes its
#   launch to a fresh `.oterm-aigate/` dir, history for these launches starts empty
#   and the user's own oterm data (~/.local/share/oterm) is never touched.
#
# Configure via env (defaults from aigate gateway config via _common.sh):
#   AIGATE_MODEL   intentionally NOT used — oterm has no launch-time model flag or
#                  config key ([S1]/[S3]); the model is picked in the new-chat
#                  dialog. This mirrors _oterm_builder, which ignores the model ref.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

detect_os
detect_pm
load_gateway_config   # aigate gateway base (AIGATE_BASE) + internal key (AIGATE_KEY)

BIN="oterm"
# Faithful to the aigate preset (`pip install oterm`); `python3 -m pip` is portable.
INSTALL_CMD=(python3 -m pip install oterm)

# Namespaced data dir + config path (mirrors cli_tools_router.py:884-885/_oterm_builder).
# Relative to the CWD, exactly like the backend builder, so nothing user-owned is
# touched and history for aigate launches is isolated.
OTERM_DATA_DIR=".oterm-aigate"
OTERM_CONFIG=".oterm-aigate/config.json"

log_msg "os=$AIGATE_OS pm=$AIGATE_PM gateway_base=$AIGATE_BASE"

# --- Idempotent install (never reinstalls when already present) -------------------
if ! ensure_installed "$BIN" "${INSTALL_CMD[@]}"; then
  log_msg "could not install $BIN on this platform; aborting launch."
  if [ "$AIGATE_OS" = "termux" ]; then
    log_msg "HINT (Termux aarch64): oterm pulls the Rust-based wheel 'jiter' transitively"
    log_msg "      (pydantic 2.13.5 -> pydantic-core). jiter has no prebuilt wheel for"
    log_msg "      cpython-3.14-aarch64-linux-android, so the sdist build fails (no rust/"
    log_msg "      rustup). Install a Rust toolchain (pkg install rust) or run oterm from a"
    log_msg "      manylinux environment, then re-run this script."
  fi
  exit 1
fi

# --- oterm -> aigate wiring (OpenAI Chat Completions via openaiCompatible config) --
# Best-effort reachability check (tolerate missing curl). aigate exposes a
# non-auth GET /v1/models; only a hard connect/timeout failure warns.
if have_cmd curl; then
  if ! curl -fsS -o /dev/null --max-time 3 "${AIGATE_BASE}/models" 2>/dev/null; then
    rc=$?
    if [ "$rc" -eq 7 ] || [ "$rc" -eq 28 ]; then
      log_msg "WARN: aigate not reachable at $AIGATE_BASE (check gateway_base_url / is aigate running?);"
      log_msg "      oterm will open but model suggestions and chat will fail. Start aigate first."
    fi
  fi
fi

# Env injection every tool gets (cli_tools_router.py:1081-1084). oterm's config
# references "${OPENAI_API_KEY}" and resolves it from this exported value at load.
export OPENAI_API_BASE="$AIGATE_BASE"
export OPENAI_API_KEY="$AIGATE_KEY"

# Write the namespaced oterm config.json (openaiCompatible.aigate block).
# Single, unquoted heredoc: ${AIGATE_BASE} expands to the gateway base; the api_key
# is written LITERALLY as "${OPENAI_API_KEY}" (the leading backslash escapes bash's
# expansion) so oterm — not bash — resolves the env reference at startup.
log_msg "writing $OTERM_CONFIG (openaiCompatible.aigate -> $AIGATE_BASE)"
mkdir -p "$OTERM_DATA_DIR"
cat > "$OTERM_CONFIG" <<AIGATE_EOF
{
  "openaiCompatible": {
    "aigate": {
      "base_url": "${AIGATE_BASE}",
      "api_key": "\${OPENAI_API_KEY}"
    }
  }
}
AIGATE_EOF

log_msg "launching $BIN via aigate (OpenAI-compatible endpoint ${AIGATE_BASE}/chat/completions)"
log_msg "  In oterm's new-chat dialog pick the 'aigate' (OpenAI Compatible) provider,"
log_msg "  then type/pick a gateway model id (suggested live from ${AIGATE_BASE}/models)."
# Bare `oterm` = interactive TUI. OTERM_DATA_DIR is scoped to this process only
# (matches cli_tools_router.py:917: `OTERM_DATA_DIR=.oterm-aigate oterm`).
exec OTERM_DATA_DIR="$OTERM_DATA_DIR" "$BIN" "$@"

#!/usr/bin/env bash
# openhands.sh — install + launch OpenHands CLI (Grup B / B1) for aigate.
#
# Source of truth: documents/pm/cli-tools-install-backlog.md (B1);
# aigate preset:  src/backend/cli_presets.py
#                   - line 88 : install _pip("openhands") -> `pip install openhands`
#                   - line 190: "openhands": LaunchSupport(LAUNCH_VERIFIED)
# launch builder: src/backend/cli_tools_router.py _openhands_builder (line 960)
#
# =============================== FACT-BASED (R47/R48) ===============================
# Every claim below is cross-checked across >=2 independent sources:
#
# [S1] aigate code (authoritative for the launch form):
#   - src/backend/cli_presets.py:88  -> install = `pip install openhands`, bin `openhands`
#   - src/backend/cli_presets.py:190 -> openhands = LAUNCH_VERIFIED (not NO_INSTALL/UNSUPPORTED)
#   - src/backend/cli_tools_router.py:920-972 (_openhands_builder) -> the documented
#     launch form is the LLM_* env route + `--override-with-envs`:
#       LLM_MODEL=openai/<raw>   (optional; litellm-style `openai/<id>`)
#       LLM_BASE_URL=<gateway base>      (= AIGATE_BASE, e.g. http://localhost:8080/v1)
#       LLM_API_KEY=<internal key>       (= AIGATE_KEY)
#       + bare `openhands` = interactive Terminal (TUI); REQUIRES --override-with-envs
#         to make the CLI read the LLM_* env vars (otherwise they are ignored).
#   - Cross-check: the gateway serves OpenAI-compatible /v1/chat/completions AND
#     /v1/models (router.py:1079-1084 inject OPENAI_API_BASE/OPENAI_API_KEY; the
#     LLM_MODEL `openai/<id>` is resolved by the gateway the same way as the other
#     verified tools).
#
# [S2] PyPI registry (https://pypi.org/pypi/openhands/json, fetched):
#   - name=openhands, version=1.16.0, summary="OpenHands CLI - Terminal User Interface
#     for OpenHands AI Agent"
#   - requires_python = "==3.12.*"  (HARD pin — pure-python py3-none-any wheel)
#   - bin: `openhands` (project declares `openhands = "openhands_cli.entrypoint:main"`)
#   => `pip install openhands` ONLY resolves on Python 3.12. This is the aigate preset's
#      install string, but it will FAIL on platforms whose system python is 3.13/3.14.
#
# [S3] Official OpenHands docs + GitHub (OpenHands/OpenHands-CLI, read 2026-09-09):
#   - GitHub README "Installation": recommended `uv tool install openhands --python 3.12`
#     (uv 0.11.6+, manages its own 3.12 interpreter so it works regardless of system
#     python); alternative standalone binary `curl -fsSL https://install.openhands.dev/install.sh | sh`.
#   - GitHub README "Configuration": "By default, environment variables like LLM_API_KEY,
#     LLM_MODEL, and LLM_BASE_URL are ignored; pass --override-with-envs to apply them
#     (not persisted)."
#   - Docs command-reference (docs.openhands.dev/openhands/usage/cli/command-reference):
#       `--override-with-envs` -> "Apply environment variables (LLM_API_KEY, LLM_MODEL,
#       LLM_BASE_URL) to override stored settings"
#       Env table: LLM_API_KEY, LLM_MODEL (requires --override-with-envs),
#       LLM_BASE_URL (requires --override-with-envs).
#       Running Modes: `openhands` = Terminal (TUI) "Interactive development".
#   => CONFIRMS [S1]'s launch form exactly.
#
# CROSS-CHECK RESULT: openhands in aigate = VERIFIED (LAUNCH_VERIFIED), NOT NO_INSTALL
#   and NOT UNSUPPORTED. It is OpenAI-compatible (the gateway's /v1/chat/completions),
#   wired via LLM_* env vars + --override-with-envs to the aigate gateway base/key.
#   No anthropic-only / responses-only / not-a-cli blocker.
#
# =============================== INSTALL (verified) ===============================
# Two verified routes (both from the sources above):
#   (a) `uv tool install openhands --python 3.12`  [S3, official recommended] —
#       preferred: uv fetches a managed 3.12 so it works even on Python 3.13/3.14 hosts.
#   (b) `python3 -m pip install openhands`          [S1 preset / S2 PyPI] —
#       faithful to the aigate preset, but ONLY succeeds on Python 3.12 (requires_python
#       ==3.12.*). Used as fallback when `uv` is absent.
# Standalone binary [S3] is documented in a comment as a third option.
#
# =============================== KNOWN-BROKEN CAVEAT (with evidence) ===============================
# * Python version: PyPI requires_python ==3.12.* [S2]. On THIS device python3 is
#   3.14.6 and `uv` is NOT installed, so the pip route [S1/S2] WILL FAIL here:
#       $ python3 -m pip install openhands  -> "ERROR: Package 'openhands' requires
#         a different Python: 3.14.6 not in '==3.12.*'"
#   Fix: install uv (https://docs.astral.sh/uv/) then re-run — the script prefers the
#   uv route automatically. (Recorded, not assumed: `python3 -V` => Python 3.14.6,
#   `command -v uv` => none, on this host.)
# * The PyPI `openhands-ai` package (1.x) is the Agent-Canvas/SERVER stack and ships
#   NO terminal CLI — do NOT install it [S1 comment lines 924-931]. The preset's
#   `pip install openhands` is already the correct package.
# * Upstream repo is marked "no longer actively maintained" (Agent Canvas is flagship)
#   [S3 README "Project status"] — functional but frozen; pin 1.16.0.
#
# Configure via env (defaults from aigate gateway config via _common.sh):
#   AIGATE_MODEL   optional; forwarded to openhands as LLM_MODEL=openai/<AIGATE_MODEL>
#                  (must match a gateway-served model id). Without it, openhands launches
#                  with its own default model; base+key still point at aigate.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

detect_os
detect_pm
load_gateway_config   # aigate gateway base (AIGATE_BASE) + internal key (AIGATE_KEY)

# --- openhands / Python version guard (runs BEFORE any pip/uv install) ---
# openhands PyPI requires_python ==3.12.* (verified S2 in header; openhands 1.16.0).
# `python3 -m pip install openhands` resolves ONLY on Python 3.12 and FAILS on
# 3.13/3.14 ("requires a different Python: X not in '==3.12.*'"). uv, however,
# fetches its own managed 3.12 interpreter (official recommended route, S3), so it
# works regardless of the system python. Refuse early (exit 1) only when uv is
# absent AND system python is not 3.12 — clear message, no raw pip failure.
if have_cmd uv; then
  log_msg "uv detected — akan pakai 'uv tool install openhands --python 3.12' (kelola 3.12 sendiri)."
elif have_cmd python3; then
  pyver="$(python3 -c 'import sys;print("%d.%d" % sys.version_info[:2])' 2>/dev/null || true)"
  py_maj="${pyver%%.*}"
  py_min="${pyver#*.}"; py_min="${py_min%%[!0-9]*}"
  if [ -n "$py_maj" ] && [ -n "$py_min" ]; then
    if [ "$py_maj" -eq 3 ] && [ "$py_min" -eq 12 ]; then
      log_msg "python3 = $pyver (cocok dengan openhands requires_python ==3.12.*); pip route OK."
    else
      log_msg "ERROR: openhands butuh persis Python 3.12 (PyPI requires_python ==3.12.*);"
      log_msg "       device ini pakai Python ${pyver}."
      log_msg "       Saran: pasang Python 3.12 (mis. 'pkg install python3.12', pyenv, atau venv 3.12),"
      log_msg "       ATAU pasang uv (https://docs.astral.sh/uv/) agar openhands pakai 3.12 sendiri, lalu re-run."
      exit 1
    fi
  else
    log_msg "WARN: gagal parse 'python3 --version' (didapat '${pyver}'); tetap coba install."
  fi
else
  log_msg "WARN: python3 tidak ditemukan; tidak bisa cek versi Python sebelum install."
fi

BIN="openhands"

log_msg "os=$AIGATE_OS pm=$AIGATE_PM gateway_base=$AIGATE_BASE"

# --- Idempotent install (verified routes, never reinstalls when present) ---------
# Prefer uv (official recommended; manages its own Python 3.12, sidesteps the
# ==3.12.* system-python pin). Fall back to pip (aigate preset) when uv is missing.
if have_cmd uv; then
  INSTALL_CMD=(uv tool install openhands --python 3.12)
else
  INSTALL_CMD=(python3 -m pip install openhands)
fi

if ! ensure_installed "$BIN" "${INSTALL_CMD[@]}"; then
  log_msg "could not install $BIN on this platform; aborting launch."
  log_msg "HINT: on Python != 3.12 the pip route fails (PyPI requires ==3.12.*)."
  log_msg "      Install uv (https://docs.astral.sh/uv/) then re-run, OR use the"
  log_msg "      standalone binary: curl -fsSL https://install.openhands.dev/install.sh | sh"
  exit 1
fi

# uv installs the binary into ~/.local/bin (or $XDG_BIN_HOME / $HOME/.cargo/bin);
# make sure that dir is on PATH before the launch check / exec.
for _d in "${HOME:-}/.local/bin" "${HOME:-}/.cargo/bin"; do
  case ":$PATH:" in
    *":$_d:"*) ;;
    *) [ -d "$_d" ] && PATH="$_d:$PATH" ;;
  esac
done
export PATH
# Re-validate now that PATH may include the install dir.
if ! have_cmd "$BIN"; then
  log_msg "WARN: $BIN not found on PATH after install (install dir may differ); launch may fail."
fi

# --- Factual Python-version caveat (PyPI requires_python ==3.12.* verified S2) ----
if have_cmd python3; then
  pyver="$(python3 -c 'import sys;print("%d.%d" % sys.version_info[:2])' 2>/dev/null || true)"
  case "$pyver" in
    3.13|3.14|3.1[5-9]|3.[2-9][0-9])
      if ! have_cmd uv; then
        log_msg "NOTE: python3 is $pyver but openhands requires ==3.12.* (PyPI [S2])."
        log_msg "      The pip install above likely failed; use uv or the standalone binary."
      fi
      ;;
  esac
fi

# --- openhands -> aigate wiring (OpenAI-compatible via LLM_* env) ----------------
# Best-effort reachability check (tolerate missing curl). aigate exposes a
# non-auth GET /v1/models; only a hard connect/timeout failure warns.
if have_cmd curl; then
  if ! curl -fsS -o /dev/null --max-time 3 "${AIGATE_BASE}/models" 2>/dev/null; then
    rc=$?
    if [ "$rc" -eq 7 ] || [ "$rc" -eq 28 ]; then
      log_msg "WARN: aigate not reachable at $AIGATE_BASE (check gateway_base_url / is aigate running?);"
      log_msg "      openhands will fail to connect. Start aigate first if it is not running."
    fi
  fi
fi

# Env injection every tool gets (cli_tools_router.py:1081-1084).
export OPENAI_API_BASE="$AIGATE_BASE"
export OPENAI_API_KEY="$AIGATE_KEY"

# LLM_* env route — mirrors _openhands_builder (cli_tools_router.py:960-972) EXACTLY.
# Without --override-with-envs the CLI ignores LLM_* env (GitHub README [S3] + docs).
export LLM_BASE_URL="$AIGATE_BASE"
export LLM_API_KEY="$AIGATE_KEY"

AIGATE_MODEL="${AIGATE_MODEL:-}"
if [ -n "$AIGATE_MODEL" ]; then
  export LLM_MODEL="openai/${AIGATE_MODEL}"
  log_msg "preselected model: openai/${AIGATE_MODEL}"
fi

log_msg "launching $BIN via aigate (OpenAI-compatible endpoint ${AIGATE_BASE}/chat/completions)"
# bare `openhands` = interactive Terminal (TUI); --override-with-envs applies LLM_* env.
exec "$BIN" --override-with-envs "$@"

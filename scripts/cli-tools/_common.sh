#!/usr/bin/env bash
# _common.sh — shared helper for aigate CLI-tool install/launch scripts.
#
# Sourced (NOT executed) by each tool script, e.g. claude.sh:
#     source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
#
# What it provides (all helpers are idempotent / no-op safe):
#   detect_os             -> AIGATE_OS  (termux | linux | mac | windows | unknown)
#   detect_pm             -> AIGATE_PM  (pkg | apt | brew | winget | "" )
#   load_gateway_config   -> AIGATE_BASE (default http://localhost:8080/v1)
#                            AIGATE_KEY  (default aigate-local)
#   have_cmd <bin>        -> true if `command -v <bin>` succeeds
#   ensure_installed <bin> <install...> -> install only when missing
#   log_msg <msg>         -> timestamped line on stderr
#
# Gateway wiring contract (mirrors src/backend/cli_tools_router.py):
#   aigate exposes an OpenAI-compatible endpoint at gateway_base_url (default
#   http://localhost:8080/v1) and an internal_api_key (default "aigate-local").
#   Tools that speak OpenAI chat/completions receive these as OPENAI_API_BASE /
#   OPENAI_API_KEY. Tools on a different wire format (e.g. claude -> Anthropic
#   Messages) are launched natively instead — aigate itself returns 409
#   tool_unsupported for them, so we mirror that behaviour.
#
# Cross-platform: these are bash scripts. On Windows they are meant to run under
# WSL or Git Bash (where bash + the upstream CLIs are available); native
# cmd/PowerShell is out of scope.

# Guard against double-sourcing.
if [ -n "${AIGATE_COMMON_LOADED:-}" ]; then
  return 0 2>/dev/null || true
fi
AIGATE_COMMON_LOADED=1

log_msg() { printf '[aigate-cli] %s\n' "$*" >&2; }

have_cmd() { command -v "$1" >/dev/null 2>&1; }

detect_os() {
  local os="unknown"
  case "$(uname -s 2>/dev/null || echo unknown)" in
    Linux*)
      if [ -n "${TERMUX_VERSION:-}" ] || [ -d "/data/data/com.termux/files" ]; then
        os="termux"
      else
        os="linux"
      fi ;;
    Darwin*) os="mac" ;;
  esac
  # Windows layers that still present a bash shell.
  case "$(uname -o 2>/dev/null || echo)" in
    *Cygwin*|*MINGW*|*MSYS*) os="windows" ;;
  esac
  if [ -n "${WSL_DISTRO_NAME:-}" ] || grep -qi microsoft /proc/version 2>/dev/null; then
    os="windows"
  fi
  AIGATE_OS="$os"
  export AIGATE_OS
}

detect_pm() {
  case "${AIGATE_OS:-}" in
    termux)  AIGATE_PM="pkg" ;;
    linux)   AIGATE_PM="apt" ;;
    mac)     AIGATE_PM="brew" ;;
    windows) AIGATE_PM="winget" ;;  # WSL keeps its distro PM; choco is an alternative
    *)       AIGATE_PM="" ;;
  esac
  export AIGATE_PM
}

# Read aigate gateway base + internal key from its SQLite DB (~/.aigate/aigate.db).
# Falls back to the documented defaults when the DB is absent or python3 missing.
load_gateway_config() {
  local base="http://localhost:8080/v1"
  local key="aigate-local"
  local db="${AIGATE_DB_PATH:-$HOME/.aigate/aigate.db}"
  if [ -f "$db" ] && have_cmd python3; then
    local out
    out="$(python3 - "$db" <<'PY' 2>/dev/null
import sqlite3, sys
db = sys.argv[1]
try:
    con = sqlite3.connect(db)
    cur = con.cursor()
    try:
        cur.execute("SELECT value FROM setting WHERE key='gateway_base_url'")
        row = cur.fetchone()
        if row and row[0]:
            print("BASE=" + str(row[0]))
    except Exception:
        pass
    try:
        cur.execute("SELECT internal_api_key FROM endpoint "
                    "WHERE access_control_enabled=1 ORDER BY id LIMIT 1")
        row = cur.fetchone()
        if row and row[0]:
            print("KEY=" + str(row[0]))
    except Exception:
        pass
    con.close()
except Exception:
    pass
PY
)"
    if [ -n "$out" ]; then
      while IFS= read -r line; do
        case "$line" in
          BASE=*) base="${line#BASE=}" ;;
          KEY=*)  key="${line#KEY=}" ;;
        esac
      done <<<"$out"
    fi
  fi
  AIGATE_BASE="$base"
  AIGATE_KEY="$key"
  export AIGATE_BASE AIGATE_KEY
}

# Install <bin> only when missing. Remaining args are the install command.
ensure_installed() {
  local bin="$1"; shift
  if have_cmd "$bin"; then
    log_msg "already installed: $bin"
    return 0
  fi
  log_msg "installing $bin via: $*"
  if "$@"; then
    if have_cmd "$bin"; then
      log_msg "installed: $bin"
      return 0
    fi
    log_msg "WARN: install finished but '$bin' still not on PATH"
    return 1
  fi
  log_msg "ERROR: failed to install $bin"
  return 1
}

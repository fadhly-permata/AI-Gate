#!/usr/bin/env bash
#
# bootstrap.sh — cold-start bootstrap for aigate (Termux / Linux / macOS).
#
# One command that "just works" on a machine that has nothing — not even
# Python. It ensures a Python interpreter >= 3.10 exists, warns if `git` is
# missing, then hands off to `run.py` (which already installs the pip
# dependencies). It does NOT touch run.py and does NOT duplicate its pip logic.
#
# Usage:
#   bash scripts/bootstrap.sh                 # ensure Python, then start aigate
#   bash scripts/bootstrap.sh --check-only     # detect only; no install, no launch
#   bash scripts/bootstrap.sh <args...>        # extra args forwarded to run.py
#
# Behaviour guarantees:
#   * Non-interactive & idempotent: a second run on a ready machine is a no-op
#     that just launches (existing interpreter is detected, install skipped).
#   * NEVER calls `sudo` and NEVER prompts for a password. On a regular Linux
#     box a system package manager needs root; if we are not already root we do
#     NOT escalate — we fall back to the userspace `uv` path instead. Termux
#     (`pkg`) and macOS (`brew`) install into a user prefix, so no root needed.
#
# Keep this file parseable by a strict POSIX shell (`dash -n`). It is intended
# to be *run* with bash (see the shebang and the `--check-only` CI gate).

set -euo pipefail

# --- Where is the repo root, so this works from any CWD? ---------------------
# Script lives in <repo>/scripts/, so root is one level up. No hardcoded paths.
SELF="${BASH_SOURCE:-$0}"
SCRIPT_DIR="$(cd "$(dirname "$SELF")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RUN_PY="$REPO_ROOT/run.py"

# Minimum interpreter version. Mirrors pyproject.toml [project]
# requires-python = ">=3.10" (line 11) — that entry is the source of truth;
# keep this constant in sync if it ever changes (same pattern as run.py:18-21).
MIN_PY_MAJOR=3
MIN_PY_MINOR=10
# Version the bootstrap asks package managers / uv to install (per PM handover).
INSTALL_PY_VERSION="3.12"

CHECK_ONLY=0

# --- tiny output helpers (stderr so stdout stays clean for run.py) ----------
log()   { printf '%s\n' "$*" >&2; }
note()  { printf '[aigate-bootstrap] %s\n' "$*" >&2; }
warn()  { printf '[aigate-bootstrap] WARNING: %s\n' "$*" >&2; }

die() {
  log ""
  log "aigate could not start automatically."
  log "$*"
  log ""
  log "Once Python 3.10 or newer is on this machine, run this file again."
  exit 1
}

usage() {
  cat >&2 <<'EOF'
Usage: bash scripts/bootstrap.sh [--check-only] [args passed to run.py]

  --check-only   Report the detected platform, Python interpreter, and whether
                 git is present. Does NOT install anything and does NOT start
                 aigate. Intended for test gates.
  -h, --help     Show this help.
EOF
}

# --- does an interpreter command exist AND meet the minimum version? --------
# $1 = the interpreter command name (e.g. python3). Returns 0 when usable.
interpreter_ok() {
  command -v "$1" >/dev/null 2>&1 || return 1
  "$@" -c "import sys; sys.exit(0 if sys.version_info[:2] >= ($MIN_PY_MAJOR, $MIN_PY_MINOR) else 1)" \
    >/dev/null 2>&1
}

# --- detect platform: termux | linux | mac | unknown ------------------------
# Termux must be checked BEFORE generic Linux (Termux is Linux but uses `pkg`,
# not apt, and has no system-root package manager).
detect_platform() {
  PLATFORM="unknown"
  case "$(uname -s 2>/dev/null || echo unknown)" in
    Linux*)
      if [ -n "${TERMUX_VERSION:-}" ] || [ -n "${PREFIX:-}" ] \
         || [ -d "/data/data/com.termux/files" ] \
         || printf '%s' "${PREFIX:-}" | grep -q com.termux; then
        PLATFORM="termux"
      else
        PLATFORM="linux"
      fi ;;
    Darwin*) PLATFORM="mac" ;;
  esac
}

# --- find an already-present usable interpreter (skip install if found) -----
find_interpreter() {
  PY=""
  if interpreter_ok python3; then PY="$(command -v python3)"; return 0; fi
  if interpreter_ok python;  then PY="$(command -v python)";  return 0; fi
  if interpreter_ok "python$MIN_PY_MAJOR.$MIN_PY_MINOR"; then
    PY="$(command -v "python$MIN_PY_MAJOR.$MIN_PY_MINOR")"; return 0
  fi
  return 1
}

# --- pick the native install command for this platform ----------------------
# Echoes the first package manager that exists, or empty. We deliberately do
# NOT prefix any of these with sudo (see sudo guarantee in the header).
native_install_hint() {
  case "$PLATFORM" in
    termux)
      if command -v pkg >/dev/null 2>&1; then printf 'pkg'; fi ;;
    mac)
      if command -v brew >/dev/null 2>&1; then printf 'brew'; fi ;;
    linux)
      # Root is required by all of these. Only suggest one if we are already
      # root; otherwise the caller falls back to the userspace uv path.
      if [ "$(id -u)" = "0" ]; then
        for pm in apt-get dnf yum pacman zypper; do
          if command -v "$pm" >/dev/null 2>&1; then printf '%s' "$pm"; return 0; fi
        done
      fi ;;
  esac
  return 0
}

# --- run the native package install (best-effort; caller decides fallback) --
# Returns 0 on success. Never blocks for a password: everything is -y / non-interactive,
# and the only way here needs effective root, which we already checked.
native_install() {
  pm="$(native_install_hint)"
  [ -n "$pm" ] || return 1
  note "installing Python via native package manager: $pm"
  case "$pm" in
    pkg)     pkg install -y python ;;
    brew)    brew install "python@$INSTALL_PY_VERSION" ;;
    apt-get) apt-get install -y python3 ;;
    dnf)     dnf install -y python3 ;;
    yum)     yum install -y python3 ;;
    pacman)  pacman -Sy --noconfirm python ;;
    zypper)  zypper --non-interactive install python3 ;;
    *)       return 1 ;;
  esac
}

# --- userspace uv fallback (the no-sudo path) -------------------------------
# Installs `uv` itself into ~/.local/bin (no root), then a managed CPython,
# then resolves that interpreter's absolute path into PY. uv does not persist a
# PATH change we rely on, so we add the common install dirs for this session
# only and then use `uv python find` to get the concrete executable path.
uv_install() {
  note "native Python install unavailable — falling back to userspace uv (no root)"
  if ! command -v uv >/dev/null 2>&1; then
    if command -v curl >/dev/null 2>&1; then
      curl -LsSf https://astral.sh/uv/install.sh | sh
    elif command -v wget >/dev/null 2>&1; then
      wget -qO- https://astral.sh/uv/install.sh | sh
    else
      warn "neither curl nor wget is available to fetch the uv installer"
      return 1
    fi
    for d in "$HOME/.local/bin" "$HOME/.cargo/bin"; do
      [ -x "$d/uv" ] && PATH="$d:$PATH"
    done
  fi
  command -v uv >/dev/null 2>&1 || { warn "uv installed but not found on PATH"; return 1; }
  uv python install "$INSTALL_PY_VERSION" || { warn "uv python install failed"; return 1; }
  found="$(uv python find "$INSTALL_PY_VERSION" 2>/dev/null || true)"
  [ -n "$found" ] && [ -x "$found" ] || { warn "uv did not report a usable interpreter"; return 1; }
  PY="$found"
}

ensure_python() {
  # 1. reuse an existing interpreter
  if find_interpreter; then
    note "reusing existing interpreter: $PY"
    return 0
  fi
  # 2. try native package manager (only where it needs no root, or we are root)
  if [ "$(id -u)" = "0" ] || [ "$PLATFORM" = "termux" ] || [ "$PLATFORM" = "mac" ]; then
    if native_install; then
      hash -r 2>/dev/null || true
      if find_interpreter; then
        note "Python installed via native package manager: $PY"
        return 0
      fi
    fi
  fi
  # 3. fall back to userspace uv (no sudo) — also the direct choice when native
  #    is unavailable or would need an interactive root prompt.
  if uv_install; then
    note "Python installed via userspace uv: $PY"
    return 0
  fi
  return 1
}

check_git() {
  if command -v git >/dev/null 2>&1; then
    GIT_STATE="present"
  else
    GIT_STATE="missing"
    warn "git is not installed. aigate will still run, but the git-based self-heal feature will be unavailable. Install git yourself if you want it."
  fi
}

report_status() {
  log ""
  log "platform:     $PLATFORM"
  log "interpreter:  ${PY:-none found}"
  log "git:          $GIT_STATE"
  log "run.py:       $(if [ -f "$RUN_PY" ]; then printf 'found'; else printf 'MISSING'; fi)"
  log ""
}

main() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --check-only) CHECK_ONLY=1; shift ;;
      -h|--help)    usage; exit 0 ;;
      *)            break ;;   # remaining args are forwarded to run.py
    esac
  done

  if [ ! -f "$RUN_PY" ]; then
    die "aigate's run.py was not found next to this script. Run bootstrap from inside the aigate folder."
  fi

  detect_platform
  check_git

  if [ "$CHECK_ONLY" = "1" ]; then
    # Detection only — no install, no launch.
    find_interpreter || true
    report_status
    note "check-only: nothing installed, aigate not started."
    exit 0
  fi

  if ! ensure_python; then
    die "a Python interpreter, a package manager, and the userspace 'uv' fallback all failed to provide Python 3.10 or newer on this platform ($PLATFORM)."
  fi

  report_status
  note "handing off to run.py (it installs the Python packages aigate needs)."
  log ""
  # Forward any remaining user args to run.py. exec replaces this shell.
  exec "$PY" "$RUN_PY" "$@"
}

main "$@"

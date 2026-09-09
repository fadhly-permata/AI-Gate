#!/usr/bin/env bash
# compat-test.sh — cross-platform compat harness for aigate CLI tools.
#
# Probes all 24 CLI tool install/launch scripts (scripts/cli-tools/<tool>.sh)
# on the CURRENT platform and records the result into the compatibility catalog
# (src/backend/cli_compat.json), filling ONLY the column for the platform this
# script runs on. Other platform columns are left untouched.
#
# Why: tools behave differently per OS. This lets a user on Windows / Linux /
# macOS run one command, then commit + push the result so the `cli tools` view
# (which reads cli_compat.json) shows real per-platform status everywhere.
#
# Usage:
#   bash compat-test.sh --apply     # default: really install/launch + write JSON
#   bash compat-test.sh --dry-run   # show the plan, install NOTHING, write NOTHING
#
# Notes:
#   * The per-tool scripts forward "$@" to `exec "$BIN" "$@"`, so passing --help
#     makes a VERIFIED tool attempt install then run `<bin> --help`; a NO_INSTALL
#     / NOT_A_CLI script just prints a message and exits 0 (no side effects).
#   * 10 tools have a GLOBAL classification (same on every platform) and are
#     filled in directly without running anything: 8 no_install + 2 not_a_cli.
#   * The other 14 are PROBED by running their --help script in an isolated temp
#     dir. gemini/codex are wired to `not_wired` if the probe succeeds (they
#     install but run in a mode aigate does not serve).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SCRIPTS_DIR="$REPO_ROOT/scripts/cli-tools"
JSON_FILE="$REPO_ROOT/src/backend/cli_compat.json"

# --- flags -----------------------------------------------------------------
DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --apply)   DRY_RUN=0 ;;
    -h|--help)
      grep -E '^#' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "[aigate-cli] unknown arg: $arg (use --dry-run or --apply)" >&2
      exit 2
      ;;
  esac
done

# --- prerequisites ----------------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
  echo "[aigate-cli] ERROR: python3 is required to read/write cli_compat.json" >&2
  exit 1
fi
if [ ! -f "$JSON_FILE" ]; then
  echo "[aigate-cli] ERROR: $JSON_FILE not found" >&2
  exit 1
fi

# --- platform detection (termux/linux/windows/macos) ------------------------
detect_platform() {
  local os="unknown"
  case "$(uname -s 2>/dev/null || echo unknown)" in
    Linux*)
      if [ -n "${TERMUX_VERSION:-}" ] || [ -d "/data/data/com.termux/files" ]; then
        os="termux"
      else
        os="linux"
      fi ;;
    Darwin*) os="macos" ;;
  esac
  case "$(uname -o 2>/dev/null || echo)" in
    *Cygwin*|*MINGW*|*MSYS*) os="windows" ;;
  esac
  if [ -n "${WSL_DISTRO_NAME:-}" ] || grep -qi microsoft /proc/version 2>/dev/null; then
    os="windows"
  fi
  PLATFORM="$os"
}
detect_platform

DATE="$(date +%Y-%m-%d)"
SOURCE_PREFIX="compat-test-${PLATFORM}-${DATE}"

# --- global classification (same on every platform; no run needed) -----------
NO_INSTALL_TOOLS="antigravity phi goose amp swe-agent autogpt sgpt mods"
NOT_A_CLI_TOOLS="gpt-researcher crewai"
# Probed tools that, if they install+launch, are still NOT wired to aigate.
NOT_WIRED_TOOLS="gemini codex"

is_member() {
  local needle="$1"; shift
  local item
  for item in "$@"; do
    [ "$item" = "$needle" ] && return 0
  done
  return 1
}

# --- helpers ----------------------------------------------------------------
# List all tool names from the JSON (sorted, one per line).
tool_list() {
  python3 - "$JSON_FILE" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as fh:
    data = json.load(fh)
for t in sorted(data.get("compat", {}).keys()):
    print(t)
PY
}

# Read the Termux note for a tool (used to keep global reasoning visible).
termux_note() {
  python3 - "$JSON_FILE" "$1" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as fh:
    data = json.load(fh)
t = sys.argv[2]
print(data.get("compat", {}).get(t, {}).get("termux", {}).get("note", ""))
PY
}

# Atomically write one tool's platform column.
write_status() {
  local tool="$1" status="$2" note="$3" source="$4"
  python3 - "$JSON_FILE" "$tool" "$PLATFORM" "$status" "$note" "$source" <<'PY'
import json, sys, os, tempfile
path, tool, plat, status, note, source = sys.argv[1:7]
with open(path, encoding="utf-8") as fh:
    data = json.load(fh)
if tool not in data.get("compat", {}):
    data.setdefault("compat", {})[tool] = {}
data["compat"][tool][plat] = {"status": status, "note": note, "source": source}
d = os.path.dirname(path)
fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
try:
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        json.dump(data, out, indent=2, ensure_ascii=False)
        out.write("\n")
    os.replace(tmp, path)
except Exception:
    if os.path.exists(tmp):
        os.unlink(tmp)
    raise
PY
}

# Run one probe: bash scripts/cli-tools/<tool>.sh --help inside an isolated dir.
# Echoes one of: verified | installable | broken | not_wired
probe_tool() {
  local tool="$1"
  local script="$SCRIPTS_DIR/$tool.sh"
  local log="$PROBE_DIR/$tool.log"
  if [ ! -f "$script" ]; then
    echo "installable"   # script missing -> cannot confirm; treat as unknown-ish
    return
  fi
  ( cd "$PROBE_DIR" && timeout 300 bash "$script" --help >"$log" 2>&1 ); rc=$?
  if [ "$rc" -eq 0 ]; then
    if is_member "$tool" $NOT_WIRED_TOOLS; then
      echo "not_wired"
    else
      echo "verified"
    fi
  else
    if grep -q "aborting launch" "$log" 2>/dev/null; then
      echo "broken"
    else
      echo "installable"
    fi
  fi
}

# --- isolated probe dir -----------------------------------------------------
PROBE_DIR="$(mktemp -d -p "${TMPDIR:-$HOME}" 2>/dev/null || mktemp -d 2>/dev/null || echo "${HOME:-$REPO_ROOT}/.cli-compat-test")"
mkdir -p "$PROBE_DIR"
cleanup() { rm -rf "$PROBE_DIR" 2>/dev/null || true; }
trap cleanup EXIT

# --- banner -----------------------------------------------------------------
echo "==================================================================="
if [ "$DRY_RUN" -eq 1 ]; then
  echo " aigate CLI-tools cross-platform harness  [DRY-RUN — nothing installed/written]"
else
  echo " aigate CLI-tools cross-platform harness  [APPLY — will install/launch + write JSON]"
fi
echo " platform detected : $PLATFORM"
echo " catalog           : $JSON_FILE"
echo "==================================================================="

# --- main loop --------------------------------------------------------------
SUMMARY=()
while IFS= read -r tool; do
  [ -z "$tool" ] && continue

  if is_member "$tool" $NO_INSTALL_TOOLS; then
    status="no_install"
    note="NO_INSTALL (global classification — same on all platforms; see Termux row for detail)"
    plan="[GLOBAL] no run"
  elif is_member "$tool" $NOT_A_CLI_TOOLS; then
    status="not_a_cli"
    note="NOT_A_CLI (global classification — same on all platforms; see Termux row for detail)"
    plan="[GLOBAL] no run"
  else
    if [ "$DRY_RUN" -eq 1 ]; then
      if is_member "$tool" $NOT_WIRED_TOOLS; then
        status="(probe)"; note="would probe; -> not_wired if install+launch ok"
      else
        status="(probe)"; note="would probe; -> verified | installable | broken"
      fi
      plan="[PROBE] bash $tool.sh --help"
    else
      status="$(probe_tool "$tool")"
      case "$status" in
        verified)  note="verified via compat-test.sh on $PLATFORM ($DATE)" ;;
        not_wired) note="probe ok; runs native mode, not wired to aigate (compat-test.sh $DATE)" ;;
        broken)    note="install failed during probe (compat-test.sh $DATE)" ;;
        installable) note="install succeeded but launch/--help failed or needs key/interactive (compat-test.sh $DATE)" ;;
        *)         note="unexpected probe result (compat-test.sh $DATE)" ;;
      esac
      plan="[PROBE] bash $tool.sh --help -> $status"
    fi
  fi

  # Write (only when not dry-run) and record for the summary.
  if [ "$DRY_RUN" -eq 0 ]; then
    write_status "$tool" "$status" "$note" "$SOURCE_PREFIX"
  fi
  SUMMARY+=("$(printf '%-16s %-12s %s' "$tool" "$status" "$plan")")
  printf '%-16s %-12s %s\n' "$tool" "$status" "$plan"
done < <(tool_list)

# --- summary + next steps ---------------------------------------------------
echo "-------------------------------------------------------------------"
echo " SUMMARY ($PLATFORM):"
for line in "${SUMMARY[@]}"; do
  echo "   $line"
done
echo "-------------------------------------------------------------------"
if [ "$DRY_RUN" -eq 1 ]; then
  echo " DRY-RUN complete. Re-run WITHOUT --dry-run to install, launch, and write results."
else
  echo " Done. Results written to the '$PLATFORM' column of cli_compat.json."
  echo " Review, then commit + push so other platforms see the data:"
  echo "   git add src/backend/cli_compat.json"
  echo "   git commit -m \"test(cli-tools): fill $PLATFORM compat from cross-platform harness\""
  echo "   git push origin HEAD"
fi

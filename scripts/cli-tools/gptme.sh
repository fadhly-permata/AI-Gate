#!/usr/bin/env bash
# gptme.sh — install + launch gptme (Grup C / C5) for aigate.
#
# Source of truth:
#   aigate preset:  src/backend/cli_presets.py
#                     - line 104 : install _pip("gptme") -> `pip install gptme`, bin `gptme`
#                     - line 223 : "gptme": LaunchSupport(LAUNCH_VERIFIED)
#   launch builder: src/backend/cli_tools_router.py _gptme_builder (line 595)
#
# =============================== FACT-BASED (R47/R48) ===============================
# Every claim below is cross-checked across >=2 independent sources.
#
# [S1] aigate code (authoritative for the launch form):
#   - src/backend/cli_presets.py:104 -> install = `pip install gptme`, binary = `gptme`.
#   - src/backend/cli_presets.py:223 -> gptme = LAUNCH_VERIFIED (NOT NO_INSTALL/UNSUPPORTED).
#   - src/backend/cli_tools_router.py:595-612 (_gptme_builder) -> the documented
#     OpenAI-compatible launch form is:
#       OPENAI_BASE_URL=<gateway base> gptme [-m local/<raw_model>]
#     i.e. the `local/` provider prefix + the gateway base url as OPENAI_BASE_URL.
#     The docstring notes the `local/` prefix keeps gptme on the chat-completions
#     path (the gateway does NOT serve /v1/responses; bare `openai/*` GPT-5-class
#     models are routed to /v1/responses by gptme and would fail).
#   - src/backend/cli_tools_router.py:982 -> "gptme": _gptme_builder (builder map entry).
#   - src/backend/cli_tools_router.py:1079-1084 (resolve) -> every launched tool gets
#     env OPENAI_API_BASE=<base> and OPENAI_API_KEY=<key> injected; gptme reads
#     OPENAI_API_KEY for its key (the builder relies on that export and only
#     PREFIXES OPENAI_BASE_URL inline, quoting ctx.base).
#   - gateway base = ctx.base = gateway_base_url Setting, default
#     http://localhost:8080/v1 (cli_tools_router.py:50 DEFAULT_GATEWAY_BASE),
#     and aigate serves OpenAI-compatible /v1/chat/completions + /v1/models there.
#
# [S2] PyPI registry (https://pypi.org/pypi/gptme/json, fetched 2026-09-09):
#   - name=gptme, version=0.33.0, summary="Powerful AI agent for coding and general
#     tasks. Terminal-first ...". This IS ErikBjare/gptme (homepage https://gptme.org,
#     repo https://github.com/gptme/gptme) — NOT an unrelated squatter.
#   - requires_python = ">=3.10,<3.15"; wheel = py3-none-any (NUM_WHEELS=2,
#     python_version=py3) — pure-python, platform-independent.
#   - upstream GitHub pyproject.toml [project.scripts]: `gptme = "gptme.cli.main:main"`
#     => `pip install gptme` installs the binary `gptme` (matches [S1] binary).
#
# [S3] Official gptme docs + GitHub (gptme.org/docs/providers.html "Local", GitHub
#     README, read 2026-09-09):
#   - docs "Local" section EXACTLY:
#       ollama pull llama3.2:1b
#       ollama serve
#       OPENAI_BASE_URL="http://127.0.0.1:11434/v1" gptme 'hello' -m local/llama3.2:1b
#     => confirms [S1]'s launch form: env OPENAI_BASE_URL=<openai-compatible base/v1>
#        + `-m local/<model>` is the documented route for ANY OpenAI-compatible server.
#   - docs "Selecting a provider and model": `-m local/<model>` (e.g. local/llama3.2:1b);
#     `gptme '/models'` lists known models. `-m` is the model flag.
#   - GitHub README install: `pip install gptme` (also pipx/uv). Prereqs Python 3.10+.
#     Credentials: OPENAI_API_KEY is the OpenAI provider key; for local/OpenAI-compatible
#     servers use OPENAI_BASE_URL (FAQ "How do I use local models?":
#     `export OPENAI_BASE_URL=http://localhost:8080/v1; gptme -m local/<model-name>`).
#   => CONFIRMS [S1] EXACTLY: gptme talks to an OpenAI-compatible endpoint via
#      OPENAI_BASE_URL + OPENAI_API_KEY, with the `local/` provider prefix.
#
# CROSS-CHECK RESULT: gptme in aigate = VERIFIED (LAUNCH_VERIFIED), NOT NO_INSTALL
#   and NOT UNSUPPORTED. It is OpenAI-compatible (the gateway's /v1/chat/completions),
#   wired via `OPENAI_BASE_URL=<AIGATE_BASE> gptme [-m local/<AIGATE_MODEL>]`. The key
#   is OPENAI_API_KEY (gptme reads it; router injects it). NO anthropic-only /
#   responses-only / not-a-cli blocker. The launch form is the upstream-documented
#   OpenAI-compatible `local/` route, not a guessed flag.
#
# =============================== INSTALL (verified) ===============================
# aigate preset [S1] = `pip install gptme`. We run it as `python3 -m pip install gptme`
# (portable across shells, same convention as llm.sh / openhands.sh). Binary `gptme` [S2].
# NOTE: gptme is NOT in aigate's TERMUX_INSTALL map and is NOT a Termux pkg, so the
#   portable pip route is the only install path; see the known-broken caveat below.
#
# =============================== KNOWN-BROKEN CAVEAT (with evidence) ===============================
# * On THIS device (Termux 0.118.x, aarch64, Python 3.14.6) `pip install gptme`
#   FAILS at the dependency-build step (verified via `python3 -m pip install --dry-run gptme`,
#   run here 2026-09-09). The failure is the transitive Rust dependency `jiter`
#   (pulled in via gptme's `openai` SDK dep, openai = "^2.48"), exactly like llm.sh:
#       Target triple not supported by rustup: aarch64-unknown-linux-android
#       Rust not found, installing into a temporary directory
#       ERROR: Failed to build 'jiter' when installing build dependencies for jiter
#   Evidence from PyPI (https://pypi.org/pypi/jiter/json): jiter 0.16.0 publishes 105
#   wheels — manylinux_aarch64, musllinux_aarch64, macosx/win/linux x86_64, armv7l,
#   ppc64le, s390x, riscv64 — but ZERO `android` wheels. pip on Termux resolves the
#   SOABI `cpython-314-aarch64-linux-android`, finds no matching wheel, falls back to
#   the sdist (tar.gz) and tries to compile Rust; `rust`/`cargo`/`rustup` are ABSENT
#   (command -v returned nothing) and rustup does not support the android target, so
#   the build fails. This is a platform/wheel-availability issue (Android SOABI), NOT a
#   problem with the gptme package itself.
# * Python VERSION is NOT the blocker: gptme requires_python ">=3.10,<3.15" [S2], and
#   the device's Python 3.14.6 satisfies that (3.14.6 < 3.15.0). Unlike openhands
#   (==3.12.*), gptme's version range is fine here.
# * Workaround: install a Rust toolchain (pkg install rust, or rustup) so the `jiter`
#   wheel can compile from sdist, OR run gptme from a manylinux/other environment
#   (e.g. a venv on a Linux host, or a Docker/CI image) where prebuilt wheels exist.
#   The script attempts the pip install, and if it fails, prints this hint and exits 1.
#
# Configure via env (defaults from aigate gateway config via _common.sh):
#   AIGATE_MODEL   optional; forwarded to gptme as -m local/<AIGATE_MODEL> (a gateway-
#                  known model id). Without it, gptme opens its interactive TUI and you
#                  pick the model there. Must match a model the gateway serves.
#   AIGATE_DB_PATH optional override of the aigate SQLite DB path (see _common.sh).

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

detect_os
detect_pm
load_gateway_config   # aigate gateway base (AIGATE_BASE) + internal key (AIGATE_KEY)

BIN="gptme"
# Faithful to the aigate preset (`pip install gptme`); `python3 -m pip` is portable.
INSTALL_CMD=(python3 -m pip install gptme)

log_msg "os=$AIGATE_OS pm=$AIGATE_PM gateway_base=$AIGATE_BASE"

# --- Idempotent install (never reinstalls when already present) -------------------
if ! ensure_installed "$BIN" "${INSTALL_CMD[@]}"; then
  log_msg "could not install $BIN on this platform; aborting launch."
  if [ "$AIGATE_OS" = "termux" ]; then
    log_msg "HINT (Termux aarch64): pip install gptme fails because the transitive"
    log_msg "      Rust dependency 'jiter' (via the openai SDK) has no prebuilt wheel"
    log_msg "      for cpython-314-aarch64-linux-android; the sdist build needs Rust."
    log_msg "      Install a Rust toolchain (pkg install rust / rustup) so the wheel can"
    log_msg "      compile, OR run gptme from a manylinux environment. (Python version"
    log_msg "      3.14.6 is FINE for gptme, which allows >=3.10,<3.15.)"
  fi
  exit 1
fi

# --- gptme -> aigate wiring (OpenAI Chat Completions via `local/` provider) -------
# Best-effort reachability check (tolerate missing curl). aigate exposes a
# non-auth GET /v1/models; only a hard connect/timeout failure warns.
if have_cmd curl; then
  if ! curl -fsS -o /dev/null --max-time 3 "${AIGATE_BASE}/models" 2>/dev/null; then
    rc=$?
    if [ "$rc" -eq 7 ] || [ "$rc" -eq 28 ]; then
      log_msg "WARN: aigate not reachable at $AIGATE_BASE (check gateway_base_url / is aigate running?);"
      log_msg "      gptme will fail to connect. Start aigate first if it is not running."
    fi
  fi
fi

# Env injection every tool gets (cli_tools_router.py:1079-1084): the router exports
# OPENAI_API_BASE + OPENAI_API_KEY for every launched tool. We mirror that, and ALSO
# set OPENAI_BASE_URL because gptme's OpenAI-compatible `local/` provider reads
# OPENAI_BASE_URL (NOT OPENAI_API_BASE) — that is the exact env var the aigate builder
# prefixes inline (cli_tools_router.py:595-612) and the gptme docs use for local
# servers (gptme.org/docs/providers.html "Local"). OPENAI_API_KEY is what gptme reads
# for its key (router injects it as plaintext per ADR-007).
export OPENAI_API_BASE="$AIGATE_BASE"
export OPENAI_API_KEY="$AIGATE_KEY"
export OPENAI_BASE_URL="$AIGATE_BASE"

AIGATE_MODEL="${AIGATE_MODEL:-}"

if [ -n "$AIGATE_MODEL" ]; then
  log_msg "launching $BIN via aigate (OpenAI-compatible endpoint ${AIGATE_BASE}/chat/completions, model=local/${AIGATE_MODEL})"
  # Mirror _gptme_builder: `-m local/<raw_model>` keeps gptme on the chat-completions
  # path (avoids /v1/responses). Trailing "$@" lets an operator append extra flags;
  # with none, gptme opens its interactive chat.
  exec "$BIN" -m "local/${AIGATE_MODEL}" "$@"
else
  log_msg "launching $BIN via aigate (OpenAI-compatible endpoint ${AIGATE_BASE}/chat/completions; interactive — pick model in the TUI)"
  # No model selected -> bare `gptme` opens the interactive TUI (matches the builder,
  # which passes no -m and no prompt). "$@" passes through any extra flags.
  exec "$BIN" "$@"
fi

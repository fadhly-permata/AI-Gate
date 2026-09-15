#
# bootstrap.ps1 — cold-start bootstrap for aigate (Windows PowerShell 5.1 + PowerShell 7).
#
# One command that "just works" on a clean Windows machine that has nothing —
# not even Python. It ensures a Python interpreter >= 3.10 exists, warns if
# `git` is missing, then hands off to run.py (which already installs the pip
# dependencies). It does NOT touch run.py and does NOT duplicate its pip logic.
#
# Usage:
#   pwsh scripts/bootstrap.ps1                # ensure Python, then start aigate
#   powershell -File scripts\bootstrap.ps1    # same, via Windows PowerShell 5.1
#   pwsh scripts/bootstrap.ps1 -CheckOnly     # detect only; no install, no launch
#   pwsh scripts/bootstrap.ps1 <args...>       # extra args forwarded to run.py
#
# Behaviour guarantees:
#   * Non-interactive & idempotent: a second run on a ready machine just launches.
#   * No silent elevation and no password prompt from this script. `winget`
#     installs Python per-user (no admin); if the native path is unavailable we
#     fall back to the userspace `uv` installer, which writes under %USERPROFILE%
#     and never requests elevation.

$ErrorActionPreference = 'Stop'

[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [Parameter(ValueFromRemainingArguments = $true)]
    $RestArgs = @()
)

# --- Where is the repo root, so this works from any CWD? --------------------
# Script lives in <repo>\scripts\, so root is one level up. No hardcoded paths.
$RepoRoot = Split-Path -Parent $PSScriptRoot
$RunPy    = Join-Path $RepoRoot 'run.py'

# Minimum interpreter version. Mirrors pyproject.toml [project]
# requires-python = ">=3.10" (line 11) — that entry is the source of truth;
# keep this constant in sync if it ever changes (same pattern as run.py:18-21).
$MinPython = [version]'3.10'
# Version the bootstrap asks winget / uv to install (per PM handover).
$InstallVersion = '3.12'
$WingetId       = 'Python.Python.3.12'

# Interpreter selected for the hand-off: a command plus the launcher args that
# precede the script path (e.g. py -> @('-3'); a full python.exe path -> @()).
$script:PyCmd  = $null
$script:PyArgs = @()
$script:GitState = 'unknown'

# --- output helpers (stderr, so stdout stays clean for run.py) --------------
function Out-Info { param([string]$Message) [Console]::Error.WriteLine($Message) }
function Out-Note { param([string]$Message) [Console]::Error.WriteLine("[aigate-bootstrap] $Message") }
function Out-Warn { param([string]$Message) [Console]::Error.WriteLine("[aigate-bootstrap] WARNING: $Message") }

function Stop-Bootstrap {
    param([string]$Reason)
    Out-Info ''
    Out-Info 'aigate could not start automatically.'
    Out-Info $Reason
    Out-Info ''
    Out-Info 'Once Python 3.10 or newer is on this machine, run this file again.'
    exit 1
}

# --- does an interpreter command exist AND meet the minimum version? --------
function Test-PythonCmd {
    param([string]$Command, [string[]]$CmdArgs = @())
    if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) { return $false }
    $probe = "import sys; sys.exit(0 if sys.version_info[:2] >= ($($MinPython.Major), $($MinPython.Minor)) else 1)"
    $exit = 1
    try {
        $a = $CmdArgs
        & $Command @a -c $probe 2>$null | Out-Null
        $exit = $LASTEXITCODE
    } catch {
        return $false
    }
    return ($exit -eq 0)
}

# --- find an already-present usable interpreter (skip install if found) -----
function Find-Python {
    $script:PyCmd  = $null
    $script:PyArgs = @()
    $candidates = @(
        @{ Cmd = 'py';      Args = @('-3') },
        @{ Cmd = 'python3'; Args = @() },
        @{ Cmd = 'python';  Args = @() }
    )
    foreach ($cand in $candidates) {
        if (Test-PythonCmd -Command $cand.Cmd -CmdArgs $cand.Args) {
            $script:PyCmd  = $cand.Cmd
            $script:PyArgs = $cand.Args
            return $true
        }
    }
    return $false
}

# --- refresh this session's PATH after an install changed the registry ------
function Update-SessionPath {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user    = [Environment]::GetEnvironmentVariable('Path', 'User')
    $parts   = @($machine, $user, $env:Path) | Where-Object { $_ }
    $env:Path = ($parts -join ';')
}

# --- native install via winget (per-user, non-interactive) ------------------
function Install-NativePython {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Out-Note 'winget not found; will try the userspace uv fallback.'
        return $false
    }
    Out-Note "installing Python via winget (per-user, non-interactive): $WingetId"
    $ok = $true
    try {
        & winget install -e --id $WingetId --silent `
            --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) { $ok = $false }
    } catch {
        $ok = $false
    }
    if (-not $ok) { return $false }
    Update-SessionPath
    return $true
}

# --- userspace uv fallback (the no-elevation path) --------------------------
function Install-UvPython {
    Out-Note 'native Python install unavailable — falling back to userspace uv (no admin)'
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        try {
            # Documented standalone installer; writes under %USERPROFILE%\.local\bin.
            & powershell -NoProfile -ExecutionPolicy ByPass -Command 'irm https://astral.sh/uv/install.ps1 | iex'
        } catch {
            return $false
        }
        Update-SessionPath
        if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
            $cand = Join-Path $env:USERPROFILE '.local\bin\uv.exe'
            if (-not (Test-Path $cand)) {
                Out-Warn 'uv installed but could not be located on PATH.'
                return $false
            }
            $env:Path = (Split-Path -Parent $cand) + ';' + $env:Path
        }
    }
    $ok = $true
    try {
        uv python install $InstallVersion
        if ($LASTEXITCODE -ne 0) { $ok = $false }
    } catch {
        $ok = $false
    }
    if (-not $ok) { Out-Warn 'uv python install failed'; return $false }
    $found = $null
    try { $found = (uv python find $InstallVersion 2>$null | Select-Object -First 1) } catch { $found = $null }
    if (-not $found -or -not (Test-Path -LiteralPath $found)) {
        Out-Warn 'uv did not report a usable interpreter.'
        return $false
    }
    $script:PyCmd  = [string]$found
    $script:PyArgs = @()
    return $true
}

function Get-PythonDisplay {
    if (-not $script:PyCmd) { return 'none found' }
    $cmd = $script:PyCmd
    $a   = $script:PyArgs
    $v = ''
    try {
        $v = (& $cmd @a -c "import sys;print('.'.join(str(x) for x in sys.version_info[:3]))").Trim()
    } catch { $v = '?' }
    $src = $cmd
    $resolved = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($resolved -and $resolved.Source) { $src = $resolved.Source }
    return "$src (Python $v)"
}

function Ensure-Python {
    if (Find-Python) {
        Out-Note ('reusing existing interpreter: ' + (Get-PythonDisplay))
        return $true
    }
    if ((Install-NativePython) -and (Find-Python)) {
        Out-Note ('Python installed via winget: ' + (Get-PythonDisplay))
        return $true
    }
    if ((Install-UvPython) -and (Test-PythonCmd -Command $script:PyCmd)) {
        Out-Note ('Python installed via userspace uv: ' + (Get-PythonDisplay))
        return $true
    }
    return $false
}

function Check-Git {
    if (Get-Command git -ErrorAction SilentlyContinue) {
        $script:GitState = 'present'
    } else {
        $script:GitState = 'missing'
        Out-Warn 'git is not installed. aigate will still run, but the git-based self-heal feature will be unavailable. Install git yourself if you want it.'
    }
}

function Report-Status {
    Out-Info ''
    Out-Info 'platform:     windows'
    Out-Info ('interpreter:  ' + (Get-PythonDisplay))
    Out-Info ('git:          ' + $script:GitState)
    $run = 'MISSING'; if (Test-Path -LiteralPath $RunPy) { $run = 'found' }
    Out-Info ('run.py:       ' + $run)
    Out-Info ''
}

# --- main -------------------------------------------------------------------
if (-not (Test-Path -LiteralPath $RunPy)) {
    Stop-Bootstrap "aigate's run.py was not found next to this script. Run bootstrap from inside the aigate folder."
}

Check-Git

if ($CheckOnly) {
    # Detection only — no install, no launch.
    $null = Find-Python
    Report-Status
    Out-Note 'check-only: nothing installed, aigate not started.'
    exit 0
}

if (-not (Ensure-Python)) {
    Stop-Bootstrap 'a Python interpreter, winget, and the userspace uv fallback all failed to provide Python 3.10 or newer on this machine.'
}

Report-Status
Out-Note 'handing off to run.py (it installs the Python packages aigate needs).'
Out-Info ''

# Forward any remaining user args to run.py and propagate its exit code.
$cmd = $script:PyCmd
$a   = $script:PyArgs
& $cmd @a $RunPy @RestArgs
exit $LASTEXITCODE

# start_stack.ps1 — QorTroller Full Stack Launcher
# ===================================================
# Starts all four processes in separate PowerShell windows:
#   1. Bridge       (port 8000) — protocol engine, stewards, GIC
#   2. Daemon       (port 8080) — AI brain, 32 tools
#   3. Watcher      (5-min cadence) — autonomous monitoring loop
#   4. CLI Agent    — Rich terminal chat interface
#
# Usage:
#   .\start_stack.ps1            # start all four
#   .\start_stack.ps1 -NoCLI    # start bridge+daemon+watcher only
#   .\start_stack.ps1 -WatchInterval 60  # watcher at 60-second cadence
#
# Requirements:
#   pip install uvicorn rich requests
#   QUICKSILVER_API_KEY in bridge/.env
#   OPERATOR_API_KEY    in bridge/.env

param(
    [switch]$NoCLI,
    [int]$WatchInterval = 300
)

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = "python"

function Start-Window {
    param(
        [string]$Title,
        [string]$Command,
        [string]$Color = "DarkBlue"
    )
    Start-Process powershell -ArgumentList "-NoExit", "-Command",
        "& { `$Host.UI.RawUI.WindowTitle = '$Title'; $Command }" `
        -WorkingDirectory $Root
}

Write-Host ""
Write-Host "  QorTroller Full Stack" -ForegroundColor Green
Write-Host "  =====================" -ForegroundColor Green
Write-Host ""

# ── 1. Bridge (port 8000) ─────────────────────────────────────────────────
Write-Host "  [1/4] Starting Bridge on port 8000..." -ForegroundColor Cyan
Start-Window -Title "QorTroller Bridge :8000" `
    -Command "$Python -m bridge.vapi_bridge.main"
Start-Sleep -Seconds 2

# ── 2. Daemon (port 8080) ─────────────────────────────────────────────────
Write-Host "  [2/4] Starting Daemon on port 8080..." -ForegroundColor Cyan
Start-Window -Title "QorTroller Daemon :8080" `
    -Command "`$env:DAEMON_PORT='8080'; $Python qortroller_daemon.py"
Start-Sleep -Seconds 2

# ── 3. Watcher ────────────────────────────────────────────────────────────
Write-Host "  [3/4] Starting Watcher (${WatchInterval}s cadence)..." -ForegroundColor Cyan
Start-Window -Title "QorTroller Watcher" `
    -Command "$Python protocol_watcher.py --interval $WatchInterval"
Start-Sleep -Seconds 1

# ── 4. CLI Agent ──────────────────────────────────────────────────────────
if (-not $NoCLI) {
    Write-Host "  [4/4] Starting CLI Agent..." -ForegroundColor Cyan
    # Give bridge + daemon time to fully start
    Write-Host "        (waiting 12s for bridge startup...)" -ForegroundColor DarkGray
    Start-Sleep -Seconds 12
    Start-Window -Title "QorTroller CLI" `
        -Command "$Python qortroller_cli_agent.py"
}

Write-Host ""
Write-Host "  Stack launched." -ForegroundColor Green
Write-Host ""
Write-Host "  Bridge   : http://localhost:8000" -ForegroundColor White
Write-Host "  Daemon   : http://localhost:8080" -ForegroundColor White
Write-Host "  Watcher  : polling every ${WatchInterval}s" -ForegroundColor White
if (-not $NoCLI) {
    Write-Host "  CLI      : open in new window" -ForegroundColor White
}
Write-Host ""
Write-Host "  Check watcher status anytime:" -ForegroundColor DarkGray
Write-Host "    python protocol_watcher.py --status" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Stop all: close each PowerShell window or Ctrl+C in each" -ForegroundColor DarkGray
Write-Host ""

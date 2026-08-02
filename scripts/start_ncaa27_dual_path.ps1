# Default dual-path grind start for THIS operator rig (locked 2026-08-02).
# See docs/runbook/NEXT_SESSION_FIRST.md
#
# Device map:
#   0 = 720p HD Camera (house webcam) — NEVER
#   1 = capture card path for bridge
#   2 = OBS Virtual Camera for streamer (dshow)
#
# Preflight: Edge USB-C+BT, PS5 game live, OBS Virtual Camera started.

param(
    [string]$Label = "ncaa27",
    [int]$UvcIndex = 1,
    [int]$StreamerDevice = 2,
    [double]$StreamerFps = 15,
    [switch]$NoStreamer
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo

Write-Host "[start] repo=$Repo"
Write-Host "[start] FIRST DOC: docs/runbook/NEXT_SESSION_FIRST.md"
Write-Host "[start] map: bridge uvc=$UvcIndex | streamer device=$StreamerDevice (OBS VCam)"
Write-Host "[start] EYE-CHECK required after start — open logs/eye_check_streamer_*.png"

$argsList = @(
    "scripts/retina_capture_daemon.py", "start",
    "--label", $Label,
    "--uvc-index", "$UvcIndex"
)

if (-not $NoStreamer) {
    $argsList += @(
        "--streamer",
        "--streamer-device", "$StreamerDevice",
        "--streamer-fps", "$StreamerFps"
        # backend/device-name/source-kind defaults are set inside the daemon
    )
}

Write-Host "[start] python $($argsList -join ' ')"
& python @argsList
exit $LASTEXITCODE

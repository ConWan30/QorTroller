# VAPI Calibration Agent — One-time PowerShell Setup
# ====================================================
# Run once from the repo root:
#   .\scripts\CALIBRATE_SETUP.ps1
#
# After setup, just type:
#   calibrate              <- Start agentic monitor while playing
#   calibrate status       <- One-shot scorecard
#   calibrate test         <- Run hardware calibration tests
#   calibrate players      <- Per-player breakdown

$RepoRoot = Split-Path -Parent $PSScriptRoot
$AgentScript = Join-Path $RepoRoot "scripts\calibration_agent.py"

# Verify the agent file exists
if (-not (Test-Path $AgentScript)) {
    Write-Host "[ERROR] Agent not found: $AgentScript" -ForegroundColor Red
    exit 1
}

# Build the function block to add to profile
$FunctionBlock = @"

# ── VAPI Calibration Intelligence Agent (Phase 148) ──────────────────────
# Keyword: calibrate
# Source : $AgentScript
function calibrate {
    python "$AgentScript" @args
}
# ─────────────────────────────────────────────────────────────────────────
"@

# Create profile if it doesn't exist
if (-not (Test-Path $PROFILE)) {
    New-Item -ItemType File -Path $PROFILE -Force | Out-Null
    Write-Host "[INFO] Created PowerShell profile at $PROFILE" -ForegroundColor Yellow
}

# Check if already configured
$existingContent = Get-Content $PROFILE -Raw -ErrorAction SilentlyContinue
if ($existingContent -and $existingContent.Contains("calibration_agent.py")) {
    Write-Host "[OK] 'calibrate' command already configured in profile." -ForegroundColor Green
    Write-Host "     Profile: $PROFILE" -ForegroundColor Gray
} else {
    Add-Content -Path $PROFILE -Value $FunctionBlock
    Write-Host "[OK] 'calibrate' command added to PowerShell profile." -ForegroundColor Green
    Write-Host "     Profile: $PROFILE" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Reload your profile now:" -ForegroundColor Cyan
Write-Host "  . `$PROFILE" -ForegroundColor White
Write-Host ""
Write-Host "Then use:" -ForegroundColor Cyan
Write-Host "  calibrate              # Start agentic monitor (run while playing NCAA CFB 26)" -ForegroundColor White
Write-Host "  calibrate status       # One-shot scorecard" -ForegroundColor White
Write-Host "  calibrate test         # Run hardware calibration pytest suite" -ForegroundColor White
Write-Host "  calibrate players      # Per-player touch_variance breakdown" -ForegroundColor White
Write-Host ""
Write-Host "Environment overrides (optional):" -ForegroundColor Cyan
Write-Host "  `$env:POLL_S = '10'                              # Poll every 10s instead of 30s" -ForegroundColor Gray
Write-Host "  `$env:SEPARATION_RATIO_CURRENT = '1.1'          # After running interperson_separation_analyzer.py" -ForegroundColor Gray
Write-Host "  `$env:OPERATOR_API_KEY = 'your-key'             # Enables live bridge tournament-readiness fetch" -ForegroundColor Gray

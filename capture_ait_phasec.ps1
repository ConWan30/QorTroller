# Phase C AIT capture — enrollment / verification holdout split
#
# C-2.1 protocol: https://docs.qortroller/phase-c-biometric-measurement-protocol-2026-07-05.md
#
# This script writes to a SEPARATE directory from the existing AIT corpus
# (sessions/human/terminal_cal_P*/) so that the Phase C enrollment/verification
# sessions can be analyzed independently under the holdout methodology.
#
# Session-order discipline (MANDATORY):
#   - Run ALL enrollment sessions (Phase=enrollment) for all players FIRST.
#   - Only start verification sessions (Phase=verification) after enrollment is COMPLETE.
#   - Do NOT interleave enrollment and verification sessions.
#
# Usage:
#   .\capture_ait_phasec.ps1 -Player P1 -Phase enrollment
#   .\capture_ait_phasec.ps1 -Player P2 -Phase enrollment
#   .\capture_ait_phasec.ps1 -Player P1 -Phase verification   # only after all enrollment done
#
# Per-player targets: 10 enrollment + 10 verification = 20 sessions each, 60 total.
#
# CAPTURE ENVIRONMENT (verify before starting):
#   - DualShock Edge: USB-C DATA cable to laptop (not power-only)
#   - PS5 BT connection: OK to be active (PCC ignores BT pairing state)
#   - Poll rate: must read ~1000 Hz in GET /bridge/capture-health before starting
#   - Bridge: NOT required to be running for this capture script
#     (capture_session.py reads HID directly)
#
# TARGET FORCE: hold L2 so the live readout shows 115-135.
# The python process prints your current L2 level every 2s during capture.
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("P1","P2","P3")]
    [string]$Player,

    [Parameter(Mandatory=$true)]
    [ValidateSet("enrollment","verification")]
    [string]$Phase,

    [int]$Duration = 30
)

# Guard: warn if starting verification before enrollment looks complete
$enrollDir = "sessions/human/phase_c_ait_enroll"
if ($Phase -eq "verification") {
    $p1e = (Get-ChildItem "$enrollDir/enroll_P1_*.json" -ErrorAction SilentlyContinue | Measure-Object).Count
    $p2e = (Get-ChildItem "$enrollDir/enroll_P2_*.json" -ErrorAction SilentlyContinue | Measure-Object).Count
    $p3e = (Get-ChildItem "$enrollDir/enroll_P3_*.json" -ErrorAction SilentlyContinue | Measure-Object).Count
    if ($p1e -lt 10 -or $p2e -lt 10 -or $p3e -lt 10) {
        Write-Host ""
        Write-Host "WARNING: Not all players have 10 enrollment sessions yet." -ForegroundColor Red
        Write-Host "  P1: $p1e/10  P2: $p2e/10  P3: $p3e/10" -ForegroundColor Yellow
        Write-Host "  Per C-2.1 protocol, complete ALL enrollment sessions before starting verification." -ForegroundColor Yellow
        Write-Host "  Continue anyway? (y/N)" -ForegroundColor White
        $ans = Read-Host
        if ($ans -ne "y" -and $ans -ne "Y") { exit 1 }
    }
}

# Output directory and filename
$baseDir = if ($Phase -eq "enrollment") { "sessions/human/phase_c_ait_enroll" } else { "sessions/human/phase_c_ait_verify" }
if (-not (Test-Path $baseDir)) { New-Item -ItemType Directory -Path $baseDir | Out-Null }

$prefix = if ($Phase -eq "enrollment") { "enroll" } else { "verify" }
$existing = Get-ChildItem "$baseDir/${prefix}_${Player}_*.json" -ErrorAction SilentlyContinue
$next = ($existing | Measure-Object).Count + 1
$out = "$baseDir/${prefix}_${Player}_{0:D3}.json" -f $next

# Count totals for progress display
$doneThisPhase = ($existing | Measure-Object).Count
$remaining = 10 - $doneThisPhase

Write-Host ""
Write-Host "Phase C AIT Capture" -ForegroundColor Cyan
Write-Host "  Player   : $Player"
Write-Host "  Phase    : $Phase  (session $($doneThisPhase+1)/10)"
Write-Host "  Duration : ${Duration}s"
Write-Host "  Output   : $out"
if ($remaining -gt 1) {
    Write-Host "  Remaining: $remaining sessions after this one for this player/phase" -ForegroundColor DarkGray
} elseif ($remaining -eq 1) {
    Write-Host "  Remaining: this is the LAST session for $Player/$Phase" -ForegroundColor Green
}
Write-Host ""
Write-Host "TARGET FORCE: L2 analog must read 115-135 during the hold." -ForegroundColor Cyan
Write-Host ""
Write-Host "  - Press L2 GENTLY -- just past the first click of resistance." -ForegroundColor White
Write-Host "  - The live L2 readout will print every 2s during capture." -ForegroundColor White
Write-Host "  - If the number is below 115: press a tiny bit harder." -ForegroundColor Yellow
Write-Host "  - If the number is above 135: ease off slightly." -ForegroundColor Yellow
Write-Host "  - Find the zone and FREEZE there for the full ${Duration}s." -ForegroundColor White
Write-Host ""
Write-Host "Starting in 3..." -ForegroundColor Yellow
Start-Sleep 1; Write-Host "2..." -ForegroundColor Yellow
Start-Sleep 1; Write-Host "1..." -ForegroundColor Yellow
Start-Sleep 1; Write-Host "GO -- hold L2 at 115-135!" -ForegroundColor Green

python scripts/capture_session.py --duration $Duration --notes "phase_c $Phase $Player AIT L2_target_125" --output $out --live-l2

Write-Host ""
Write-Host "Done. Session saved: $out" -ForegroundColor Green

# Quick quality check
python -c "
import json, sys
try:
    import numpy as np
    with open('$($out.Replace('\','\\'))') as f: d = json.load(f)
    vals = [r['features'].get('l2_trigger', r['features'].get('trigger_l2', 0)) for r in d.get('reports', [])]
    import numpy as np
    vals = np.array(vals, dtype=float)
    hold = vals[vals > 30]
    if len(hold) == 0:
        print('  Quality: NO L2 DATA -- check controller connection')
        sys.exit(0)
    med = np.median(hold)
    std = hold.std()
    ok = 'VALID' if 100 <= med <= 150 and std < 20 else 'CHECK FORCE LEVEL'
    print(f'  Quality: median={med:.0f}  std={std:.1f}  --> {ok}')
    if med < 100: print('  Force too LIGHT -- press a little harder next time')
    if med > 150: print('  Force too HEAVY -- press a little less next time')
except Exception as e:
    print(f'  Quality check skipped: {e}')
" 2>$null

Write-Host ""

# Show overall enrollment progress
Write-Host "--- Phase C progress ---" -ForegroundColor DarkGray
foreach ($p in @("P1","P2","P3")) {
    $ne = (Get-ChildItem "sessions/human/phase_c_ait_enroll/enroll_${p}_*.json" -ErrorAction SilentlyContinue | Measure-Object).Count
    $nv = (Get-ChildItem "sessions/human/phase_c_ait_verify/verify_${p}_*.json" -ErrorAction SilentlyContinue | Measure-Object).Count
    $mark_e = if ($ne -ge 10) { "[DONE]" } else { "[$ne/10]" }
    $mark_v = if ($nv -ge 10) { "[DONE]" } else { "[$nv/10]" }
    Write-Host ("  {0}  enroll {1}  verify {2}" -f $p, $mark_e, $mark_v) -ForegroundColor DarkGray
}
Write-Host ""
Write-Host "Next: .\capture_ait_phasec.ps1 -Player $Player -Phase $Phase"

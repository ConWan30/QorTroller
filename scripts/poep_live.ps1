# POEP-LIVE-1 — live NONCE-SCHEDULED challenge capture wrapper (avoids long-line paste-wrap).
# The challenge fires at a RANDOM, nonce-derived moment you cannot anticipate (no ENTER cue) and binds
# the response to a fresh nonce. Hold the controller relaxed with a finger RESTING on R2; react to the
# surprise buzz. poep_enabled STAYS FALSE (candidate). Stop the bridge first.
#
# Usage:  .\scripts\poep_live.ps1 [count] [force] [mode] [-Sharp]
#   .\scripts\poep_live.ps1                # 8 challenges, force 255, PULSE, sustained buzz (reliable-feel)
#   .\scripts\poep_live.ps1 -Sharp         # CLEAN mode: single 120ms jolt, no re-issue -> clean reflex
#                                          #   waveform for rung-2 shape (needs a reliable actuator/post-reset)
#   .\scripts\poep_live.ps1 8 255 rigid    # rigid stiffen instead of pulse
param([int]$Count = 8, [int]$Force = 255, [string]$Mode = "pulse", [switch]$Sharp)
$env:PYTHONIOENCODING = "utf-8"
$pyArgs = @("scripts/poep_live_capture.py", "--count", $Count, "--force", $Force, "--mode", $Mode,
            "--db", "C:/Users/Contr/.vapi/bridge.db")
if ($Sharp) { $pyArgs += "--sharp" }
python @pyArgs

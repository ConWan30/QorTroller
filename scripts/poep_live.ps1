# POEP-LIVE-1 — live NONCE-SCHEDULED challenge capture wrapper (avoids long-line paste-wrap).
# Same registered-Edge reflex primitive as edge_reflex.ps1, but the challenge fires at a RANDOM,
# nonce-derived moment you cannot anticipate (no ENTER cue) and binds the response to a fresh nonce.
# Hold the controller relaxed with a finger RESTING on R2; react to the surprise resistance.
# poep_enabled STAYS FALSE (candidate). Stop the bridge first.
#
# Usage:  .\scripts\poep_live.ps1 [count] [force] [mode]
#   .\scripts\poep_live.ps1              # 8 challenges, force 230 (strong), rigid
#   .\scripts\poep_live.ps1 8 255        # crank to MAX force if you still can't feel it
#   .\scripts\poep_live.ps1 8 230 pulse  # try a buzzing pulse if rigid feels faint
param([int]$Count = 8, [int]$Force = 255, [string]$Mode = "pulse")
$env:PYTHONIOENCODING = "utf-8"
python scripts/poep_live_capture.py --count $Count --force $Force --mode $Mode --db "C:/Users/Contr/.vapi/bridge.db"

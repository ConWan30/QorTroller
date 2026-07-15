# POEP-LIVE-1 — live NONCE-SCHEDULED challenge capture wrapper (avoids long-line paste-wrap).
# Same registered-Edge reflex primitive as edge_reflex.ps1, but the challenge fires at a RANDOM,
# nonce-derived moment you cannot anticipate (no ENTER cue) and binds the response to a fresh nonce.
# Hold the controller relaxed; react to the surprise resistance. poep_enabled STAYS FALSE (candidate).
# Stop the bridge first. Usage:  .\scripts\poep_live.ps1 8
param([int]$Count = 8)
$env:PYTHONIOENCODING = "utf-8"
python scripts/poep_live_capture.py --count $Count --db "C:/Users/Contr/.vapi/bridge.db"

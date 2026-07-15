# A2A-POEP-P2 — registered-Edge reflex campaign wrapper (avoids long-line paste-wrap in PowerShell).
# Stamps policy_ref=edge_operator_reflex_v1 + the registered Edge device_id, writes to the corpus
# home (bridge.db), still protocol. Usage:  .\scripts\edge_reflex.ps1 10
param([int]$Count = 10)
$env:PYTHONIOENCODING = "utf-8"
python scripts/l6b_desk_reaction_session.py --campaign edge-reflex --protocol still --count $Count --db "C:/Users/Contr/.vapi/bridge.db"

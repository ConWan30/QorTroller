# INV-MFG-003 governance seal wrapper (PV-CI 183 -> 184) — operator-fired.
# Exists because long inline --reason strings newline-split when pasted into
# PowerShell (banked gotcha). Interactive: you will be prompted to type
#   I understand this changes a frozen protocol invariant
Set-Location $PSScriptRoot\..
python scripts/vapi_invariant_gate.py --generate --reason "invariant_change: INV-MFG-003 pins the LIVE birth-cert override registry trust surface" --confirm-governance

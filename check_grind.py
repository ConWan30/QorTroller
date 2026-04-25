"""Smoke-run grind status check.

Usage (from repo root, in PowerShell):
    python check_grind.py

Prints PCC capture-health and GIC grind-chain-status side by side, plus
a one-line PASS/WAIT/BLOCKED verdict so you can tell at a glance whether
the gate is open and the chain is advancing.
"""
import json
import sys
import urllib.request

BRIDGE = "http://127.0.0.1:8080"
KEY    = "vapi-dev-local"

def hit(path):
    req = urllib.request.Request(BRIDGE + path, headers={"x-api-key": KEY})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

try:
    ch = hit("/operator/bridge/capture-health")
    gc = hit("/operator/bridge/grind-chain-status")
except Exception as exc:
    print(f"FAILED to reach bridge: {exc}")
    sys.exit(1)

# --- capture-health ---
print("=== PCC CAPTURE-HEALTH ===")
for k in (
    "capture_state",
    "host_state",
    "poll_rate_hz",
    "sustained_duration_s",
    "grind_mode",
    "grind_ready",
    "grind_target",
    "consecutive_clean_toward_target",
    "session_counting_paused",
    "latest_gameplay_context",
):
    print(f"  {k:36s} {ch.get(k)}")

# --- grind-chain-status ---
print()
print("=== GIC GRIND-CHAIN-STATUS ===")
for k in (
    "grind_session_id",
    "chain_length",
    "chain_intact",
    "latest_gic_hash",
    "genesis_ts",
    "latest_ts",
    "latest_gameplay_context",
):
    v = gc.get(k)
    if k == "latest_gic_hash" and isinstance(v, str) and len(v) > 16:
        v = v[:16] + "..."
    print(f"  {k:36s} {v}")

# --- one-line verdict ---
print()
ready  = ch.get("grind_ready")
paused = ch.get("session_counting_paused")
intact = gc.get("chain_intact")
length = gc.get("chain_length", 0)
target = ch.get("grind_target", 100)
state  = ch.get("capture_state")
host   = ch.get("host_state")

if not intact:
    verdict = f"BLOCKED  chain broken — investigate get_grind_chain_status"
elif paused:
    verdict = f"PAUSED   gate fail-closed: capture_state={state}, host={host} — sessions will not count"
elif not ready:
    verdict = f"WAIT     PCC not yet ready (sustained={ch.get('sustained_duration_s'):.1f}s) — gate opens after stable window"
elif length >= target:
    verdict = f"DONE     chain_length={length}/{target} reached — smoke target achieved"
else:
    verdict = f"OPEN     gate is open ({length}/{target}) — play; SessionAdjudicator polls every 5 min"

print(f">> {verdict}")

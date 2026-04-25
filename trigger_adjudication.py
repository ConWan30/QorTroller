"""Manually queue a ruling_request event for SessionAdjudicator.

Usage:
    python trigger_adjudication.py

SessionAdjudicator only processes events of type 'ruling_request' that land
in agent_events.  Nothing in the bridge auto-publishes these from gameplay
records — they're triggered by either BridgeAgent's `request_adjudication`
LLM tool or this manual HTTP endpoint.

For tonight's smoke run we run this once per "session" we want to count.
With PCC_SMOKE_BYPASS=true, each successful adjudication → validation →
GIC stamp pipeline yields chain_length += 1.
"""
import json
import sys
import urllib.request

BRIDGE = "http://127.0.0.1:8080"

# 1. discover device_id from the public devices endpoint
try:
    devs = json.loads(urllib.request.urlopen(BRIDGE + "/api/v1/devices", timeout=10).read())
except Exception as exc:
    print(f"FAILED to fetch devices: {exc}")
    sys.exit(1)

if not devs:
    print("No devices registered on the bridge.  Plug in the controller and let the bridge boot.")
    sys.exit(1)

device_id = devs[0]["device_id"]
print(f"device_id = {device_id[:24]}…")

# 2. POST a ruling_request
body = json.dumps({"device_id": device_id, "attestation_hash": ""}).encode()
req = urllib.request.Request(
    BRIDGE + "/agent/adjudicate",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
except Exception as exc:
    print(f"FAILED to POST /agent/adjudicate: {exc}")
    sys.exit(1)

print(f"queued: event_id={resp.get('event_id')} status={resp.get('status')}")
print()
print("Next steps:")
print("  1. Wait ~5 min for SessionAdjudicator's next poll cycle.")
print("     It picks up the ruling_request event and creates an agent_rulings row.")
print("  2. Wait another ~5 min for SessionAdjudicatorValidationAgent's next poll.")
print("     With PCC_SMOKE_BYPASS=true it stamps the GIC and chain_length advances.")
print("  3. Run `python check_grind.py` to verify chain_length ticked up.")
print("  4. Repeat this script 2 more times to reach chain_length=3 (smoke target).")

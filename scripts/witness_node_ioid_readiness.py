#!/usr/bin/env python3
"""TRL-1 R3 - witness-node ioID-registration readiness check.

Confirms the ON-CHAIN identity path for the trio-retina witness node is REAL, not
hypothetical: the deployed registries + the registration pattern + the
verifier-independence rail all already exist in this repo. Reports READY / gaps.

Registers NOTHING and writes no chain state - the actual ioID mint for a real
witness device is operator + device + spend gated (a future step; see the design
note). ASCII-only. Design: docs/witness-node-ioid-readiness-2026-07-11.md
"""
from __future__ import annotations

import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check_prerequisites(deployed_addrs: dict, exists) -> list:
    """Pure: (name, ok, detail) per prerequisite. `exists(relpath) -> bool` injected."""
    checks = []

    def _c(name, ok, detail):
        checks.append((name, bool(ok), detail))

    _c("ioID device-identity registry (deployed)", bool(deployed_addrs.get("VAPIioIDRegistry")),
       f"VAPIioIDRegistry = {deployed_addrs.get('VAPIioIDRegistry', 'MISSING')}")
    _c("device birth registry (deployed)", bool(deployed_addrs.get("VAPIManufacturerDeviceRegistry")),
       f"VMDR = {deployed_addrs.get('VAPIManufacturerDeviceRegistry', 'MISSING')}")
    _c("ioID registration pattern", exists("bridge/vapi_bridge/agent_registration.py"),
       "agent_registration.py (ioid_did / ioid_token precedent, e.g. the Curator DID)")
    _c("verifier-independence rail (RP-7)", exists("bridge/tests/test_dcert7_verifier_independence.py"),
       "the rail a witness node's OWN on-chain identity flips to independent")
    _c("W3bstream validation plane", exists("w3bstream/applet/Cargo.toml"),
       "mechanical-validation sandbox (frame_grabbing=false pinned)")
    return checks


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    try:
        deployed = json.load(open(os.path.join(_REPO, "contracts", "deployed-addresses.json"),
                                  encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"  ERROR: could not read deployed-addresses.json: {exc}")
        return 2

    def _exists(rel):
        return os.path.exists(os.path.join(_REPO, rel))

    checks = check_prerequisites(deployed, _exists)

    print("=" * 74)
    print("  TRL-1 R3 - WITNESS-NODE ioID-REGISTRATION READINESS")
    print("=" * 74)
    print("  The card is 'one purchase, two roadmaps': RP recall now, and the seed of a")
    print("  DePIN gaming WITNESS NODE later - the trusted thing that SEES (the controller")
    print("  is the trusted thing that ACTS). This checks the on-chain path is REAL.")
    print("-" * 74)
    for name, ok, detail in checks:
        print(f"  [{'OK ' if ok else 'GAP':3}] {name}")
        print(f"        {detail}")
    print("-" * 74)
    ready = all(ok for _, ok, _ in checks)
    if ready:
        print("  READY: every ioID-registration prerequisite exists. The witness-node identity")
        print("         path is real. The actual mint is OPERATOR + DEVICE + SPEND gated (not")
        print("         fired here) - see docs/witness-node-ioid-readiness-2026-07-11.md.")
    else:
        print("  GAPS: one or more prerequisites missing - see above.")
    print("=" * 74)
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())

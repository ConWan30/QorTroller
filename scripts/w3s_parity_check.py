#!/usr/bin/env python3
"""TRL-1 I3 - W3bstream applet parity check (mechanical-validation-only).

Audits the real w3bstream surfaces: sandbox_config.json pins frame_grabbing=false /
optical_capture=false, the applet validates (never captures), and the W3S invariants
are pinned in both the gate and the allowlist. Reports CONFORMANT / VIOLATION.
Reads only; no chain, no spend, no Rust build. ASCII-only.
Module: l9_presence/w3s_parity.py
"""
from __future__ import annotations

import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from l9_presence.w3s_parity import assess_w3s_parity, CONFORMANT

_CONFIG = os.path.join(_REPO, "w3bstream", "sandbox_config.json")
_APPLET = os.path.join(_REPO, "w3bstream", "applet", "src", "lib.rs")
_GATE = os.path.join(_REPO, "scripts", "vapi_invariant_gate.py")
_ALLOWLIST = os.path.join(_REPO, ".github", "INVARIANTS_ALLOWLIST.json")


def _read(path):
    return open(path, encoding="utf-8").read()


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    for p in (_CONFIG, _APPLET, _GATE, _ALLOWLIST):
        if not os.path.isfile(p):
            print(f"  INCOMPLETE: missing {os.path.relpath(p, _REPO)}")
            return 2
    config = json.loads(_read(_CONFIG))
    res = assess_w3s_parity(config, _read(_APPLET), _read(_GATE), _read(_ALLOWLIST))

    mech = config.get("mechanisms", config)
    print("=" * 74)
    print("  TRL-1 I3 - W3BSTREAM APPLET PARITY (mechanical-validation-only)")
    print("=" * 74)
    print(f"  config : frame_grabbing={mech.get('frame_grabbing')}  "
          f"optical_capture={mech.get('optical_capture')}")
    print(f"  applet : w3bstream/applet/src/lib.rs (validates the PoAC payload; no capture)")
    print(f"  pinned : INV-W3S-001 / INV-W3S-002 in gate + allowlist")
    print("-" * 74)
    print(f"  STATUS: {res['status']}")
    for v in res["violations"]:
        print(f"    VIOLATION: {v}")
    if res["status"] == CONFORMANT:
        print("  The sandbox validates events and never captures them - the perception")
        print("  compute plane can never become a biometric capture surface.")
    print("=" * 74)
    return 0 if res["status"] == CONFORMANT else 1


if __name__ == "__main__":
    raise SystemExit(main())

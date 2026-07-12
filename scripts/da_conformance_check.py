#!/usr/bin/env python3
"""TRL-1 I2 - DA sidecar-pointer conformance check.

Audits a PoSP boundary record (default: the real M17 record) for Arc 7's law -
bulk scene payloads live off-chain on the DA node; only 32-byte commitments cross
the boundary. Reports CONFORMANT / VIOLATION. Reads only; no chain, no spend.
ASCII-only. Module: l9_presence/da_conformance.py

  python scripts/da_conformance_check.py
  python scripts/da_conformance_check.py audits/posp_record_match13_hdmi_direct_2026-07-06.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from l9_presence.da_conformance import assess_da_conformance, CONFORMANT

_DEFAULT = os.path.join(_REPO, "audits", "posp_record_match17_rp_fixb3_2026-07-08.json")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="TRL-1 I2 DA sidecar-pointer conformance")
    ap.add_argument("record", nargs="?", default=_DEFAULT, help="PoSP record JSON (default: M17)")
    a = ap.parse_args()

    try:
        record = json.load(open(a.record, encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"  ERROR: could not read {a.record}: {exc}")
        return 2

    res = assess_da_conformance(record)
    roots = record.get("events_roots") or {}
    print("=" * 74)
    print("  TRL-1 I2 - DA SIDECAR-POINTER CONFORMANCE")
    print("=" * 74)
    print(f"  record : {os.path.basename(a.record)}")
    print(f"  law    : bulk on DA, 32B commitment on the wire (Arc 7 / alignment doc N2)")
    print("-" * 74)
    for name, v in roots.items():
        tag = "pointer" if (v is None or (isinstance(v, str) and 64 <= len(v) <= 66)) else "INLINE?"
        shown = (str(v)[:20] + "...") if isinstance(v, str) and v else str(v)
        print(f"  events_roots.{name:<24} {tag:<8} {shown}")
    print("-" * 74)
    print(f"  STATUS: {res['status']}")
    for v in res["violations"]:
        print(f"    VIOLATION: {v}")
    if res["status"] == CONFORMANT:
        print("  Scene/perception commitments are pointers; no raw scene payload crosses the")
        print("  boundary. (Bulk frames/events stay DA-class, off the wire.)")
    print("=" * 74)
    return 0 if res["status"] == CONFORMANT else 1


if __name__ == "__main__":
    raise SystemExit(main())

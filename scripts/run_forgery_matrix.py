#!/usr/bin/env python3
"""ADVERSARY-EXPAND runner — emit the presence-forgery attack -> rail matrix.

Runs every forgery attack through its target verifier and prints the machine-checked matrix +
writes the artifact to audits/. `holds=True` means every forgery hit its named fail-closed rail;
a single un-rejected attack is a finding. Offline, no rig, no chain.
"""
from __future__ import annotations

import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from l9_presence.adversarial.presence_forgery import run_forgery_matrix


def main() -> int:
    r = run_forgery_matrix()
    print(r.to_markdown())
    out = os.path.join("audits", "presence_forgery_matrix.json")
    try:
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(r.to_dict(), fh, indent=2, sort_keys=True)
        print(f"\nwrote {out}")
    except Exception as e:                       # noqa: BLE001
        print(f"\n(could not write artifact: {e})")
    return 0 if r.holds else 1


if __name__ == "__main__":
    raise SystemExit(main())

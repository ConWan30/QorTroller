#!/usr/bin/env python3
"""Run the WMP AH-1 adversarial matrix over the published UC-1 bundle.

Exit 0 iff `holds` — every registered attack hit its expected outcome (CAUGHT /
OUT-OF-SCOPE). Exit 1 if any logic-level vector is a GAP-FOUND (a real finding:
fix the verifier, re-prove, then this returns to 0). The pure path runs offline
(no snarkjs / RPC) — the full-crypto legs for A1 are already banked in the UC-1
report; this runner is the CI-fast regression pin.

  python scripts/run_wmp_adversarial_matrix.py [--bundle path.jsonl] [--json]

Design: docs/wmp-adversarial-hardening-ah1-design-2026-07-11.md
Matrix: docs/wmp-adversarial-matrix-2026-07-11.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from sdk.wmp_adversarial import run_all, load_uc1_bundle


def main() -> int:
    ap = argparse.ArgumentParser(description="WMP AH-1 adversarial matrix")
    ap.add_argument("--bundle", default=None, help="attack base (default: published UC-1 corpus)")
    ap.add_argument("--json", action="store_true", help="emit the machine mirror")
    a = ap.parse_args()

    base = load_uc1_bundle(a.bundle) if a.bundle else load_uc1_bundle()
    m = run_all(base)

    if a.json:
        print(json.dumps(m.to_dict(), indent=2))
        return 0 if m.holds else 1

    print("=" * 78)
    print("  WMP AH-1 ADVERSARIAL MATRIX  (pure consumer path — CI-fast pin)")
    print("=" * 78)
    for r in m.results:
        flag = "OK " if r.ok else "GAP"
        print(f"  [{flag}] {r.id:<4} {r.vector:<22} -> {r.result:<24} ({r.target_check})")
        print(f"        evidence: {r.evidence}")
    print("-" * 78)
    print(f"  holds = {m.holds}   ({sum(1 for r in m.results if r.ok)}/{len(m.results)} vectors banked)")
    if not m.holds:
        print("  A GAP-FOUND is a real finding: fix the verifier, re-prove, then holds -> True.")
    return 0 if m.holds else 1


if __name__ == "__main__":
    raise SystemExit(main())

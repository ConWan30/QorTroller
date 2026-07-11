#!/usr/bin/env python3
"""Build + verify a WMP Verifiable Derived-Claim (VDC) from a certified bundle.

  python scripts/build_wmp_derived_claim.py [--bundle path.jsonl] \
      [--derivation TRIGGER_ENGAGEMENT_FRACTION_v1] [--out claim.json] [--list]

Exit 0 iff the built claim VERIFIES (re-derives + binds). The SDK stays pure;
this runner is the file-I/O boundary (the skill_strata / PORT-CERT pattern).

Design: docs/wmp-derived-claim-vdc1-2026-07-11.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from sdk.wmp_derived import build_claim, verify_claim, DERIVATIONS

_DEFAULT_BUNDLE = os.path.join(_REPO, "wmp_corpus_real", "wmp_corpus.jsonl")


def _load_bundle(path: str) -> dict:
    raw = open(path, encoding="utf-8").read().strip()
    first = raw.splitlines()[0] if path.endswith(".jsonl") else raw
    return json.loads(first)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build + verify a WMP derived claim")
    ap.add_argument("--bundle", default=_DEFAULT_BUNDLE)
    ap.add_argument("--derivation", default="TRIGGER_ENGAGEMENT_FRACTION_v1")
    ap.add_argument("--out", default=None, help="write the claim JSON here")
    ap.add_argument("--generated-at", default="")
    ap.add_argument("--list", action="store_true", help="list registered derivations")
    a = ap.parse_args()

    if a.list:
        print("registered derivations:")
        for d in sorted(DERIVATIONS):
            print(f"  {d}")
        return 0

    bundle = _load_bundle(a.bundle)
    claim = build_claim(bundle, a.derivation, generated_at=a.generated_at)
    res = verify_claim(claim, bundle)

    print("=" * 74)
    print("  WMP VERIFIABLE DERIVED-CLAIM (VDC)")
    print("=" * 74)
    print(f"  derivation      : {claim['derivation_id']}")
    print(f"  parent bundle   : {claim['parent_bundle_hash'][:16]}… (bound)")
    print(f"  value           : {json.dumps(claim['value'])}")
    print(f"  claim_hash      : {claim['claim_hash'][:16]}…")
    print("-" * 74)
    for c in res["checks"]:
        print(f"  [{'OK ' if c['ok'] else 'FAIL':4}] {c['name']:<18} {c['note']}")
    print("-" * 74)
    print(f"  VERIFY: {'ok' if res['ok'] else 'FAILED'}")

    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(claim, f, indent=2)
        print(f"  wrote {a.out}")

    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Arc A — Tournament-operator PoSP record verifier.

Offline CLI for verifying a QORTROLLER-POSP-v0 CANDIDATE record without running the bridge.
Reads a PoSP JSON file and reports per-surface verification (structural consistency,
session_id presence, KAS commitment, verdict consistency).

On-chain anchoring and archive SHA-256 cross-referencing are deferred
(CHAIN_SUBMISSION_PAUSED; gated on those files being co-located with the verifier).

Exit codes:
  0 = VERIFIED (SYNCHRONIZED + all critical checks pass)
  1 = PARTIAL / FAILED / SCHEMA_ERROR
  2 = file not found / JSON parse error

Usage:
    python scripts/verify_posp_record.py audits/posp_record_match13_hdmi_direct_2026-07-06.json
    python scripts/verify_posp_record.py audits/posp_record_*.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from l9_presence.posp_verifier import verify_posp_record


def _print_report(rep, path: str) -> None:
    width = 60
    sep = "-" * width
    print(f"\n{sep}")
    print(f"  PoSP verification -- {os.path.basename(path)}")
    print(sep)
    print(f"  schema   : {rep.schema_found}")
    print(f"  verdict  : {rep.verdict_found}")
    print(f"  session  : {rep.session_id}")
    print(f"  overall  : {rep.overall}")
    print()
    for c in rep.checks:
        mark = "PASS" if c.passed else "FAIL"
        print(f"  [{mark}] {c.name}: {c.note}")
    print(f"{sep}\n")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Verify a QORTROLLER-POSP-v0 CANDIDATE record offline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Exit 0 = VERIFIED; 1 = PARTIAL/FAILED/SCHEMA_ERROR; 2 = file/JSON error",
    )
    ap.add_argument("posp_file", help="Path to PoSP JSON file")
    args = ap.parse_args()

    if not os.path.isfile(args.posp_file):
        print(f"ERROR: file not found: {args.posp_file}", file=sys.stderr)
        return 2

    try:
        with open(args.posp_file, encoding="utf-8") as fh:
            record = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: cannot read JSON: {exc}", file=sys.stderr)
        return 2

    rep = verify_posp_record(record)
    _print_report(rep, args.posp_file)
    return 0 if rep.passed() else 1


if __name__ == "__main__":
    sys.exit(main())

"""CLI wrapper for WMP-3 consumer verifier.

Usage:
    # Verify a single bundle JSON file (fixture)
    python scripts/verify_action_provenance.py --bundle path/to/bundle.json \
        --allow-synthetic

    # Verify a JSONL corpus
    python scripts/verify_action_provenance.py --corpus path/to/wmp_corpus.jsonl \
        --allow-synthetic

Output: one JSON object per bundle plus a final summary line carrying
pass / reject / deferred counts. Exit 0 iff ALL bundles VERIFIED.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk"))

from wmp_verify import verify_bundle, OUTCOME_VERIFIED  # noqa: E402


def _iter_bundles(args):
    if args.bundle:
        yield json.loads(Path(args.bundle).read_text(encoding="utf-8"))
        return
    if args.corpus:
        for line in Path(args.corpus).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="verify_action_provenance",
        description="WMP-3 consumer verifier — five-check ProvenanceBundle v1.",
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--bundle", type=Path, help="Single bundle JSON file")
    src.add_argument("--corpus", type=Path, help="JSONL corpus file")
    p.add_argument("--allow-synthetic", action="store_true",
                   help="Accept scope_synthetic=True bundles (fixture mode).")
    args = p.parse_args(argv)

    n_verified = 0
    n_rejected = 0
    n_deferred_any = 0
    for b in _iter_bundles(args):
        r = verify_bundle(b, allow_synthetic=args.allow_synthetic)
        print(json.dumps(r.to_dict(), separators=(",", ":")))
        if r.overall == OUTCOME_VERIFIED:
            n_verified += 1
        else:
            n_rejected += 1
        if r.deferred:
            n_deferred_any += 1

    summary = {
        "summary":        True,
        "verified":       n_verified,
        "rejected":       n_rejected,
        "deferred_count": n_deferred_any,
    }
    print(json.dumps(summary, separators=(",", ":")))
    return 0 if n_rejected == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

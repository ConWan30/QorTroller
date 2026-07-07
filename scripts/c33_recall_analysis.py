#!/usr/bin/env python3
"""C-3.3 offline recall analysis — compute recall at a given K threshold from an existing
scan JSON (produced by the killfeed_audit_lane.py cluster scan over a match archive).

No re-scan: reads the committed scan JSON and re-applies the cluster-size floor at --k,
reporting how recall changes without re-running the 400s OCR pass.

Usage:
    python scripts/c33_recall_analysis.py                          # K=3 (conservative floor)
    python scripts/c33_recall_analysis.py --k 2                   # K=2 (ceiling estimate)
    python scripts/c33_recall_analysis.py --scan audits/other.json --k 2

The K here is the OFFLINE AUDIT SCAN cluster-size floor — how many independent archive
crops within the 5s chaining window constitute a "promotable" kill cluster.

It is NOT `DEFAULT_K_CONSISTENCY` (the live session-anchor promotion gate in
l9_presence/killfeed_session_anchor.py), which governs live scoring and remains at 3.

The K=2 recall figure is a ceiling: it states "these 7 kills appeared 2+ times in the
dense archive, so the live system COULD have attested them at K=2 — but only if the
live classify stream also saw 2+ reads within an R2 window." The archive stream is denser
than the live classify stream, so the ceiling is not a guarantee. K=3 is the operative
floor for the PoSP authored-kills claim.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_SCAN = os.path.join(_REPO, "audits", "c33_m13_recall_scan.json")


def analyse(scan_path: str, k: int) -> None:
    with open(scan_path) as f:
        data = json.load(f)

    clusters = data["clusters"]
    kas_authored = data["kas_authored_kills"]
    total_crops = data["total_crops"]
    total_clusters = len(clusters)

    promotable = [c for c in clusters if c["size"] >= k]
    un_promotable = [c for c in clusters if c["size"] < k]

    n_promotable = len(promotable)
    n_unpromot = len(un_promotable)

    # breakdowns
    by_size: dict[int, list] = {}
    for c in clusters:
        by_size.setdefault(c["size"], []).append(c)

    print(f"\nC-3.3 Recall Analysis  |  archive: {os.path.basename(scan_path)}  |  K={k}")
    print("=" * 70)
    print(f"  Total crops scanned:        {total_crops}")
    print(f"  Distinct kill clusters:     {total_clusters}")
    print(f"  KAS authored_kills (live):  {kas_authored}")
    print()

    # cluster-size breakdown
    print("  Cluster-size breakdown:")
    for sz in sorted(by_size):
        tag = "promotable" if sz >= k else "un-promotable"
        print(f"    size={sz}: {len(by_size[sz])} clusters  [{tag} at K={k}]")
    print()

    print(f"  Promotable (size >= {k}):   {n_promotable} of {total_clusters} clusters")
    print(f"  Un-promotable (size <  {k}): {n_unpromot} of {total_clusters} clusters")
    print()

    # recall figures
    overall_pct = round(kas_authored / total_clusters * 100, 1)
    promotable_pct = round(kas_authored / n_promotable * 100, 1) if n_promotable else 0.0
    ceiling_authored = kas_authored + (n_promotable - sum(1 for c in promotable
                                                          if c["size"] >= 3 and False))
    # ceiling: if all K-promotable clusters are genuine kills and the live system catches them
    k2_ceiling_authored = kas_authored + len([c for c in clusters if 2 <= c["size"] < 3]) if k == 2 else None

    print(f"  Overall recall (KAS={kas_authored} / {total_clusters} clusters): {overall_pct}%")
    print(f"  Recall within promotable only: {kas_authored}/{n_promotable} = {promotable_pct}%")
    if k == 2:
        # 7 two-crop clusters not attested live at K=3 → ceiling if live system had K=2
        size2 = len([c for c in clusters if c["size"] == 2])
        ceiling = kas_authored + size2
        ceiling_pct = round(ceiling / total_clusters * 100, 1)
        print()
        print(f"  K=2 ceiling  (KAS_live={kas_authored} + {size2} two-crop clusters): "
              f"{ceiling}/{total_clusters} = {ceiling_pct}%")
        print(f"  [ceiling assumes the live classify stream also saw >=2 reads on each")
        print(f"   of the {size2} two-crop archive clusters — not guaranteed; archive is denser]")

    print()
    if k == 3:
        print("  Operative floor for PoSP authored-kills claim: K=3 (conservative).")
        print("  Run with --k 2 to see the ceiling estimate.")
    else:
        print("  This is a ceiling, not the operative PoSP floor.")
        print("  The PoSP claim uses K=3 (29.6%) as the conservative floor.")

    print()


def main() -> None:
    ap = argparse.ArgumentParser(description="C-3.3 recall analysis at a given K threshold")
    ap.add_argument("--scan", default=_DEFAULT_SCAN,
                    help="Path to the cluster-scan JSON (default: audits/c33_m13_recall_scan.json)")
    ap.add_argument("--k", type=int, default=3,
                    help="Cluster-size floor for 'promotable' (default 3; try 2 for ceiling)")
    args = ap.parse_args()

    if not os.path.isfile(args.scan):
        sys.exit(f"Scan JSON not found: {args.scan}")
    if args.k < 1:
        sys.exit("--k must be >= 1")

    analyse(args.scan, args.k)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""RP-CLOSE-1 gate RP-3 -- OCR precision scan over Remote-Play-encoded archives.

The zero-false-read bar (G1') and the C-3.3 recall floor were measured on HDMI-clean
M13 crops (0 false reads / 524 crops). Remote Play's streaming codec introduces
compression artifacts and macroblocking in exactly the fast scenes where kills happen.
This scan re-runs Instrument A (tight_row_ocr, v6-only -- the SAME shared engine the
live bootstrap uses) over RP-era archives to answer:

  1. Does the zero-false-read bar HOLD on RP-codec-degraded frames?
  2. What is the read rate / cluster density vs the HDMI baseline?
  3. Do ABSTAIN-discipline reads stay clean (no hallucinated handles on codec noise)?

Read-only: no daemon, no live path, no bridge. Mirrors the C-3.3 scan output shape
(audits/c33_m13_recall_scan.json) so figures are directly comparable.

Usage:
    python scripts/rp_ocr_precision_scan.py \
        --archive retina_kf_archive/match12_kas_validation_1783382836 \
        --archive retina_kf_archive/match11_kas_validation_1783378335 \
        --out audits/rp_ocr_precision_scan.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TS_RE = re.compile(r"panel_(\d+)\.png$")
_CLUSTER_WINDOW_MS = 5000.0        # same 5s chaining window as the C-3.3 scan
_OWN_HANDLE_SUBSTR = "qortrola30"  # plain-substring audit flag (canon matching already ran)


def scan_archive(archive_dir: str) -> dict:
    import cv2
    from l9_presence import killfeed_ocr_bootstrap as ob

    files = []
    for name in os.listdir(archive_dir):
        m = _TS_RE.search(name)
        if m:
            files.append((int(m.group(1)), os.path.join(archive_dir, name)))
    files.sort()

    matched = []          # (ts_ns, text, conf, slot, engine)
    abstained = 0
    read_errors = 0
    t0 = time.time()

    for i, (ts_ns, path) in enumerate(files):
        bgr = cv2.imread(path)
        if bgr is None:
            read_errors += 1
            continue
        r = ob.tight_row_ocr(bgr, engine_ids=(ob.ENGINE_V6,))
        if r.matched:
            matched.append((ts_ns, r.text, r.conf, r.slot, r.engine))
        else:
            abstained += 1
        if (i + 1) % 25 == 0:
            print(f"  {i + 1}/{len(files)} crops  {time.time() - t0:.1f}s  "
                  f"matched_so_far={len(matched)}", flush=True)

    elapsed = time.time() - t0

    # 5s-window clustering, identical to the C-3.3 methodology
    clusters = []
    for ts_ns, text, conf, slot, engine in matched:
        if clusters and (ts_ns - clusters[-1]["_last_ts"]) / 1e6 <= _CLUSTER_WINDOW_MS:
            c = clusters[-1]
            c["size"] += 1
            c["span_ms"] = round((ts_ns - c["_first_ts"]) / 1e6, 1)
            c["texts"].append(text)
            c["_last_ts"] = ts_ns
        else:
            clusters.append({"size": 1, "span_ms": 0.0, "texts": [text],
                             "_first_ts": ts_ns, "_last_ts": ts_ns})
    for c in clusters:
        c.pop("_first_ts"), c.pop("_last_ts")

    # audit flag: canon-matched reads whose raw text lacks the plain own-handle substring
    # (candidates for manual adjudication, like C-3.3's single "krfn88Qortrola30" case)
    suspect = [t for _, t, _, _, _ in matched if _OWN_HANDLE_SUBSTR not in t.lower()]

    return {
        "archive": archive_dir,
        "total_crops": len(files),
        "read_errors": read_errors,
        "matched_crops": len(matched),
        "abstained_crops": abstained,
        "clusters": clusters,
        "n_clusters": len(clusters),
        "suspect_reads": suspect,      # texts needing manual adjudication; [] = bar held clean
        "matched_texts": [t for _, t, _, _, _ in matched],
        "matched_slots": sorted({s for _, _, _, s, _ in matched}),
        "elapsed_s": round(elapsed, 1),
        "ms_per_crop": round(elapsed * 1000 / max(1, len(files)), 0),
        "engine": "v6-only (ENGINE_V6) -- same as live bootstrap",
        "cluster_window_ms": _CLUSTER_WINDOW_MS,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="RP-3 OCR precision scan (Instrument A, v6-only)")
    ap.add_argument("--archive", action="append", required=True,
                    help="Archive dir of panel_*.png crops (repeatable)")
    ap.add_argument("--out", default="audits/rp_ocr_precision_scan.json")
    args = ap.parse_args()

    results = []
    for arch in args.archive:
        if not os.path.isdir(arch):
            print(f"SKIP (not a dir): {arch}")
            continue
        print(f"\nscanning {arch} ...", flush=True)
        res = scan_archive(arch)
        results.append(res)
        print(f"  -> {res['matched_crops']}/{res['total_crops']} matched, "
              f"{res['n_clusters']} clusters, {len(res['suspect_reads'])} suspect, "
              f"{res['elapsed_s']}s")

    out = {"scan": "rp-ocr-precision-v1", "results": results}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(f"\nresult written -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

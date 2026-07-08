#!/usr/bin/env python3
"""RP-2d runner -- build a deferred-attestation record for one session.

Loads: the v2 precision scan (per-read file/ts/sha), the session archive manifest,
the live R2 window spans (retina_kf_composite.jsonl filtered to the KAS span), and
the live KAS record. Emits audits/kas_deferred_record_{display}_{date}.json and runs
the verifier mirror (re-hash referenced crops) before writing.

Usage:
    python scripts/build_deferred_attestation.py \
        --scan audits/rp_ocr_precision_scan_v2_m14_m13.json \
        --archive retina_kf_archive/match14_rp_option_b_1783475385 \
        --kas audits/kas_record_match14_rp_option_b_2026-07-07.json \
        [--composites retina_kf_composite.jsonl]

Exit 0 = record built + verifier OK; 1 = UNVERIFIABLE or verifier failure; 2 = I/O error.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from l9_presence.kas_deferred import build_deferred_record, verify_deferred_record

_SPAN_PAD_MS = 60_000.0    # windows within KAS span +/- 1 min belong to this session


def _load_windows(composites_path: str, span_ms) -> list:
    """Extract [gate_ms, end_ms] window spans from the composite jsonl, filtered to the
    session span (padded). The jsonl is a rolling multi-session file -- the span filter
    is what scopes it to THIS session."""
    if not os.path.isfile(composites_path) or not span_ms:
        return []
    lo, hi = float(span_ms[0]) - _SPAN_PAD_MS, float(span_ms[1]) + _SPAN_PAD_MS
    wins, seen = [], set()
    with open(composites_path, encoding="utf-8") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            g, e = d.get("window_gate_ms"), d.get("window_end_ms")
            if g is None or e is None:
                continue
            if lo <= float(g) <= hi and (g, e) not in seen:
                seen.add((g, e))
                wins.append((float(g), float(e)))
    return sorted(wins)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a deferred-attestation record (RP-2d)")
    ap.add_argument("--scan", required=True, help="v2 precision-scan JSON")
    ap.add_argument("--archive", required=True, help="session archive dir (with manifest.json)")
    ap.add_argument("--kas", required=True, help="live KAS record JSON")
    ap.add_argument("--composites", default="retina_kf_composite.jsonl",
                    help="live window log (rolling jsonl; span-filtered)")
    ap.add_argument("--out", default=None, help="output path (default audits/kas_deferred_record_...)")
    args = ap.parse_args()

    try:
        scan_doc = json.load(open(args.scan, encoding="utf-8"))
        manifest = json.load(open(os.path.join(args.archive, "manifest.json"), encoding="utf-8"))
        kas = json.load(open(args.kas, encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    # pick THIS archive's result out of a multi-archive scan file
    results = scan_doc.get("results") or [scan_doc]
    arch_norm = args.archive.replace("\\", "/").rstrip("/")
    scan = next((r for r in results
                 if str(r.get("archive", "")).replace("\\", "/").rstrip("/") == arch_norm), None)
    if scan is None:
        print(f"ERROR: no scan result for archive {args.archive!r} in {args.scan!r}",
              file=sys.stderr)
        return 2

    windows = _load_windows(args.composites, kas.get("span_ms"))
    rec = build_deferred_record(scan=scan, manifest=manifest, windows=windows,
                                kas_record=kas)

    sep = "-" * 64
    print(f"\n{sep}\n  Deferred attestation -- {rec.session_display}\n{sep}")
    print(f"  verdict            : {rec.verdict}")
    print(f"  deferred_authored  : {rec.deferred_authored}")
    print(f"  deferred_observed  : {rec.deferred_observed}")
    print(f"  unpromotable       : {rec.unpromotable_clusters}")
    print(f"  windows_used       : {rec.windows_used}")
    print(f"  live KAS verdict   : {rec.source_kas_verdict} "
          f"(commit {str(rec.source_kas_commitment)[:16]}...)")
    for n in rec.notes:
        print(f"  note: {n}")

    # verifier mirror BEFORE writing -- a record that fails its own verifier is not emitted
    v = verify_deferred_record(rec.to_dict(), manifest, args.archive)
    bad = [c for c in v["checks"] if not c["ok"]]
    print(f"  verifier           : {'OK' if v['ok'] else 'FAIL'} "
          f"({len(v['checks'])} checks{', ' + str(len(bad)) + ' failed' if bad else ''})")
    for c in bad[:5]:
        print(f"    FAIL {c['name']}: {c['note']}")
    if not v["ok"]:
        return 1

    out = args.out or os.path.join(
        "audits", f"kas_deferred_record_{rec.session_display}_{time.strftime('%Y-%m-%d')}.json")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(rec.to_json())
    print(f"  written            : {out}\n{sep}\n")
    return 0 if rec.verdict != "UNVERIFIABLE" else 1


if __name__ == "__main__":
    sys.exit(main())

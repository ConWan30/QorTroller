#!/usr/bin/env python3
"""LUMEN-1 runner -- build a session's SceneEventStream from its archive.

Gathers: manifest + crop gray-deltas (cv2 IO helper) + optional v2 precision scan
(kill-row clusters) + live R2 windows (retina_kf_composite.jsonl, span-filtered).
Runs the LUMEN-2 join check (every crop_sha resolves in the manifest; session_id
matches) before writing. Advisory output only.

Usage:
    python scripts/build_game_state_buffer.py \
        --archive retina_kf_archive/match14_rp_option_b_1783475385 \
        [--scan audits/rp_ocr_precision_scan_v2_m14_m13.json] \
        [--kas audits/kas_record_match14_rp_option_b_2026-07-07.json] \
        [--composites retina_kf_composite.jsonl]

Exit 0 = stream built + join check OK; 1 = join check failed; 2 = I/O error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from l9_presence.game_state_buffer import (
    PANEL_FRESH_DIFF, build_scene_stream, compute_crop_deltas, verify_stream_references,
)

_TS_RE = re.compile(r"panel_(\d+)\.png$")
_SPAN_PAD_MS = 60_000.0


def _load_windows(composites_path: str, span_ms) -> list:
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
            if g is not None and e is not None and lo <= float(g) <= hi and (g, e) not in seen:
                seen.add((g, e))
                wins.append((float(g), float(e)))
    return sorted(wins)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a SceneEventStream (LUMEN-1)")
    ap.add_argument("--archive", required=True)
    ap.add_argument("--scan", default=None, help="v2 precision-scan JSON (optional)")
    ap.add_argument("--kas", default=None, help="KAS record (span source for windows)")
    ap.add_argument("--composites", default="retina_kf_composite.jsonl")
    ap.add_argument("--fresh-diff", type=float, default=PANEL_FRESH_DIFF,
                    help="scene-change threshold (default: F-LUMEN-1 calibrated panel p75)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    try:
        manifest = json.load(open(os.path.join(args.archive, "manifest.json"), encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: manifest: {exc}", file=sys.stderr)
        return 2

    paths = []
    for name in sorted(os.listdir(args.archive)):
        m = _TS_RE.search(name)
        if m:
            paths.append((int(m.group(1)), os.path.join(args.archive, name)))
    paths.sort()
    print(f"computing gray-deltas over {len(paths)} crops ...", flush=True)
    t0 = time.time()
    deltas = compute_crop_deltas(paths)
    print(f"  {len(deltas)} deltas in {time.time() - t0:.1f}s")

    scan = None
    if args.scan:
        doc = json.load(open(args.scan, encoding="utf-8"))
        arch_norm = args.archive.replace("\\", "/").rstrip("/")
        scan = next((r for r in (doc.get("results") or [doc])
                     if str(r.get("archive", "")).replace("\\", "/").rstrip("/") == arch_norm),
                    None)
        if scan is None:
            print(f"NOTE: no scan result for this archive in {args.scan}")

    windows = []
    if args.kas and os.path.isfile(args.kas):
        kas = json.load(open(args.kas, encoding="utf-8"))
        windows = _load_windows(args.composites, kas.get("span_ms"))

    stream = build_scene_stream(manifest=manifest, deltas=deltas, scan=scan,
                                windows=windows, fresh_diff=args.fresh_diff)
    join = verify_stream_references(stream, manifest)

    sep = "-" * 64
    print(f"\n{sep}\n  Scene stream -- {stream.session_display}\n{sep}")
    print(f"  events   : {sum(stream.counts().values())}  {stream.counts()}")
    print(f"  join     : {'OK' if join['ok'] else 'FAIL'} ({join['note']})")
    for n in stream.notes:
        print(f"  note: {n}")
    if not join["ok"]:
        return 1

    out = args.out or os.path.join(
        "audits", f"scene_stream_{stream.session_display}.jsonl")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(stream.to_jsonl())
    print(f"  written  : {out}\n{sep}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

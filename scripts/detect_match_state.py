#!/usr/bin/env python3
"""LUMEN-2 runner -- detect match begin/end inside a captured session.

Feeds the pure detector (l9_presence/match_state.py) from a session's persisted
artifacts: archive manifest (session span + join key), retina_hid_events.jsonl
(R2 onsets), retina_kf_composite.jsonl (live windows), and the v2 precision scan
(kill-row clusters = definitive anchors; every read is zero-FP canon-matched).
Then runs the honest containment evaluation: every kill cluster and live window
MUST land inside a detected IN_MATCH span.

Usage:
    python scripts/detect_match_state.py \
        --archive retina_kf_archive/match14_rp_option_b_1783475385 \
        --scan audits/rp_ocr_precision_scan_v2_m14_m13.json

Exit 0 = timeline built + containment OK; 1 = containment miss; 2 = I/O error.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from l9_presence.match_state import detect_match_state, evaluate_containment


def _session_span_ms(manifest: dict) -> tuple:
    start_ms = float(manifest["started_at"]) * 1000.0
    end_ms = start_ms + 3600_000.0            # fallback: 1h cap
    archived = manifest.get("archived_at")
    if archived:
        try:
            end_ms = _dt.datetime.strptime(archived, "%Y-%m-%d %H:%M:%S").timestamp() * 1000.0
        except ValueError:
            pass
    return (start_ms, end_ms)


def _load_onsets(path: str, span) -> list:
    if not os.path.isfile(path):
        return []
    lo, hi = span
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = d.get("t_ms") or d.get("wall_ms")
            if d.get("type") == "r2_onset" and t and lo <= float(t) <= hi:
                out.append(float(t))
    return out


def _load_windows(path: str, span) -> list:
    if not os.path.isfile(path):
        return []
    lo, hi = span
    wins, seen = [], set()
    with open(path, encoding="utf-8") as fh:
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


def _kill_spans(scan: dict, anchor_k: int = 2) -> tuple:
    """Split clusters into ANCHORS (size >= anchor_k -- corroborated kill rows) and
    SIGHTINGS (size 1 -- a canon-matched handle read that may be a post-match summary
    screen showing the operator's name, NOT a kill row; F-LUMEN-2, found live on M14's
    K15 at match+4min). Sightings are excluded from activity AND containment; they are
    reported with their detected state so post-match ones read as expected-LOBBY."""
    anchors, sightings = [], []
    for c in (scan or {}).get("clusters") or []:
        ts = [r["ts_ns"] for r in (c.get("reads") or []) if r.get("ts_ns")]
        if not ts:
            continue
        span = (min(ts) / 1e6, max(ts) / 1e6)
        (anchors if int(c.get("size", 0)) >= anchor_k else sightings).append(span)
    return anchors, sightings


def main() -> int:
    ap = argparse.ArgumentParser(description="Detect match begin/end (LUMEN-2, offline v0)")
    ap.add_argument("--archive", required=True)
    ap.add_argument("--scan", default=None, help="v2 precision-scan JSON (kill anchors)")
    ap.add_argument("--hid-events", default="retina_hid_events.jsonl")
    ap.add_argument("--composites", default="retina_kf_composite.jsonl")
    ap.add_argument("--anchor-k", type=int, default=2,
                    help="min cluster size to count as a kill ANCHOR (F-LUMEN-2: "
                         "size-1 reads may be post-match handle sightings)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    try:
        manifest = json.load(open(os.path.join(args.archive, "manifest.json"), encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: manifest: {exc}", file=sys.stderr)
        return 2

    span = _session_span_ms(manifest)
    onsets = _load_onsets(args.hid_events, span)
    windows = _load_windows(args.composites, span)

    scan = None
    if args.scan:
        doc = json.load(open(args.scan, encoding="utf-8"))
        arch_norm = args.archive.replace("\\", "/").rstrip("/")
        scan = next((r for r in (doc.get("results") or [doc])
                     if str(r.get("archive", "")).replace("\\", "/").rstrip("/") == arch_norm),
                    None)
    kills, sightings = _kill_spans(scan, args.anchor_k) if scan else ([], [])

    tl = detect_match_state(session_span_ms=span, onsets_ms=onsets, windows_ms=windows,
                            kill_spans_ms=kills,
                            session_id=manifest.get("session_id"),
                            session_display=manifest.get("session_display"))
    ev = evaluate_containment(tl, kill_spans_ms=kills, windows_ms=windows)

    def _clock(ms: float) -> str:
        return _dt.datetime.fromtimestamp(ms / 1000.0).strftime("%H:%M:%S")

    sep = "-" * 64
    print(f"\n{sep}\n  Match-state timeline -- {tl.session_display}\n{sep}")
    print(f"  signals  : {len(onsets)} R2 onsets | {len(windows)} windows | {len(kills)} kill clusters")
    print(f"  matches  : {tl.n_matches}")
    for s in tl.spans:
        dur = (s.end_ms - s.start_ms) / 1000.0
        print(f"    {s.state:<9} {_clock(s.start_ms)} -> {_clock(s.end_ms)}  ({dur:.0f}s)")
    for e in tl.events:
        print(f"    event: {e['event']} @ {_clock(e['ts_ms'])}")
    print(f"  contain  : anchors {ev['kills_contained']} | windows {ev['windows_contained']} "
          f"| {'OK' if ev['ok'] else 'MISS'}")
    for s0, s1 in sightings:
        st = tl.state_at((s0 + s1) / 2)
        tag = "expected (post-match screen)" if st == "LOBBY" else "in-match single read"
        print(f"  sighting : size-1 handle read @ {_clock(s0)} -> state {st} [{tag}]")
    for n in tl.notes:
        print(f"  note: {n}")

    out = args.out or os.path.join("audits", f"match_state_{tl.session_display}.json")
    doc = tl.to_dict()
    doc["containment"] = {k: v for k, v in ev.items() if k != "missed_kills" or v}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
    print(f"  written  : {out}\n{sep}\n")
    return 0 if ev["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

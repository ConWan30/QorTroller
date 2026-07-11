#!/usr/bin/env python3
"""SESSION CLOSE REPORT -- play, stop, one command, full evidence package.

The composition capstone: every verifier/builder shipped this arc, run in one pass over
one session, with per-match slicing. Nothing here computes new evidence -- it composes
the pure cores (one implementation each, already tested) and reports honestly:

  1. PoSP offline verification (posp_verifier, 7 checks)
  2. Match-state timeline (detect_match_state; K>=2 anchors per F-LUMEN-2)
  3. Deferred attestation -- session-level AND per-match (slice_scan_by_spans)
  4. Perception root (roll_perception_root) vs what the PoSP carried
  5. Temporal beacon reference (A3-b field) + freshness note (KC-A3b-1)

Every step fail-open: a missing input is a reported gap, never a crash, never a guess.
Output: audits/session_report_{display}.md + .json. Read-only; zero rig; zero chain.

Usage (typical, after daemon stop):
    python scripts/session_close_report.py \
        --archive retina_kf_archive/<display> \
        --db <session bridge db> \
        [--scan audits/<v2 scan>.json | --run-scan]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import glob
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "scripts"))

from l9_presence.kas_deferred import build_deferred_record, slice_scan_by_spans  # noqa: E402
from l9_presence.match_state import IN_MATCH, detect_match_state, evaluate_containment  # noqa: E402
from l9_presence.posp_verifier import verify_posp_record  # noqa: E402

from detect_match_state import _kill_spans, _load_onsets, _load_windows, _session_span_ms  # noqa: E402
from lumen4a_perception_root import roll_perception_root  # noqa: E402


def _clock(ms) -> str:
    return _dt.datetime.fromtimestamp(float(ms) / 1000.0).strftime("%H:%M:%S")


def _find_audit(prefix: str, label: str):
    hits = sorted(glob.glob(os.path.join(_REPO, "audits", f"{prefix}_{label}_*.json")))
    return hits[-1] if hits else None


def main() -> int:
    ap = argparse.ArgumentParser(description="One-command session evidence report")
    ap.add_argument("--archive", required=True)
    ap.add_argument("--db", default=None, help="session bridge DB (perception root)")
    ap.add_argument("--scan", default=None, help="existing v2 scan JSON")
    ap.add_argument("--run-scan", action="store_true", help="run Instrument-A scan now (~1s/crop)")
    ap.add_argument("--hid-events", default="retina_hid_events.jsonl")
    ap.add_argument("--composites", default="retina_kf_composite.jsonl")
    args = ap.parse_args()

    gaps: list = []
    manifest = json.load(open(os.path.join(args.archive, "manifest.json"), encoding="utf-8"))
    display = manifest.get("session_display")
    label = manifest.get("label") or display
    span = _session_span_ms(manifest)

    # --- artifacts ---
    kas_path = _find_audit("kas_record", label)
    posp_path = _find_audit("posp_record", label)
    kas = json.load(open(kas_path, encoding="utf-8")) if kas_path else None
    posp = json.load(open(posp_path, encoding="utf-8")) if posp_path else None
    if not kas:
        gaps.append("no KAS record found (run daemon stop with --kas)")
    if not posp:
        gaps.append("no PoSP record found")

    # --- 1. PoSP verification ---
    posp_verify = verify_posp_record(posp) if posp else None

    # --- scan ---
    scan = None
    if args.scan and os.path.isfile(args.scan):
        doc = json.load(open(args.scan, encoding="utf-8"))
        arch_norm = args.archive.replace("\\", "/").rstrip("/")
        scan = next((r for r in (doc.get("results") or [doc])
                     if str(r.get("archive", "")).replace("\\", "/").rstrip("/") == arch_norm),
                    None)
    elif args.run_scan:
        from rp_ocr_precision_scan import scan_archive
        scan = scan_archive(args.archive)
    if scan is None:
        gaps.append("no v2 scan (pass --scan or --run-scan) -- deferred tier + kill "
                    "anchors unavailable")

    # --- 2. match-state timeline ---
    onsets = _load_onsets(args.hid_events, span)
    windows = _load_windows(args.composites, span)
    anchors, sightings = _kill_spans(scan) if scan else ([], [])
    timeline = detect_match_state(session_span_ms=span, onsets_ms=onsets,
                                  windows_ms=windows, kill_spans_ms=anchors,
                                  session_id=manifest.get("session_id"),
                                  session_display=display)
    containment = evaluate_containment(timeline, kill_spans_ms=anchors, windows_ms=windows)

    # --- 3. deferred attestation: session + per-match ---
    deferred = per_match = None
    if scan and kas:
        deferred = build_deferred_record(scan=scan, manifest=manifest,
                                         windows=windows, kas_record=kas)
        match_spans = [(s.start_ms, s.end_ms) for s in timeline.spans if s.state == IN_MATCH]
        per_match = []
        for i, part in enumerate(slice_scan_by_spans(scan, match_spans)):
            if part["span_ms"] is None:
                n_left = len(part["scan"]["clusters"])
                if n_left:
                    per_match.append({"match": None, "note":
                                      f"{n_left} cluster(s) outside every match "
                                      "(sightings/pre-post content -- not attested)"})
                continue
            w_sub = [w for w in windows if part["span_ms"][0] <= w[0] <= part["span_ms"][1]]
            rec = build_deferred_record(scan=part["scan"], manifest=manifest,
                                        windows=w_sub, kas_record=kas)
            per_match.append({"match": i + 1,
                              "span": [_clock(part["span_ms"][0]), _clock(part["span_ms"][1])],
                              "verdict": rec.verdict,
                              "deferred_authored": rec.deferred_authored,
                              "deferred_observed": rec.deferred_observed})

    # --- 4. perception root ---
    perception = None
    if args.db:
        root, stats = roll_perception_root(args.db, span[0] / 1000.0 - 120,
                                           span[1] / 1000.0 + 120)
        carried = ((posp or {}).get("events_roots") or {}).get("retina_perception_root")
        perception = {"root": root, "n_events": stats.get("n_events"),
                      "posp_carried": carried,
                      "match": (root == carried) if (root and carried) else None}
    else:
        gaps.append("no --db -- perception root not recomputed")

    # --- 5. beacon ref ---
    beacon = (posp or {}).get("temporal_beacon")

    # --- report ---
    lines = [f"# Session Report -- {display}", ""]
    lines.append(f"- session_id: `{manifest.get('session_id')}`")
    lines.append(f"- archive: {manifest.get('count')} crops, manifest-committed")
    if kas:
        lines.append(f"- KAS: **{kas.get('verdict')}** authored={kas.get('authored_kills')} "
                     f"(commit `{str(kas.get('commitment'))[:16]}...`)")
    if posp_verify:
        n_ok = sum(1 for c in posp_verify.checks if c.passed)
        lines.append(f"- PoSP: **{posp_verify.overall}** ({n_ok}/{len(posp_verify.checks)} checks)")
    lines.append(f"- match-state: {timeline.n_matches} match(es); containment "
                 f"anchors {containment['kills_contained']} windows "
                 f"{containment['windows_contained']}")
    for s in timeline.spans:
        lines.append(f"    - {s.state} {_clock(s.start_ms)} -> {_clock(s.end_ms)}")
    if deferred:
        lines.append(f"- deferred (session): **{deferred.verdict}** "
                     f"authored={deferred.deferred_authored} observed={deferred.deferred_observed}")
    for m in per_match or []:
        if m.get("match"):
            lines.append(f"    - match {m['match']} {m['span'][0]}-{m['span'][1]}: "
                         f"{m['verdict']} authored={m['deferred_authored']}")
        else:
            lines.append(f"    - {m['note']}")
    if perception:
        lines.append(f"- perception root: `{str(perception['root'])[:16]}...` "
                     f"({perception['n_events']} events; posp_carried="
                     f"{'MATCH' if perception['match'] else perception['posp_carried']})")
    if beacon:
        lines.append(f"- temporal beacon ref: block {beacon.get('block_number')} "
                     f"(freshness = keeper cadence, KC-A3b-1)")
    else:
        lines.append("- temporal beacon ref: none on record (pre-A3-b or fetch failed)")
    for g in gaps:
        lines.append(f"- GAP: {g}")
    lines.append("")
    lines.append("_Advisory report; composes tested cores; every gap stated, nothing guessed._")

    md = "\n".join(lines)
    out_md = os.path.join(_REPO, "audits", f"session_report_{display}.md")
    with open(out_md, "w", encoding="utf-8") as fh:
        fh.write(md + "\n")
    print(md)
    print(f"\nwritten -> {out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

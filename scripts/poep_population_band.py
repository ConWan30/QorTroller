#!/usr/bin/env python3
"""Pool per-operator POEP reaction latencies -> a population reaction-time band (candidate, ADVISORY).

Closes the analysis gap between the live capture runner and l9_presence.population_band. Reads the
PLAYER-LABELLED session files the desk runner writes (audits/poep_live_capture_{player}_*.json, schema
qortroller-poep-live-capture-v1), groups each file's per-challenge latency_ms by its `player` field, and
feeds l9_presence.population_band.estimate_population_band -> band + per-operator FRR + provisional flag.

Also accepts --ring-op LABEL:DIR (repeatable) to pool the UNLABELLED per-fire ring dumps
(qortroller-poep-ring-dump-v0) from a directory under LABEL, via the offline study's analyze_fire (so the
bridge ring-dump path, or the existing corpus, can be scored too).

HONEST: candidate/advisory — prints a band, GATES NOTHING; poep_enabled/L6B/L6_CHALLENGES stay False; the
band is PROVISIONAL until >= MIN_OPERATORS_FOR_POPULATION (2) operators each with >= MIN_SAMPLES_PER_OPERATOR
(20). The ~120ms anticipation floor it uses as the population sub-floor is a conservative UNCITED prior, not
a measured floor. No rig, no spend, no chain, no flag flip.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import statistics
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "l9_presence"))
sys.path.insert(0, os.path.join(_ROOT, "scripts"))
from population_band import (  # noqa: E402
    estimate_population_band, frr_for_band, MIN_OPERATORS_FOR_POPULATION, MIN_SAMPLES_PER_OPERATOR,
)
from poep_ring_coupling_study import analyze_fire  # noqa: E402


def _window(lats: list[float], min_ms: float | None, max_ms: float | None) -> list[float]:
    """Keep latencies inside the sane reaction window [min_ms, max_ms] (either bound optional). DISCLOSED
    by the caller — this drops no-reaction / slow-outlier fires (e.g. F-RIG27-8-inflated RP latencies)."""
    return [x for x in lats
            if (min_ms is None or x >= min_ms) and (max_ms is None or x <= max_ms)]


def latencies_from_live_files(paths: list[str]) -> dict[str, list[float]]:
    """Group per-challenge latency_ms by the `player` field of each labelled live-capture session file."""
    ops: dict[str, list[float]] = {}
    for p in paths:
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if d.get("schema") != "qortroller-poep-live-capture-v1":
            continue
        player = (d.get("player") or "UNKNOWN").strip() or "UNKNOWN"
        for rec in d.get("records", []):
            lat = rec.get("latency_ms")
            if isinstance(lat, (int, float)) and lat > 0.0:      # None/<=0 = no clean reflex -> drop honestly
                ops.setdefault(player, []).append(float(lat))
    return ops


def latencies_from_ring_dir(d: str) -> list[float]:
    """Pool the PLAUSIBLE per-fire point latency (lat_pt_ms) from a dir of qortroller-poep-ring-dump-v0 files."""
    lats: list[float] = []
    for fp in sorted(glob.glob(os.path.join(d, "*.json"))):
        try:
            rec = json.load(open(fp, encoding="utf-8"))
        except Exception:
            continue
        if rec.get("schema") != "qortroller-poep-ring-dump-v0":
            continue
        r = analyze_fire(rec)
        if r["plausible"] and r["lat_pt_ms"] and r["lat_pt_ms"] > 0.0:   # gold t0 + in-window reaction only
            lats.append(float(r["lat_pt_ms"]))
    return lats


def main() -> int:
    ap = argparse.ArgumentParser(description="POEP population reaction-time band (candidate, advisory)")
    ap.add_argument("--dir", default="audits",
                    help="dir holding poep_live_capture_*.json labelled session files (default: audits)")
    ap.add_argument("--ring-op", action="append", default=[], metavar="LABEL:DIR",
                    help="additionally pool ring dumps (qortroller-poep-ring-dump-v0) from DIR under LABEL "
                         "(repeatable). e.g. --ring-op op1:audits/poep_ring_dump")
    ap.add_argument("--players", default=None,
                    help="comma-separated operator labels to INCLUDE from the live files (default: all found). "
                         "Scope to your 2 real operators so old/ambiguous labels don't pollute the band.")
    ap.add_argument("--min-ms", type=float, default=None,
                    help="drop reactions below this (no-reaction / spurious-fast); disclosed in output")
    ap.add_argument("--max-ms", type=float, default=None,
                    help="drop reactions above this (no-reaction / F-RIG27-8-inflated RP outliers); disclosed")
    ap.add_argument("--score-band", default=None, metavar="LO,HI",
                    help="HELD-OUT MODE: instead of FITTING a band, score the loaded captures against a FROZEN "
                         "band LO,HI (e.g. 202,410). Reports held-out FRR = fraction of a FRESH capture's "
                         "reactions OUTSIDE the frozen band -> the real generalization test (not in-sample fit). "
                         "Use with --players <new_label> pointing at a capture NOT used to fit the band.")
    args = ap.parse_args()

    ops = latencies_from_live_files(sorted(glob.glob(os.path.join(args.dir, "poep_live_capture_*.json"))))
    if args.players:
        keep = {p.strip() for p in args.players.split(",") if p.strip()}
        ops = {op: s for op, s in ops.items() if op in keep}
    for spec in args.ring_op:
        if ":" not in spec:
            print(f"  bad --ring-op '{spec}' (want LABEL:DIR)"); return 2
        label, d = spec.split(":", 1)
        ops[label.strip() or "UNKNOWN"] = latencies_from_ring_dir(d)

    windowed = (args.min_ms is not None) or (args.max_ms is not None)
    if windowed:
        ops = {op: _window(s, args.min_ms, args.max_ms) for op, s in ops.items()}
    ops = {op: s for op, s in ops.items() if s}
    if not ops:
        print(f"no reaction samples found (looked for {args.dir}/poep_live_capture_*.json + any --ring-op dirs"
              + (" ; after the --min-ms/--max-ms window" if windowed else "") + ")")
        return 2

    print("=== QorTroller POEP population reaction-time band (candidate; advisory; gates nothing) ===")
    if windowed:
        print(f"  reaction window FILTER APPLIED: [{args.min_ms}, {args.max_ms}] ms "
              f"(dropped no-reaction / slow-outlier fires; disclosed)")
    for op, s in sorted(ops.items()):
        flag = "" if len(s) >= MIN_SAMPLES_PER_OPERATOR else f"  (< {MIN_SAMPLES_PER_OPERATOR} - thin)"
        print(f"  operator {op}: n={len(s)}  min={min(s):.0f} median={statistics.median(s):.0f} "
              f"max={max(s):.0f} ms{flag}")

    # HELD-OUT SCORING: score a FRESH capture against a FROZEN band (generalization test, NOT a re-fit).
    if args.score_band is not None:
        try:
            lo_s, hi_s = args.score_band.split(",")
            lo, hi = float(lo_s), float(hi_s)
        except Exception:
            print(f"  bad --score-band '{args.score_band}' (want LO,HI e.g. 202,410)"); return 2
        print(f"\n  === HELD-OUT SCORING against the FROZEN band ({lo:.0f}, {hi:.0f}] ms ===")
        print("  held-out FRR = fraction of THIS (fresh, not-used-to-fit) capture OUTSIDE the frozen band.")
        for op, s in sorted(ops.items()):
            frr = frr_for_band(s, lo, hi)
            n_in = sum(1 for x in s if lo <= x <= hi)
            below = sum(1 for x in s if x < lo)
            above = sum(1 for x in s if x > hi)
            print(f"  operator {op}: n={len(s)}  in-band={n_in}/{len(s)}  held-out FRR={frr}  "
                  f"(below={below} above={above})")
        print("  NOTE: this is the real generalization test — a low held-out FRR means the frozen band")
        print("  captures a fresh capture well; a high one means the band doesn't generalize (widen/recapture).")
        print("  candidate/advisory; gates nothing; poep_enabled/L6B/L6_CHALLENGES stay False.")
        return 0

    r = estimate_population_band(ops)
    print(f"\n  operators: {r['n_operators']} (need >= {MIN_OPERATORS_FOR_POPULATION}) | "
          f"total samples: {r['n_samples']}")
    print("  !! 'operators' = distinct LABELS, NOT verified distinct people. This is a POPULATION band ONLY")
    print("     if these labels are genuinely different humans. Same person under 2 labels is NOT a population.")
    print(f"  band: ({r['band_lo_ms']}, {r['band_hi_ms']}] ms   anticipation sub-floor: "
          f"{r['anticipation_floor_ms']:.0f}ms")
    print(f"  degenerate_band: {r['degenerate_band']}   PROVISIONAL: {r['provisional']}   "
          f"operators_needed: {r['operators_needed']}")
    print(f"  per-operator FRR (fraction outside the band): {r['per_operator_frr']}")
    print(f"  worst-case FAR  population-band: {r['worst_case_far_population_band']}  |  "
          f"single-operator-band: {r['worst_case_far_single_operator_band']}")
    print(f"\n  {r['confidence_note']}")
    print(f"  FAR: {r['far_note']}")
    print(f"  {r['gate_note']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

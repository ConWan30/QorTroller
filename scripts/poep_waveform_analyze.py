"""POEP rung-2 analyzer — run P-WAVE-0 shape features on REAL captured reflex waveforms.

This is the payoff of a rig session. `poep_live_capture.py` now stores the raw DC-removed reflex curve
per challenge; this tool reads a capture audit JSON and answers the single load-bearing empirical
question P-WAVE-0 flagged (grok round-22 caveat 2):

    Do real grip reflexes SETTLE-TO-PLATEAU (tail_slope ~ 0), or RETURN-TO-BASELINE (tail_slope < 0)?

If they settle, the P-WAVE-0 shape gate's triangle separation stands (conditional PASS confirmed on real
data). If they return-to-baseline, the `tail_slope` threshold must be DROPPED and shape is even weaker
than P-WAVE-0 suggested — an honest negative that redirects the FLIP-A ladder. Either way the answer is
data, not assumption.

It also reports what fraction of the operator's real reflexes pass the human-shape gate (a real-data FRR,
which the synthetic FRR 0.027 could not honestly stand in for) and verifies each stored waveform against
its `waveform_commitment` (integrity — the curve was not swapped).

poep_enabled stays False. This is analysis, not a flip. Aggregates are safe to bank; the per-reflex
curves are operator biometric and live only in the gitignored capture JSON.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from l9_presence.poep_live_verify import waveform_commitment, waveform_digest  # noqa: E402
from l9_presence.poep_waveform_shape import (  # noqa: E402
    human_shape_gate,
    waveform_shape_features,
)

# PHYSICALLY-anchored settle criteria (grok round-23 decircularization) -- NOT the gate's TAIL_SLOPE_MIN.
# tail_slope is normalized (fraction of curve amplitude per sample). These describe the RELAXATION physics,
# they are not reused from the synthetic-tuned shape gate.
FLAT_EPS = 0.010            # |tail_slope| < this  => flat within sensor noise (<1% amplitude/sample) => SETTLED
RETURN_EPS = 0.020         # tail_slope <= -this   => clearly relaxing toward baseline => RETURNING
PEAK_TAIL_FRAC = 0.75      # peak in the last quarter => no settled tail observed => INDETERMINATE (window short)


def _percentile(xs_sorted: list[float], p: float):
    if not xs_sorted:
        return None
    k = (len(xs_sorted) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(xs_sorted) - 1)
    return round(xs_sorted[lo] + (xs_sorted[hi] - xs_sorted[lo]) * (k - lo), 4)


def _classify_tail(f: dict) -> str:
    """Physical classification of ONE reflex's relaxation (no gate constant)."""
    if f["peak_frac"] > PEAK_TAIL_FRAC or f["tail_slope"] > FLAT_EPS:
        return "indeterminate"          # peak in last quarter or tail still rising -> no settled tail seen
    if f["tail_slope"] >= -FLAT_EPS:
        return "settled"                # flat within noise
    if f["tail_slope"] <= -RETURN_EPS:
        return "returning"              # clearly descending toward baseline
    return "slight_drift"               # between: ambiguous, operator judges from the distribution


def analyze_waveform_capture(audit: dict) -> dict:
    """Pure: report the tail_slope DISTRIBUTION + a physically-anchored settle/return classification.

    grok round-23: this deliberately does NOT emit a single boolean keyed to the shape gate's threshold
    (that would re-inject the very assumption the rig session is meant to test). It reports the data --
    distribution + per-curve physical class + counts -- and the OPERATOR reads the answer. The gate
    pass-rate is kept as a SEPARATELY-LABELED FRR proxy that intentionally uses gate constants.
    """
    records = [r for r in audit.get("records", []) if r.get("waveform")]
    per = []
    tails = []
    counts = {"settled": 0, "returning": 0, "slight_drift": 0, "indeterminate": 0}
    n_pass_gate = 0
    n_integrity_ok = 0
    for r in records:
        wf = r["waveform"]
        f = waveform_shape_features(wf)
        tails.append(f["tail_slope"])
        klass = _classify_tail(f)
        counts[klass] += 1
        passed = human_shape_gate(f)
        if passed:
            n_pass_gate += 1
        integrity = None
        if r.get("waveform_digest") is not None:
            wd = waveform_digest(wf)
            integrity = (wd == r["waveform_digest"])
            if integrity and r.get("waveform_commitment") is not None:
                wc = waveform_commitment(nonce=r["nonce"], wave_digest=wd,
                                         t_challenge_ns=r["t_challenge_ns"])
                integrity = (wc == r["waveform_commitment"])
            if integrity:
                n_integrity_ok += 1
        per.append({
            "challenge_index": r.get("challenge_index"),
            "tail_slope": round(f["tail_slope"], 4),
            "peak_frac": round(f["peak_frac"], 3),
            "overshoot_ratio": round(f["overshoot_ratio"], 3),
            "rise_samples": f["rise_samples"],
            "tail_class": klass,
            "passes_human_shape_gate": passed,        # FRR-proxy component (uses GATE constants, labeled)
            "waveform_integrity_ok": integrity,
        })

    n = len(records)
    tails_sorted = sorted(tails)
    mean_tail = (sum(tails) / n) if n else None
    determinate = counts["settled"] + counts["returning"] + counts["slight_drift"]
    return {
        "n_waveforms": n,
        "tail_slope_distribution": {                  # THE data the operator reads (not a baked boolean)
            "mean": (round(mean_tail, 4) if n else None),
            "median": _percentile(tails_sorted, 0.5),
            "p10": _percentile(tails_sorted, 0.10),
            "p90": _percentile(tails_sorted, 0.90),
            "min": (round(min(tails), 4) if n else None),
            "max": (round(max(tails), 4) if n else None),
        },
        "physical_settle_criteria": {"flat_eps": FLAT_EPS, "return_eps": RETURN_EPS,
                                     "peak_tail_frac": PEAK_TAIL_FRAC,
                                     "note": "normalized amplitude/sample; NOT the shape-gate TAIL_SLOPE_MIN"},
        "tail_class_counts": counts,
        "real_data_shape_gate_pass_rate": (round(n_pass_gate / n, 3) if n else None),
        "shape_gate_pass_rate_label": "FRR-proxy — intentionally uses shape-gate constants, NOT a settle decider",
        "waveform_integrity_ok": (n_integrity_ok == n) if n else None,
        "verdict": (
            "no waveforms in capture" if n == 0 else
            f"tail median {_percentile(tails_sorted, 0.5)} | settled={counts['settled']} "
            f"returning={counts['returning']} slight_drift={counts['slight_drift']} "
            f"indeterminate={counts['indeterminate']} of {n}. "
            "OPERATOR reads settle-vs-baseline from the distribution + counts; "
            "indeterminate = window too short / still rising (needs longer capture or onset-alignment). "
            "No single boolean — the gate threshold is NOT reused as the science decider."
        ),
        "determinate_n": determinate,
        "per_reflex": per,
        "note": "poep_enabled stays False. Aggregates bankable; per-reflex tail_slopes are derived from "
                "operator-biometric waveforms (gitignored source).",
    }


def main() -> int:  # pragma: no cover
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("capture_json", help="path to a poep_live_capture_*.json (rung-2 capture)")
    ap.add_argument("--full", action="store_true", help="print per-reflex detail (biometric-derived)")
    args = ap.parse_args()

    audit = json.loads(Path(args.capture_json).read_text(encoding="utf-8"))
    rep = analyze_waveform_capture(audit)

    d = rep["tail_slope_distribution"]
    c = rep["tail_class_counts"]
    print("=" * 66)
    print("  POEP RUNG-2 — real reflex waveform shape analysis")
    print("=" * 66)
    print(f"  waveforms:            {rep['n_waveforms']}  (determinate {rep['determinate_n']})")
    print(f"  tail_slope dist:      median={d['median']} mean={d['mean']} "
          f"p10={d['p10']} p90={d['p90']} min={d['min']} max={d['max']}")
    print(f"  tail classes:         settled={c['settled']} returning={c['returning']} "
          f"slight_drift={c['slight_drift']} indeterminate={c['indeterminate']}")
    print(f"  shape-gate pass rate: {rep['real_data_shape_gate_pass_rate']}  ({rep['shape_gate_pass_rate_label']})")
    print(f"  waveform integrity:   {rep['waveform_integrity_ok']}")
    print("-" * 66)
    print(f"  READ: {rep['verdict']}")
    print("=" * 66)
    if args.full:
        for p in rep["per_reflex"]:
            print(f"  #{p['challenge_index']:>2} tail={p['tail_slope']:+.4f} peak_frac={p['peak_frac']:.2f} "
                  f"class={p['tail_class']:<13} gate={'PASS' if p['passes_human_shape_gate'] else 'fail'} "
                  f"integrity={p['waveform_integrity_ok']}")
    print("  poep_enabled stays False — this is analysis, not a flip. Operator reads the distribution.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

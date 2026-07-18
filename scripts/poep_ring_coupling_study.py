#!/usr/bin/env python3
"""(ii) R2-onset Increment-0 — OFFLINE actuator-coupling study.

Reads the nonce-bound POEP ring dumps written by DualShockTransport._dump_poep_ring_series
(schema qortroller-poep-ring-dump-v0, under audits/poep_ring_dump/, gated on POEP_RING_DUMP_ENABLED)
and answers the grok r2onset-01 go/no-go question WITHOUT touching the bridge, the corpus, or any flag:

  Does the operator's R2 reaction (in the ACTUATOR-BLIND post window) reliably deviate more than the
  challenge's own commanded-force window AND more than noise — so the reaction can be timed on the R2
  analog channel with the (proven-live) device clock?

Per-fire, using the device clock (offset 28 ticks) anchored at probe_device_ts:
  * pre_r2_mean        — mean R2 over the pre-window
  * actuator window    — t_rel_ms in [0, hold_ms + MECH_SETTLE_MS]  (the commanded tug + settle)
  * post window        — t_rel_ms >  hold_ms + MECH_SETTLE_MS       (actuator-blind; where a human onset must live)
  * max|dR2| in each window; naive "first |dR2|>DELTA" false-onset check (lands in actuator window?)
  * gated onset        — first POST-window frame with |dR2|>DELTA sustained N_SUSTAIN frames -> latency_ms
  * T_mech estimate    — when R2 re-quiets to within QUIET_BAND of pre_mean after the tug

THIS IS A MEASUREMENT TOOL, NOT A DETECTOR. It never writes to the bridge/corpus and makes no presence
claim. It only reports whether the R2-onset channel is viable, so the operator can greenlight (or kill)
the full ring detector (Increment-1).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import statistics
from typing import Any

DELTA = 5          # min |R2 - pre_mean| (0..255) to count as movement (grok: delta~=5)
N_SUSTAIN = 2      # consecutive frames required (anti single-frame noise)
MECH_SETTLE_MS = 30.0   # actuator settle margin after the commanded hold (empirical; refine from T_mech)
QUIET_BAND = 4     # |R2 - pre_mean| within this = "quiet" (for T_mech re-quiet detection)


def _t_rel_ms(frame: dict, probe_tick: float, tpms: float) -> float | None:
    """Device-clock ms since the probe, using offset-28 ticks. None if this frame has no device_ts."""
    dt = frame.get("device_ts")
    if not dt or not probe_tick or tpms <= 0:
        return None
    span = (float(dt) - float(probe_tick)) % (1 << 32)   # wrap-safe uint32
    return span / tpms


def analyze_fire(rec: dict[str, Any]) -> dict[str, Any]:
    tpms = float(rec.get("device_ticks_per_ms") or 3000.0)
    probe_tick = float(rec.get("probe_device_ts") or 0.0)
    hold_ms = float(rec.get("probe_hold_ms") or 15.0)
    actuator_end_ms = hold_ms + MECH_SETTLE_MS
    pre = rec.get("pre_series") or []
    post = rec.get("post_series") or []

    pre_r2 = [float(f.get("r2", 0) or 0) for f in pre if isinstance(f, dict)]
    pre_mean = statistics.fmean(pre_r2) if pre_r2 else 0.0

    act_dev, post_dev, timeline = [], [], []
    for f in post:
        if not isinstance(f, dict):
            continue
        tr = _t_rel_ms(f, probe_tick, tpms)
        d = abs(float(f.get("r2", 0) or 0) - pre_mean)
        timeline.append((tr, d, float(f.get("r2", 0) or 0)))
        if tr is None:
            continue
        (act_dev if tr <= actuator_end_ms else post_dev).append((tr, d))

    max_act = max((d for _, d in act_dev), default=0.0)
    max_post = max((d for _, d in post_dev), default=0.0)

    # naive detector: first |dR2|>DELTA anywhere post-fire -> does it fall in the actuator window?
    naive_onset_ms, naive_in_actuator = None, None
    for tr, d in ((t, d) for t, d, _ in timeline if t is not None):
        if d > DELTA:
            naive_onset_ms = tr
            naive_in_actuator = tr <= actuator_end_ms
            break

    # gated detector: first POST-window frame with |dR2|>DELTA sustained N_SUSTAIN frames
    gated_onset_ms, run = None, 0
    for tr, d, _ in timeline:
        if tr is None or tr <= actuator_end_ms:
            run = 0
            continue
        run = run + 1 if d > DELTA else 0
        if run >= N_SUSTAIN:
            gated_onset_ms = tr   # first frame of the sustained run's END; conservative
            break

    # T_mech: after the tug, when does R2 re-quiet to within QUIET_BAND of pre_mean?
    t_mech_ms = None
    for tr, d, _ in timeline:
        if tr is not None and tr > hold_ms and d <= QUIET_BAND:
            t_mech_ms = tr
            break

    n_dev = sum(1 for t, _, _ in timeline if t is not None)
    return {
        "nonce": rec.get("nonce"),
        "force": rec.get("probe_r2_force"),
        "mode": rec.get("probe_mode"),
        "hold_ms": hold_ms,
        "pre_mean_r2": round(pre_mean, 1),
        "n_pre": len(pre), "n_post": len(post), "n_post_with_dev_ts": n_dev,
        "max_dR2_actuator": round(max_act, 1),
        "max_dR2_post": round(max_post, 1),
        "naive_onset_ms": None if naive_onset_ms is None else round(naive_onset_ms, 1),
        "naive_in_actuator": naive_in_actuator,
        "gated_onset_ms": None if gated_onset_ms is None else round(gated_onset_ms, 1),
        "t_mech_ms": None if t_mech_ms is None else round(t_mech_ms, 1),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="(ii) R2-onset offline actuator-coupling study")
    ap.add_argument("--dir", default=os.path.join("audits", "poep_ring_dump"),
                    help="directory of qortroller-poep-ring-dump-v0 json files")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.dir, "*.json")))
    if not files:
        print(f"no ring dumps in {args.dir} — capture a rig session with POEP_RING_DUMP_ENABLED=1 first")
        return 2

    rows = []
    for fp in files:
        try:
            rec = json.load(open(fp, encoding="utf-8"))
        except Exception as exc:
            print(f"  skip {os.path.basename(fp)}: {exc}")
            continue
        if rec.get("schema") != "qortroller-poep-ring-dump-v0":
            continue
        rows.append(analyze_fire(rec))

    if not rows:
        print("no valid v0 dumps found")
        return 2

    print(f"=== POEP R2-onset coupling study — {len(rows)} fire(s) from {args.dir} ===")
    hdr = ("nonce", "force", "mode", "pre_r2", "maxdR2_act", "maxdR2_post",
           "naive_ms", "naive_in_act", "gated_ms", "t_mech_ms")
    print("  " + " | ".join(f"{h:>11}" for h in hdr))
    for r in rows:
        print("  " + " | ".join(f"{str(v):>11}" for v in (
            str(r["nonce"])[:11], r["force"], r["mode"], r["pre_mean_r2"],
            r["max_dR2_actuator"], r["max_dR2_post"], r["naive_onset_ms"],
            r["naive_in_actuator"], r["gated_onset_ms"], r["t_mech_ms"])))

    # aggregate go/no-go
    post_moves = [r["max_dR2_post"] for r in rows]
    act_moves = [r["max_dR2_actuator"] for r in rows]
    n_gated = sum(1 for r in rows if r["gated_onset_ms"] is not None)
    n_naive_false = sum(1 for r in rows if r["naive_in_actuator"] is True)
    n_dev = sum(1 for r in rows if r["n_post_with_dev_ts"] > 0)
    print("\n=== GO/NO-GO ===")
    print(f"  device_ts present on post frames: {n_dev}/{len(rows)} fires")
    print(f"  median max|dR2| post-window : {statistics.median(post_moves):.1f}")
    print(f"  median max|dR2| actuator-win: {statistics.median(act_moves):.1f}")
    print(f"  gated onset found (post-win): {n_gated}/{len(rows)} fires")
    print(f"  naive-detector FALSE onset (in actuator window): {n_naive_false}/{len(rows)} fires")
    go = (n_dev == len(rows) and statistics.median(post_moves) > DELTA and n_gated >= max(1, len(rows) // 2))
    print(f"\n  VERDICT: {'GREENLIGHT ring onset detector' if go else 'NO-GO / insufficient — inspect above'}")
    print("  (this tool makes NO presence claim; it only measures channel viability.)")
    return 0 if go else 1


if __name__ == "__main__":
    raise SystemExit(main())

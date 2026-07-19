#!/usr/bin/env python3
"""(ii) R2-onset — OFFLINE actuator-coupling study (F-R2ONSET-1 honest-t0 rework).

Reads the nonce-bound POEP ring dumps (schema qortroller-poep-ring-dump-v0, audits/poep_ring_dump/,
written under POEP_RING_DUMP_ENABLED) and answers the grok r2onset-02 go/no-go WITHOUT touching the
bridge, corpus, or any flag.

F-R2ONSET-1 (rig-4d): the device-latency reference `probe_device_ts` = the last PRE-frame's device_ts is
STALE — ~972 ms before the fire when spaced, and frozen entirely under rapid fire (20 s artifact onsets).
This rework recovers the true fire instant t0 in device-clock space and reports its uncertainty honestly
(grok r2onset-02 co-design):

  t0 = mono-EXTRAPOLATED, gap-CLAMPED device tick.
    From the last pre-frame anchor (a_mono=t_mono, a_dev=device_ts), the fire is (probe_ts_mono - a_mono)
    seconds later; the silicon counter runs at a KNOWN ~3 MHz, so t0 = a_dev + elapsed * tpms. Clamp into
    [a_dev, post0_dev] (the fire lies between the last pre-frame and the first post-frame). We do NOT
    regress t_mono vs device_ts across the burst gap — that map is invalid under RP (grok rail #6).
  Uncertainty (grok D): report the FULL interval — lat_hi uses t0=a_dev (earliest), lat_lo uses t0=post0
    (latest), lat_pt uses the extrapolation. reference_gap_ms = the pre->post0 device gap (the burst floor).
  Never claim precision finer than the reference gap without a live read-at-fire (C, the next increment).

Fallback: dumps lacking probe_ts_mono / frame t_mono resolve t0 = a_dev with method "stale_pre" (honest).

This is a MEASUREMENT TOOL, NOT a detector. It writes nothing to the bridge/corpus and makes NO presence
claim. It reports whether the R2-onset channel is viable UNDER AN HONEST t0, so the operator can decide:
detector (Increment-1) vs live read-at-fire (C) vs "voluntary-not-reflex".
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import statistics
from typing import Any

DELTA = 5           # min |R2 - pre_mean| (0..255) to count as movement
N_SUSTAIN = 2       # consecutive frames required (anti single-frame noise)
MECH_SETTLE_MS = 30.0    # actuator settle margin after the commanded hold (relative to t0/fire)
QUIET_BAND = 4      # |R2 - pre_mean| within this = "quiet" (for T_mech re-quiet)
GATED_CEIL_MS = 2000.0   # study plausibility ceiling on gated onset (NOT the human band; kills 20s artifacts)
GAP_REPORT_MS = 1500.0   # reference-gap ceiling to flag (spaced ~972 stays visible; rapid-fire fails)
_U32 = 1 << 32


def _wrap(x: float) -> float:
    return x % _U32


def _last_pre_anchor(pre: list[dict]) -> dict | None:
    for f in reversed(pre or []):
        if isinstance(f, dict) and f.get("device_ts"):
            return f
    return None


def _first_post0(post: list[dict]) -> dict | None:
    for f in post or []:
        if isinstance(f, dict) and f.get("device_ts"):
            return f
    return None


def _resolve_t0(rec: dict, anchor: dict, tpms: float, post0_rel: float | None,
                last_post_rel: float | None, drain_delta_rel: float) -> tuple[float, str, float, float]:
    """Return (t0_rel, method, earliest_rel, latest_rel) — all relative to anchor.device_ts (wrap-safe).

    The uncertainty interval is [earliest_rel, latest_rel] (earliest -> largest latency lat_hi, latest ->
    smallest lat_lo). Precedence:
      1. read_at_fire (C): the ~1 kHz drain captured the fire-instant tick. Gold t0 — and note the drain is
         FRESHER than post0 under RP (post0 is a stale buffered sample), so t0_read can exceed post0. The
         uncertainty is ONE drain interval (the read could be that stale), NOT the pre->post frame gap:
         t0 in [t0_read - drain_delta, t0_read] -> a TIGHT interval.
      2. mono_extrap: extrapolate the monotonic fire into device space from the anchor (known 3 MHz rate).
         t0 in [anchor, post0] -> the full frame-gap interval.
      3. stale_pre: t0 = anchor (honest fallback when the monotonic anchor is absent).
    """
    a_dev = float(anchor["device_ts"])
    t0_read = rec.get("t0_read_device_ts")
    if t0_read and last_post_rel is not None:
        t0r_rel = _wrap(float(t0_read) - a_dev)
        skew = 5.0 * tpms
        # accept if the gold tick lands after the (stale) anchor and within the captured window
        if -skew <= t0r_rel <= last_post_rel + skew:
            t0_rel = max(t0r_rel, 0.0)
            earliest = max(t0_rel - max(drain_delta_rel, 0.0), 0.0)   # read could be one drain interval stale
            return t0_rel, "read_at_fire", earliest, t0_rel
    probe_mono = rec.get("probe_ts_mono")
    a_mono = anchor.get("t_mono")
    if probe_mono is None or a_mono is None:
        return 0.0, "stale_pre", 0.0, (post0_rel if post0_rel is not None else 0.0)
    elapsed_ms = (float(probe_mono) - float(a_mono)) * 1000.0
    t0_rel = elapsed_ms * tpms
    method = "mono_extrap"
    if t0_rel < 0.0:
        t0_rel, method = 0.0, "extrap_clamped"
    elif post0_rel is not None and t0_rel > post0_rel:
        t0_rel, method = post0_rel, "extrap_clamped"
    return t0_rel, method, 0.0, (post0_rel if post0_rel is not None else t0_rel)   # [anchor, post0]


def analyze_fire(rec: dict[str, Any]) -> dict[str, Any]:
    tpms = float(rec.get("device_ticks_per_ms") or 3000.0)
    hold_ms = float(rec.get("probe_hold_ms") or 15.0)
    act_end_ms = hold_ms + MECH_SETTLE_MS
    pre = rec.get("pre_series") or []
    post = rec.get("post_series") or []

    pre_r2 = [float(f.get("r2", 0) or 0) for f in pre if isinstance(f, dict)]
    pre_mean = statistics.fmean(pre_r2) if pre_r2 else 0.0

    anchor = _last_pre_anchor(pre)
    post0 = _first_post0(post)
    n_post_dev = sum(1 for f in post if isinstance(f, dict) and f.get("device_ts"))

    base: dict[str, Any] = {
        "nonce": rec.get("nonce"), "force": rec.get("probe_r2_force"), "mode": rec.get("probe_mode"),
        "hold_ms": hold_ms, "pre_mean_r2": round(pre_mean, 1),
        "n_pre": len(pre), "n_post": len(post), "n_post_with_dev_ts": n_post_dev,
    }
    if anchor is None:
        base.update({"t0_method": "no_anchor", "reference_gap_ms": None, "t0_legacy_delta_ms": None,
                     "max_dR2_actuator": 0.0, "max_dR2_post": 0.0, "naive_onset_ms": None,
                     "naive_in_actuator": None, "gated_onset_ms": None, "t_mech_ms": None,
                     "lat_lo_ms": None, "lat_pt_ms": None, "lat_hi_ms": None, "plausible": False})
        return base

    a_dev = float(anchor["device_ts"])
    post_devs = [_wrap(float(f["device_ts"]) - a_dev)
                 for f in post if isinstance(f, dict) and f.get("device_ts")]
    post0_rel = post_devs[0] if post_devs else None
    last_post_rel = post_devs[-1] if post_devs else None
    # drain interval = median consecutive post-frame device gap = the read-at-fire staleness bound
    _diffs = sorted(post_devs[i + 1] - post_devs[i] for i in range(len(post_devs) - 1)
                    if post_devs[i + 1] >= post_devs[i])
    drain_delta_rel = _diffs[len(_diffs) // 2] if _diffs else 0.0
    t0_rel, method, earliest_rel, latest_rel = _resolve_t0(
        rec, anchor, tpms, post0_rel, last_post_rel, drain_delta_rel)
    # reference_gap = t0 uncertainty = latest possible t0 minus earliest possible t0.
    # read_at_fire -> ONE drain interval (tight); mono/stale -> the full anchor->post0 frame gap (wide).
    reference_gap_ms = (latest_rel - earliest_rel) / tpms
    legacy_probe = rec.get("probe_device_ts")
    t0_legacy_delta_ms = None
    if legacy_probe:
        t0_legacy_delta_ms = round((t0_rel - _wrap(float(legacy_probe) - a_dev)) / tpms, 1)

    # per-post-frame timeline relative to the RECOVERED fire t0
    timeline = []  # (t_rel_ms, |dR2|, onset_rel_ticks)
    for f in post:
        if not isinstance(f, dict) or not f.get("device_ts"):
            continue
        rel = _wrap(float(f["device_ts"]) - a_dev)
        timeline.append(((rel - t0_rel) / tpms, abs(float(f.get("r2", 0) or 0) - pre_mean), rel))

    # windows are relative to the recovered fire t0; frames with t<0 are pre-fire (stale-buffered) -> excluded
    max_act = max((d for t, d, _ in timeline if 0.0 <= t <= act_end_ms), default=0.0)
    max_post = max((d for t, d, _ in timeline if t > act_end_ms), default=0.0)

    naive_ms, naive_in_act = None, None
    for t, d, _ in timeline:
        if t >= 0.0 and d > DELTA:
            naive_ms, naive_in_act = t, (t <= act_end_ms)
            break

    onset_rel, run = None, 0
    for t, d, rel in timeline:
        if t <= act_end_ms:
            run = 0
            continue
        run = run + 1 if d > DELTA else 0
        if run >= N_SUSTAIN:
            onset_rel = rel
            break

    t_mech_ms = None
    for t, d, _ in timeline:
        if t > hold_ms and d <= QUIET_BAND:
            t_mech_ms = round(t, 1)
            break

    lat_lo = lat_pt = lat_hi = None
    if onset_rel is not None:
        lat_hi = (onset_rel - earliest_rel) / tpms                   # t0 = earliest possible -> largest latency
        lat_pt = (onset_rel - t0_rel) / tpms                         # t0 = chosen (read_at_fire / extrap / stale)
        lat_lo = (onset_rel - latest_rel) / tpms                     # t0 = latest possible -> smallest latency

    plausible = bool(
        onset_rel is not None and lat_pt is not None and 0.0 < lat_pt <= GATED_CEIL_MS
        and reference_gap_ms is not None and reference_gap_ms <= GAP_REPORT_MS
        and n_post_dev > 0
    )
    base.update({
        "t0_method": method,
        "reference_gap_ms": None if reference_gap_ms is None else round(reference_gap_ms, 1),
        "t0_legacy_delta_ms": t0_legacy_delta_ms,
        "max_dR2_actuator": round(max_act, 1), "max_dR2_post": round(max_post, 1),
        "naive_onset_ms": None if naive_ms is None else round(naive_ms, 1),
        "naive_in_actuator": naive_in_act,
        "gated_onset_ms": None if lat_pt is None else round(lat_pt, 1),   # gated onset = the point latency
        "t_mech_ms": t_mech_ms,
        "lat_lo_ms": None if lat_lo is None else round(lat_lo, 1),
        "lat_pt_ms": None if lat_pt is None else round(lat_pt, 1),
        "lat_hi_ms": None if lat_hi is None else round(lat_hi, 1),
        "plausible": plausible,
    })
    return base


def main() -> int:
    ap = argparse.ArgumentParser(description="(ii) R2-onset offline study (honest-t0)")
    ap.add_argument("--dir", default=os.path.join("audits", "poep_ring_dump"))
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.dir, "*.json")))
    if not files:
        print(f"no ring dumps in {args.dir} — capture with POEP_RING_DUMP_ENABLED=1 first")
        return 2
    rows = []
    for fp in files:
        try:
            rec = json.load(open(fp, encoding="utf-8"))
        except Exception as exc:
            print(f"  skip {os.path.basename(fp)}: {exc}"); continue
        if rec.get("schema") == "qortroller-poep-ring-dump-v0":
            rows.append(analyze_fire(rec))
    if not rows:
        print("no valid v0 dumps"); return 2

    print(f"=== POEP R2-onset study (honest-t0) — {len(rows)} fire(s) from {args.dir} ===")
    hdr = ("nonce", "t0_method", "ref_gap", "maxdR2post", "lat_lo", "lat_pt", "lat_hi", "plausible")
    print("  " + " | ".join(f"{h:>10}" for h in hdr))
    for r in rows:
        print("  " + " | ".join(f"{str(v):>10}" for v in (
            str(r["nonce"])[:10], r["t0_method"], r["reference_gap_ms"], r["max_dR2_post"],
            r["lat_lo_ms"], r["lat_pt_ms"], r["lat_hi_ms"], r["plausible"])))

    plaus = [r for r in rows if r["plausible"]]
    post_moves = [r["max_dR2_post"] for r in rows]
    print("\n=== GO/NO-GO (honest-t0) ===")
    print(f"  plausible fires (t0 recovered, lat_pt in (0,{GATED_CEIL_MS:.0f}]ms, ref_gap<= {GAP_REPORT_MS:.0f}): {len(plaus)}/{len(rows)}")
    print(f"  median max|dR2| post-window: {statistics.median(post_moves):.1f} (channel carries the reaction)")
    if plaus:
        pts = [r["lat_pt_ms"] for r in plaus]
        gaps = [r["reference_gap_ms"] for r in plaus]
        n_raf = sum(1 for r in plaus if r["t0_method"] == "read_at_fire")
        print(f"  plausible lat_pt: min={min(pts):.0f} median={statistics.median(pts):.0f} max={max(pts):.0f} ms")
        print(f"  plausible ref_gap: median={statistics.median(gaps):.0f} ms  ({n_raf} read_at_fire)")
        if n_raf:
            print("  HONESTY: read_at_fire ref_gap is a typical-cadence PROXY (median frame gap), NOT a certified")
            print("  uncertainty bound - the drain's actual staleness at fire is UNMEASURED (needs a drain-wall")
            print("  age; next increment). Treat lat as band-scale, not +/-ref_gap metrology.")
    # GREENLIT = channel viable UNDER HONEST t0 (NOT 'band cleared'); require majority plausible + R2 moves
    go = (len(plaus) >= (len(rows) + 1) // 2 and statistics.median(post_moves) > DELTA)
    verdict = "CHANNEL VIABLE under honest t0" if go else "NO-GO / insufficient — inspect"
    print(f"\n  VERDICT: {verdict}")
    if plaus:
        med = statistics.median([r["lat_pt_ms"] for r in plaus])
        if med > 280:
            print(f"  NOTE: median plausible onset {med:.0f}ms >> 280ms band. If bounds are tight this is a")
            print("        VOLUNTARY-not-reflex channel (physiology/UX), a finding SEPARATE from F-R2ONSET-1.")
    print("  Reads the recovered device t0 + FULL [lo,pt,hi] bounds. Live read-at-fire (C) is the next")
    print("  increment for gold-standard precision. Makes NO presence claim.")
    return 0 if go else 1


if __name__ == "__main__":
    raise SystemExit(main())

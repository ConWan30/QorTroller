#!/usr/bin/env python
"""RP-config dual-L2 diagnostic analysis — find the Remote-Play-reliable L2 source.

2026-07-02 finding (docs/hid-timing-resolution-2026-07-01.md follow-up): during Remote Play the raw
interface-3 L2 at report offset 5 STICKS HIGH on release (113/113 crosscheck disagreements were raw=255 /
pyds=0), collapsing l2_ads holds to held_n=1. This script consumes the two dumps captured with
RETINA_ADS_RP_DIAG=true during a Remote-Play session —
  retina_rp_rawdump.jsonl : {wall_ms, hex}          (raw interface-3 reports, ~1kHz, from the hidapi thread)
  retina_rp_pyds.jsonl    : {wall_ms, pyds_l2_*}     (pydualsense L2 per consumption tick — the ground truth)
— and answers three questions so the next RP session can pick the correct source and calibrate:

  (1) WHICH raw byte offset tracks pydualsense L2 under RP? For every offset, correlate its per-report value
      against the pyds L2 state (held/released) in the same wall window. Offset 5 should show ~no separation
      (stuck); the offset that IS high-when-held / low-when-released is the RP-reliable L2 byte (if any).
  (2) Are the raw reports STALE (device timestamp @28 repeats -> reports not refreshing) or merely LAGGED
      (ts advances but content trails)? Distinguishes 'RP starves interface-3' from 'RP shifts the layout'.
  (3) Does ANY offset cleanly separate? If none, interface-3 is unusable under RP and the fix must pair the
      device timestamp with pydualsense's L2 value (or a different interface).

    python scripts/analyze_rp_l2_diag.py    # reads the two jsonl dumps in cwd
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _load(p):
    f = Path(p)
    if not f.exists():
        print("MISSING:", p, "— capture a Remote-Play session with RETINA_ADS_RP_DIAG=true first")
        return None
    return [json.loads(ln) for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]


def main() -> int:
    raw = _load("retina_rp_rawdump.jsonl")
    pyds = _load("retina_rp_pyds.jsonl")
    if not raw or not pyds:
        return 1
    B = [(r["wall_ms"], bytes.fromhex(r["hex"])) for r in raw]
    L = len(B[0][1])
    thr = 40
    print("raw reports=%d (%d bytes) | pyds ticks=%d" % (len(B), L, len(pyds)))

    # (2) staleness: does the device timestamp @28 advance every report, or repeat?
    ts = [b[28] | b[29] << 8 | b[30] << 16 | b[31] << 24 for _, b in B]
    repeats = sum(1 for i in range(len(ts) - 1) if ts[i + 1] == ts[i])
    print("\n(2) device ts @28: %d/%d consecutive repeats (%.1f%%) -> %s" % (
        repeats, len(ts) - 1, 100.0 * repeats / max(len(ts) - 1, 1),
        "STALE (reports not refreshing under RP)" if repeats > 0.2 * len(ts) else "advancing (not stale; lag/layout)"))

    # build pyds held/released wall-windows (a tick is 'held' iff pyds_l2_max >= thr)
    held_win, rel_win = [], []
    for i, p in enumerate(pyds):
        w = p["wall_ms"]
        lo = pyds[i - 1]["wall_ms"] if i else w - 1200.0
        (held_win if p["pyds_l2_max"] >= thr else rel_win).append((lo, w))

    def _in(w, wins):
        return any(a < w <= b for a, b in wins)

    raw_held = [b for wm, b in B if _in(wm, held_win)]
    raw_rel = [b for wm, b in B if _in(wm, rel_win)]
    print("\n(1) raw reports in pyds-HELD windows=%d, pyds-RELEASED windows=%d" % (len(raw_held), len(raw_rel)))
    if not raw_held or not raw_rel:
        print("    need both held and released pyds ticks — do clean press/release cycles next capture")
        return 1

    # for each offset: mean value when pyds-held vs pyds-released; a real L2 byte is high-held / low-released
    print("    offset:  mean(HELD)  mean(REL)   separation  (L2 byte = big positive separation, ~clean split)")
    best = []
    for off in range(L):
        mh = sum(b[off] for b in raw_held) / len(raw_held)
        mr = sum(b[off] for b in raw_rel) / len(raw_rel)
        best.append((mh - mr, off, mh, mr))
    best.sort(reverse=True)
    for sep, off, mh, mr in best[:8]:
        star = "  <-- tracks pyds L2 under RP" if sep > 120 else ("  (offset 5 = the stuck byte)" if off == 5 else "")
        print("      [%2d]:   %6.1f     %6.1f      %+7.1f%s" % (off, mh, mr, sep, star))
    o5 = next((x for x in best if x[1] == 5), None)
    if o5:
        print("\n    offset 5 (the increment-one source): mean_held=%.1f mean_rel=%.1f sep=%+.1f -> %s" % (
            o5[2], o5[3], o5[0], "STUCK (confirms the RP finding)" if o5[0] < 60 else "separates?"))

    # (4) PAIRING FEASIBILITY — measured, not assumed. If no raw offset separates, the only remaining fix is
    # to pair the device timestamp (interface-3 timing) with pydualsense's L2 VALUE. But that is correlation
    # across two async read handles — the failure mode rejected in the plumbing decision (a dropped report
    # desyncs it silently). So characterize the fragility from the SAME dumps: (i) does the raw stream drop
    # out (interface-3 starved -> the device-ts goes stale, pairing desyncs), and (ii) does a per-tick
    # device->wall anchor stay consistent (the drain-anchor model) or jump. Then the fallback verdict carries
    # its fragility MEASURED, so the RP session is one-shot in the bad-offset branch too, not just the good.
    import statistics as _st
    wr = [wm for wm, _ in B]
    gaps = [wr[i + 1] - wr[i] for i in range(len(wr) - 1)]
    med_gap = _st.median(gaps) if gaps else 0.0
    drops = sum(1 for g in gaps if med_gap and g > 5 * med_gap)
    drop_frac = drops / max(len(gaps), 1)
    anchors = []
    for p in pyds:                                       # nearest raw device-ts at each pyds tick
        w = p["wall_ms"]
        j = min(range(len(B)), key=lambda k: abs(B[k][0] - w))
        anchors.append((w, ts[j]))
    rates = [(anchors[i + 1][1] - anchors[i][1]) / (anchors[i + 1][0] - anchors[i][0])
             for i in range(len(anchors) - 1) if anchors[i + 1][0] > anchors[i][0]]
    cv = (_st.pstdev(rates) / _st.mean(rates)) if len(rates) > 1 and _st.mean(rates) else 0.0
    feasible = drop_frac < 0.02 and cv < 0.05
    print("\n(4) pairing feasibility (device-ts @28 + pydualsense-L2 fallback — the fix that inherits the")
    print("    rejected two-read-handle risk, so measured not assumed):")
    print("    raw stream: median gap=%.2fms, drop-outs(>5x median)=%d (%.2f%%)" % (
        med_gap, drops, 100 * drop_frac))
    print("    per-tick device->wall anchor rate: mean=%.0f units/ms (expect ~3000), CV=%.3f" % (
        _st.mean(rates) if rates else 0.0, cv))
    print("    -> pairing %s (drop %.2f%% %s 2%%, anchor CV %.3f %s 0.05)" % (
        "VIABLE" if feasible else "FRAGILE", 100 * drop_frac, "<" if drop_frac < 0.02 else ">=",
        cv, "<" if cv < 0.05 else ">="))

    winner = best[0]
    if winner[0] > 120:
        verdict = ("raw offset %d is the RP-reliable L2 (sep=%+.1f) — repoint push_l2_raw's L2 read to it"
                   % (winner[1], winner[0]))
    elif feasible:
        verdict = ("NO raw offset separates under RP, but device-ts+pydualsense-L2 pairing measures VIABLE "
                   "(drop %.2f%%, anchor CV %.3f) — implement the drain-anchored pairing" % (100 * drop_frac, cv))
    else:
        verdict = ("NO raw offset separates AND the pairing fallback measures FRAGILE (drop %.2f%%, anchor "
                   "CV %.3f) — do NOT ship the pairing on this evidence; interface-3 is RP-hostile, needs a "
                   "different interface or an RP-config fix before l2_ads can run in gameplay" % (100 * drop_frac, cv))
    print("\n(3) VERDICT: %s" % verdict)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

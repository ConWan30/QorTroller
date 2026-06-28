"""Standalone WGC processed-fps probe (READ-ONLY screen capture; no controller writes).

Measures `rgc.frames_seen / sec` = the POST-PROCESSING throughput of the coupled-retina callback, alongside the
running bridge. Originally written for s-retina-wgc-process-isolation-scope (cycle-40) to test an
in-bridge-contention hypothesis; that framing was SUPERSEDED (see s-wgc-fps-processing-wall-resolved, cycle-43):
the ~7fps was the per-frame CALLBACK (full-res copy + dense Farneback), NOT the capture surface. Raw WGC
delivery is ~39fps (a no-op-callback probe proves it). The fix (slice-at-source `cab15fdc` + phaseCorrelate
`eb9eec27`) dropped the callback to ~3-4ms, so this probe now reads ~delivery-bound (~32fps SDR, 2026-06-27).

Interpreting the number NOW: the binding ceiling is WGC DELIVERY (~39fps), not the callback. To disambiguate a
LOW reading, run a no-op-callback raw-arrival probe (low raw => stream/present-rate limited; high raw + low
here => callback contended by the ambient floor). To EXCEED ~39fps (e.g. 60fps HDR), raise DELIVERY (the Remote
Play stream fps / HDR present path), not the callback -- see the 60fps-HDR scope note.

Run while the operator plays Remote Play FULLSCREEN. Default monitor 1 (laptop display).
"""
from __future__ import annotations

import argparse
import os
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "bridge"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--monitor", type=int, default=1, help="1-based monitor index (0 = use --window)")
    ap.add_argument("--window", default="Remote Play")
    ap.add_argument("--seconds", type=int, default=30)
    args = ap.parse_args()

    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")  # surface the WGC timestamp units log
    from vapi_bridge.qortroller_retina_capture import RetinaGameCapture
    rgc = RetinaGameCapture(args.window, monitor_index=args.monitor)
    if not rgc.start():
        print("FAILED to start WGC (monitor/window not found?). Is Remote Play visible on that display?")
        return
    tgt = f"monitor #{args.monitor}" if args.monitor >= 1 else f"window ~'{args.window}'"
    print(f"standalone WGC started on {tgt}; measuring {args.seconds}s (play normally)...", flush=True)

    t0 = time.time()
    last = 0
    while time.time() - t0 < args.seconds:
        time.sleep(5.0)
        fs = rgc.frames_seen
        el = time.time() - t0
        st = rgc.status()
        print(f"  t={el:4.0f}s  frames_seen={fs}  (~{fs/el:.1f} fps avg, +{fs-last} in last 5s)  "
              f"ts_source={st.get('ts_source')} ts_offset_ms={st.get('ts_offset_ms')} "
              f"fmt={st.get('frame_format')}", flush=True)
        last = fs

    fs = rgc.frames_seen
    el = time.time() - t0
    try:
        rgc.stop()
    except Exception:
        pass
    fps = fs / el if el else 0.0
    print(f"\nRESULT: {fs} frames / {el:.0f}s = ~{fps:.1f} fps PROCESSED (fmt={rgc._source.frame_format})", flush=True)
    if fps >= 30:
        print("VERDICT: DELIVERY-BOUND -> the slice+phaseCorrelate callback fix is working (processed ~= raw "
              "WGC delivery ~39fps). The ceiling is now DELIVERY, not the callback. To go higher (e.g. 60fps "
              "HDR) raise the Remote Play stream / HDR present rate, not the callback.", flush=True)
    elif fps >= 10:
        print("VERDICT: PARTIAL -> either raw WGC delivery is low (Remote Play stream / present rate) OR the "
              "callback is contended by the ambient floor. Disambiguate with a no-op-callback raw-arrival probe "
              "(high raw + low here => contention; low raw => stream-limited) + per-stage timing.", flush=True)
    else:
        print("VERDICT: LOW -> investigate before blaming the surface. Run the no-op raw-arrival probe: if raw "
              "is also low it's the stream / present rate (HDR? network?); if raw is ~39 the callback is the "
              "bottleneck (contention, or a regression in the slice / phaseCorrelate path).", flush=True)


if __name__ == "__main__":
    main()

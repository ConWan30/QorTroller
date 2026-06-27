"""Phase 0 validation for s-retina-wgc-process-isolation-scope (cycle-40).

Measures STANDALONE WGC frame rate ALONGSIDE the running bridge, to test the in-bridge-contention hypothesis
behind the ~2fps screen-lobe:
  * full-rate here (~>=20fps) while the bridge sees ~2fps -> the ~2fps IS in-bridge contention -> Phase 1
    (process-isolate WGC+cv_motion into a subprocess) is the correct fix.
  * ALSO ~2fps here -> the capture ITSELF is the limit (Remote Play protected surface / monitor present-rate)
    -> process isolation will NOT help -> re-scope (DXGI Desktop Duplication / accept low-rate witness).

Run while the operator plays Remote Play FULLSCREEN. READ-ONLY: captures the screen (WGC) only; no controller
writes, no input, nothing the anti-cheat could see as manipulation. Default monitor 1 (laptop display).
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
        print(f"  t={el:4.0f}s  frames_seen={fs}  (~{fs/el:.1f} fps avg, +{fs-last} in last 5s)", flush=True)
        last = fs

    fs = rgc.frames_seen
    el = time.time() - t0
    try:
        rgc.stop()
    except Exception:
        pass
    fps = fs / el if el else 0.0
    print(f"\nRESULT: {fs} frames / {el:.0f}s = ~{fps:.1f} fps standalone (fmt={rgc._source.frame_format})", flush=True)
    if fps >= 20:
        print("VERDICT (a): FULL-RATE standalone -> the bridge's ~2fps IS in-bridge contention "
              "-> Phase 1 process isolation is the correct fix.", flush=True)
    elif fps >= 5:
        print("VERDICT (mixed): partial rate -> inconclusive; re-run, ensure Remote Play is the only "
              "fullscreen content on this monitor.", flush=True)
    else:
        print("VERDICT (b): ALSO ~2fps standalone -> the CAPTURE ITSELF is the limit (Remote Play "
              "protected surface / monitor present-rate). Process isolation will NOT help -> re-scope "
              "(DXGI Desktop Duplication, or treat the screen-lobe as a low-rate witness only).", flush=True)


if __name__ == "__main__":
    main()

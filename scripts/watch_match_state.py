#!/usr/bin/env python3
"""LUMEN-2b watcher -- live match-state transitions from the streaming signal logs.

Two modes:

LIVE (default; run alongside the daemon during a match):
    python scripts/watch_match_state.py --session-start <unix_s> [--poll 5]
  Incrementally tails retina_hid_events.jsonl + retina_kf_composite.jsonl (append-only;
  byte-offset tail — never re-reads), pushes signals into LiveMatchStateTracker, prints
  MATCH_STARTED / MATCH_ENDED as they become CONFIRMED. Read-only; zero rig footprint
  beyond two file reads per poll; advisory only.

REPLAY (the rig-free validation; how this script was proven before any live run):
    python scripts/watch_match_state.py --replay \
        --archive retina_kf_archive/match14_rp_option_b_1783475385 \
        --scan audits/rp_ocr_precision_scan_v2_m14_m13.json
  Streams the session's REAL persisted signals through a simulated clock in virtual
  ticks, so the live emission semantics (confirmation latency, end-hysteresis, no flap
  through in-match no-fire gaps) are exercised on ground-truth data offline. Honest
  feeder caveat: replay kill anchors come from the archive scan (denser than the live
  classify stream); anchors only ever strengthen confirmation -- onsets/windows are the
  live-guaranteed feed.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from l9_presence.match_state_live import LiveMatchStateTracker

_ANCHOR_K = 2


def _clock(ms: float) -> str:
    return _dt.datetime.fromtimestamp(ms / 1000.0).strftime("%H:%M:%S")


class _Tail:
    """Byte-offset incremental reader for an append-only jsonl file."""

    def __init__(self, path: str):
        self.path, self.offset = path, 0

    def read_new(self) -> list:
        if not os.path.isfile(self.path):
            return []
        out = []
        with open(self.path, encoding="utf-8") as fh:
            fh.seek(self.offset)
            for line in fh:
                if not line.endswith("\n"):
                    break                      # partial write; re-read next poll
                self.offset += len(line.encode("utf-8"))
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out


def _emit(transitions, virtual: bool = False) -> None:
    for t in transitions:
        lag_s = (t.detected_at_ms - t.ts_ms) / 1000.0
        print(f"  >> {t.event} @ {_clock(t.ts_ms)} "
              f"(confirmed {_clock(t.detected_at_ms)}, +{lag_s:.0f}s"
              f"{', virtual' if virtual else ''})", flush=True)


def run_live(args) -> int:
    tr = LiveMatchStateTracker(session_start_ms=float(args.session_start) * 1000.0)
    hid, comp = _Tail(args.hid_events), _Tail(args.composites)
    seen_windows = set()
    print(f"watching match state (session start {_clock(tr.session_start_ms)}; "
          f"poll {args.poll}s; Ctrl+C to stop) ...")
    try:
        while True:
            for d in hid.read_new():
                t = d.get("t_ms") or d.get("wall_ms")
                if d.get("type") == "r2_onset" and t and t >= tr.session_start_ms:
                    tr.push_onset(float(t))
            for d in comp.read_new():
                g, e = d.get("window_gate_ms"), d.get("window_end_ms")
                if g and e and g >= tr.session_start_ms and (g, e) not in seen_windows:
                    seen_windows.add((g, e))
                    tr.push_window(float(g), float(e))
            now_ms = time.time() * 1000.0
            _emit(tr.tick(now_ms))
            time.sleep(max(1.0, float(args.poll)))
    except KeyboardInterrupt:
        _emit(tr.close_session(time.time() * 1000.0))
        print("session closed (flushed).")
    return 0


def run_replay(args) -> int:
    manifest = json.load(open(os.path.join(args.archive, "manifest.json"), encoding="utf-8"))
    start_ms = float(manifest["started_at"]) * 1000.0
    end_ms = start_ms + 3600_000.0
    try:
        end_ms = _dt.datetime.strptime(manifest["archived_at"],
                                       "%Y-%m-%d %H:%M:%S").timestamp() * 1000.0
    except (KeyError, ValueError):
        pass

    feed = []                                    # (ts_ms, kind, payload)
    for d in _Tail(args.hid_events).read_new():
        t = d.get("t_ms") or d.get("wall_ms")
        if d.get("type") == "r2_onset" and t and start_ms <= t <= end_ms:
            feed.append((float(t), "onset", None))
    seen = set()
    for d in _Tail(args.composites).read_new():
        g, e = d.get("window_gate_ms"), d.get("window_end_ms")
        if g and e and start_ms <= g <= end_ms and (g, e) not in seen:
            seen.add((g, e))
            feed.append((float(g), "window", (float(g), float(e))))
    if args.scan:
        doc = json.load(open(args.scan, encoding="utf-8"))
        arch_norm = args.archive.replace("\\", "/").rstrip("/")
        scan = next((r for r in (doc.get("results") or [doc])
                     if str(r.get("archive", "")).replace("\\", "/").rstrip("/") == arch_norm),
                    None)
        for c in (scan or {}).get("clusters") or []:
            if int(c.get("size", 0)) < _ANCHOR_K:
                continue                          # F-LUMEN-2 sighting discipline
            ts = [r["ts_ns"] / 1e6 for r in (c.get("reads") or []) if r.get("ts_ns")]
            if ts:
                feed.append((min(ts), "kill", (min(ts), max(ts))))
    feed.sort()

    tr = LiveMatchStateTracker(session_start_ms=start_ms,
                               session_id=manifest.get("session_id"))
    print(f"replaying {manifest.get('session_display')} -- {len(feed)} signals, "
          f"virtual {args.step}s ticks ...")
    clock = start_ms
    i = 0
    horizon = end_ms + (tr.exit_gap_s + 60.0) * 1000.0   # run past the end for hysteresis
    n_events = 0
    while clock <= horizon:
        clock += float(args.step) * 1000.0
        while i < len(feed) and feed[i][0] <= clock:
            ts, kind, payload = feed[i]
            i += 1
            if kind == "onset":
                tr.push_onset(ts)
            elif kind == "window":
                tr.push_window(*payload)
            else:
                tr.push_kill_span(*payload)
        ev = tr.tick(clock)
        n_events += len(ev)
        _emit(ev, virtual=True)
    print(f"replay done: {n_events} transitions.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Live/replay match-state watcher (LUMEN-2b)")
    ap.add_argument("--replay", action="store_true")
    ap.add_argument("--archive", default=None, help="replay: session archive dir")
    ap.add_argument("--scan", default=None, help="replay: v2 scan (K>=2 kill anchors)")
    ap.add_argument("--session-start", type=float, default=None,
                    help="live: session start (unix seconds)")
    ap.add_argument("--hid-events", default="retina_hid_events.jsonl")
    ap.add_argument("--composites", default="retina_kf_composite.jsonl")
    ap.add_argument("--poll", type=float, default=5.0)
    ap.add_argument("--step", type=float, default=5.0, help="replay: virtual tick seconds")
    args = ap.parse_args()

    if args.replay:
        if not args.archive:
            print("--replay needs --archive", file=sys.stderr)
            return 2
        return run_replay(args)
    if args.session_start is None:
        print("live mode needs --session-start <unix_s>", file=sys.stderr)
        return 2
    return run_live(args)


if __name__ == "__main__":
    sys.exit(main())

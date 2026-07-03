#!/usr/bin/env python
"""l2_ads calibration runner (Increment B.2) — drives the firing-range capture protocol.

PROTOCOL: announce a segment -> write the ATOMIC control file (temp + os.replace -> ~/.vapi/ads_segment.json,
which the bridge's feed_ads stamps onto every emitted record) -> wait for N events -> per-segment live report
-> advance. HALT-AND-LOOK on EITHER the tripwire (sustained raw-high/pyds-low, the 113/113 stuck pattern) OR a
nonzero unlabeled-record count (the control-file write path failing) — a poisoned segment is stopped at
CAPTURE time, not discovered at analysis. The halt paths are the load-bearing part: a runner that reports
beautifully but does not actually stop the segment on a tripped tripwire defeats the tripwire one layer up.

Reads the bridge's files (ads.jsonl records + *_crosscheck.jsonl) — file-based IPC, NO bridge change. Writes
the control file + its own transition-boundary session log (per-segment counts reconcile at HOLD C against
what the runner believes it captured). NO enabled=True, NO threshold/calibration logic (that is the HOLD-C
pass), NO FROZEN/PoAC/PV-CI/vault.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass, asdict
from typing import Callable, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from l9_presence.ads_coupling import StuckTripwire, ADS_ABSTAIN_UNCALIBRATED, DEFAULT_L2_THRESHOLD

DEFAULT_SEGMENT_PATH = os.path.expanduser("~/.vapi/ads_segment.json")
MIN_EVENT_GAP_MS = 400.0     # consecutive events closer than this = a likely split (one press, two events)
UNLABELED = "unlabeled"


# --- atomic control-file write (the reader was built to expect exactly this) ------------------------

def atomic_write_segment(path: str, optic: str, fire_state: str, segment: str) -> None:
    """Write {optic, fire_state, segment} to `path` ATOMICALLY: a temp file in the same dir + os.replace, so
    the bridge reader (Increment A) can never observe a torn write — only an absent or a complete file. This
    is what leaves the reader's only fail-closed path in practice as absent-file."""
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    payload = json.dumps({"optic": optic, "fire_state": fire_state, "segment": segment})
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)                # atomic rename on POSIX and Windows
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


def _load_jsonl(path: str) -> list:
    if not os.path.exists(path):
        return []
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if ln:
                    try:
                        out.append(json.loads(ln))
                    except Exception:
                        pass
    except Exception:
        pass
    return out


# --- tripwire re-derived from the crosscheck log (ONE source of truth: replay StuckTripwire) ---------

def tripwire_from_crosscheck_log(entries: list, thr: int, n_trip: int = 3) -> dict:
    """Re-derive the tripwire state from the bridge's crosscheck log (disagreement entries carrying cumulative
    n_agree/n_disagree) by REPLAYING the SAME StuckTripwire over the reconstructed observation sequence: the
    n_agree delta between consecutive disagreements is the number of agreements that reset the run, so feeding
    those (as (0,0) agreements) + each logged disagreement reproduces the bridge's latched tripped state. One
    detection implementation, exercised both live (bridge) and offline (here)."""
    tw = StuckTripwire(n_trip=n_trip)
    prev_agree = 0
    for e in entries:
        n_agree = int(e.get("n_agree", 0))
        for _ in range(max(0, n_agree - prev_agree)):
            tw.observe(0, 0, thr)            # implied agreement between disagreements -> reset the run
        prev_agree = n_agree
        tw.observe(int(e.get("raw_l2", 0)), int(e.get("pyds_l2", 0)), thr)   # the actual disagreement
    return tw.status()


# --- per-segment live report ------------------------------------------------------------------------

@dataclass
class SegmentReport:
    segment: str
    optic: str
    fire_state: str
    n_events: int                       # labeled ads_event records in the segment window
    abstain_rate: Optional[float]       # must be 1.0 while uncalibrated (None if no events yet)
    n_disagreements: int                # crosscheck disagreements in-window (edge-skew is OK; halt is on tripped)
    split_count: int                    # consecutive events < MIN_EVENT_GAP_MS apart -> must be 0
    unlabeled_count: int                # records stamped 'unlabeled' in-window -> nonzero HALTS
    tripped: bool                       # sustained stuck -> HALTS


def build_segment_report(ads_records: list, crosscheck_entries: list, *, segment: str, optic: str,
                         fire_state: str, window_start_ms: float, window_end_ms: float,
                         thr: int, n_trip: int = 3) -> SegmentReport:
    ev = [r for r in ads_records
          if r.get("trigger_context") == "ads_event"
          and window_start_ms <= float(r.get("onset_ts_ms", -1e18)) <= window_end_ms]
    labeled = [r for r in ev if r.get("segment") == segment]
    unlabeled = [r for r in ev if r.get("segment") == UNLABELED]
    n = len(labeled)
    abstain = (sum(1 for r in labeled if r.get("verdict") == ADS_ABSTAIN_UNCALIBRATED) / n) if n else None
    onsets = sorted(float(r.get("onset_ts_ms", 0.0)) for r in labeled)
    splits = sum(1 for a, b in zip(onsets, onsets[1:]) if (b - a) < MIN_EVENT_GAP_MS)
    cc_in = [c for c in crosscheck_entries
             if window_start_ms <= float(c.get("ts_ms", -1e18)) <= window_end_ms]
    tw = tripwire_from_crosscheck_log(cc_in, thr, n_trip)
    return SegmentReport(segment=segment, optic=optic, fire_state=fire_state, n_events=n,
                         abstain_rate=abstain, n_disagreements=len(cc_in), split_count=splits,
                         unlabeled_count=len(unlabeled), tripped=bool(tw.get("tripped")))


def should_halt(report: SegmentReport) -> tuple[bool, str]:
    """HALT-AND-LOOK: stop the segment + mark its records suspect on the tripwire OR any unlabeled record.
    Either condition means the segment's records cannot be trusted for calibration."""
    if report.tripped:
        return True, ("TRIPWIRE TRIPPED — sustained raw-high/pyds-low (the 113/113 stuck pattern); segment "
                      "records are SUSPECT (do NOT calibrate on them)")
    if report.unlabeled_count > 0:
        return True, (f"UNLABELED RECORDS ({report.unlabeled_count}) mid-segment — the control-file write path "
                      f"is failing; segment records are SUSPECT")
    return False, ""


# --- transition-boundary session log (rider 2: HOLD-C reconciliation) -------------------------------

def log_transition(session_log_path: str, event: str, **fields) -> None:
    """Append a transition-boundary event to the runner's own session log so per-segment counts reconcile at
    HOLD C against what the runner BELIEVES it captured (a stamped-after-close record is the stale-read
    tripcase, caught at analysis). Events: segment_opened / segment_closed / segment_halted."""
    rec = {"event": event, "ts_ms": round(time.time() * 1000.0, 1), **fields}
    d = os.path.dirname(session_log_path) or "."
    os.makedirs(d, exist_ok=True)
    with open(session_log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")


# --- capture loop (halt actually stops; injectable for tests) ---------------------------------------

def capture_segment(*, ads_log: str, crosscheck_log: str, segment: str, optic: str, fire_state: str,
                    n_events: int, thr: int, n_trip: int, window_start_ms: float, poll_interval_s: float = 1.0,
                    max_wait_s: float = 600.0, now_fn: Callable[[], float] = time.time,
                    read_fn: Callable[[str], list] = _load_jsonl,
                    sleep_fn: Callable[[float], None] = time.sleep) -> tuple[SegmentReport, bool, str]:
    """Poll the bridge's files until N labeled events OR a halt condition. Returns (report, halted, reason).
    On halt, RETURNS IMMEDIATELY — it does NOT wait for N events (the whole point of the tripwire)."""
    deadline = now_fn() + max_wait_s
    report = None
    while True:
        ads = read_fn(ads_log)
        cc = read_fn(crosscheck_log)
        report = build_segment_report(ads, cc, segment=segment, optic=optic, fire_state=fire_state,
                                      window_start_ms=window_start_ms, window_end_ms=now_fn() * 1000.0,
                                      thr=thr, n_trip=n_trip)
        halt, reason = should_halt(report)
        if halt:
            return report, True, reason                 # HALT — stop capture immediately, do NOT reach N
        if report.n_events >= n_events:
            return report, False, ""                    # captured enough, clean
        if now_fn() >= deadline:
            return report, False, "timeout (not a halt — no tripwire/unlabeled)"
        sleep_fn(poll_interval_s)


def _fmt_report(r: SegmentReport) -> str:
    ar = "n/a" if r.abstain_rate is None else f"{r.abstain_rate * 100:.0f}%"
    return (f"[{r.optic}/{r.fire_state}/{r.segment}] events={r.n_events} abstain={ar} "
            f"disagreements={r.n_disagreements} splits={r.split_count} unlabeled={r.unlabeled_count} "
            f"tripped={r.tripped}")


def run_segment(seg: dict, args) -> bool:
    """Announce -> atomic write -> capture -> report -> transition-log. Returns True to continue, False to
    halt the whole run (a halt means look before proceeding)."""
    optic, fire_state, segment = seg["optic"], seg["fire_state"], seg["segment"]
    input(f"\n>>> Ready for segment [{optic}/{fire_state}/{segment}] — {args.n} events. Press Enter to begin...")
    atomic_write_segment(args.segment_file, optic, fire_state, segment)
    win_start = time.time() * 1000.0
    log_transition(args.session_log, "segment_opened", optic=optic, fire_state=fire_state, segment=segment)
    report, halted, reason = capture_segment(
        ads_log=args.ads_log, crosscheck_log=args.crosscheck_log, segment=segment, optic=optic,
        fire_state=fire_state, n_events=args.n, thr=args.thr, n_trip=args.n_trip, window_start_ms=win_start,
        poll_interval_s=args.poll)
    print("   " + _fmt_report(report))
    log_transition(args.session_log, "segment_halted" if halted else "segment_closed",
                   optic=optic, fire_state=fire_state, segment=segment, n_records=report.n_events,
                   unlabeled=report.unlabeled_count, tripped=report.tripped, reason=reason)
    if halted:
        print(f"   !!! HALT — {reason}")
        return False
    if report.abstain_rate not in (None, 1.0):
        print(f"   !!! WARNING abstain_rate={report.abstain_rate} != 100% while uncalibrated — investigate")
    if report.split_count:
        print(f"   !!! WARNING split_count={report.split_count} (expected 0)")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="l2_ads calibration runner (B.2) — per-segment capture with halt")
    ap.add_argument("--segment-file", default=DEFAULT_SEGMENT_PATH)
    ap.add_argument("--ads-log", default="retina_ads.jsonl")
    ap.add_argument("--crosscheck-log", default="retina_ads_crosscheck.jsonl")
    ap.add_argument("--session-log", default=os.path.expanduser("~/.vapi/ads_calibration_session.jsonl"))
    ap.add_argument("--n", type=int, default=15, help="events per segment (8x kill-check protocol)")
    ap.add_argument("--thr", type=int, default=DEFAULT_L2_THRESHOLD)
    ap.add_argument("--n-trip", type=int, default=3)
    ap.add_argument("--poll", type=float, default=1.0)
    # 8x no-fire kill-check FIRST (cheapest kill-check): no separation on the easiest optic -> stop.
    ap.add_argument("--optic", default="high_8x")
    ap.add_argument("--fire-state", default="no_fire")
    ap.add_argument("--segment", default="s1")
    a = ap.parse_args()
    seg = {"optic": a.optic, "fire_state": a.fire_state, "segment": a.segment}
    print(f"l2_ads calibration runner — {a.n} events; halt on tripwire OR unlabeled. NO enabled=True, "
          f"NO threshold (HOLD C). Bridge must be running with ads enabled + RETINA_ADS_RP_DIAG.")
    ok = run_segment(seg, a)
    # clear the segment label at the end so stray records after the session are unlabeled, not mislabeled
    try:
        os.remove(a.segment_file)
    except Exception:
        pass
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

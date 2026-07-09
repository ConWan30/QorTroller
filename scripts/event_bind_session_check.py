#!/usr/bin/env python3
"""EVENT-BIND increment 2b — post-session binding check (the Session-1 success readout).

Reads a session's OUTCOME + INPUT lobe JSONL (the daemon's retina_kf_composite.jsonl +
retina_hid_events.jsonl), adapts them into the binder, and reports how many authored kills bind
RECORD_HASH_PRODUCTION (splice-proof) vs TEMPORAL_PROTOTYPE. With EVENT_BIND_STAMP_ENABLED on during
capture, a live-stamped session should report RECORD_HASH_PRODUCTION on real kills — the increment-2b
validation. Read-only: touches no KAS record / commitment. Offline, no rig, no chain.

Usage:
    python scripts/event_bind_session_check.py \
        [--composites retina_kf_composite.jsonl] [--hid retina_hid_events.jsonl] [--span LO HI]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from l9_presence.event_bind import bind_session_events
from l9_presence.killfeed_hid_event import session_hid_events
from l9_presence.killfeed_screen_event import session_screen_events


def _load_jsonl(path):
    out = []
    if not os.path.exists(path):
        return out
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:  # noqa: BLE001 — a torn line never blocks the check
            continue
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="EVENT-BIND inc 2b post-session binding check")
    ap.add_argument("--composites", default="retina_kf_composite.jsonl")
    ap.add_argument("--hid", default="retina_hid_events.jsonl")
    ap.add_argument("--span", nargs=2, type=float, default=None, metavar=("LO", "HI"))
    a = ap.parse_args()

    comps = _load_jsonl(a.composites)
    hid_raw = _load_jsonl(a.hid)
    if a.span:
        lo, hi = a.span
        hid_raw = [r for r in hid_raw if isinstance(r.get("t_ms"), (int, float)) and lo <= r["t_ms"] <= hi]

    scr = session_screen_events(comps)          # AUTHORED_PRESENT outcome events
    hid = session_hid_events(hid_raw, span_ms=(tuple(a.span) if a.span else None))
    report = bind_session_events(scr, hid)

    n_scr_stamped = sum(1 for e in scr if e.get("record_hash"))
    n_hid_stamped = sum(1 for e in hid if e.get("record_hash"))
    print(report.to_markdown())
    print(f"\n  authored outcomes: {len(scr)} ({n_scr_stamped} carry record_hash)  |  "
          f"hid onsets: {len(hid)} ({n_hid_stamped} carry record_hash)")
    print(f"  crypto-bound (splice-proof): {report.n_crypto}/{report.n_outcomes}  |  "
          f"binding_is_cryptographic={report.binding_is_cryptographic}")
    if report.n_outcomes == 0:
        print("  (no authored kills in this session window — play a match with kills, stamping ON)")
        return 0
    if report.n_crypto > 0:
        print("  RESULT: EVENT-BIND stamping VALIDATED live — real kills bind RECORD_HASH_PRODUCTION.")
        return 0
    print("  RESULT: temporal-only — stamping was OFF or the anchors didn't reach the lobes. "
          "Confirm EVENT_BIND_STAMP_ENABLED=1 was set before the bridge started.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Remote Play A/B probe — compares capture INTEGRITY (PCC) + biometric LIVENESS (NQPV co-capture)
between dual-connection (A: USB->laptop + BT->PS5, play on TV) and Remote Play (B: PS5 streamed to laptop).

Two questions:
  1. Does capture stay NOMINAL (not CONTESTED)? -> host_state/capture_state dist + poll-rate CV.
  2. Does L4/IMU come alive? -> nqpv_l4l5l6_ok fraction + humanity_prob + controller_signal CLEAN fraction.

Usage: python scripts/remote_play_ab_probe.py --label A_dual_connection --window 75
       (switch to Remote Play) python scripts/remote_play_ab_probe.py --label B_remote_play --window 75
Reads bridge.db directly (no auth). Appends each phase to audits/remote-play-ab-latest.json.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import statistics as st
import time
from collections import Counter

DB = os.path.expanduser("~/.vapi/bridge.db")
OUT = os.path.join("audits", "remote-play-ab-latest.json")


def _summarize(conn: sqlite3.Connection, since: float) -> dict:
    ch = conn.execute(
        "SELECT capture_state, host_state, poll_rate_hz FROM capture_health_log WHERE created_at >= ?",
        (since,),
    ).fetchall()
    rates = [r[2] for r in ch if r[2] is not None]
    poll_cv = (st.pstdev(rates) / st.mean(rates)) if len(rates) >= 2 and st.mean(rates) else None

    co = conn.execute(
        "SELECT nqpv_l4l5l6_ok, humanity_prob, nqpv_retina_controller_signal FROM nqpv_cocapture_log "
        "WHERE created_at >= ?",
        (since,),
    ).fetchall()
    l4_ok = [r[0] for r in co if r[0] is not None]
    hp = [r[1] for r in co if r[1] is not None]
    sig = [r[2] for r in co if r[2]]
    clean = sum(1 for s in sig if s == "CONTROLLER_CLEAN")

    return {
        "integrity": {
            "n_pcc_samples": len(ch),
            "host_state_dist": dict(Counter(r[1] for r in ch)),
            "capture_state_dist": dict(Counter(r[0] for r in ch)),
            "poll_rate_mean": round(st.mean(rates), 1) if rates else None,
            "poll_rate_cv": round(poll_cv, 4) if poll_cv is not None else None,
            "contested": any(r[1] == "CONTESTED" for r in ch),
        },
        "liveness": {
            "n_cocapture_samples": len(co),
            "l4l5l6_ok_fraction": round(sum(l4_ok) / len(l4_ok), 3) if l4_ok else None,
            "humanity_prob_mean": round(st.mean(hp), 3) if hp else None,
            "humanity_prob_max": round(max(hp), 3) if hp else None,
            "controller_clean_fraction": round(clean / len(sig), 3) if sig else None,
            "controller_signal_dist": dict(Counter(sig)),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True, help="A_dual_connection | B_remote_play")
    ap.add_argument("--window", type=int, default=75, help="sampling window seconds")
    args = ap.parse_args()

    start = time.time()
    print(f"[AB] phase={args.label} sampling {args.window}s — play normally now...", flush=True)
    time.sleep(args.window)

    conn = sqlite3.connect(DB)
    try:
        summary = _summarize(conn, start)
    finally:
        conn.close()

    record = {"label": args.label, "window_s": args.window, "started_at": start, "summary": summary}
    print(json.dumps(record, indent=2), flush=True)

    existing = []
    if os.path.exists(OUT):
        try:
            existing = json.load(open(OUT))
        except Exception:
            existing = []
    existing = [e for e in existing if e.get("label") != args.label] + [record]
    json.dump(existing, open(OUT, "w"), indent=2)
    print(f"[AB] wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()

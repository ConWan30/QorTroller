"""Grok round-04 Step C observer half (docs/a2a/live-l2b-unit-scale-investigation/
round-04-grok-audit.md, C3 step 3 + open-question 1: additive script, not a one-off
snippet).

This is ONLY the observer terminal. It does NOT start the bridge (per round-04 C3
mod 2: bridge must be started manually, in its own terminal, with
L2B_IMU_SPIKE_THRESH=0.03 process-scoped -- never under scripts/bridge_watchdog.py,
which would inherit the parent env WITHOUT the override on any restart). This script
only subscribes read-only to the bridge's existing /ws/records WebSocket (already
streams l2b_coupled_fraction/l2b_p_human unauthenticated, http.py ~L178-179) and
sends periodic keep-alive text pings (server closes idle clients after 60s of
silence, http.py ~L247-249 -- round-04 C2 finding).

Default port is 8080 (this machine's live bridge/.env HTTP_PORT per round-04's
preflight, NOT the 8000 assumed in round-03's original scope -- round-04 flagged
this as a HIGH-severity procedure bug). Override with --port if different.

Usage (bridge already running manually in another terminal, per C3 steps 1-2):
    python scripts/diag_l2b_ws_observer.py [--port=8080] [--duration-s=240]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path
from typing import Optional

import websockets

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORT = 8080          # round-04 C2: this machine's live HTTP_PORT, not 8000
PING_INTERVAL_S = 20.0        # must stay < the server's 60s idle-close window
MIN_PRESS_EVENTS_FOR_VERDICT = 15  # mirrors controller/l2b_imu_press_correlation.py

# Dual gate from round-04 Ask 4 (replaces Claude's looser single-threshold scope):
RECOVERY_FRACTION_MIN = 0.55
RECOVERY_P_HUMAN_MIN = 0.5
FAIL_FRACTION_MAX = 0.15


async def _pinger(ws, interval_s: float, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_s)
        except asyncio.TimeoutError:
            try:
                await ws.send("ping")
            except Exception:  # noqa: BLE001
                return


async def observe(port: int, duration_s: float, out_path: Optional[Path]) -> dict:
    uri = f"ws://127.0.0.1:{port}/ws/records"
    print(f"L2B WS OBSERVER connecting to {uri} (duration_s={duration_s}, "
          f"ping_interval_s={PING_INTERVAL_S})")
    print("Bridge must already be running manually (per round-04 C3 steps 1-2) "
          "with L2B_IMU_SPIKE_THRESH=0.03 set BEFORE it started.")

    samples: list[dict] = []
    t0 = time.time()
    stop = asyncio.Event()

    async with websockets.connect(uri, open_timeout=10) as ws:
        ping_task = asyncio.create_task(_pinger(ws, PING_INTERVAL_S, stop))
        try:
            while time.time() - t0 < duration_s:
                remaining = duration_s - (time.time() - t0)
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 5.0))
                except asyncio.TimeoutError:
                    continue
                try:
                    msg = json.loads(raw)
                except (TypeError, ValueError):
                    continue

                cf = msg.get("l2b_coupled_fraction")
                ph = msg.get("l2b_p_human")
                inf_name = msg.get("inference_name")

                if cf is not None:
                    row = {
                        "t_s": round(time.time() - t0, 1),
                        "l2b_coupled_fraction": cf,
                        "l2b_p_human": ph,
                        "inference_name": inf_name,
                        "fired_0x31": inf_name == "0x31",
                    }
                    samples.append(row)
                    print(f"  t={row['t_s']:.1f}s coupled_fraction={cf} p_human={ph} "
                          f"inference={inf_name}")
        finally:
            stop.set()
            ping_task.cancel()

    n = len(samples)
    last5 = samples[-5:] if n >= 5 else samples
    # "sustained ... after warmup" (round-04 Ask 4) means recent state, not the whole session --
    # early cold-start rows (first ~15 press events) are EXPECTED to look decoupled before any
    # recovery has had a chance to show up; only fires within the trailing window count against
    # the verdict. (classify() can only fire 0x31 on rows where cf is non-null in the first place,
    # since extract_features() gates both -- but scoring only the tail is still the correct
    # "after warmup" read regardless.)
    fires_0x31_recent = sum(1 for s in last5 if s["fired_0x31"])
    fires_0x31_total = sum(1 for s in samples if s["fired_0x31"])
    median_cf = statistics.median(s["l2b_coupled_fraction"] for s in last5) if last5 else None
    median_ph = statistics.median(
        s["l2b_p_human"] for s in last5 if s["l2b_p_human"] is not None
    ) if any(s["l2b_p_human"] is not None for s in last5) else None

    report = {
        "duration_s": round(time.time() - t0, 1),
        "n_non_null_samples": n,
        "fires_0x31_total": fires_0x31_total,
        "fires_0x31_in_last5": fires_0x31_recent,
        "median_coupled_fraction_last5": median_cf,
        "median_p_human_last5": median_ph,
        "all_samples": samples,
    }

    verdict = "INCONCLUSIVE: fewer than 5 non-null samples observed -- press more / run longer"
    if n >= 5 and median_cf is not None:
        if median_cf >= RECOVERY_FRACTION_MIN and (median_ph or 0) > RECOVERY_P_HUMAN_MIN and fires_0x31_recent == 0:
            verdict = f"RECOVERY CONFIRMED: median_cf={median_cf} median_ph={median_ph} 0x31_in_last5=0"
        elif median_cf < FAIL_FRACTION_MAX or fires_0x31_recent > 0:
            verdict = (f"RECOVERY FAILED: median_cf={median_cf} (<{FAIL_FRACTION_MAX} or 0x31 "
                       f"still firing recently, count={fires_0x31_recent}) -- do NOT jump to a "
                       f"production fix; see round-04 Ask 5 fallback ladder (C-fail-1..5)")
        else:
            verdict = f"PARTIAL / inconclusive: median_cf={median_cf} in [0.15, 0.55) -- capture, do not ship D1 yet"
    report["verdict"] = verdict

    print("\n--- final report ---")
    print(json.dumps({k: v for k, v in report.items() if k != "all_samples"}, indent=2))
    print(f"\n{verdict}")

    if out_path is not None:
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nWritten: {out_path}")

    return report


def main() -> None:
    ap = argparse.ArgumentParser(description="Step C observer: read-only /ws/records tap (no bridge start)")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--duration-s", type=float, default=240.0)
    ap.add_argument("--out", type=str, default=None, help="optional path to write the JSON report")
    args = ap.parse_args()

    out_path = Path(args.out) if args.out else None
    asyncio.run(observe(args.port, args.duration_s, out_path))


if __name__ == "__main__":
    main()

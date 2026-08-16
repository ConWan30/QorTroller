#!/usr/bin/env python3
"""BT DualSense Edge observer runner — research path (no L6, no chain).

Topology: USB → PS5 (game) + BT → laptop (this process).

Usage:
  python scripts/bt_edge_observe.py --duration 30
  python scripts/bt_edge_observe.py --duration 10 --out logs/bt_obs.jsonl

Press buttons in-game while it runs. Ctrl+C stops early and still writes summary.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge"))

from vapi_bridge.bt_edge_observer import (  # noqa: E402
    BtEdgeObserver,
    enumerate_edge_devices,
    run_session,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="BT Edge HID observer (read-only)")
    ap.add_argument("--duration", type=float, default=30.0, help="Seconds to capture")
    ap.add_argument(
        "--out",
        type=str,
        default="",
        help="JSONL output path (default logs/bt_edge_obs_<ts>.jsonl)",
    )
    ap.add_argument(
        "--list",
        action="store_true",
        help="List Edge HID devices and exit",
    )
    ap.add_argument(
        "--no-prefer-bt",
        action="store_true",
        help="Do not prefer Bluetooth path over USB",
    )
    ap.add_argument(
        "--smoke",
        type=float,
        default=0.0,
        help="If >0, print decoded samples for N seconds then exit (no file)",
    )
    args = ap.parse_args()

    if args.list:
        devs = enumerate_edge_devices()
        print(json.dumps(devs, indent=2, default=str))
        return 0 if devs else 1

    prefer_bt = not args.no_prefer_bt

    if args.smoke > 0:
        print(f"[bt-obs] smoke {args.smoke}s — mash buttons", flush=True)
        try:
            with BtEdgeObserver(prefer_bluetooth=prefer_bt) as obs:
                print(f"[bt-obs] open ok bluetooth={obs.is_bluetooth}", flush=True)
                n = 0
                shown = 0
                t_end = time.time() + args.smoke
                while time.time() < t_end:
                    s = obs.read_sample()
                    if not s:
                        time.sleep(0.001)
                        continue
                    n += 1
                    if s.buttons or s.l2 > 10 or s.r2 > 10 or shown < 3:
                        if shown < 20:
                            print(
                                f"  rid={s.report_id:#x} sticks=({s.lx},{s.ly},{s.rx},{s.ry}) "
                                f"L2={s.l2} R2={s.r2} btns={s.buttons}",
                                flush=True,
                            )
                            shown += 1
                print(f"[bt-obs] smoke reports={n} rate≈{n / max(args.smoke, 1e-6):.0f}Hz")
                return 0 if n > 0 else 1
        except Exception as e:
            print(f"[bt-obs] FAIL: {e}", file=sys.stderr)
            return 1

    out = Path(args.out) if args.out else (
        ROOT / "logs" / f"bt_edge_obs_{int(time.time())}.jsonl"
    )
    print(
        f"[bt-obs] capturing {args.duration}s → {out} "
        f"(prefer_bt={prefer_bt}, READ-only, no L6/chain)",
        flush=True,
    )
    try:
        summary = run_session(
            args.duration,
            out,
            prefer_bluetooth=prefer_bt,
        )
    except KeyboardInterrupt:
        print("[bt-obs] interrupted", flush=True)
        return 130
    except Exception as e:
        print(f"[bt-obs] FAIL: {e}", file=sys.stderr)
        return 1

    print(json.dumps(summary, indent=2))
    print(
        f"[bt-obs] done rate≈{summary.get('rate_hz', 0):.0f}Hz "
        f"reports={summary.get('reports')} → {out}"
    )
    if not summary.get("reports"):
        print(
            "[bt-obs] WARNING: 0 reports. Wake the pad (move sticks), "
            "close Steam/DS4Windows if open, re-pair BT, retry.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

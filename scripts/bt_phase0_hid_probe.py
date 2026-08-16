#!/usr/bin/env python3
"""BT Phase 0/1 — DualSense Edge HID probe (observe only).

Uses bridge.vapi_bridge.bt_edge_observer for open/decode so we do not
false-SILENT when the stream is live.

Usage:
  python scripts/bt_phase0_hid_probe.py
  python scripts/bt_phase0_hid_probe.py --sample 5
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge"))

from vapi_bridge.bt_edge_observer import (  # noqa: E402
    BtEdgeObserver,
    enumerate_edge_devices,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="BT Phase 0 HID probe")
    ap.add_argument("--sample", type=float, default=0.0)
    ap.add_argument("--open-first", action="store_true",
                    help="Ignored (compat); sampling always opens device")
    args = ap.parse_args()

    devs = enumerate_edge_devices()
    print("=== BT Phase 0 HID probe ===")
    print(f"DualSense Edge matches: {len(devs)}")
    if not devs:
        print("RESULT: NO_PAD")
        return 1

    for i, d in enumerate(devs):
        path = d.get("path")
        if isinstance(path, bytes):
            path = path.decode("utf-8", "replace")
        print(f"--- device[{i}] ---")
        print(f"  product:  {d.get('product')}")
        print(f"  iface:    {d.get('interface')}")
        print(f"  usage:    page={d.get('usage_page')} usage={d.get('usage')}")
        print(f"  bluetooth:{d.get('is_bluetooth')}")
        print(f"  path:     {str(path)[:100]}")

    if args.sample <= 0:
        print("RESULT: ENUM_OK")
        return 0

    try:
        with BtEdgeObserver(prefer_bluetooth=True) as obs:
            print(f"Opening bluetooth={obs.is_bluetooth} …")
            n = 0
            n_active = 0
            t0 = time.time()
            last = None
            while time.time() - t0 < args.sample:
                s = obs.read_sample()
                if s is None:
                    time.sleep(0.001)
                    continue
                n += 1
                last = s
                if s.buttons or s.l2 > 8 or s.r2 > 8:
                    n_active += 1
            elapsed = max(time.time() - t0, 1e-6)
            rate = n / elapsed
            print(
                f"sample_s={elapsed:.2f} reports={n} active={n_active} "
                f"rate_hz≈{rate:.1f}"
            )
            if last:
                print(
                    f"last rid={last.report_id:#x} "
                    f"sticks=({last.lx},{last.ly},{last.rx},{last.ry}) "
                    f"L2={last.l2} R2={last.r2} btns={last.buttons}"
                )
            if n == 0:
                print("RESULT: OPEN_OK_BUT_SILENT")
                return 1
            print("RESULT: REPORTS_OK")
            return 0
    except Exception as e:
        print(f"RESULT: OPEN_FAIL {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

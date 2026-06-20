"""
l6b_probe_feel_test.py — One-shot R2 adaptive-trigger feel test (desk plumbing).

Fires the same actuator path as L6B (pydualsense trigger write), holds longer
than the 15ms production window so you can confirm the hardware path works.

USAGE (USB-only, bridge STOPPED to avoid dual-writer contention):
  python scripts/l6b_probe_feel_test.py
  python scripts/l6b_probe_feel_test.py --force 128 --hold-ms 300 --mode rigid
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", type=int, default=128, help="R2 force 1-255")
    parser.add_argument(
        "--mode",
        choices=("rigid", "pulse"),
        default="rigid",
        help="rigid = sustained resistance (recommended for feel test)",
    )
    parser.add_argument(
        "--hold-ms",
        type=int,
        default=200,
        help="How long to hold effect before clearing (ms)",
    )
    args = parser.parse_args()

    try:
        from pydualsense import pydualsense
    except ImportError:
        print("ERROR: pip install pydualsense")
        return 1

    from bridge.controller.l6_challenge_profiles import l6b_probe_profile
    from bridge.controller.l6_trigger_driver import L6TriggerDriver

    force = max(1, min(255, args.force))
    hold_ms = max(50, min(1000, args.hold_ms))
    profile = l6b_probe_profile(force, mode=args.mode)

    print("L6B probe feel test — DualSense Edge adaptive R2 (NOT rumble motors)")
    print(f"  mode={args.mode}  force={force}  hold_ms={hold_ms}")
    print("  Hold R2 lightly — you should feel resistance on R2 for the hold window.")
    print()

    ds = pydualsense()
    ds.init()
    try:
        driver = L6TriggerDriver()
        L6TriggerDriver._sync_write(ds, profile)
        print(f"  Effect ON — waiting {hold_ms} ms...")
        time.sleep(hold_ms / 1000.0)
        asyncio.run(driver.clear_triggers(ds))
        print("  Effect OFF (BASELINE_OFF).")
        print("  If you felt nothing: run python scripts/l6_hardware_check.py")
    finally:
        try:
            ds.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

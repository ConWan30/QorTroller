#!/usr/bin/env python3
"""TRL-1 A1 - LUMEN N5 increment 2 (lag directionality) synthetic-separation demo.

Shows the metric SEPARATES genuine causal coupling (input precedes screen) from a
replay/precognition class (screen precedes input) on synthetic windows - the ladder's
first rung (synthetic -> archive -> live -> calibrated). The GENUINE baseline runs on
archive windows; the real DECOUPLED (replay) class needs a controlled stimulus -
card-gated (RP-4). Advisory; never gates a verdict. ASCII-only.
"""
from __future__ import annotations

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from l9_presence.predictive_coupling import assess_directionality


def _wins(channel, lag_ms, n=12, coupling=0.5):
    return [{"channel": channel, "coupling": coupling, "lag_ms": lag_ms} for _ in range(n)]


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    # Synthetic classes: genuine = input precedes screen (+lag); replay = screen
    # precedes input (-lag, the recoil-precognition signature).
    genuine = _wins("b1_flash", 100.0) + _wins("b2_killmark", 90.0)
    replay = _wins("b1_flash", -100.0) + _wins("b2_killmark", -80.0)
    res = assess_directionality(genuine, replay)

    print("=" * 74)
    print("  TRL-1 A1 - LUMEN N5 inc2: LAG DIRECTIONALITY (synthetic separation)")
    print("=" * 74)
    print("  genuine = input precedes screen (causal); replay = screen precedes input")
    print("-" * 74)
    for ch in res["channels"]:
        g = ch["genuine"]["leading_fraction"]
        d = ch["decoupled"]["leading_fraction"]
        print(f"  {ch['channel']:<12} genuine leading={g}  decoupled leading={d}  "
              f"-> {'SEPARATES' if ch['separates'] else 'no'} ({ch['note']})")
    print("-" * 74)
    print(f"  separates_any : {res['separates_any']}")
    print(f"  bar           : {res['pre_registered_bar']}")
    print(f"  offline scope : {res['offline_scope']}")
    print("=" * 74)
    return 0 if res["separates_any"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

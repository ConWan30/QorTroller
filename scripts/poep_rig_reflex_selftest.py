"""L3 adapter MECHANISM SELFTEST (operator rig) - fire via EdgeReflexAdapter directly, report fire+capture.

This validates ONLY the L3 fire+IMU mechanism: did a real adaptive-trigger force fire on the registered
Edge, and did we capture a reflex window? It fires via the adapter DIRECTLY - NOT through a session, NOT
through challenge_live's activity gate - so it makes NO session/presence claim. poep_enabled / L6B /
L6_CHALLENGES stay False; advances nothing; no chain; no spend.

    POEP_LIVE_FIRE_ENABLED=1 python scripts/poep_rig_reflex_selftest.py --count 5 --amplitude 60

Under exclusive HID the adapter REFUSES to fire while the bridge holds the pad (dual-writer) - stop the
bridge first. Reaching SYNCHRONIZED_CONTROLLER under real play needs the single-HID bridge fire+IMU ring
(a later arc), NOT this selftest.
"""
from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from l9_presence.poep_rig_reflex_adapter import CLAIM_CEILING  # noqa: E402


def main() -> int:  # pragma: no cover - hardware path (rig-only; never CI)
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--count", type=int, default=5, help="challenges to fire")
    ap.add_argument("--amplitude", type=int, default=60, help="R2 force 1-255 (clamped to 40-80 gameplay band)")
    ap.add_argument("--mode", choices=("rigid", "pulse"), default="pulse")
    ap.add_argument("--hold-ms", type=int, default=1500, dest="hold_ms")
    ap.add_argument("--device-id", default=None, dest="device_id")
    args = ap.parse_args()

    from l9_presence.poep_rig_reflex_adapter import make_edge_reflex_adapter

    print("=" * 70)
    print("  L3 ADAPTER MECHANISM SELFTEST  (fire+capture only - NOT a presence claim)")
    print("=" * 70)
    print(f"  {CLAIM_CEILING}")
    print("-" * 70)
    print("  Hold the controller relaxed, finger RESTING on R2. React the instant you feel")
    print("  the BUZZ. This fires real haptics; it makes no session/presence claim.")
    print("=" * 70)

    try:
        adapter = make_edge_reflex_adapter(
            device_id=args.device_id, mode=args.mode, hold_ms=args.hold_ms)
    except RuntimeError as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2

    n_fired = n_real = n_clean = 0
    for i in range(1, max(1, args.count) + 1):
        nonce = secrets.token_hex(16)
        fr = adapter.fire_fn(args.amplitude, nonce)
        if not fr.fired:
            print(f"  [{i}] REFUSED  real_hw={fr.real_hardware}  {fr.error}")
            continue
        n_fired += 1
        n_real += 1 if fr.real_hardware else 0
        win = adapter.imu_capture_fn(fr.t_fire_ns)
        if win is None:
            print(f"  [{i}] fired real_hw={fr.real_hardware} force={fr.amplitude}  window=NONE  {fr.error}")
            continue
        clean = win.latency_ms > 0.0
        n_clean += 1 if clean else 0
        print(f"  [{i}] fired real_hw={fr.real_hardware} force={fr.amplitude}  "
              f"latency_ms={win.latency_ms:.1f} peak_lsb={win.peak_lsb:.0f} "
              f"precursor_ms={win.precursor_gap_ms:.1f}  {'CLEAN' if clean else 'no-clean-peak'}")

    print("-" * 70)
    print(f"  fired={n_fired}/{args.count}  real_hardware={n_real}  clean_reflex={n_clean}")
    print("  MECHANISM ONLY - poep_enabled stays False; no session/presence/candidate produced.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

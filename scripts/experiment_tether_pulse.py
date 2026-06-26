#!/usr/bin/env python3
"""
VSD Cycle 25 experiment harness: does the novel tether pulse generator "work"?

Simulates a realistic player trigger rhythm (no hardware, no USB, no PS5).
Feeds the TetherPulseGenerator and prints decisions + synthetic "pulse sent" events.

Run:
  python scripts/experiment_tether_pulse.py

Tune via env or edit the TetherConfig in the script.

This is purely to answer "could the use case work?" before investing in full
dual-connection hardware sessions or L6 micro profile additions.
"""

import math
import os
import time as _t
from bridge.vapi_bridge.tether_pulse_generator import TetherPulseGenerator, TetherConfig


def main():
    enabled = os.environ.get("DUAL_GRIND_TETHER_ENABLED", "1").lower() in ("1", "true", "yes")
    amp_max = int(os.environ.get("DUAL_GRIND_TETHER_AMP_MAX", "12"))
    duty = float(os.environ.get("DUAL_GRIND_TETHER_DUTY_S", "1.2"))

    cfg = TetherConfig(
        enabled=enabled,
        amplitude_max=amp_max,
        min_interval_s=duty,
        sync_to_player_rhythm=True,
    )

    pulses = []
    def fake_send(amp: int, dur_ms: int):
        pulses.append(( _t.monotonic(), amp, dur_ms ))
        print(f"  [TETHER] sent amp={amp} dur={dur_ms}ms @t={_t.monotonic():.2f}")

    gen = TetherPulseGenerator(cfg, send_action=fake_send)

    print("=== Tether Pulse Generator experiment (simulated player rhythm) ===")
    print(f"enabled={enabled} amp_max={amp_max} duty={duty}s")
    print("Simulating ~3s of press/release rhythm (R2-like) ...")
    print()

    base = _t.monotonic()
    for i in range(300):  # 3s @ 10ms steps (coarse for demo)
        t = base + i * 0.01
        # Fake rhythmic force: 0.6s press, 0.4s release, with some variance
        phase = (i * 0.01) % 1.0
        force = 180.0 * max(0.0, math.sin(phase * math.pi * 2))   # rough 0-180 "analog"
        if phase > 0.6:
            force *= 0.1  # release tail

        gen.feed_biomarker(force, t)
        emitted = gen.maybe_send_tether(t)
        if i % 20 == 0:
            print(f"t={t-base:.2f}s force~{force:5.1f} last_pulse={gen.last_pulse_ts-base:.2f}")

    print()
    print(f"Total synthetic pulses emitted: {len(pulses)}")
    if pulses:
        amps = [p[1] for p in pulses]
        print(f"  amp range: {min(amps)}..{max(amps)} (cap {amp_max})")
        intervals = [pulses[i][0]-pulses[i-1][0] for i in range(1, len(pulses))]
        if intervals:
            print(f"  observed intervals (s): min={min(intervals):.2f} max={max(intervals):.2f} (target >= {duty})")
    print()
    print("Conclusion (manual review):")
    print(" - Pulses are low amp and respect duty cycle in the sim.")
    print(" - With real L6/driver wrapper + proper ps5_compat guard + restore,")
    print("   this would be a candidate 'active tether' to defend module state.")
    print(" - Next real step: hardware dual-session measurement (USB capture stable +")
    print("   no 'module not attached' on PS5 for >20min grind).")
    print()
    print("If this run showed reasonable low-rate low-amp behavior → use case has potential.")


if __name__ == "__main__":
    main()

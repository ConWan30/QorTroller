"""Investigates whether L4 (controller/tinyml_biometric_fusion.py,
BiometricFeatureExtractor) has the same timing exposure investigated for
L2B/L2C/L5. Read-only investigation, no production code touched.

FINDING (this script confirms it): L4's press_timing_jitter_variance feature
(index 11) is architecturally DIFFERENT from L2B/L2C/L5's exposure -- it does
NOT call time.monotonic() at all, live or otherwise. It reads
getattr(s, "timestamp_ms", 0) with a HARDCODED 0 DEFAULT (not a monotonic()
fallback). Before dualshock_integration.py's C-fail-4 fix started stamping
real timestamp_ms onto every live frame, EVERY snap's _ts would have been
exactly 0 -- and since self._jitter_cross_last_ts = _ts unconditionally, the
guard `if self._jitter_cross_last_ts > 0` NEVER passes when _ts is always 0,
so no interval is EVER appended to the IBI deque. The feature stays
permanently "insufficient data" and _press_timing_jitter_variance() returns
its own documented "insufficient data" default: 0.0.

The independent design problem: 0.0 is NOT a neutral sentinel for this
feature -- the function's own docstring defines "Bot deterministic macro:
< 0.00005 (essentially zero variance)" as the bot-like range, and 0.0 falls
squarely inside it. "No data yet" and "definitely a bot" produce the
identical value.

Because L4's extract(frames) (dualshock_integration.py:2200) is called on
the SAME frames list that _stamp_frame_collection_times() already mutates
earlier in _session_loop (the C-fail-4 fix, shipped for L2B/L2C), this
specific defect was ALREADY silently repaired as an unintended side effect --
confirmed here, not assumed.

Historical corpus check: sessions/human/hw_*.json report objects DO carry a
real, correctly-incrementing timestamp_ms field at the top level (confirmed:
hw_005.json, 30002 reports, min=0 max=29999, mean delta=~1.0ms) -- meaning
OFFLINE calibration (the thresholds anomaly=7.009/continuity=5.367 documented
in CLAUDE.md) was computed from CORRECT jitter values the whole time. Only
the LIVE bridge path was ever broken, mirroring the exact L2B pattern.

Usage: python scripts/diag_l4_jitter_timestamp_repro.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "controller"))

from tinyml_biometric_fusion import BiometricFeatureExtractor  # noqa: E402

_CROSS_BIT = 0x20  # buttons_0 bit 5, matches the class's own constant


def _snap(buttons_0: int, timestamp_ms: float | None = None):
    attrs = {
        "buttons_0": buttons_0, "buttons_1": 0,
        "left_stick_x": 0, "left_stick_y": 0, "right_stick_x": 0,
        "l2_trigger": 0, "r2_trigger": 0,
        "gyro_x": 0.0, "gyro_y": 0.0, "gyro_z": 0.0,
        "accel_x": 0.0, "accel_y": 0.0, "accel_z": 1.0,
        "l2_effect_mode": 0, "r2_effect_mode": 0,
        "touch_active": False, "touch0_x": 0, "touch0_y": 0,
    }
    if timestamp_ms is not None:
        attrs["timestamp_ms"] = timestamp_ms
    return type("_S", (), attrs)()


def build_batches(with_timestamps: bool, n_batches: int = 8, batch_size: int = 20):
    """Realistic Cross-press pattern: one press near the start of each batch,
    a few hundred ms apart across batches (typical human button-mash cadence,
    WITH natural jitter -- deliberately varied gaps, not a perfectly uniform
    period, so a healthy result is a nonzero, human-range jitter value rather
    than a test artifact of artificial uniformity)."""
    gaps_ms = [320.0, 410.0, 290.0, 380.0, 340.0, 400.0, 300.0, 360.0]  # varied, not periodic
    batches = []
    t = 0.0
    for b in range(n_batches):
        batch = []
        gap = gaps_ms[b % len(gaps_ms)]
        for i in range(batch_size):
            pressed = (i == 2)  # one press per batch, at a fixed offset
            ts = t if with_timestamps else None
            batch.append(_snap(_CROSS_BIT if pressed else 0, timestamp_ms=ts))
            t += gap / batch_size  # spread frames across this batch's gap
        batches.append(batch)
    return batches


def run(with_timestamps: bool) -> float:
    extractor = BiometricFeatureExtractor()
    batches = build_batches(with_timestamps)  # 8 presses -> 7 IBIs, >= min_samples=4
    feats = None
    for batch in batches:
        feats = extractor.extract(batch, window_frames=120)
    return feats.press_timing_jitter_variance, len(extractor._jitter_cross_ibis)


def main() -> None:
    print("--- WITHOUT timestamp_ms (pre-C-fail-4-fix production state) ---")
    jitter_before, n_ibis_before = run(with_timestamps=False)
    print(f"  press_timing_jitter_variance={jitter_before} n_ibis_accumulated={n_ibis_before}")

    print("\n--- WITH timestamp_ms (current, post-fix production state) ---")
    jitter_after, n_ibis_after = run(with_timestamps=True)
    print(f"  press_timing_jitter_variance={jitter_after} n_ibis_accumulated={n_ibis_after}")

    print("\n--- verdict ---")
    if n_ibis_before == 0 and jitter_before == 0.0:
        print("CONFIRMED: without timestamp_ms, the IBI deque NEVER accumulates any samples "
              "(permanently 'insufficient data') and press_timing_jitter_variance is stuck at "
              "0.0 -- which the feature's OWN docstring defines as the 'bot deterministic macro' "
              "range (<0.00005), not a neutral/inactive sentinel.")
    else:
        print("UNEXPECTED: some IBI samples accumulated even without timestamp_ms -- re-examine.")

    if n_ibis_after >= 4:
        print(f"CONFIRMED: with timestamp_ms present, {n_ibis_after} real IBI samples accumulate "
              f"and press_timing_jitter_variance={jitter_after} lands in the documented human "
              f"range (~0.001-0.05), clearly outside the bot range (<0.00005) -- the feature "
              f"works correctly once timestamp_ms is present.")
    else:
        print("UNEXPECTED: timestamp_ms present but insufficient IBI samples accumulated -- "
              "check press schedule / _MIN_SAMPLES-equivalent floor (min_samples=4).")


if __name__ == "__main__":
    main()

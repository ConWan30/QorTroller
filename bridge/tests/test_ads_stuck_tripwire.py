"""D-CERT-5 tripwire (Increment B) — StuckTripwire against synthetic crosscheck patterns.

The load-bearing gate on the calibration corpus's validity: a SUSTAINED one-directional raw-high/pyds-low
disagreement (the 113/113 stuck pattern) MUST trip; edge-skew clusters (brief, at a transition) MUST NOT.
Built + tested BEFORE the runner wraps it. Pure, no rig.
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from l9_presence.ads_coupling import StuckTripwire, DEFAULT_L2_THRESHOLD

THR = DEFAULT_L2_THRESHOLD   # 40
HIGH, LOW = 255, 0


def test_sustained_stuck_trips():
    tw = StuckTripwire(n_trip=3)
    assert tw.observe(HIGH, LOW, THR) is False   # run 1
    assert tw.observe(HIGH, LOW, THR) is False   # run 2
    assert tw.observe(HIGH, LOW, THR) is True     # run 3 -> TRIP
    assert tw.tripped is True


def test_edge_skew_does_not_trip():
    # a release edge: raw lags pyds by 1-2 observations, then agrees -> brief stuck run, never reaches n_trip
    tw = StuckTripwire(n_trip=3)
    tw.observe(HIGH, HIGH, THR)   # held (agree)
    tw.observe(HIGH, LOW, THR)    # release edge-skew: raw still high, pyds dropped (run 1)
    tw.observe(HIGH, LOW, THR)    # raw lags one more (run 2)
    tw.observe(LOW, LOW, THR)     # raw drops -> agree -> reset
    assert tw.tripped is False


def test_legitimate_hold_never_trips():
    tw = StuckTripwire(n_trip=3)
    for _ in range(20):
        tw.observe(HIGH, HIGH, THR)   # both high (scoped hold) -> agree
    assert tw.tripped is False


def test_opposite_direction_does_not_trip_and_resets():
    tw = StuckTripwire(n_trip=3)
    tw.observe(HIGH, LOW, THR)    # run 1 (stuck direction)
    tw.observe(HIGH, LOW, THR)    # run 2
    tw.observe(LOW, HIGH, THR)    # OPPOSITE (raw low, pyds high) -> reset
    tw.observe(HIGH, LOW, THR)    # run 1 again
    tw.observe(HIGH, LOW, THR)    # run 2 -> still < 3
    assert tw.tripped is False


def test_run_resets_on_agreement():
    tw = StuckTripwire(n_trip=3)
    tw.observe(HIGH, LOW, THR); tw.observe(HIGH, LOW, THR)   # run 2
    tw.observe(LOW, LOW, THR)                                # agree -> reset
    tw.observe(HIGH, LOW, THR); tw.observe(HIGH, LOW, THR)   # run 2 again
    assert tw.tripped is False                              # never 3 consecutive


def test_latches_once_tripped():
    tw = StuckTripwire(n_trip=2)
    tw.observe(HIGH, LOW, THR); tw.observe(HIGH, LOW, THR)   # trips
    assert tw.tripped is True
    tw.observe(HIGH, HIGH, THR)   # agree -> stays tripped (latching; a trip is halt-and-look)
    assert tw.tripped is True


def test_threshold_sense_not_byte_exact():
    tw = StuckTripwire(n_trip=1)
    assert tw.observe(THR - 1, THR - 5, THR) is False   # both below thr -> agree (not stuck)
    assert tw.observe(THR, THR - 1, THR) is True        # raw at thr, pyds below -> stuck


def test_status_diagnostics():
    tw = StuckTripwire(n_trip=5)
    for _ in range(3):
        tw.observe(HIGH, LOW, THR)
    st = tw.status()
    assert st["tripped"] is False and st["current_run"] == 3
    assert st["max_run"] == 3 and st["stuck_observations"] == 3

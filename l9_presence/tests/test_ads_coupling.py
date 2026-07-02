"""Tests for l2_ads — ADS coupling channel (second anti-splice channel; scaffold, honest-abstain, raw-first).

Covers the three binding points (onset transition / held-state / release-exit), the abstain rail, and the
raw-first corpus property (interruptions + exit latency derivable at any threshold)."""
from __future__ import annotations

import l9_presence.ads_coupling as ac


def _event(m, baseline, onset, held, exit_, t0=1000.0, dt=20.0):
    """Drive a full L2 press->hold->release event and return the emitted record.
    onset/held/exit_ are lists of center-ROI scalars for each phase."""
    rec = None
    m.feed(200, baseline, t0)                                   # rising edge (baseline captured)
    for i, v in enumerate(onset, 1):
        r = m.feed(200, v, t0 + i * dt)                         # onset-window samples (<300ms)
        rec = r or rec
    t = t0 + 320.0                                              # cross onset_end -> HELD
    for v in held:
        r = m.feed(200, v, t); rec = r or rec
        t += dt
    rt = t                                                     # release
    r = m.feed(0, exit_[0] if exit_ else baseline, rt); rec = r or rec   # falling edge -> EXIT
    for v in exit_[1:]:
        t += dt
        r = m.feed(0, v, t); rec = r or rec
    r = m.feed(0, exit_[-1] if exit_ else baseline, rt + 520.0); rec = r or rec  # past exit window -> emit
    return rec


def _cal(threshold=30.0, **kw):
    return ac.AdsCouplingMonitor(detector=ac.AdsTransitionDetector(threshold=threshold), **kw)


# --- honest-abstain rail + raw-first corpus (the load-bearing scaffold properties) ---

def test_uncalibrated_abstains_but_still_captures_raw_sequences():
    m = ac.AdsCouplingMonitor()                                # threshold None
    rec = _event(m, 10.0, [80.0, 85.0], [82.0, 84.0, 83.0], [12.0, 10.0])
    assert rec["verdict"] == ac.ADS_ABSTAIN_UNCALIBRATED
    assert rec["calibrated"] is False
    # raw-first: the corpus still carries the held + exit signal so it's derivable once calibrated
    assert len(rec["held_seq"]) >= 2 and len(rec["exit_seq"]) >= 1
    assert rec["held_scoped_frac"] is None and rec["scope_exit_latency_ms"] is None


def test_never_fabricates_a_verdict_when_uncalibrated():
    d = ac.AdsTransitionDetector(threshold=None)
    assert d.verdict(10.0, [90.0]) == ac.ADS_ABSTAIN_UNCALIBRATED
    assert d.is_scoped(10.0, 90.0) is None


# --- binding point 1: onset transition ---

def test_onset_transition_bound_when_calibrated():
    rec = _event(_cal(30.0), 5.0, [70.0, 72.0], [71.0], [6.0])
    assert rec["verdict"] == ac.ADS_TRANSITION_BOUND
    assert rec["transition_magnitude"] >= 30.0


def test_splice_negative_l2_without_screen_transition_is_absent():
    """Anti-splice case: live L2 but the replayed screen does NOT transition in response -> flat -> ABSENT."""
    rec = _event(_cal(30.0), 50.0, [50.5, 49.8], [50.2], [50.0])
    assert rec["verdict"] == ac.ADS_TRANSITION_ABSENT


# --- binding point 2: held-state, and the interruption discriminator ---

def test_held_clean_dip_vs_flicker_distinguished_at_same_fraction():
    """A 0.8 scoped-fraction from ONE clean dip must be distinguishable from flicker. Both ~0.8 frac, but
    different interruption counts — the raw held_seq makes this derivable."""
    base = 0.0
    scoped, un = 70.0, 5.0                                      # scoped >= 30 above baseline; un < 30
    clean = [scoped] * 8 + [un] * 2                             # one contiguous dip
    flick = [scoped, un, scoped, un, scoped, un, scoped, un, scoped, scoped]  # flickering
    rc = _event(_cal(30.0), base, [scoped], clean, [un])
    rf = _event(_cal(30.0), base, [scoped], flick, [un])
    assert rc["held_interruptions"] < rf["held_interruptions"]  # flicker has MORE interruptions
    assert rc["held_interruptions"] == 1                        # one clean scoped->unscoped edge


def test_held_scoped_frac_present_when_calibrated():
    rec = _event(_cal(30.0), 0.0, [70.0], [72.0, 71.0, 73.0, 70.0], [5.0])
    assert rec["held_scoped_frac"] is not None and rec["held_scoped_frac"] >= 0.5


# --- binding point 3: release -> scope exit ---

def test_release_edge_captured_and_exit_latency_derived():
    """The third binding point: on release the scope exits. release_ts + exit_seq are always captured;
    scope_exit_latency_ms is derived when calibrated (first post-release sample back under threshold)."""
    rec = _event(_cal(30.0), 0.0, [70.0], [72.0, 71.0], [70.0, 6.0, 4.0])  # stays scoped 1 sample, then exits
    assert rec["release_ts_ms"] is not None
    assert len(rec["exit_seq"]) >= 2
    assert rec["scope_exit_latency_ms"] is not None            # exit detected within the exit window


def test_exit_latency_none_when_uncalibrated_but_raw_kept():
    rec = _event(ac.AdsCouplingMonitor(), 0.0, [70.0], [72.0], [70.0, 5.0])
    assert rec["scope_exit_latency_ms"] is None
    assert len(rec["exit_seq"]) >= 1                            # raw still there for later derivation


# --- state-machine mechanics ---

def test_long_hold_emits_truncated_without_waiting_for_release():
    m = _cal(30.0, max_hold_ms=200.0)
    m.feed(200, 0.0, 1000.0)                                    # rising
    m.feed(200, 70.0, 1400.0)                                   # past onset (300) -> HELD boundary sample
    rec = m.feed(200, 71.0, 1450.0)                            # now-onset >= max_hold(200) -> emit truncated
    assert rec is not None and rec["hold_truncated"] is True
    assert rec["release_ts_ms"] is None                        # emitted while still held


def test_default_window_is_tight_300ms_regression_pin():
    m = ac.AdsCouplingMonitor()
    assert m.window_ms == (0.0, 300.0)                          # the parametric anti-splice lever vs R2's 5000
    assert m.l2_threshold == ac.DEFAULT_L2_THRESHOLD == 40


# --- flush(): close a window whose deadline passed mid-tick (loop-1 flush_stale parity) ---

def test_flush_closes_exit_window_past_deadline():
    """A tick's replayed samples can stop before exit_end; flush at a later now_ms emits the event."""
    m = _cal(30.0)
    m.feed(200, 5.0, 1000.0)                                   # rising, baseline 5.0
    m.feed(200, 80.0, 1100.0)                                  # onset sample IN window (1000-1300) -> transition
    m.feed(200, 78.0, 1400.0)                                  # onset closed -> HELD (boundary sample)
    m.feed(0, 78.0, 1500.0)                                    # falling -> EXIT (exit_end = 2000)
    m.feed(0, 6.0, 1550.0)                                     # one exit sample, then samples stop
    assert m._phase == "EXIT"                                  # stuck without a feed past 2000
    rec = m.flush(2100.0)                                      # now_ms past exit_end -> resolve
    assert rec is not None and rec["verdict"] == ac.ADS_TRANSITION_BOUND
    assert m._phase == "IDLE"


def test_flush_truncates_overlong_hold():
    m = _cal(30.0, max_hold_ms=200.0)
    m.feed(200, 5.0, 1000.0)                                   # rising
    m.feed(200, 70.0, 1400.0)                                  # HELD
    rec = m.flush(1500.0)                                      # now-onset (500) >= max_hold (200) -> truncate
    assert rec is not None and rec["hold_truncated"] is True and rec["release_ts_ms"] is None


def test_flush_advances_onset_to_held_without_emitting():
    m = _cal(30.0)
    m.feed(200, 5.0, 1000.0)                                   # ONSET (onset_end 1300)
    rec = m.flush(1350.0)                                      # past onset_end but hold is young
    assert rec is None and m._phase == "HELD"                  # advanced, not emitted


def test_flush_noop_when_idle_or_deadline_not_passed():
    m = _cal(30.0)
    assert m.flush(1000.0) is None                             # IDLE -> nothing
    m.feed(200, 5.0, 1000.0)                                   # ONSET, onset_end 1300
    assert m.flush(1200.0) is None                             # still inside onset window -> no spurious emit


# --- DeviceClockL2Source: ingestion-layer timing fix (unwrap + device->wall anchor) ---

def test_device_clock_unwraps_uint32_wrap_boundary():
    """Rider 2 regression: the sensor timestamp is uint32 @ 3MHz and wraps ~every 24min. Crossing the wrap
    must stay monotonic with continuous spacing — NOT a ~1430s phantom jump."""
    src = ac.DeviceClockL2Source()
    ts = (1 << 32) - 5 * 3000                                  # 5ms of ticks before the wrap
    for i in range(20):                                        # ~1ms/report across the boundary
        src.push_raw(1000.0 + i * 1.0, ts % (1 << 32), 200)
        ts += 3000                                             # +1ms in device ticks
    xs = [w for w, _ in src.drain()]
    assert all(xs[i + 1] > xs[i] for i in range(len(xs) - 1))  # monotonic across the wrap
    assert max(xs) - min(xs) < 100.0                           # ~20ms span, not a missed-wrap 1.4e6ms jump
    assert src.stats()["wraps"] == 1


def test_device_clock_timing_rides_device_not_jittered_wall():
    """Rider 3: device deltas drive the corrected timeline; a small wall error nudges the anchor slowly."""
    src = ac.DeviceClockL2Source()
    src.push_raw(1000.0, 0, 0)                                 # anchor
    src.push_raw(1005.0, 30000, 200)                           # device +10ms; wall says +5ms (jitter)
    ev = src.drain()
    assert abs(ev[1][0] - 1010.0) < 0.5                        # corrected uses device +10ms, not wall +5ms


def test_device_clock_ignores_read_jitter_spike():
    """A delayed/backed-up read spikes wall; the anchor ignores it (err > tol) and rides the device clock."""
    src = ac.DeviceClockL2Source(anchor_tol_ms=50.0)
    src.push_raw(1000.0, 0, 0)
    src.push_raw(1500.0, 9000, 200)                            # wall +500ms spike, device only +3ms
    ev = src.drain()
    assert abs(ev[1][0] - 1003.0) < 1.0                        # rides device (+3ms), not the 500ms spike


def test_device_clock_drain_clears_and_ordered():
    src = ac.DeviceClockL2Source()
    for i in range(5):
        src.push_raw(1000.0 + i, i * 3000, 200)
    ev = src.drain()
    assert len(ev) == 5 and src.drain() == []                  # drained + cleared
    assert all(ev[i + 1][0] >= ev[i][0] for i in range(4))     # oldest-first

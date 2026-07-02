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

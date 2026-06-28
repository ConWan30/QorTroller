"""Deterministic tests for the L9 cross-channel render-latency invariant (numpy-only, no hardware).

Proves the design claim of s-cross-channel-latency-invariant: a GENUINE session's coupled channels
share ONE pipeline lag (low MAD -> PRESENT_COHERENT), while a FORGED session (active-spectate /
replay-along, where chance-couplings against a screen on someone else's clock have UNshared lags)
reads INCOHERENT or INSUFFICIENT -- never PRESENT. Also pins the fail-open + null-collapse honesty
rails and the calibration verdict discipline (INSUFFICIENT_DATA < N_FLOOR, mirroring the B2 audit).
"""
from __future__ import annotations

import numpy as np
import pytest

from l9_presence import cross_channel_latency as X
from l9_presence.cross_channel_latency import (
    CalibrationVerdict,
    ChannelLag,
    LatencyVerdict,
)

_NAMES = ["b1_flash", "b2_killmark", "geo_pan", "ads_fov"]


# ---------------------------------------------------------------------------
# synthetic session builders
# ---------------------------------------------------------------------------

def _genuine(rng, n=4, L=50.0, jitter=8.0, coupling=0.40):
    """All channels driven by the live player -> lags cluster at L +/- jitter, nulls collapsed."""
    return [ChannelLag(_NAMES[i], coupling + rng.normal(0, 0.03), 0.02 + rng.uniform(0, 0.02),
                       L + rng.normal(0, jitter)) for i in range(n)]


def _forged(rng, n=4):
    """Active-spectate fire-along: channels couple weakly by chance against a screen on a clock the
    forger's trigger does NOT drive -> each chance-coupling lands at an unrelated point across the
    pipeline window (no shared lag). Margins clear the null guard (the chance-couplings are real
    correlations, just not co-clocked), so the gate must reject them on LAG DISAGREEMENT, not score."""
    anchors = [40.0, 150.0, 260.0, 370.0]   # unrelated lags -> large MAD, no shared clock
    return [ChannelLag(_NAMES[i], rng.uniform(0.15, 0.30), rng.uniform(0.0, 0.04),
                       anchors[i] + rng.normal(0, 15)) for i in range(n)]


# ---------------------------------------------------------------------------
# the gate
# ---------------------------------------------------------------------------

def test_present_coherent_when_channels_share_one_lag():
    rng = np.random.default_rng(7)
    r = X.assess_latency_agreement(_genuine(rng))
    assert r.verdict is LatencyVerdict.PRESENT_COHERENT
    assert r.n_coupled == 4
    assert r.lag_spread_ms is not None and r.lag_spread_ms <= X.TAU_LAG_MS
    assert set(r.coupled_channels) == set(_NAMES)


def test_incoherent_when_coupled_but_lags_disagree():
    # four channels all clear the null-collapse guard, but their lags are spread across the pipeline
    chans = [ChannelLag("b1_flash", 0.30, 0.02, 10.0),
             ChannelLag("b2_killmark", 0.28, 0.03, 120.0),
             ChannelLag("geo_pan", 0.33, 0.02, 250.0),
             ChannelLag("ads_fov", 0.31, 0.02, 380.0)]
    r = X.assess_latency_agreement(chans)
    assert r.verdict is LatencyVerdict.INCOHERENT_NO_SHARED_CLOCK
    assert r.lag_spread_ms > X.TAU_LAG_MS


def test_single_coupled_channel_refuses_to_certify():
    # exactly the B2-too-thin case: one channel coupled, everything else abstained
    chans = [ChannelLag("b2_killmark", 0.45, 0.02, 60.0),
             ChannelLag("b1_flash", 0.03, 0.02, 50.0)]   # b1 null did NOT collapse -> excluded
    r = X.assess_latency_agreement(chans)
    assert r.verdict is LatencyVerdict.INSUFFICIENT_CHANNELS
    assert r.n_coupled == 1


def test_unverifiable_when_no_channel_clears_null_guard():
    chans = [ChannelLag("b1_flash", 0.04, 0.02, 50.0),    # margin 0.02 < 0.05
             ChannelLag("b2_killmark", 0.06, 0.03, 55.0)]  # margin 0.03 < 0.05
    r = X.assess_latency_agreement(chans)
    assert r.verdict is LatencyVerdict.UNVERIFIABLE
    assert r.n_coupled == 0


def test_null_suspect_channel_is_excluded_and_surfaced():
    # b2 has high coupling but its null did NOT collapse (spurious) -> excluded + surfaced as suspect;
    # the two genuine channels still carry the agreement call
    chans = [ChannelLag("b1_flash", 0.40, 0.02, 48.0),
             ChannelLag("geo_pan", 0.38, 0.03, 52.0),
             ChannelLag("b2_killmark", 0.50, 0.49, 300.0)]  # coupling high but margin 0.01 -> suspect
    r = X.assess_latency_agreement(chans)
    assert r.verdict is LatencyVerdict.PRESENT_COHERENT
    assert "b2_killmark" not in r.coupled_channels
    assert "b2_killmark" in r.evidence["null_suspect_channels"]


def test_mad_robust_to_one_noisy_genuine_channel():
    # three tight + one noisy channel: median/MAD stays coherent (a forger cannot HURT a genuine
    # session, and one jittery channel does not break a real shared clock)
    chans = [ChannelLag("b1_flash", 0.40, 0.02, 48.0),
             ChannelLag("b2_killmark", 0.38, 0.02, 50.0),
             ChannelLag("geo_pan", 0.41, 0.02, 52.0),
             ChannelLag("ads_fov", 0.39, 0.02, 95.0)]   # the noisy one
    r = X.assess_latency_agreement(chans)
    assert r.verdict is LatencyVerdict.PRESENT_COHERENT


def test_empty_input_is_unverifiable_not_a_crash():
    r = X.assess_latency_agreement([])
    assert r.verdict is LatencyVerdict.UNVERIFIABLE
    assert r.lag_center_ms is None and r.lag_spread_ms is None


# ---------------------------------------------------------------------------
# the calibration harness
# ---------------------------------------------------------------------------

def test_calibrate_insufficient_data_below_floor():
    rng = np.random.default_rng(1)
    g = [_genuine(rng) for _ in range(5)]
    f = [_forged(rng) for _ in range(5)]
    c = X.calibrate_tau_lag(g, f)
    assert c.verdict is CalibrationVerdict.INSUFFICIENT_DATA
    assert c.tau_lag_ms is None
    assert c.n_genuine == 5 and c.n_forged == 5


def test_calibrate_provisional_between_floor_and_production():
    rng = np.random.default_rng(2)
    n_between = 15   # N_FLOOR (10) <= n < N_PRODUCTION (30)
    g = [_genuine(rng) for _ in range(n_between)]
    f = [_forged(rng) for _ in range(n_between)]
    c = X.calibrate_tau_lag(g, f)
    assert c.verdict is CalibrationVerdict.CALIBRATED_PROVISIONAL
    assert c.far is not None and c.far <= X.FAR_TARGET     # FAR-safe selection
    assert c.tau_lag_ms is not None


def test_calibrate_synthetic_separation_is_far_safe():
    # the headline in-principle proof: with full-channel sessions the invariant separates genuine
    # (shared clock) from forged (scattered) at FAR=0 with low FRR -> CALIBRATED.
    rng = np.random.default_rng(42)
    g = [_genuine(rng) for _ in range(40)]
    f = [_forged(rng) for _ in range(40)]
    c = X.calibrate_tau_lag(g, f)
    assert c.verdict is CalibrationVerdict.CALIBRATED
    assert c.far == 0.0                 # zero forged sessions admitted
    assert c.frr <= 0.10                # genuine acceptance >= 90%
    assert 0.0 < c.tau_lag_ms <= 200.0  # a real operating point inside the swept band
    # the chosen tau must actually clear the genuine set it was fit on
    assert X.assess_latency_agreement(g[0], tau_lag_ms=c.tau_lag_ms).verdict is \
        LatencyVerdict.PRESENT_COHERENT


def test_calibrate_no_safe_threshold_reports_best_effort():
    # genuine and forged drawn from the SAME scattered distribution -> no tau both admits genuine
    # (FRR<=ceiling) AND rejects forged (FAR=0); harness must say NO_SAFE_THRESHOLD and still surface
    # a triage operating point, never crash, never falsely CALIBRATED.
    rng = np.random.default_rng(3)
    g = [_forged(rng) for _ in range(30)]   # deliberately mislabeled scattered-as-genuine
    f = [_forged(rng) for _ in range(30)]
    c = X.calibrate_tau_lag(g, f)
    assert c.verdict is CalibrationVerdict.NO_SAFE_THRESHOLD
    assert "best_effort" in c.evidence and "sweep" in c.evidence


def test_calibration_status_is_always_uncalibrated_synthetic():
    # honesty rail #3: the module never claims a live-calibrated score
    rng = np.random.default_rng(9)
    r = X.assess_latency_agreement(_genuine(rng))
    c = X.calibrate_tau_lag([_genuine(rng) for _ in range(30)], [_forged(rng) for _ in range(30)])
    assert r.calibration_status == "UNCALIBRATED_SYNTHETIC"
    assert c.calibration_status == "UNCALIBRATED_SYNTHETIC"

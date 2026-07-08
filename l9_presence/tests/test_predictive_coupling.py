"""LUMEN-3/N5 increment-1 tests — lag-structure coherence.

Pins: consistency math (frame-quantized tolerance); MIN_COUPLING informative gate (the
degenerate zero-lag-on-zero-coupling trap is excluded, never counted as coherence);
INSUFFICIENT fail-open; negative-median incoherent; the pre-registered separation bar
both ways; channel filtering.
"""
from __future__ import annotations

from l9_presence.predictive_coupling import (
    INSUFFICIENT,
    LAG_COHERENT,
    LAG_INCOHERENT,
    assess_separation,
    channel_lag_stats,
)


def _w(lag, coupling=0.4, ch="b2_killmark"):
    return {"channel": ch, "coupling": coupling, "null": 0.02, "lag_ms": lag}


def test_consistent_positive_lags_are_coherent():
    ws = [_w(33.3) for _ in range(10)] + [_w(66.6)]     # 10/11 within tol of median
    s = channel_lag_stats(ws, "b2_killmark")
    assert s.verdict == LAG_COHERENT and s.consistency >= 0.9
    assert s.median_lag_ms == 33.3


def test_scattered_lags_are_incoherent():
    ws = [_w(x) for x in (0, 100, 250, 33, 400, 180, 90, 320, 10, 470)]
    s = channel_lag_stats(ws, "b2_killmark")
    assert s.verdict == LAG_INCOHERENT


def test_zero_coupling_windows_carry_no_lag_information():
    """The degenerate trap: spectate windows often report lag=0 at coupling~0.03 —
    those must be EXCLUDED, never counted as 'consistent'."""
    ws = [_w(0.0, coupling=0.03) for _ in range(20)]
    s = channel_lag_stats(ws, "b2_killmark")
    assert s.verdict == INSUFFICIENT and s.n_informative == 0


def test_insufficient_below_min_windows():
    s = channel_lag_stats([_w(33.3) for _ in range(5)], "b2_killmark")
    assert s.verdict == INSUFFICIENT


def test_negative_median_is_incoherent():
    """Precognition signature: effect preceding cause is never coherent causation."""
    ws = [_w(-50.0) for _ in range(10)]
    s = channel_lag_stats(ws, "b2_killmark")
    assert s.verdict == LAG_INCOHERENT


def test_channel_filtering():
    ws = [_w(33.3, ch="geometric") for _ in range(10)]
    s = channel_lag_stats(ws, "b2_killmark")
    assert s.n_total == 0 and s.verdict == INSUFFICIENT


def test_separation_bar_met():
    genuine = [_w(33.3) for _ in range(12)]
    decoupled = [_w(x) for x in (0, 100, 250, 33, 400, 180, 90, 320, 10, 470, 200, 60)]
    r = assess_separation(genuine, decoupled, channels=("b2_killmark",))
    assert r["separates_any"] is True
    assert r["channels"][0]["separates"] is True
    assert r["advisory"] is True


def test_separation_bar_missed_is_honest():
    genuine = [_w(33.3) for _ in range(12)]
    decoupled = [_w(33.3) for _ in range(12)]      # equally consistent -> no separation
    r = assess_separation(genuine, decoupled, channels=("b2_killmark",))
    assert r["separates_any"] is False
    assert "bar missed" in r["channels"][0]["note"]

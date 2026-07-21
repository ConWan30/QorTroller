"""Composite-B v0 tests — the adversary-tested design (grok r08 PASS residual-accepted).

Pins the load-bearing disciplines: fail-closed pre-conditions, F17 fractional gate, F6 G4-missing
caps at PARTIAL, F19 pure-passive is replayable (max PARTIAL) / optical mandatory for CONTINUOUS,
F2 machine fields never a soft pass, GIC/tournament non-mapping.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from l9_presence.realplay_liveness import (  # noqa: E402
    RealPlayVerdict, WindowFeatures, evaluate_realplay_liveness, device_clock_rate_locked,
    DEVICE_TICKS_PER_MS, W_MIN_CONTINUOUS_S,
)


def _good_window(**over):
    """A fully-passing human-shape window with locked device clock. Override per test."""
    base = dict(
        capture_nominal=True,
        host_exclusive_usb_or_unknown=True,
        gameplay_active_fraction=0.8,
        menu_detected=False,
        tremor_peak_hz=9.5,
        tremor_band_power=0.01,
        l2b_coupled_fraction=0.7,
        press_events=40,
        l5_macro_quantized=False,
        device_ts_span_ticks=int(DEVICE_TICKS_PER_MS * 130_000),  # ~130s of ticks
        wall_span_ms=130_000.0,                                    # matches -> rate locked
        window_s=130.0,
        optical_consistent=None,
    )
    base.update(over)
    return WindowFeatures(**base)


# ---- device-clock rate lock (anti-replay layer 1) ----

def test_rate_lock_ticks_absent_returns_none():
    assert device_clock_rate_locked(None, 1000.0) is None
    assert device_clock_rate_locked(0, 1000.0) is None
    assert device_clock_rate_locked(3_000_000, None) is None


def test_rate_lock_true_when_tracking_wall_clock():
    # 3000 ticks/ms over 1000ms = exactly true rate
    assert device_clock_rate_locked(3_000_000, 1000.0) is True


def test_rate_lock_false_when_off_rate():
    # half the expected ticks -> not locked
    assert device_clock_rate_locked(1_500_000, 1000.0) is False


# ---- fail-closed pre-conditions -> UNVERIFIABLE ----

def test_capture_degraded_unverifiable():
    r = evaluate_realplay_liveness(_good_window(capture_nominal=False))
    assert r.verdict is RealPlayVerdict.UNVERIFIABLE
    assert r.is_pass is False


def test_device_ticks_absent_unverifiable_no_tmono_fallback():
    r = evaluate_realplay_liveness(_good_window(device_ts_span_ticks=0))
    assert r.verdict is RealPlayVerdict.UNVERIFIABLE
    assert "ticks absent" in r.reason


def test_rate_not_locked_unverifiable():
    # ticks present but only half-rate -> fail closed, not PARTIAL
    r = evaluate_realplay_liveness(_good_window(device_ts_span_ticks=int(DEVICE_TICKS_PER_MS * 65_000)))
    assert r.verdict is RealPlayVerdict.UNVERIFIABLE
    assert "rate not locked" in r.reason


def test_window_too_short_unverifiable():
    r = evaluate_realplay_liveness(_good_window(window_s=10.0))
    assert r.verdict is RealPlayVerdict.UNVERIFIABLE


def test_menu_only_unverifiable():
    r = evaluate_realplay_liveness(_good_window(menu_detected=True))
    assert r.verdict is RealPlayVerdict.UNVERIFIABLE
    assert "menu" in r.reason.lower()


def test_gameplay_fraction_below_floor_unverifiable_F17():
    r = evaluate_realplay_liveness(_good_window(gameplay_active_fraction=0.05))
    assert r.verdict is RealPlayVerdict.UNVERIFIABLE


def test_gameplay_fraction_none_invents_no_credit():
    r = evaluate_realplay_liveness(_good_window(gameplay_active_fraction=None))
    assert r.verdict is RealPlayVerdict.UNVERIFIABLE


# ---- human-shape gates ----

def test_absent_tremor_unverifiable():
    r = evaluate_realplay_liveness(_good_window(tremor_peak_hz=None))
    assert r.verdict is RealPlayVerdict.UNVERIFIABLE


def test_out_of_band_tremor_unverifiable():
    r = evaluate_realplay_liveness(_good_window(tremor_peak_hz=2.0))  # below 8-12Hz band
    assert r.verdict is RealPlayVerdict.UNVERIFIABLE


def test_quantized_macro_rhythm_unverifiable():
    r = evaluate_realplay_liveness(_good_window(l5_macro_quantized=True))
    assert r.verdict is RealPlayVerdict.UNVERIFIABLE


def test_decoupled_causal_unverifiable():
    # enough presses but coupling below threshold -> decoupled injection signature
    r = evaluate_realplay_liveness(_good_window(l2b_coupled_fraction=0.1, press_events=40))
    assert r.verdict is RealPlayVerdict.UNVERIFIABLE


# ---- F6: G4 N/A (sparse presses) caps at PARTIAL, never CONTINUOUS ----

def test_sparse_presses_G4_na_caps_at_partial_even_with_optical():
    r = evaluate_realplay_liveness(_good_window(press_events=3, l2b_coupled_fraction=None,
                                                optical_consistent=True))
    assert r.verdict is RealPlayVerdict.PARTIAL_PRESENT   # G4 N/A -> not strong_shape -> no CONTINUOUS
    assert r.replay_resistant is False
    assert r.gate_bitmap["G4_causal"] is None


# ---- F19: pure-passive is REPLAYABLE (max PARTIAL); optical MANDATORY for CONTINUOUS ----

def test_pure_passive_no_optical_is_partial_replayable():
    r = evaluate_realplay_liveness(_good_window(optical_consistent=None))
    assert r.verdict is RealPlayVerdict.PARTIAL_PRESENT
    assert r.replay_resistant is False            # the accepted design ceiling
    assert r.display_tier == "amber"


def test_optical_false_is_partial_not_continuous():
    r = evaluate_realplay_liveness(_good_window(optical_consistent=False))
    assert r.verdict is RealPlayVerdict.PARTIAL_PRESENT
    assert r.replay_resistant is False


def test_optical_true_strong_shape_long_window_is_continuous_replay_resistant():
    r = evaluate_realplay_liveness(_good_window(optical_consistent=True, window_s=130.0))
    assert r.verdict is RealPlayVerdict.CONTINUOUS_PRESENT
    assert r.replay_resistant is True
    assert r.display_tier == "green"


def test_optical_true_but_short_window_stays_partial():
    # optical + strong shape but window < W_MIN_CONTINUOUS -> PARTIAL, not CONTINUOUS
    r = evaluate_realplay_liveness(_good_window(optical_consistent=True,
                                               window_s=W_MIN_CONTINUOUS_S - 1,
                                               device_ts_span_ticks=int(DEVICE_TICKS_PER_MS * 119_000),
                                               wall_span_ms=119_000.0))
    assert r.verdict is RealPlayVerdict.PARTIAL_PRESENT


# ---- machine-field discipline (F2/F14): never a soft pass, never tournament/GIC/poep ----

def test_machine_fields_never_pass_or_tournament_mapped():
    for r in (
        evaluate_realplay_liveness(_good_window(optical_consistent=None)),      # PARTIAL
        evaluate_realplay_liveness(_good_window(optical_consistent=True)),      # CONTINUOUS
        evaluate_realplay_liveness(_good_window(capture_nominal=False)),        # UNVERIFIABLE
    ):
        d = r.to_dict()
        assert d["is_pass"] is False
        assert d["maps_to_tournament_hard_code"] is False
        assert d["advances_poep_enabled"] is False
        assert d["streak_eligible"] is False
        assert d["domain_tag"] == "QORTROLLER-REALPLAY-LIVE-v0"


def test_partial_never_aliases_continuous():
    r = evaluate_realplay_liveness(_good_window(optical_consistent=None))
    assert r.verdict.value != RealPlayVerdict.CONTINUOUS_PRESENT.value
    assert r.verdict.value != "SYNCHRONIZED_CONTROLLER"
    assert r.verdict.value != "SYNCHRONIZED"

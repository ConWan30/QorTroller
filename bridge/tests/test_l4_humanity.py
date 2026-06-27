"""Cycle-36 — live p_L4 re-anchor (l4_humanity.p_l4_from_distance), DEFAULT-OFF + config-gated.

The load-bearing test is byte-identical-when-off: with the flag off the live humanity formula must be
unchanged. Plus the re-anchor endpoints/monotonicity, the not-warmed neutral prior, clamping, and the
headline correction (ON credits a NOMINAL human that OFF under-credits).
"""
from __future__ import annotations

import math

from vapi_bridge.l4_humanity import p_l4_from_distance

THR = 7.009  # default live L4 anomaly threshold


# --- neutral prior (unchanged) ---

def test_not_warmed_is_neutral():
    assert p_l4_from_distance(3.0, False) == 0.5
    assert p_l4_from_distance(3.0, False, reanchor_enabled=True) == 0.5


def test_distance_none_is_neutral():
    assert p_l4_from_distance(None, True) == 0.5
    assert p_l4_from_distance(None, True, reanchor_enabled=True) == 0.5


# --- OFF (default) is BYTE-IDENTICAL to the legacy exp(-(d-2)) ---

def test_off_is_byte_identical_legacy():
    for d in (0.0, 1.0, 2.0, 2.45, 5.0, 7.009, 50.0, 216.0):
        legacy = math.exp(-max(0.0, d - 2.0))
        assert p_l4_from_distance(d, True) == legacy
        assert p_l4_from_distance(d, True, reanchor_enabled=False) == legacy


def test_off_default_flag_value_is_false():
    # the default call (no reanchor kwarg) must equal the legacy formula -> default is OFF
    assert p_l4_from_distance(5.0, True) == math.exp(-3.0)


# --- ON: the corpus-validated re-anchor ---

def test_on_anchor_endpoints():
    assert abs(p_l4_from_distance(0.0, True, reanchor_enabled=True, anomaly_threshold=THR) - 1.0) < 1e-9
    assert abs(p_l4_from_distance(THR, True, reanchor_enabled=True, anomaly_threshold=THR) - 0.5) < 1e-9
    assert abs(p_l4_from_distance(2 * THR, True, reanchor_enabled=True, anomaly_threshold=THR) - 0.25) < 1e-9


def test_on_is_monotonic_decreasing():
    vals = [p_l4_from_distance(d, True, reanchor_enabled=True, anomaly_threshold=THR)
            for d in (0, 1, 3, 5, 8, 20)]
    assert all(a > b for a, b in zip(vals, vals[1:]))


def test_on_clamped_to_unit_interval():
    assert p_l4_from_distance(1e6, True, reanchor_enabled=True, anomaly_threshold=THR) >= 0.0
    assert p_l4_from_distance(0.0, True, reanchor_enabled=True, anomaly_threshold=THR) <= 1.0


def test_on_handles_bad_threshold_without_crash():
    # zero / None threshold falls back to default (no div-by-zero)
    assert 0.0 <= p_l4_from_distance(3.0, True, reanchor_enabled=True, anomaly_threshold=0) <= 1.0
    assert 0.0 <= p_l4_from_distance(3.0, True, reanchor_enabled=True, anomaly_threshold=None) <= 1.0


# --- the headline: ON corrects the under-crediting of a NOMINAL human ---

def test_on_corrects_nominal_human_undercredit():
    d = 5.0  # well under the 7.009 anomaly threshold = a NOMINAL human
    off = p_l4_from_distance(d, True)                                              # ~0.05 (under-credits)
    on = p_l4_from_distance(d, True, reanchor_enabled=True, anomaly_threshold=THR)  # ~0.61 (corrects)
    assert off < 0.1
    assert on > 0.5
    assert on > off

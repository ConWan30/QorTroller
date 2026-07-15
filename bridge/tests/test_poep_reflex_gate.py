"""A2A-POEP-P2 B1+B2 — the reflex-corpus quality gate (grok round-06 tags).

Pins that usable = policy-allowlist AND REFLEX_OBSERVED AND IMU-corroborated AND in-band -- never
REFLEX_OBSERVED alone (which counts the 113 null-route peak=0 junk + CCO device-physics).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from l9_presence.poep_reflex_gate import (
    dedup_bursts, is_usable_reflex, policy_is_reflex,
)


def _u(**kw):
    base = dict(policy_ref="desk_operator_still", reflex_verdict="REFLEX_OBSERVED",
               accel_delta_peak=1038.0, latency_ms=208.0)
    base.update(kw)
    return is_usable_reflex(**base)


# --- B2: category-bleed guard ---------------------------------------------------
def test_allowlist_only_reflex_policies():
    assert policy_is_reflex("desk_operator_still")
    assert policy_is_reflex("edge_operator_reflex_v1")        # future Edge campaign tag
    assert not policy_is_reflex("CCO_T0_POLICY_v1_OPTION_C")  # device-physics, NOT reflex
    assert not policy_is_reflex(None)                         # broken/null route
    assert not policy_is_reflex("desk_operator_squeeze")      # failed protocol


def test_cco_device_physics_never_usable_even_with_strong_imu():
    # a CCO row with a real IMU peak in-band is STILL not a reflex -- category-bleed guard
    assert not _u(policy_ref="CCO_T0_POLICY_v1_OPTION_C", accel_delta_peak=571.0)


def test_null_route_peak0_junk_excluded():
    # the 113 null-policy REFLEX_OBSERVED rows: peak=0, no policy -> excluded twice over
    assert not _u(policy_ref=None, accel_delta_peak=0.0)
    assert not _u(policy_ref="desk_operator_still", accel_delta_peak=0.0)   # peak floor alone catches it


# --- B1: usable filter ----------------------------------------------------------
def test_real_desk_reflex_is_usable():
    assert _u()                                              # allowlist + observed + peak + in-band


def test_out_of_band_and_artifact_excluded():
    assert not _u(latency_ms=59.0)                           # too fast (below 80ms floor)
    assert not _u(latency_ms=400.0)                          # too slow (above 350ms)
    assert not _u(latency_ms=39709.0)                        # 39.7s wall-clock artifact
    assert not _u(reflex_verdict=None)                       # not observed


# --- B1 dedup: independence -----------------------------------------------------
def test_burst_dedup_collapses_correlated_probes():
    # 5 probes 1s apart = 1 effective; spread out = counted
    assert dedup_bursts([0, 1000, 2000, 3000, 4000], min_gap_ms=5000) == 1
    assert dedup_bursts([0, 6000, 12000], min_gap_ms=5000) == 3
    assert dedup_bursts([]) == 0

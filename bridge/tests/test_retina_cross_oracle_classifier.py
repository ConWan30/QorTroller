"""Dry-run cross-oracle classifier mirroring FSCA Retina rules."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.retina_perception import (  # noqa: E402
    RULE_L4_ANOMALY_WITHOUT_RETINA,
    RULE_RETINA_TRAJECTORY_WITHOUT_L4,
    classify_cross_oracle_window,
)

_ANOMALY = 7.009
_CONT = 5.367


def test_quadrant_retina_only():
    """Retina anomaly + low L4 → RETINA_TRAJECTORY_WITHOUT_L4."""
    fired = classify_cross_oracle_window(
        4.0, 2, l4_anomaly_threshold=_ANOMALY, l4_continuity_threshold=_CONT
    )
    assert fired == [RULE_RETINA_TRAJECTORY_WITHOUT_L4]


def test_quadrant_l4_only():
    """High L4 + no retina → L4_ANOMALY_WITHOUT_RETINA."""
    fired = classify_cross_oracle_window(
        8.0, 0, l4_anomaly_threshold=_ANOMALY, l4_continuity_threshold=_CONT
    )
    assert fired == [RULE_L4_ANOMALY_WITHOUT_RETINA]


def test_quadrant_both_agree_anomaly():
    """High L4 + retina anomalies → both rules silent (agreement)."""
    fired = classify_cross_oracle_window(
        8.0, 1, l4_anomaly_threshold=_ANOMALY, l4_continuity_threshold=_CONT
    )
    assert fired == []


def test_quadrant_neither():
    """Low L4 + no retina → neither rule."""
    fired = classify_cross_oracle_window(
        4.0, 0, l4_anomaly_threshold=_ANOMALY, l4_continuity_threshold=_CONT
    )
    assert fired == []


def test_none_l4_fail_open():
    """Missing L4 distance → no rules fire."""
    assert classify_cross_oracle_window(
        None, 5, l4_anomaly_threshold=_ANOMALY, l4_continuity_threshold=_CONT
    ) == []


def test_boundary_at_thresholds():
    """Exact threshold boundaries: l4 == continuity does not fire rule 1; l4 == anomaly fires rule 2 only if count 0."""
    assert classify_cross_oracle_window(
        _CONT, 1, l4_anomaly_threshold=_ANOMALY, l4_continuity_threshold=_CONT
    ) == []
    assert classify_cross_oracle_window(
        _ANOMALY, 0, l4_anomaly_threshold=_ANOMALY, l4_continuity_threshold=_CONT
    ) == [RULE_L4_ANOMALY_WITHOUT_RETINA]

"""Tests for the tri-channel L9 screen-retina fusion (pure logic)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from bridge.vapi_bridge.retina_causal_coherence import CoherenceVerdict  # noqa: E402
from bridge.vapi_bridge.screen_retina_fusion import (  # noqa: E402
    ContinuousAxis,
    L9FusionVerdict,
    classify_continuous,
    fuse_screen_retina,
)


# ---- continuous axis ----

def test_continuous_neutral_when_no_coupling_data():
    assert classify_continuous(None, None, None) is ContinuousAxis.NEUTRAL


def test_continuous_coupled_clean():
    # strong coupling, neg-control collapsed, low residual
    assert classify_continuous(0.85, 0.10, 0.20) is ContinuousAxis.COUPLED_CLEAN


def test_continuous_injection_high_residual():
    assert classify_continuous(0.80, 0.10, 0.70) is ContinuousAxis.COUPLED_INJECTION


def test_continuous_decoupled_when_neg_control_does_not_collapse():
    # high coupling AND high negative control -> latency-search artifact -> DECOUPLED
    assert classify_continuous(0.80, 0.78, 0.10) is ContinuousAxis.DECOUPLED


def test_continuous_decoupled_when_below_threshold():
    assert classify_continuous(0.10, 0.02, 0.10) is ContinuousAxis.DECOUPLED


# ---- fusion verdicts ----

def test_live_coherent_both_axes():
    r = fuse_screen_retina(0.85, 0.10, 0.15, CoherenceVerdict.COHERENT, 1.0)
    assert r.verdict is L9FusionVerdict.LIVE_COHERENT
    assert r.continuous is ContinuousAxis.COUPLED_CLEAN


def test_live_coupled_when_coupling_clean_but_outcomes_thin():
    r = fuse_screen_retina(0.85, 0.10, 0.15, CoherenceVerdict.INSUFFICIENT)
    assert r.verdict is L9FusionVerdict.LIVE_COUPLED


def test_injection_suspect_overrides_coherence():
    r = fuse_screen_retina(0.80, 0.10, 0.75, CoherenceVerdict.COHERENT, 1.0)
    assert r.verdict is L9FusionVerdict.INJECTION_SUSPECT


def test_replay_or_relay_when_decoupled_and_orphan_outcome():
    # camera does not track stick AND HUD advances without input -> strongest cheat signal
    r = fuse_screen_retina(0.80, 0.79, 0.10, CoherenceVerdict.ORPHAN_OUTCOME, 0.0)
    assert r.verdict is L9FusionVerdict.REPLAY_OR_RELAY


def test_replay_or_relay_when_decoupled_and_no_input_caused_outcomes():
    r = fuse_screen_retina(0.10, 0.02, 0.10, CoherenceVerdict.INSUFFICIENT)
    assert r.verdict is L9FusionVerdict.REPLAY_OR_RELAY


def test_decoupled_review_when_axes_contradict_clean_vs_orphan():
    # camera tracks stick cleanly, yet HUD advances without input -> contradiction -> review
    r = fuse_screen_retina(0.85, 0.10, 0.15, CoherenceVerdict.ORPHAN_OUTCOME, 0.2)
    assert r.verdict is L9FusionVerdict.DECOUPLED_REVIEW


def test_decoupled_review_when_decoupled_but_outcomes_coherent():
    r = fuse_screen_retina(0.10, 0.02, 0.10, CoherenceVerdict.COHERENT, 1.0)
    assert r.verdict is L9FusionVerdict.DECOUPLED_REVIEW


def test_neutral_continuous_rests_on_coherence():
    # player not aiming (no coupling) -> verdict from the discrete axis
    assert fuse_screen_retina(None, None, None, CoherenceVerdict.COHERENT, 1.0).verdict \
        is L9FusionVerdict.LIVE_COHERENT
    assert fuse_screen_retina(None, None, None, CoherenceVerdict.ORPHAN_OUTCOME, 0.0).verdict \
        is L9FusionVerdict.REPLAY_OR_RELAY
    assert fuse_screen_retina(None, None, None, CoherenceVerdict.INSUFFICIENT).verdict \
        is L9FusionVerdict.INSUFFICIENT


def test_report_dict_shape_and_uncalibrated():
    r = fuse_screen_retina(0.85, 0.10, 0.15, CoherenceVerdict.COHERENT, 1.0)
    d = r.to_dict()
    assert d["calibration"] == "UNCALIBRATED"
    assert d["verdict"] == "LIVE_COHERENT"
    assert d["neg_control_gap"] == 0.75
    assert d["continuous_axis"] == "COUPLED_CLEAN"


def test_neg_control_gap_none_when_no_coupling():
    d = fuse_screen_retina(None, None, None, CoherenceVerdict.INSUFFICIENT).to_dict()
    assert d["neg_control_gap"] is None

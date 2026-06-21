"""Tests for the replay-through-all-oracles panel (Fusion v2 Phase 3; pure, no hardware)."""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from bridge.vapi_bridge.oracle_panel import (  # noqa: E402
    SessionArtifact,
    derive_input_events,
    derive_screen_events,
    evaluate_artifact,
)
from bridge.vapi_bridge.retina_causal_coherence import CoherenceVerdict  # noqa: E402
from bridge.vapi_bridge.screen_retina_fusion import L9FusionVerdict  # noqa: E402

# 3 down-advance/first-down outcomes at t=3s,6s,9s, each after a trigger onset at 1s,4s,7s
_HUD = [
    (2000.0, "1ST & 10"), (3000.0, "2ND & 6"),
    (5000.0, "2ND & 6"), (6000.0, "3RD & 2"),
    (8000.0, "3RD & 2"), (9000.0, "1ST & 10"),
]


def _streams(n=600, rate_hz=60.0, coupled=True, seed=0):
    import random
    rng = random.Random(seed)
    dt = 1000.0 / rate_hz
    ts = [i * dt for i in range(n)]
    sx = [128 + 60.0 * math.sin(2 * math.pi * 0.8 * t / 1000.0) for t in ts]
    sy = [128 + 8.0 * math.sin(2 * math.pi * 0.3 * t / 1000.0) for t in ts]
    lag = int(round(40.0 / dt))
    yaw = [rng.gauss(0, 0.4) for _ in range(n)]
    if coupled:
        for i in range(lag, n):
            yaw[i] += (sx[i - lag] - 128) * 1.5
    pitch = [rng.gauss(0, 0.4) for _ in range(n)]
    return ts, sx, sy, yaw, pitch


def _fire_with_onsets(ts, onset_times_ms):
    fire = [0.0] * len(ts)
    for k, t in enumerate(ts):
        # fire high for 300ms after each onset time
        if any(ot <= t < ot + 300 for ot in onset_times_ms):
            fire[k] = 200.0
    return fire


def _live_artifact():
    ts, sx, sy, yaw, pitch = _streams(coupled=True)
    fire = _fire_with_onsets(ts, [1000.0, 4000.0, 7000.0])
    return SessionArtifact(in_ts=ts, in_sx=sx, in_sy=sy, mo_ts=ts, mo_yaw=yaw, mo_pitch=pitch,
                           in_fire=fire, hud_texts=_HUD, class_label="HUMAN_CLEAN")


def _replay_artifact():
    ts, sx, sy, yaw, pitch = _streams(coupled=False)  # camera is pure noise (decoupled)
    return SessionArtifact(in_ts=ts, in_sx=sx, in_sy=sy, mo_ts=ts, mo_yaw=yaw, mo_pitch=pitch,
                           in_fire=[0.0] * len(ts),    # no controller input
                           hud_texts=_HUD, class_label="HUMAN_RELAY")  # HUD advances anyway


# ---- derivation ----

def test_derive_input_events_from_fire_onsets():
    a = _live_artifact()
    ev = derive_input_events(a)
    onsets = [e for e in ev if e.type == "controller.trigger.onset"]
    assert len(onsets) == 3  # three rising R2 edges


def test_derive_screen_events_three_outcomes():
    a = _live_artifact()
    se = derive_screen_events(a)
    caused = [e for e in se if e.input_caused]
    assert len(caused) == 3  # two down-advances + one first-down


# ---- panel verdicts ----

def test_live_artifact_is_coherent_and_live():
    r = evaluate_artifact(_live_artifact())
    assert r.coupling_score is not None and r.coupling_score > 0.2
    assert r.negative_control is not None and (r.coupling_score - r.negative_control) > 0.15
    assert r.coherence is CoherenceVerdict.COHERENT
    assert r.fusion_verdict is L9FusionVerdict.LIVE_COHERENT


def test_replay_artifact_is_replay_or_relay():
    r = evaluate_artifact(_replay_artifact())
    # camera decoupled from stick + HUD advances with no input -> strongest cheat signal
    assert r.coherence is CoherenceVerdict.ORPHAN_OUTCOME
    assert r.fusion_verdict is L9FusionVerdict.REPLAY_OR_RELAY


def test_report_dict_uncalibrated_and_labelled():
    d = evaluate_artifact(_live_artifact()).to_dict()
    assert d["calibration"] == "UNCALIBRATED"
    assert d["class_label"] == "HUMAN_CLEAN"
    assert d["fusion_verdict"] == "LIVE_COHERENT"


def test_no_hud_yields_insufficient_coherence():
    ts, sx, sy, yaw, pitch = _streams(coupled=True)
    a = SessionArtifact(in_ts=ts, in_sx=sx, in_sy=sy, mo_ts=ts, mo_yaw=yaw, mo_pitch=pitch,
                        in_fire=_fire_with_onsets(ts, [1000.0]), hud_texts=[], class_label="HUMAN_CLEAN")
    r = evaluate_artifact(a)
    assert r.coherence is CoherenceVerdict.INSUFFICIENT  # no screen channel
    # continuous coupling still proves presence
    assert r.fusion_verdict in (L9FusionVerdict.LIVE_COUPLED, L9FusionVerdict.LIVE_COHERENT)

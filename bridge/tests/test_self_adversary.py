"""Tests for the self-adversarial artifact generators (Fusion v2 Phase 4; pure, no hardware)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# reuse the synthetic-artifact builders from the panel test
from bridge.tests.test_oracle_panel import _live_artifact, _streams  # noqa: E402
from bridge.vapi_bridge.oracle_panel import SessionArtifact, evaluate_artifact  # noqa: E402
from bridge.vapi_bridge.retina_causal_coherence import CoherenceVerdict  # noqa: E402
from bridge.vapi_bridge.screen_retina_fusion import ContinuousAxis, L9FusionVerdict  # noqa: E402
from bridge.vapi_bridge.self_adversary import (  # noqa: E402
    CLASS_BOT_FULL,
    CLASS_HUMAN_INPUT_MACRO,
    CLASS_HUMAN_RELAY,
    make_headless,
    make_injection,
    make_relay,
    make_replay,
)


def _foreign():
    ts, sx, sy, yaw, pitch = _streams(coupled=False, seed=99)  # unrelated camera
    return SessionArtifact(in_ts=ts, in_sx=sx, in_sy=sy, mo_ts=ts, mo_yaw=yaw, mo_pitch=pitch)


def test_replay_collapses_coupling():
    base = evaluate_artifact(_live_artifact())
    rep = evaluate_artifact(make_replay(_live_artifact(), _foreign()))
    assert base.fusion_verdict is L9FusionVerdict.LIVE_COHERENT
    # foreign camera no longer tracks the stick -> coupling collapses far below the live score
    assert rep.coupling_score < base.coupling_score
    assert rep.fusion_verdict in (L9FusionVerdict.REPLAY_OR_RELAY, L9FusionVerdict.DECOUPLED_REVIEW)


def test_replay_label_and_provenance():
    a = make_replay(_live_artifact(), _foreign())
    assert a.class_label == CLASS_HUMAN_RELAY and a.provenance == "real_derived"


def test_relay_orphan_outcome():
    r = evaluate_artifact(make_relay(_live_artifact()))
    # idle controller, screen still advances -> orphan outcomes -> replay/relay
    assert r.coherence is CoherenceVerdict.ORPHAN_OUTCOME
    assert r.fusion_verdict is L9FusionVerdict.REPLAY_OR_RELAY
    assert r.n_input_events == 0


def test_headless_no_render_no_coupling():
    a = make_headless(_live_artifact())
    r = evaluate_artifact(a)
    assert a.class_label == CLASS_BOT_FULL
    # no frames -> no coupling, no screen events; input present but unrendered.
    # ORPHAN_INPUT vs INSUFFICIENT is a calibration threshold (orphan_input_floor); assert structure.
    assert r.coupling_score is None and r.n_screen_events == 0 and r.n_input_events >= 1
    assert r.coherence in (CoherenceVerdict.ORPHAN_INPUT, CoherenceVerdict.INSUFFICIENT)


def test_injection_raises_decoupled_energy():
    base = evaluate_artifact(_live_artifact())
    inj = evaluate_artifact(make_injection(_live_artifact(), strength=2.0))
    assert inj.class_label == CLASS_HUMAN_INPUT_MACRO
    # added decoupled camera motion the stick did not cause -> residual rises
    assert inj.decoupled_energy > base.decoupled_energy


def test_injection_strength_monotonic():
    weak = evaluate_artifact(make_injection(_live_artifact(), strength=1.0))
    strong = evaluate_artifact(make_injection(_live_artifact(), strength=4.0))
    assert strong.decoupled_energy >= weak.decoupled_energy

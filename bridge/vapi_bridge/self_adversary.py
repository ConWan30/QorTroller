"""QorTroller × L9 — self-adversarial artifact generators (Fusion v2 Phase 4).

The N=1 unlock: manufacture ground-truth-labelled adversaries from a real recorded session
using QorTroller's own primitives, so the oracle panel can be calibrated at home without a
real aimbot or a player cohort. Pure transforms over a `SessionArtifact` -> `SessionArtifact`;
each stamps the ground-truth `class_label` + `provenance` so the confusion is honestly labelled.

Lives beside the panel in the bridge (artifact schema is here); l9_presence stays pure.
UNCALIBRATED research only; no FROZEN/PoAC/chain touch. The verdict each produces is the
honest expectation, not a guarantee — that's exactly what the calibration experiment measures.
"""
from __future__ import annotations

import math
from dataclasses import replace

from .oracle_panel import SessionArtifact

# class labels (match l9_presence.adversarial.session_class.SessionClass values)
CLASS_HUMAN_CLEAN = "HUMAN_CLEAN"
CLASS_BOT_FULL = "BOT_FULL"
CLASS_HUMAN_INPUT_MACRO = "HUMAN_INPUT_MACRO"
CLASS_HUMAN_RELAY = "HUMAN_RELAY"
PROV_REAL_DERIVED = "real_derived"


def make_replay(a: SessionArtifact, foreign: SessionArtifact) -> SessionArtifact:
    """REPLAY/RELAY: keep the real HID, but the on-screen camera comes from a DIFFERENT
    session. The camera no longer tracks this stick -> continuous coupling collapses.
    Expected: REPLAY_OR_RELAY (decoupled camera, screen not driven by this controller)."""
    n = min(len(a.mo_ts), len(foreign.mo_yaw), len(foreign.mo_pitch))
    return replace(
        a,
        mo_ts=list(a.mo_ts[:n]),
        mo_yaw=list(foreign.mo_yaw[:n]),     # foreign camera motion
        mo_pitch=list(foreign.mo_pitch[:n]),
        class_label=CLASS_HUMAN_RELAY,
        provenance=PROV_REAL_DERIVED,
    )


def make_relay(a: SessionArtifact) -> SessionArtifact:
    """RELAY: the certified controller is idle (neutral sticks, no trigger) while a real
    screen advances (someone else plays on device B). No input -> orphan outcomes.
    Expected: ORPHAN_OUTCOME -> REPLAY_OR_RELAY."""
    n = len(a.in_ts)
    return replace(
        a,
        in_sx=[128.0] * n, in_sy=[128.0] * n, in_fire=[0.0] * n,  # idle controller
        class_label=CLASS_HUMAN_RELAY,
        provenance=PROV_REAL_DERIVED,
    )


def make_headless(a: SessionArtifact) -> SessionArtifact:
    """HEADLESS REPLAY: recorded HID replayed with NO rendered screen (no frames, no HUD).
    Input present, no outcomes -> ORPHAN_INPUT. Expected coherence: ORPHAN_INPUT."""
    return replace(
        a,
        mo_ts=[], mo_yaw=[], mo_pitch=[], hud_texts=[],
        class_label=CLASS_BOT_FULL,
        provenance=PROV_REAL_DERIVED,
    )


def make_injection(a: SessionArtifact, strength: float = 1.5, freq_hz: float = 0.17,
                   seed: int = 0) -> SessionArtifact:
    """INJECTION/aim-assist: keep the real stick->camera coupling but ADD decoupled camera
    motion the stick did not cause (a smooth auto-aim sweep). Coupling persists but the
    unexplained-motion residual (decoupled_energy) rises. Expected: raised decoupled_energy
    (-> INJECTION_SUSPECT once past threshold)."""
    import random
    rng = random.Random(seed)
    amp = strength * 30.0
    yaw = list(a.mo_yaw)
    pitch = list(a.mo_pitch)
    for i, t in enumerate(a.mo_ts):
        inj = amp * math.sin(2 * math.pi * freq_hz * (t / 1000.0)) + rng.gauss(0, amp * 0.1)
        if i < len(yaw):
            yaw[i] += inj                    # decoupled component independent of the stick
        if i < len(pitch):
            pitch[i] += 0.3 * inj
    return replace(
        a, mo_yaw=yaw, mo_pitch=pitch,
        class_label=CLASS_HUMAN_INPUT_MACRO,
        provenance=PROV_REAL_DERIVED,
    )

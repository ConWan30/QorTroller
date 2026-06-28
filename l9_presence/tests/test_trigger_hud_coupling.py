"""Deterministic tests for L9 Channel B1 (trigger→HUD coupling; numpy-only, no I/O, no hardware).

Validates the anti-GCAP claim the geometric channel could NOT make: when your R2 trigger causally
drives the on-screen flash (genuine fire), coupling is HIGH with a COLLAPSING shuffled null; when the
on-screen flashes are someone else's (a spectated replay you pulled the trigger into), your trigger
has no causal relationship to them → coupling LOW, no real margin. That clean separation is exactly
what the soft stick→pan channel lacked (measured live 2026-06-27: real spectate footage produced
stick→pan coupling up to ~0.10, overlapping genuine aim).
"""
from __future__ import annotations

import numpy as np
import pytest

from l9_presence import trigger_hud_coupling as TH


# ---------------------------------------------------------------------------
# synthetic session builders
# ---------------------------------------------------------------------------

def _pulses(ts: np.ndarray, times, width_ms: float = 35.0, amp: float = 255.0) -> np.ndarray:
    """Sum of gaussian pulses at `times` (a fire-pulse / muzzle-flash train)."""
    sig = np.zeros_like(ts)
    for t in times:
        sig = sig + amp * np.exp(-0.5 * ((ts - t) / (width_ms / 2.0)) ** 2)
    return sig


def _human_fire_session(lag_ms=120.0, dur_ms=4000.0, n=14, noise=6.0, seed=0):
    """R2 fire pulses, and on-screen flashes that FOLLOW each fire at a fixed render+stream lag."""
    rng = np.random.default_rng(seed)
    tr_ts = np.arange(0.0, dur_ms, dur_ms / 4000.0)                 # ~1 kHz trigger
    fires = np.sort(rng.uniform(250.0, dur_ms - 250.0, n))
    r2 = _pulses(tr_ts, fires)
    roi_ts = np.arange(0.0, dur_ms, 1000.0 / 60.0)                  # 60 fps center-ROI
    roi = _pulses(roi_ts, fires + lag_ms) + 20.0 + noise * rng.standard_normal(roi_ts.size)
    return tr_ts, r2, roi_ts, roi


def _decoupled_fire_session(dur_ms=4000.0, n=14, noise=6.0, seed=1):
    """You pull R2 (fires), but the on-screen flashes are an INDEPENDENT train — someone else's
    gameplay you are spectating. Your trigger cannot cause them."""
    rng = np.random.default_rng(seed)
    tr_ts = np.arange(0.0, dur_ms, dur_ms / 4000.0)
    fires = np.sort(rng.uniform(250.0, dur_ms - 250.0, n))          # YOUR trigger pulls
    r2 = _pulses(tr_ts, fires)
    roi_ts = np.arange(0.0, dur_ms, 1000.0 / 60.0)
    others = np.sort(rng.uniform(250.0, dur_ms - 250.0, n))         # someone else's flashes (replay)
    roi = _pulses(roi_ts, others) + 20.0 + noise * rng.standard_normal(roi_ts.size)
    return tr_ts, r2, roi_ts, roi


def _fill(o, tr_ts, r2, roi_ts, roi):
    for t, v in zip(tr_ts, r2):
        o.push_trigger(t, v)
    for t, v in zip(roi_ts, roi):
        o.push_roi(t, v)


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

def test_human_fire_couples_with_collapsing_null():
    o = TH.TriggerHudCouplingOracle(); _fill(o, *_human_fire_session())
    f = o.extract_features(); nc = o.negative_control()
    assert f is not None and nc is not None
    assert f.coupling_score > 0.6              # your trigger explains the on-screen flashes
    assert f.coupled is True
    assert f.coupling_score - nc > 0.3         # real causal margin over the time-shuffled null
    assert f.fire_events >= 8
    assert 0.0 <= f.lag_ms <= TH.TH_LAG_MAX_MS


def test_decoupled_replay_does_not_couple():
    o = TH.TriggerHudCouplingOracle(); _fill(o, *_decoupled_fire_session())
    f = o.extract_features()
    assert f is not None
    # your R2 has no causal relationship to someone else's flashes -> low coupling
    assert f.coupling_score < 0.45
    assert f.coupled is False


def test_separation_human_vs_decoupled():
    """The GO/NO-GO: genuine trigger→flash coupling clearly exceeds a spectated replay's — the clean
    anti-GCAP separation the geometric stick→pan channel could not achieve over Remote Play."""
    h = TH.TriggerHudCouplingOracle(); _fill(h, *_human_fire_session())
    d = TH.TriggerHudCouplingOracle(); _fill(d, *_decoupled_fire_session())
    hf, df = h.extract_features(), d.extract_features()
    assert hf is not None and df is not None
    assert hf.coupling_score > df.coupling_score + 0.3


def test_no_trigger_activity_abstains():
    o = TH.TriggerHudCouplingOracle()
    tr_ts = np.arange(0.0, 4000.0, 1.0)
    r2 = np.full(tr_ts.size, 0.0)                                   # not firing
    roi_ts = np.arange(0.0, 4000.0, 1000.0 / 60.0)
    roi = 20.0 + 5.0 * np.sin(2 * np.pi * 1.0 * roi_ts / 1000.0)
    _fill(o, tr_ts, r2, roi_ts, roi)
    assert o.extract_features() is None        # no firing -> undefined (neutral, not a false accusation)
    nc = o.negative_control()                  # diagnostic only; the shuffled null collapses on a flat trigger
    assert nc is None or nc < 0.1


# --- B2 signal extractors: redness (hitmarker) vs luminance (flash) -------------------------------------

def test_center_redness_isolates_red_from_white_flash():
    """The load-bearing B2 distinction: a RED hitmarker spikes redness; a WHITE muzzle flash does NOT
    (R≈G≈B → redness≈0). That is why B2 is hit-specific where B1 is flash-generic."""
    red = np.zeros((40, 40, 3), dtype=np.uint8)
    red[15:25, 15:25, 2] = 255                 # B,G,R order -> a pure-red center patch
    white = np.full((40, 40, 3), 255, dtype=np.uint8)   # a white flash
    assert TH.center_roi_redness(red) > 50.0    # red hitmarker -> high redness
    assert TH.center_roi_redness(white) < 1.0   # white flash -> ~zero redness (B2 correctly ignores it)


def test_center_luminance_tracks_brightness():
    gray_bright = np.full((40, 40), 255.0)
    gray_dark = np.full((40, 40), 5.0)
    assert TH.center_roi_luminance(gray_bright) > 200.0
    assert TH.center_roi_luminance(gray_dark) < 10.0
    assert TH.center_roi_luminance(np.zeros((0, 0))) == 0.0   # empty ROI -> 0.0, never throws

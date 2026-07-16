"""P-WAVE-0 synthetic waveform-shape separability (FLIP-A rung 3 de-risk), demoted per grok round-22.

The honest, NARROW result: the physics shape gate separates the human MODEL from NAIVE canned shapes
(step/pulse/triangle/random) ONLY IF reflexes settle-to-plateau (the tail_slope assumption, UNKNOWN
until real capture). It does NOT bound a SETTLING adversary — those pass the gate, and the harness
reports that limit rather than hiding it. Engineering justification to build rung-2 capture, NOT a
separability result. poep_enabled stays False.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from l9_presence.poep_waveform_shape import (
    FAR_BAR,
    FRR_BAR,
    NAIVE_MACRO_CLASSES,
    SETTLING_ADVERSARY_CLASSES,
    class_pass_rate,
    human_shape_gate,
    separability_report,
    synth_human,
    synth_macro_random,
    synth_macro_step,
    waveform_shape_features,
)


def test_naive_canned_shapes_are_separated():
    r = separability_report()
    assert r["naive_canned_separated"] is True
    assert r["human_frr"] <= FRR_BAR
    assert r["worst_naive_far"] <= FAR_BAR
    for c in NAIVE_MACRO_CLASSES:
        assert class_pass_rate(c) <= FAR_BAR


def test_harness_honestly_reports_it_does_NOT_bound_settling_adversaries():
    # the load-bearing honesty (grok round-22): settling non-reflex shapes PASS the gate; shape alone
    # is not a robust discriminator. The report must SHOW this, not hide it.
    r = separability_report()
    assert r["shape_bounds_settling_adversary"] is False
    assert r["worst_settling_far"] > FAR_BAR          # at least one settling adversary sails through
    assert any(class_pass_rate(c) > FAR_BAR for c in SETTLING_ADVERSARY_CLASSES)


def test_report_is_reproducible_across_processes():
    # grok round-22 bug fix: per-class seed uses adler32, not Python's salted hash()
    a = separability_report(seed=0xF00D)
    b = separability_report(seed=0xF00D)
    assert a["human_frr"] == b["human_frr"]
    assert a["naive_macro_far"] == b["naive_macro_far"]
    assert a["settling_adversary_far"] == b["settling_adversary_far"]


def test_human_model_passes_the_gate():
    rng = random.Random(7)
    passes = sum(1 for _ in range(200) if human_shape_gate(waveform_shape_features(synth_human(rng))))
    assert passes / 200 >= 1.0 - FRR_BAR


def test_naive_step_and_random_fail_hard():
    rng = random.Random(5)
    assert not human_shape_gate(waveform_shape_features(synth_macro_step(rng)))
    assert not human_shape_gate(waveform_shape_features(synth_macro_random(rng)))


def test_human_features_are_physically_sane():
    rng = random.Random(3)
    f = waveform_shape_features(synth_human(rng))
    assert f["overshoot_ratio"] > 0.0
    assert f["max_jerk"] < 1.0
    assert f["rise_sign_changes"] <= 3
    assert f["tail_slope"] > -0.02          # human settles (tail ~flat)

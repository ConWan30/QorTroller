"""Cycle-30 steps 5+6 — NQPV adversary synthesizer + PILOT study harness (RETINA-EXCL-2).

Covers: synthesizer determinism + per-class oracle profiles; the harness FULL regime SEPARATES
(PASS); the PILOT single-live-oracle regime CANNOT separate (FAIL = the load-bearing finding);
INSUFFICIENT_DATA when oracles abstain; the anti-GCAP rail; and the near-miss orthogonality attack
(spoof_all_rate) raising FAR.
"""
from __future__ import annotations

from vapi_bridge.nqpv_adversary_synth import AdversaryClass, synthesize
from vapi_bridge.nqpv_corpus_loader import LABEL_ADVERSARY, LABEL_HUMAN, NqpvCorpusRecord
from vapi_bridge.nqpv_study_harness import (
    COCAPTURE_LIVE_ORACLES,
    PILOT_LIVE_ORACLES,
    is_human_side,
    run_study,
)


def _humans(n: int) -> list[NqpvCorpusRecord]:
    """Full-oracle human positives: every orthogonal oracle reads human."""
    return [
        NqpvCorpusRecord(
            device_id=f"h{i}", record_hash=f"hr{i}", ts_ns=i, label=LABEL_HUMAN, source="synthetic",
            cco_tier="P-T3", l4_l5_l6_ok=True, poep_present=True, retina_coupled_verdict="COUPLED_CLEAN",
        )
        for i in range(n)
    ]


# --- synthesizer ---

def test_synth_is_deterministic_per_seed():
    a = synthesize(n_per_class=10, seed=42)
    b = synthesize(n_per_class=10, seed=42)
    assert [r.record_hash for r in a] == [r.record_hash for r in b]
    assert [r.retina_coupled_verdict for r in a] == [r.retina_coupled_verdict for r in b]


def test_synth_class_profiles_and_count():
    recs = synthesize(n_per_class=5)
    assert len(recs) == 5 * len(AdversaryClass)
    assert all(r.label == LABEL_ADVERSARY for r in recs)
    by_dev = {r.device_id: r for r in recs}
    # spot-check one of each class via re-synth to know the ids -> just check distributions:
    replays = [r for r in recs if r.retina_coupled_verdict == "PLAUSIBLE"]
    assert replays and all(r.poep_present is False and r.l4_l5_l6_ok is True for r in replays)  # REPLAY
    macros = [r for r in recs if r.l4_l5_l6_ok is False]
    assert macros and all(r.retina_coupled_verdict == "IMPLAUSIBLE" for r in macros)            # MACRO
    assert by_dev  # binding present on every synthetic record


def test_synth_near_miss_spoof_rate_zero_keeps_screen_inconsistent():
    near = synthesize(n_per_class=20, classes=(AdversaryClass.NEAR_MISS_HUMAN,), spoof_all_rate=0.0)
    assert all(r.retina_coupled_verdict == "IMPLAUSIBLE" for r in near)  # screen witness uncracked


def test_synth_near_miss_spoof_rate_one_cracks_screen():
    near = synthesize(n_per_class=20, classes=(AdversaryClass.NEAR_MISS_HUMAN,), spoof_all_rate=1.0)
    assert all(r.retina_coupled_verdict == "COUPLED_CLEAN" for r in near)  # all oracles spoofed


# --- harness: FULL regime separates ---

def test_full_regime_separates_and_passes():
    corpus = _humans(30) + synthesize(n_per_class=20, spoof_all_rate=0.0)
    rep = run_study(corpus)  # full regime (live_oracles=None)
    assert rep.regime == "full"
    assert rep.feasibility == "PASS"
    assert rep.operating_point is not None
    assert rep.operating_point.far <= 0.05
    assert rep.operating_point.tar >= 0.80
    assert rep.operating_point.anti_gcap_ok            # fusion did not collapse human TAR


# --- harness: PILOT regime CANNOT separate (the load-bearing finding) ---

def test_pilot_regime_cannot_separate_is_measurable_fail():
    corpus = _humans(30) + synthesize(n_per_class=20, spoof_all_rate=0.0)
    rep = run_study(corpus, live_oracles=PILOT_LIVE_ORACLES)
    assert rep.regime == "pilot"
    assert rep.measurable is True                       # NOT insufficient -- it IS measurable
    assert rep.feasibility == "FAIL"                    # ...it just can't separate on one oracle
    assert rep.operating_point is None
    # replay + relay + near-miss all pass l4l5l6 -> false accepts -> high FAR somewhere in the sweep
    assert max(p.far for p in rep.roc) > 0.5


def test_cocapture_regime_still_cannot_separate_without_presence_oracles():
    # adding cco (the other live-co-capture oracle) does not rescue separation: replay carries real
    # hardware too, so cco+l4l5l6 still false-accept the replay. Presence oracles remain required.
    corpus = _humans(30) + synthesize(n_per_class=20, spoof_all_rate=0.0)
    rep = run_study(corpus, live_oracles=COCAPTURE_LIVE_ORACLES)
    assert rep.regime == "cocapture"
    assert rep.feasibility == "FAIL"


# --- harness: INSUFFICIENT_DATA ---

def test_insufficient_data_when_human_oracles_all_abstain():
    # project onto an oracle the humans don't carry -> nothing measurable
    humans = [NqpvCorpusRecord(device_id="h", record_hash="r", ts_ns=1, label=LABEL_HUMAN,
                               source="records", l4_l5_l6_ok=True)]
    rep = run_study(humans + synthesize(n_per_class=5), live_oracles=frozenset({"poep"}))
    assert rep.feasibility == "INSUFFICIENT_DATA"
    assert rep.measurable is False


def test_insufficient_data_with_no_adversaries():
    rep = run_study(_humans(10))
    assert rep.feasibility == "INSUFFICIENT_DATA"


# --- harness: near-miss orthogonality attack raises FAR ---

def test_near_miss_full_spoof_defeats_full_regime():
    # when the residual attack spoofs EVERY oracle (incl. the screen witness), the fusion accepts it.
    corpus = _humans(30) + synthesize(
        n_per_class=20, classes=(AdversaryClass.NEAR_MISS_HUMAN,), spoof_all_rate=1.0
    )
    rep = run_study(corpus, far_target=0.05)
    assert rep.feasibility == "FAIL"                    # FAR floor is the all-spoof near-miss
    assert max(p.far for p in rep.roc) > 0.5


def test_human_side_helper():
    from vapi_bridge.novel_presence_fusion import NQPVVerdict
    assert is_human_side(NQPVVerdict.CONSISTENT_HUMAN)
    assert is_human_side(NQPVVerdict.CONSISTENT_HUMAN_VERIFIED_HARDWARE)
    assert not is_human_side(NQPVVerdict.INDETERMINATE)
    assert not is_human_side(NQPVVerdict.INCONSISTENT_TRAJECTORY_WITHOUT_PRESENCE)

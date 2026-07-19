"""Population reaction-time band — fixture tests (CI-safe, no gitignored dumps).

Verifies (a) the anticipation floor is the population-safe sub-floor (NOT the single-operator 320ms band
edge, grok F5), (b) the data-driven band estimator is honestly PROVISIONAL until enough operators, (c) a
WIDER population band RAISES the joint worst-case FAR (the same grok-audited math), and (d) the new
SOFT_TOO_FAST verdict routes a fast human below the band to "retry", not "SUSPECTED_BOT". Synthetic only.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "l9_presence"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "scripts"))
from population_band import (  # noqa: E402
    ANTICIPATION_FLOOR_MS, MIN_OPERATORS_FOR_POPULATION, MIN_SAMPLES_PER_OPERATOR,
    population_safe_sub_floor_ms, _percentile, frr_for_band, estimate_population_band,
    single_operator_floor_false_positive_rate,
)
from qortroller_anticheat import detect_session, GO_LO_MS, GO_HI_MS  # noqa: E402
from poep_r2onset_adversarial import _synth_rec, detect_voluntary_go, attack_dead_feed  # noqa: E402
import random  # noqa: E402


# --- the population-safe sub-floor (F5) ---------------------------------------------------------

def test_population_safe_sub_floor_is_anticipation_not_band_edge():
    # The sub-floor MUST be the anticipation boundary (~120ms), NOT the single-operator 320ms band edge.
    assert population_safe_sub_floor_ms() == ANTICIPATION_FLOOR_MS == 120.0
    assert population_safe_sub_floor_ms() < GO_LO_MS  # strictly below the single-operator band floor


def test_f5_single_operator_floor_false_positives_a_fast_operator():
    # F5 DEMO: a fast ~200ms operator is 100% rejected as sub-floor by the single-operator 320ms floor...
    fast = [random.Random(1).gauss(200, 15) for _ in range(50)]
    assert single_operator_floor_false_positive_rate(fast, single_op_floor_ms=GO_LO_MS) == 1.0
    # ...but 0% rejected by the population-safe anticipation floor (all are > 120ms).
    assert single_operator_floor_false_positive_rate(fast, single_op_floor_ms=ANTICIPATION_FLOOR_MS) == 0.0


def test_anticipation_floor_still_rejects_true_sub_human():
    # A genuinely sub-human ~80ms feed IS rejected even by the anticipation floor (it is not a fast human).
    subhuman = [80.0] * 30
    assert single_operator_floor_false_positive_rate(subhuman, single_op_floor_ms=ANTICIPATION_FLOOR_MS) == 1.0


# --- band estimator honesty ---------------------------------------------------------------------

def test_percentile_basic():
    xs = [100.0, 200.0, 300.0, 400.0, 500.0]
    assert _percentile(xs, 0) == 100.0
    assert _percentile(xs, 100) == 500.0
    assert _percentile(xs, 50) == 300.0


def test_frr_for_band_counts_outside_only():
    s = [100.0, 200.0, 300.0, 400.0, 500.0]
    assert frr_for_band(s, 150.0, 450.0) == 0.4          # 100 and 500 are outside -> 2/5
    assert frr_for_band(s, 0.0, 1000.0) == 0.0           # all inside
    assert frr_for_band([], 0.0, 100.0) == 0.0           # empty -> 0.0


def test_single_operator_band_is_provisional():
    rnd = random.Random(2)
    r = estimate_population_band({"opA": [rnd.gauss(344, 20) for _ in range(30)]})
    assert r["provisional"] is True
    assert r["n_operators"] == 1
    assert r["operators_needed"] == MIN_OPERATORS_FOR_POPULATION - 1
    assert r["band_lo_ms"] is not None and r["band_hi_ms"] is not None
    assert r["advisory"] is True


def test_empty_samples_yields_no_band_provisional():
    r = estimate_population_band({"opA": [], "opB": [None]})
    assert r["provisional"] is True
    assert r["band_lo_ms"] is None and r["band_hi_ms"] is None
    assert r["n_samples"] == 0


def test_band_floor_never_below_anticipation_even_for_fast_pool():
    # A pool of very fast (~150ms) reactions must NOT push the band floor below the anticipation boundary.
    rnd = random.Random(3)
    r = estimate_population_band({f"op{i}": [rnd.gauss(150, 10) for _ in range(25)] for i in range(6)})
    assert r["band_lo_ms"] >= ANTICIPATION_FLOOR_MS


def test_enough_operators_and_samples_is_not_provisional():
    rnd = random.Random(4)
    ops = {f"op{i}": [rnd.gauss(340, 25) for _ in range(MIN_SAMPLES_PER_OPERATOR)]
           for i in range(MIN_OPERATORS_FOR_POPULATION)}
    r = estimate_population_band(ops)
    assert r["provisional"] is False
    assert r["operators_needed"] == 0
    assert set(r["per_operator_frr"].keys()) == set(ops.keys())


def test_wider_population_band_raises_worst_case_far():
    # A WIDER population band (+ lower anticipation sub-floor) RAISES the joint worst-case FAR (F4), for a
    # COHERENT band only (grok r03 F1: the >= invariant is scoped to coherent bands).
    rnd = random.Random(5)
    ops = {f"op{i}": [rnd.gauss(300, 60) for _ in range(25)] for i in range(6)}   # spread -> wide COHERENT band
    r = estimate_population_band(ops)
    assert r["degenerate_band"] is False
    assert r["worst_case_far_population_band"] >= r["worst_case_far_single_operator_band"]
    assert 0.0 <= r["worst_case_far_population_band"] <= 1.0


def test_degenerate_band_is_flagged_provisional_with_undefined_far():
    # grok r03 F1/F2: a pool entirely below the anticipation floor -> floor >= ceiling -> DEGENERATE band.
    # It MUST be provisional, flagged, and MUST NOT report a misleadingly-low 0.0 FAR (understatement).
    ops = {f"op{i}": [50.0 + i for _ in range(20)] for i in range(6)}   # all ~50ms, 6 ops x 20 samples
    r = estimate_population_band(ops)
    assert r["degenerate_band"] is True
    assert r["provisional"] is True                         # count gates alone cannot stamp it non-provisional
    assert r["worst_case_far_population_band"] is None      # UNDEFINED, not a false 0.0 < single_op_far
    assert r["band_lo_ms"] >= r["band_hi_ms"]               # the inversion is surfaced, not hidden
    assert "DEGENERATE" in r["far_note"]


def test_far_understatement_invariant_cannot_be_violated_by_degenerate_band():
    # The old bug: a degenerate band returned pop_far=0.0 < single_op_far=3.2e-4 (reversed >= invariant).
    # Now pop_far is None for degenerate bands, so no numeric comparison can be silently reversed.
    ops = {f"op{i}": [50.0] * 20 for i in range(6)}
    r = estimate_population_band(ops)
    assert r["worst_case_far_population_band"] is None
    assert r["worst_case_far_single_operator_band"] > 0.0


# --- SOFT_TOO_FAST routing (per-fire + session) -------------------------------------------------

def test_fast_human_is_soft_not_bot_under_population_band():
    # onset 200ms: single-op floor -> REJECT_TOO_FAST (F5 false-positive); population band -> SOFT_TOO_FAST.
    rec = _synth_rec(200.0)
    assert detect_voluntary_go(rec)["verdict"] == "REJECT_TOO_FAST"                    # single-op (bug)
    pop = detect_voluntary_go(rec, go_lo_ms=GO_LO_MS, go_hi_ms=GO_HI_MS, sub_floor_ms=ANTICIPATION_FLOOR_MS)
    assert pop["verdict"] == "SOFT_TOO_FAST"                                           # population (fixed)


def test_true_subhuman_still_rejected_under_population_band():
    # onset 80ms is below the anticipation floor -> REJECT_TOO_FAST even with the population sub-floor.
    rec = _synth_rec(80.0)
    pop = detect_voluntary_go(rec, go_lo_ms=GO_LO_MS, go_hi_ms=GO_HI_MS, sub_floor_ms=ANTICIPATION_FLOOR_MS)
    assert pop["verdict"] == "REJECT_TOO_FAST"


def test_detect_session_counts_soft_too_fast_as_soft_not_bot():
    # A session of fast (200ms) humans under the population band -> all SOFT, ZERO sub-floor, so NOT bot.
    recs = [_synth_rec(200.0) for _ in range(6)]
    r = detect_session(recs, go_lo_ms=GO_LO_MS, go_hi_ms=GO_HI_MS, sub_floor_ms=ANTICIPATION_FLOOR_MS)
    assert r["n_soft"] == 6            # all counted as soft (fast-retry), not rejected
    assert r["n_sub_floor"] == 0      # none hit the sub-floor bot rail
    assert r["verdict"] != "SUSPECTED_BOT"


def test_detect_session_default_path_byte_identical_flags_fast_as_bot():
    # Default (single-op) path: the SAME fast session hits the 320ms sub-floor -> SUSPECTED_BOT (F5, unfixed
    # on the default path by design — the population band is the fix, opt-in). Pins the default is unchanged.
    recs = [_synth_rec(200.0) for _ in range(6)]
    r = detect_session(recs)          # defaults: sub_floor = go_lo = 320
    assert r["n_sub_floor"] == 6
    assert r["verdict"] == "SUSPECTED_BOT"


def test_gate_note_disclaims_flag_flip():
    r = estimate_population_band({"opA": [340.0] * 20})
    assert "poep_enabled" in r["gate_note"] and "gates nothing" in r["gate_note"]


# --- grok r05 residuals (F7/F8/F9) --------------------------------------------------------------

def test_detect_session_return_uses_n_soft_not_the_old_key():
    # grok r05 F7: the return key is n_soft (aggregate), the old n_soft_slow is gone. The runner consumer
    # scripts/qortroller_anticheat_report.py was updated to match (verified separately by running it).
    r = detect_session([_synth_rec(345.0) for _ in range(6)])
    assert "n_soft" in r and "n_soft_slow" not in r


def test_detect_session_threads_sub_floor_into_far():
    # grok r05 F8: the SAME in-band session must report a HIGHER blind_bot_far under a population sub-floor
    # (smaller fatal zone -> bigger soft escape) than under the default (sub==go_lo). Verdict is HUMAN_PRESENT
    # in both (in-band GOs); only the reported FAR changes.
    recs = [_synth_rec(345.0) for _ in range(8)]
    default = detect_session(recs)                                              # sub == go_lo == 320
    pop = detect_session(recs, sub_floor_ms=ANTICIPATION_FLOOR_MS)              # sub == 120
    assert default["verdict"] == pop["verdict"] == "HUMAN_PRESENT"
    assert pop["blind_bot_far"] > default["blind_bot_far"]                      # population FAR is higher (F8)


def test_detect_session_far_note_is_config_conditional():
    # grok r05 F9: the far_note must NOT assert the single-op 3.2e-4 envelope for a population config.
    recs = [_synth_rec(345.0) for _ in range(6)]
    default = detect_session(recs)
    pop = detect_session(recs, sub_floor_ms=ANTICIPATION_FLOOR_MS)
    # default: 3.2e-4 IS presented as the envelope. population: 3.2e-4 is EXPLICITLY disclaimed ("does NOT
    # apply") and the note points at worst_case_true_far to compute the real (higher) population envelope.
    assert "3.2e-4" in default["far_note"] and "does NOT apply" not in default["far_note"]
    assert "does NOT apply" in pop["far_note"] and "worst_case_true_far" in pop["far_note"]


def test_far_note_edge_explicit_sub_equal_go_lo_uses_single_op_prose():
    # grok r07 F12: an EXPLICIT sub_floor == go_lo (or >= go_lo) is effectively single-op -> single-op note,
    # NOT the population "does NOT apply" prose (the branch keys on effective sub >= go_lo, not on `is None`).
    recs = [_synth_rec(345.0) for _ in range(6)]
    r = detect_session(recs, sub_floor_ms=GO_LO_MS)          # explicit sub == go_lo == 320
    assert "3.2e-4" in r["far_note"] and "does NOT apply" not in r["far_note"]

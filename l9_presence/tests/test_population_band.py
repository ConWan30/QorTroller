"""Population reaction-time band — fixture tests (CI-safe, no gitignored dumps).

Verifies (a) the anticipation floor is the population-safe sub-floor (NOT a band edge like the old 320ms
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
import json  # noqa: E402
import random  # noqa: E402


def _write_dumps(tmp_path, onset_ms, n):
    for i in range(n):
        (tmp_path / f"d{i}.json").write_text(json.dumps(_synth_rec(float(onset_ms))), encoding="utf-8")
    return str(tmp_path)


# --- the population-safe sub-floor (F5) ---------------------------------------------------------

def test_population_safe_sub_floor_is_anticipation_not_band_edge():
    # The sub-floor MUST be the anticipation boundary (~120ms), NOT a band edge like the old single-op 320ms.
    assert population_safe_sub_floor_ms() == ANTICIPATION_FLOOR_MS == 120.0
    assert population_safe_sub_floor_ms() < GO_LO_MS  # strictly below the measured band floor


def test_f5_single_operator_floor_false_positives_a_fast_operator():
    # F5 DEMO: a fast ~200ms operator is 100% rejected as sub-floor by the OLD single-operator 320ms floor...
    fast = [random.Random(1).gauss(200, 15) for _ in range(50)]
    assert single_operator_floor_false_positive_rate(fast, single_op_floor_ms=320.0) == 1.0
    # ...but 0% rejected by the population-safe anticipation floor (all are > 120ms) — the fix, now the default.
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

def test_fast_human_below_band_is_soft_by_default():
    # A reaction in (sub_floor 120, go_lo 195) is SOFT_TOO_FAST BY DEFAULT (F5 fixed by default); the OLD
    # strict single-op config (sub_floor=320) would wrongly REJECT_TOO_FAST it.
    rec = _synth_rec(150.0)                                             # 120 < 150 < 195
    assert detect_voluntary_go(rec)["verdict"] == "SOFT_TOO_FAST"       # default = population (fixed)
    strict = detect_voluntary_go(rec, sub_floor_ms=320.0)              # old strict floor
    assert strict["verdict"] == "REJECT_TOO_FAST"                       # single-op would flag it a bot


def test_true_subhuman_still_rejected_by_default():
    # onset 80ms is below the 120ms anticipation floor -> REJECT_TOO_FAST even on the default population config.
    assert detect_voluntary_go(_synth_rec(80.0))["verdict"] == "REJECT_TOO_FAST"


def test_detect_session_counts_soft_too_fast_as_soft_not_bot():
    # A session of fast (150ms, below-band) humans on the DEFAULT config -> all SOFT, ZERO sub-floor, NOT bot.
    recs = [_synth_rec(150.0) for _ in range(6)]
    r = detect_session(recs)          # default = population (sub_floor 120)
    assert r["n_soft"] == 6            # all counted as soft (fast-retry), not rejected
    assert r["n_sub_floor"] == 0      # none hit the sub-floor bot rail
    assert r["verdict"] != "SUSPECTED_BOT"


def test_default_is_population_config_strict_is_opt_in():
    # The DEFAULT is now the measured population config: a fast (150ms) below-band session is SOFT, NOT a bot.
    # The OLD strict single-operator behavior is opt-in via sub_floor=320 (then the SAME session is bot-flagged).
    recs = [_synth_rec(150.0) for _ in range(6)]
    default = detect_session(recs)                          # population by default
    assert default["n_sub_floor"] == 0 and default["verdict"] != "SUSPECTED_BOT"
    strict = detect_session(recs, sub_floor_ms=320.0)      # explicit old strict floor
    assert strict["n_sub_floor"] == 6 and strict["verdict"] == "SUSPECTED_BOT"


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
    # grok r05 F8: the SAME in-band session reports a HIGHER blind_bot_far on the DEFAULT population config
    # (sub 120, smaller fatal zone -> bigger soft escape) than on the explicit strict config (sub=go_lo).
    # Verdict is HUMAN_PRESENT in both (in-band GOs); only the reported FAR changes.
    recs = [_synth_rec(345.0) for _ in range(8)]
    default_pop = detect_session(recs)                                          # sub == 120 (population)
    strict = detect_session(recs, sub_floor_ms=GO_LO_MS)                        # sub == go_lo (single-op)
    assert default_pop["verdict"] == strict["verdict"] == "HUMAN_PRESENT"
    assert default_pop["blind_bot_far"] > strict["blind_bot_far"]              # population FAR is higher (F8)


def test_detect_session_far_note_is_config_conditional():
    # grok r05 F9 + F12: the DEFAULT far_note is the POPULATION one (does NOT apply the single-op analytic);
    # an explicit strict sub_floor (>= go_lo) gets the single-op note.
    recs = [_synth_rec(345.0) for _ in range(6)]
    default_pop = detect_session(recs)
    strict = detect_session(recs, sub_floor_ms=GO_LO_MS)
    assert "does NOT apply" in default_pop["far_note"] and "worst_case_true_far" in default_pop["far_note"]
    assert "(band/GO_HI)^K" in strict["far_note"] and "does NOT apply" not in strict["far_note"]


# --- runner CLI: --sub-floor / --population knobs (grok r07 F14) ---------------------------------

def test_runner_default_is_population_fast_session_not_bot(tmp_path, monkeypatch, capsys):
    # DEFAULT (no band knobs) is now the POPULATION config: a fast below-band (150ms) session is SOFT, NOT bot.
    import qortroller_anticheat_report as rpt
    d = _write_dumps(tmp_path, 150.0, 6)
    monkeypatch.setattr(sys, "argv", ["report", "--dir", d, "--isi-ms", "3000"])
    rc = rpt.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "POPULATION" in out and "SOFT=6" in out and "sub_floor=0" in out and "SUSPECTED_BOT" not in out


def test_runner_strict_sub_floor_flags_fast_session_as_bot(tmp_path, monkeypatch, capsys):
    # The OLD strict behavior is opt-in: --sub-floor 320 makes the SAME fast (150ms) session SUSPECTED_BOT.
    import qortroller_anticheat_report as rpt
    d = _write_dumps(tmp_path, 150.0, 6)
    monkeypatch.setattr(sys, "argv", ["report", "--dir", d, "--isi-ms", "3000", "--sub-floor", "320"])
    rc = rpt.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "single-operator (strict)" in out and "SUSPECTED_BOT" in out and "sub_floor=6" in out


def test_runner_population_flag_uses_anticipation_floor(tmp_path, monkeypatch, capsys):
    # --population pins the ~120ms anticipation floor (same as the default now); a 150ms session -> SOFT.
    import qortroller_anticheat_report as rpt
    d = _write_dumps(tmp_path, 150.0, 6)
    monkeypatch.setattr(sys, "argv", ["report", "--dir", d, "--isi-ms", "3000", "--population"])
    rc = rpt.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "sub-floor 120ms" in out and "POPULATION" in out and "SOFT=6" in out


# --- population-band pooling runner (poep_population_band.py) ------------------------------------

def _write_live_file(tmp_path, player, latencies):
    recs = [{"challenge_index": i, "nonce": f"n{i}", "latency_ms": (float(x) if x is not None else None)}
            for i, x in enumerate(latencies)]
    p = tmp_path / f"poep_live_capture_{player}_2026-07-19_00000{len(list(tmp_path.glob('*.json')))}.json"
    p.write_text(json.dumps({"schema": "qortroller-poep-live-capture-v1", "player": player, "records": recs}),
                 encoding="utf-8")
    return p


def test_pooling_groups_by_player_and_reaches_non_provisional(tmp_path, monkeypatch, capsys):
    import poep_population_band as pb
    rnd = random.Random(11)
    _write_live_file(tmp_path, "alice", [rnd.gauss(340, 20) for _ in range(20)])
    _write_live_file(tmp_path, "bob", [rnd.gauss(330, 25) for _ in range(20)])
    monkeypatch.setattr(sys, "argv", ["pb", "--dir", str(tmp_path)])
    rc = pb.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "operator alice: n=20" in out and "operator bob: n=20" in out
    assert "operators: 2" in out and "PROVISIONAL: False" in out
    # the load-bearing honesty rail: labels != verified people
    assert "distinct LABELS, NOT verified distinct people" in out


def test_pooling_drops_no_reaction_latencies_and_windows(tmp_path, monkeypatch, capsys):
    import poep_population_band as pb
    # 20 clean + 3 None (no reaction) + 2 slow outliers (F-RIG27-8-style). None dropped always; slow dropped by --max-ms.
    _write_live_file(tmp_path, "alice", [340.0] * 20 + [None, None, None] + [1600.0, 1800.0])
    monkeypatch.setattr(sys, "argv", ["pb", "--dir", str(tmp_path), "--max-ms", "800"])
    rc = pb.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "FILTER APPLIED" in out
    assert "operator alice: n=20" in out          # 3 None + 2 slow all excluded


def test_pooling_players_filter_scopes_to_real_operators(tmp_path, monkeypatch, capsys):
    import poep_population_band as pb
    _write_live_file(tmp_path, "alice", [340.0] * 20)
    _write_live_file(tmp_path, "bob", [330.0] * 20)
    _write_live_file(tmp_path, "OLD_TESTLABEL", [500.0] * 20)      # ambiguous old label to exclude
    monkeypatch.setattr(sys, "argv", ["pb", "--dir", str(tmp_path), "--players", "alice,bob"])
    rc = pb.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "operator alice" in out and "operator bob" in out and "OLD_TESTLABEL" not in out
    assert "operators: 2" in out


def test_pooling_no_samples_returns_2(tmp_path, monkeypatch, capsys):
    import poep_population_band as pb
    monkeypatch.setattr(sys, "argv", ["pb", "--dir", str(tmp_path)])     # empty dir
    rc = pb.main()
    assert rc == 2


def test_pooling_score_band_is_held_out_not_refit(tmp_path, monkeypatch, capsys):
    # --score-band scores a FRESH capture against a FROZEN band (generalization), it does NOT re-fit.
    import poep_population_band as pb
    # a held-out Con run: 18 inside (202,410], 2 below, 0 above
    lat = [250.0] * 18 + [150.0, 190.0]
    _write_live_file(tmp_path, "ConHeldout", lat)
    monkeypatch.setattr(sys, "argv", ["pb", "--dir", str(tmp_path), "--players", "ConHeldout",
                                      "--min-ms", "120", "--score-band", "202,410"])
    rc = pb.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "HELD-OUT SCORING against the FROZEN band (202, 410]" in out
    assert "in-band=18/20" in out and "held-out FRR=0.1" in out and "below=2 above=0" in out
    # crucially it did NOT print the fitting output (no PROVISIONAL / band-fit line)
    assert "PROVISIONAL:" not in out


def test_pooling_score_band_rejects_bad_arg(tmp_path, monkeypatch, capsys):
    import poep_population_band as pb
    _write_live_file(tmp_path, "X", [250.0] * 20)
    monkeypatch.setattr(sys, "argv", ["pb", "--dir", str(tmp_path), "--score-band", "not-a-band"])
    rc = pb.main()
    assert rc == 2

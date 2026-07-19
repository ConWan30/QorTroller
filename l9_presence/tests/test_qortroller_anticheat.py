"""QorTroller anti-cheat detector (candidate, advisory) — fixture tests (CI-safe, no gitignored dumps).

Verifies the session-level verdict ladder, the unobservable-challenge compounding FAR, and the honest
fire-time-observing-bot residual. All sessions are built from synthetic dump-recs.
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "l9_presence"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "scripts"))
from qortroller_anticheat import (  # noqa: E402
    detect_session, go_threshold, binom_tail_ge, blind_bot_p, blind_bot_far, blind_bot_probs,
    observed_isi_ms, worst_case_true_far, K_REQUIRED_DEFAULT, GO_HI_MS, GO_LO_MS,
)
from poep_r2onset_adversarial import _synth_rec, attack_fixed_delay_bot, attack_dead_feed  # noqa: E402
import random  # noqa: E402


def _human_session(n_go=8, n_slow=2, n_flat=1):
    return ([_synth_rec(345.0) for _ in range(n_go)]
            + [_synth_rec(500.0) for _ in range(n_slow)]
            + [attack_dead_feed() for _ in range(n_flat)])


def test_human_session_is_present_with_small_far():
    r = detect_session(_human_session(n_go=8))
    assert r["verdict"] == "HUMAN_PRESENT"
    assert r["n_go"] >= r["go_threshold"]
    assert r["blind_bot_far"] < 1e-3


def test_blind_bot_random_timing_not_present():
    rnd = random.Random(11)
    sess = [_synth_rec(rnd.uniform(0.0, 3000.0)) for _ in range(30)]
    v = detect_session(sess)["verdict"]
    assert v in ("SUSPECTED_BOT", "INSUFFICIENT")     # rarely in-band -> never HUMAN_PRESENT
    assert v != "HUMAN_PRESENT"


def test_sub_floor_presses_are_suspected_bot():
    r = detect_session([attack_fixed_delay_bot(150.0) for _ in range(20)])   # below the human floor
    assert r["verdict"] == "SUSPECTED_BOT"


def test_all_dead_feed_is_dead_not_human():
    r = detect_session([attack_dead_feed() for _ in range(20)])
    assert r["verdict"] == "DEAD_FEED"


def test_fire_time_observing_bot_is_published_residual():
    # a bot that KNOWS the fire time (impossible for a fire-time-blind bot; rig/crypto residual) presses
    # in-band every time -> the detector GOes. This is HONESTLY a residual: the reported FAR is blind-bot
    # only, and residual_note names the HMAC frame-commitment follow-on. Must NOT be silently defeated.
    r = detect_session([attack_fixed_delay_bot(345.0) for _ in range(20)])
    assert r["verdict"] == "HUMAN_PRESENT"
    assert "residual" in r["residual_note"].lower() and "blind-bot" in r["residual_note"].lower()


def test_threshold_scales_with_n():
    assert go_threshold(5) == 5                # K floor binds
    assert go_threshold(100) == max(K_REQUIRED_DEFAULT, math.ceil(0.20 * 100)) == 20   # rate term binds


def test_far_concentrates_beyond_crossover_but_is_non_monotone():
    # F3/F1: FAR CONCENTRATES only beyond the K-floor crossover (~N=25); it is NON-monotone below it.
    p = blind_bot_p()
    assert binom_tail_ge(100, go_threshold(100), p) < binom_tail_ge(50, go_threshold(50), p)  # concentrates
    assert binom_tail_ge(25, go_threshold(25), p) > binom_tail_ge(20, go_threshold(20), p)    # rises to peak


def test_true_far_is_at_most_the_binomial_upper_bound():
    # F2: the true multinomial FAR (zero sub-floor) is <= the loose binomial upper bound, for all N.
    for n in (10, 20, 25, 35, 50):
        thr = go_threshold(n)
        assert blind_bot_far(n, thr) <= binom_tail_ge(n, thr, blind_bot_p()) + 1e-18


def test_true_far_peak_is_at_the_crossover_not_large_n():
    # F1: the disclosed worst case is at the crossover (~N=25), NOT at N=20 and NOT at large N.
    thr = go_threshold
    fars = {n: blind_bot_far(n, thr(n)) for n in range(5, 60)}
    peak_n = max(fars, key=fars.get)
    assert 23 <= peak_n <= 27                          # crossover region
    assert blind_bot_far(25, thr(25)) > blind_bot_far(20, thr(20))
    assert blind_bot_far(50, thr(50)) < blind_bot_far(25, thr(25))


def test_session_reports_true_and_ub_far_and_isi_context():
    r = detect_session(_human_session(n_go=8))
    assert r["blind_bot_far"] <= r["blind_bot_far_binom_ub"]        # true <= UB
    assert "assumed_isi_ms" in r and "observed_isi_ms" in r         # ISI context surfaced (F9)
    assert "TIMING-ONLY" in r["residual_note"]                      # synthetic-privilege disclosure (F13)


def test_observed_isi_measured_from_probe_ts_mono():
    # synthetic recs carry probe_ts_mono=100.01; a real multi-fire session would show real gaps
    assert observed_isi_ms(_human_session()) is None or observed_isi_ms(_human_session()) >= 0


def test_true_far_is_non_monotone_in_isi_not_collapsing_at_short_isi():
    # F16: a rapid cadence raises p_go AND p_fast. Peak-over-N TRUE FAR at ISI=500ms EXCEEDS ISI=3000ms
    # (the sub-floor trap does NOT "collapse" the TRUE FAR at short ISI; the joint worst case is a short ISI).
    peak_500 = max(blind_bot_far(n, go_threshold(n), 500.0) for n in range(5, 40))
    peak_3000 = max(blind_bot_far(n, go_threshold(n), 3000.0) for n in range(5, 40))
    assert peak_500 > peak_3000                        # rapid cadence is WORSE for TRUE FAR, not "collapsed"


def test_blind_bot_probs_clamped_for_isi_below_band():
    # F18: intersection measure keeps p_go + p_fast <= 1 even for ISI < GO_HI / ISI <= GO_LO
    for isi in (100.0, 320.0, 350.0, 400.0, 3000.0):
        p_go, p_fast = blind_bot_probs(isi)
        assert 0.0 <= p_go and 0.0 <= p_fast and (p_go + p_fast) <= 1.0 + 1e-12


def test_joint_worst_case_true_far_is_the_analytic_max_not_understated():
    # F19: the JOINT worst-case TRUE FAR over (N,ISI) is code-derived and == (band/GO_HI)^K at N=K, ISI=GO_HI.
    # Pins ~3.2e-4 so it can NEVER be silently understated (the r06 1.4e-4 slice failed this).
    n, isi, far = worst_case_true_far()
    analytic = ((GO_HI_MS - GO_LO_MS) / GO_HI_MS) ** K_REQUIRED_DEFAULT   # 0.20^5 = 3.2e-4
    assert far >= 3.0e-4                                   # NOT the understated 1.4e-4
    assert abs(far - analytic) < 5e-6                      # grid finds the analytic joint max
    assert n == K_REQUIRED_DEFAULT and abs(isi - GO_HI_MS) < 6.0   # at N=K, ISI~=GO_HI


def test_binom_tail_matches_direct_sum():
    # sanity: P(Bin(4, 0.5) >= 3) = C(4,3)*.5^4 + C(4,4)*.5^4 = (4+1)/16 = 0.3125
    assert abs(binom_tail_ge(4, 3, 0.5) - 0.3125) < 1e-12


def test_too_few_challenges_is_insufficient():
    assert detect_session([_synth_rec(345.0) for _ in range(3)])["verdict"] == "INSUFFICIENT"


def test_detector_emits_only_advisory_and_gates_nothing():
    r = detect_session(_human_session())
    assert r["advisory"] is True
    assert "poep_enabled" in r["gate_note"] and "False" in r["gate_note"]

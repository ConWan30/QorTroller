"""(ii) R2-onset ADVERSARIAL harness v0 — fixture-only tests (no gitignored dumps; CI-safe).

Verifies: construction attacks REJECT by design; a valid in-band reaction GOes; slow honest taps are SOFT
(not bot); the fixed-delay in-band bot is an HONEST RESIDUAL (FAR=1.0 single-shot, documented not hidden);
the random-bot FAR matches the analytic band_width/ISI.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from poep_r2onset_adversarial import (  # noqa: E402
    detect_voluntary_go, _synth_rec, attack_dead_feed, attack_absurd_t0, attack_naive_replay,
    attack_fixed_delay_bot, attack_random_bot_far, GO_LO_MS, GO_HI_MS, _A,
)


def test_valid_in_band_reaction_goes():
    assert detect_voluntary_go(_synth_rec(345.0))["verdict"] == "GO"


def test_sub_floor_press_rejected():
    v = detect_voluntary_go(attack_fixed_delay_bot(150.0))   # below the 320ms floor
    assert v["verdict"] == "REJECT_TOO_FAST"


def test_slow_honest_tap_is_soft_not_bot():
    v = detect_voluntary_go(_synth_rec(500.0))               # slower than the band -> retry, not a bot
    assert v["verdict"] == "SOFT_TOO_SLOW"


def test_dead_feed_rejected():
    assert detect_voluntary_go(attack_dead_feed())["verdict"] == "REJECT_NO_REACTION"


def test_absurd_t0_rejected():
    assert detect_voluntary_go(attack_absurd_t0())["verdict"] == "REJECT"


def test_naive_replay_rejected_by_construction():
    # a captured response re-fired against a FRESH far t0: the unrelated t0 fails gold-window acceptance
    # -> non-gold (uncertain) reference -> REJECT. Pin the MECHANISM (not just != GO) so the rail can't be
    # a forced-out-of-band-latency artifact (grok adversarial-verify nit).
    donor = _synth_rec(345.0)
    v = detect_voluntary_go(attack_naive_replay(donor, _A + 50_000_000))
    assert v["verdict"] == "REJECT" and "gold" in v["reason"].lower()


def test_no_gold_t0_rejected():
    # without a read-at-fire gold t0 the reference is too uncertain to certify a reaction -> REJECT
    assert detect_voluntary_go(_synth_rec(345.0, gold=False))["verdict"] == "REJECT"


def test_fixed_delay_in_band_bot_is_honest_residual():
    # THE one attack a single challenge cannot beat: a bot at ~345ms GOes. This is the PUBLISHED residual
    # (FAR=1.0 single-shot), the driver for the multi-challenge-variance follow-on. It must NOT be hidden.
    assert detect_voluntary_go(attack_fixed_delay_bot(345.0))["verdict"] == "GO"


def test_random_bot_far_matches_analytic_band_over_isi():
    isi = 3000.0
    far = attack_random_bot_far(isi, trials=40000, seed=1)
    analytic = (GO_HI_MS - GO_LO_MS) / isi
    assert abs(far - analytic) < 0.01           # simulated FAR ~= band_width / ISI

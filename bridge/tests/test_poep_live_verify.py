"""P-LIVE-0 tests (A2A-POEP-P3P4, grok round-16). The nonce-bound verify defeats -- BY CONSTRUCTION --
the two attacks that crushed offline RBM-v0 (A-REPLAY FAR 0.90, A-CONST FAR 0.76), and honestly does
NOT claim to defeat a reactive bot.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from l9_presence.poep_live_verify import (
    ChallengeResponse, LiveChallenge, poep_commitment, response_feature_digest, schedule_commitment,
    verify_live_response,
)

DEV = "581a836c"
T0 = 1_000_000_000_000  # challenge fires (ns)


def _valid_response(nonce, latency_ms=160.0, peak=1500.0, precursor=9.0, dt_ms=160.0):
    t_resp = T0 + int(dt_ms * 1e6)
    fd = response_feature_digest(latency_ms, peak, precursor)
    com = poep_commitment(device_id=DEV, nonce=nonce, feature_digest=fd, ts_ns=t_resp)
    return ChallengeResponse(t_response_ns=t_resp, latency_ms=latency_ms, peak_lsb=peak,
                             precursor_gap_ms=precursor, nonce=nonce, commitment=com)


def test_live_human_response_passes():
    ch = LiveChallenge(DEV, nonce="fresh-nonce-abc", t_challenge_ns=T0)
    assert verify_live_response(ch, _valid_response("fresh-nonce-abc"))["ok"] is True


def test_A_REPLAY_defeated_by_fresh_nonce():
    # attacker replays a response that was valid for an OLD nonce against a FRESH challenge.
    old = _valid_response("old-nonce-from-last-session")
    fresh_ch = LiveChallenge(DEV, nonce="fresh-nonce-now", t_challenge_ns=T0)
    r = verify_live_response(fresh_ch, old)
    assert r["ok"] is False and any("nonce_mismatch" in x for x in r["reasons"])


def test_A_CONST_pre_scheduled_macro_defeated_by_unpredictable_timing():
    # a fixed-schedule macro fires 500ms after ITS expected time, but the real challenge fired later;
    # the response lands outside the [80,300]ms reaction window of the actual challenge.
    ch = LiveChallenge(DEV, nonce="n1", t_challenge_ns=T0)
    early = _valid_response("n1", dt_ms=1500.0)   # 1.5s after challenge -> out of band (too slow / pre-scheduled)
    r = verify_live_response(ch, early)
    assert r["ok"] is False and any("reaction_band" in x for x in r["reasons"])


def test_pre_recorded_before_challenge_defeated():
    ch = LiveChallenge(DEV, nonce="n2", t_challenge_ns=T0)
    resp = _valid_response("n2")
    pre = ChallengeResponse(t_response_ns=T0 - 1000, latency_ms=resp.latency_ms, peak_lsb=resp.peak_lsb,
                            precursor_gap_ms=resp.precursor_gap_ms, nonce="n2", commitment=resp.commitment)
    r = verify_live_response(ch, pre)
    assert r["ok"] is False and any("not_after_challenge" in x for x in r["reasons"])


def test_forged_commitment_defeated():
    ch = LiveChallenge(DEV, nonce="n3", t_challenge_ns=T0)
    good = _valid_response("n3")
    forged = ChallengeResponse(good.t_response_ns, good.latency_ms, good.peak_lsb,
                               good.precursor_gap_ms, "n3", commitment="deadbeef" * 8)
    r = verify_live_response(ch, forged)
    assert r["ok"] is False and r["commitment_ok"] is False


def test_never_claims_presence_verdict_or_flips_poep():
    ch = LiveChallenge(DEV, nonce="n4", t_challenge_ns=T0)
    r = verify_live_response(ch, _valid_response("n4"))
    assert r["is_presence_verdict"] is False and r["poep_enabled"] is False
    assert "NOT yet anti-reactive-bot" in r["claim"]


# --- F-POEP-LIVE-1 (ii): schedule-commitment leg -----------------------------------------------------

DELAY_NS = 7_000_000_000     # 7s committed CSPRNG delay
T_ARM = T0 - DELAY_NS        # arm 7s before the fire -> t_challenge == t_arm + delay exactly


def _sched_challenge(nonce, *, t_challenge=T0, t_arm=T_ARM, delay_ns=DELAY_NS, tamper=None):
    sc = schedule_commitment(nonce=nonce, delay_ns=delay_ns, t_arm_ns=t_arm, t_challenge_ns=t_challenge)
    if tamper == "commitment":
        sc = "deadbeef" * 8
    return LiveChallenge(DEV, nonce, t_challenge, t_arm_ns=t_arm, delay_ns=delay_ns, schedule_commitment=sc)


def test_legacy_challenge_has_schedule_ok_none():
    # 3-field challenge (no schedule leg) -> schedule_ok None, existing behavior byte-identical
    ch = LiveChallenge(DEV, nonce="leg", t_challenge_ns=T0)
    r = verify_live_response(ch, _valid_response("leg"))
    assert r["ok"] is True and r["schedule_ok"] is None


def test_schedule_bound_challenge_verifies():
    ch = _sched_challenge("sch1")
    r = verify_live_response(ch, _valid_response("sch1"))
    assert r["ok"] is True and r["schedule_ok"] is True


def test_schedule_commitment_forgery_fails():
    ch = _sched_challenge("sch2", tamper="commitment")
    r = verify_live_response(ch, _valid_response("sch2"))
    assert r["ok"] is False and r["schedule_ok"] is False
    assert any("schedule_commitment_mismatch" in x for x in r["reasons"])


def test_schedule_drift_fails_when_fire_deviates_from_committed_delay():
    # fire lands 2s after t_arm+delay -> beyond the ~300ms silent pre-collection tolerance
    t_arm = T0 - DELAY_NS
    drifted_challenge = LiveChallenge(
        DEV, "sch3", T0, t_arm_ns=t_arm, delay_ns=DELAY_NS - 2_000_000_000,  # committed delay 2s short
        schedule_commitment=schedule_commitment(
            nonce="sch3", delay_ns=DELAY_NS - 2_000_000_000, t_arm_ns=t_arm, t_challenge_ns=T0),
    )
    r = verify_live_response(drifted_challenge, _valid_response("sch3"))
    assert r["ok"] is False and r["schedule_ok"] is False
    assert any("schedule_drift" in x for x in r["reasons"])

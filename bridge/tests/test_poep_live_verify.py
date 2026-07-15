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
    ChallengeResponse, LiveChallenge, poep_commitment, response_feature_digest, verify_live_response,
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

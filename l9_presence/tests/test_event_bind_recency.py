"""EVENT-BIND increment 3 tests — PoSR recency compose (replay resistance).

Pins: recency verdicts (FRESH/STALE/NO_BEACON/UNVERIFIABLE) incl. the future-block anti-forgery rail;
the compose matrix (crypto+fresh -> REPLAY_RESISTANT; crypto+stale -> SPLICE_PROOF_ONLY = the honest
downgrade that catches the naive replay; temporal -> TEMPORAL_ONLY); boundary at the staleness bar.
"""
from __future__ import annotations

from l9_presence.event_bind import HidOnset, ScreenOutcome, bind_events
from l9_presence.event_bind_recency import (
    DEFAULT_MAX_STALENESS_BLOCKS,
    RecencyVerdict,
    ReplayResistance,
    recency_verdict,
    replay_resistance,
)

_A = "a" * 64
_B = "b" * 64


def _beacon(block):
    return {"block_number": block, "block_hash": "de" * 32, "registry": "0x96", "fetched_at": "t"}


def _crypto_report():
    """A fully splice-proof session (shared anchor)."""
    return bind_events([ScreenOutcome(1000.0, _A)], [HidOnset(1080.0, _A)])


def _temporal_report():
    """A splice / unstamped session (temporal only)."""
    return bind_events([ScreenOutcome(1000.0, _A)], [HidOnset(1080.0, _B)])


# ------------------------------------------------------------------- recency verdict
def test_fresh_within_bar():
    r = recency_verdict(_beacon(1000), 1000 + 100)     # 100 <= 256
    assert r.verdict == RecencyVerdict.FRESH and r.staleness_blocks == 100


def test_stale_beyond_bar():
    r = recency_verdict(_beacon(1000), 1000 + 500)     # 500 > 256
    assert r.verdict == RecencyVerdict.STALE and r.staleness_blocks == 500


def test_boundary_is_fresh():
    r = recency_verdict(_beacon(1000), 1000 + DEFAULT_MAX_STALENESS_BLOCKS)
    assert r.verdict == RecencyVerdict.FRESH


def test_no_beacon():
    assert recency_verdict(None, 1000).verdict == RecencyVerdict.NO_BEACON
    assert recency_verdict({}, 1000).verdict == RecencyVerdict.NO_BEACON


def test_future_block_is_anti_forgery_unverifiable():
    """A beacon claiming a block NEWER than the reference cannot be witnessed against the future."""
    r = recency_verdict(_beacon(2000), 1000)
    assert r.verdict == RecencyVerdict.UNVERIFIABLE


def test_malformed_beacon_unverifiable():
    assert recency_verdict({"block_number": "soon"}, 1000).verdict == RecencyVerdict.UNVERIFIABLE
    assert recency_verdict(_beacon(1000), None).verdict == RecencyVerdict.UNVERIFIABLE


# ------------------------------------------------------------------- compose matrix
def test_crypto_and_fresh_is_replay_resistant():
    rr = replay_resistance(_crypto_report(), _beacon(1000), 1100)
    assert rr.verdict == ReplayResistance.REPLAY_RESISTANT
    assert rr.binding_is_cryptographic is True


def test_crypto_but_stale_is_splice_proof_only():
    """THE increment-3 result: crypto binding passes (splice closed) but a STALE beacon -> replay is
    NOT resisted. This is exactly the naive full-session replay the crypto join alone cannot catch."""
    rr = replay_resistance(_crypto_report(), _beacon(1000), 1000 + 5000)
    assert rr.verdict == ReplayResistance.SPLICE_PROOF_ONLY
    assert rr.recency.verdict == RecencyVerdict.STALE


def test_crypto_but_no_beacon_is_splice_proof_only():
    rr = replay_resistance(_crypto_report(), None, 1100)
    assert rr.verdict == ReplayResistance.SPLICE_PROOF_ONLY


def test_temporal_binding_is_temporal_only_regardless_of_beacon():
    rr = replay_resistance(_temporal_report(), _beacon(1000), 1100)   # fresh, but not crypto
    assert rr.verdict == ReplayResistance.TEMPORAL_ONLY


def test_future_block_makes_compose_unverifiable():
    rr = replay_resistance(_crypto_report(), _beacon(2000), 1000)
    assert rr.verdict == ReplayResistance.UNVERIFIABLE


def test_to_dict_serializable():
    rr = replay_resistance(_crypto_report(), _beacon(1000), 1100)
    d = rr.to_dict()
    assert d["verdict"] == "REPLAY_RESISTANT" and d["staleness_blocks"] == 100
    import json
    assert json.dumps(d)

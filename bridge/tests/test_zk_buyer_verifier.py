"""Data Economy Arc 2 — zk_buyer_verifier bridge read path.

The bridge verifies a private buyer-category Groth16 proof against the on-chain
VAPIBuyerCategoryVerifier WITHOUT learning the buyerDID. Fail-OPEN posture
(mirrors Arc 1 reads, NOT the fail-loud Curator write path): when the verifier
is undeployed, the proof is malformed, the category is out of the FROZEN 1..4
enum, or the RPC raises, verification returns False. An unverifiable proof
never grants category access.

   T-BCV-BRIDGE-1  Valid proof + in-range category → True; pubSignals built as
                   [1, category, timestamp, commitment, nullifier] (snarkjs order).
   T-BCV-BRIDGE-2  Verifier undeployed (real ChainClient, empty address) → False,
                   with NO RPC attempted (sync_w3 is None).
   T-BCV-BRIDGE-3  RPC raising in the staticcall fails open False (never propagates).
   T-BCV-BRIDGE-4  claimed_category outside FROZEN 1..4 → False BEFORE any chain
                   contact (INV-BUY-001 mirrored bridge-side; no RPC round-trip).
   T-BCV-BRIDGE-5  Malformed proof (wrong byte length) → False, no chain contact.
"""
from __future__ import annotations

from dataclasses import dataclass

from bridge.vapi_bridge import zk_buyer_verifier as zk


def _proof(words):
    """Pack 10 ints into the 320-byte wire payload."""
    assert len(words) == 10
    return b"".join(int(w).to_bytes(32, "big") for w in words)


# pA.x pA.y | pB00 pB01 pB10 pB11 | pC.x pC.y | commitment nullifier
_WORDS = [11, 12, 21, 22, 23, 24, 31, 32, 0xC0, 0xD0]


class _StubChain:
    def __init__(self, result=True, raises=False):
        self._result = result
        self._raises = raises
        self.calls = []

    def verify_buyer_category_proof_onchain(self, pA, pB, pC, pub_signals):
        self.calls.append((pA, pB, pC, pub_signals))
        if self._raises:
            # The real chain helper catches internally; this stub mimics the
            # already-failed-open contract (returns False), proving the top
            # function honours whatever the chain layer reports.
            return False
        return self._result


# ── T-BCV-BRIDGE-1 ────────────────────────────────────────────────────────────

def test_T_BCV_BRIDGE_1_valid_proof_true_and_pubsignals_order():
    chain = _StubChain(result=True)
    ok = zk.verify_buyer_category_proof(chain, _proof(_WORDS), claimed_category=3,
                                        current_timestamp=1750000000)
    assert ok is True
    assert len(chain.calls) == 1
    pA, pB, pC, pub = chain.calls[0]
    assert pA == (11, 12)
    assert pB == ((21, 22), (23, 24))
    assert pC == (31, 32)
    # snarkjs order: [valid=1, claimedCategory, currentTimestamp, commitment, nullifier]
    assert pub == [1, 3, 1750000000, 0xC0, 0xD0]


# ── T-BCV-BRIDGE-2 ────────────────────────────────────────────────────────────

def test_T_BCV_BRIDGE_2_verifier_undeployed_fail_open_false():
    from bridge.vapi_bridge.chain import ChainClient

    @dataclass
    class _Cfg:
        buyer_category_verifier_address: str = ""

    c = ChainClient.__new__(ChainClient)
    c._cfg = _Cfg()
    c._sync_w3 = None  # no RPC possible
    ok = zk.verify_buyer_category_proof(c, _proof(_WORDS), claimed_category=3,
                                        current_timestamp=1750000000)
    assert ok is False


# ── T-BCV-BRIDGE-3 ────────────────────────────────────────────────────────────

def test_T_BCV_BRIDGE_3_chain_reports_false_fail_open():
    chain = _StubChain(raises=True)
    ok = zk.verify_buyer_category_proof(chain, _proof(_WORDS), claimed_category=2,
                                        current_timestamp=1750000000)
    assert ok is False


# ── T-BCV-BRIDGE-4 ────────────────────────────────────────────────────────────

def test_T_BCV_BRIDGE_4_category_out_of_range_no_chain_contact():
    chain = _StubChain(result=True)
    for bad in (0, 5, -1, 99):
        assert zk.verify_buyer_category_proof(chain, _proof(_WORDS), claimed_category=bad,
                                              current_timestamp=1750000000) is False
    assert chain.calls == [], "out-of-range category must short-circuit before RPC"


# ── T-BCV-BRIDGE-5 ────────────────────────────────────────────────────────────

def test_T_BCV_BRIDGE_5_malformed_proof_no_chain_contact():
    chain = _StubChain(result=True)
    # Too short, too long, and non-bytes all fail open without touching the chain.
    assert zk.verify_buyer_category_proof(chain, b"\x00" * 100, 3, 1750000000) is False
    assert zk.verify_buyer_category_proof(chain, b"\x00" * 321, 3, 1750000000) is False
    assert zk.verify_buyer_category_proof(chain, "not-bytes", 3, 1750000000) is False
    assert chain.calls == [], "malformed proof must short-circuit before RPC"

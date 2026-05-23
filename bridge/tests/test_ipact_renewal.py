"""Phase B item ③ — VHP renewal cadence (iPACT-DePIN) test vectors.

Covers the seven §5 subcategories of wiki/methodology/ipact_renewal_cadence_v1_scope.md
plus the load-bearing "same construction, not parallel" device_id byte-identity test:

  (a) byte-pinned commitment + genesis KATs (the QorTroller-novel deterministic artifact)
  (b) chain validity (genesis + N-link recompute; tamper breaks)
  (c) replay rejection (duplicate/regressing epoch_index + ts_ns)
  (d) dormant-blind close (enforcement ON → renewal without fresh proof is SKIPPED)
  (e) default-OFF behavior (renewal byte-identical to pre-③; commitment chain still logs)
  (f) regime-agnostic artifact identity (commitment bytes independent of §4.8.5 framing)
  (g) challenge-issuance correctness (fresh nonce per renewal; stale challenge rejected)
  + device_id_to_bytes32 byte-identity vs the live CONSENT family convention.
"""

from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "bridge"))

from vapi_bridge import ipact_renewal as I

# fixed deterministic inputs
DEV = "Sony_DualShock_Edge_CFI-ZCP1"
TOK = 2
TS0 = 1_700_000_000_000_000_000


# ===========================================================================
# (a) byte-pinned KATs — deterministic, QorTroller-owned
# ===========================================================================

def test_domain_tag_widths_frozen():
    assert I._DOMAIN_TAG == b"QORTROLLER-IPACT-RENEWAL-v1"
    assert len(I._DOMAIN_TAG) == 27
    assert I._GENESIS_TAG == b"QORTROLLER-IPACT-RENEWAL-GENESIS-v1"
    assert len(I._GENESIS_TAG) == 35
    assert I.NO_REATTEST_PROOF == b"\x00" * 32
    assert I.IPACT_RENEWAL_EPOCH_DAYS == 90


def test_device_id_32b_kat():
    d32 = I.device_id_to_bytes32(DEV)
    assert d32.hex() == "10e0169446ba3320fcaa486ab8e06a4794e5378418edaa2301335162e6f96062"
    assert d32 == hashlib.sha256(DEV.encode("utf-8")).digest()


def test_genesis_commitment_kat():
    assert I.genesis_commitment(DEV, TOK).hex() == \
        "36e2d0911db62b3096875e586bbcdfda559e90043d1196a89a572dee201a78bd"


def test_commitment_off_kat():
    gen = I.genesis_commitment(DEV, TOK)
    c0 = I.compute_commitment(DEV, TOK, gen, 0, I.NO_REATTEST_PROOF, TS0)
    assert c0.hex() == "4241206df3720e7831fca171850f0f38f24f8d04e7b15a855bd77140f88cea02"


def test_reattest_proof_kat():
    nonce = bytes(range(32))
    sig = b"COMPOSITE_SIG_FIXTURE_BYTES_v1"
    assert I.compute_reattest_proof(nonce, sig).hex() == \
        "20376fca5add4a976f375bf6bc35bf90b630fafd56da55151e4bc0c2af1e0eb8"


def test_commitment_on_kat():
    gen = I.genesis_commitment(DEV, TOK)
    c0 = I.compute_commitment(DEV, TOK, gen, 0, I.NO_REATTEST_PROOF, TS0)
    rp = I.compute_reattest_proof(bytes(range(32)), b"COMPOSITE_SIG_FIXTURE_BYTES_v1")
    c1 = I.compute_commitment(DEV, TOK, c0, 1, rp, TS0 + 1)
    assert c1.hex() == "16c42db9db52aaf8822d01eb75e1cb1144b62ba41d1cbe4e6f0faffa9a4e79ce"


def test_compute_commitment_rejects_bad_widths():
    gen = I.genesis_commitment(DEV, TOK)
    with pytest.raises(ValueError):
        I.compute_commitment(DEV, TOK, b"short", 0, I.NO_REATTEST_PROOF, TS0)
    with pytest.raises(ValueError):
        I.compute_commitment(DEV, TOK, gen, 0, b"short", TS0)


# ===========================================================================
# device_id_to_bytes32 — SAME construction as CONSENT, not parallel
# ===========================================================================

def test_device_id_byte_identical_to_consent_convention():
    from vapi_bridge.consent_categories import device_id_to_bytes32 as consent_fn
    cases = [
        DEV,                       # fallback SHA-256(utf8) branch
        "sony_dualshock_edge_v1",  # fallback branch
        "ab" * 32,                 # 64-char hex branch
        "0x" + "cd" * 32,          # 0x-prefixed hex branch
        hashlib.sha256(b"x").digest(),  # raw 32 bytes branch
    ]
    for c in cases:
        assert I.device_id_to_bytes32(c) == consent_fn(c), f"divergence for {c!r}"


def test_device_id_branches():
    hexdev = "ab" * 32
    assert I.device_id_to_bytes32(hexdev) == bytes.fromhex(hexdev)
    assert I.device_id_to_bytes32("0x" + hexdev) == bytes.fromhex(hexdev)
    raw = hashlib.sha256(b"raw").digest()
    assert I.device_id_to_bytes32(raw) == raw
    with pytest.raises(ValueError):
        I.device_id_to_bytes32(b"\x00" * 31)  # wrong-width raw bytes


# ===========================================================================
# (b) chain validity
# ===========================================================================

def _build_chain(device_id, token_id, n, *, proofs=None):
    """Build n valid chained links. proofs[i] (32B) or NO_REATTEST_PROOF."""
    links = []
    prev = I.genesis_commitment(device_id, token_id)
    for i in range(n):
        proof = (proofs[i] if proofs else I.NO_REATTEST_PROOF)
        ts = TS0 + i
        c = I.compute_commitment(device_id, token_id, prev, i, proof, ts)
        links.append({"epoch_index": i, "reattest_proof": proof, "ts_ns": ts, "commitment": c})
        prev = c
    return links


def test_chain_valid_roundtrip():
    links = _build_chain(DEV, TOK, 5)
    ok, reason = I.verify_chain(DEV, TOK, links)
    assert ok is True and reason == ""


def test_chain_tamper_breaks():
    links = _build_chain(DEV, TOK, 4)
    # tamper the commitment of link 2
    bad = bytearray(links[2]["commitment"]); bad[0] ^= 1
    links[2]["commitment"] = bytes(bad)
    ok, reason = I.verify_chain(DEV, TOK, links)
    assert ok is False and "mismatch" in reason


def test_chain_tamper_reattest_breaks():
    links = _build_chain(DEV, TOK, 3)
    # flip the reattest_proof on link 1 without recomputing → chain breaks
    links[1]["reattest_proof"] = hashlib.sha256(b"forged").digest()
    ok, _ = I.verify_chain(DEV, TOK, links)
    assert ok is False


# ===========================================================================
# (c) replay rejection (verify-chain level)
# ===========================================================================

def test_duplicate_epoch_index_rejected():
    links = _build_chain(DEV, TOK, 2)
    links[1]["epoch_index"] = 0  # regress epoch
    ok, reason = I.verify_chain(DEV, TOK, links)
    assert ok is False and "epoch_index" in reason


def test_regressing_ts_ns_rejected():
    links = _build_chain(DEV, TOK, 2)
    # make link1 chain correctly but with a non-increasing ts → recompute its commitment too
    prev = links[0]["commitment"]
    bad_ts = links[0]["ts_ns"]  # equal to prev → must be rejected
    c = I.compute_commitment(DEV, TOK, prev, 1, I.NO_REATTEST_PROOF, bad_ts)
    links[1] = {"epoch_index": 1, "reattest_proof": I.NO_REATTEST_PROOF,
                "ts_ns": bad_ts, "commitment": c}
    ok, reason = I.verify_chain(DEV, TOK, links)
    assert ok is False and "ts_ns" in reason


# ===========================================================================
# (f) regime-agnostic artifact identity
# ===========================================================================

def test_regime_agnostic_artifact_identity():
    # compute_commitment has NO regime parameter — the bytes depend only on the locked
    # inputs, so the §4.8.5 "refreshable" vs "one-time" framing cannot change the artifact.
    gen = I.genesis_commitment(DEV, TOK)
    a = I.compute_commitment(DEV, TOK, gen, 0, I.NO_REATTEST_PROOF, TS0)
    b = I.compute_commitment(DEV, TOK, gen, 0, I.NO_REATTEST_PROOF, TS0)
    assert a == b
    import inspect
    params = set(inspect.signature(I.compute_commitment).parameters)
    assert "regime" not in params and "refreshable" not in params


# ===========================================================================
# (g) challenge-issuance correctness
# ===========================================================================

def test_fresh_nonce_changes_proof_and_commitment():
    sig = b"sig-fixture"
    p1 = I.compute_reattest_proof(bytes(range(32)), sig)
    p2 = I.compute_reattest_proof(bytes(range(1, 33)), sig)  # different nonce
    assert p1 != p2  # fresh nonce → different proof
    gen = I.genesis_commitment(DEV, TOK)
    c1 = I.compute_commitment(DEV, TOK, gen, 0, p1, TS0)
    c2 = I.compute_commitment(DEV, TOK, gen, 0, p2, TS0)
    assert c1 != c2  # → different commitment


def test_stale_challenge_rejected():
    # a proof computed against an OLD nonce does not match the proof for a NEW nonce
    sig = b"sig-fixture"
    fresh_nonce = bytes(range(32))
    stale_nonce = bytes(range(100, 132))
    proof_for_fresh = I.compute_reattest_proof(fresh_nonce, sig)
    proof_for_stale = I.compute_reattest_proof(stale_nonce, sig)
    assert proof_for_fresh != proof_for_stale


def test_reattest_proof_deterministic_for_fixed_pair():
    nonce, sig = bytes(range(32)), b"abc"
    assert I.compute_reattest_proof(nonce, sig) == I.compute_reattest_proof(nonce, sig)


# ===========================================================================
# (d) + (e) agent-level: dormant-blind close (ON) + default-OFF behavior
# ===========================================================================

class _FakeStore:
    def __init__(self, expiring):
        self._expiring = expiring
        self.vhp_renewals = []
        self.commitments = []  # (device_id, epoch_index, commitment, reattest_proof, enforced)

    def get_expiring_vhps(self, cutoff):
        return list(self._expiring)

    def get_total_vhp_count(self):
        return len(self._expiring) or 1

    def insert_vhp_renewal(self, **kw):
        self.vhp_renewals.append(kw); return len(self.vhp_renewals)

    def get_ipact_renewal_head(self, device_id):
        links = [c for c in self.commitments if c["device_id"] == device_id]
        if not links:
            return None
        last = max(links, key=lambda c: c["epoch_index"])
        return {"commitment": last["commitment"], "epoch_index": last["epoch_index"],
                "ts_ns": last["ts_ns"]}

    def get_prev_ipact_ts_ns(self, device_id):
        links = [c for c in self.commitments if c["device_id"] == device_id]
        return max((c["ts_ns"] for c in links), default=0)

    def insert_ipact_renewal_commitment(self, **kw):
        self.commitments.append(kw); return len(self.commitments)


class _Cfg:
    def __init__(self, enforce):
        self.agent_dry_run_mode = True
        self.ioswarm_renewal_enabled = False
        self.ipact_renewal_enforcement_enabled = enforce


def _make_agent(enforce, proof=None):
    from vapi_bridge.vhp_renewal_agent import VHPRenewalAgent
    store = _FakeStore([{"device_id": DEV, "token_id": TOK, "expires_at": TS0 / 1e9}])
    agent = VHPRenewalAgent(cfg=_Cfg(enforce), store=store, chain=None, bus=None)
    if proof is not None:
        agent._obtain_reattest_proof = lambda vhp: proof  # inject
    return agent, store


def test_default_off_renews_and_logs_commitment():
    # (e) enforcement OFF → renewal proceeds (vhp_renewal recorded) AND commitment chain logs
    agent, store = _make_agent(enforce=False)
    asyncio.run(agent._check_and_renew())
    assert len(store.vhp_renewals) == 1                     # renewal happened (pre-③ behavior)
    assert store.vhp_renewals[0]["new_expires_at"] == \
        pytest.approx(TS0 / 1e9 + I.IPACT_RENEWAL_EPOCH_DAYS * 86_400)
    assert len(store.commitments) == 1                      # commitment chain accumulated
    assert store.commitments[0]["reattest_proof"] == I.NO_REATTEST_PROOF
    assert store.commitments[0]["enforced"] == 0


def test_enforcement_on_without_proof_skips_renewal():
    # (d) enforcement ON + no fresh proof (hook returns None) → renewal SKIPPED
    agent, store = _make_agent(enforce=True, proof=None)
    asyncio.run(agent._check_and_renew())
    assert len(store.vhp_renewals) == 0   # dormant-blind gate: no renewal
    assert len(store.commitments) == 0    # nothing committed either


def test_enforcement_on_with_proof_renews():
    # (d) enforcement ON + valid fresh proof injected → renewal proceeds, enforced=1
    proof = I.compute_reattest_proof(bytes(range(32)), b"composite-sig-blob")
    agent, store = _make_agent(enforce=True, proof=proof)
    asyncio.run(agent._check_and_renew())
    assert len(store.vhp_renewals) == 1
    assert len(store.commitments) == 1
    assert store.commitments[0]["reattest_proof"] == proof
    assert store.commitments[0]["enforced"] == 1

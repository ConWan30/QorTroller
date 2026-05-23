"""Phase B backlog #8 — iPACT renewal handshake wiring tests (§5 of the wiring scope doc).

Covers (a)-(g):
  (a) ① pubkey round-trip (full byte-pinned KATs live in l9_presence/tests/test_composite_sig.py)
  (b) challenge issuance — fresh nonce per call; single-use; TTL expiry
  (c) challenge domain separation — RENEWAL-family-tag sig ≠ CHALLENGE response
  (d) integration: ①↔③ compose (freeze-unlock evidence) — enforced renewal + forged-sig skip
  (e) lazy-import / enforcement-OFF — seam not reached; renewal byte-identical to ③-shipped
  (f) test-key-not-in-production guard — (i) vapi_bridge never imports the fixture; (ii) no-seam → None
  (g) ① regression re-run is a P-check step (run test_composite_sig.py), not duplicated here.
"""

from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))                 # l9_presence
sys.path.insert(0, str(_ROOT / "bridge"))      # vapi_bridge
sys.path.insert(0, str(_ROOT / "bridge" / "tests"))  # fixtures (test-only)

from vapi_bridge import ipact_challenge as IC
from vapi_bridge import ipact_renewal as IR
from vapi_bridge.vhp_renewal_agent import VHPRenewalAgent
from l9_presence import composite_sig as C
from fixtures.ipact_signer_fixture import IpactTestSigner

DEV = "Sony_DualShock_Edge_CFI-ZCP1"
TOK = 2
TS0 = 1_700_000_000_000_000_000


# ===========================================================================
# (a) ① pubkey round-trip (smoke; full KATs in ①'s suite)
# ===========================================================================

def test_pubkey_roundtrip_smoke():
    kp = C.generate_keypair(C.ALG_MLDSA44_ECDSA_P256_SHA256)
    blob = C.encode_pubkey(kp.public())
    assert C.encode_pubkey(C.decode_pubkey(blob)) == blob


# ===========================================================================
# (b) challenge issuance
# ===========================================================================

def test_challenge_tag_frozen_width():
    assert IC.CHALLENGE_TAG == b"QORTROLLER-IPACT-CHALLENGE-v1"
    assert len(IC.CHALLENGE_TAG) == 29


def test_fresh_nonce_per_call():
    s = IC.ChallengeStore()
    a = s.issue(DEV); b = s.issue(DEV)
    assert a.nonce != b.nonce and a.challenge_id != b.challenge_id
    assert len(a.nonce) == 32


def test_challenge_single_use():
    s = IC.ChallengeStore()
    ch = s.issue(DEV)
    assert s.consume(ch.challenge_id) is True    # first use OK
    assert s.consume(ch.challenge_id) is False   # replay rejected


def test_challenge_ttl_expiry():
    s = IC.ChallengeStore(ttl_s=300)
    ch = s.issue(DEV, now=1000.0)
    assert s.consume(ch.challenge_id, now=1000.0 + 301) is False  # expired
    # a fresh one within TTL consumes fine
    ch2 = s.issue(DEV, now=2000.0)
    assert s.consume(ch2.challenge_id, now=2000.0 + 10) is True


def test_unknown_challenge_rejected():
    assert IC.ChallengeStore().consume("deadbeef") is False


# ===========================================================================
# (c) challenge domain separation (W-5)
# ===========================================================================

def test_challenge_tag_distinct_from_family_tag():
    assert IC.CHALLENGE_TAG != IR._DOMAIN_TAG  # b"...CHALLENGE-v1" != b"...RENEWAL-v1"


def test_renewal_family_sig_does_not_verify_as_challenge():
    # a composite-sig made under the RENEWAL family tag must NOT verify under the
    # CHALLENGE tag (and vice versa) — cross-protocol reuse resistance.
    kp = C.generate_keypair(C.ALG_MLDSA44_ECDSA_P256_SHA256)
    nonce = hashlib.sha256(b"nonce").digest()
    sig_family = C.sign(kp, IR._DOMAIN_TAG, nonce)        # signed under RENEWAL family tag
    pub = kp.public()
    assert C.verify(pub, IC.CHALLENGE_TAG, nonce, sig_family) is False  # rejected as challenge
    sig_challenge = C.sign(kp, IC.CHALLENGE_TAG, nonce)   # signed under CHALLENGE tag
    assert C.verify(pub, IR._DOMAIN_TAG, nonce, sig_challenge) is False  # rejected as family


# ===========================================================================
# agent test harness (fake store)
# ===========================================================================

class _FakeStore:
    def __init__(self):
        self._expiring = [{"device_id": DEV, "token_id": TOK, "expires_at": TS0 / 1e9}]
        self.vhp_renewals = []
        self.commitments = []

    def get_expiring_vhps(self, cutoff): return list(self._expiring)
    def get_total_vhp_count(self): return 1
    def insert_vhp_renewal(self, **kw): self.vhp_renewals.append(kw); return len(self.vhp_renewals)

    def get_ipact_renewal_head(self, device_id):
        links = [c for c in self.commitments if c["device_id"] == device_id]
        if not links: return None
        last = max(links, key=lambda c: c["epoch_index"])
        return {"commitment": last["commitment"], "epoch_index": last["epoch_index"], "ts_ns": last["ts_ns"]}

    def get_prev_ipact_ts_ns(self, device_id):
        return max((c["ts_ns"] for c in self.commitments if c["device_id"] == device_id), default=0)

    def insert_ipact_renewal_commitment(self, **kw): self.commitments.append(kw); return len(self.commitments)


class _Cfg:
    def __init__(self, enforce):
        self.agent_dry_run_mode = True
        self.ioswarm_renewal_enabled = False
        self.ipact_renewal_enforcement_enabled = enforce


# ===========================================================================
# (d) integration: ①↔③ compose — the freeze-unlock evidence
# ===========================================================================

def test_integration_enforced_renewal_with_real_composite_sig():
    signer = IpactTestSigner(C.ALG_MLDSA44_ECDSA_P256_SHA256)
    store = _FakeStore()
    agent = VHPRenewalAgent(
        cfg=_Cfg(enforce=True), store=store, chain=None, bus=None,
        reattest_signer=signer.signer_callable(),
        device_pubkey_provider=signer.pubkey_provider(),
    )
    asyncio.run(agent._check_and_renew())
    # enforcement ON + valid real composite-sig re-attestation → renewal proceeds
    assert len(store.vhp_renewals) == 1
    assert len(store.commitments) == 1
    c = store.commitments[0]
    assert c["enforced"] == 1
    assert c["reattest_proof"] != IR.NO_REATTEST_PROOF       # real proof, not sentinel
    assert len(c["reattest_proof"]) == 32
    # the proof is exactly SHA-256(challenge_bytes || composite_sig_bytes) for the
    # issued nonce — proven by the commitment recomputing from the stored fields
    ok, reason = IR.verify_chain(DEV, TOK, store.commitments)
    assert ok is True, reason


def test_integration_forged_sig_skips_renewal():
    # a signer that returns garbage → verify fails → _obtain_reattest_proof None → SKIP
    store = _FakeStore()
    agent = VHPRenewalAgent(
        cfg=_Cfg(enforce=True), store=store, chain=None, bus=None,
        reattest_signer=lambda nonce: b"forged-not-a-composite-sig",
        device_pubkey_provider=IpactTestSigner().pubkey_provider(),
    )
    asyncio.run(agent._check_and_renew())
    assert len(store.vhp_renewals) == 0   # dormant-blind gate held
    assert len(store.commitments) == 0


# ===========================================================================
# (e) lazy-import / enforcement-OFF — byte-identical to ③-shipped
# ===========================================================================

def test_enforcement_off_byte_identical_renewal():
    store = _FakeStore()
    # no seams injected + enforcement OFF → seam not reached, composite_sig not needed
    agent = VHPRenewalAgent(cfg=_Cfg(enforce=False), store=store, chain=None, bus=None)
    asyncio.run(agent._check_and_renew())
    assert len(store.vhp_renewals) == 1                       # renews (pre-③/③-shipped behavior)
    assert store.commitments[0]["reattest_proof"] == IR.NO_REATTEST_PROOF
    assert store.commitments[0]["enforced"] == 0


# ===========================================================================
# (f) test-key-not-in-production guard (EDIT 2, defense-in-depth)
# ===========================================================================

def test_vapi_bridge_never_imports_the_fixture():
    pkg = _ROOT / "bridge" / "vapi_bridge"
    offenders = []
    for py in pkg.rglob("*.py"):
        if "ipact_signer_fixture" in py.read_text(encoding="utf-8", errors="ignore"):
            offenders.append(str(py.relative_to(_ROOT)))
    assert offenders == [], f"vapi_bridge must not import the test fixture: {offenders}"


def test_production_agent_no_seam_is_fail_closed():
    # production construction (no seams) → enforcement-ON gate returns None (fail-closed)
    agent = VHPRenewalAgent(cfg=_Cfg(enforce=True), store=_FakeStore(), chain=None, bus=None)
    assert agent._reattest_signer is None
    assert agent._device_pubkey_provider is None
    assert agent._obtain_reattest_proof({"device_id": DEV, "token_id": TOK}) is None

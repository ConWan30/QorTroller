"""Phase 3 (Path B) — host-side SDK signer integration tests.

Verifies the dormant-blind closure: VHPRenewalAgent auto-loads the host-held
composite keypair from composite_device_identity.make_reattest_signer when
ipact_host_signer_enabled=True, runs the full i<->iii handshake against a real
key, and advances the renewal chain with enforced=1.

Tests requiring the provisioned host key (~/.vapi/device_composite_mldsa44.json)
are skipped on CI (key is host-local; Step 1 provisioned it on the testnet host).

T-P3B-1: host-signer auto-load + enforcement ON -> renewal enforced=1, verify_chain passes.
T-P3B-2: host-signer flag OFF + enforcement ON -> skip (fail-closed dormant-blind gate).
T-P3B-3: load_or_generate is stable (same keypair returned on repeated calls).
T-P3B-4: make_reattest_signer round-trips sign -> verify with the host-held key.
"""
from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "bridge"))

from vapi_bridge import ipact_challenge as IC, ipact_renewal as IR
from vapi_bridge.vhp_renewal_agent import VHPRenewalAgent
from vapi_bridge.composite_device_identity import (
    DEFAULT_COMPOSITE_KEY_PATH,
    get_composite_pubkey_blob,
    load_or_generate,
    make_reattest_signer,
)
from l9_presence import composite_sig as C

DEV = "Sony_DualShock_Edge_CFI-ZCP1"
TOK = 2
TS0 = 1_700_000_000_000_000_000


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
        if not links:
            return None
        last = max(links, key=lambda c: c["epoch_index"])
        return {"commitment": last["commitment"], "epoch_index": last["epoch_index"], "ts_ns": last["ts_ns"]}

    def get_prev_ipact_ts_ns(self, device_id):
        return max((c["ts_ns"] for c in self.commitments if c["device_id"] == device_id), default=0)

    def insert_ipact_renewal_commitment(self, **kw): self.commitments.append(kw); return len(self.commitments)


class _Cfg:
    def __init__(self, *, enforce=True, host_signer=True):
        self.agent_dry_run_mode = True
        self.ioswarm_renewal_enabled = False
        self.ipact_renewal_enforcement_enabled = enforce
        self.ipact_host_signer_enabled = host_signer


_KEY_EXISTS = Path(DEFAULT_COMPOSITE_KEY_PATH).exists()
_skip_no_key = pytest.mark.skipif(
    not _KEY_EXISTS, reason="host composite key not provisioned (~/.vapi/device_composite_mldsa44.json)"
)


# ===========================================================================
# T-P3B-1: full auto-load path -- the dormant-blind closure integration test
# ===========================================================================

@_skip_no_key
def test_p3b_1_host_signer_autoload_enforcement_on():
    """T-P3B-1: host-signer auto-load (no injected signer) + enforcement ON -> enforced=1, verify_chain OK.

    This is the test_integration_enforced_renewal_with_registered_keypair from the Phase 3
    brief. The pubkey provider is injected to return the real blob (avoids live-chain call
    in test); the signer is NOT injected, exercising the auto-load path introduced in Step 2.
    """
    pubkey_blob = get_composite_pubkey_blob()

    def _pubkey_provider(device_id: str) -> bytes:
        return pubkey_blob

    store = _FakeStore()
    agent = VHPRenewalAgent(
        cfg=_Cfg(enforce=True, host_signer=True),
        store=store, chain=None, bus=None,
        device_pubkey_provider=_pubkey_provider,
    )
    asyncio.run(agent._check_and_renew())

    assert len(store.vhp_renewals) == 1, "renewal must proceed with host-held composite key"
    assert len(store.commitments) == 1
    c = store.commitments[0]
    assert c["enforced"] == 1
    assert c["reattest_proof"] != IR.NO_REATTEST_PROOF
    assert len(c["reattest_proof"]) == 32
    ok, reason = IR.verify_chain(DEV, TOK, store.commitments)
    assert ok is True, reason


# ===========================================================================
# T-P3B-2: signer disabled -- enforcement ON must still gate (fail-closed)
# ===========================================================================

def test_p3b_2_host_signer_disabled_gates_renewal():
    """T-P3B-2: ipact_host_signer_enabled=False + enforcement ON -> skip (dormant-blind gate holds)."""
    store = _FakeStore()
    agent = VHPRenewalAgent(
        cfg=_Cfg(enforce=True, host_signer=False),
        store=store, chain=None, bus=None,
    )
    asyncio.run(agent._check_and_renew())
    assert len(store.vhp_renewals) == 0, "enforcement ON + no signer -> gate must hold"
    assert len(store.commitments) == 0


# ===========================================================================
# T-P3B-3: keypair stability across calls
# ===========================================================================

@_skip_no_key
def test_p3b_3_load_or_generate_stable():
    """T-P3B-3: load_or_generate returns the SAME keypair (stable device identity)."""
    kp1 = load_or_generate()
    kp2 = load_or_generate()
    blob1 = C.encode_pubkey(kp1.public())
    blob2 = C.encode_pubkey(kp2.public())
    assert blob1 == blob2, "device composite keypair must be stable across calls"


# ===========================================================================
# T-P3B-4: signer callable sign -> verify round-trip
# ===========================================================================

@_skip_no_key
def test_p3b_4_reattest_signer_roundtrip():
    """T-P3B-4: make_reattest_signer produces a callable that round-trips sign -> verify."""
    signer = make_reattest_signer()
    pubkey_blob = get_composite_pubkey_blob()
    nonce = hashlib.sha256(b"test-nonce-p3b4").digest()
    sig_blob = signer(nonce)
    pub = C.decode_pubkey(pubkey_blob)
    assert C.verify(pub, IC.CHALLENGE_TAG, nonce, sig_blob) is True

"""Phase B ② P4b — bridge read-path tests (§5 b/c/e of the scope doc).

  (b) integrity check: resolve_composite_pubkey returns the verified blob; a tampered
      event blob (SHA-256 != on-chain hash) -> None (fail-closed).
  (c) W-1 RESOLUTION EVIDENCE (load-bearing): a re-attestation through ③'s REAL renewal
      path verifies against a REGISTERED (not injected-fixture) composite pubkey ->
      commitment chain advances with enforced=1. This is what ② delivers: the production
      composite-pubkey source for #8's verifier.
  (e) integrity-check fail-closed mode: tampered registry blob -> provider returns None ->
      renewal SKIPPED (no exception leaked).
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
sys.path.insert(0, str(_ROOT / "bridge" / "tests"))

from vapi_bridge import ipact_renewal as IR
from vapi_bridge.poep_registry_handler import (
    InMemoryPoEPRegistryReader,
    resolve_composite_pubkey,
)
from vapi_bridge.vhp_renewal_agent import VHPRenewalAgent
from fixtures.ipact_signer_fixture import IpactTestSigner

GAMER = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692"
DEV = "Sony_DualShock_Edge_CFI-ZCP1"
TOK = 2
TS0 = 1_700_000_000_000_000_000


# ===========================================================================
# (b) integrity check
# ===========================================================================

def test_resolve_returns_verified_blob():
    reader = InMemoryPoEPRegistryReader()
    blob = b"\x01" + b"composite-pubkey-blob-fixture"
    reader.register(GAMER, DEV, blob)
    assert resolve_composite_pubkey(reader, GAMER, DEV) == blob


def test_resolve_unregistered_returns_none():
    assert resolve_composite_pubkey(InMemoryPoEPRegistryReader(), GAMER, DEV) is None


def test_resolve_revoked_returns_none():
    reader = InMemoryPoEPRegistryReader()
    reader.register(GAMER, DEV, b"blob")
    reader.revoke(GAMER, DEV)
    assert resolve_composite_pubkey(reader, GAMER, DEV) is None


def test_resolve_tampered_blob_fail_closed():
    # event-sourced blob no longer matches the on-chain hash -> integrity check fails -> None
    reader = InMemoryPoEPRegistryReader()
    reader.register(GAMER, DEV, b"true-blob")
    reader.tamper_blob(GAMER, DEV, b"tampered-blob")  # sha256 != on-chain anchor (sha256(true-blob))
    assert resolve_composite_pubkey(reader, GAMER, DEV) is None


# ===========================================================================
# agent harness (reuses the #8 shape)
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


def _registry_provider(reader, gamer):
    return lambda device_id: resolve_composite_pubkey(reader, gamer, device_id)


# ===========================================================================
# (c) W-1 resolution evidence — registered key through ③
# ===========================================================================

def test_w1_resolution_registered_key_through_three():
    # the device's composite keypair (fixture) is REGISTERED in the registry; the agent's
    # pubkey provider reads it from the registry (not an injected raw key); a re-attestation
    # signed by that keypair verifies -> ③ commitment advances enforced=1.
    signer = IpactTestSigner()                 # holds the device composite keypair
    reader = InMemoryPoEPRegistryReader()
    reader.register(GAMER, DEV, signer.pubkey_blob())   # gamer-sovereign on-chain registration (simulated)
    store = _FakeStore()
    agent = VHPRenewalAgent(
        cfg=_Cfg(enforce=True), store=store, chain=None, bus=None,
        reattest_signer=signer.signer_callable(),
        device_pubkey_provider=_registry_provider(reader, GAMER),  # registry-backed, NOT injected raw key
    )
    asyncio.run(agent._check_and_renew())
    assert len(store.vhp_renewals) == 1
    assert len(store.commitments) == 1
    assert store.commitments[0]["enforced"] == 1
    assert store.commitments[0]["reattest_proof"] != IR.NO_REATTEST_PROOF
    ok, reason = IR.verify_chain(DEV, TOK, store.commitments)
    assert ok is True, reason


def test_w1_unregistered_device_skips_renewal():
    # device NOT registered -> provider returns None -> enforcement-ON gate skips renewal
    signer = IpactTestSigner()
    reader = InMemoryPoEPRegistryReader()  # empty
    store = _FakeStore()
    agent = VHPRenewalAgent(
        cfg=_Cfg(enforce=True), store=store, chain=None, bus=None,
        reattest_signer=signer.signer_callable(),
        device_pubkey_provider=_registry_provider(reader, GAMER),
    )
    asyncio.run(agent._check_and_renew())
    assert len(store.vhp_renewals) == 0
    assert len(store.commitments) == 0


# ===========================================================================
# (e) integrity-check fail-closed mode (registered but tampered event blob)
# ===========================================================================

def test_w1_tampered_registry_blob_skips_renewal():
    signer = IpactTestSigner()
    reader = InMemoryPoEPRegistryReader()
    reader.register(GAMER, DEV, signer.pubkey_blob())
    reader.tamper_blob(GAMER, DEV, b"\x01" + b"forged-pubkey-blob")  # event blob != on-chain hash
    store = _FakeStore()
    agent = VHPRenewalAgent(
        cfg=_Cfg(enforce=True), store=store, chain=None, bus=None,
        reattest_signer=signer.signer_callable(),
        device_pubkey_provider=_registry_provider(reader, GAMER),
    )
    asyncio.run(agent._check_and_renew())
    assert len(store.vhp_renewals) == 0    # fail-closed: integrity mismatch -> no renewal
    assert len(store.commitments) == 0

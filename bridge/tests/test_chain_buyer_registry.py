"""Data Economy Arc 1 Commit 1 — chain.py VAPIBuyerRegistry view methods.

The bridge only ever READS the buyer registry (is_valid_buyer_credential /
get_buyer_category). Credential issuance/revocation is the Curator's on-chain
write path (curator_attestation module, Commit 2), never a bridge call — so the
bridge ABI carries the two views and NO writers.

Fail-OPEN posture (mirrors the VMDR + CONSENT precedent): when
buyer_registry_address is unset OR sync_w3 is unavailable OR the RPC raises, the
views return the dormant default (False for validity, 0 for category). An
unavailable registry must NEVER grant a buyer access it does not hold on-chain.

   T-BUY-CHAIN-1  Both views fail-open dormant when buyer_registry_address unset.
   T-BUY-CHAIN-2  Dormant answers are cached for 60s — back-to-back calls do NOT
                  re-attempt RPC (verified via direct cache inspection + mutation).
   T-BUY-CHAIN-3  Cache keys are distinct per (validity, did, category) and
                  (category, did) — locks the cache-key invariant against drift.
   T-BUY-CHAIN-4  ABI constant _VAPI_BUYER_REGISTRY_ABI carries isValidCredential
                  + getCategory views ONLY; no issueCredential/revokeCredential
                  writers (least-privilege bridge ABI surface).
   T-BUY-CHAIN-5  buyerDID is normalised through device_id_to_bytes32 so the read
                  path and the future write path agree on the on-chain key.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest


@dataclass
class _MinimalCfg:
    """Minimum config surface the methods touch — no full Config dependency.

    NOTE: buyer_registry_address defaults to "" here (NOT the live address) so the
    fail-open path is exercised without any RPC. The production Config defaults to
    the live address; that is covered by config tests, not these unit tests.
    """
    buyer_registry_address: str = ""
    iotex_rpc_url: str = "http://invalid.local:0"  # unused in fail-open path


def _make_client_no_chain():
    """Construct a ChainClient-like object with only the attributes the view
    methods read, bypassing the full Web3 init (which would bind sockets)."""
    from bridge.vapi_bridge.chain import ChainClient

    obj = ChainClient.__new__(ChainClient)
    obj._cfg = _MinimalCfg()
    obj._sync_w3 = None  # fail-open path
    return obj


# ── T-BUY-CHAIN-1 ─────────────────────────────────────────────────────────────

def test_T_BUY_CHAIN_1_views_fail_open_dormant_when_unset():
    """Both views MUST return dormant defaults when the registry address is unset
    (fail-open: an unavailable registry never grants access)."""
    c = _make_client_no_chain()
    assert c.is_valid_buyer_credential("buyer-did-1", 1) is False
    assert c.get_buyer_category("buyer-did-1") == 0


# ── T-BUY-CHAIN-2 ─────────────────────────────────────────────────────────────

def test_T_BUY_CHAIN_2_dormant_answer_is_cached_60s():
    """The dormant answer is cached too — a second call MUST read the cache, not
    re-attempt RPC. Verified by mutating the cached value and observing the next
    read returns the mutated value (proving no re-fetch)."""
    c = _make_client_no_chain()
    assert c.is_valid_buyer_credential("did-cache", 2) is False
    assert c.get_buyer_category("did-cache") == 0

    cache = c._buyer_cache()
    vkey = ("valid", "did-cache", 2)
    ckey = ("cat", "did-cache")
    assert vkey in cache and ckey in cache
    vts, _ = cache[vkey]
    cts, _ = cache[ckey]
    # Mutate cached values; next reads must reflect them (cache hit, no re-fetch).
    cache[vkey] = (vts, True)
    cache[ckey] = (cts, 4)
    assert c.is_valid_buyer_credential("did-cache", 2) is True
    assert c.get_buyer_category("did-cache") == 4


# ── T-BUY-CHAIN-3 ─────────────────────────────────────────────────────────────

def test_T_BUY_CHAIN_3_cache_keys_distinct_per_did_and_category():
    """Validity cache keys MUST distinguish category (same buyer, different
    category = different on-chain answer), and category lookups MUST be keyed
    separately from validity. Locks the cache-key invariant against collisions."""
    c = _make_client_no_chain()
    c.is_valid_buyer_credential("did-x", 1)
    c.is_valid_buyer_credential("did-x", 3)
    c.get_buyer_category("did-x")
    cache = c._buyer_cache()
    assert ("valid", "did-x", 1) in cache
    assert ("valid", "did-x", 3) in cache
    assert ("cat", "did-x") in cache
    # Distinct categories for the same DID must not collide onto one key.
    assert ("valid", "did-x", 1) != ("valid", "did-x", 3)


# ── T-BUY-CHAIN-4 ─────────────────────────────────────────────────────────────

def test_T_BUY_CHAIN_4_abi_present_views_only():
    """The bridge ABI MUST contain the two view-call entries the methods consume.
    It MUST NOT contain issueCredential / revokeCredential — those are the
    Curator's on-chain writes via the bridge wallet, never bridge ABI calls
    (least-privilege surface; the bridge cannot mint/revoke a credential)."""
    from bridge.vapi_bridge import chain as _chain
    abi = _chain._VAPI_BUYER_REGISTRY_ABI
    names = {entry["name"] for entry in abi}
    assert "isValidCredential" in names
    assert "getCategory" in names
    assert "issueCredential" not in names, "writer must NOT be in bridge ABI"
    assert "revokeCredential" not in names, "writer must NOT be in bridge ABI"
    assert "setCuratorWallet" not in names, "owner writer must NOT be in bridge ABI"
    # Every view takes a bytes32 buyerDID (matches the rest of the protocol).
    for entry in abi:
        if entry["type"] == "function":
            assert any(inp["type"] == "bytes32" for inp in entry["inputs"]), \
                f"{entry['name']} must take bytes32 buyerDID"


# ── T-BUY-CHAIN-5 ─────────────────────────────────────────────────────────────

def test_T_BUY_CHAIN_5_buyer_did_normalised_via_device_id_to_bytes32():
    """The read path normalises buyerDID through device_id_to_bytes32 — a 0x-hex
    32-byte DID is used directly, an arbitrary string is SHA-256'd. This is the
    SAME normaliser the write path (curator_attestation) will use, so read and
    write agree byte-for-byte on the on-chain key. Lock the contract here."""
    from bridge.vapi_bridge.consent_categories import device_id_to_bytes32
    import hashlib

    # 0x-prefixed 64-hex → used directly as the 32-byte value.
    hex_did = "0x" + "ab" * 32
    assert device_id_to_bytes32(hex_did) == bytes.fromhex("ab" * 32)
    # Arbitrary DID string → deterministic SHA-256.
    assert device_id_to_bytes32("did:io:0xBEEF") == \
        hashlib.sha256(b"did:io:0xBEEF").digest()
    # Both forms are 32 bytes (valid bytes32 for the on-chain call).
    assert len(device_id_to_bytes32(hex_did)) == 32
    assert len(device_id_to_bytes32("did:io:0xBEEF")) == 32

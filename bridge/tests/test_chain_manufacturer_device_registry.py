"""Path A Arc 1 Commit 2 — chain.py VAPIManufacturerDeviceRegistry view methods.

Pre-deploy posture: MANUFACTURER_DEVICE_REGISTRY_ADDRESS is unset. The four view
methods MUST fail-open to dormant defaults (0 for path/tier, False for booleans)
so bridge readiness does NOT depend on the deploy. Same precedent as
get_registered_composite_pubkey and is_consent_valid (both documented as
INTENTIONAL fail-open in CLAUDE.md Hard Rules).

   T-VMDR-CHAIN-1  All four view methods fail-open dormant when
                   manufacturer_device_registry_address is unset.
   T-VMDR-CHAIN-2  Dormant answers are cached for 60s — back-to-back calls
                   do NOT trigger repeated RPC attempts (cache hit verified
                   via direct cache inspection).
   T-VMDR-CHAIN-3  Cached bundle is shape (sig:int, tier:int, isA:bool, isAct:bool)
                   — locks the internal cache invariant against silent drift.
   T-VMDR-CHAIN-4  ABI constant _VAPI_MANUFACTURER_DEVICE_REGISTRY_ABI is present
                   in chain.py with the 4 view-call entries the bridge consumes;
                   no writer entries (registerDevice/revokeDevice) present —
                   those are operator wallet calls, never bridge calls.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import patch

import pytest


@dataclass
class _MinimalCfg:
    """Minimum config surface the methods touch — no full Config dependency."""
    manufacturer_device_registry_address: str = ""
    iotex_rpc_url: str = "http://invalid.local:0"  # unused in fail-open path


def _make_client_no_chain():
    """Construct a ChainClient-like object with attributes the methods read,
    bypassing the full Web3 init (which would try to bind sockets)."""
    from bridge.vapi_bridge.chain import ChainClient

    # ChainClient.__init__ touches AsyncWeb3 + sync Web3 + private key + etc.
    # For unit tests of the dormant-path we don't need any of it — instantiate
    # via __new__ and set only the attributes the methods actually read.
    obj = ChainClient.__new__(ChainClient)
    obj._cfg = _MinimalCfg()
    obj._sync_w3 = None  # fail-open path
    return obj


# ── T-VMDR-CHAIN-1 ────────────────────────────────────────────────────────────

def test_T_VMDR_CHAIN_1_view_methods_fail_open_dormant_when_unset():
    """All four view methods MUST return dormant defaults when the registry
    address is unset (Arc 1 pre-deploy posture)."""
    c = _make_client_no_chain()
    assert c.get_device_signing_path("test-device") == 0
    assert c.get_proof_tier("test-device") == 0
    assert c.is_path_a("test-device") is False
    assert c.is_active_in_mfg_registry("test-device") is False


# ── T-VMDR-CHAIN-2 ────────────────────────────────────────────────────────────

def test_T_VMDR_CHAIN_2_dormant_answer_is_cached_60s():
    """The dormant answer is cached too — back-to-back calls MUST hit the cache,
    not re-attempt the RPC (which is expensive even when fail-open). Verified
    by inspecting the per-instance _vmdr_view_cache directly."""
    c = _make_client_no_chain()
    # First call seeds the cache
    c.get_device_signing_path("dev-cache-test")
    cache = c._vmdr_cache()
    assert "dev-cache-test" in cache
    ts, bundle = cache["dev-cache-test"]
    assert bundle == (0, 0, False, False)
    # Second call reads from cache — confirm by mutating the cached value and
    # observing the next read returns the mutated value (proving no re-fetch).
    cache["dev-cache-test"] = (ts, (1, 1, True, True))
    assert c.get_device_signing_path("dev-cache-test") == 1
    assert c.get_proof_tier("dev-cache-test") == 1
    assert c.is_path_a("dev-cache-test") is True
    assert c.is_active_in_mfg_registry("dev-cache-test") is True


# ── T-VMDR-CHAIN-3 ────────────────────────────────────────────────────────────

def test_T_VMDR_CHAIN_3_cache_bundle_shape_locked():
    """Cached bundle MUST be a 4-tuple (sig:int, tier:int, isA:bool, isAct:bool).
    Any drift (e.g. dict instead of tuple, extra fields, type change) would
    silently change downstream behavior. Locks the cache invariant in CI."""
    c = _make_client_no_chain()
    c.is_path_a("dev-shape-test")
    cache = c._vmdr_cache()
    ts, bundle = cache["dev-shape-test"]
    assert isinstance(ts, float)
    assert isinstance(bundle, tuple)
    assert len(bundle) == 4
    sig, tier, isA, isAct = bundle
    assert isinstance(sig, int)
    assert isinstance(tier, int)
    assert isinstance(isA, bool)
    assert isinstance(isAct, bool)


# ── T-VMDR-CHAIN-4 ────────────────────────────────────────────────────────────

def test_T_VMDR_CHAIN_4_abi_present_views_only():
    """The bridge ABI MUST contain the four view-call entries the methods
    consume + the two events for forensic event-log queries. It MUST NOT
    contain registerDevice / revokeDevice — those are operator/manufacturer
    wallet calls, never bridge calls (least-privilege ABI surface)."""
    from bridge.vapi_bridge import chain as _chain
    abi = _chain._VAPI_MANUFACTURER_DEVICE_REGISTRY_ABI
    names = {entry["name"] for entry in abi}
    # Required view calls
    assert "getSigningPath"   in names
    assert "getProofTier"     in names
    assert "isPathA"          in names
    assert "isActive"         in names
    # Required events
    assert "DeviceRegistered" in names
    assert "DeviceRevoked"    in names
    # Writer calls MUST NOT be in the bridge ABI
    assert "registerDevice"   not in names, "writer must NOT be in bridge ABI"
    assert "revokeDevice"     not in names, "writer must NOT be in bridge ABI"
    # All view entries take bytes32 deviceId (matches the rest of the protocol)
    for entry in abi:
        if entry["type"] == "function":
            assert any(inp["type"] == "bytes32" for inp in entry["inputs"]), \
                f"{entry['name']} must take bytes32 deviceId"

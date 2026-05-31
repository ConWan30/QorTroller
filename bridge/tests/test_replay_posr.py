"""Data Economy Arc 6 — PoSR bridge-side sidecar test suite.

Covers the SHA-256 commitment math from spec §1.2-§1.3 + the PoSRBeaconBinder
fail-closed-when-no-beacon honesty rail. Stateless / pure-function tests
need no chain RPC; binder tests use an in-process stub for the chain.
"""

from __future__ import annotations

import asyncio
import hashlib

import pytest

from bridge.vapi_bridge.replay_proof_pipeline import (
    ANCHOR_CADENCE_BLOCKS,
    BEACON_DOMAIN_TAG,
    BeaconReference,
    PoSRBeaconBinder,
    cadence_aligned_block,
    compute_close_beacon_commitment,
    compute_open_beacon_commitment,
)


# ── cadence_aligned_block helper (Demo Spec) ────────────────────────────────

def test_cadence_aligned_block_aligned_input_returns_self():
    assert cadence_aligned_block(64) == 64
    assert cadence_aligned_block(128) == 128
    assert cadence_aligned_block(64 * 1000) == 64 * 1000


def test_cadence_aligned_block_rounds_down_to_nearest():
    assert cadence_aligned_block(100) == 64
    assert cadence_aligned_block(63) == 0
    assert cadence_aligned_block(127) == 64
    assert cadence_aligned_block(65) == 64


def test_cadence_aligned_block_zero_input_returns_zero():
    assert cadence_aligned_block(0) == 0


def test_cadence_aligned_block_large_block_realistic():
    """44188831 is from the Arc 5 ceremony beacon. The nearest cadence-
    aligned block ≤ that is 44188800 (= 690450 * 64)."""
    assert cadence_aligned_block(44188831) == 44188800


def test_cadence_aligned_block_rejects_negative():
    with pytest.raises(ValueError):
        cadence_aligned_block(-1)
    with pytest.raises(ValueError):
        cadence_aligned_block(-64)


def test_cadence_aligned_block_rejects_non_int():
    with pytest.raises(TypeError):
        cadence_aligned_block("64")
    with pytest.raises(TypeError):
        cadence_aligned_block(64.0)
    with pytest.raises(TypeError):
        cadence_aligned_block(None)


# ── Pinned constants ────────────────────────────────────────────────────────

def test_domain_tag_is_exactly_23_bytes_and_byte_identical_to_frozen():
    assert isinstance(BEACON_DOMAIN_TAG, bytes)
    assert BEACON_DOMAIN_TAG == b"VAPI-TEMPORAL-BEACON-v1"
    assert len(BEACON_DOMAIN_TAG) == 23
    # Round-trips to ASCII without surprise re-encoding
    assert BEACON_DOMAIN_TAG.decode("ascii") == "VAPI-TEMPORAL-BEACON-v1"


def test_anchor_cadence_matches_registry_pin():
    """Bridge-side cadence must equal the registry's INV-TBR-002 (=64).
    Drift would cause bridge clients to bind to a non-cadence block that
    the registry would never anchor → permanent unverifiable proofs."""
    assert ANCHOR_CADENCE_BLOCKS == 64


# ── Open-beacon commitment ──────────────────────────────────────────────────

_DEV_ID = bytes.fromhex("a1" * 32)
_OPEN_HASH = bytes.fromhex("b2" * 32)
_CLOSE_HASH = bytes.fromhex("c3" * 32)
_POAC_GENESIS = bytes.fromhex("d4" * 32)
_POAC_FINAL = bytes.fromhex("e5" * 32)


def _expected_open(blk: int) -> bytes:
    h = hashlib.sha256()
    h.update(BEACON_DOMAIN_TAG)
    h.update(blk.to_bytes(8, "big"))
    h.update(_OPEN_HASH)
    h.update(_DEV_ID)
    h.update(_POAC_GENESIS)
    return h.digest()


def test_open_commitment_is_deterministic_and_matches_canonical_encoding():
    """Recompute the commitment from raw bytes per spec §1.2 and assert
    byte-for-byte equality with the helper's output."""
    blk = 44188800
    got = compute_open_beacon_commitment(
        open_block_number=blk,
        open_block_hash=_OPEN_HASH,
        device_id_32=_DEV_ID,
        poac_genesis_link=_POAC_GENESIS,
    )
    assert got == _expected_open(blk)
    # Determinism: same inputs → same output
    again = compute_open_beacon_commitment(
        open_block_number=blk,
        open_block_hash=_OPEN_HASH,
        device_id_32=_DEV_ID,
        poac_genesis_link=_POAC_GENESIS,
    )
    assert again == got


@pytest.mark.parametrize("field", [
    "open_block_number", "open_block_hash", "device_id_32", "poac_genesis_link",
])
def test_open_commitment_avalanche_any_input_changes_output(field):
    """Changing ANY single input byte changes the output (collision-resistance
    sanity, not a real avalanche test — just a regression guard against
    accidentally dropping a field from the hash chain)."""
    blk = 44188800
    base = dict(
        open_block_number=blk, open_block_hash=_OPEN_HASH,
        device_id_32=_DEV_ID, poac_genesis_link=_POAC_GENESIS,
    )
    base_out = compute_open_beacon_commitment(**base)

    perturbed = dict(base)
    if field == "open_block_number":
        perturbed[field] = blk + 1
    elif field == "open_block_hash":
        perturbed[field] = bytes(b ^ 1 for b in _OPEN_HASH)
    elif field == "device_id_32":
        perturbed[field] = bytes(b ^ 1 for b in _DEV_ID)
    elif field == "poac_genesis_link":
        perturbed[field] = bytes(b ^ 1 for b in _POAC_GENESIS)

    assert compute_open_beacon_commitment(**perturbed) != base_out


def test_open_commitment_rejects_malformed_inputs():
    blk = 44188800
    base = dict(
        open_block_number=blk, open_block_hash=_OPEN_HASH,
        device_id_32=_DEV_ID, poac_genesis_link=_POAC_GENESIS,
    )
    # Wrong-length 32-byte fields rejected
    with pytest.raises(ValueError):
        compute_open_beacon_commitment(**{**base, "open_block_hash": b"\x00" * 31})
    with pytest.raises(ValueError):
        compute_open_beacon_commitment(**{**base, "device_id_32": b"\x00" * 33})
    # uint64 range enforced
    with pytest.raises(ValueError):
        compute_open_beacon_commitment(**{**base, "open_block_number": -1})
    with pytest.raises(ValueError):
        compute_open_beacon_commitment(**{**base, "open_block_number": 2**64})


# ── Close-beacon commitment + chaining (the INSEPARABILITY claim) ──────────

def test_close_commitment_chains_to_open_inseparability():
    """The close commitment depends on the open commitment. A different
    open produces a different close, even with identical close inputs.
    This is the spec §1.3 inseparability claim — close cannot be repaired
    with a stale or unrelated open."""
    open_a = _expected_open(44188800)
    open_b = _expected_open(44188864)  # different block → different open

    close_blk = 44188928
    args = dict(
        close_block_number=close_blk, close_block_hash=_CLOSE_HASH,
        poac_final_link=_POAC_FINAL,
    )
    close_a = compute_close_beacon_commitment(open_beacon_commitment=open_a, **args)
    close_b = compute_close_beacon_commitment(open_beacon_commitment=open_b, **args)
    assert close_a != close_b, "close commitment must vary with open commitment"


def test_close_commitment_canonical_encoding():
    """Recompute the close commitment from raw bytes per spec §1.3."""
    open_commit = _expected_open(44188800)
    close_blk = 44188928
    expected = hashlib.sha256(
        BEACON_DOMAIN_TAG
        + close_blk.to_bytes(8, "big")
        + _CLOSE_HASH
        + open_commit
        + _POAC_FINAL
    ).digest()
    got = compute_close_beacon_commitment(
        close_block_number=close_blk, close_block_hash=_CLOSE_HASH,
        open_beacon_commitment=open_commit, poac_final_link=_POAC_FINAL,
    )
    assert got == expected


# ── PoSRBeaconBinder honesty rail (fail-closed when no anchor) ─────────────

class _NoBeaconChain:
    """Stub: registry unset → get_latest_temporal_beacon returns the (0, 0) sentinel."""
    async def get_latest_temporal_beacon(self):
        return (0, b"\x00" * 32)


class _AnchoredChain:
    """Stub: registry returns a real (block, hash) pair."""
    def __init__(self, block, hash_bytes):
        self._block = block
        self._hash = hash_bytes

    async def get_latest_temporal_beacon(self):
        return (self._block, self._hash)


class _FlakyChain:
    """Stub: any call raises — binder must catch + return None."""
    async def get_latest_temporal_beacon(self):
        raise RuntimeError("RPC down")


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_binder_fails_closed_when_chain_is_none():
    """No chain wired → no beacon ref. The PoSR upgrade is dormant; VHR
    proofs fall back to v1 Arc 5 behavior (no recency binding) — honest."""
    binder = PoSRBeaconBinder(chain=None)
    assert _run(binder.fetch_latest_beacon()) is None
    assert _run(binder.open_session(
        device_id_32=_DEV_ID, poac_genesis_link=_POAC_GENESIS,
    )) is None


def test_binder_fails_closed_when_registry_unset():
    """Chain wired but registry returns (0, 0x00..) sentinel → binder
    returns None. This is the "registry not deployed yet" case."""
    binder = PoSRBeaconBinder(chain=_NoBeaconChain())
    assert _run(binder.fetch_latest_beacon()) is None


def test_binder_fails_closed_on_rpc_error():
    """Chain raises → binder catches + returns None — proof generation
    proceeds without the recency upgrade rather than aborting."""
    binder = PoSRBeaconBinder(chain=_FlakyChain())
    assert _run(binder.fetch_latest_beacon()) is None


def test_binder_returns_commitment_pair_on_anchored_beacon():
    """Happy path: chain returns an anchored beacon → binder produces
    open + close commitments that chain correctly."""
    chain = _AnchoredChain(44188800, _OPEN_HASH)
    binder = PoSRBeaconBinder(chain=chain)
    out = _run(binder.open_session(
        device_id_32=_DEV_ID, poac_genesis_link=_POAC_GENESIS,
    ))
    assert out is not None
    open_ref, open_commit = out
    assert open_ref.block_number == 44188800
    assert open_ref.block_hash == _OPEN_HASH
    assert open_commit == _expected_open(44188800)
    # Swap to a later beacon for the close
    chain._block = 44188928
    chain._hash = _CLOSE_HASH
    close_out = _run(binder.close_session(
        open_commitment=open_commit, poac_final_link=_POAC_FINAL,
    ))
    assert close_out is not None
    close_ref, close_commit = close_out
    assert close_ref.block_number == 44188928
    # Close commit must be the canonical one
    expected_close = hashlib.sha256(
        BEACON_DOMAIN_TAG
        + (44188928).to_bytes(8, "big")
        + _CLOSE_HASH
        + open_commit
        + _POAC_FINAL
    ).digest()
    assert close_commit == expected_close


def test_binder_hex_block_hash_string_is_accepted():
    """Chain layer may return block_hash as 0x-prefixed hex string in some
    code paths — binder must handle both bytes and hex."""
    chain = _AnchoredChain(44188800, "0x" + "b2" * 32)
    binder = PoSRBeaconBinder(chain=chain)
    ref = _run(binder.fetch_latest_beacon())
    assert ref is not None
    assert ref.block_hash == _OPEN_HASH

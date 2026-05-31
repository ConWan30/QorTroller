"""Data Economy Arc 6 — Proof of Session Recency (PoSR), bridge-side sidecar.

Per spec §1.2 / §1.3 — at session open the bridge folds the latest anchored
IoTeX block hash into an open-beacon commitment; at session close it folds
the next anchored block hash AND the open-commitment into a close-beacon
commitment. The pair `(open_commitment, close_commitment)` bounds the
session in verifiable time:

  • Open precedes any HID-frame ingestion → the session demonstrably began
    no earlier than `N_open` (block hash `H_open` did not exist before)
  • Close follows the last HID-frame ingestion → the session demonstrably
    ended no earlier than `N_close`
  • Close chains to open → the pair cannot be split or remixed

Stale re-listing, pre-computation drip, and tournament-window backdating
are all defeated by this binding.

Canonical encoding — FROZEN-v1 #14 `VAPI-TEMPORAL-BEACON-v1`:

  open_beacon_commitment = SHA-256(
      b"VAPI-TEMPORAL-BEACON-v1"        (23-byte domain tag, FROZEN)
      || open_block_number_be(8)        (uint64 big-endian)
      || open_block_hash(32)            (bytes32 from VAPITemporalBeaconRegistry)
      || device_id_32(32)               (32-byte device identifier)
      || poac_genesis_link(32)          (first PoAC chain-link of session)
  ) → 32 bytes

  close_beacon_commitment = SHA-256(
      b"VAPI-TEMPORAL-BEACON-v1"
      || close_block_number_be(8)
      || close_block_hash(32)
      || open_beacon_commitment(32)     (chains close → open)
      || poac_final_link(32)            (last PoAC chain-link of session)
  ) → 32 bytes

Pinned by PV-CI INV-POSR-001 (domain tag presence) + INV-POSR-002 (close
chains to open). The 23-byte domain tag is also a FROZEN-v1 #14 family
identifier — keccak256-pinned in the on-chain registry's BEACON_DOMAIN
constant (INV-TBR-001).

This is SHA-256 sidecar (matches GIC v1 / WEC v1 / CONSENT v1 discipline).
The IN-CIRCUIT version used by VAPIReplayProofVerifier_v2 uses Poseidon
for field-native efficiency (Commit 3 lands the circuit). The two
representations are reconciled on-chain by VAPIReplayProofVerifier_v2
checking the claimed block hash against VAPITemporalBeaconRegistry's
anchored hash, AND the Groth16 proof committing to the Poseidon analogue
of the same beacon inputs.

Honesty rail: PoSR fails CLOSED when:
  - chain registry is not yet deployed (returns no latest beacon)
  - no cadence block has yet been anchored
  - chain RPC raises
A session that can't get a beacon read at OPEN does not get a PoSR-bound
proof — its VHR proof simply lacks the recency upgrade. v1 (Arc 5) proofs
continue to work unchanged.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Optional

log = logging.getLogger(__name__)

# FROZEN-v1 #14 domain tag — exactly 23 bytes. Pinned by INV-POSR-001 here
# AND by INV-TBR-001 on the on-chain registry's BEACON_DOMAIN constant
# (keccak256 of this same string). Drift would cascade across all
# off-chain verifiers + the on-chain registry, so this string is a
# protocol-fork-or-bust constant.
BEACON_DOMAIN_TAG: bytes = b"VAPI-TEMPORAL-BEACON-v1"

# Cadence: bridge clients align session-boundary beacon reads to multiples
# of 64 blocks (matches the registry's ANCHOR_CADENCE / INV-TBR-002).
ANCHOR_CADENCE_BLOCKS: int = 64


@dataclass(frozen=True)
class BeaconReference:
    """A single (block_number, block_hash) pair from VAPITemporalBeaconRegistry."""
    block_number: int
    block_hash: bytes   # 32 bytes


@dataclass(frozen=True)
class PoSRSessionBeacon:
    """Both endpoints of a session's temporal binding."""
    open_ref: BeaconReference
    open_commitment: bytes        # 32 bytes (SHA-256)
    close_ref: BeaconReference
    close_commitment: bytes       # 32 bytes (SHA-256)


def cadence_aligned_block(block_number: int) -> int:
    """Return the largest block number ≤ `block_number` that is a multiple
    of ANCHOR_CADENCE_BLOCKS (64). Used by the keeper to pick the next
    cadence-aligned block to anchor, and by off-chain verifiers to
    determine which cadence block a session's open beacon should bind to.

    Strict typing: rejects non-int (including float and bool-typed sneaky
    coercions) and negative inputs.
    """
    if type(block_number) is not int:   # NOT isinstance — exclude bool
        raise TypeError(
            f"block_number must be int, got {type(block_number).__name__}"
        )
    if block_number < 0:
        raise ValueError(f"block_number must be non-negative, got {block_number}")
    return block_number - (block_number % ANCHOR_CADENCE_BLOCKS)


# ── Stateless commitment math (pure-function, testable without RPC) ────────

def _validate_32(name: str, value: bytes) -> bytes:
    if not isinstance(value, (bytes, bytearray)):
        raise TypeError(f"{name} must be bytes, got {type(value).__name__}")
    if len(value) != 32:
        raise ValueError(f"{name} must be exactly 32 bytes, got {len(value)}")
    return bytes(value)


def _be8(n: int, name: str) -> bytes:
    if not isinstance(n, int) or n < 0 or n > 0xFFFFFFFFFFFFFFFF:
        raise ValueError(f"{name} must be uint64, got {n}")
    return int(n).to_bytes(8, "big")


def compute_open_beacon_commitment(
    *,
    open_block_number: int,
    open_block_hash: bytes,
    device_id_32: bytes,
    poac_genesis_link: bytes,
) -> bytes:
    """Compute the FROZEN open-beacon commitment per spec §1.2.

    Inputs are validated strictly — drift in any byte changes the
    32-byte SHA-256 output, which would silently break verification.
    """
    h = hashlib.sha256()
    h.update(BEACON_DOMAIN_TAG)
    h.update(_be8(open_block_number, "open_block_number"))
    h.update(_validate_32("open_block_hash", open_block_hash))
    h.update(_validate_32("device_id_32", device_id_32))
    h.update(_validate_32("poac_genesis_link", poac_genesis_link))
    return h.digest()


def compute_close_beacon_commitment(
    *,
    close_block_number: int,
    close_block_hash: bytes,
    open_beacon_commitment: bytes,
    poac_final_link: bytes,
) -> bytes:
    """Compute the FROZEN close-beacon commitment per spec §1.3.

    The close commitment CHAINS to the open commitment — close cannot be
    repaired with a different open (the inseparability claim). Pinned by
    INV-POSR-002 (the literal string `open_beacon_commitment` must appear
    in this module, in this chaining context).
    """
    h = hashlib.sha256()
    h.update(BEACON_DOMAIN_TAG)
    h.update(_be8(close_block_number, "close_block_number"))
    h.update(_validate_32("close_block_hash", close_block_hash))
    h.update(_validate_32("open_beacon_commitment", open_beacon_commitment))
    h.update(_validate_32("poac_final_link", poac_final_link))
    return h.digest()


# ── Binder — orchestrates registry read + commitment compute ───────────────

class PoSRBeaconBinder:
    """Session-boundary worker (spec §5 Thread B). Reads the latest anchored
    beacon from the on-chain registry and produces a session-bound commitment
    pair.

    Construction is cheap; reads happen at session open/close. The binder
    does NOT persist anything — that's the caller's responsibility.

    Honesty rail: when the registry is not deployed (chain.posr_registry
    methods unavailable OR the registry address is unset) the binder returns
    None from open/close compute methods. The orchestrator treats None as
    "no PoSR upgrade available for this session" — falls back to v1 (Arc 5)
    proof generation without recency binding. No fabrication.
    """

    def __init__(self, chain: Any) -> None:
        self._chain = chain

    async def fetch_latest_beacon(self) -> Optional[BeaconReference]:
        """Read latestBeacon() from VAPITemporalBeaconRegistry. Returns None
        on any failure (chain unavailable, registry unset, no anchor yet,
        block_number == 0 sentinel)."""
        if self._chain is None:
            return None
        getter = getattr(self._chain, "get_latest_temporal_beacon", None)
        if getter is None:
            return None
        try:
            result = await getter()
        except Exception:
            log.exception("PoSR latestBeacon read failed (treat as unavailable)")
            return None
        if not result:
            return None
        block_number, block_hash = result
        if int(block_number) == 0:
            return None
        if isinstance(block_hash, str):
            hex_h = block_hash[2:] if block_hash.startswith(("0x", "0X")) else block_hash
            block_hash = bytes.fromhex(hex_h)
        return BeaconReference(int(block_number), bytes(block_hash))

    async def open_session(
        self, *, device_id_32: bytes, poac_genesis_link: bytes,
    ) -> Optional[tuple[BeaconReference, bytes]]:
        """Returns (open_ref, open_commitment) or None if no beacon available."""
        ref = await self.fetch_latest_beacon()
        if ref is None:
            return None
        commitment = compute_open_beacon_commitment(
            open_block_number=ref.block_number,
            open_block_hash=ref.block_hash,
            device_id_32=device_id_32,
            poac_genesis_link=poac_genesis_link,
        )
        return ref, commitment

    async def close_session(
        self, *,
        open_commitment: bytes,
        poac_final_link: bytes,
    ) -> Optional[tuple[BeaconReference, bytes]]:
        """Returns (close_ref, close_commitment) or None. close_ref MUST come
        from a beacon strictly after open — caller is responsible for
        ensuring the chain has progressed at least one ANCHOR_CADENCE block
        between open and close (a real gameplay session takes minutes; the
        cadence is ~2.8 min on empirical IoTeX testnet)."""
        ref = await self.fetch_latest_beacon()
        if ref is None:
            return None
        commitment = compute_close_beacon_commitment(
            close_block_number=ref.block_number,
            close_block_hash=ref.block_hash,
            open_beacon_commitment=open_commitment,
            poac_final_link=poac_final_link,
        )
        return ref, commitment

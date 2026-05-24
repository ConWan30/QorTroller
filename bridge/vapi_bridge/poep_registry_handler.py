"""Phase B ② P4b — bridge READ path for VAPIPoEPRegistry (resolves #8 W-1).

The bridge READS the registry (view calls + event logs) but NEVER writes — gamers
(msg.sender) register their own devices; the bridge only consumes the registered
composite public key to verify ③/#8 re-attestations (W1 / gamer-sovereignty).

Two-RPC-call integrity pattern (load-bearing — do NOT merge into one):
  (1) fetch the DeviceRegistered event-log blob (event-sourced storage), and
  (2) call the getCompositePubkeyHash(gamer, deviceId) view function (on-chain anchor),
then verify SHA-256(blob) == on-chain hash BEFORE trusting the blob. The event blob
alone is not tamper-evident; the on-chain hash is the anchor. Any failure -> None
(fail-closed): downstream treats it as no-pubkey-available -> renewal SKIPPED.

This module is stdlib-only (hashlib) over a small reader abstraction so the integrity
logic is unit-testable without a live chain; the production reader is web3-backed
(see chain.get_registered_composite_pubkey), the test reader is in-memory.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Optional, Protocol

from .consent_categories import device_id_to_bytes32

log = logging.getLogger(__name__)


class PoEPRegistryReader(Protocol):
    """Minimal read surface over VAPIPoEPRegistry (production: web3; test: in-memory)."""

    def is_registration_valid(self, gamer: str, device_id_b32: bytes) -> bool: ...
    def get_composite_pubkey_hash(self, gamer: str, device_id_b32: bytes) -> Optional[bytes]: ...
    def get_registration_blob(self, gamer: str, device_id_b32: bytes) -> Optional[bytes]: ...


def resolve_composite_pubkey(
    reader: PoEPRegistryReader,
    gamer: str,
    device_id,
) -> Optional[bytes]:
    """Return the verified ① ``encode_pubkey`` blob for (gamer, device_id), or None.

    Fail-closed on every negative path: not registered / revoked, missing hash or blob,
    or **SHA-256(blob) != on-chain hash** (tamper). ``device_id`` may be a str (canonical
    device id) or 32 raw bytes; it is normalised via device_id_to_bytes32 to match the
    contract's bytes32 keying.
    """
    try:
        device_id_b32 = device_id_to_bytes32(device_id)
        if not reader.is_registration_valid(gamer, device_id_b32):
            return None
        onchain_hash = reader.get_composite_pubkey_hash(gamer, device_id_b32)   # (2) view call
        blob = reader.get_registration_blob(gamer, device_id_b32)               # (1) event log
        if not onchain_hash or not blob:
            return None
        if hashlib.sha256(blob).digest() != onchain_hash:
            log.warning(
                "PoEP registry integrity check FAILED for device %r (sha256(blob) != on-chain "
                "hash) — fail-closed", device_id,
            )
            return None  # tamper / mismatch -> fail-closed
        return blob
    except Exception as exc:  # fail-closed on any reader/RPC error
        log.debug("resolve_composite_pubkey error (fail-closed): %s", exc)
        return None


class InMemoryPoEPRegistryReader:
    """Test-time reader mimicking VAPIPoEPRegistry (no chain). Stores per (gamer, b32)
    the full pubkey blob + revoked flag; computes the on-chain hash as SHA-256(blob),
    exactly as the contract does. Used by the wallet-free bridge tests (§5b/c/e)."""

    def __init__(self) -> None:
        self._rec: dict[tuple[str, bytes], dict] = {}

    def register(self, gamer: str, device_id, blob: bytes) -> None:
        b32 = device_id_to_bytes32(device_id)
        self._rec[(gamer, b32)] = {"blob": blob, "revoked": False}

    def revoke(self, gamer: str, device_id) -> None:
        b32 = device_id_to_bytes32(device_id)
        if (gamer, b32) in self._rec:
            self._rec[(gamer, b32)]["revoked"] = True

    def tamper_blob(self, gamer: str, device_id, bad_blob: bytes) -> None:
        """Simulate an event-log blob that no longer matches the on-chain hash."""
        b32 = device_id_to_bytes32(device_id)
        self._rec[(gamer, b32)]["event_blob_override"] = bad_blob

    def is_registration_valid(self, gamer: str, device_id_b32: bytes) -> bool:
        r = self._rec.get((gamer, device_id_b32))
        return bool(r) and not r["revoked"]

    def get_composite_pubkey_hash(self, gamer: str, device_id_b32: bytes) -> Optional[bytes]:
        r = self._rec.get((gamer, device_id_b32))
        return hashlib.sha256(r["blob"]).digest() if r else None  # on-chain anchor = sha256(true blob)

    def get_registration_blob(self, gamer: str, device_id_b32: bytes) -> Optional[bytes]:
        r = self._rec.get((gamer, device_id_b32))
        if not r:
            return None
        return r.get("event_blob_override", r["blob"])  # event-sourced (may be tampered)


def make_chain_backed_provider(chain, resolve_gamer=None):
    """Return a sync `Callable[[str], Optional[bytes]]` for the agent's
    `_device_pubkey_provider`, backed by ``chain.get_registered_composite_pubkey`` (fail-open
    when the registry is undeployed). ``resolve_gamer`` (optional) maps device_id -> gamer
    address; in v1 the chain wrapper resolves the registering gamer internally."""
    def _provider(device_id) -> Optional[bytes]:
        try:
            return chain.get_registered_composite_pubkey(device_id)
        except Exception as exc:
            log.debug("chain-backed pubkey provider error (fail-open): %s", exc)
            return None
    return _provider

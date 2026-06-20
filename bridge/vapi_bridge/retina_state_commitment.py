"""Off-chain Retina state commitment primitive (W3bstream prep).

Per ``docs/retina-w3bstream-integration.md`` — NOT pinned in PV-CI until operator GO.
Distinct from PoAC ``world_model_hash`` (EWC TinyML) and Arc 7 ``pq_commitment``.

Phase 3 adds ``VAPI-RETINA-STATE-v2`` with Poseidon ``events_root`` (off-chain
circomlibjs chain). Phase 2 ``VAPI-RETINA-STATE-v1`` SHA-256 root remains the
default for backward compatibility.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, Mapping, Sequence

from .retina_events_root import (
    EVENTS_ROOT_SCHEME_POSEIDON_V1,
    EVENTS_ROOT_SCHEME_SHA256_V1,
    compute_events_root_poseidon,
)

DOMAIN_TAG = b"VAPI-RETINA-STATE-v1"
DOMAIN_TAG_V2 = b"VAPI-RETINA-STATE-v2"

EventsRootScheme = Literal["sha256_v1", "poseidon_v1"]


def _device_id_bytes(device_id_hex: str) -> bytes:
    """Normalize arbitrary device id string to 32-byte commitment input."""
    raw = (device_id_hex or "").lower().replace("0x", "").strip()
    if len(raw) == 64:
        try:
            return bytes.fromhex(raw)
        except ValueError:
            pass
    if len(raw) == 32:
        try:
            return bytes.fromhex(raw) + bytes.fromhex(raw)
        except ValueError:
            pass
    return hashlib.sha256(raw.encode("utf-8") if raw else b"unknown").digest()


def compute_events_root(events: Sequence[Mapping[str, Any]]) -> bytes:
    """Phase 2 default: deterministic SHA-256 sorted canonical JSON lines."""
    if not events:
        return hashlib.sha256(b"").digest()
    lines = [
        json.dumps(dict(e), sort_keys=True, separators=(",", ":")).encode("utf-8")
        for e in events
    ]
    lines.sort()
    return hashlib.sha256(b"\n".join(lines)).digest()


def compute_events_root_for_scheme(
    events: Sequence[Mapping[str, Any]],
    scheme: EventsRootScheme = EVENTS_ROOT_SCHEME_SHA256_V1,
) -> bytes:
    if scheme == EVENTS_ROOT_SCHEME_POSEIDON_V1:
        return compute_events_root_poseidon(events)
    return compute_events_root(events)


def compute_retina_state_commitment(
    device_id_hex: str,
    ts_ns: int,
    events: Sequence[Mapping[str, Any]],
    *,
    events_root_scheme: EventsRootScheme = EVENTS_ROOT_SCHEME_SHA256_V1,
) -> str:
    """SHA-256(domain || device_id(32) || ts_ns_be(8) || events_root(32)) → hex."""
    domain = DOMAIN_TAG_V2 if events_root_scheme == EVENTS_ROOT_SCHEME_POSEIDON_V1 else DOMAIN_TAG
    device_b = _device_id_bytes(device_id_hex)
    root = compute_events_root_for_scheme(events, events_root_scheme)
    preimage = domain + device_b + int(ts_ns).to_bytes(8, "big", signed=False) + root
    return hashlib.sha256(preimage).hexdigest()


def compute_retina_state_commitment_v2(
    device_id_hex: str,
    ts_ns: int,
    events: Sequence[Mapping[str, Any]],
) -> str:
    """Convenience wrapper for Poseidon events_root + ``VAPI-RETINA-STATE-v2``."""
    return compute_retina_state_commitment(
        device_id_hex,
        ts_ns,
        events,
        events_root_scheme=EVENTS_ROOT_SCHEME_POSEIDON_V1,
    )

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
# TRA-1 T3 CANDIDATE (NOT FROZEN, NOT PV-CI-pinned): the verify rung over the CANONICAL Trio
# Retina standard - the ORDERED events root (F-TRA0-1, replayable) bound to the WorldState frame.
# Promotion to a FROZEN-v1 primitive is an OPERATOR SEAL, never autonomous.
DOMAIN_TAG_V3 = b"VAPI-RETINA-STATE-v3"

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


def compute_worldstate_digest(worldstate: Mapping[str, Any] | None) -> bytes:
    """SHA-256 over the canonical (sorted-key) WorldState JSON. Empty/None -> SHA-256(b"")."""
    if not worldstate:
        return hashlib.sha256(b"").digest()
    canon = json.dumps(dict(worldstate), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).digest()


def compute_retina_state_commitment_v3(
    device_id_hex: str,
    ts_ns: int,
    events: Sequence[Mapping[str, Any]],
    *,
    worldstate: Mapping[str, Any] | None = None,
    chain_fn=None,
) -> str:
    """VAPI-RETINA-STATE-v3 (CANDIDATE) - the verify rung over the CANONICAL Trio Retina standard.

    Validates the event stream (retina.event/0.1 conformance + the T4 separation law) and, when
    supplied, the WorldState (schema + separation + biometric floor); commits the ORDERED events
    root (F-TRA0-1, replayable) and binds the WorldState frame:

        SHA-256( VAPI-RETINA-STATE-v3 || device_id(32) || ts_ns_be(8)
                 || ordered_events_root(32) || worldstate_digest(32) )

    NOT PV-CI-pinned. Promotion to a FROZEN-v1 primitive is an OPERATOR SEAL, never autonomous."""
    from .retina_event_std import stream_problems
    from .retina_worldstate_std import validate_worldstate
    from .retina_events_root import compute_events_root_poseidon_ordered

    problems = stream_problems(events)
    if worldstate is not None:
        problems += validate_worldstate(worldstate)
    if problems:
        raise ValueError(f"non-conformant retina state (v3): {problems[:5]}")

    root = compute_events_root_poseidon_ordered(events, chain_fn=chain_fn)
    ws_digest = compute_worldstate_digest(worldstate)
    device_b = _device_id_bytes(device_id_hex)
    preimage = (
        DOMAIN_TAG_V3 + device_b + int(ts_ns).to_bytes(8, "big", signed=False)
        + root + ws_digest
    )
    return hashlib.sha256(preimage).hexdigest()

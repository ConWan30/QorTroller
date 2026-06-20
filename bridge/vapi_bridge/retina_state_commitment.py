"""Off-chain Retina state commitment primitive (W3bstream prep).

Per ``docs/retina-w3bstream-integration.md`` — NOT pinned in PV-CI until operator GO.
Distinct from PoAC ``world_model_hash`` (EWC TinyML) and Arc 7 ``pq_commitment``.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

DOMAIN_TAG = b"VAPI-RETINA-STATE-v1"


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
    """Deterministic 32-byte root over canonical event JSON (sorted keys)."""
    if not events:
        return hashlib.sha256(b"").digest()
    lines = [
        json.dumps(dict(e), sort_keys=True, separators=(",", ":")).encode("utf-8")
        for e in events
    ]
    lines.sort()
    return hashlib.sha256(b"\n".join(lines)).digest()


def compute_retina_state_commitment(
    device_id_hex: str,
    ts_ns: int,
    events: Sequence[Mapping[str, Any]],
) -> str:
    """SHA-256(domain || device_id(32) || ts_ns_be(8) || events_root(32)) → hex."""
    device_b = _device_id_bytes(device_id_hex)
    root = compute_events_root(events)
    preimage = DOMAIN_TAG + device_b + int(ts_ns).to_bytes(8, "big", signed=False) + root
    return hashlib.sha256(preimage).hexdigest()

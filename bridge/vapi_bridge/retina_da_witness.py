"""Retina Phase 3c — DA witness bundle keyed by ``events_root``.

The full witness JSON (events + root metadata) lives off-chain on ``da_router``;
the DA lookup key is the 32-byte ``events_root`` only. ``state_commitment_hex``
is included as auditor cross-link metadata, not as the DA key.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Mapping, Sequence

from .replay_proof_pipeline.da_layer import da_router
from .retina_events_root import (
    EVENTS_ROOT_SCHEME_POSEIDON_V1,
    EVENTS_ROOT_SCHEME_SHA256_V1,
)
from .retina_state_commitment import compute_events_root_for_scheme

log = logging.getLogger(__name__)

DA_WITNESS_SCHEMA = "vapi-retina-da-witness-v1"


def _root_bytes(root_hex: str) -> bytes:
    raw = (root_hex or "").strip()
    stripped = raw[2:] if raw.lower().startswith("0x") else raw
    if len(stripped) != 64:
        raise ValueError(f"invalid events_root hex length: {len(stripped)}")
    return bytes.fromhex(stripped)


def build_retina_witness_bytes(
    *,
    device_id: str,
    ts_ns: int,
    events: Sequence[Mapping[str, Any]] | Sequence[dict[str, Any]],
    events_root_hex: str,
    events_root_scheme: str,
    record_hash_hex: str = "",
    state_commitment_hex: str = "",
) -> bytes:
    """Canonical JSON witness payload for off-chain DA storage."""
    payload = {
        "schema": DA_WITNESS_SCHEMA,
        "device_id": device_id,
        "record_hash_hex": record_hash_hex or "",
        "ts_ns": int(ts_ns),
        "events_root_scheme": events_root_scheme,
        "events_root_hex": events_root_hex,
        "state_commitment_hex": state_commitment_hex or "",
        "events": list(events),
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def upload_retina_witness_to_da(events_root_hex: str, witness_bytes: bytes) -> bool:
    """Store witness bytes on mock DA keyed by ``events_root``."""
    root = _root_bytes(events_root_hex)
    return da_router.upload_blob(root, witness_bytes)


def download_retina_witness_from_da(events_root_hex: str) -> bytes | None:
    """Fetch witness bytes from mock DA (test / replay helper)."""
    try:
        root = _root_bytes(events_root_hex)
    except ValueError:
        return None
    return da_router.download_blob(root)


def maybe_upload_retina_witness_to_da(
    store: Any,
    cfg: Any,
    *,
    device_id: str,
    record_hash_hex: str,
    state_commitment_hex: str,
    events: Sequence[Mapping[str, Any]] | Sequence[dict[str, Any]],
    ts_ns: int,
    w3bstream_exit_code: int = 0,
    events_root_scheme: str = EVENTS_ROOT_SCHEME_SHA256_V1,
) -> dict[str, Any]:
    """Post-persist DA witness upload when enabled and W3bstream validation passed."""
    enabled = bool(getattr(cfg, "retina_da_witness_enabled", False))
    result: dict[str, Any] = {
        "da_witness_enabled": enabled,
        "uploaded": False,
        "payload_bytes": 0,
        "timestamp": time.time(),
    }
    if not enabled:
        return result
    if not events:
        result["skipped"] = "missing_events"
        return result
    if int(w3bstream_exit_code) != 0:
        result["skipped"] = f"w3bstream_exit_{w3bstream_exit_code}"
        return result
    try:
        root_bytes = compute_events_root_for_scheme(events, events_root_scheme)
        events_root_hex = root_bytes.hex()
        witness = build_retina_witness_bytes(
            device_id=device_id,
            ts_ns=ts_ns,
            events=events,
            events_root_hex=events_root_hex,
            events_root_scheme=events_root_scheme,
            record_hash_hex=record_hash_hex,
            state_commitment_hex=state_commitment_hex,
        )
        upload_retina_witness_to_da(events_root_hex, witness)
        result["uploaded"] = True
        result["payload_bytes"] = len(witness)
        result["events_root_hex"] = events_root_hex
        result["events_root_scheme"] = events_root_scheme
        if hasattr(store, "insert_retina_da_witness_log"):
            store.insert_retina_da_witness_log(
                device_id=device_id,
                record_hash_hex=record_hash_hex,
                state_commitment_hex=state_commitment_hex,
                events_root_hex=events_root_hex,
                events_root_scheme=events_root_scheme,
                payload_bytes=len(witness),
                uploaded=True,
            )
    except Exception as exc:
        log.warning("retina DA witness upload fail-open: %s", exc)
        result["error"] = str(exc)[:200]
        if hasattr(store, "insert_retina_da_witness_log"):
            try:
                store.insert_retina_da_witness_log(
                    device_id=device_id,
                    record_hash_hex=record_hash_hex,
                    state_commitment_hex=state_commitment_hex,
                    events_root_hex="",
                    events_root_scheme=events_root_scheme,
                    payload_bytes=0,
                    uploaded=False,
                    error=str(exc)[:200],
                )
            except Exception:
                pass
    return result

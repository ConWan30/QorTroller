"""Retina Phase 2b — bulk event upload to DePIN DA (sidecar pointer pattern).

The full ``retina_event_log`` JSON bulk lives off-chain on ``da_router``;
only the 32-byte ``retina_state_commitment`` crosses ingestion / wire boundaries.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Mapping, Sequence

from .replay_proof_pipeline.da_layer import da_router

log = logging.getLogger(__name__)

DA_BULK_SCHEMA = "vapi-retina-da-bulk-v1"


def _commitment_bytes(commitment_hex: str) -> bytes:
    raw = (commitment_hex or "").strip()
    stripped = raw[2:] if raw.lower().startswith("0x") else raw
    if len(stripped) != 64:
        raise ValueError(f"invalid commitment hex length: {len(stripped)}")
    return bytes.fromhex(stripped)


def build_retina_da_bulk_bytes(
    *,
    device_id: str,
    ts_ns: int,
    events: Sequence[Mapping[str, Any]] | Sequence[dict[str, Any]],
    world_state_json: str = "",
    record_hash_hex: str = "",
) -> bytes:
    """Canonical JSON bulk payload for off-chain DA storage."""
    world_state: Any = {}
    if world_state_json:
        try:
            world_state = json.loads(world_state_json)
        except json.JSONDecodeError:
            world_state = {"raw": world_state_json[:500]}
    payload = {
        "schema": DA_BULK_SCHEMA,
        "device_id": device_id,
        "record_hash_hex": record_hash_hex or "",
        "ts_ns": int(ts_ns),
        "events": list(events),
        "world_state": world_state,
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def upload_retina_bulk_to_da(commitment_hex: str, bulk_bytes: bytes) -> bool:
    """Store bulk bytes on mock DA keyed by ``retina_state_commitment``."""
    commitment = _commitment_bytes(commitment_hex)
    return da_router.upload_blob(commitment, bulk_bytes)


def download_retina_bulk_from_da(commitment_hex: str) -> bytes | None:
    """Fetch bulk bytes from mock DA (test / replay helper)."""
    try:
        commitment = _commitment_bytes(commitment_hex)
    except ValueError:
        return None
    return da_router.download_blob(commitment)


def maybe_upload_retina_to_da(
    store: Any,
    cfg: Any,
    *,
    device_id: str,
    record_hash_hex: str,
    state_commitment_hex: str,
    events: Sequence[Mapping[str, Any]] | Sequence[dict[str, Any]],
    world_state_json: str = "",
    ts_ns: int,
    w3bstream_exit_code: int = 0,
) -> dict[str, Any]:
    """Post-persist DA upload when enabled and W3bstream validation passed."""
    enabled = bool(getattr(cfg, "retina_da_upload_enabled", False))
    result: dict[str, Any] = {
        "da_upload_enabled": enabled,
        "uploaded": False,
        "payload_bytes": 0,
        "timestamp": time.time(),
    }
    if not enabled:
        return result
    if not state_commitment_hex or not events:
        result["skipped"] = "missing_commitment_or_events"
        return result
    if int(w3bstream_exit_code) != 0:
        result["skipped"] = f"w3bstream_exit_{w3bstream_exit_code}"
        return result
    try:
        bulk = build_retina_da_bulk_bytes(
            device_id=device_id,
            ts_ns=ts_ns,
            events=events,
            world_state_json=world_state_json,
            record_hash_hex=record_hash_hex,
        )
        upload_retina_bulk_to_da(state_commitment_hex, bulk)
        result["uploaded"] = True
        result["payload_bytes"] = len(bulk)
        if hasattr(store, "insert_retina_da_upload_log"):
            store.insert_retina_da_upload_log(
                device_id=device_id,
                record_hash_hex=record_hash_hex,
                state_commitment_hex=state_commitment_hex,
                payload_bytes=len(bulk),
                uploaded=True,
            )
    except Exception as exc:
        log.warning("retina DA upload fail-open: %s", exc)
        result["error"] = str(exc)[:200]
        if hasattr(store, "insert_retina_da_upload_log"):
            try:
                store.insert_retina_da_upload_log(
                    device_id=device_id,
                    record_hash_hex=record_hash_hex,
                    state_commitment_hex=state_commitment_hex,
                    payload_bytes=0,
                    uploaded=False,
                    error=str(exc)[:200],
                )
            except Exception:
                pass
    return result

"""W3bstream EvmLogPayload builder + Python validation mirror of ``lib.rs``.

Mechanical sidecar validation only — no Mahalanobis, no DA fetch in v2.0.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Mapping

log = logging.getLogger(__name__)

ANCHOR_CADENCE = 64

EXIT_OK = 0
EXIT_CADENCE = 4
EXIT_PQ = 5
EXIT_RETINA = 6

_VALID_PQ_PLACEHOLDER = "ab" * 32


def resolve_sidecar_commitment(commitment_hex: str) -> tuple[bool, str]:
    """Return (ok, error_message). Mirrors ``resolve_sidecar_commitment`` in lib.rs."""
    raw = (commitment_hex or "").strip()
    if not raw:
        return False, "empty sidecar commitment"
    stripped = raw[2:] if raw.lower().startswith("0x") else raw
    if not stripped or all(c in "0xX" for c in stripped):
        return False, "zero-padded sidecar commitment"
    if len(stripped) != 64 or any(c not in "0123456789abcdefABCDEF" for c in stripped):
        return False, "invalid sidecar commitment format"
    return True, ""


def validate_evm_log_payload(
    payload: Mapping[str, Any],
    *,
    enforce_retina: bool | None = None,
) -> int:
    """Mirror ``handle_poac_payload`` exit codes (cadence / PQ / retina only)."""
    block_number = int(payload.get("block_number") or 0)
    if block_number % ANCHOR_CADENCE != 0:
        return EXIT_CADENCE

    pq_ok, _ = resolve_sidecar_commitment(str(payload.get("pq_commitment") or ""))
    if not pq_ok:
        return EXIT_PQ

    retina_hex = str(payload.get("retina_state_commitment") or "")
    enforce = (
        bool(payload.get("retina_w3bstream_enforce"))
        if enforce_retina is None
        else bool(enforce_retina)
    )
    retina_nonempty = bool(retina_hex.strip())

    if enforce or retina_nonempty:
        ret_ok, _ = resolve_sidecar_commitment(retina_hex)
        if not ret_ok:
            return EXIT_RETINA
        if enforce and not retina_nonempty:
            return EXIT_RETINA

    return EXIT_OK


def build_evm_log_payload(
    *,
    device_id: str,
    block_number: int,
    payload_hash: str,
    signature: str,
    pq_commitment: str,
    retina_state_commitment: str = "",
    retina_w3bstream_enforce: bool = False,
) -> dict[str, Any]:
    """JSON-serializable payload aligned with ``EvmLogPayload`` in lib.rs."""
    return {
        "device_id": device_id,
        "block_number": int(block_number),
        "payload_hash": payload_hash,
        "signature": signature,
        "pq_commitment": pq_commitment,
        "retina_state_commitment": retina_state_commitment or "",
        "retina_w3bstream_enforce": bool(retina_w3bstream_enforce),
    }


def build_evm_log_payload_from_retina_row(
    row: Mapping[str, Any],
    *,
    block_number: int = 64,
    pq_commitment: str = _VALID_PQ_PLACEHOLDER,
    retina_w3bstream_enforce: bool = False,
) -> dict[str, Any]:
    """Round-trip helper: retina_event_log row → EvmLogPayload dict."""
    record_hash = str(row.get("record_hash_hex") or "")
    return build_evm_log_payload(
        device_id=str(row.get("device_id") or "unknown"),
        block_number=block_number,
        payload_hash=record_hash or ("cc" * 32),
        signature="sig-placeholder",
        pq_commitment=pq_commitment,
        retina_state_commitment=str(row.get("state_commitment_hex") or ""),
        retina_w3bstream_enforce=retina_w3bstream_enforce,
    )


def maybe_validate_after_persist(
    store: Any,
    cfg: Any,
    *,
    device_id: str,
    record_hash_hex: str,
    state_commitment_hex: str,
) -> dict[str, Any]:
    """Post-persist hook: format-validate retina commitment when flags enabled."""
    enabled = bool(getattr(cfg, "retina_w3bstream_validation_enabled", False))
    enforce = bool(getattr(cfg, "retina_w3bstream_enforce_on_ingest", False))
    result = {
        "validation_enabled": enabled,
        "enforce_on_ingest": enforce,
        "exit_code": EXIT_OK,
        "validated": False,
        "timestamp": time.time(),
    }
    if not enabled or not state_commitment_hex:
        return result

    payload = build_evm_log_payload(
        device_id=device_id,
        block_number=64,
        payload_hash=record_hash_hex or ("dd" * 32),
        signature="persist-hook",
        pq_commitment=_VALID_PQ_PLACEHOLDER,
        retina_state_commitment=state_commitment_hex,
        retina_w3bstream_enforce=enforce,
    )
    exit_code = validate_evm_log_payload(payload, enforce_retina=enforce)
    result["exit_code"] = exit_code
    result["validated"] = True

    if hasattr(store, "insert_retina_w3bstream_log"):
        try:
            store.insert_retina_w3bstream_log(
                device_id=device_id,
                record_hash_hex=record_hash_hex,
                state_commitment_hex=state_commitment_hex,
                exit_code=exit_code,
                enforce_retina=enforce,
            )
        except Exception as exc:
            log.debug("retina_w3bstream_log insert skipped: %s", exc)

    return result


def payload_to_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(payload), separators=(",", ":")).encode("utf-8")

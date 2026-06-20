"""Retina Phase 2c — PHYSICAL_DATA_ATTESTATION v1 for perception sidecar pointers."""
from __future__ import annotations

import logging
import time
from typing import Any

from .operator_initiative_auto_supersede import _canonical_agent_id_bytes
from .physical_data_attestation import (
    RETINA_PERCEPTION_OBSERVATION,
    attestation_type_from_string,
    compute_pda_hash,
)
from .retina_w3bstream import EXIT_OK

log = logging.getLogger(__name__)


def _commitment_bytes(commitment_hex: str) -> bytes:
    raw = (commitment_hex or "").strip()
    stripped = raw[2:] if raw.lower().startswith("0x") else raw
    if len(stripped) != 64:
        raise ValueError(f"invalid commitment hex length: {len(stripped)}")
    return bytes.fromhex(stripped)


def maybe_record_retina_pda_attestation(
    store: Any,
    cfg: Any,
    *,
    device_id: str,
    state_commitment_hex: str,
    ts_ns: int,
    w3bstream_exit_code: int = 0,
) -> dict[str, Any]:
    """Post-persist PDA log when enabled and W3bstream validation passed."""
    enabled = bool(getattr(cfg, "retina_pda_attestation_enabled", False))
    agent_name = str(
        getattr(cfg, "retina_pda_attestation_agent_id", "bridge_agent") or "bridge_agent"
    )
    result: dict[str, Any] = {
        "pda_attestation_enabled": enabled,
        "recorded": False,
        "attestation_type": RETINA_PERCEPTION_OBSERVATION,
        "timestamp": time.time(),
    }
    if not enabled:
        return result
    if not state_commitment_hex:
        result["skipped"] = "missing_commitment"
        return result
    if int(w3bstream_exit_code) != EXIT_OK:
        result["skipped"] = f"w3bstream_exit_{int(w3bstream_exit_code)}"
        return result
    if not hasattr(store, "insert_physical_data_attestation"):
        result["skipped"] = "store_missing_insert"
        return result
    try:
        hw_hash = _commitment_bytes(state_commitment_hex)
        agent_id_bytes = _canonical_agent_id_bytes(agent_name)
        at_hash = attestation_type_from_string(RETINA_PERCEPTION_OBSERVATION)
        pda = compute_pda_hash(hw_hash, agent_id_bytes, at_hash, int(ts_ns))
        row_id = store.insert_physical_data_attestation(
            pda_commitment=pda.hex(),
            hardware_data_hash=hw_hash.hex(),
            agent_id=agent_id_bytes.hex(),
            attestation_type=RETINA_PERCEPTION_OBSERVATION,
            attestation_type_hash=at_hash.hex(),
            ts_ns=int(ts_ns),
        )
        result["recorded"] = bool(row_id)
        result["pda_commitment"] = pda.hex()
        result["row_id"] = int(row_id or 0)
        result["device_id"] = device_id
    except Exception as exc:
        log.warning("retina PDA attestation fail-open: %s", exc)
        result["error"] = str(exc)[:200]
    return result

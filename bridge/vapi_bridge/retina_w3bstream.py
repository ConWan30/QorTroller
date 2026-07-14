"""W3bstream EvmLogPayload builder + Python validation mirror of ``lib.rs``.

Mechanical sidecar validation only — no Mahalanobis, no DA fetch in v2.0.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Mapping

from .retina_events_root import compute_events_root_poseidon, events_root_hex

log = logging.getLogger(__name__)

ANCHOR_CADENCE = 64

EXIT_OK = 0
EXIT_CADENCE = 4
EXIT_PQ = 5
EXIT_RETINA = 6
EXIT_EVENTS_ROOT = 7
# DEPIN-1 LEG 2 — node_id + session_root mechanical gate (mirrors lib.rs exit 8)
EXIT_NODE_SESSION = 8

_VALID_PQ_PLACEHOLDER = "ab" * 32
_VALID_NODE_ID_PLACEHOLDER = "cd" * 32
_VALID_SESSION_ROOT_PLACEHOLDER = "ef" * 32


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


def resolve_node_session(
    node_id: str,
    session_root: str,
    *,
    node_session_verify: bool = False,
) -> tuple[dict[str, bool], str]:
    """Mirror ``resolve_node_session`` in lib.rs.

    Mechanical format/presence only — does NOT re-derive node_id or recompute
    session_root. Returns ``(resolution_dict, error_message)``; empty error on success.
    """
    node_raw = (node_id or "").strip()
    root_raw = (session_root or "").strip()
    node_empty = not node_raw
    root_empty = not root_raw

    if node_session_verify:
        if node_empty:
            return (
                {
                    "node_id_valid": False,
                    "session_root_valid": not root_empty,
                    "node_session_gate_ok": False,
                },
                "node_session_verify requires non-empty node_id",
            )
        if root_empty:
            return (
                {
                    "node_id_valid": True,
                    "session_root_valid": False,
                    "node_session_gate_ok": False,
                },
                "node_session_verify requires non-empty session_root",
            )
        ok_n, err_n = resolve_sidecar_commitment(node_raw)
        if not ok_n:
            return (
                {
                    "node_id_valid": False,
                    "session_root_valid": False,
                    "node_session_gate_ok": False,
                },
                f"node_id: {err_n}",
            )
        ok_r, err_r = resolve_sidecar_commitment(root_raw)
        if not ok_r:
            return (
                {
                    "node_id_valid": True,
                    "session_root_valid": False,
                    "node_session_gate_ok": False,
                },
                f"session_root: {err_r}",
            )
        return (
            {
                "node_id_valid": True,
                "session_root_valid": True,
                "node_session_gate_ok": True,
            },
            "",
        )

    # Gate OFF: empty = skip; nonempty must be well-formed (fail-closed on garbage).
    if not node_empty:
        ok_n, err_n = resolve_sidecar_commitment(node_raw)
        if not ok_n:
            return (
                {
                    "node_id_valid": False,
                    "session_root_valid": not root_empty,
                    "node_session_gate_ok": False,
                },
                f"node_id: {err_n}",
            )
    if not root_empty:
        ok_r, err_r = resolve_sidecar_commitment(root_raw)
        if not ok_r:
            return (
                {
                    "node_id_valid": not node_empty,
                    "session_root_valid": False,
                    "node_session_gate_ok": False,
                },
                f"session_root: {err_r}",
            )

    return (
        {
            "node_id_valid": not node_empty,
            "session_root_valid": not root_empty,
            "node_session_gate_ok": True,
        },
        "",
    )


def _normalize_hex64(value: str) -> str:
    raw = (value or "").strip()
    return raw[2:] if raw.lower().startswith("0x") else raw


def verify_events_root_recompute(
    events: Any,
    events_root_hex_value: str,
) -> tuple[bool, str]:
    """Mechanical recompute check when payload carries inline event witness."""
    if events is None:
        return True, ""
    if not isinstance(events, list):
        return False, "retina_events must be a list"
    expected = _normalize_hex64(events_root_hex_value)
    if not expected:
        return False, "events_root required when retina_events present"
    ok, err = resolve_sidecar_commitment(expected)
    if not ok:
        return False, f"events_root format: {err}"
    try:
        computed = events_root_hex(compute_events_root_poseidon(events))
    except Exception as exc:
        return False, f"events_root recompute failed: {exc}"
    if computed.lower() != expected.lower():
        return False, "events_root mismatch"
    return True, ""


def validate_evm_log_payload(
    payload: Mapping[str, Any],
    *,
    enforce_retina: bool | None = None,
) -> int:
    """Mirror ``handle_poac_payload`` exit codes (cadence / PQ / retina / events_root)."""
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

    if bool(payload.get("retina_events_root_verify")):
        events = payload.get("retina_events")
        root_hex = str(payload.get("events_root") or "")
        if events is not None or root_hex.strip():
            ok, _ = verify_events_root_recompute(events, root_hex)
            if not ok:
                return EXIT_EVENTS_ROOT

    # DEPIN-1 LEG 2 — node_id + session_root mechanical gate
    _res, err = resolve_node_session(
        str(payload.get("node_id") or ""),
        str(payload.get("session_root") or ""),
        node_session_verify=bool(payload.get("node_session_verify")),
    )
    if err:
        return EXIT_NODE_SESSION

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
    events_root: str = "",
    retina_events: list[dict[str, Any]] | None = None,
    retina_events_root_verify: bool = False,
    node_id: str = "",
    session_root: str = "",
    node_session_verify: bool = False,
) -> dict[str, Any]:
    """JSON-serializable payload aligned with ``EvmLogPayload`` in lib.rs."""
    out: dict[str, Any] = {
        "device_id": device_id,
        "block_number": int(block_number),
        "payload_hash": payload_hash,
        "signature": signature,
        "pq_commitment": pq_commitment,
        "retina_state_commitment": retina_state_commitment or "",
        "retina_w3bstream_enforce": bool(retina_w3bstream_enforce),
        "events_root": events_root or "",
        "retina_events_root_verify": bool(retina_events_root_verify),
        "node_id": node_id or "",
        "session_root": session_root or "",
        "node_session_verify": bool(node_session_verify),
    }
    if retina_events is not None:
        out["retina_events"] = retina_events
    return out


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
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Post-persist hook: format-validate retina commitment when flags enabled."""
    enabled = bool(getattr(cfg, "retina_w3bstream_validation_enabled", False))
    enforce = bool(getattr(cfg, "retina_w3bstream_enforce_on_ingest", False))
    verify_root = bool(getattr(cfg, "retina_events_root_verify_on_ingest", False))
    result = {
        "validation_enabled": enabled,
        "enforce_on_ingest": enforce,
        "events_root_verify": verify_root,
        "exit_code": EXIT_OK,
        "validated": False,
        "timestamp": time.time(),
    }
    if not enabled or not state_commitment_hex:
        return result

    events_root = ""
    if verify_root and events:
        try:
            events_root = events_root_hex(compute_events_root_poseidon(events))
        except Exception as exc:
            log.debug("events_root compute skipped: %s", exc)

    payload = build_evm_log_payload(
        device_id=device_id,
        block_number=64,
        payload_hash=record_hash_hex or ("dd" * 32),
        signature="persist-hook",
        pq_commitment=_VALID_PQ_PLACEHOLDER,
        retina_state_commitment=state_commitment_hex,
        retina_w3bstream_enforce=enforce,
        events_root=events_root,
        retina_events=events if verify_root else None,
        retina_events_root_verify=verify_root,
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

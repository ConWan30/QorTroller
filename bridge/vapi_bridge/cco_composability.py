"""CCO Phase F — on-chain composability preparation (deploy-hold, Option F1).

Pure-function composable-claim hash + PoEP registry view helper surface.
Lens bool sub-check is optional and fail-open. Does NOT deploy Lens v3 (Option F2).
Design: ``wiki/methodology/CCO_POEP_FUSION_v4.md`` §Phase F, §4.1; F-V3-001.

F-COMPOSE-1 — MFG registration (identity) and PoEP registration (presence) are
distinct attestations on separate registries; a device can hold either independently.
``off_chain_verifiable`` requires a gamer-signed PoEP ``DeviceRegistered`` event whose
commitment passes the registry's *current-state* checks (``isRegistrationValid`` on the
event's gamer + ``isRecorded`` on the commitment) — not MFG registration and not mere
log presence. ``prep_only`` is honest only when the scan completed with zero PoEP events
(``SCAN_COMPLETE_EMPTY``). RPC scan failure surfaces as ``registry_unreachable``, never
masquerade as ``prep_only``.

Reference example (live scan 2026-06-20): demo device ``581a836c…`` holds *both* —
MFG-registered for I1 identity and PoEP-registered with commitment ``72ad94ff…`` at block
43955767 (gamer ``0x0Cf36dB57…``) — making it the worked example of I1 ×
``off_chain_verifiable``. The prior inference that this device lacked PoEP registration
was wrong; measured chain state superseded the prediction.
"""
from __future__ import annotations

import hashlib
import struct
import time
from typing import Any, Literal, Optional, Protocol

from .consent_categories import device_id_to_bytes32

_SCHEMA = "qortroller-composability-v1"
_DOMAIN = b"VAPI-COMPOSABLE-CLAIM-v1"

_IDENTITY_CODES: dict[str, int] = {
    "I0_SOFTWARE": 0x00,
    "PATH_B_HOST_KEY": 0x01,
    "I1_SILICON": 0x02,
    "UNKNOWN": 0xFF,
}

_PRESENCE_CODES: dict[str, int] = {
    "P-T0": 0x00,
    "P-T1": 0x01,
    "P-T2": 0x02,
    "P-T3": 0x03,
}

Readiness = Literal[
    "disabled",
    "registry_undeployed",
    "registry_unreachable",
    "missing_device_id",
    "missing_grid_axes",
    "tournament_blocked_path_b",
    "prep_only",
    "off_chain_verifiable",
]


class PoEPComposabilityReader(Protocol):
    """Minimal VAPIPoEPRegistry read surface for Phase F (production: web3; test: in-memory)."""

    def get_poep_commitment(self, device_id) -> Optional[bytes]: ...
    def is_poep_commitment_recorded(self, commitment: bytes) -> bool: ...


def _encode_code(table: dict[str, int], key: str | None, default: int = 0xFF) -> int:
    if not key:
        return default
    return table.get(key, default)


def compute_composable_claim_hash(
    *,
    device_id: str,
    identity_class: str | None,
    presence_tier: str | None,
    poep_commitment: bytes | None = None,
    is_fully_eligible: bool = False,
    ts_ns: int | None = None,
) -> bytes:
    """Candidate v1 composable claim commitment (NOT a FROZEN-v1 family member).

    Binds identity axis + presence axis + optional on-chain PoEP commitment + optional
    Lens eligibility bit. Intended for off-chain verification until Lens v3 (Option F2).
    """
    if ts_ns is None:
        ts_ns = time.time_ns()
    device_b32 = device_id_to_bytes32(device_id)
    identity_byte = _encode_code(_IDENTITY_CODES, identity_class).to_bytes(1, "big")
    presence_byte = _encode_code(_PRESENCE_CODES, presence_tier).to_bytes(1, "big")
    poep_b32 = (poep_commitment if poep_commitment and len(poep_commitment) == 32
                else b"\x00" * 32)
    eligible_byte = b"\x01" if is_fully_eligible else b"\x00"
    return hashlib.sha256(
        _DOMAIN
        + device_b32
        + identity_byte
        + presence_byte
        + poep_b32
        + eligible_byte
        + struct.pack(">Q", int(ts_ns)),
    ).digest()


def _resolve_readiness(
    *,
    enabled: bool,
    registry_deployed: bool,
    device_id: str | None,
    identity_class: str | None,
    presence_tier: str | None,
    poep_commitment: bytes | None,
    poep_recorded: bool | None,
    poep_scan_outcome: str | None = None,
) -> Readiness:
    if not enabled:
        return "disabled"
    if not device_id:
        return "missing_device_id"
    if identity_class is None or presence_tier is None:
        return "missing_grid_axes"
    if identity_class == "PATH_B_HOST_KEY" and presence_tier == "P-T3":
        return "tournament_blocked_path_b"
    if not registry_deployed:
        return "registry_undeployed"
    if poep_scan_outcome == "SCAN_FAILED":
        return "registry_unreachable"
    if poep_commitment and poep_recorded is True:
        return "off_chain_verifiable"
    if poep_scan_outcome == "SCAN_COMPLETE_EMPTY":
        return "prep_only"
    if poep_scan_outcome == "SCAN_COMPLETE_FOUND":
        return "prep_only"
    return "prep_only"


def assemble_composability_status(
    *,
    enabled: bool,
    registry_deployed: bool,
    device_id: str | None = None,
    identity_class: str | None = None,
    presence_tier: str | None = None,
    poep_commitment: bytes | None = None,
    poep_commitment_recorded: bool | None = None,
    poep_scan_outcome: str | None = None,
    poep_scan_error: str | None = None,
    is_fully_eligible_onchain: bool | None = None,
    lens_subcheck_enabled: bool = False,
    ts_ns: int | None = None,
) -> dict[str, Any]:
    """Build Phase F composability block for session-status (deploy-hold)."""
    readiness = _resolve_readiness(
        enabled=enabled,
        registry_deployed=registry_deployed,
        device_id=device_id,
        identity_class=identity_class,
        presence_tier=presence_tier,
        poep_commitment=poep_commitment,
        poep_recorded=poep_commitment_recorded,
        poep_scan_outcome=poep_scan_outcome,
    )

    claim_hash: str | None = None
    if device_id and identity_class is not None and presence_tier is not None:
        digest = compute_composable_claim_hash(
            device_id=device_id,
            identity_class=identity_class,
            presence_tier=presence_tier,
            poep_commitment=poep_commitment,
            is_fully_eligible=bool(is_fully_eligible_onchain) if lens_subcheck_enabled else False,
            ts_ns=ts_ns,
        )
        claim_hash = "0x" + digest.hex()

    return {
        "schema": _SCHEMA,
        "enabled": enabled,
        "option": "F1",
        "registry_deployed": registry_deployed,
        "readiness": readiness,
        "poep_scan_outcome": poep_scan_outcome,
        "poep_scan_error": poep_scan_error,
        "composable_claim_hash": claim_hash,
        "poep_commitment_hex": (
            "0x" + poep_commitment.hex() if poep_commitment else None
        ),
        "poep_commitment_recorded": poep_commitment_recorded,
        "lens_subcheck": {
            "enabled": lens_subcheck_enabled,
            "is_fully_eligible_onchain": is_fully_eligible_onchain,
        },
        "composable_on_chain": False,
        "operator_gates": [
            "CCO_COMPOSABILITY_ENABLED=true",
            "POEP_REGISTRY_ADDRESS set + live",
            "Lens v3 or composability wrapper deploy (Option F2)",
            "Operator GO + governance if new FROZEN family",
        ],
    }


def apply_composability_to_grid(
    grid: dict[str, Any],
    composability: dict[str, Any],
) -> dict[str, Any]:
    """Merge Phase F composability fields into an identity_grid dict (non-destructive)."""
    merged = dict(grid)
    merged["composable_claim_hash"] = composability.get("composable_claim_hash")
    merged["composability_readiness"] = composability.get("readiness")
    merged["composable_on_chain"] = composability.get("composable_on_chain", False)
    merged["composability"] = composability
    return merged


def resolve_poep_commitment(
    reader: PoEPComposabilityReader,
    device_id,
) -> tuple[bytes | None, bool | None]:
    """Return (poep_commitment, is_recorded) from registry reader; fail-closed on errors."""
    try:
        commitment = reader.get_poep_commitment(device_id)
        if not commitment or commitment == b"\x00" * 32:
            return None, None
        recorded = reader.is_poep_commitment_recorded(commitment)
        return commitment, recorded
    except Exception:
        return None, None


class InMemoryPoEPComposabilityReader:
    """Test-time reader for VAPIPoEPRegistry PoEP commitment surface."""

    def __init__(self) -> None:
        self._by_device: dict[bytes, bytes] = {}
        self._recorded: set[bytes] = set()

    def register(self, device_id, commitment: bytes) -> None:
        b32 = device_id_to_bytes32(device_id)
        self._by_device[b32] = commitment
        self._recorded.add(commitment)

    def get_poep_commitment(self, device_id) -> Optional[bytes]:
        return self._by_device.get(device_id_to_bytes32(device_id))

    def is_poep_commitment_recorded(self, commitment: bytes) -> bool:
        return commitment in self._recorded

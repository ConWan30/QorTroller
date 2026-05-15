"""
Phase 242-BT Stream 1 — BT-WITNESS v1 capability scaffolding.

Canonical anchor: wiki/methodology/bt_calibration_v1_1_architectural_revision.md
                  (supersedes v1.0 BLE-named ideation per BT-CALIB-LESSON-001).
Source anchor:    wiki/assessments/VAPI Bluetooth Calibration_*.pdf.

WHAT THIS IS:
    The BT-WITNESS v1 capability is the protocol-side commitment primitive
    that anchors a LAN-tower BlueZ witness's HCI-event observation of a
    paired DualSense Edge controller session.  The on-chain commitment is
    a SHA-256 over: witness public key + device id + session id + a feature
    commitment root (canonical-JSON-sorted features) + transport-code byte
    + ts_ns.  The capability tag `b"VAPI-BT-WITNESS-v1"` is consumed by the
    bridge + future BTWitnessRegistry contract; it is NOT an 11th PATTERN-017
    commitment-family entry (commitment family count stays 10 — this is a
    CAPABILITY following the POSEIDON-BN254-AS reframe precedent).

WHAT THIS IS *NOT* (Stream 1 boundary):
    - No BlueZ subprocess integration (Linux+dongle hardware-dependent;
      Stream 2 — gated on the operator's witness-rig provisioning).
    - No actual feature extraction (per the v1.1 canonical anchor §5,
      seven empirical unknowns must be resolved by Stage-2 pre-corpus
      measurement BEFORE a feature schema can be committed; Stream 2
      ships the final feature set after Stage-2 lands its measurement
      campaign).
    - No contract deploy (Stream 3 — wallet-gated; Operator Initiative
      O3 completion is a precondition per the operator's hard rule
      "no mainnet deploys until Operator Initiative is totally complete").
    - No FROZEN-region edits.

FROZEN INVARIANTS (Stream 1 commits — Stream 4 PV-CI ceremony pins these):
    INV-BT-WITNESS-001  Domain tag = b"VAPI-BT-WITNESS-v1" (18 bytes literal).
    INV-BT-WITNESS-002  Transport code = 0x01 for BR/EDR (FROZEN per the
                        v1.1 canonical anchor §1: DualSense Edge transport
                        is Bluetooth Classic BR/EDR with HIDP, NOT BLE/HOGP).
                        Future BLE-HOGP variant (Xbox Wireless v5+) gets
                        a SEPARATE capability tag — v1.1 §2 deliberately
                        refuses to overload the BR/EDR commitment surface.
    INV-BT-WITNESS-003  compute_bt_witness_commitment byte layout is FROZEN
                        at the four-field-plus-feature-root composition
                        described in this module — any reordering or width
                        change requires v2 capability tag.

DELIBERATE STREAM 1 RESTRAINT:
    BT_WITNESS_FEATURE_NAMES is an empty tuple.  The Stream 1 commitment
    therefore folds an empty canonical-JSON `{}` into the feature_root
    slot, producing a deterministic-but-feature-free commitment.  This is
    the forcing function: Stream 2 commits the canonical feature set only
    after Stage-2 (weeks 7-14 of the 6-month timeline) measures the seven
    empirical unknowns in v1.1 §5.  A future PR that prematurely adds
    feature names will be caught by T-PHASE242-2 in CI.

L8 v1 CLAIM ENVELOPE (per v1.1 §7):
    - Session-bound presence attestation ONLY.
    - NOT cross-session controller identity (requires the same-model
      separability study on N>=3 identical DualSense Edges per
      CROSS-LESSON-001 — that study has not been run).
    - Detection performance inherits the BlueShield published baseline
      (5.84% FN CFO inspection, 8.72% FN RSSI inspection, 2.37% combined
      FP) as a FLOOR — L8 v1 does not claim improvement on detection
      axes BlueShield already characterizes.
    - Novelty lives in the forensic + governance layer: cross-tournament
      portability of witness signatures + non-repudiable temporal
      ordering for adjudication + on-chain TWC commitment.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Dict, Tuple


# ---------------------------------------------------------------------------
# FROZEN constants (Stream 4 PV-CI ceremony will pin these as INV-BT-WITNESS-*)
# ---------------------------------------------------------------------------

#: Domain tag (18 bytes).  Distinguishes BT-WITNESS-v1 commitments from
#: every other PATTERN-017 / capability commitment.  Pinned by Stream 4
#: INV-BT-WITNESS-001.  Width MUST stay 18; any future BLE-HOGP variant
#: gets a separate tag (`b"VAPI-BT-WITNESS-BLE-v1"`).
BT_WITNESS_DOMAIN_TAG: bytes = b"VAPI-BT-WITNESS-v1"
assert len(BT_WITNESS_DOMAIN_TAG) == 18, "BT_WITNESS_DOMAIN_TAG must be 18 bytes"

#: Stage 1 + 2 of v1.1 architectural revision is COMPLETE for the
#: design layer.  Stage 2 measurement campaign is operator-driven
#: (weeks 7-14).  Stage 3 adversarial validation (weeks 15-24)
#: precedes first calibration capture.
BT_WITNESS_VERSION: str = "v1.1"

#: Transport code byte for BR/EDR (FROZEN per v1.1 §1).
BT_WITNESS_TRANSPORT_BR_EDR: int = 0x01

#: Transport code reserved for the BLE-HOGP variant — NOT YET ALLOCATED.
#: Stream 2 of any future Phase 242-BLE phase would allocate this with a
#: separate capability tag.  Pre-allocating here merely documents intent.
BT_WITNESS_TRANSPORT_BLE_HOGP_RESERVED: int = 0x02

#: Stream 1 ships an empty feature schema — the forcing function for
#: Stream 2 to land its measurement-informed final set explicitly.  Per
#: the v1.1 canonical anchor §2, the candidate set is:
#:     - rssi_variance_normalized  (only feature that survives v1.0)
#:     - tpoll_variance            (co-signal, empirical unknown #2)
#:     - afh_normalized_retransmission_rate (co-signal, empirical unknown #3)
#: But none of these are committed in Stream 1.
BT_WITNESS_FEATURE_NAMES: Tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class BTWitnessResult:
    """Slotted result envelope for the bridge-side BT-WITNESS API surface.

    Stream 1 ships this shape; Stream 2 wires it through to the actual
    HCI-event observation pipeline.  All Stream 1 producers return a
    result with `feature_root_hex` set to the canonical empty-dict hash
    (see _empty_feature_root_hex below) and `n_features=0`.
    """
    commitment_hex: str
    witness_pubkey_hex: str
    device_id_hex: str
    session_id_hex: str
    feature_root_hex: str
    n_features: int
    transport_code: int
    ts_ns: int
    error: str = ""


# ---------------------------------------------------------------------------
# Commitment primitive
# ---------------------------------------------------------------------------

def _hex_to_bytes_strict(hex_str: str, expected_len: int, field_name: str) -> bytes:
    """Strict hex→bytes parse with explicit width check.  Returns raw bytes.

    Raises ValueError on any non-hex / wrong-width input — mirrors the
    CORPUS-SNAPSHOT-v1 helper pattern.
    """
    cleaned = (hex_str or "").lower()
    if cleaned.startswith("0x"):
        cleaned = cleaned[2:]
    try:
        raw = bytes.fromhex(cleaned)
    except ValueError as exc:
        raise ValueError(f"{field_name}: not valid hex: {exc!s}")
    if len(raw) != expected_len:
        raise ValueError(
            f"{field_name}: expected {expected_len} bytes, got {len(raw)}"
        )
    return raw


def _canonical_feature_root(features: Dict[str, float]) -> bytes:
    """Compute SHA-256 of canonical-JSON-sorted features dict.

    Stream 1 callers MUST pass an empty dict (matches BT_WITNESS_FEATURE_NAMES
    being empty).  Stream 2 commits the canonical feature set; this helper
    will then accept the canonical-named keys.  Canonical JSON uses
    sort_keys=True + separators=(",", ":") + ensure_ascii=False — the
    same discipline as scripts/vsd_ui_compiler.canonical_json.
    """
    if features is None:
        features = {}
    canonical_bytes = json.dumps(
        features,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical_bytes).digest()


def empty_feature_root() -> bytes:
    """Return the Stream 1 feature root: SHA-256 of canonical-JSON `{}`.

    Hardcoding-free: derived from _canonical_feature_root({}) at runtime so
    a future change to the canonical-JSON algorithm propagates uniformly.
    """
    return _canonical_feature_root({})


def compute_bt_witness_commitment(
    witness_pubkey_hex: str,
    device_id_hex: str,
    session_id_hex: str,
    features: Dict[str, float],
    ts_ns: int,
    transport_code: int = BT_WITNESS_TRANSPORT_BR_EDR,
) -> bytes:
    """Compute the FROZEN BT-WITNESS v1 commitment (32 bytes).

    FROZEN byte layout (INV-BT-WITNESS-003):
        SHA-256(
            BT_WITNESS_DOMAIN_TAG (18 B) ||
            witness_pubkey (20 B; Ethereum address bytes) ||
            device_id (32 B; SHA-256(device_id_string)) ||
            session_id (32 B; SHA-256(session_id_string)) ||
            feature_root (32 B; canonical-JSON-sorted features) ||
            transport_code (1 B; 0x01 = BR/EDR — INV-BT-WITNESS-002) ||
            ts_ns (8 B; big-endian uint64)
        ) = 143 B preimage → 32 B output

    Stream 1 callers pass `features={}` — produces the empty-feature
    canonical commitment (Stream 2 ships real features post-Stage-2
    measurement).
    """
    witness = _hex_to_bytes_strict(witness_pubkey_hex, 20, "witness_pubkey_hex")
    device  = _hex_to_bytes_strict(device_id_hex,    32, "device_id_hex")
    session = _hex_to_bytes_strict(session_id_hex,   32, "session_id_hex")

    if not isinstance(transport_code, int) or not 0 <= transport_code <= 0xFF:
        raise ValueError(
            f"transport_code: expected uint8 (0..255), got {transport_code!r}"
        )
    if transport_code != BT_WITNESS_TRANSPORT_BR_EDR:
        # Stream 1 only authorizes BR/EDR.  Future BLE-HOGP / classic-only
        # variants are explicitly out of scope — a different capability tag
        # must be allocated.  v1.1 §2 mandates this.
        raise ValueError(
            f"transport_code: Stream 1 only authorizes 0x01 (BR/EDR), got 0x{transport_code:02x}. "
            "Per the v1.1 canonical anchor §1, the DualSense Edge transport is BR/EDR; "
            "other transports require a separate capability tag (not yet allocated)."
        )

    if not isinstance(ts_ns, int) or ts_ns < 0:
        raise ValueError(f"ts_ns: expected uint64, got {ts_ns!r}")
    if ts_ns >= (1 << 64):
        raise ValueError(f"ts_ns: overflow uint64 ({ts_ns})")

    feature_root = _canonical_feature_root(features or {})
    assert len(feature_root) == 32

    preimage = (
        BT_WITNESS_DOMAIN_TAG
        + witness
        + device
        + session
        + feature_root
        + transport_code.to_bytes(1, "big")
        + ts_ns.to_bytes(8, "big")
    )
    assert len(preimage) == 18 + 20 + 32 + 32 + 32 + 1 + 8 == 143

    return hashlib.sha256(preimage).digest()

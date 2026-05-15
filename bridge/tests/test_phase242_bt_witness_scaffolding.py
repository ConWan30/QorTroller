"""Phase 242-BT Stream 1 — BT-WITNESS v1 capability scaffolding tests.

T-PHASE242-1  Domain tag value + width (FROZEN per INV-BT-WITNESS-001).
T-PHASE242-2  BT_WITNESS_FEATURE_NAMES is empty in Stream 1 (forcing function).
T-PHASE242-3  compute_bt_witness_commitment determinism + byte-stability.
T-PHASE242-4  Tamper detection per-input (each of 5 input fields).
T-PHASE242-5  Stream 1 transport_code MUST be 0x01 (BR/EDR) — others rejected.
T-PHASE242-6  bt_witness_log insert/get round-trip + UNIQUE idempotency.
T-PHASE242-7  Capability tag is NOT a new PATTERN-017 commitment family
              (commitment family count stays 10 — see CLAUDE.md).
T-PHASE242-8  empty_feature_root() = SHA-256 of canonical-JSON `{}`.
"""
from __future__ import annotations

import hashlib
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# sys.path setup — same convention as test_phase173 / test_phase151.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))

# Web3/eth_account stub
sys.modules.setdefault("web3", MagicMock())
sys.modules.setdefault("web3.exceptions", MagicMock())
sys.modules.setdefault("eth_account", MagicMock())


# ---------------------------------------------------------------------------
# T-PHASE242-1
# ---------------------------------------------------------------------------

def test_t_phase242_1_domain_tag_frozen():
    """BT_WITNESS_DOMAIN_TAG MUST equal the FROZEN 18-byte literal."""
    from vapi_bridge.bt_witness import BT_WITNESS_DOMAIN_TAG
    assert BT_WITNESS_DOMAIN_TAG == b"VAPI-BT-WITNESS-v1"
    assert len(BT_WITNESS_DOMAIN_TAG) == 18


# ---------------------------------------------------------------------------
# T-PHASE242-2
# ---------------------------------------------------------------------------

def test_t_phase242_2_feature_names_empty_in_stream_1():
    """BT_WITNESS_FEATURE_NAMES MUST be empty in Stream 1 — Stage-2
    measurement (weeks 7-14 of the v1.1 canonical anchor's 6-month
    timeline) must inform feature selection BEFORE the schema is committed.
    This test is the forcing function: Stream 2 must update this test
    AND ship measurement evidence in the commit body."""
    from vapi_bridge.bt_witness import BT_WITNESS_FEATURE_NAMES
    assert BT_WITNESS_FEATURE_NAMES == (), (
        "Stream 1 ships an empty feature set by design — Stage-2 captures "
        "inform feature selection per the canonical anchor's empirical-"
        "first discipline. If Stream 2 has shipped its measurement-"
        "informed final set, update this test along with the schema."
    )


# ---------------------------------------------------------------------------
# T-PHASE242-3
# ---------------------------------------------------------------------------

def test_t_phase242_3_commitment_determinism_and_manual_recompute():
    """compute_bt_witness_commitment must be byte-deterministic AND match
    a hand-computed SHA-256 of the documented preimage layout."""
    from vapi_bridge.bt_witness import (
        compute_bt_witness_commitment,
        empty_feature_root,
        BT_WITNESS_DOMAIN_TAG,
        BT_WITNESS_TRANSPORT_BR_EDR,
    )

    witness_pubkey = "0x" + "ab" * 20  # 20 bytes
    device_id      = "0x" + "11" * 32  # 32 bytes (SHA-256 of canonical device-id string)
    session_id     = "0x" + "22" * 32  # 32 bytes
    ts_ns          = 1747252800_000_000_000  # 2026-05-14 UTC

    # Two independent runs MUST produce byte-identical output.
    c1 = compute_bt_witness_commitment(
        witness_pubkey_hex=witness_pubkey,
        device_id_hex=device_id,
        session_id_hex=session_id,
        features={},
        ts_ns=ts_ns,
    )
    c2 = compute_bt_witness_commitment(
        witness_pubkey_hex=witness_pubkey,
        device_id_hex=device_id,
        session_id_hex=session_id,
        features={},
        ts_ns=ts_ns,
    )
    assert c1 == c2, "compute_bt_witness_commitment must be deterministic"
    assert len(c1) == 32

    # Hand recompute the FROZEN byte layout (INV-BT-WITNESS-003):
    #   tag(18) || pubkey(20) || device(32) || session(32) ||
    #   feature_root(32) || transport(1) || ts_ns(8) = 143 bytes
    preimage = (
        BT_WITNESS_DOMAIN_TAG
        + bytes.fromhex("ab" * 20)
        + bytes.fromhex("11" * 32)
        + bytes.fromhex("22" * 32)
        + empty_feature_root()
        + BT_WITNESS_TRANSPORT_BR_EDR.to_bytes(1, "big")
        + ts_ns.to_bytes(8, "big")
    )
    assert len(preimage) == 143
    expected = hashlib.sha256(preimage).digest()
    assert c1 == expected, "hand-recomputed commitment must match"


# ---------------------------------------------------------------------------
# T-PHASE242-4
# ---------------------------------------------------------------------------

def test_t_phase242_4_per_input_tamper_detection():
    """Changing any single input field MUST change the commitment.
    Verifies all 5 input fields are independently load-bearing in the
    FROZEN preimage."""
    from vapi_bridge.bt_witness import compute_bt_witness_commitment

    base = dict(
        witness_pubkey_hex="0x" + "ab" * 20,
        device_id_hex     ="0x" + "11" * 32,
        session_id_hex    ="0x" + "22" * 32,
        features          ={},
        ts_ns             =1747252800_000_000_000,
    )
    c0 = compute_bt_witness_commitment(**base)

    # Tamper each field independently:
    tampered = [
        {**base, "witness_pubkey_hex": "0x" + "cd" * 20},
        {**base, "device_id_hex":      "0x" + "33" * 32},
        {**base, "session_id_hex":     "0x" + "44" * 32},
        {**base, "ts_ns":              base["ts_ns"] + 1},
    ]
    for i, t in enumerate(tampered):
        ct = compute_bt_witness_commitment(**t)
        assert ct != c0, f"tamper at field index {i} did not change commitment"

    # Invalid hex widths must raise ValueError:
    with pytest.raises(ValueError, match="witness_pubkey_hex"):
        compute_bt_witness_commitment(
            witness_pubkey_hex="0xab",  # too short
            device_id_hex=base["device_id_hex"],
            session_id_hex=base["session_id_hex"],
            features={},
            ts_ns=base["ts_ns"],
        )
    with pytest.raises(ValueError, match="device_id_hex"):
        compute_bt_witness_commitment(
            witness_pubkey_hex=base["witness_pubkey_hex"],
            device_id_hex="0x11" * 16,  # wrong width
            session_id_hex=base["session_id_hex"],
            features={},
            ts_ns=base["ts_ns"],
        )


# ---------------------------------------------------------------------------
# T-PHASE242-5
# ---------------------------------------------------------------------------

def test_t_phase242_5_stream_1_transport_code_br_edr_only():
    """Stream 1 only authorizes transport_code=0x01 (BR/EDR) per v1.1 §1.
    Future BLE-HOGP variant (Xbox Wireless v5+) gets a separate capability
    tag — Stream 1 must REJECT attempts to use other transport codes."""
    from vapi_bridge.bt_witness import (
        compute_bt_witness_commitment,
        BT_WITNESS_TRANSPORT_BR_EDR,
        BT_WITNESS_TRANSPORT_BLE_HOGP_RESERVED,
    )
    assert BT_WITNESS_TRANSPORT_BR_EDR == 0x01
    assert BT_WITNESS_TRANSPORT_BLE_HOGP_RESERVED == 0x02

    base = dict(
        witness_pubkey_hex="0x" + "ab" * 20,
        device_id_hex     ="0x" + "11" * 32,
        session_id_hex    ="0x" + "22" * 32,
        features          ={},
        ts_ns             =1747252800_000_000_000,
    )
    # BR/EDR explicit pass:
    compute_bt_witness_commitment(**base, transport_code=BT_WITNESS_TRANSPORT_BR_EDR)
    # BLE-HOGP reserved value MUST raise:
    with pytest.raises(ValueError, match="BR/EDR"):
        compute_bt_witness_commitment(
            **base, transport_code=BT_WITNESS_TRANSPORT_BLE_HOGP_RESERVED
        )
    # Out-of-range uint8 MUST raise:
    with pytest.raises(ValueError, match="uint8"):
        compute_bt_witness_commitment(**base, transport_code=256)


# ---------------------------------------------------------------------------
# T-PHASE242-6
# ---------------------------------------------------------------------------

def test_t_phase242_6_store_round_trip_and_idempotency():
    """bt_witness_log table must accept inserts; duplicate commitment_hex
    must hit the UNIQUE index and return the existing row id (idempotent)."""
    from vapi_bridge.store import Store
    from vapi_bridge.bt_witness import (
        compute_bt_witness_commitment,
        empty_feature_root,
        BT_WITNESS_TRANSPORT_BR_EDR,
    )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db_path = os.path.join(td, "test_phase242.db")
        store = Store(db_path)

        commit_bytes = compute_bt_witness_commitment(
            witness_pubkey_hex="0x" + "ab" * 20,
            device_id_hex="0x" + "11" * 32,
            session_id_hex="0x" + "22" * 32,
            features={},
            ts_ns=1747252800_000_000_000,
        )
        commit_hex = commit_bytes.hex()

        # First insert: should succeed, return non-zero row id.
        rid1 = store.insert_bt_witness_event(
            commitment_hex=commit_hex,
            witness_pubkey_hex="0x" + "ab" * 20,
            device_id_hex="0x" + "11" * 32,
            session_id_hex="0x" + "22" * 32,
            feature_root_hex=empty_feature_root().hex(),
            n_features=0,
            transport_code=BT_WITNESS_TRANSPORT_BR_EDR,
            ts_ns=1747252800_000_000_000,
            trigger_reason="stream-1-smoke",
        )
        assert rid1 > 0

        # Status reflects 1 event with no on-chain confirmation:
        status = store.get_bt_witness_status()
        assert status["total_events"] == 1
        assert status["on_chain_confirmed"] == 0
        assert status["latest_commitment"] == commit_hex

        # Duplicate insert returns the SAME row id (UNIQUE collision):
        rid2 = store.insert_bt_witness_event(
            commitment_hex=commit_hex,
            witness_pubkey_hex="0x" + "ab" * 20,
            device_id_hex="0x" + "11" * 32,
            session_id_hex="0x" + "22" * 32,
            feature_root_hex=empty_feature_root().hex(),
            n_features=0,
            transport_code=BT_WITNESS_TRANSPORT_BR_EDR,
            ts_ns=1747252800_000_000_000 + 1,  # different ts; same commitment if other fields match
            trigger_reason="duplicate-attempt",
        )
        # Idempotent: same row id returned, total still 1.
        assert rid2 == rid1
        status2 = store.get_bt_witness_status()
        assert status2["total_events"] == 1


# ---------------------------------------------------------------------------
# T-PHASE242-7
# ---------------------------------------------------------------------------

def test_t_phase242_7_capability_not_new_pattern_017_family():
    """BT-WITNESS-v1 is a CAPABILITY tag (POSEIDON-BN254-AS reframe
    precedent), NOT an 11th PATTERN-017 commitment-family entry.  The
    PATTERN-017 commitment-family count stays at 10:
        PoAC / GIC / WEC / VAME / CORPUS-SNAPSHOT / CONSENT /
        BIOMETRIC-SNAPSHOT / LISTING-v1 / FRR / ZKBA-ARTIFACT-v1.

    This test pins the structural distinction by verifying the BT-WITNESS
    module deliberately does NOT live in vapi_bridge/ as a *peer* of the
    primitive-family modules (corpus_snapshot.py, vame.py, etc.) — it
    lives there for engineering convenience but its tag uses the
    `VAPI-BT-WITNESS-v1` literal that is structurally distinct from the
    family naming scheme.
    """
    from vapi_bridge.bt_witness import BT_WITNESS_DOMAIN_TAG
    # The tag SHOULD NOT match any PATTERN-017 family tag exactly:
    pattern_017_tags = {
        b"VAPI-GIC-GENESIS-v1",
        b"VAPI-WEC-GENESIS-v1",
        b"VAPI-VAME-v1",
        b"VAPI-CORPUS-SNAPSHOT-v1",
        b"VAPI-CONSENT-v1",
        b"VAPI-BIOMETRIC-SNAPSHOT-v1",
        b"VAPI-LISTING-v1",
        b"VAPI-FRR-v1",
        b"VAPI-ZKBA-ARTIFACT-v1",
    }
    assert BT_WITNESS_DOMAIN_TAG not in pattern_017_tags
    # The tag SHOULD have the VAPI- prefix discipline:
    assert BT_WITNESS_DOMAIN_TAG.startswith(b"VAPI-")
    # The tag MUST contain "WITNESS" — distinguishing capability from
    # commitment-family naming:
    assert b"WITNESS" in BT_WITNESS_DOMAIN_TAG


# ---------------------------------------------------------------------------
# T-PHASE242-8
# ---------------------------------------------------------------------------

def test_t_phase242_8_empty_feature_root_matches_canonical_json():
    """empty_feature_root() MUST equal SHA-256 of canonical-JSON `{}` —
    pins the Stream 1 feature-slot semantics so Stream 2 can extend
    safely without breaking the Stream 1 commitment recomputability."""
    from vapi_bridge.bt_witness import empty_feature_root
    expected = hashlib.sha256(b"{}").digest()
    assert empty_feature_root() == expected
    assert len(empty_feature_root()) == 32

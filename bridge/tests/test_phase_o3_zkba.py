"""Phase O3-ZKBA-TRACK1 — ZKBA primitive + store tests.

Stream Z1 + Z2 + Z7 of PLAN-VBDIP-0002-ZKBA-PARALLEL-v1.

T-ZKBA-1:  compute_zkba_commitment is deterministic — same inputs -> same bytes
T-ZKBA-2:  tamper detection on each preimage component byte (parametrized)
T-ZKBA-3:  domain tag b"VAPI-ZKBA-ARTIFACT-v1" exists and is unique in bridge/
T-ZKBA-4:  ProofWeightClass enum values pinned (FROZEN-v1 contract)
T-ZKBA-5:  ZKBAClass enum values pinned (FROZEN-v1 contract)
T-ZKBA-6:  zkba_artifact_log migration is idempotent — fresh + existing DB
T-ZKBA-7:  insert_zkba_artifact round-trip with get_zkba_artifact_status +
           UNIQUE(commitment_hex) idempotency
"""
import hashlib
import os
import re
import struct
import sys
import tempfile
import shutil

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.zkba_artifact import (
    ZKBAClass,
    ProofWeightClass,
    ZKBADraftResult,
    compute_zkba_commitment,
    build_zkba_draft,
    _DOMAIN_TAG,
)


# Constant 32B test hashes used as preimage components
_HASH_A = hashlib.sha256(b"component-A").digest()
_HASH_B = hashlib.sha256(b"component-B").digest()
_HASH_C = hashlib.sha256(b"component-C").digest()


# ---------------------------------------------------------------------------
# T-ZKBA-1: compute_zkba_commitment determinism + manual recompute
# ---------------------------------------------------------------------------

def test_t_zkba_1_commitment_deterministic():
    ts = 1778000000000000000
    components = (_HASH_A, _HASH_B, _HASH_C)
    h1 = compute_zkba_commitment(
        zkba_class=ZKBAClass.GIC,
        proof_weight=ProofWeightClass.CHAIN_ONLY,
        component_hashes=components,
        ts_ns=ts,
    )
    h2 = compute_zkba_commitment(
        zkba_class=ZKBAClass.GIC,
        proof_weight=ProofWeightClass.CHAIN_ONLY,
        component_hashes=components,
        ts_ns=ts,
    )
    assert h1 == h2
    assert len(h1) == 32

    # Manual recompute — verify byte order matches the FROZEN-v1 formula
    sorted_components = sorted([_HASH_A, _HASH_B, _HASH_C])
    expected = hashlib.sha256(
        _DOMAIN_TAG
        + ZKBAClass.GIC.value.to_bytes(1, "big")
        + ProofWeightClass.CHAIN_ONLY.value.to_bytes(1, "big")
        + (3).to_bytes(1, "big")
        + b"".join(sorted_components)
        + struct.pack(">Q", ts)
    ).digest()
    assert h1 == expected

    # Order-independence: shuffling components does NOT change the commitment
    h3 = compute_zkba_commitment(
        zkba_class=ZKBAClass.GIC,
        proof_weight=ProofWeightClass.CHAIN_ONLY,
        component_hashes=(_HASH_C, _HASH_A, _HASH_B),  # different caller order
        ts_ns=ts,
    )
    assert h3 == h1


# ---------------------------------------------------------------------------
# T-ZKBA-2: tamper detection — each preimage component changes the commitment
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tamper_target", [
    "zkba_class",
    "proof_weight",
    "component_count",
    "component_byte",
    "ts_ns",
])
def test_t_zkba_2_commitment_tamper_detection(tamper_target):
    ts = 1778000000000000000
    base_components = (_HASH_A, _HASH_B)
    base = compute_zkba_commitment(
        zkba_class=ZKBAClass.AIT,
        proof_weight=ProofWeightClass.DIRECT_HID,
        component_hashes=base_components,
        ts_ns=ts,
    )

    if tamper_target == "zkba_class":
        tampered = compute_zkba_commitment(
            zkba_class=ZKBAClass.VHP,   # changed
            proof_weight=ProofWeightClass.DIRECT_HID,
            component_hashes=base_components,
            ts_ns=ts,
        )
    elif tamper_target == "proof_weight":
        tampered = compute_zkba_commitment(
            zkba_class=ZKBAClass.AIT,
            proof_weight=ProofWeightClass.CHAIN_ONLY,   # changed
            component_hashes=base_components,
            ts_ns=ts,
        )
    elif tamper_target == "component_count":
        tampered = compute_zkba_commitment(
            zkba_class=ZKBAClass.AIT,
            proof_weight=ProofWeightClass.DIRECT_HID,
            component_hashes=(_HASH_A,),   # one fewer
            ts_ns=ts,
        )
    elif tamper_target == "component_byte":
        # Flip one byte of one component
        tampered_hash = bytearray(_HASH_A)
        tampered_hash[0] ^= 0xFF
        tampered = compute_zkba_commitment(
            zkba_class=ZKBAClass.AIT,
            proof_weight=ProofWeightClass.DIRECT_HID,
            component_hashes=(bytes(tampered_hash), _HASH_B),
            ts_ns=ts,
        )
    elif tamper_target == "ts_ns":
        tampered = compute_zkba_commitment(
            zkba_class=ZKBAClass.AIT,
            proof_weight=ProofWeightClass.DIRECT_HID,
            component_hashes=base_components,
            ts_ns=ts + 1,   # changed
        )
    else:
        pytest.fail(f"unknown tamper_target: {tamper_target}")

    assert tampered != base, f"tampering {tamper_target} did not change commitment"


# ---------------------------------------------------------------------------
# T-ZKBA-3: Domain tag uniqueness in bridge/vapi_bridge/
# ---------------------------------------------------------------------------

def test_t_zkba_3_domain_tag_unique_in_codebase():
    """Verify b"VAPI-ZKBA-ARTIFACT-v1" appears only in zkba_artifact.py.

    Other VAPI-*-v1 tags must not collide.  This enforces INV-ZKBA-002
    (planned for Stream Z8 PV-CI gate).
    """
    assert _DOMAIN_TAG == b"VAPI-ZKBA-ARTIFACT-v1"
    bridge_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "vapi_bridge"))
    pattern = re.compile(rb'b"VAPI-ZKBA-ARTIFACT-v1"')
    matches: list[str] = []
    for entry in os.listdir(bridge_dir):
        if not entry.endswith(".py"):
            continue
        path = os.path.join(bridge_dir, entry)
        try:
            with open(path, "rb") as f:
                content = f.read()
        except (OSError, PermissionError):
            continue
        if pattern.search(content):
            matches.append(entry)
    assert matches == ["zkba_artifact.py"], (
        f"domain tag uniqueness violated; found in: {matches}"
    )


# ---------------------------------------------------------------------------
# T-ZKBA-4: ProofWeightClass enum values pinned (FROZEN-v1 contract)
# ---------------------------------------------------------------------------

def test_t_zkba_4_proof_weight_enum_pinned():
    """ProofWeightClass IntEnum values are FROZEN-v1.  Any change requires
    ZKBA v2 + new domain tag (would invalidate every existing artifact)."""
    assert int(ProofWeightClass.DIRECT_HID) == 1
    assert int(ProofWeightClass.CALIBRATION_PLUS_CONTEXT) == 2
    assert int(ProofWeightClass.CHAIN_ONLY) == 3
    assert int(ProofWeightClass.MARKETPLACE_DERIVED) == 4
    assert int(ProofWeightClass.DEMO) == 5
    assert int(ProofWeightClass.FROZEN_DISABLED) == 6
    # No additional values
    assert len(list(ProofWeightClass)) == 6


# ---------------------------------------------------------------------------
# T-ZKBA-5: ZKBAClass enum values pinned (FROZEN-v1 contract)
# ---------------------------------------------------------------------------

def test_t_zkba_5_class_enum_pinned():
    """ZKBAClass IntEnum values are FROZEN-v1.  Any change requires
    ZKBA v2 + new domain tag (would invalidate every existing artifact)."""
    assert int(ZKBAClass.AIT) == 1
    assert int(ZKBAClass.GIC) == 2
    assert int(ZKBAClass.VHP) == 3
    assert int(ZKBAClass.HARDWARE) == 4
    assert int(ZKBAClass.CONSENT) == 5
    assert int(ZKBAClass.TOURNAMENT) == 6
    assert int(ZKBAClass.MARKET) == 7
    # No additional values
    assert len(list(ZKBAClass)) == 7


# ---------------------------------------------------------------------------
# T-ZKBA-6: zkba_artifact_log migration is idempotent
# ---------------------------------------------------------------------------

def test_t_zkba_6_artifact_log_migration_idempotent(tmp_path):
    """Migration must be safe to run multiple times — second Store()
    instantiation on the same DB must not raise."""
    from vapi_bridge.store import Store

    db_path = str(tmp_path / "test_zkba_6.db")
    s1 = Store(db_path)   # first init runs migration
    # Sanity: table exists by attempting to query it (would raise if missing)
    with s1._conn() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='zkba_artifact_log'"
        ).fetchone()
    assert row is not None, "zkba_artifact_log table not created"

    # Second instantiation on same DB — migration must be idempotent
    s2 = Store(db_path)
    with s2._conn() as conn:
        row2 = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='zkba_artifact_log'"
        ).fetchone()
    assert row2 is not None

    # schema_versions has the expected migration entry exactly once
    with s2._conn() as conn:
        cnt = conn.execute(
            "SELECT COUNT(*) FROM schema_versions WHERE migration_name='zkba_artifact_log'"
        ).fetchone()[0]
    assert int(cnt) == 1


# ---------------------------------------------------------------------------
# T-ZKBA-7: insert_zkba_artifact round-trip + UNIQUE(commitment_hex) idempotency
# ---------------------------------------------------------------------------

def test_t_zkba_7_artifact_log_insert_and_status(tmp_path):
    """insert -> get_zkba_artifact_status round-trip; UNIQUE collision
    returns existing row id."""
    from vapi_bridge.store import Store

    db_path = str(tmp_path / "test_zkba_7.db")
    store = Store(db_path)

    ts = 1778000000000000000
    draft = build_zkba_draft(
        zkba_class=ZKBAClass.GIC,
        proof_weight=ProofWeightClass.CHAIN_ONLY,
        component_hashes=(_HASH_A, _HASH_B),
        ts_ns=ts,
    )
    assert isinstance(draft, ZKBADraftResult)
    assert len(draft.commitment_hex) == 64

    row_id_1 = store.insert_zkba_artifact(
        zkba_class=int(draft.zkba_class),
        proof_weight=int(draft.proof_weight),
        commitment_hex=draft.commitment_hex,
        preimage_json='["aa", "bb"]',
        ts_ns=draft.ts_ns,
    )
    assert row_id_1 > 0

    status = store.get_zkba_artifact_status(draft.commitment_hex)
    assert status is not None
    assert status["commitment_hex"] == draft.commitment_hex
    assert status["zkba_class"] == int(ZKBAClass.GIC)
    assert status["proof_weight"] == int(ProofWeightClass.CHAIN_ONLY)
    assert status["ts_ns"] == ts
    assert status["anchor_tx_hash"] is None   # Track 1 invariant: not anchored

    # UNIQUE(commitment_hex) idempotency: re-insert returns same row id
    row_id_2 = store.insert_zkba_artifact(
        zkba_class=int(draft.zkba_class),
        proof_weight=int(draft.proof_weight),
        commitment_hex=draft.commitment_hex,
        preimage_json='["aa", "bb"]',
        ts_ns=draft.ts_ns,
    )
    assert row_id_2 == row_id_1, "UNIQUE collision should return existing row id"

    # history list returns the artifact
    hist = store.get_zkba_artifact_history(limit=10)
    assert len(hist) == 1
    assert hist[0]["commitment_hex"] == draft.commitment_hex

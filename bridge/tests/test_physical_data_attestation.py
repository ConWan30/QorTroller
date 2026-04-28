"""Phase O0 Stream 3-prep Session 2 — PHYSICAL_DATA_ATTESTATION v1
(seventh and final FROZEN-v1 primitive).

Pass 2C Section 4.2 hash formula + Decision T2 (one test file) +
Decision T3 (anchor_pda_attestation chain wrapper name) + Decision T4
(no record_* orchestrator) + Decision T5 (keccak256 for
attestation_type via eth_utils.keccak) + DELTA2-Pass2C (INV-PDA-002
freezes the domain tag literal).

Tests:
  T-PDA-1:  compute_pda_hash determinism — same inputs always produce
            the same hash (INV-PDA-001 property).
  T-PDA-2:  per-input-field tamper detection — single-bit changes in
            each of the four hash inputs (hardware_data_hash, agent_id,
            attestation_type_hash, ts_ns) produce a different hash.
  T-PDA-3:  domain tag binding — changing the domain tag (synthetic
            inline recompute) produces a different hash for identical
            inputs (load-bearing for primitive-class isolation).
  T-PDA-4:  attestation_type_from_string keccak256 behavior — canonical
            strings produce known-hash bytes32 outputs that match a
            manually computed Solidity-equivalent reference.
  T-PDA-5:  recognized canonical strings produce distinct
            attestation_type hashes (and therefore distinct PDA
            commitments when used in the FROZEN formula).
  T-PDA-6:  invalid input lengths raise ValueError (per-field length
            checks for hardware_data_hash, agent_id, attestation_type_hash).
  T-PDA-7:  ts_ns out of uint64 range raises ValueError.
  T-PDA-8:  store table insert + status round-trip including UNIQUE
            collision idempotency on duplicate pda_commitment.
  T-PDA-9:  store get_physical_data_attestation_history filters by
            agent_id, attestation_type, both, neither, and respects DESC
            ts_ns ordering.
  T-PDA-10: INV-PDA-001 verification — hash determinism property
            (a copy of T-PDA-1 phrased as the invariant assertion, so
            future PV-CI gate freeze can quote this test as the
            determinism check).
  T-PDA-11: INV-PDA-002 verification — domain tag literal pinned (the
            literal b"VAPI-PHYSICAL-DATA-ATTESTATION-v1" is present in
            physical_data_attestation.py source as a frozen module-level
            constant). Mirrors Stream 3-prep Session 1 INV-AGENT-COMMIT-002
            verification pattern.

Note (Finding 1 — Pass 2C arithmetic typos): Pass 2C Section 4.2 line
538 commented the tag as "32 bytes"; actual is 33. Line 552 commented
hash input total as "136 bytes"; actual is 137. The formula is
correct; only the byte-count comments in Pass 2C were off by one.
T-PDA-3 verifies the actual 33-byte tag length structurally.
"""
import hashlib
import os
import struct
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.physical_data_attestation import (  # noqa: E402
    PhysicalDataAttestation,
    compute_pda_hash,
    attestation_type_from_string,
    RECOGNIZED_ATTESTATION_TYPES,
    _PDA_TAG,
)


# ---------------------------------------------------------------------------
# Shared test fixtures (synthetic-but-valid inputs)
# ---------------------------------------------------------------------------

_AGENT_ID_A = bytes.fromhex(
    "1111111111111111111111111111111111111111111111111111111111111111"
)  # 32 bytes
_AGENT_ID_B = bytes.fromhex(
    "2222222222222222222222222222222222222222222222222222222222222222"
)
_HW_HASH_A = hashlib.sha256(b"physical-data-artifact-A").digest()  # 32 bytes
_HW_HASH_B = hashlib.sha256(b"physical-data-artifact-B").digest()
_AT_TYPE_A = "BIOMETRIC_CORPUS_SNAPSHOT"
_AT_TYPE_B = "TREMOR_FFT_FEATURE_VECTOR"
_AT_HASH_A = attestation_type_from_string(_AT_TYPE_A)  # 32 bytes (keccak256)
_AT_HASH_B = attestation_type_from_string(_AT_TYPE_B)
_TS_NS = 1_700_000_000_000_000_000  # 2023-11-14 in ns


# ---------------------------------------------------------------------------
# T-PDA-1: hash determinism
# ---------------------------------------------------------------------------

def test_t_pda_1_hash_determinism():
    """INV-PDA-001: same inputs always produce the same hash."""
    h1 = compute_pda_hash(_HW_HASH_A, _AGENT_ID_A, _AT_HASH_A, _TS_NS)
    h2 = compute_pda_hash(_HW_HASH_A, _AGENT_ID_A, _AT_HASH_A, _TS_NS)
    assert h1 == h2
    assert len(h1) == 32
    # Manual recompute matches Pass 2C Section 4.2 formula
    expected = hashlib.sha256(
        _PDA_TAG + _HW_HASH_A + _AGENT_ID_A + _AT_HASH_A
        + struct.pack(">Q", _TS_NS)
    ).digest()
    assert h1 == expected


# ---------------------------------------------------------------------------
# T-PDA-2: per-input-field tamper detection
# ---------------------------------------------------------------------------

def test_t_pda_2_tamper_detection_per_field():
    """Changing any single input field produces a different hash."""
    base = compute_pda_hash(_HW_HASH_A, _AGENT_ID_A, _AT_HASH_A, _TS_NS)

    # Different hardware_data_hash
    h_hw = compute_pda_hash(_HW_HASH_B, _AGENT_ID_A, _AT_HASH_A, _TS_NS)
    assert h_hw != base

    # Different agent_id
    h_aid = compute_pda_hash(_HW_HASH_A, _AGENT_ID_B, _AT_HASH_A, _TS_NS)
    assert h_aid != base

    # Different attestation_type_hash
    h_at = compute_pda_hash(_HW_HASH_A, _AGENT_ID_A, _AT_HASH_B, _TS_NS)
    assert h_at != base

    # Different ts_ns
    h_ts = compute_pda_hash(_HW_HASH_A, _AGENT_ID_A, _AT_HASH_A, _TS_NS + 1)
    assert h_ts != base

    # All four mutations distinct from base AND from each other
    assert len({base, h_hw, h_aid, h_at, h_ts}) == 5


# ---------------------------------------------------------------------------
# T-PDA-3: domain tag binding
# ---------------------------------------------------------------------------

def test_t_pda_3_domain_tag_binding():
    """Changing the domain tag (synthetic inline recompute) produces a
    different hash for identical input fields. Demonstrates that the
    tag is load-bearing for primitive-class isolation — PHYSICAL_DATA_ATTESTATION
    v1 hashes are not collidable with other primitive class hashes that
    happen to share the same field bytes.
    """
    actual = compute_pda_hash(_HW_HASH_A, _AGENT_ID_A, _AT_HASH_A, _TS_NS)

    # Recompute with a different tag (e.g. AGENT_COMMIT v1's tag)
    fake_tag = b"VAPI-AGENT-COMMIT-v1"  # 20 bytes — different primitive
    body = (_HW_HASH_A + _AGENT_ID_A + _AT_HASH_A
            + struct.pack(">Q", _TS_NS))
    fake = hashlib.sha256(fake_tag + body).digest()

    assert actual != fake

    # Also confirm the actual tag length matches Pass 2C-corrected count
    assert len(_PDA_TAG) == 33  # Finding 1: Pass 2C said 32, actual is 33


# ---------------------------------------------------------------------------
# T-PDA-4: keccak256 attestation_type behavior
# ---------------------------------------------------------------------------

def test_t_pda_4_attestation_type_keccak256():
    """attestation_type_from_string uses keccak256 (not SHA-256) per
    Decision T5 and Pass 2C Section 4.2. Verify against a manually
    computed reference using eth_utils.keccak directly.
    """
    from eth_utils import keccak as _kec

    s = "BIOMETRIC_CORPUS_SNAPSHOT"
    actual = attestation_type_from_string(s)
    expected = _kec(text=s)
    assert actual == expected
    assert len(actual) == 32

    # Determinism: repeated calls produce the same hash
    repeats = [attestation_type_from_string(s) for _ in range(5)]
    assert len(set(repeats)) == 1

    # Sanity: attestation_type_from_string is NOT SHA-256 (different output)
    sha = hashlib.sha256(s.encode("utf-8")).digest()
    assert actual != sha, (
        "attestation_type_from_string must use keccak256, not SHA-256 "
        "(Decision T5)"
    )


# ---------------------------------------------------------------------------
# T-PDA-5: recognized canonical strings produce distinct hashes
# ---------------------------------------------------------------------------

def test_t_pda_5_recognized_strings_distinct_hashes():
    """Each of the five RECOGNIZED_ATTESTATION_TYPES strings produces a
    distinct attestation_type_hash, and consequently a distinct PDA
    commitment when used in the FROZEN formula with otherwise-identical
    inputs.
    """
    assert len(RECOGNIZED_ATTESTATION_TYPES) == 5
    expected = (
        "BIOMETRIC_CORPUS_SNAPSHOT",
        "POAC_CHAIN_INTEGRITY",
        "TREMOR_FFT_FEATURE_VECTOR",
        "FLEET_COHERENCE_OBSERVATION",
        "HARDWARE_CERTIFICATION",
    )
    assert set(RECOGNIZED_ATTESTATION_TYPES) == set(expected)

    type_hashes = [attestation_type_from_string(s)
                   for s in RECOGNIZED_ATTESTATION_TYPES]
    assert len(set(type_hashes)) == 5  # all distinct

    # PDA commitments distinct as a consequence
    pda_hashes = [
        compute_pda_hash(_HW_HASH_A, _AGENT_ID_A, ath, _TS_NS)
        for ath in type_hashes
    ]
    assert len(set(pda_hashes)) == 5


# ---------------------------------------------------------------------------
# T-PDA-6: invalid input lengths raise ValueError
# ---------------------------------------------------------------------------

def test_t_pda_6_invalid_input_lengths_raise():
    """Per-field length validation: each of hardware_data_hash, agent_id,
    and attestation_type_hash must be exactly 32 bytes.
    """
    short = b"\x00" * 16
    long = b"\x00" * 64
    valid = b"\x00" * 32

    # hardware_data_hash wrong length
    with pytest.raises(ValueError, match="hardware_data_hash"):
        compute_pda_hash(short, valid, valid, _TS_NS)
    with pytest.raises(ValueError, match="hardware_data_hash"):
        compute_pda_hash(long, valid, valid, _TS_NS)

    # agent_id wrong length
    with pytest.raises(ValueError, match="agent_id"):
        compute_pda_hash(valid, short, valid, _TS_NS)

    # attestation_type_hash wrong length
    with pytest.raises(ValueError, match="attestation_type_hash"):
        compute_pda_hash(valid, valid, short, _TS_NS)


# ---------------------------------------------------------------------------
# T-PDA-7: ts_ns uint64 range
# ---------------------------------------------------------------------------

def test_t_pda_7_ts_ns_uint64_range():
    """ts_ns must fit in uint64 [0, 2**64 - 1]."""
    valid = b"\x00" * 32

    # Boundary values are accepted
    h_lo = compute_pda_hash(valid, valid, valid, 0)
    h_hi = compute_pda_hash(valid, valid, valid, 0xFFFFFFFFFFFFFFFF)
    assert len(h_lo) == 32
    assert len(h_hi) == 32

    # Out of range raises
    with pytest.raises(ValueError, match="ts_ns"):
        compute_pda_hash(valid, valid, valid, -1)
    with pytest.raises(ValueError, match="ts_ns"):
        compute_pda_hash(valid, valid, valid, 0xFFFFFFFFFFFFFFFF + 1)


# ---------------------------------------------------------------------------
# T-PDA-8: store insert + UNIQUE collision idempotency
# ---------------------------------------------------------------------------

def test_t_pda_8_store_insert_and_unique_idempotency(tmp_path):
    """Inserting a PHYSICAL_DATA_ATTESTATION v1 row writes successfully;
    duplicate insert (same pda_commitment) returns the existing row id
    rather than raising. Mirrors AGENT_COMMIT v1 / corpus_snapshot
    UNIQUE-collision pattern.
    """
    from vapi_bridge.store import Store
    db_path = str(tmp_path / "test_pda_store.db")
    store = Store(db_path)

    pda = compute_pda_hash(_HW_HASH_A, _AGENT_ID_A, _AT_HASH_A, _TS_NS)
    pda_hex = pda.hex()

    row_id_1 = store.insert_physical_data_attestation(
        pda_commitment=pda_hex,
        hardware_data_hash=_HW_HASH_A.hex(),
        agent_id=_AGENT_ID_A.hex(),
        attestation_type=_AT_TYPE_A,
        attestation_type_hash=_AT_HASH_A.hex(),
        ts_ns=_TS_NS,
    )
    assert row_id_1 > 0

    # Duplicate insert returns the existing row id (idempotent).
    row_id_2 = store.insert_physical_data_attestation(
        pda_commitment=pda_hex,
        hardware_data_hash=_HW_HASH_A.hex(),
        agent_id=_AGENT_ID_A.hex(),
        attestation_type=_AT_TYPE_A,
        attestation_type_hash=_AT_HASH_A.hex(),
        ts_ns=_TS_NS,
    )
    assert row_id_2 == row_id_1

    # Status reflects exactly one attestation logged.
    status = store.get_physical_data_attestation_status()
    assert status["total_attestations"] == 1
    assert status["latest_pda_commitment"] == pda_hex
    assert status["latest_agent_id"] == _AGENT_ID_A.hex()
    assert status["latest_attestation_type"] == _AT_TYPE_A
    assert status["on_chain_confirmed"] is False
    assert status["anchor_id"] == -1


# ---------------------------------------------------------------------------
# T-PDA-9: history filtering and DESC ordering
# ---------------------------------------------------------------------------

def test_t_pda_9_history_filter_and_desc_ordering(tmp_path):
    """get_physical_data_attestation_history filters by agent_id,
    attestation_type, both, or neither, and returns DESC ts_ns ordering.
    """
    from vapi_bridge.store import Store
    db_path = str(tmp_path / "test_pda_history.db")
    store = Store(db_path)

    # Insert four attestations across 2 agents × 2 attestation types at
    # distinct timestamps:
    #   Row 1: AGENT_A, BIOMETRIC_CORPUS_SNAPSHOT, ts=T+0
    #   Row 2: AGENT_B, BIOMETRIC_CORPUS_SNAPSHOT, ts=T+1s
    #   Row 3: AGENT_A, TREMOR_FFT_FEATURE_VECTOR, ts=T+2s
    #   Row 4: AGENT_A, BIOMETRIC_CORPUS_SNAPSHOT, ts=T+3s   <- different hw_hash
    h_1 = compute_pda_hash(_HW_HASH_A, _AGENT_ID_A, _AT_HASH_A, _TS_NS)
    h_2 = compute_pda_hash(_HW_HASH_A, _AGENT_ID_B, _AT_HASH_A,
                           _TS_NS + 1_000_000_000)
    h_3 = compute_pda_hash(_HW_HASH_A, _AGENT_ID_A, _AT_HASH_B,
                           _TS_NS + 2_000_000_000)
    h_4 = compute_pda_hash(_HW_HASH_B, _AGENT_ID_A, _AT_HASH_A,
                           _TS_NS + 3_000_000_000)

    store.insert_physical_data_attestation(
        pda_commitment=h_1.hex(), hardware_data_hash=_HW_HASH_A.hex(),
        agent_id=_AGENT_ID_A.hex(), attestation_type=_AT_TYPE_A,
        attestation_type_hash=_AT_HASH_A.hex(), ts_ns=_TS_NS,
    )
    store.insert_physical_data_attestation(
        pda_commitment=h_2.hex(), hardware_data_hash=_HW_HASH_A.hex(),
        agent_id=_AGENT_ID_B.hex(), attestation_type=_AT_TYPE_A,
        attestation_type_hash=_AT_HASH_A.hex(),
        ts_ns=_TS_NS + 1_000_000_000,
    )
    store.insert_physical_data_attestation(
        pda_commitment=h_3.hex(), hardware_data_hash=_HW_HASH_A.hex(),
        agent_id=_AGENT_ID_A.hex(), attestation_type=_AT_TYPE_B,
        attestation_type_hash=_AT_HASH_B.hex(),
        ts_ns=_TS_NS + 2_000_000_000,
    )
    store.insert_physical_data_attestation(
        pda_commitment=h_4.hex(), hardware_data_hash=_HW_HASH_B.hex(),
        agent_id=_AGENT_ID_A.hex(), attestation_type=_AT_TYPE_A,
        attestation_type_hash=_AT_HASH_A.hex(),
        ts_ns=_TS_NS + 3_000_000_000,
    )

    # No filter: all 4 rows DESC.
    all_rows = store.get_physical_data_attestation_history()
    assert len(all_rows) == 4
    assert all_rows[0]["pda_commitment"] == h_4.hex()
    assert all_rows[3]["pda_commitment"] == h_1.hex()

    # Filter by agent_id only: AGENT_A → 3 rows.
    a_rows = store.get_physical_data_attestation_history(
        agent_id=_AGENT_ID_A.hex()
    )
    assert len(a_rows) == 3
    assert a_rows[0]["pda_commitment"] == h_4.hex()
    assert a_rows[2]["pda_commitment"] == h_1.hex()

    # Filter by attestation_type only: BIOMETRIC_CORPUS_SNAPSHOT → 3 rows.
    type_rows = store.get_physical_data_attestation_history(
        attestation_type=_AT_TYPE_A
    )
    assert len(type_rows) == 3
    assert all(r["attestation_type"] == _AT_TYPE_A for r in type_rows)

    # Filter by both: AGENT_A AND BIOMETRIC_CORPUS_SNAPSHOT → 2 rows.
    both_rows = store.get_physical_data_attestation_history(
        agent_id=_AGENT_ID_A.hex(), attestation_type=_AT_TYPE_A,
    )
    assert len(both_rows) == 2
    assert both_rows[0]["pda_commitment"] == h_4.hex()
    assert both_rows[1]["pda_commitment"] == h_1.hex()


# ---------------------------------------------------------------------------
# T-PDA-10: INV-PDA-001 verification
# ---------------------------------------------------------------------------

def test_t_pda_10_inv_pda_001_hash_determinism():
    """INV-PDA-001 (PV-CI candidate): hash determinism property.

    Pass 2C Section 4.2 freezes compute_pda_hash. This test asserts the
    determinism property explicitly so the gate-extension session
    (Stream 3-prep Session 3) can quote it as the determinism check
    when the invariant is frozen via --confirm-governance.
    """
    inputs = (_HW_HASH_A, _AGENT_ID_A, _AT_HASH_A, _TS_NS)
    hashes = [compute_pda_hash(*inputs) for _ in range(10)]
    assert len(set(hashes)) == 1, "hash determinism violated across repeated calls"
    assert all(len(h) == 32 for h in hashes)


# ---------------------------------------------------------------------------
# T-PDA-11: INV-PDA-002 verification
# ---------------------------------------------------------------------------

def test_t_pda_11_inv_pda_002_domain_tag_pinned():
    """INV-PDA-002 (PV-CI candidate, DELTA2-Pass2C): the domain tag
    literal b"VAPI-PHYSICAL-DATA-ATTESTATION-v1" is pinned in
    physical_data_attestation.py.

    Mirrors Stream 3-prep Session 1 INV-AGENT-COMMIT-002 pattern (and
    Phase 237.5 INV-CORPUS-002 pattern). The gate-extension session
    will freeze this via a regex match against the source file in
    vapi_invariant_gate.py's INVARIANTS list.
    """
    # Module-level constant matches the locked literal.
    assert _PDA_TAG == b"VAPI-PHYSICAL-DATA-ATTESTATION-v1"
    # 33 bytes per Finding 1 — Pass 2C said "32 bytes" (off by one).
    assert len(_PDA_TAG) == 33

    # Source-file presence: literal is grep-able from the source.
    import vapi_bridge.physical_data_attestation as pda_mod
    src_path = pda_mod.__file__
    with open(src_path, "r", encoding="utf-8") as f:
        src = f.read()
    assert 'b"VAPI-PHYSICAL-DATA-ATTESTATION-v1"' in src

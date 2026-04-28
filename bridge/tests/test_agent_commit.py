"""Phase O0 Stream 3-prep Session 1 — AGENT_COMMIT v1 (sixth FROZEN-v1 primitive).

Pass 2C Section 4.1 hash formula + Decision T-Pass2C (git-commit-specific
fields) + Decision DELTA-Pass2C (INV-AGENT-COMMIT-002 freezes the domain
tag literal).

Tests:
  T-AC-1: compute_agent_commit_hash determinism — same inputs → same hash
  T-AC-2: per-input-field tamper detection — single-bit changes in each
          field produce a different hash
  T-AC-3: domain tag binding — changing the domain tag (synthetic via
          inline recompute) produces a different hash for identical inputs
  T-AC-4: prev_commit_hash chain property — different prev_commit_hash
          values for the same other inputs produce distinct hashes
          (load-bearing for on-chain chain integrity)
  T-AC-5: genesis_agent_commit produces the canonical first-commit hash
          (commit_sha=20 zero bytes, prev_commit_hash=32 zero bytes,
          repo_uri_sha=SHA-256 of canonical VAPI repo URI)
  T-AC-6: invalid input lengths raise ValueError (per-field length checks)
  T-AC-7: ts_ns out of uint64 range raises ValueError
  T-AC-8: store table insert + status round-trip including UNIQUE
          collision idempotency (mirrors Phase 236 corpus_snapshot test)
  T-AC-9: store get_agent_commit_history filters by agent_id and respects
          DESC ts_ns ordering
  T-AC-10: INV-AGENT-COMMIT-001 verification — hash determinism property
           (a copy of T-AC-1 phrased as the invariant assertion, so future
           PV-CI gate freeze can quote this test as the determinism check)
  T-AC-11: INV-AGENT-COMMIT-002 verification — domain tag literal pinned
           (the literal b"VAPI-AGENT-COMMIT-v1" is present in
           agent_commit.py source as a frozen module-level constant)
"""
import hashlib
import os
import struct
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.agent_commit import (  # noqa: E402
    AgentCommit,
    compute_agent_commit_hash,
    genesis_agent_commit,
    repo_uri_sha_from_uri,
    _AGENT_COMMIT_TAG,
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
_COMMIT_SHA_A = bytes.fromhex("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")  # 20 bytes
_COMMIT_SHA_B = bytes.fromhex("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
_PREV_HASH_A = bytes.fromhex(
    "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
)
_PREV_HASH_B = bytes.fromhex(
    "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
)
_REPO_URI_SHA_A = hashlib.sha256(b"https://github.com/ConWan30/vapi-prototype").digest()
_REPO_URI_SHA_B = hashlib.sha256(b"https://github.com/ConWan30/some-other-repo").digest()
_TS_NS = 1_700_000_000_000_000_000  # 2023-11-14 in ns


# ---------------------------------------------------------------------------
# T-AC-1: hash determinism
# ---------------------------------------------------------------------------

def test_t_ac_1_hash_determinism():
    """INV-AGENT-COMMIT-001: same inputs always produce the same hash."""
    h1 = compute_agent_commit_hash(_AGENT_ID_A, _COMMIT_SHA_A, _PREV_HASH_A,
                                   _REPO_URI_SHA_A, _TS_NS)
    h2 = compute_agent_commit_hash(_AGENT_ID_A, _COMMIT_SHA_A, _PREV_HASH_A,
                                   _REPO_URI_SHA_A, _TS_NS)
    assert h1 == h2
    assert len(h1) == 32

    # Manual SHA-256 recompute as cross-check against the FROZEN formula.
    expected = hashlib.sha256(
        _AGENT_COMMIT_TAG
        + _AGENT_ID_A
        + _COMMIT_SHA_A
        + _PREV_HASH_A
        + _REPO_URI_SHA_A
        + struct.pack(">Q", _TS_NS)
    ).digest()
    assert h1 == expected


# ---------------------------------------------------------------------------
# T-AC-2: per-input-field tamper detection
# ---------------------------------------------------------------------------

def test_t_ac_2_tamper_detection_per_field():
    """Changing any single input field produces a different hash."""
    base = compute_agent_commit_hash(
        _AGENT_ID_A, _COMMIT_SHA_A, _PREV_HASH_A, _REPO_URI_SHA_A, _TS_NS
    )

    # Different agent_id → different hash
    h_agent = compute_agent_commit_hash(
        _AGENT_ID_B, _COMMIT_SHA_A, _PREV_HASH_A, _REPO_URI_SHA_A, _TS_NS
    )
    assert h_agent != base

    # Different commit_sha → different hash
    h_sha = compute_agent_commit_hash(
        _AGENT_ID_A, _COMMIT_SHA_B, _PREV_HASH_A, _REPO_URI_SHA_A, _TS_NS
    )
    assert h_sha != base

    # Different prev_commit_hash → different hash
    h_prev = compute_agent_commit_hash(
        _AGENT_ID_A, _COMMIT_SHA_A, _PREV_HASH_B, _REPO_URI_SHA_A, _TS_NS
    )
    assert h_prev != base

    # Different repo_uri_sha → different hash
    h_repo = compute_agent_commit_hash(
        _AGENT_ID_A, _COMMIT_SHA_A, _PREV_HASH_A, _REPO_URI_SHA_B, _TS_NS
    )
    assert h_repo != base

    # Different ts_ns (single-second change) → different hash
    h_ts = compute_agent_commit_hash(
        _AGENT_ID_A, _COMMIT_SHA_A, _PREV_HASH_A, _REPO_URI_SHA_A, _TS_NS + 1
    )
    assert h_ts != base

    # All four field-change hashes are pairwise distinct.
    all_hashes = {base, h_agent, h_sha, h_prev, h_repo, h_ts}
    assert len(all_hashes) == 6


# ---------------------------------------------------------------------------
# T-AC-3: domain tag binding
# ---------------------------------------------------------------------------

def test_t_ac_3_domain_tag_binding():
    """Different domain tag → different hash for identical inputs.

    Verifies that the domain tag is part of the hash input, so a
    AGENT_COMMIT v2 (with a different tag) would not collide with v1
    even if all other inputs are identical.
    """
    h_v1 = compute_agent_commit_hash(
        _AGENT_ID_A, _COMMIT_SHA_A, _PREV_HASH_A, _REPO_URI_SHA_A, _TS_NS
    )

    # Synthetic v2 hash recompute with a different tag.
    fake_v2_tag = b"VAPI-AGENT-COMMIT-v2"
    h_v2 = hashlib.sha256(
        fake_v2_tag
        + _AGENT_ID_A
        + _COMMIT_SHA_A
        + _PREV_HASH_A
        + _REPO_URI_SHA_A
        + struct.pack(">Q", _TS_NS)
    ).digest()

    assert h_v1 != h_v2


# ---------------------------------------------------------------------------
# T-AC-4: prev_commit_hash chain property
# ---------------------------------------------------------------------------

def test_t_ac_4_prev_commit_hash_chain_property():
    """Chain of three commits where commit N+1's prev_commit_hash is commit N's hash.

    Verifies the on-chain hash chain mirrors git's commit chain. Tampering
    with any earlier commit in the chain invalidates every subsequent
    commit's hash via the prev_commit_hash dependency.
    """
    genesis = genesis_agent_commit(_AGENT_ID_A, _TS_NS)

    commit_2 = compute_agent_commit_hash(
        _AGENT_ID_A, _COMMIT_SHA_A, genesis, _REPO_URI_SHA_A, _TS_NS + 1_000_000_000
    )
    commit_3 = compute_agent_commit_hash(
        _AGENT_ID_A, _COMMIT_SHA_B, commit_2, _REPO_URI_SHA_A, _TS_NS + 2_000_000_000
    )

    # Three distinct hashes form the chain.
    assert genesis != commit_2
    assert commit_2 != commit_3
    assert genesis != commit_3

    # If commit_2's prev_commit_hash were tampered (e.g., swapped to a
    # different agent's genesis), commit_3's hash would no longer match.
    foreign_genesis = genesis_agent_commit(_AGENT_ID_B, _TS_NS)
    tampered_commit_2 = compute_agent_commit_hash(
        _AGENT_ID_A, _COMMIT_SHA_A, foreign_genesis, _REPO_URI_SHA_A,
        _TS_NS + 1_000_000_000,
    )
    tampered_commit_3 = compute_agent_commit_hash(
        _AGENT_ID_A, _COMMIT_SHA_B, tampered_commit_2, _REPO_URI_SHA_A,
        _TS_NS + 2_000_000_000,
    )
    assert tampered_commit_3 != commit_3


# ---------------------------------------------------------------------------
# T-AC-5: genesis canonical form
# ---------------------------------------------------------------------------

def test_t_ac_5_genesis_canonical_form():
    """genesis_agent_commit produces the canonical first-commit hash.

    Genesis has commit_sha = 20 zeros, prev_commit_hash = 32 zeros, and
    repo_uri_sha = SHA-256 of the canonical VAPI repo URI.
    """
    canonical_repo_uri_sha = hashlib.sha256(
        b"https://github.com/ConWan30/vapi-prototype"
    ).digest()

    h_genesis = genesis_agent_commit(_AGENT_ID_A, _TS_NS)

    h_manual = compute_agent_commit_hash(
        agent_id=_AGENT_ID_A,
        commit_sha=b"\x00" * 20,
        prev_commit_hash=b"\x00" * 32,
        repo_uri_sha=canonical_repo_uri_sha,
        ts_ns=_TS_NS,
    )

    assert h_genesis == h_manual

    # Confirm the helper repo_uri_sha_from_uri produces the same canonical hash.
    assert repo_uri_sha_from_uri(
        "https://github.com/ConWan30/vapi-prototype"
    ) == canonical_repo_uri_sha


# ---------------------------------------------------------------------------
# T-AC-6: invalid input lengths raise ValueError
# ---------------------------------------------------------------------------

def test_t_ac_6_invalid_input_lengths_raise():
    """Per-field length validation: each malformed input raises ValueError."""
    with pytest.raises(ValueError, match="agent_id"):
        compute_agent_commit_hash(
            b"\x00" * 31, _COMMIT_SHA_A, _PREV_HASH_A, _REPO_URI_SHA_A, _TS_NS
        )
    with pytest.raises(ValueError, match="commit_sha"):
        compute_agent_commit_hash(
            _AGENT_ID_A, b"\x00" * 19, _PREV_HASH_A, _REPO_URI_SHA_A, _TS_NS
        )
    with pytest.raises(ValueError, match="commit_sha"):
        # 32-byte commit_sha is wrong (must be 20 bytes for git SHA-1)
        compute_agent_commit_hash(
            _AGENT_ID_A, b"\x00" * 32, _PREV_HASH_A, _REPO_URI_SHA_A, _TS_NS
        )
    with pytest.raises(ValueError, match="prev_commit_hash"):
        compute_agent_commit_hash(
            _AGENT_ID_A, _COMMIT_SHA_A, b"\x00" * 31, _REPO_URI_SHA_A, _TS_NS
        )
    with pytest.raises(ValueError, match="repo_uri_sha"):
        compute_agent_commit_hash(
            _AGENT_ID_A, _COMMIT_SHA_A, _PREV_HASH_A, b"\x00" * 33, _TS_NS
        )


# ---------------------------------------------------------------------------
# T-AC-7: ts_ns out of uint64 range raises
# ---------------------------------------------------------------------------

def test_t_ac_7_ts_ns_uint64_range():
    """ts_ns must be in uint64 range [0, 2^64 - 1]."""
    with pytest.raises(ValueError, match="ts_ns"):
        compute_agent_commit_hash(
            _AGENT_ID_A, _COMMIT_SHA_A, _PREV_HASH_A, _REPO_URI_SHA_A, -1
        )
    with pytest.raises(ValueError, match="ts_ns"):
        compute_agent_commit_hash(
            _AGENT_ID_A, _COMMIT_SHA_A, _PREV_HASH_A, _REPO_URI_SHA_A,
            0x10000000000000000,  # 2^64
        )
    # Boundary values 0 and 2^64 - 1 are accepted.
    compute_agent_commit_hash(
        _AGENT_ID_A, _COMMIT_SHA_A, _PREV_HASH_A, _REPO_URI_SHA_A, 0
    )
    compute_agent_commit_hash(
        _AGENT_ID_A, _COMMIT_SHA_A, _PREV_HASH_A, _REPO_URI_SHA_A,
        0xFFFFFFFFFFFFFFFF,
    )


# ---------------------------------------------------------------------------
# T-AC-8: store insert + UNIQUE collision idempotency
# ---------------------------------------------------------------------------

def test_t_ac_8_store_insert_and_unique_idempotency(tmp_path):
    """Inserting an AGENT_COMMIT v1 row writes successfully; duplicate
    insert (same commit_hash) returns the existing row id rather than
    raising. Mirrors Phase 236 corpus_snapshot UNIQUE-collision pattern."""
    from vapi_bridge.store import Store
    db_path = str(tmp_path / "test_agent_commit_store.db")
    store = Store(db_path)

    h = compute_agent_commit_hash(
        _AGENT_ID_A, _COMMIT_SHA_A, _PREV_HASH_A, _REPO_URI_SHA_A, _TS_NS
    )
    h_hex = h.hex()

    row_id_1 = store.insert_agent_commit(
        commit_hash=h_hex,
        agent_id=_AGENT_ID_A.hex(),
        commit_sha=_COMMIT_SHA_A.hex(),
        prev_commit_hash=_PREV_HASH_A.hex(),
        repo_uri_sha=_REPO_URI_SHA_A.hex(),
        ts_ns=_TS_NS,
    )
    assert row_id_1 > 0

    # Duplicate insert returns the existing row id (idempotent).
    row_id_2 = store.insert_agent_commit(
        commit_hash=h_hex,
        agent_id=_AGENT_ID_A.hex(),
        commit_sha=_COMMIT_SHA_A.hex(),
        prev_commit_hash=_PREV_HASH_A.hex(),
        repo_uri_sha=_REPO_URI_SHA_A.hex(),
        ts_ns=_TS_NS,
    )
    assert row_id_2 == row_id_1

    # Status reflects exactly one commit logged.
    status = store.get_agent_commit_status()
    assert status["total_commits"] == 1
    assert status["latest_hash"] == h_hex
    assert status["latest_agent_id"] == _AGENT_ID_A.hex()
    assert status["on_chain_confirmed"] is False
    assert status["anchor_id"] == -1


# ---------------------------------------------------------------------------
# T-AC-9: history filtering and DESC ordering
# ---------------------------------------------------------------------------

def test_t_ac_9_history_filter_and_desc_ordering(tmp_path):
    """get_agent_commit_history filters by agent_id when provided and
    returns DESC ts_ns ordering across all rows when not."""
    from vapi_bridge.store import Store
    db_path = str(tmp_path / "test_agent_commit_history.db")
    store = Store(db_path)

    # Insert three commits across two agents at distinct timestamps.
    h_a1 = compute_agent_commit_hash(_AGENT_ID_A, _COMMIT_SHA_A,
                                     _PREV_HASH_A, _REPO_URI_SHA_A, _TS_NS)
    h_a2 = compute_agent_commit_hash(_AGENT_ID_A, _COMMIT_SHA_B,
                                     h_a1, _REPO_URI_SHA_A, _TS_NS + 1_000_000_000)
    h_b1 = compute_agent_commit_hash(_AGENT_ID_B, _COMMIT_SHA_A,
                                     _PREV_HASH_A, _REPO_URI_SHA_A, _TS_NS + 500_000_000)

    store.insert_agent_commit(
        commit_hash=h_a1.hex(), agent_id=_AGENT_ID_A.hex(),
        commit_sha=_COMMIT_SHA_A.hex(), prev_commit_hash=_PREV_HASH_A.hex(),
        repo_uri_sha=_REPO_URI_SHA_A.hex(), ts_ns=_TS_NS,
    )
    store.insert_agent_commit(
        commit_hash=h_b1.hex(), agent_id=_AGENT_ID_B.hex(),
        commit_sha=_COMMIT_SHA_A.hex(), prev_commit_hash=_PREV_HASH_A.hex(),
        repo_uri_sha=_REPO_URI_SHA_A.hex(), ts_ns=_TS_NS + 500_000_000,
    )
    store.insert_agent_commit(
        commit_hash=h_a2.hex(), agent_id=_AGENT_ID_A.hex(),
        commit_sha=_COMMIT_SHA_B.hex(), prev_commit_hash=h_a1.hex(),
        repo_uri_sha=_REPO_URI_SHA_A.hex(), ts_ns=_TS_NS + 1_000_000_000,
    )

    # All-agent history: 3 rows in DESC ts_ns order.
    all_rows = store.get_agent_commit_history()
    assert len(all_rows) == 3
    assert all_rows[0]["commit_hash"] == h_a2.hex()  # newest
    assert all_rows[1]["commit_hash"] == h_b1.hex()
    assert all_rows[2]["commit_hash"] == h_a1.hex()  # oldest

    # Filtered by AGENT_A: 2 rows.
    a_rows = store.get_agent_commit_history(agent_id=_AGENT_ID_A.hex())
    assert len(a_rows) == 2
    assert a_rows[0]["commit_hash"] == h_a2.hex()
    assert a_rows[1]["commit_hash"] == h_a1.hex()

    # Filtered by AGENT_B: 1 row.
    b_rows = store.get_agent_commit_history(agent_id=_AGENT_ID_B.hex())
    assert len(b_rows) == 1
    assert b_rows[0]["commit_hash"] == h_b1.hex()


# ---------------------------------------------------------------------------
# T-AC-10: INV-AGENT-COMMIT-001 verification
# ---------------------------------------------------------------------------

def test_t_ac_10_inv_agent_commit_001_hash_determinism():
    """INV-AGENT-COMMIT-001 (PV-CI candidate): hash determinism property.

    Pass 2C Section 4.1 freezes compute_agent_commit_hash. This test
    asserts the determinism property explicitly so the gate-extension
    session can quote it as the determinism check when the invariant
    is frozen via --confirm-governance.
    """
    inputs = (_AGENT_ID_A, _COMMIT_SHA_A, _PREV_HASH_A, _REPO_URI_SHA_A, _TS_NS)
    hashes = [compute_agent_commit_hash(*inputs) for _ in range(10)]
    assert len(set(hashes)) == 1, "hash determinism violated across repeated calls"
    assert all(len(h) == 32 for h in hashes)


# ---------------------------------------------------------------------------
# T-AC-11: INV-AGENT-COMMIT-002 verification
# ---------------------------------------------------------------------------

def test_t_ac_11_inv_agent_commit_002_domain_tag_pinned():
    """INV-AGENT-COMMIT-002 (PV-CI candidate, DELTA-Pass2C): the domain
    tag literal b"VAPI-AGENT-COMMIT-v1" is pinned in agent_commit.py.

    Mirrors Phase 237.5 INV-CORPUS-002 pattern. The gate-extension
    session will freeze this via a regex match against the source file
    in vapi_invariant_gate.py's INVARIANTS list.
    """
    # Module-level constant matches the locked literal.
    assert _AGENT_COMMIT_TAG == b"VAPI-AGENT-COMMIT-v1"
    assert len(_AGENT_COMMIT_TAG) == 20

    # Source-file presence: literal is grep-able from the source.
    import vapi_bridge.agent_commit as ac_mod
    src_path = ac_mod.__file__
    with open(src_path, "r", encoding="utf-8") as f:
        src = f.read()
    assert 'b"VAPI-AGENT-COMMIT-v1"' in src

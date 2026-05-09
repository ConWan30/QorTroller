"""Phase 237-ZK-SEPPROOF — BIOMETRIC-SNAPSHOT-v1 primitive tests.

Verifies the FROZEN-v1 formula is byte-identical for canonical inputs,
deterministic across reruns, sensitive to every input field, and properly
bounds-checks scale overflow.

This primitive is the cryptographic binding between AIT centroids/cov_inv
and on-chain anchored snapshots. ZK-SEPPROOF circuit consumes the
commitment as a public input. Any change to byte order, scale, or domain
tag invalidates every prior anchored snapshot — these tests are the
regression guard.

T-237-SEP-BS-1..10.
"""
from __future__ import annotations

import hashlib
import struct
import sys
import types as _types
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BRIDGE_DIR = Path(__file__).parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

# Stub heavy-import modules
for _mod in ["web3", "web3.exceptions", "eth_account", "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _types.ModuleType(_mod)
if "dotenv" not in sys.modules:
    _dotenv = _types.ModuleType("dotenv")
    _dotenv.load_dotenv = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules["dotenv"] = _dotenv

from vapi_bridge.biometric_snapshot import (  # noqa: E402
    compute_biometric_commitment,
    expected_body_length,
    _SNAPSHOT_TAG,
    _FROZEN_SCALE,
)


# ── Canonical AIT-shaped inputs (Phase 229: F=4, N=3) ───────────────────────

CANONICAL_FEATURE_DIM = 4
CANONICAL_PLAYER_IDS = [0, 1, 2]
CANONICAL_CENTROIDS = {
    0: [9.37, 0.85, 0.52, 0.71],     # P1: tremor 9.37 Hz, gravity-derived angles
    1: [1.71, 0.92, 0.39, 0.67],     # P2
    2: [3.85, 0.78, 0.61, 0.82],     # P3
}
CANONICAL_COV_INV = [
    [ 0.045, -0.012,  0.003,  0.001],
    [-0.012,  2.310, -0.085,  0.122],
    [ 0.003, -0.085,  3.040, -0.218],
    [ 0.001,  0.122, -0.218,  2.760],
]
CANONICAL_TS_NS = 1_778_316_000_000_000_000   # 2026-05-09T13:00 UTC equivalent


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-BS-1: domain tag is 25 bytes literal
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_bs_1_domain_tag_frozen():
    """FROZEN: domain tag must be exactly b'VAPI-BIOMETRIC-SNAPSHOT-v1' (26 bytes).
    Any change is a v2 break and invalidates all prior anchors."""
    assert _SNAPSHOT_TAG == b"VAPI-BIOMETRIC-SNAPSHOT-v1"
    assert len(_SNAPSHOT_TAG) == 26


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-BS-2: scale factor is 1e9 literal
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_bs_2_scale_frozen():
    """FROZEN: scale factor must be exactly 1_000_000_000. Smaller scales lose
    cov_inv precision; larger scales risk int64 overflow on extreme corpus."""
    assert _FROZEN_SCALE == 1_000_000_000


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-BS-3: expected body length matches Phase 229 AIT shape
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_bs_3_body_length_ait_shape():
    """AIT (F=4, N=3) must produce 263-byte canonical body.

    Layout: 26 (tag) + 1 (F) + 1 (N) + 3 (ids) + 96 (centroids) + 128 (cov_inv) + 8 (ts) = 263.
    """
    assert expected_body_length(feature_dim=4, n_players=3) == 263


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-BS-4: commitment is deterministic (same inputs -> same digest)
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_bs_4_deterministic():
    c1 = compute_biometric_commitment(
        feature_dim=CANONICAL_FEATURE_DIM,
        sorted_player_ids=CANONICAL_PLAYER_IDS,
        centroids_by_player=CANONICAL_CENTROIDS,
        cov_inv=CANONICAL_COV_INV,
        ts_ns=CANONICAL_TS_NS,
    )
    c2 = compute_biometric_commitment(
        feature_dim=CANONICAL_FEATURE_DIM,
        sorted_player_ids=CANONICAL_PLAYER_IDS,
        centroids_by_player=CANONICAL_CENTROIDS,
        cov_inv=CANONICAL_COV_INV,
        ts_ns=CANONICAL_TS_NS,
    )
    assert c1 == c2
    assert len(c1) == 32  # SHA-256 output


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-BS-5: manual SHA-256 reconstruction matches commitment
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_bs_5_manual_recompute_matches():
    """Verify the canonical body layout by reconstructing the digest manually.
    This is the regression guard against silent layout changes."""
    expected_body = bytearray()
    expected_body.extend(_SNAPSHOT_TAG)
    expected_body.append(4)            # feature_dim
    expected_body.append(3)            # n_players
    for pid in [0, 1, 2]:
        expected_body.append(pid)
    # Centroids row-major sorted by player_id ascending
    for pid in [0, 1, 2]:
        for v in CANONICAL_CENTROIDS[pid]:
            scaled = int(round(v * 1_000_000_000))
            expected_body.extend(struct.pack(">q", scaled))
    # cov_inv row-major
    for row in CANONICAL_COV_INV:
        for v in row:
            scaled = int(round(v * 1_000_000_000))
            expected_body.extend(struct.pack(">q", scaled))
    expected_body.extend(struct.pack(">Q", CANONICAL_TS_NS))

    expected_digest = hashlib.sha256(bytes(expected_body)).digest()
    actual_digest = compute_biometric_commitment(
        feature_dim=CANONICAL_FEATURE_DIM,
        sorted_player_ids=CANONICAL_PLAYER_IDS,
        centroids_by_player=CANONICAL_CENTROIDS,
        cov_inv=CANONICAL_COV_INV,
        ts_ns=CANONICAL_TS_NS,
    )
    assert actual_digest == expected_digest
    # Body length matches expected
    assert len(expected_body) == expected_body_length(4, 3) == 263


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-BS-6: every input field is sensitive (changing one changes digest)
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_bs_6_per_input_sensitivity():
    """Changing ANY field must change the digest. Partial sensitivity is a
    bug — a malicious prover could find equivalent inputs with same digest."""
    base = compute_biometric_commitment(
        feature_dim=4,
        sorted_player_ids=[0, 1, 2],
        centroids_by_player=CANONICAL_CENTROIDS,
        cov_inv=CANONICAL_COV_INV,
        ts_ns=CANONICAL_TS_NS,
    )

    # Change one centroid value
    cents_mod = {k: list(v) for k, v in CANONICAL_CENTROIDS.items()}
    cents_mod[0] = [9.38, 0.85, 0.52, 0.71]  # tweak P1 tremor by 0.01 Hz
    c_centroid_change = compute_biometric_commitment(
        feature_dim=4, sorted_player_ids=[0, 1, 2],
        centroids_by_player=cents_mod, cov_inv=CANONICAL_COV_INV,
        ts_ns=CANONICAL_TS_NS,
    )
    assert c_centroid_change != base, "centroid sensitivity broken"

    # Change one cov_inv value
    cov_mod = [list(row) for row in CANONICAL_COV_INV]
    cov_mod[0][0] = 0.046  # tweak by 0.001
    c_cov_change = compute_biometric_commitment(
        feature_dim=4, sorted_player_ids=[0, 1, 2],
        centroids_by_player=CANONICAL_CENTROIDS, cov_inv=cov_mod,
        ts_ns=CANONICAL_TS_NS,
    )
    assert c_cov_change != base, "cov_inv sensitivity broken"

    # Change ts_ns
    c_ts_change = compute_biometric_commitment(
        feature_dim=4, sorted_player_ids=[0, 1, 2],
        centroids_by_player=CANONICAL_CENTROIDS, cov_inv=CANONICAL_COV_INV,
        ts_ns=CANONICAL_TS_NS + 1,
    )
    assert c_ts_change != base, "ts_ns sensitivity broken"

    # Change feature_dim — would require centroid reshape; smoke check via different N
    cents_2p = {0: [9.37, 0.85, 0.52, 0.71], 1: [1.71, 0.92, 0.39, 0.67]}
    c_fewer = compute_biometric_commitment(
        feature_dim=4, sorted_player_ids=[0, 1],
        centroids_by_player=cents_2p, cov_inv=CANONICAL_COV_INV,
        ts_ns=CANONICAL_TS_NS,
    )
    assert c_fewer != base, "n_players sensitivity broken"


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-BS-7: sort order canonicality (unsorted input -> same digest as sorted)
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_bs_7_sort_order_canonical():
    """The function defensively re-sorts player_ids ascending. Caller passing
    [2, 0, 1] must produce same digest as [0, 1, 2]. Otherwise canonical-form
    requirement is broken."""
    sorted_digest = compute_biometric_commitment(
        feature_dim=4, sorted_player_ids=[0, 1, 2],
        centroids_by_player=CANONICAL_CENTROIDS, cov_inv=CANONICAL_COV_INV,
        ts_ns=CANONICAL_TS_NS,
    )
    unsorted_digest = compute_biometric_commitment(
        feature_dim=4, sorted_player_ids=[2, 0, 1],
        centroids_by_player=CANONICAL_CENTROIDS, cov_inv=CANONICAL_COV_INV,
        ts_ns=CANONICAL_TS_NS,
    )
    assert sorted_digest == unsorted_digest, (
        "canonical sort broken — same logical inputs in different order produce "
        "different digests, allowing malleability"
    )


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-BS-8: missing centroid raises ValueError
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_bs_8_missing_centroid_raises():
    incomplete = {0: [9.37, 0.85, 0.52, 0.71], 1: [1.71, 0.92, 0.39, 0.67]}
    with pytest.raises(ValueError, match="missing centroid"):
        compute_biometric_commitment(
            feature_dim=4, sorted_player_ids=[0, 1, 2],  # 2 not in dict
            centroids_by_player=incomplete, cov_inv=CANONICAL_COV_INV,
            ts_ns=CANONICAL_TS_NS,
        )


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-BS-9: shape mismatch raises ValueError
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_bs_9_shape_mismatch_raises():
    # Wrong centroid length
    bad_cents = dict(CANONICAL_CENTROIDS)
    bad_cents[0] = [9.37, 0.85, 0.52]  # 3 features instead of 4
    with pytest.raises(ValueError, match="centroid for player .* has len"):
        compute_biometric_commitment(
            feature_dim=4, sorted_player_ids=[0, 1, 2],
            centroids_by_player=bad_cents, cov_inv=CANONICAL_COV_INV,
            ts_ns=CANONICAL_TS_NS,
        )

    # Wrong cov_inv shape
    bad_cov = [[1.0, 0.0], [0.0, 1.0]]  # 2x2 instead of 4x4
    with pytest.raises(ValueError, match="cov_inv must be"):
        compute_biometric_commitment(
            feature_dim=4, sorted_player_ids=[0, 1, 2],
            centroids_by_player=CANONICAL_CENTROIDS, cov_inv=bad_cov,
            ts_ns=CANONICAL_TS_NS,
        )


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-BS-10: scale overflow raises (defends against extreme inputs)
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_bs_10_scale_overflow_raises():
    """A centroid value of 1e10 scaled by 1e9 = 1e19 — overflows int64.
    Function must raise rather than silently truncate."""
    overflow_cents = dict(CANONICAL_CENTROIDS)
    overflow_cents[0] = [1e10, 0.85, 0.52, 0.71]  # absurd tremor freq
    with pytest.raises(ValueError, match="overflow"):
        compute_biometric_commitment(
            feature_dim=4, sorted_player_ids=[0, 1, 2],
            centroids_by_player=overflow_cents, cov_inv=CANONICAL_COV_INV,
            ts_ns=CANONICAL_TS_NS,
        )


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-BS-11: ts_ns uint64 boundary
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_bs_11_ts_uint64_boundary():
    """ts_ns must be in uint64 range. Negative or > 2^64-1 raises."""
    with pytest.raises(ValueError, match="ts_ns out of uint64 range"):
        compute_biometric_commitment(
            feature_dim=4, sorted_player_ids=[0, 1, 2],
            centroids_by_player=CANONICAL_CENTROIDS, cov_inv=CANONICAL_COV_INV,
            ts_ns=-1,
        )
    with pytest.raises(ValueError, match="ts_ns out of uint64 range"):
        compute_biometric_commitment(
            feature_dim=4, sorted_player_ids=[0, 1, 2],
            centroids_by_player=CANONICAL_CENTROIDS, cov_inv=CANONICAL_COV_INV,
            ts_ns=2**64,
        )

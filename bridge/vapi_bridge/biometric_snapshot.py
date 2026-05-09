"""Phase 237-ZK-SEPPROOF — Biometric snapshot primitive. FROZEN FORMULA v1.

Sixth member of the PATTERN-016 FROZEN-v1 family alongside GIC (Phase 235-A),
WEC (Phase 236-WATCHDOG), VAME (Phase 236-VAME), CORPUS-SNAPSHOT
(Phase 237.5), and CONSENT (Phase 237).

What this primitive binds (vs CORPUS-SNAPSHOT-v1):
    CORPUS-SNAPSHOT binds wiki state + agent root + ratio + corpus_n —
    the *governance posture* of the corpus at a moment in time. It does
    NOT bind the actual centroid or covariance values, because those
    weren't needed for ratio-based gating.

    BIOMETRIC-SNAPSHOT binds the actual per-player centroids + pooled
    inverse covariance matrix bytes themselves. Required for ZK-SEPPROOF
    soundness: the ZK verifier needs to assert the witness centroids
    cryptographically match an on-chain commitment, not just
    operator-trusted off-chain values.

    These are complementary, not redundant. CORPUS-SNAPSHOT serves
    governance/audit. BIOMETRIC-SNAPSHOT serves cryptographic separation
    proof binding.

Snapshot triggers (caller-driven; this module is pure functions):
    - New AIT session inserted that changes centroids meaningfully
    - Recalibration that updates pooled cov_inv
    - Manual via POST /operator/anchor-biometric-snapshot
    - First-anchor at AIT P0 gate clearance (current state: ratio=1.199,
      all_pairs_above_1=True, N=37)

BIOMETRIC-SNAPSHOT_v1 commitment formula:
    commitment = SHA-256(
        b"VAPI-BIOMETRIC-SNAPSHOT-v1" (26 bytes)  — domain separation
        || feature_dim_be             (1 byte)    — uint8: number of features
        || n_players_be               (1 byte)    — uint8: number of players
        || sorted_player_ids          (N bytes)   — sorted ascending uint8 player IDs
        || centroids_scaled_be        (N × F × 8) — int64 BE: centroid * 1e9, row-major,
                                                    sorted by player_id ascending
        || cov_inv_scaled_be          (F × F × 8) — int64 BE: cov_inv * 1e9, row-major
        || ts_ns_be                   (8 bytes)   — uint64 BE: snapshot time
    )

    For AIT (F=4, N=3):  26 + 1 + 1 + 3 + 96 + 128 + 8 = 263 bytes -> SHA-256 -> 32 bytes

Scale factor (FROZEN): 1_000_000_000 (1e9).
    Matches the precision tier above CORPUS-SNAPSHOT's ratio_milli (1e6) because
    cov_inv values are typically smaller (sub-unit) and need finer resolution.

    AIT centroid value ranges (empirical Phase 229):
      accel_tremor_peak_hz: 1-60 Hz   -> scaled int64: 1e9 to 6e10  (well within range)
      roll_cos, roll_sin:    [-1, 1]  -> scaled int64: -1e9 to +1e9
      pitch_cos:             [-1, 1]  -> scaled int64: -1e9 to +1e9

    cov_inv typical values: -10 to +10 -> scaled int64: -1e10 to +1e10

    int64 range: ~+/-9.2e18 -> ~9 orders of magnitude of headroom.

Endian (FROZEN): big-endian throughout (matches all other PATTERN-016 primitives).

Sort order (FROZEN): player_ids sorted ascending. Centroids ordered to match.
    Cov_inv is row-major (cov_inv[i][j] for i in 0..F-1, j in 0..F-1).

Any change to byte order, domain tag, scale factor, sort rule, or signed vs unsigned
encoding requires v2 + new tag. v1 is permanently frozen.
"""
from __future__ import annotations

import hashlib
import struct
from typing import Mapping, Sequence

# ── Frozen constants ─────────────────────────────────────────────────────────

_SNAPSHOT_TAG = b"VAPI-BIOMETRIC-SNAPSHOT-v1"   # 26 bytes
_FROZEN_SCALE = 1_000_000_000                    # 1e9 — finer than CORPUS-SNAPSHOT's 1e6

_INT64_MIN = -(1 << 63)        # -9_223_372_036_854_775_808
_INT64_MAX = (1 << 63) - 1     #  9_223_372_036_854_775_807


def _scale_value(x: float) -> int:
    """Convert a float to scaled int64 (x * 1e9, rounded), with bounds check.

    Raises ValueError if scaled value would overflow signed int64.
    """
    if x is None:
        x = 0.0
    n = int(round(float(x) * _FROZEN_SCALE))
    if n < _INT64_MIN or n > _INT64_MAX:
        raise ValueError(
            f"scaled value {n} (from {x}) overflows int64 range "
            f"[{_INT64_MIN}, {_INT64_MAX}]"
        )
    return n


def _pack_matrix_row_major(matrix: Sequence[Sequence[float]]) -> bytes:
    """Pack a 2D float matrix row-major as int64 BE scaled values.

    Returns concatenated big-endian signed int64 bytes. No row/col delimiters —
    callers commit to the matrix shape via separate fields (feature_dim,
    n_players) to disambiguate during reconstruction.
    """
    out = bytearray()
    for row in matrix:
        for cell in row:
            out.extend(struct.pack(">q", _scale_value(cell)))
    return bytes(out)


def compute_biometric_commitment(
    feature_dim: int,
    sorted_player_ids: Sequence[int],
    centroids_by_player: Mapping[int, Sequence[float]],
    cov_inv: Sequence[Sequence[float]],
    ts_ns: int,
) -> bytes:
    """Compute the biometric snapshot commitment v1 — FROZEN formula.

    Args:
        feature_dim: Number of biometric features (e.g. 4 for AIT).
        sorted_player_ids: Ascending uint8 player IDs (e.g. [0, 1, 2] for AIT).
                            Caller is responsible for sorting; we re-sort defensively
                            but commitment is based on the canonical sorted order.
        centroids_by_player: Mapping player_id -> sequence of `feature_dim` floats.
                              Every ID in sorted_player_ids must be present.
        cov_inv:         feature_dim x feature_dim pooled inverse covariance matrix.
        ts_ns:           Unix timestamp in nanoseconds (uint64).

    Returns:
        32-byte SHA-256 digest.

    Raises:
        ValueError on shape mismatches, missing players, or scale overflow.
    """
    # Defensive validations
    if not (1 <= int(feature_dim) <= 255):
        raise ValueError(f"feature_dim must be in [1, 255], got {feature_dim}")
    if not (0 <= int(ts_ns) <= 0xFFFFFFFFFFFFFFFF):
        raise ValueError(f"ts_ns out of uint64 range: {ts_ns}")

    sorted_ids = sorted(int(pid) for pid in sorted_player_ids)
    n_players = len(sorted_ids)
    if not (1 <= n_players <= 255):
        raise ValueError(f"n_players must be in [1, 255], got {n_players}")
    for pid in sorted_ids:
        if not (0 <= pid <= 255):
            raise ValueError(f"player_id must be uint8, got {pid}")

    # Centroid shape check
    centroids_ordered: list[list[float]] = []
    for pid in sorted_ids:
        if pid not in centroids_by_player:
            raise ValueError(f"missing centroid for player_id={pid}")
        cent = centroids_by_player[pid]
        if len(cent) != feature_dim:
            raise ValueError(
                f"centroid for player {pid} has len {len(cent)}, expected {feature_dim}"
            )
        centroids_ordered.append([float(v) for v in cent])

    # cov_inv shape check
    if len(cov_inv) != feature_dim:
        raise ValueError(
            f"cov_inv must be {feature_dim}x{feature_dim}, got {len(cov_inv)} rows"
        )
    for i, row in enumerate(cov_inv):
        if len(row) != feature_dim:
            raise ValueError(
                f"cov_inv row {i} has len {len(row)}, expected {feature_dim}"
            )

    # Compose the canonical bytestream
    body = bytearray()
    body.extend(_SNAPSHOT_TAG)                                  # 25 bytes
    body.append(int(feature_dim))                                # 1 byte
    body.append(n_players)                                       # 1 byte
    for pid in sorted_ids:
        body.append(pid)                                         # N bytes
    body.extend(_pack_matrix_row_major(centroids_ordered))       # N x F x 8 bytes
    body.extend(_pack_matrix_row_major(cov_inv))                 # F x F x 8 bytes
    body.extend(struct.pack(">Q", int(ts_ns)))                   # 8 bytes

    return hashlib.sha256(bytes(body)).digest()


def expected_body_length(feature_dim: int, n_players: int) -> int:
    """Return the canonical body length for a given (F, N) — for tests + validation."""
    return (
        len(_SNAPSHOT_TAG)              # 26
        + 1                              # feature_dim
        + 1                              # n_players
        + n_players                      # sorted_player_ids
        + n_players * feature_dim * 8    # centroids
        + feature_dim * feature_dim * 8  # cov_inv
        + 8                              # ts_ns
    )

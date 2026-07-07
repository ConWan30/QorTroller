"""Reflex-band commitment adapter (D-CERT-8) — a THIN F=1 / N=1 reuse of the FROZEN
BIOMETRIC-SNAPSHOT-v1 commitment family for the developer-self reflex band.

This is NOT a new commitment family and mints NO new domain tag. The single-subject
reflex model produced by ``l9_presence.poep_calibration.single_subject_reflex_model``
is genuinely a 1-feature (reaction latency ms) / 1-subject centroid + inverse-covariance
biometric fingerprint:

    band = mu +/- 2.5*sigma        (poep_calibration.py: band_lo/hi are mu +/- 2.5 sd)

so the band commits, in-spec, as::

    compute_biometric_commitment(
        feature_dim         = 1,
        sorted_player_ids   = [0],                    # canonical single subject
        centroids_by_player = {0: [latency_mean_ms]}, # centroid = mean reaction latency
        cov_inv             = [[1.0 / sigma**2]],     # 1x1 inverse covariance
        ts_ns               = salt,                   # per-enrollment hiding salt (see below)
    )

``compute_biometric_commitment`` is the SHARED canonicalization entry point (the same one
the AIT snapshot path uses at operator_api/agent_grind.py). Mint (enrollment) and
audit-recompute both call ``reflex_band_commitment`` here, so they are bit-identical BY
CONSTRUCTION — there is no parallel encoder that could drift on a float-representation edge.
The family's ``_FROZEN_SCALE = 1e9`` fixed-point scaling amply represents both ``mu`` (~200)
and ``1/sigma**2`` (~1e-3) without overflow or underflow.

HIDING (why ``ts_ns`` carries a salt, not a timestamp): a reflex band is low-entropy
(~2 floats over a narrow physiological range), so a commitment without a strong salt would
not HIDE the band — an adversary with the public commitment could brute-force (mu, sigma).
Per VAPI_BIOMETRIC_PRIVACY.md ("only derived thresholds and commitments survive, never raw")
the commitment must actually hide. The family's ``ts_ns`` uint64 slot is packed raw (unscaled),
so a per-enrollment ``secrets.randbits(64)`` salt rides it cleanly — pure family reuse, no extra
parameter, no local encoder. The raw ``(mu, sigma, salt)`` stays operator-held (the enrollment
disclosure record) and is disclosed on audit; it is NEVER emitted on the proof / API / JSONL.
"""
from __future__ import annotations

from .biometric_snapshot import compute_biometric_commitment

# Canonical single-subject player id for the N=1 reflex band. The human-readable player
# label (e.g. "DEV") travels separately as the raw `calibration_player_scope` field.
_SINGLE_SUBJECT_ID = 0

_U64_MAX = 0xFFFFFFFFFFFFFFFF


def reflex_band_commitment(latency_mean_ms: float, latency_std_ms: float, salt: int) -> str:
    """Return the 32-byte BIOMETRIC-SNAPSHOT-v1 commitment (hex) over the reflex band's
    centroid + inverse variance, hidden by a per-enrollment ``salt`` (uint64, operator-held).

    Raises:
        ValueError on a degenerate band (std <= 0 -> undefined inverse variance) or a
        salt outside the uint64 range.
    """
    sd = float(latency_std_ms)
    if sd <= 0.0:
        raise ValueError(f"degenerate reflex band: std must be > 0, got {sd}")
    salt_i = int(salt)
    if not (0 <= salt_i <= _U64_MAX):
        raise ValueError(f"salt out of uint64 range: {salt}")
    cov_inv = [[1.0 / (sd * sd)]]
    digest = compute_biometric_commitment(
        feature_dim=1,
        sorted_player_ids=[_SINGLE_SUBJECT_ID],
        centroids_by_player={_SINGLE_SUBJECT_ID: [float(latency_mean_ms)]},
        cov_inv=cov_inv,
        ts_ns=salt_i,
    )
    return digest.hex()


def verify_reflex_band_commitment(
    latency_mean_ms: float,
    latency_std_ms: float,
    salt: int,
    expected_hex: str,
) -> bool:
    """Recompute-on-audit: True iff the disclosed ``(mu, sigma, salt)`` reproduces
    ``expected_hex``. Uses the SAME function as the mint path, so a match is bit-exact and a
    mismatch means the commitment does not correspond to the disclosed band. Fail-closed:
    any malformed input returns False (never raises during an audit)."""
    try:
        return reflex_band_commitment(latency_mean_ms, latency_std_ms, salt) == str(expected_hex).lower()
    except (ValueError, TypeError):
        return False

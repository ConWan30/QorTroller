"""Phase B item ③ — VHP Renewal Cadence (iPACT-DePIN). FROZEN FORMULA v1 (RESERVED).

Reference implementation of ``wiki/methodology/ipact_renewal_cadence_v1_scope.md``
(DRAFT scope, operator-approved 2026-05-23). The renewal-cadence commitment primitive:
a chained SHA-256 commitment per VHP renewal, binding a fresh device re-attestation
proof — QorTroller's iPACT-DePIN instance (IIP-64 §4.8.5).

FROZEN FORMULA v1 (byte order — RESERVED, not yet frozen via PV-CI ceremony):

    commitment = SHA-256(
        b"QORTROLLER-IPACT-RENEWAL-v1"   (27-byte domain tag)
        || device_id_32B                 (32 bytes = device_id_to_bytes32(device_id))
        || uint64_be(token_id)           (8 bytes)
        || prev_commitment               (32 bytes — SHA-256 output, or genesis)
        || uint64_be(epoch_index)        (8 bytes; 0 at issuance, +1 per renewal)
        || reattest_proof                (32 bytes — SHA-256-class digest, or NO_REATTEST_PROOF)
        || uint64_be(ts_ns)              (8 bytes, big-endian, nanoseconds since Unix epoch)
    )                                     = 147 bytes input → 32 bytes output

Genesis (first renewal's prev_commitment):

    SHA-256(b"QORTROLLER-IPACT-RENEWAL-GENESIS-v1" || device_id_32B || uint64_be(token_id))

The genesis is deterministic given (device_id, token_id) — a chain anchor, not a secret.
Any party can re-derive device_id_32B = device_id_to_bytes32(device_id) and the chain root.

re-attestation proof (when enforcement ON — default validator (B) composite-sig over a
bridge-issued fresh challenge):

    reattest_proof = SHA-256(
        uint8(len(nonce)) || nonce                  (challenge_bytes; nonce = 32 CSPRNG bytes)
        || uint32_be(len(composite_sig)) || composite_sig   (① composite_sig.sign(...) blob)
    )

When enforcement is OFF (default), the commitment chain still forms with
reattest_proof = NO_REATTEST_PROOF (32 zero bytes) — a sentinel meaning "no re-attestation
required this epoch." This lets the chain accumulate for the observation period before the
flip-on governance event closes the dormant-blind gap.

STATUS: DRAFT. Tag QORTROLLER-IPACT-RENEWAL-v1 is RESERVED (scope-doc only) — NOT in
_PATTERN_017_FROZEN_TAGS or the PV-CI allowlist; the freeze ceremony is a separate later
step. Standalone pure-Python (stdlib only; no bridge imports) — independently verifiable,
mirroring grind_chain.py / l9_presence/composite_sig.py.

Any change to byte order, domain tags, or hash algorithm requires v2 + new tags.
"""

from __future__ import annotations

import hashlib
import struct

# --- domain tags (FROZEN v1 widths asserted at import) ----------------------
_DOMAIN_TAG = b"QORTROLLER-IPACT-RENEWAL-v1"
_GENESIS_TAG = b"QORTROLLER-IPACT-RENEWAL-GENESIS-v1"
assert len(_DOMAIN_TAG) == 27, "domain tag must be 27 bytes (FROZEN v1)"
assert len(_GENESIS_TAG) == 35, "genesis tag must be 35 bytes (FROZEN v1)"

#: 32-zero-byte sentinel reattest_proof used when enforcement is OFF (no re-attestation).
NO_REATTEST_PROOF = b"\x00" * 32

#: FROZEN cadence parameter (v1) — the renewal epoch in days. Promoted from the prior
#: hardcoded `90 * 86_400` literal in vhp_renewal_agent.py (no value change). Gets its own
#: PV-CI invariant in the freeze ceremony. Single-tier in v1; per-device-tier deferred to v2.
IPACT_RENEWAL_EPOCH_DAYS = 90


def device_id_to_bytes32(device_id: str | bytes) -> bytes:
    """Normalise device_id into 32 bytes — BYTE-IDENTICAL to the CONSENT family's
    ``consent_categories.device_id_to_bytes32`` (verified 2026-05-23; a test asserts
    byte-identity across all three branches so this is the *same* construction, not a
    parallel one).

    Branches:
      (i)   32 raw bytes            → passthrough
      (ii)  64-char hex (±0x prefix) → bytes.fromhex (canonical on-chain bytes32 form)
      (iii) any other string        → SHA-256(device_id.utf-8) fallback
    """
    if isinstance(device_id, bytes):
        if len(device_id) != 32:
            raise ValueError(f"raw device_id must be 32 bytes, got {len(device_id)}")
        return device_id
    if not isinstance(device_id, str):
        raise TypeError(f"device_id must be str or bytes, got {type(device_id).__name__}")
    s = device_id.strip()
    if s.startswith("0x") or s.startswith("0X"):
        s = s[2:]
    try:
        b = bytes.fromhex(s)
        if len(b) == 32:
            return b
    except ValueError:
        pass
    # Fallback hashes the ORIGINAL device_id (not the stripped `s`) — matches CONSENT exactly.
    return hashlib.sha256(device_id.encode("utf-8")).digest()


def genesis_commitment(device_id: str | bytes, token_id: int) -> bytes:
    """Compute the deterministic genesis (prev_commitment for the first renewal).

    Returns 32 bytes. Deterministic given (device_id, token_id) — a chain anchor, not a
    secret; any party can reconstruct it.
    """
    return hashlib.sha256(
        _GENESIS_TAG
        + device_id_to_bytes32(device_id)
        + struct.pack(">Q", token_id)
    ).digest()


def compute_reattest_proof(nonce: bytes, composite_sig: bytes) -> bytes:
    """Compute the 32-byte reattest_proof from a bridge-issued nonce + ① composite-sig.

        reattest_proof = SHA-256( uint8(len(nonce)) || nonce
                                  || uint32_be(len(composite_sig)) || composite_sig )

    ``composite_sig`` is the blob from l9_presence/composite_sig.sign(...) / encode_composite(...).
    Wire-level the slot is proof-type-agnostic (any 32-byte digest); this helper is the
    default validator (B) composite-sig binding.
    """
    if len(nonce) > 255:
        raise ValueError(f"nonce must be <=255 bytes, got {len(nonce)}")
    if len(composite_sig) >= (1 << 32):
        raise ValueError("composite_sig too long for uint32 length prefix")
    challenge_bytes = bytes([len(nonce)]) + nonce
    composite_sig_bytes = struct.pack(">I", len(composite_sig)) + composite_sig
    return hashlib.sha256(challenge_bytes + composite_sig_bytes).digest()


def compute_commitment(
    device_id: str | bytes,
    token_id: int,
    prev_commitment: bytes,
    epoch_index: int,
    reattest_proof: bytes,
    ts_ns: int,
) -> bytes:
    """Compute one renewal-cadence commitment (FROZEN v1 byte order = 146B input).

    Args:
        device_id:       device id (normalised via device_id_to_bytes32).
        token_id:        VHP tokenId (uint64).
        prev_commitment: 32-byte prior commitment (or genesis_commitment(...) for the first).
        epoch_index:     renewal sequence number (uint64; 0 at issuance, +1 per renewal).
        reattest_proof:  32-byte SHA-256-class digest (or NO_REATTEST_PROOF when enforcement OFF).
        ts_ns:           Unix timestamp in nanoseconds (strictly monotonic per device).

    Returns:
        32 bytes — the renewal commitment for this epoch link.
    """
    if len(prev_commitment) != 32:
        raise ValueError(f"prev_commitment must be 32 bytes, got {len(prev_commitment)}")
    if len(reattest_proof) != 32:
        raise ValueError(f"reattest_proof must be 32 bytes, got {len(reattest_proof)}")
    return hashlib.sha256(
        _DOMAIN_TAG
        + device_id_to_bytes32(device_id)
        + struct.pack(">Q", token_id)
        + prev_commitment
        + struct.pack(">Q", epoch_index)
        + reattest_proof
        + struct.pack(">Q", ts_ns)
    ).digest()


def verify_chain(
    device_id: str | bytes,
    token_id: int,
    links: list[dict],
) -> tuple[bool, str]:
    """Recompute a renewal chain and verify integrity end to end.

    Each link dict must carry: epoch_index (int), reattest_proof (32 bytes),
    ts_ns (int), commitment (32 bytes — the stored value to check against).
    The first link's prev_commitment is the deterministic genesis; each subsequent
    link chains to the prior link's recomputed commitment.

    Returns (True, "") on a fully valid chain; (False, reason) on the first break.
    """
    prev = genesis_commitment(device_id, token_id)
    prev_epoch = -1
    prev_ts = -1
    for i, link in enumerate(links):
        epoch_index = int(link["epoch_index"])
        reattest_proof = link["reattest_proof"]
        ts_ns = int(link["ts_ns"])
        stored = link["commitment"]
        if epoch_index <= prev_epoch:
            return (False, f"link {i}: epoch_index {epoch_index} not strictly increasing")
        if ts_ns <= prev_ts:
            return (False, f"link {i}: ts_ns {ts_ns} not strictly increasing")
        recomputed = compute_commitment(
            device_id, token_id, prev, epoch_index, reattest_proof, ts_ns
        )
        if recomputed != stored:
            return (False, f"link {i}: commitment mismatch (chain tamper)")
        prev = recomputed
        prev_epoch = epoch_index
        prev_ts = ts_ns
    return (True, "")

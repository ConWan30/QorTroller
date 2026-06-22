"""VSD Self-Verifying Loop — Synthesis Integrity Chain (SIC). FROZEN FORMULA v1.

The synthesis-domain twin of GIC/WEC: a tamper-evident hash chain over methodology-loop
cycles. Each cycle commits its signed PBSA + the deterministic checker results, so the dev
loop produces the same kind of verifiable provenance the protocol produces for gameplay.

SIC_N = SHA-256(
    prev_sic_32b            (32 bytes)
    || pbsa_manifest_32b    (32 bytes — bytes.fromhex(pbsa_manifest_hash_hex))
    || harness_byte         (1 byte — 0x01 pass / 0x00 fail)
    || pv_ci_byte           (1 byte — 0x01 pass / 0x00 fail)
    || mythos_drift_byte    (1 byte — min(drift_count, 255))
    || ts_ns_be             (8 bytes, big-endian uint64)
)                           = 75 bytes input -> 32 bytes output

Genesis (first cycle of a loop run):
    SHA-256(b"VAPI-SIC-GENESIS-v1" || vault_id.encode() || struct.pack(">Q", ts_ns))

Any change to byte order or hash algorithm requires SIC v2 and a new genesis tag.
Pure stdlib; standalone (no bridge/vault imports) so it can be independently verified.
"""
import hashlib
import struct

_GENESIS_TAG = b"VAPI-SIC-GENESIS-v1"


def genesis_sic(vault_id: str, ts_ns: int) -> bytes:
    """Genesis SIC for a new loop run (used as prev_sic for the first cycle link)."""
    return hashlib.sha256(
        _GENESIS_TAG + vault_id.encode() + struct.pack(">Q", ts_ns)
    ).digest()


def compute_sic(
    prev_sic: bytes,
    pbsa_manifest_hash_hex: str,
    harness_pass: bool,
    pv_ci_pass: bool,
    mythos_drift_count: int,
    ts_ns: int,
) -> bytes:
    """Compute the SIC hash for one methodology-loop cycle.

    FROZEN byte order v1: prev(32) || pbsa(32) || harness(1) || pv_ci(1) || drift(1) || ts(8).
    pbsa_manifest_hash_hex is the SHA-256 (64 hex) of the cycle's signed PBSA manifest;
    "" -> 32 zero bytes (allowed for a cycle with no PBSA, e.g. a no-op verify cycle).
    """
    pbsa_bytes = bytes.fromhex(pbsa_manifest_hash_hex) if pbsa_manifest_hash_hex else b"\x00" * 32
    if len(pbsa_bytes) != 32:
        raise ValueError("pbsa_manifest_hash_hex must be 64 hex chars (32 bytes) or empty")
    return hashlib.sha256(
        prev_sic
        + pbsa_bytes
        + (b"\x01" if harness_pass else b"\x00")
        + (b"\x01" if pv_ci_pass else b"\x00")
        + min(max(int(mythos_drift_count), 0), 255).to_bytes(1, "big")
        + struct.pack(">Q", ts_ns)
    ).digest()


def verify_chain(vault_id: str, genesis_ts_ns: int, links: list[dict]) -> bool:
    """Recompute the chain from genesis over an ordered list of cycle dicts and confirm
    each stored sic_hex matches. A single mismatch -> False (tamper-evident).

    Each link dict: {pbsa_manifest_hash, harness_pass, pv_ci_pass, mythos_drift, ts_ns, sic_hex}.
    """
    prev = genesis_sic(vault_id, genesis_ts_ns)
    for link in links:
        expected = compute_sic(
            prev,
            link.get("pbsa_manifest_hash", "") or "",
            bool(link.get("harness_pass")),
            bool(link.get("pv_ci_pass")),
            int(link.get("mythos_drift", 0)),
            int(link["ts_ns"]),
        )
        if expected.hex() != link.get("sic_hex"):
            return False
        prev = expected
    return True

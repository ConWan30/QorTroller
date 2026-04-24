"""Phase 235-A — Grind Integrity Chain (GIC). FROZEN FORMULA v1.

GIC_N = SHA-256(
    prev_gic_32b          (32 bytes)
    || commitment_hash_32b (32 bytes — bytes.fromhex(commitment_hash_hex))
    || verdict_code        (1 byte, big-endian)
    || host_state_code     (1 byte, big-endian)
    || ts_ns_be            (8 bytes, big-endian uint64)
)                          = 74 bytes total input → 32 bytes output

Genesis (first session in a grind run):
    SHA-256(b"VAPI-GIC-GENESIS-v1" || grind_session_id.encode() || struct.pack(">Q", ts_ns))

Any future change to byte order, code table, or hash algorithm requires GIC v2
and a new genesis tag. v1 is permanently frozen.
"""
import hashlib
import struct

VERDICT_CODES: dict[str, int] = {
    "CLEAR":   0x00,
    "CERTIFY": 0x01,
    "FLAG":    0x10,
    "HOLD":    0x11,
    "BLOCK":   0x20,
}

PCC_HOST_CODES: dict[str, int] = {
    "EXCLUSIVE_USB": 0x01,
    "UNKNOWN":       0x02,
    "EXCLUSIVE_BT":  0x10,
    "CONTESTED":     0x20,
    "DEGRADED":      0x30,
    "DISCONNECTED":  0xFF,
}

_GENESIS_TAG = b"VAPI-GIC-GENESIS-v1"


def genesis_gic(grind_session_id: str, ts_ns: int) -> bytes:
    """Compute the genesis (first) GIC hash for a new grind session run.

    Args:
        grind_session_id: Stable identifier for this grind run (e.g. "grind_20260422").
        ts_ns: Unix timestamp in nanoseconds at genesis time.

    Returns:
        32 bytes — the genesis GIC hash (used as prev_gic for the first real session).
    """
    return hashlib.sha256(
        _GENESIS_TAG
        + grind_session_id.encode()
        + struct.pack(">Q", ts_ns)
    ).digest()


def compute_gic(
    prev_gic: bytes,
    commitment_hash_hex: str,
    pcc_host_state: str,
    fallback_verdict: str,
    ts_ns: int,
) -> bytes:
    """Compute the GIC hash for one count-eligible grind session.

    FROZEN byte order v1: prev(32) || ch(32) || verdict(1) || host(1) || ts(8) = 74B

    Args:
        prev_gic:            32-byte GIC output from previous session (or genesis).
        commitment_hash_hex: Hex commitment_hash from agent_rulings (32 bytes → 64 hex chars).
        pcc_host_state:      Host state string (EXCLUSIVE_USB, UNKNOWN, …).
        fallback_verdict:    Deterministic _rule_fallback() output (CLEAR/CERTIFY/FLAG/HOLD/BLOCK).
        ts_ns:               Unix timestamp in nanoseconds for this session.

    Returns:
        32 bytes — the GIC hash for this session link.
    """
    verdict_byte = VERDICT_CODES.get(fallback_verdict, VERDICT_CODES["FLAG"]).to_bytes(1, "big")
    host_byte = PCC_HOST_CODES.get(pcc_host_state, PCC_HOST_CODES["DISCONNECTED"]).to_bytes(1, "big")
    return hashlib.sha256(
        prev_gic
        + bytes.fromhex(commitment_hash_hex)
        + verdict_byte
        + host_byte
        + struct.pack(">Q", ts_ns)
    ).digest()

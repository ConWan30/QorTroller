"""Phase 236-WATCHDOG — Watchdog Event Chain (WEC). FROZEN FORMULA v1.

WEC pairs with the GIC chain. GIC documents cognitive-session continuity
(was-this-session-clean), WEC documents operational continuity (was-the-bridge-up
to produce that session). Together they give a complete provenance for a grind run.

WEC_N = SHA-256(
    prev_wec_32b              (32 bytes)
    || event_code             (1 byte, big-endian)
    || pid_be                 (4 bytes, big-endian uint32)
    || grind_session_id_hash  (16 bytes — SHA-256(grind_session_id)[:16])
    || ts_ns_be               (8 bytes, big-endian uint64)
)                              = 61 bytes total input → 32 bytes output

Genesis (first event in a grind run):
    SHA-256(b"VAPI-WEC-GENESIS-v1" || grind_session_id.encode() || struct.pack(">Q", ts_ns))

Any future change to byte order, event-code table, or hash algorithm requires
WEC v2 and a new genesis tag. v1 is permanently frozen.
"""
import hashlib
import struct

EVENT_CODES: dict[str, int] = {
    "BRIDGE_START":                  0x01,
    "BRIDGE_HEALTHY":                0x02,
    "BRIDGE_UNRESPONSIVE":           0x03,
    "BRIDGE_RESTART_TRIGGERED":      0x04,
    "BRIDGE_RESTART_REFUSED_GIC":    0x05,
    "BRIDGE_RESTART_REFUSED_SID":    0x06,
    "BRIDGE_DEGRADED_HOST_STATE":    0x07,
    "WATCHDOG_BACKOFF_CEILING":      0xFE,
    "WATCHDOG_HALT":                 0xFF,
}

EVENT_NAMES: dict[int, str] = {v: k for k, v in EVENT_CODES.items()}

_GENESIS_TAG = b"VAPI-WEC-GENESIS-v1"


def grind_session_id_hash(grind_session_id: str) -> bytes:
    """SHA-256(grind_session_id)[:16] — 16-byte session-binding tag.

    The full 32-byte hash would dominate the input; 16 bytes is enough to make
    cross-session WEC collision negligible (2^-128) without inflating the chain.
    """
    return hashlib.sha256(grind_session_id.encode()).digest()[:16]


def genesis_wec(grind_session_id: str, ts_ns: int) -> bytes:
    """Compute the genesis (first) WEC hash for a new watchdog lifetime under grind_session_id.

    Args:
        grind_session_id: Stable identifier matching the active grind run.
        ts_ns: Unix timestamp in nanoseconds at watchdog start.

    Returns:
        32 bytes — used as prev_wec for the first real BRIDGE_START event.
    """
    return hashlib.sha256(
        _GENESIS_TAG
        + grind_session_id.encode()
        + struct.pack(">Q", ts_ns)
    ).digest()


def compute_wec(
    prev_wec: bytes,
    event_code: int,
    pid: int,
    grind_session_id: str,
    ts_ns: int,
) -> bytes:
    """Compute the WEC hash for one watchdog event.

    FROZEN byte order v1: prev(32) || code(1) || pid(4) || sid_hash(16) || ts(8) = 61B

    Args:
        prev_wec:         32-byte WEC output from previous event (or genesis).
        event_code:       One of EVENT_CODES values (0x01..0xFF).
        pid:              Bridge process ID (uint32; 0 if unknown).
        grind_session_id: Active grind session ID (used for sid_hash).
        ts_ns:            Unix timestamp in nanoseconds for this event.

    Returns:
        32 bytes — the WEC hash for this event link.
    """
    if not (0 <= event_code <= 0xFF):
        raise ValueError(f"event_code out of range: {event_code}")
    if not (0 <= pid <= 0xFFFFFFFF):
        raise ValueError(f"pid out of range: {pid}")
    return hashlib.sha256(
        prev_wec
        + event_code.to_bytes(1, "big")
        + struct.pack(">I", pid)
        + grind_session_id_hash(grind_session_id)
        + struct.pack(">Q", ts_ns)
    ).digest()

"""Phase 236-VAME — VAPI Application-Layer Message Envelope. FROZEN FORMULA v1.

Sidecar response-header authentication that binds every authenticated bridge
response to the GIC chain head. Sits ABOVE TLS — provides application-layer
integrity that survives proxy/MITM scenarios where TLS is decrypted at a
mid-box (corporate proxies, observability loops, etc.).

Design choice — sidecar headers, NOT body wrapper:
  Wrapping the body in {"data": ..., "_vame": ...} would break every existing
  reader. Instead we expose VAME via response HEADERS so the JSON body shape
  is unchanged. Frontend reads the headers, recomputes the commitment from
  (chain_head, ts_ns, endpoint, body_bytes), validates locally.

Hash function — SHA-256 in v1, Poseidon deferred:
  Adding a Poseidon dependency to bridge runtime for one feature is heavy.
  v1 uses SHA-256 (consistent with GIC, WEC, and PoAC chain-link hashing).
  v2 will move to Poseidon when Phase 237-ZK-SEPPROOF lands and circomlib
  is already a hard dep — at that point the unified Poseidon binding becomes
  a one-line swap. The novelty is the GIC-chain-head binding, not the hash.

VAME_v1 commitment formula:
    commitment = SHA-256(
        b"VAPI-VAME-v1"           (12 bytes)  — domain separation
        || chain_head_16b         (16 bytes)  — first 16 bytes of latest GIC hash,
                                                 or 16 zero bytes if no chain
        || ts_ns_be(8)            (8 bytes)   — nanosecond stamp on this response
        || endpoint_bytes         (variable)  — utf-8 endpoint path
        || body_bytes             (variable)  — exact JSON body bytes (canonical)
    )                              → 32 bytes → 64-hex commitment

Response headers (one set per stamped response):
    X-VAME-Version:    "vame/1.0"
    X-VAME-Commitment: <64-hex sha256 commitment>
    X-VAME-Chain-Head: <32-hex>  (first 16 bytes of latest_gic_hash)
    X-VAME-TS-NS:      <int>
    X-VAME-Endpoint:   <path>

Frontend validation:
    1. Recompute commitment locally from response body bytes.
    2. Compare to X-VAME-Commitment.
    3. Mismatch → flag as VAME_INTEGRITY_FAILURE.

Any future change to the formula requires VAME v2 + new domain tag.
v1 is permanently frozen.
"""
from __future__ import annotations

import hashlib
import struct
import time

VAME_VERSION_STR = "vame/1.0"
_VAME_TAG = b"VAPI-VAME-v1"
_CHAIN_HEAD_BYTES = 16  # first 16 bytes of the GIC hash bound into the commitment


def chain_head_from_hex(latest_gic_hash_hex: str | None) -> bytes:
    """Extract the 16-byte chain-head prefix from a GIC hash hex string.

    Returns 16 zero bytes when the chain is empty or hash is unparsable —
    this is the "no chain" anchor (still a valid VAME stamp; just not bound
    to any specific session).
    """
    if not latest_gic_hash_hex:
        return b"\x00" * _CHAIN_HEAD_BYTES
    try:
        head = bytes.fromhex(latest_gic_hash_hex)[:_CHAIN_HEAD_BYTES]
        if len(head) < _CHAIN_HEAD_BYTES:
            head = head + b"\x00" * (_CHAIN_HEAD_BYTES - len(head))
        return head
    except (ValueError, TypeError):
        return b"\x00" * _CHAIN_HEAD_BYTES


def compute_vame_commitment(
    chain_head: bytes,
    ts_ns: int,
    endpoint: str,
    body_bytes: bytes,
) -> str:
    """Compute the VAME v1 commitment hex for a response.

    Args:
        chain_head:  16 bytes from chain_head_from_hex().
        ts_ns:       Unix timestamp in nanoseconds for this response.
        endpoint:    Endpoint path (e.g. "/operator/bridge/grind-chain-status").
        body_bytes:  Exact response body bytes (the raw JSON payload).

    Returns:
        64-character lowercase hex string (32-byte SHA-256 digest).
    """
    if len(chain_head) != _CHAIN_HEAD_BYTES:
        raise ValueError(
            f"chain_head must be {_CHAIN_HEAD_BYTES} bytes, got {len(chain_head)}"
        )
    if not (0 <= int(ts_ns) <= 0xFFFFFFFFFFFFFFFF):
        raise ValueError(f"ts_ns out of uint64 range: {ts_ns}")
    return hashlib.sha256(
        _VAME_TAG
        + chain_head
        + struct.pack(">Q", int(ts_ns))
        + endpoint.encode("utf-8")
        + body_bytes
    ).hexdigest()


def stamp_response_headers(
    chain_head_hex: str | None,
    endpoint: str,
    body_bytes: bytes,
    ts_ns: int | None = None,
) -> dict[str, str]:
    """Compute the full set of VAME response headers for a stamped response.

    Returns a dict suitable for spreading into Starlette's `headers` argument
    or assigning via Response.headers.update().
    """
    if ts_ns is None:
        ts_ns = time.time_ns()
    head = chain_head_from_hex(chain_head_hex)
    commitment = compute_vame_commitment(head, ts_ns, endpoint, body_bytes)
    return {
        "X-VAME-Version":    VAME_VERSION_STR,
        "X-VAME-Commitment": commitment,
        "X-VAME-Chain-Head": head.hex(),
        "X-VAME-TS-NS":      str(int(ts_ns)),
        "X-VAME-Endpoint":   endpoint,
    }

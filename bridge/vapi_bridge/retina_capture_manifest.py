"""Retina Witness Mark — capture manifest (RWM L0, Component 1). CANDIDATE, not FROZEN-v1.

Hash-chained record of frames archived during a single retina-capture session,
following the WEC/GIC PATTERN-017 discipline (prev-hash chaining, tagged genesis,
fixed-width big-endian fields) with a domain-specific entry shape. See
docs/a2a/retina-witness-mark/l0-implementation-plan.md for the full design and the
F-RWM-5/6/7 dispositions this module implements.

Cadence resolved against the daemon's existing precedent (scripts/retina_capture_daemon.py
::_archive_ring's manifest.json, the U1 tier-1 standing manifest): that manifest is built
ONCE per session, at stop time, over all files archived during the session -- never on a
periodic in-session interval. The RWM manifest follows the same cadence: build_session_chain
runs once per session at stop time, not incrementally during play. This resolves the L0
plan's open checkpoint-cadence question (previously "not yet confirmed, needs a real read");
the read is done, this is the answer.

Genesis:
    SHA-256(DOMAIN_TAG_GENESIS || session_id.encode() || device_id(32) || ts_ns_be(8))

Entry:
    SHA-256(prev_hash(32) || frame_hash(32) || frame_index_be(4) || ts_ns_be(8)) = 76B -> 32B

Discipline match vs. WEC/GIC (bridge/vapi_bridge/watchdog_chain.py, grind_chain.py):
prev-hash chaining, tagged genesis, fixed-width big-endian fields, no per-entry domain
tag -- matches exactly. Field layout does not match either byte-for-byte (by design; each
PATTERN-017 family's fields are domain-specific). device_id(32) in genesis is a stated
divergence: unlike a grind/watchdog session (implicitly single-device), a footage manifest
is meant to be checked by third parties matching footage to a specific certified device.

CANDIDATE per D-RWM-1 Path A -- not FROZEN-v1, no governance ceremony, no PV-CI pin.
"""
from __future__ import annotations

import hashlib
import struct

DOMAIN_TAG_GENESIS = b"VAPI-RWM-MANIFEST-GENESIS-v1"


def genesis_manifest_hash(session_id: str, device_id_hex: str, ts_ns: int) -> bytes:
    """SHA-256(DOMAIN_TAG_GENESIS || session_id.encode() || device_id(32) || ts_ns_be(8)).

    session_id raw (not pre-hashed) -- matches WEC/GIC's genesis convention exactly.
    device_id_hex must decode to exactly 32 bytes (the certified device's SHA-256
    device_id, hex-encoded, e.g. the registered Edge's 581a836c...9f8 identifier).

    Args:
        session_id: Stable identifier for the capture session (matches the KAS/PoSP
            session_id join key per l9_presence/session_identity.py).
        device_id_hex: 64-char hex string decoding to the 32-byte device_id.
        ts_ns: Unix timestamp in nanoseconds at manifest-genesis time.

    Returns:
        32 bytes -- used as prev_hash for the session's first frame entry.
    """
    device_id = bytes.fromhex(device_id_hex)
    if len(device_id) != 32:
        raise ValueError(f"device_id_hex must decode to 32 bytes, got {len(device_id)}")
    return hashlib.sha256(
        DOMAIN_TAG_GENESIS
        + session_id.encode()
        + device_id
        + struct.pack(">Q", ts_ns)
    ).digest()


def compute_manifest_entry(prev_hash: bytes, frame_hash: bytes, frame_index: int, ts_ns: int) -> bytes:
    """SHA-256(prev_hash(32) || frame_hash(32) || frame_index_be(4) || ts_ns_be(8)) = 76B.

    frame_hash MUST be computed over the exact bytes written to disk, locator mark
    already composited in (F-RWM-5: composite -> hash -> append -> write). Hashing
    pre-composite bytes means no verifier can ever recompute a matching hash from the
    archived file, since the archived file itself has the mark burned in.

    Args:
        prev_hash: 32-byte chain hash from the previous entry (or genesis).
        frame_hash: 32-byte SHA-256 of the composited frame's raw pixel bytes.
        frame_index: 0-based index of this frame within the session (uint32).
        ts_ns: Unix timestamp in nanoseconds when this frame was archived.

    Returns:
        32 bytes -- the chain hash for this entry.
    """
    if len(prev_hash) != 32:
        raise ValueError(f"prev_hash must be 32 bytes, got {len(prev_hash)}")
    if len(frame_hash) != 32:
        raise ValueError(f"frame_hash must be 32 bytes, got {len(frame_hash)}")
    if not (0 <= frame_index <= 0xFFFFFFFF):
        raise ValueError(f"frame_index out of range: {frame_index}")
    return hashlib.sha256(
        prev_hash
        + frame_hash
        + struct.pack(">I", frame_index)
        + struct.pack(">Q", ts_ns)
    ).digest()


def build_session_chain(
    session_id: str,
    device_id_hex: str,
    genesis_ts_ns: int,
    frames: list[tuple[bytes, int]],
) -> list[bytes]:
    """Build the full hash chain for one session in a single pass, at session-stop.

    Matches the cadence of the existing per-session manifest.json (scripts/
    retina_capture_daemon.py::_archive_ring) -- built once over all frames archived
    during the session, not incrementally during play.

    Args:
        session_id: Stable session identifier (see genesis_manifest_hash).
        device_id_hex: 64-char hex device_id (see genesis_manifest_hash).
        genesis_ts_ns: Timestamp for the genesis entry.
        frames: (frame_hash, ts_ns) tuples in frame_index order (0-based, contiguous).

    Returns:
        The chain: [genesis_hash, entry_0, entry_1, ..., entry_N-1]. Length is
        len(frames) + 1.
    """
    chain = [genesis_manifest_hash(session_id, device_id_hex, genesis_ts_ns)]
    for frame_index, (frame_hash, ts_ns) in enumerate(frames):
        chain.append(compute_manifest_entry(chain[-1], frame_hash, frame_index, ts_ns))
    return chain


def verify_session_chain(
    session_id: str,
    device_id_hex: str,
    genesis_ts_ns: int,
    frames: list[tuple[bytes, int]],
    claimed_chain: list[bytes],
) -> bool:
    """Recompute the chain from scratch and compare against a claimed chain.

    Tamper-evidence: any altered frame_hash, frame_index, or ts_ns anywhere in
    `frames` produces a different hash from that point forward, breaking the
    comparison. Returns False (never raises) on any mismatch or malformed input --
    fail-closed, matching this session's established discipline.
    """
    try:
        recomputed = build_session_chain(session_id, device_id_hex, genesis_ts_ns, frames)
    # F-RWM-8 (LANE RWM r13): ValueError/TypeError alone don't cover every
    # exception build_session_chain's call graph can raise on malformed input --
    # struct.pack(">Q", ts_ns) raises struct.error for ts_ns outside [0, 2**64),
    # and session_id.encode() raises AttributeError when session_id isn't a str.
    # This function's whole purpose is letting a third party re-verify a footage
    # manifest with unvalidated input, so the fail-closed contract has to actually
    # hold here. If you add a new call inside build_session_chain/genesis_manifest_hash/
    # compute_manifest_entry that can raise a different exception type, audit
    # whether it belongs in this tuple too -- this catch is not exhaustive by
    # accident, it's enumerated from the actual call graph as of this fix.
    except (ValueError, TypeError, struct.error, AttributeError):
        return False
    return recomputed == claimed_chain

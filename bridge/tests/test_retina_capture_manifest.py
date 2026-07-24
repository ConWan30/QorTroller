"""Tests for the Retina Witness Mark capture manifest (RWM L0, Component 1).

CANDIDATE primitive per D-RWM-1 Path A -- not FROZEN-v1, no PV-CI pin. See
docs/a2a/retina-witness-mark/l0-implementation-plan.md for the design this
implements.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vapi_bridge.retina_capture_manifest import (  # noqa: E402
    DOMAIN_TAG_GENESIS,
    build_session_chain,
    compute_manifest_entry,
    genesis_manifest_hash,
    verify_session_chain,
)

SESSION_ID = "test_session_2026_07_24"
DEVICE_ID_HEX = "581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8"
GENESIS_TS = 1_700_000_000_000_000_000


def _fake_frame_hash(i: int) -> bytes:
    return hashlib.sha256(f"frame-{i}".encode()).digest()


def _fake_frames(n: int, base_ts: int = GENESIS_TS + 1) -> list[tuple[bytes, int]]:
    return [(_fake_frame_hash(i), base_ts + i) for i in range(n)]


def test_genesis_deterministic():
    a = genesis_manifest_hash(SESSION_ID, DEVICE_ID_HEX, GENESIS_TS)
    b = genesis_manifest_hash(SESSION_ID, DEVICE_ID_HEX, GENESIS_TS)
    assert a == b
    assert len(a) == 32


def test_genesis_domain_separated_by_session_id():
    a = genesis_manifest_hash(SESSION_ID, DEVICE_ID_HEX, GENESIS_TS)
    b = genesis_manifest_hash(SESSION_ID + "_other", DEVICE_ID_HEX, GENESIS_TS)
    assert a != b


def test_genesis_domain_separated_by_device_id():
    other_device = "0" * 64
    a = genesis_manifest_hash(SESSION_ID, DEVICE_ID_HEX, GENESIS_TS)
    b = genesis_manifest_hash(SESSION_ID, other_device, GENESIS_TS)
    assert a != b


def test_genesis_domain_separated_by_timestamp():
    a = genesis_manifest_hash(SESSION_ID, DEVICE_ID_HEX, GENESIS_TS)
    b = genesis_manifest_hash(SESSION_ID, DEVICE_ID_HEX, GENESIS_TS + 1)
    assert a != b


def test_genesis_rejects_malformed_device_id():
    import pytest
    with pytest.raises(ValueError):
        genesis_manifest_hash(SESSION_ID, "not-hex-and-too-short", GENESIS_TS)
    with pytest.raises(ValueError):
        genesis_manifest_hash(SESSION_ID, "ab" * 16, GENESIS_TS)  # 16 bytes, not 32


def test_entry_rejects_bad_prev_hash_length():
    import pytest
    with pytest.raises(ValueError):
        compute_manifest_entry(b"short", _fake_frame_hash(0), 0, GENESIS_TS)


def test_entry_rejects_bad_frame_hash_length():
    import pytest
    genesis = genesis_manifest_hash(SESSION_ID, DEVICE_ID_HEX, GENESIS_TS)
    with pytest.raises(ValueError):
        compute_manifest_entry(genesis, b"short", 0, GENESIS_TS)


def test_entry_rejects_out_of_range_frame_index():
    import pytest
    genesis = genesis_manifest_hash(SESSION_ID, DEVICE_ID_HEX, GENESIS_TS)
    with pytest.raises(ValueError):
        compute_manifest_entry(genesis, _fake_frame_hash(0), -1, GENESIS_TS)
    with pytest.raises(ValueError):
        compute_manifest_entry(genesis, _fake_frame_hash(0), 0x100000000, GENESIS_TS)


def test_chain_builds_correct_length():
    frames = _fake_frames(10)
    chain = build_session_chain(SESSION_ID, DEVICE_ID_HEX, GENESIS_TS, frames)
    assert len(chain) == len(frames) + 1  # genesis + one entry per frame
    assert all(len(h) == 32 for h in chain)


def test_chain_empty_frames_is_just_genesis():
    chain = build_session_chain(SESSION_ID, DEVICE_ID_HEX, GENESIS_TS, [])
    assert len(chain) == 1
    assert chain[0] == genesis_manifest_hash(SESSION_ID, DEVICE_ID_HEX, GENESIS_TS)


def test_chain_deterministic():
    frames = _fake_frames(7)
    a = build_session_chain(SESSION_ID, DEVICE_ID_HEX, GENESIS_TS, frames)
    b = build_session_chain(SESSION_ID, DEVICE_ID_HEX, GENESIS_TS, frames)
    assert a == b


def test_verify_genuine_chain_passes():
    frames = _fake_frames(8)
    chain = build_session_chain(SESSION_ID, DEVICE_ID_HEX, GENESIS_TS, frames)
    assert verify_session_chain(SESSION_ID, DEVICE_ID_HEX, GENESIS_TS, frames, chain) is True


def test_verify_tamper_in_middle_breaks_chain_from_that_point_forward():
    """Chain-continuity: mirrors WEC/GIC's existing test pattern (test_wec_tamper_detected)."""
    frames = _fake_frames(10)
    chain = build_session_chain(SESSION_ID, DEVICE_ID_HEX, GENESIS_TS, frames)
    tampered = list(chain)
    tampered[5] = b"\x00" * 32  # alter one mid-chain hash
    assert verify_session_chain(SESSION_ID, DEVICE_ID_HEX, GENESIS_TS, frames, tampered) is False


def test_verify_tampered_frame_data_breaks_recomputation():
    """Altering the underlying frame data (not the stored chain) also fails verification --
    the claimed chain no longer matches what build_session_chain recomputes from the frames."""
    frames = _fake_frames(6)
    chain = build_session_chain(SESSION_ID, DEVICE_ID_HEX, GENESIS_TS, frames)
    tampered_frames = list(frames)
    tampered_frames[2] = (_fake_frame_hash(999), tampered_frames[2][1])  # swap in a different frame_hash
    assert verify_session_chain(SESSION_ID, DEVICE_ID_HEX, GENESIS_TS, tampered_frames, chain) is False


def test_verify_never_raises_on_malformed_input():
    """Fail-closed: malformed input returns False, never propagates an exception."""
    assert verify_session_chain(SESSION_ID, "not-hex", GENESIS_TS, [], [b"\x00" * 32]) is False


def test_domain_tag_distinct_from_sibling_pattern_017_families():
    """Domain separation from VAPI-RETINA-STATE-v1/v2/v3 / VAPI-VAME-v1 / WEC / GIC --
    per the L0 plan's test-plan item 1."""
    sibling_tags = {
        b"VAPI-RETINA-STATE-v1", b"VAPI-RETINA-STATE-v2", b"VAPI-RETINA-STATE-v3",
        b"VAPI-VAME-v1",
        b"VAPI-WEC-GENESIS-v1",
        b"VAPI-GIC-GENESIS-v1",
    }
    assert DOMAIN_TAG_GENESIS not in sibling_tags
    assert DOMAIN_TAG_GENESIS == b"VAPI-RWM-MANIFEST-GENESIS-v1"

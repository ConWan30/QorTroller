"""Tests for the Retina Witness Mark locator mark (RWM L0, Component 2).

CANDIDATE primitive per D-RWM-1 Path A -- not FROZEN-v1, no PV-CI pin. See
docs/a2a/retina-witness-mark/l0-implementation-plan.md for the design this
implements, including the F-RWM-3/5/6 dispositions.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vapi_bridge.retina_witness_mark import (  # noqa: E402
    DEFAULT_PALETTE,
    DOMAIN_TAG,
    PREAMBLE_COLORS,
    compute_locator_payload,
    composite_mark_onto_frame,
    decode_mark_from_frames,
    encode_mark_symbols,
)

SESSION_HASH_8B = bytes.fromhex("a1b2c3d4e5f60718")
FRAME_SHAPE = (64, 64, 3)


def _blank_frame() -> np.ndarray:
    return np.zeros(FRAME_SHAPE, dtype=np.uint8)


def _mark_all_frames(symbols: list[tuple[int, int, int]]) -> list[np.ndarray]:
    base = _blank_frame()
    return [composite_mark_onto_frame(base, sym) for sym in symbols]


def test_compute_locator_payload_deterministic():
    a = compute_locator_payload(SESSION_HASH_8B, 3)
    b = compute_locator_payload(SESSION_HASH_8B, 3)
    assert a == b
    assert len(a) == 12


def test_compute_locator_payload_domain_separated_by_checkpoint():
    a = compute_locator_payload(SESSION_HASH_8B, 3)
    b = compute_locator_payload(SESSION_HASH_8B, 4)
    assert a != b


def test_compute_locator_payload_rejects_bad_session_hash_length():
    with pytest.raises(ValueError):
        compute_locator_payload(b"seven77", 0)  # 7 bytes, not 8


def test_compute_locator_payload_rejects_out_of_range_checkpoint():
    with pytest.raises(ValueError):
        compute_locator_payload(SESSION_HASH_8B, -1)
    with pytest.raises(ValueError):
        compute_locator_payload(SESSION_HASH_8B, 0x1000000)


def test_preamble_and_palette_disjoint():
    """PREAMBLE_COLORS ∩ DEFAULT_PALETTE == ∅ -- asserted directly per LANE RWM r06's
    test-plan addition, not just relied upon implicitly."""
    assert not (set(PREAMBLE_COLORS) & set(DEFAULT_PALETTE))
    assert len(PREAMBLE_COLORS) == 2
    assert len(DEFAULT_PALETTE) == 4


def test_encode_symbol_count():
    payload = compute_locator_payload(SESSION_HASH_8B, 1)
    symbols = encode_mark_symbols(payload)
    # 2 preamble + (12 bytes * 4 symbols/byte * 3 repeats) = 2 + 144 = 146
    assert len(symbols) == 146


def test_encode_decode_roundtrip():
    payload = compute_locator_payload(SESSION_HASH_8B, 42)
    symbols = encode_mark_symbols(payload)
    frames = _mark_all_frames(symbols)
    decoded = decode_mark_from_frames(frames)
    assert decoded == payload


def test_decode_survives_dropped_frames_before_mark():
    """Preamble-detection under simulated dropped frames: decode must still find sync
    after removing frames from the middle of a sequence (before the mark cycle)."""
    payload = compute_locator_payload(SESSION_HASH_8B, 7)
    symbols = encode_mark_symbols(payload)
    mark_frames = _mark_all_frames(symbols)
    # simulate 20 unrelated frames before the mark, then drop half of them
    filler = [_blank_frame() for _ in range(20)]
    dropped_filler = filler[::2]
    sequence = dropped_filler + mark_frames
    decoded = decode_mark_from_frames(sequence)
    assert decoded == payload


def test_decode_majority_vote_corrects_single_symbol_corruption():
    """Simulated single-symbol corruption: one of each symbol's 3 repeated frames is
    replaced with a DIFFERENT payload color (never a preamble color -- that's the
    separate rejection path tested below); majority-vote (2-of-3) must still recover
    the payload despite one wrong vote per group."""
    payload = compute_locator_payload(SESSION_HASH_8B, 9)
    symbols = encode_mark_symbols(payload)
    frames = _mark_all_frames(symbols)
    # corrupt the FIRST repetition of every payload symbol group (indices 2, 5, 8, ...)
    # with the NEXT color in the payload palette (guaranteed different from the correct
    # one, and guaranteed to classify as a payload color, not a preamble color).
    for i in range(2, len(frames), 3):
        correct_color = symbols[i]
        wrong_color = DEFAULT_PALETTE[(DEFAULT_PALETTE.index(correct_color) + 1) % 4]
        frames[i] = composite_mark_onto_frame(_blank_frame(), wrong_color)
    decoded = decode_mark_from_frames(frames)
    assert decoded == payload


def test_decode_returns_none_on_crc_mismatch():
    """CRC catching a corrupted decode: flip a payload bit so the body no longer matches
    its own CRC-8 -- decode must return None, never a wrong-but-plausible payload."""
    payload = compute_locator_payload(SESSION_HASH_8B, 11)
    corrupted_payload = bytes([payload[0] ^ 0xFF]) + payload[1:]  # flip first byte's bits
    symbols = encode_mark_symbols(corrupted_payload)
    frames = _mark_all_frames(symbols)
    decoded = decode_mark_from_frames(frames)
    assert decoded is None


def test_decode_returns_none_when_no_preamble_found():
    frames = [_blank_frame() for _ in range(10)]  # all-black, no preamble sequence present
    assert decode_mark_from_frames(frames) is None


def test_decode_rejects_preamble_color_inside_claimed_payload_run():
    """A payload run that happens to contain a preamble-colored symbol mid-stream must not
    be accepted as a valid decode -- the decoder rejects it and keeps scanning rather than
    silently treating a preamble color as if it were payload data."""
    payload = compute_locator_payload(SESSION_HASH_8B, 13)
    symbols = encode_mark_symbols(payload)
    frames = _mark_all_frames(symbols)
    # inject a preamble color into the middle of the payload run (index 2 = first payload frame)
    frames[10] = composite_mark_onto_frame(_blank_frame(), PREAMBLE_COLORS[0])
    decoded = decode_mark_from_frames(frames)
    assert decoded is None


def test_composite_mark_onto_frame_never_mutates_input():
    original = _blank_frame()
    original_copy = original.copy()
    _ = composite_mark_onto_frame(original, (255, 0, 0))
    assert np.array_equal(original, original_copy)


def test_composite_mark_all_corners():
    frame = _blank_frame()
    for corner in ("bottom-right", "bottom-left", "top-right", "top-left"):
        marked = composite_mark_onto_frame(frame, (0, 255, 0), corner=corner)
        assert marked.shape == frame.shape


def test_domain_tag_is_the_declared_candidate_tag():
    assert DOMAIN_TAG == b"VAPI-RETINA-WITNESS-MARK-v1"


# --- F-RWM-9 (grok round-02, independently reproduced by claude-code) ---
# Oversized block_px made `h - block_px` negative, and numpy reads a negative
# slice start as "from the end" -> the whole frame got painted/sampled silently.
# Pre-fix probe: 16x16 frame + block_px=32 -> 256/256 pixels painted, no raise.


def test_composite_rejects_block_px_larger_than_frame():
    """The exact pre-fix silent-whole-frame-paint case, now fail-closed."""
    small = np.zeros((16, 16, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="does not fit in frame"):
        composite_mark_onto_frame(small, DEFAULT_PALETTE[0], block_px=32)


def test_sample_rejects_block_px_larger_than_frame():
    """Sampling must reject exactly what painting rejects — asymmetry here would
    let a frame be painted at one location and read back at another."""
    from vapi_bridge.retina_witness_mark import _sample_mark_color

    small = np.zeros((16, 16, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="does not fit in frame"):
        _sample_mark_color(small, block_px=32)


def test_composite_rejects_non_positive_block_px():
    frame = _blank_frame()
    for bad in (0, -1, -32):
        with pytest.raises(ValueError, match="positive int"):
            composite_mark_onto_frame(frame, DEFAULT_PALETTE[0], block_px=bad)


def test_composite_accepts_block_px_exactly_frame_size():
    """Boundary: a block the exact size of the frame is degenerate but well-defined
    (it does not wrap), so it must be ACCEPTED — the guard rejects wrapping, not
    edge cases."""
    small = np.zeros((16, 16, 3), dtype=np.uint8)
    marked = composite_mark_onto_frame(small, DEFAULT_PALETTE[0], block_px=16)
    assert marked.shape == small.shape
    assert tuple(int(v) for v in marked[8, 8][:3]) == DEFAULT_PALETTE[0]

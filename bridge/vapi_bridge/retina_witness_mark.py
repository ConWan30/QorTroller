"""Retina Witness Mark — locator mark (RWM L0, Component 2). CANDIDATE, not FROZEN-v1.

A visual, non-cryptographic locator composited into archived capture frames: a small
color-block sequence pointing at "this footage claims session X, checkpoint Y" -- NOT
a proof by itself (see retina_capture_manifest.py for the real tamper-evidence
mechanism). Path A's two-mechanism split, per docs/a2a/retina-witness-mark/scope.md
(D-RWM-1) and l0-implementation-plan.md: the locator is cheap, decodable even on a
transcoded copy, and never claims more than "here is where to look for proof."

DEFAULT_PALETTE is 4 colors -> 2 bits/symbol (F-RWM-6: the original design's bit-budget
math silently assumed 1 bit/symbol with no palette defined; this module defines the
palette first and derives every number from it). PREAMBLE_COLORS (2, disjoint from
DEFAULT_PALETTE) mark sync boundaries so a decoder can find a mark in an arbitrary frame
sequence even with dropped/reordered frames (F-RWM-3).

Bit budget: 96-bit payload (12 bytes) / 2 bits-per-symbol = 48 symbols per payload pass.
x3 repetition (majority-vote decode) = 144 symbol-slots, + the 2-symbol preamble once
per cycle = 146 symbol-slots per full mark cycle.
"""
from __future__ import annotations

from typing import Optional

DOMAIN_TAG = b"VAPI-RETINA-WITNESS-MARK-v1"

# 2 reserved sentinel colors (sync preamble only, never carry payload bits) +
# 4 payload colors (2 bits/symbol) -- 6 total, chosen for maximum pairwise visual
# separation under compression/noise (exact swatch TBD at live-rig testing; these are
# placeholders for the encoding scheme, not a finalized color spec).
PREAMBLE_COLORS: list[tuple[int, int, int]] = [(255, 255, 255), (0, 0, 0)]
DEFAULT_PALETTE: list[tuple[int, int, int]] = [
    (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
]  # R, G, B, Y -> 00, 01, 10, 11

if set(PREAMBLE_COLORS) & set(DEFAULT_PALETTE):
    raise RuntimeError("PREAMBLE_COLORS and DEFAULT_PALETTE must be disjoint")

_REPEAT = 3
_PAYLOAD_BYTES = 12  # 8-byte session hash-prefix + 3-byte checkpoint index + 1-byte CRC-8

# CRC-8-CCITT (polynomial 0x07) -- standard, simple, table-free. Error DETECTION only,
# not correction; ~1/256 undetected-corruption rate, proportionate for a fail-closed
# locator (accepted residual, see LANE RWM r06 review).
_CRC8_POLY = 0x07


def _crc8(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ _CRC8_POLY) & 0xFF if (crc & 0x80) else (crc << 1) & 0xFF
    return crc


def compute_locator_payload(session_id_hash_8b: bytes, checkpoint_index: int) -> bytes:
    """8-byte session_id hash-prefix + 3-byte checkpoint index + 1-byte CRC-8 = 12B/96 bits.

    Deliberately NOT the full commitment from the superseded design -- under Path A
    this is a LOCATOR, not a proof, so it only needs to be practically-unique for
    lookup, not cryptographically complete. Full verification happens by using this
    to find the session, then checking the manifest/chain -- not from the mark alone.

    Args:
        session_id_hash_8b: First 8 bytes of SHA-256(session_id) (caller's
            responsibility to derive consistently).
        checkpoint_index: 0-based checkpoint counter (uint24, up to 16.7M).

    Returns:
        12 bytes: session_id_hash_8b + checkpoint_index_be(3) + crc8(1).
    """
    if len(session_id_hash_8b) != 8:
        raise ValueError(f"session_id_hash_8b must be 8 bytes, got {len(session_id_hash_8b)}")
    if not (0 <= checkpoint_index <= 0xFFFFFF):
        raise ValueError(f"checkpoint_index out of range: {checkpoint_index}")
    body = session_id_hash_8b + checkpoint_index.to_bytes(3, "big")
    return body + bytes([_crc8(body)])


def _bytes_to_2bit_symbols(payload: bytes) -> list[int]:
    symbols = []
    for byte in payload:
        for shift in (6, 4, 2, 0):
            symbols.append((byte >> shift) & 0b11)
    return symbols


def _2bit_symbols_to_bytes(symbols: list[int]) -> bytes:
    if len(symbols) % 4 != 0:
        raise ValueError(f"symbol count must be a multiple of 4, got {len(symbols)}")
    out = bytearray()
    for i in range(0, len(symbols), 4):
        byte = 0
        for j in range(4):
            byte = (byte << 2) | (symbols[i + j] & 0b11)
        out.append(byte)
    return bytes(out)


def encode_mark_symbols(
    payload: bytes, *, palette: list[tuple[int, int, int]] = DEFAULT_PALETTE
) -> list[tuple[int, int, int]]:
    """Encode `payload` as a symbol sequence: 2-symbol sync preamble + payload
    (2 bits/symbol against `palette`, each symbol repeated 3x for majority-vote decode).

    The preamble is drawn from PREAMBLE_COLORS, never reused for payload bits, so a
    decoder can't mistake genuine payload data for a sync marker or vice versa --
    addresses F-RWM-3's missing sync. Repetition-3 is the simplest viable
    error-correction scheme, not full Reed-Solomon, since the payload is only 96 bits;
    if live testing shows it insufficient, Reed-Solomon is the documented fallback.

    Args:
        payload: Exactly _PAYLOAD_BYTES (12) bytes -- see compute_locator_payload.
        palette: 4 colors, disjoint from PREAMBLE_COLORS.

    Returns:
        List of (r, g, b) tuples: [preamble_0, preamble_1, sym_0_rep_0, sym_0_rep_1,
        sym_0_rep_2, sym_1_rep_0, ...] -- 2 + len(payload)*4*3 entries.
    """
    if len(payload) != _PAYLOAD_BYTES:
        raise ValueError(f"payload must be {_PAYLOAD_BYTES} bytes, got {len(payload)}")
    if len(palette) != 4:
        raise ValueError(f"palette must have exactly 4 colors, got {len(palette)}")
    if set(palette) & set(PREAMBLE_COLORS):
        raise ValueError("palette must not overlap PREAMBLE_COLORS")
    symbols = _bytes_to_2bit_symbols(payload)
    out = list(PREAMBLE_COLORS)
    for sym in symbols:
        out.extend([palette[sym]] * _REPEAT)
    return out


def composite_mark_onto_frame(
    frame, symbol: tuple[int, int, int], *, corner: str = "bottom-right", block_px: int = 32
):
    """Paint `symbol` as a block_px x block_px solid block in `corner` of `frame`.

    Pure: returns a NEW frame, never mutates input, operates only on the archival
    copy (matches the superseded design's discipline on this point).

    Args:
        frame: numpy array, shape (H, W, 3) or (H, W, 4), any dtype supporting
            integer color assignment.
        symbol: (r, g, b) color to paint.
        corner: one of "bottom-right", "bottom-left", "top-right", "top-left".
        block_px: side length of the painted square, in pixels.

    Returns:
        A new array of the same shape/dtype as `frame`, with the block painted.
    """
    out = frame.copy()
    h, w = out.shape[0], out.shape[1]
    if corner == "bottom-right":
        y0, y1, x0, x1 = h - block_px, h, w - block_px, w
    elif corner == "bottom-left":
        y0, y1, x0, x1 = h - block_px, h, 0, block_px
    elif corner == "top-right":
        y0, y1, x0, x1 = 0, block_px, w - block_px, w
    elif corner == "top-left":
        y0, y1, x0, x1 = 0, block_px, 0, block_px
    else:
        raise ValueError(f"unknown corner: {corner}")
    out[y0:y1, x0:x1, 0] = symbol[0]
    out[y0:y1, x0:x1, 1] = symbol[1]
    out[y0:y1, x0:x1, 2] = symbol[2]
    return out


def _sample_mark_color(
    frame, *, corner: str = "bottom-right", block_px: int = 32
) -> tuple[int, int, int]:
    """Read back the mark color from a frame's marked corner (center pixel of the block)."""
    h, w = frame.shape[0], frame.shape[1]
    if corner == "bottom-right":
        cy, cx = h - block_px // 2, w - block_px // 2
    elif corner == "bottom-left":
        cy, cx = h - block_px // 2, block_px // 2
    elif corner == "top-right":
        cy, cx = block_px // 2, w - block_px // 2
    elif corner == "top-left":
        cy, cx = block_px // 2, block_px // 2
    else:
        raise ValueError(f"unknown corner: {corner}")
    px = frame[cy, cx]
    return int(px[0]), int(px[1]), int(px[2])


def _nearest_color_index(pixel: tuple[int, int, int], palette: list[tuple[int, int, int]]) -> int:
    best_i, best_d = 0, None
    for i, c in enumerate(palette):
        d = sum((int(pixel[k]) - c[k]) ** 2 for k in range(3))
        if best_d is None or d < best_d:
            best_i, best_d = i, d
    return best_i


def decode_mark_from_frames(
    frames: list,
    *,
    corner: str = "bottom-right",
    block_px: int = 32,
    palette: list[tuple[int, int, int]] = DEFAULT_PALETTE,
) -> Optional[bytes]:
    """Scan `frames` for the 2-symbol sync preamble, then majority-vote decode the
    payload run following it.

    Returns None (not a wrong answer) if no valid preamble is found, an incomplete
    payload run follows it, or the CRC-8 check fails -- fail-closed, matching this
    session's established discipline for every oracle touched this arc.

    Args:
        frames: sequence of numpy arrays (frame_i.shape supports _sample_mark_color).
        corner, block_px, palette: must match the encode-side parameters.

    Returns:
        The 12-byte decoded payload (see compute_locator_payload), or None.
    """
    full_alphabet = list(PREAMBLE_COLORS) + list(palette)
    classified = [_nearest_color_index(_sample_mark_color(f, corner=corner, block_px=block_px), full_alphabet)
                  for f in frames]
    # indices 0,1 in full_alphabet are the two preamble colors; 2..5 are payload colors
    n_payload_symbols = _PAYLOAD_BYTES * 4  # 2 bits/symbol
    needed_after_preamble = n_payload_symbols * _REPEAT
    for i in range(len(classified) - 1):
        if classified[i] == 0 and classified[i + 1] == 1:
            start = i + 2
            if start + needed_after_preamble > len(classified):
                continue  # not enough frames left for a full payload run from this sync point
            run = classified[start:start + needed_after_preamble]
            if any(c < 2 for c in run):
                continue  # a preamble color appears inside the claimed payload run -- not a real match
            payload_symbols = []
            ok = True
            for g in range(n_payload_symbols):
                votes = run[g * _REPEAT:(g + 1) * _REPEAT]
                counts = {v: votes.count(v) for v in set(votes)}
                majority = max(counts, key=counts.get)
                if counts[majority] < 2:  # no majority among 3 votes -- reject this sync point
                    ok = False
                    break
                payload_symbols.append(majority - 2)  # rebase palette index 2..5 -> 0..3
            if not ok:
                continue
            try:
                candidate = _2bit_symbols_to_bytes(payload_symbols)
            except ValueError:
                continue
            body, crc = candidate[:-1], candidate[-1]
            if _crc8(body) != crc:
                continue  # CRC mismatch -- corrupted decode, never return a wrong-but-plausible payload
            return candidate
    return None

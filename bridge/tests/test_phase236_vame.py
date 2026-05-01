"""Phase 236-VAME — VAPI Application-Layer Message Envelope. FROZEN FORMULA v1.

Closes the source-without-tests drift surfaced by the Phase O0 test-coverage
audit: bridge/vapi_bridge/vame.py shipped in commit cb902568 but no test file
existed despite CLAUDE.md asserting T236-VAME-1..8.

Scope: pure-formula tests against vame.py only. The Starlette _VAMEMiddleware
that splices these headers onto live responses is exercised through the
operator-API integration tests, not here.

T236-VAME-1: chain_head_from_hex edge cases — None, empty, valid 64-hex,
             short hex (zero-padded to 16B), invalid hex (zeroed)
T236-VAME-2: compute_vame_commitment manual SHA-256 recompute matches
T236-VAME-3: stamp_response_headers header contract — 5 keys, exact names + shapes
T236-VAME-4: body tamper detection — modifying body_bytes changes commitment
T236-VAME-5: chain-head tamper detection — different chain head → different commitment
T236-VAME-6: ts_ns tamper detection — different ts_ns → different commitment
T236-VAME-7: chain_head length validation — wrong-length chain_head → ValueError
T236-VAME-8: ts_ns range validation — out of uint64 range → ValueError
"""
import hashlib
import os
import struct
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.vame import (
    VAME_VERSION_STR,
    chain_head_from_hex,
    compute_vame_commitment,
    stamp_response_headers,
)

_VAME_TAG = b"VAPI-VAME-v1"
_CHAIN_HEAD_BYTES = 16
_GIC_HEX = "deadbeef" * 8  # 64-hex = 32 bytes
_ENDPOINT = "/bridge/grind-chain-status"
_BODY = b'{"chain_length":20,"chain_intact":true}'


# ---------------------------------------------------------------------------
# T236-VAME-1: chain_head_from_hex edge cases
# ---------------------------------------------------------------------------

def test_t236_vame_1_chain_head_edge_cases():
    # None and empty → 16 zero bytes
    assert chain_head_from_hex(None) == b"\x00" * 16
    assert chain_head_from_hex("")   == b"\x00" * 16

    # Valid 64-hex GIC → first 16 bytes
    head = chain_head_from_hex(_GIC_HEX)
    assert len(head) == 16
    assert head == bytes.fromhex(_GIC_HEX)[:16]

    # Short hex → zero-padded right to 16 bytes
    short = chain_head_from_hex("ab" * 4)  # 4 bytes
    assert len(short) == 16
    assert short == bytes.fromhex("ab" * 4) + b"\x00" * 12

    # Invalid hex → 16 zero bytes (fail-open, matches docstring)
    assert chain_head_from_hex("not-hex-at-all") == b"\x00" * 16
    assert chain_head_from_hex("zz") == b"\x00" * 16


# ---------------------------------------------------------------------------
# T236-VAME-2: commitment manual recompute
# ---------------------------------------------------------------------------

def test_t236_vame_2_commitment_correct():
    ts_ns = 1745000000000000000
    head = chain_head_from_hex(_GIC_HEX)
    commitment = compute_vame_commitment(head, ts_ns, _ENDPOINT, _BODY)

    expected_hex = hashlib.sha256(
        _VAME_TAG
        + head
        + struct.pack(">Q", ts_ns)
        + _ENDPOINT.encode("utf-8")
        + _BODY
    ).hexdigest()

    assert commitment == expected_hex
    assert len(commitment) == 64
    assert int(commitment, 16) >= 0  # valid hex


# ---------------------------------------------------------------------------
# T236-VAME-3: stamp_response_headers contract
# ---------------------------------------------------------------------------

def test_t236_vame_3_header_contract():
    ts_ns = 1745000000000000000
    headers = stamp_response_headers(_GIC_HEX, _ENDPOINT, _BODY, ts_ns=ts_ns)

    # Exactly the 5 frozen header keys
    assert set(headers.keys()) == {
        "X-VAME-Version",
        "X-VAME-Commitment",
        "X-VAME-Chain-Head",
        "X-VAME-TS-NS",
        "X-VAME-Endpoint",
    }

    # Version is the FROZEN string — any change is a v2 break
    assert headers["X-VAME-Version"] == VAME_VERSION_STR == "vame/1.0"

    # Commitment is 64-hex, matches the formula output
    assert len(headers["X-VAME-Commitment"]) == 64
    head = chain_head_from_hex(_GIC_HEX)
    assert headers["X-VAME-Commitment"] == compute_vame_commitment(
        head, ts_ns, _ENDPOINT, _BODY
    )

    # Chain-Head is exactly 32-hex (16 bytes)
    assert len(headers["X-VAME-Chain-Head"]) == 32
    assert headers["X-VAME-Chain-Head"] == head.hex()

    # TS-NS is the integer as a string
    assert headers["X-VAME-TS-NS"] == str(ts_ns)

    # Endpoint is echoed verbatim
    assert headers["X-VAME-Endpoint"] == _ENDPOINT

    # Default ts_ns path (no kwarg) still produces 5 keys
    headers_auto = stamp_response_headers(_GIC_HEX, _ENDPOINT, _BODY)
    assert set(headers_auto.keys()) == set(headers.keys())


# ---------------------------------------------------------------------------
# T236-VAME-4: body tamper detection
# ---------------------------------------------------------------------------

def test_t236_vame_4_body_tamper_detection():
    ts_ns = 1745000000000000000
    head = chain_head_from_hex(_GIC_HEX)

    legit = compute_vame_commitment(head, ts_ns, _ENDPOINT, _BODY)
    tampered = compute_vame_commitment(
        head, ts_ns, _ENDPOINT, _BODY + b" "  # one extra byte
    )
    assert legit != tampered


# ---------------------------------------------------------------------------
# T236-VAME-5: chain-head tamper detection
# ---------------------------------------------------------------------------

def test_t236_vame_5_chain_head_tamper_detection():
    ts_ns = 1745000000000000000
    head_a = chain_head_from_hex("aa" * 32)
    head_b = chain_head_from_hex("bb" * 32)
    assert head_a != head_b

    commit_a = compute_vame_commitment(head_a, ts_ns, _ENDPOINT, _BODY)
    commit_b = compute_vame_commitment(head_b, ts_ns, _ENDPOINT, _BODY)
    assert commit_a != commit_b

    # No-chain anchor differs from any real chain head
    no_chain = compute_vame_commitment(b"\x00" * 16, ts_ns, _ENDPOINT, _BODY)
    assert no_chain != commit_a


# ---------------------------------------------------------------------------
# T236-VAME-6: ts_ns tamper detection
# ---------------------------------------------------------------------------

def test_t236_vame_6_ts_tamper_detection():
    head = chain_head_from_hex(_GIC_HEX)
    commit_t1 = compute_vame_commitment(head, 1745000000000000000, _ENDPOINT, _BODY)
    commit_t2 = compute_vame_commitment(head, 1745000000000000001, _ENDPOINT, _BODY)
    assert commit_t1 != commit_t2

    # Endpoint sensitivity (bonus, same byte-budget) — different endpoint → different commit
    commit_other = compute_vame_commitment(
        head, 1745000000000000000, "/bridge/capture-health", _BODY
    )
    assert commit_other != commit_t1


# ---------------------------------------------------------------------------
# T236-VAME-7: chain_head length validation
# ---------------------------------------------------------------------------

def test_t236_vame_7_chain_head_length_invalid():
    ts_ns = 1745000000000000000
    with pytest.raises(ValueError):
        compute_vame_commitment(b"\x00" * 8, ts_ns, _ENDPOINT, _BODY)
    with pytest.raises(ValueError):
        compute_vame_commitment(b"\x00" * 32, ts_ns, _ENDPOINT, _BODY)
    with pytest.raises(ValueError):
        compute_vame_commitment(b"", ts_ns, _ENDPOINT, _BODY)


# ---------------------------------------------------------------------------
# T236-VAME-8: ts_ns range validation
# ---------------------------------------------------------------------------

def test_t236_vame_8_ts_ns_range_invalid():
    head = chain_head_from_hex(_GIC_HEX)
    with pytest.raises(ValueError):
        compute_vame_commitment(head, -1, _ENDPOINT, _BODY)
    with pytest.raises(ValueError):
        compute_vame_commitment(head, 0x1_0000_0000_0000_0000, _ENDPOINT, _BODY)

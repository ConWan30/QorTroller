"""Phase O0 Stream 4-prep Session 1 — HMAC request signing middleware tests.

Verifies hmac_middleware behavior per Pass 2C Section 5.1 +
Decisions A3, A4. Canonical request format is METHOD\\nPATH\\nTIMESTAMP\\nNONCE\\nSHA256_HEX(body);
signature is base64 HMAC-SHA-256; timestamp tolerance ±300s; nonce
dedup window 600s.

Tests:
  T-HMAC-1:  compute_canonical_request determinism — same inputs always
             produce the same canonical string.
  T-HMAC-2:  compute_canonical_request format conformance — Pass 2C
             field order METHOD\\nPATH\\nTIMESTAMP\\nNONCE\\nSHA256_HEX(body),
             5 newline-separated parts, body hash is hex SHA-256.
  T-HMAC-3:  per-input-field sensitivity — single-field changes (method
             case-only excluded since uppercased internally; path,
             timestamp, nonce, body) produce a different canonical.
  T-HMAC-4:  compute_hmac determinism + base64 encoding sanity — output
             is 44-char ASCII base64 of 32-byte HMAC-SHA256 digest.
  T-HMAC-5:  verify_hmac success — round-trip through compute and verify.
  T-HMAC-6:  verify_hmac failure on tampered signature raises
             HmacInvalidSignature (constant-time compare via
             hmac.compare_digest).
  T-HMAC-7:  NonceDedupTracker rejects duplicate nonce within window
             (HmacReplayDetected); accepts after the TTL elapses.
  T-HMAC-8:  NonceDedupTracker lazy-evicts stale entries on each call.
  T-HMAC-9:  NonceDedupTracker rejects empty nonce with ValueError
             (defense in depth — empty nonce would create dedup
             collisions across all empty-nonce requests).
  T-HMAC-10: check_timestamp_freshness accepts within ±tolerance,
             rejects outside (HmacStaleTimestamp). Both directions
             (past and future) tested per Pass 2C ±300s spec.
  T-HMAC-11: end-to-end flow — sign a request, verify the signature,
             check timestamp freshness, register the nonce. All steps
             pass for a fresh request; replay detection fires on the
             second attempt.
  T-HMAC-12: hmac.compare_digest is the comparison primitive — verified
             via source-grep so future refactors cannot accidentally
             swap to == without surfacing in this test.
"""
import os
import re
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.hmac_middleware import (  # noqa: E402
    NonceDedupTracker,
    check_timestamp_freshness,
    compute_canonical_request,
    compute_hmac,
    verify_hmac,
    HmacInvalidSignature,
    HmacReplayDetected,
    HmacStaleTimestamp,
)


# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

_SECRET = "test-hmac-shared-secret-32-bytes-min"
_METHOD = "GET"
_PATH = "/agent/agent-commit-history"
_TS = 1714280000  # arbitrary fixed Unix seconds
_NONCE = "11111111-2222-3333-4444-555555555555"
_BODY = b""


# ---------------------------------------------------------------------------
# T-HMAC-1
# ---------------------------------------------------------------------------

def test_t_hmac_1_canonical_request_determinism():
    """Same inputs produce the same canonical string across repeated calls."""
    s1 = compute_canonical_request(_METHOD, _PATH, _TS, _NONCE, _BODY)
    s2 = compute_canonical_request(_METHOD, _PATH, _TS, _NONCE, _BODY)
    assert s1 == s2


# ---------------------------------------------------------------------------
# T-HMAC-2
# ---------------------------------------------------------------------------

def test_t_hmac_2_canonical_request_format_per_pass_2c():
    """Pass 2C Section 5.1 line 736 freezes the order METHOD\\nPATH\\nTIMESTAMP\\nNONCE\\nSHA256_HEX(body)."""
    canonical = compute_canonical_request(_METHOD, _PATH, _TS, _NONCE, _BODY)
    parts = canonical.split("\n")
    assert len(parts) == 5
    assert parts[0] == "GET"             # METHOD (uppercased)
    assert parts[1] == _PATH             # PATH
    assert parts[2] == str(_TS)          # TIMESTAMP (decimal string)
    assert parts[3] == _NONCE            # NONCE
    # parts[4] = SHA-256 hex of empty body = e3b0c44...
    assert parts[4] == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )

    # Lowercased method input still produces uppercased canonical (defense
    # against accidental case mismatches between sign and verify sides)
    canonical_lc = compute_canonical_request("get", _PATH, _TS, _NONCE, _BODY)
    assert canonical_lc == canonical


# ---------------------------------------------------------------------------
# T-HMAC-3
# ---------------------------------------------------------------------------

def test_t_hmac_3_per_field_sensitivity():
    """Single-field changes produce a different canonical string."""
    base = compute_canonical_request(_METHOD, _PATH, _TS, _NONCE, _BODY)

    # Different path
    assert compute_canonical_request(_METHOD, "/different/path", _TS, _NONCE, _BODY) != base
    # Different timestamp
    assert compute_canonical_request(_METHOD, _PATH, _TS + 1, _NONCE, _BODY) != base
    # Different nonce
    assert compute_canonical_request(_METHOD, _PATH, _TS, "different-nonce", _BODY) != base
    # Different body
    assert compute_canonical_request(_METHOD, _PATH, _TS, _NONCE, b"different") != base
    # Different method (verb)
    assert compute_canonical_request("POST", _PATH, _TS, _NONCE, _BODY) != base


# ---------------------------------------------------------------------------
# T-HMAC-4
# ---------------------------------------------------------------------------

def test_t_hmac_4_compute_hmac_determinism_and_base64_format():
    """compute_hmac is deterministic and returns a 44-char standard
    base64 string (32-byte HMAC-SHA256 digest base64 = 44 chars with
    one '=' pad).
    """
    canonical = compute_canonical_request(_METHOD, _PATH, _TS, _NONCE, _BODY)
    s1 = compute_hmac(canonical, _SECRET)
    s2 = compute_hmac(canonical, _SECRET)
    assert s1 == s2
    assert len(s1) == 44  # 32 bytes base64 + padding
    assert re.match(r"^[A-Za-z0-9+/]+=*$", s1) is not None  # standard b64 alphabet

    # Sanity: not empty / not the input
    assert s1
    assert s1 != canonical


# ---------------------------------------------------------------------------
# T-HMAC-5
# ---------------------------------------------------------------------------

def test_t_hmac_5_verify_hmac_success():
    """Sign → verify round trip. verify_hmac returns None on success."""
    canonical = compute_canonical_request(_METHOD, _PATH, _TS, _NONCE, _BODY)
    sig = compute_hmac(canonical, _SECRET)
    # Should not raise
    verify_hmac(sig, canonical, _SECRET)


# ---------------------------------------------------------------------------
# T-HMAC-6
# ---------------------------------------------------------------------------

def test_t_hmac_6_verify_hmac_invalid_signature_raises():
    """Tampered signature triggers HmacInvalidSignature."""
    canonical = compute_canonical_request(_METHOD, _PATH, _TS, _NONCE, _BODY)
    sig = compute_hmac(canonical, _SECRET)
    # Flip one base64 character (preserve length)
    flipped = ("X" + sig[1:]) if sig[0] != "X" else ("Y" + sig[1:])
    with pytest.raises(HmacInvalidSignature, match="mismatch"):
        verify_hmac(flipped, canonical, _SECRET)

    # Wrong secret also raises
    with pytest.raises(HmacInvalidSignature):
        verify_hmac(sig, canonical, "different-secret")

    # Wrong canonical also raises
    other_canonical = compute_canonical_request(_METHOD, "/other", _TS, _NONCE, _BODY)
    with pytest.raises(HmacInvalidSignature):
        verify_hmac(sig, other_canonical, _SECRET)


# ---------------------------------------------------------------------------
# T-HMAC-7
# ---------------------------------------------------------------------------

def test_t_hmac_7_nonce_dedup_within_window():
    """Same nonce twice within the TTL window raises HmacReplayDetected;
    same nonce after the window passes (eviction).
    """
    tracker = NonceDedupTracker(ttl_seconds=600)

    # First registration: success
    tracker.check_and_register("nonce-A", now_seconds=1000)
    assert tracker.size == 1

    # Replay at the same time: rejected
    with pytest.raises(HmacReplayDetected, match="nonce-A"):
        tracker.check_and_register("nonce-A", now_seconds=1010)

    # Different nonce at the same time: accepted
    tracker.check_and_register("nonce-B", now_seconds=1010)

    # Replay AFTER TTL elapses: accepted (entry was evicted)
    # nonce-A's stored ts=1000; at now=1700 (TTL=600 → cutoff=1100), 1000<1100 → evicted
    tracker.check_and_register("nonce-A", now_seconds=1700)


# ---------------------------------------------------------------------------
# T-HMAC-8
# ---------------------------------------------------------------------------

def test_t_hmac_8_nonce_lazy_eviction():
    """Stale entries are dropped on each check_and_register call."""
    tracker = NonceDedupTracker(ttl_seconds=600)

    # Insert 3 nonces at t=1000
    for i, n in enumerate(["nA", "nB", "nC"]):
        tracker.check_and_register(n, now_seconds=1000 + i)
    assert tracker.size == 3

    # Trigger eviction with a fresh registration far in the future
    tracker.check_and_register("nD", now_seconds=2000)
    # All 3 stale (cutoff=1400, all stored ts<1400) → evicted
    # tracker now holds only "nD"
    assert tracker.size == 1
    assert "nD" in tracker._seen
    assert "nA" not in tracker._seen


# ---------------------------------------------------------------------------
# T-HMAC-9
# ---------------------------------------------------------------------------

def test_t_hmac_9_empty_nonce_raises_value_error():
    """Empty nonce rejected at register time (defense against dedup
    collisions across all empty-nonce requests)."""
    tracker = NonceDedupTracker()
    with pytest.raises(ValueError, match="non-empty"):
        tracker.check_and_register("")


# ---------------------------------------------------------------------------
# T-HMAC-10
# ---------------------------------------------------------------------------

def test_t_hmac_10_timestamp_freshness_window():
    """check_timestamp_freshness accepts within ±tolerance, rejects outside.
    Pass 2C Section 5.1 line 741: ±300s clock skew window (Decision A4).
    """
    now = 1_700_000_000
    # Within tolerance — past + future
    check_timestamp_freshness(now - 100, tolerance_seconds=300, now_seconds=now)
    check_timestamp_freshness(now + 100, tolerance_seconds=300, now_seconds=now)
    # Boundary — exactly 300s
    check_timestamp_freshness(now - 300, tolerance_seconds=300, now_seconds=now)
    check_timestamp_freshness(now + 300, tolerance_seconds=300, now_seconds=now)

    # Outside tolerance — past
    with pytest.raises(HmacStaleTimestamp, match="exceeds tolerance"):
        check_timestamp_freshness(now - 301, tolerance_seconds=300, now_seconds=now)
    # Outside tolerance — future
    with pytest.raises(HmacStaleTimestamp, match="exceeds tolerance"):
        check_timestamp_freshness(now + 301, tolerance_seconds=300, now_seconds=now)


# ---------------------------------------------------------------------------
# T-HMAC-11
# ---------------------------------------------------------------------------

def test_t_hmac_11_end_to_end_signing_flow():
    """End-to-end: sign a request → verify signature → check timestamp →
    register nonce. Replay attempt fails on the second registration.
    """
    tracker = NonceDedupTracker(ttl_seconds=600)

    # Signer side
    method = "POST"
    path = "/agent/something"
    timestamp = int(time.time())
    nonce = "abc-def-ghi-end-to-end"
    body = b'{"key": "value"}'

    canonical = compute_canonical_request(method, path, timestamp, nonce, body)
    signature = compute_hmac(canonical, _SECRET)

    # Verifier side
    verify_hmac(signature, canonical, _SECRET)
    check_timestamp_freshness(timestamp, tolerance_seconds=300)
    tracker.check_and_register(nonce)

    # Replay attempt → HmacReplayDetected
    with pytest.raises(HmacReplayDetected):
        tracker.check_and_register(nonce)


# ---------------------------------------------------------------------------
# T-HMAC-12
# ---------------------------------------------------------------------------

def test_t_hmac_12_uses_compare_digest():
    """Source-grep verifies hmac.compare_digest is the comparison
    primitive (not == on signature strings). Defense against future
    refactors silently downgrading to a non-constant-time compare.
    """
    import vapi_bridge.hmac_middleware as hm
    src = open(hm.__file__, "r", encoding="utf-8").read()
    assert "hmac.compare_digest" in src, (
        "hmac_middleware must use hmac.compare_digest for timing-attack safety"
    )

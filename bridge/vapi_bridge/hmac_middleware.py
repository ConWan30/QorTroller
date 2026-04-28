"""Phase O0 Stream 4-prep Session 1 — HMAC request signing middleware.

Verifies per-request HMAC-SHA256 signatures on agent requests to the
bridge. Composes WITH OAuth 2.1 token verification (oauth_issuer.py) —
both layers must succeed at the FastAPI dependency boundary (Session 2)
for an /agent/* request to authenticate.

The HMAC layer protects against:
  - Token replay across requests (per-request nonce dedup)
  - Body tampering between TLS termination and the bridge process
    (body hash bound into the canonical request)
  - Stale tokens being reused outside the timestamp tolerance window
  - Method/path spoofing (METHOD and PATH bound into canonical request)

Origin and design lineage:

  Pass 2A V2 Option B selected OAuth 2.1 + HMAC over mTLS.

  Pass 2C Section 5.1 lines 732-755 ratified:
    - Canonical request format (Decision A3): METHOD\nPATH\nTIMESTAMP\nNONCE\nSHA256(body)
    - Headers (Decision A4): X-Agent-KeyId, X-Timestamp, X-Nonce, X-Signature
    - Signature encoding (Decision A4): base64 HMAC-SHA-256
    - Timestamp tolerance (Decision A4): ±300 seconds clock skew
    - Nonce dedup window (Decision A4): 600 seconds (twice clock skew)
    - In-memory LRU nonce store; Redis-backed deferred to P3+

  Decision A3 (Stream 4-prep Session 1) corrected the Session 1 prompt's
    suggested canonical-request order (timestamp+nonce+method+path+body)
    to Pass 2C's specification (METHOD\nPATH\nTIMESTAMP\nNONCE\nSHA256(body)).
    Pass 2C is the design contract; the prompt order was drift.

  Decision A4 (Stream 4-prep Session 1) adopted Pass 2C's three numeric/
    encoding deltas vs the prompt: timestamp tolerance 300s (not 60s),
    nonce dedup window 600s (not 300s), signature base64 (not hex).

Canonical request format (FROZEN per Pass 2C; field order is load-bearing
for HMAC verification compatibility with on-the-wire signatures):

    METHOD\n
    PATH\n
    TIMESTAMP\n
    NONCE\n
    SHA256_HEX(body)

  - METHOD is uppercased ("GET", "POST", "PUT", "DELETE", ...).
  - PATH is the request URI path component including any query string
    the caller chooses to include in their signature. Callers MUST be
    consistent: if the signing side includes the query, the verifying
    side must too. Phase O0 convention: PATH = path + "?" + query when
    a query string is present, else just path. Callers are responsible
    for canonicalization.
  - TIMESTAMP is integer Unix seconds, formatted as decimal string.
  - NONCE is a UUIDv4 hex (or any unique-per-window string).
  - SHA256_HEX(body) is hashlib.sha256(body_bytes).hexdigest(). Empty
    body → SHA-256 of zero bytes (a fixed well-known value).

Threading model:

  NonceDedupTracker is designed for a single asyncio event loop. The
  bridge runs a single Uvicorn event loop; all FastAPI dependencies
  execute in that loop without thread parallelism for sync handlers,
  so the tracker's plain dict access is safe without locks. Future
  multi-worker deployments would need a Redis-backed nonce store
  (Pass 2C Section 5.1 line 750).

Authentication is OPERATIONAL infrastructure, NOT a FROZEN-v1 primitive.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Optional


# Defaults per Decision A4 (Pass 2C Section 5.1 lines 741, 750).
_DEFAULT_TIMESTAMP_TOLERANCE_S = 300
_DEFAULT_NONCE_TTL_S = 600


# -----------------------------------------------------------------------
# Custom exceptions
# -----------------------------------------------------------------------

class HmacValidationError(Exception):
    """Generic HMAC validation failure base class."""


class HmacInvalidSignature(HmacValidationError):
    """Provided signature does not match the expected signature."""


class HmacReplayDetected(HmacValidationError):
    """Nonce has been seen within the dedup window."""


class HmacStaleTimestamp(HmacValidationError):
    """Timestamp is outside the configured tolerance window."""


# -----------------------------------------------------------------------
# Canonical request + signature primitives
# -----------------------------------------------------------------------

def compute_canonical_request(
    method: str,
    path: str,
    timestamp: int,
    nonce: str,
    body_bytes: bytes,
) -> str:
    """Build the canonical request string per Pass 2C Section 5.1.

    Field order is FROZEN: METHOD\\nPATH\\nTIMESTAMP\\nNONCE\\nSHA256_HEX(body).
    Any change to field order or separator invalidates every signature
    issued by signers that follow the documented format.

    Args:
        method:      HTTP method; uppercased internally for consistency.
        path:        Request URI path (caller-canonicalized).
        timestamp:   Integer Unix seconds.
        nonce:       Per-request unique string (UUIDv4 hex recommended).
        body_bytes:  Raw request body as bytes (use b"" for empty body).

    Returns:
        The canonical request string.
    """
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    return f"{method.upper()}\n{path}\n{int(timestamp)}\n{nonce}\n{body_hash}"


def compute_hmac(canonical_request: str, secret: str) -> str:
    """Compute HMAC-SHA256 over the canonical request, base64-encoded.

    Returns the standard base64 encoding (RFC 4648 §4) of the 32-byte
    HMAC-SHA256 digest. URL-safe base64 is NOT used per Pass 2C —
    standard base64 matches the "X-Signature" header convention in
    Pass 2C Section 5.1 line 743.

    Args:
        canonical_request:  Output of compute_canonical_request().
        secret:             Per-agent HMAC signing secret.

    Returns:
        Base64-encoded HMAC-SHA256 digest as ASCII string (44 chars).
    """
    digest = hmac.new(
        secret.encode("utf-8"),
        canonical_request.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def verify_hmac(
    provided_signature_b64: str,
    canonical_request: str,
    secret: str,
) -> None:
    """Verify a base64-encoded HMAC-SHA256 signature in constant time.

    Raises:
        HmacInvalidSignature:  provided signature does not match the
                               expected signature for the given
                               canonical request and secret.

    Uses hmac.compare_digest on the base64 strings (same length when
    both are valid HMAC-SHA256 outputs → 44 chars including padding).
    Constant-time on equal-length strings is sufficient for the timing-
    attack defense; padding-stripping or base64-decoding before compare
    would not improve the property.
    """
    expected = compute_hmac(canonical_request, secret)
    if not hmac.compare_digest(expected, provided_signature_b64):
        raise HmacInvalidSignature("HMAC signature mismatch")


def check_timestamp_freshness(
    timestamp: int,
    tolerance_seconds: int = _DEFAULT_TIMESTAMP_TOLERANCE_S,
    now_seconds: "Optional[int]" = None,
) -> None:
    """Reject timestamps outside the tolerance window.

    Per Pass 2C Section 5.1 line 741: ±300s clock skew window enforced.

    Args:
        timestamp:          Unix seconds claimed by the request.
        tolerance_seconds:  Maximum |now - timestamp| accepted (default 300).
        now_seconds:        Override for testing (default = time.time()).

    Raises:
        HmacStaleTimestamp:  if abs(now - timestamp) > tolerance_seconds.
    """
    now = int(now_seconds if now_seconds is not None else time.time())
    delta = abs(now - int(timestamp))
    if delta > int(tolerance_seconds):
        raise HmacStaleTimestamp(
            f"timestamp delta {delta}s exceeds tolerance {tolerance_seconds}s"
        )


# -----------------------------------------------------------------------
# NonceDedupTracker
# -----------------------------------------------------------------------

class NonceDedupTracker:
    """In-memory nonce dedup tracker with TTL eviction.

    Stores {nonce: ts_seen}. On each check_and_register call, lazy-
    evicts entries older than ttl_seconds, then either accepts the new
    nonce (storing ts_seen=now) or rejects it as a replay.

    Per Pass 2C Section 5.1 line 750: TTL = 600 seconds (twice the
    ±300s clock skew window).

    Single-event-loop assumption: not threadsafe. The bridge runs a
    single Uvicorn event loop; all FastAPI handlers share it without
    thread parallelism for sync code, so plain dict access is safe.
    Multi-worker deployments need Redis-backed dedup (P3+).
    """

    def __init__(self, ttl_seconds: int = _DEFAULT_NONCE_TTL_S) -> None:
        if int(ttl_seconds) <= 0:
            raise ValueError(f"ttl_seconds must be positive, got {ttl_seconds}")
        self._ttl_seconds = int(ttl_seconds)
        self._seen: dict[str, int] = {}

    @property
    def ttl_seconds(self) -> int:
        return self._ttl_seconds

    @property
    def size(self) -> int:
        return len(self._seen)

    def check_and_register(
        self,
        nonce: str,
        now_seconds: "Optional[int]" = None,
    ) -> None:
        """Register a nonce; raise HmacReplayDetected if seen in-window.

        Args:
            nonce:        The per-request nonce string. Must be non-empty.
            now_seconds:  Override for testing (default = time.time()).

        Raises:
            HmacReplayDetected:  nonce was registered within the last
                                 ttl_seconds.
            ValueError:          nonce is empty.
        """
        if not nonce:
            raise ValueError("nonce must be non-empty")

        now = int(now_seconds if now_seconds is not None else time.time())
        cutoff = now - self._ttl_seconds

        # Lazy eviction: drop entries older than the cutoff.
        # Build a list first to avoid "dict changed size during iteration".
        stale = [n for n, ts in self._seen.items() if ts < cutoff]
        for n in stale:
            del self._seen[n]

        if nonce in self._seen:
            raise HmacReplayDetected(f"nonce already seen: {nonce}")

        self._seen[nonce] = now

"""Phase O0 Stream 4-prep Session 2 — agent_auth.py FastAPI dependency tests.

Verifies _check_agent_token's eight-step validation sequence per Pass
2C Section 5.1 + Decisions B1-A, B3, B4. Tests use a tiny FastAPI app
with one /protected endpoint that depends on the dependency, then
exercise it via FastAPI TestClient with various header combinations.

Tests:
  T-AA-1:   Success — valid OAuth + valid HMAC + fresh timestamp +
            unique nonce returns 200 with AgentIdentity payload.
  T-AA-2:   Step 0 — OAuth not configured (no clients) → 503.
  T-AA-3:   Step 1 — missing Authorization header → 401.
  T-AA-4:   Step 1 — Authorization not Bearer scheme → 401.
  T-AA-5:   Step 2 — invalid OAuth token (wrong secret) → 401 with
            "invalid token" message.
  T-AA-6:   Step 2 — expired OAuth token → 401 with "token expired".
  T-AA-7:   Step 2 — token granting wrong scope → 401 with
            "insufficient scope".
  T-AA-8:   Step 3 — missing X-Agent-KeyId / X-Timestamp / X-Nonce /
            X-Signature each → 401 listing the missing header.
  T-AA-9:   Step 4 — X-Agent-KeyId != OAuth token sub → 401 with
            "binding violation" (Decision B1-A).
  T-AA-10:  Step 5 — non-integer X-Timestamp → 401.
  T-AA-11:  Step 6 — invalid HMAC signature → 401 with "signature
            invalid".
  T-AA-12:  Step 7 — stale timestamp (past tolerance) → 401.
  T-AA-13:  Step 7 — future timestamp (past tolerance) → 401.
  T-AA-14:  Step 8 — replay attack (duplicate nonce) → 401 with
            "replay detected" on second attempt.
  T-AA-15:  Decision B4 — query string included in canonical PATH;
            request signed with path-only PATH fails verification when
            query is present (defense against query-tampering attacks).
"""
import base64
import hashlib
import hmac
import os
import sys
import time

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import jwt  # type: ignore[import-untyped]

from vapi_bridge.agent_auth import (  # noqa: E402
    AgentIdentity,
    make_check_agent_token,
)
from vapi_bridge.hmac_middleware import NonceDedupTracker  # noqa: E402
from vapi_bridge.oauth_issuer import OAuthIssuer  # noqa: E402


# ---------------------------------------------------------------------------
# Shared test fixtures + helpers
# ---------------------------------------------------------------------------

_SECRET = "test-issuer-signing-secret-32-bytes-min"
_CLIENT_ID = "vapi-anchor-sentry"
_CLIENT_SECRET = "sentry-shared-secret-not-real"
_PHASE_O0_SCOPES = ["bridge:agent:phases:read"]
_TEST_PATH = "/protected"


def _build_app(
    issuer_secret: str = _SECRET,
    clients: "dict | None" = None,
    nonce_tracker: NonceDedupTracker | None = None,
    timestamp_tolerance_seconds: int = 300,
) -> "tuple[TestClient, NonceDedupTracker]":
    """Build a tiny FastAPI app with a single protected endpoint.

    Returns (TestClient, NonceDedupTracker) so tests can inspect or
    seed the tracker. When `clients` is None, OAuth issuer is None
    (simulates not-configured state for T-AA-2).
    """
    if clients is None:
        oauth_issuer = None
        oauth_clients: dict = {}
    else:
        oauth_issuer = OAuthIssuer(
            secret=issuer_secret,
            clients=clients,
            ttl_seconds=300,
        )
        oauth_clients = clients

    if nonce_tracker is None:
        nonce_tracker = NonceDedupTracker(ttl_seconds=600)

    dep = make_check_agent_token(
        oauth_issuer=oauth_issuer,
        oauth_clients=oauth_clients,
        nonce_tracker=nonce_tracker,
        timestamp_tolerance_seconds=timestamp_tolerance_seconds,
    )

    app = FastAPI()

    @app.get(_TEST_PATH)
    async def protected(auth: AgentIdentity = Depends(dep)):
        return {
            "client_id":      auth.client_id,
            "agent_kid":      auth.agent_kid,
            "granted_scopes": auth.granted_scopes,
        }

    return TestClient(app), nonce_tracker


def _make_token(
    client_id: str = _CLIENT_ID,
    secret: str = _SECRET,
    scopes: "list[str]" = _PHASE_O0_SCOPES,
    ttl: int = 300,
) -> str:
    """Mint a fresh OAuth-equivalent JWT directly (bypassing OAuthIssuer
    so tests can construct edge-case tokens like wrong-secret variants).
    """
    now = int(time.time())
    payload = {
        "sub":   client_id,
        "iss":   "vapi-bridge-oauth",
        "aud":   "vapi-bridge-agent-endpoints",
        "exp":   now + ttl,
        "iat":   now,
        "scope": " ".join(scopes),
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    if isinstance(token, bytes):
        token = token.decode("ascii")
    return token


def _sign_request(
    method: str,
    path: str,
    body: bytes,
    secret: str,
    timestamp: "int | None" = None,
    nonce: "str | None" = None,
) -> "tuple[int, str, str]":
    """Compute (timestamp, nonce, signature_b64) for a given request."""
    ts = timestamp if timestamp is not None else int(time.time())
    n = nonce if nonce is not None else f"nonce-{ts}-{os.urandom(4).hex()}"
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = f"{method.upper()}\n{path}\n{ts}\n{n}\n{body_hash}"
    sig = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).digest()
    return (ts, n, base64.b64encode(sig).decode("ascii"))


def _phase_o0_clients() -> dict:
    return {_CLIENT_ID: (_CLIENT_SECRET, list(_PHASE_O0_SCOPES))}


# ---------------------------------------------------------------------------
# T-AA-1
# ---------------------------------------------------------------------------

def test_t_aa_1_success_path():
    """All eight steps pass → 200 with AgentIdentity payload."""
    client, _ = _build_app(clients=_phase_o0_clients())
    token = _make_token()

    # Sign GET /protected with empty body. Signing secret = OAuth client
    # secret per Decision B1-A.
    ts, nonce, sig = _sign_request("GET", _TEST_PATH, b"", _CLIENT_SECRET)

    r = client.get(
        _TEST_PATH,
        headers={
            "Authorization": f"Bearer {token}",
            "X-Agent-KeyId": _CLIENT_ID,
            "X-Timestamp":   str(ts),
            "X-Nonce":       nonce,
            "X-Signature":   sig,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["client_id"] == _CLIENT_ID
    assert body["agent_kid"] == _CLIENT_ID
    assert body["granted_scopes"] == _PHASE_O0_SCOPES


# ---------------------------------------------------------------------------
# T-AA-2
# ---------------------------------------------------------------------------

def test_t_aa_2_oauth_not_configured_returns_503():
    """Step 0: when oauth_issuer is None → 503."""
    client, _ = _build_app(clients=None)  # → issuer=None
    r = client.get(_TEST_PATH, headers={"Authorization": "Bearer anything"})
    assert r.status_code == 503
    assert "OAuth not configured" in r.json()["detail"]


# ---------------------------------------------------------------------------
# T-AA-3
# ---------------------------------------------------------------------------

def test_t_aa_3_missing_authorization_header():
    """Step 1: no Authorization → 401."""
    client, _ = _build_app(clients=_phase_o0_clients())
    r = client.get(_TEST_PATH)
    assert r.status_code == 401
    assert "Authorization" in r.json()["detail"]


# ---------------------------------------------------------------------------
# T-AA-4
# ---------------------------------------------------------------------------

def test_t_aa_4_non_bearer_authorization_scheme():
    """Step 1: Basic / Digest / etc. → 401."""
    client, _ = _build_app(clients=_phase_o0_clients())
    r = client.get(_TEST_PATH, headers={"Authorization": "Basic abc123"})
    assert r.status_code == 401
    assert "Bearer" in r.json()["detail"]


# ---------------------------------------------------------------------------
# T-AA-5
# ---------------------------------------------------------------------------

def test_t_aa_5_invalid_oauth_token():
    """Step 2: token signed with wrong secret → 401 'invalid token'."""
    client, _ = _build_app(clients=_phase_o0_clients())
    forged_token = _make_token(secret="wrong-secret")
    r = client.get(
        _TEST_PATH,
        headers={"Authorization": f"Bearer {forged_token}"},
    )
    assert r.status_code == 401
    assert "invalid token" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# T-AA-6
# ---------------------------------------------------------------------------

def test_t_aa_6_expired_oauth_token():
    """Step 2: expired token → 401 'token expired'."""
    client, _ = _build_app(clients=_phase_o0_clients())
    # Build a token whose exp is in the past
    now = int(time.time())
    payload = {
        "sub": _CLIENT_ID, "iss": "vapi-bridge-oauth",
        "aud": "vapi-bridge-agent-endpoints",
        "exp": now - 60, "iat": now - 360,
        "scope": " ".join(_PHASE_O0_SCOPES),
    }
    expired = jwt.encode(payload, _SECRET, algorithm="HS256")
    if isinstance(expired, bytes):
        expired = expired.decode("ascii")
    r = client.get(_TEST_PATH, headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401
    assert "expired" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# T-AA-7
# ---------------------------------------------------------------------------

def test_t_aa_7_token_with_wrong_scope():
    """Step 2: token granting only a different scope → 401
    'insufficient scope'.
    """
    client, _ = _build_app(clients=_phase_o0_clients())
    bad_scope_token = _make_token(scopes=["bridge:agent:other:read"])
    r = client.get(
        _TEST_PATH,
        headers={"Authorization": f"Bearer {bad_scope_token}"},
    )
    assert r.status_code == 401
    assert "scope" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# T-AA-8
# ---------------------------------------------------------------------------

def test_t_aa_8_missing_hmac_headers():
    """Step 3: each missing HMAC header listed in 401 detail."""
    client, _ = _build_app(clients=_phase_o0_clients())
    token = _make_token()
    base_headers = {"Authorization": f"Bearer {token}"}

    # Missing all four
    r = client.get(_TEST_PATH, headers=base_headers)
    assert r.status_code == 401
    detail = r.json()["detail"]
    for required in ("X-Agent-KeyId", "X-Timestamp", "X-Nonce", "X-Signature"):
        assert required in detail

    # Missing only X-Signature
    ts, nonce, _ = _sign_request("GET", _TEST_PATH, b"", _CLIENT_SECRET)
    r = client.get(
        _TEST_PATH,
        headers={
            **base_headers,
            "X-Agent-KeyId": _CLIENT_ID,
            "X-Timestamp":   str(ts),
            "X-Nonce":       nonce,
            # X-Signature omitted
        },
    )
    assert r.status_code == 401
    assert "X-Signature" in r.json()["detail"]


# ---------------------------------------------------------------------------
# T-AA-9
# ---------------------------------------------------------------------------

def test_t_aa_9_keyid_must_match_client_id():
    """Step 4: X-Agent-KeyId != OAuth sub → 401 'binding violation'."""
    client, _ = _build_app(clients=_phase_o0_clients())
    token = _make_token()
    ts, nonce, sig = _sign_request("GET", _TEST_PATH, b"", _CLIENT_SECRET)
    r = client.get(
        _TEST_PATH,
        headers={
            "Authorization": f"Bearer {token}",
            "X-Agent-KeyId": "different-agent-id",  # mismatch
            "X-Timestamp":   str(ts),
            "X-Nonce":       nonce,
            "X-Signature":   sig,
        },
    )
    assert r.status_code == 401
    assert "binding" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# T-AA-10
# ---------------------------------------------------------------------------

def test_t_aa_10_non_integer_timestamp():
    """Step 5: X-Timestamp not parseable as int → 401."""
    client, _ = _build_app(clients=_phase_o0_clients())
    token = _make_token()
    r = client.get(
        _TEST_PATH,
        headers={
            "Authorization": f"Bearer {token}",
            "X-Agent-KeyId": _CLIENT_ID,
            "X-Timestamp":   "not-a-number",
            "X-Nonce":       "n-1",
            "X-Signature":   "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        },
    )
    assert r.status_code == 401
    assert "Timestamp" in r.json()["detail"]


# ---------------------------------------------------------------------------
# T-AA-11
# ---------------------------------------------------------------------------

def test_t_aa_11_invalid_hmac_signature():
    """Step 6: tampered signature → 401 'signature invalid'."""
    client, _ = _build_app(clients=_phase_o0_clients())
    token = _make_token()
    ts, nonce, sig = _sign_request("GET", _TEST_PATH, b"", _CLIENT_SECRET)

    # Flip one base64 character of the signature
    flipped_sig = ("X" + sig[1:]) if sig[0] != "X" else ("Y" + sig[1:])
    r = client.get(
        _TEST_PATH,
        headers={
            "Authorization": f"Bearer {token}",
            "X-Agent-KeyId": _CLIENT_ID,
            "X-Timestamp":   str(ts),
            "X-Nonce":       nonce,
            "X-Signature":   flipped_sig,
        },
    )
    assert r.status_code == 401
    assert "invalid" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# T-AA-12
# ---------------------------------------------------------------------------

def test_t_aa_12_stale_timestamp_past_tolerance():
    """Step 7: timestamp 600s in the past (tolerance 300s) → 401."""
    client, _ = _build_app(clients=_phase_o0_clients())
    token = _make_token()

    stale_ts = int(time.time()) - 600
    ts, nonce, sig = _sign_request(
        "GET", _TEST_PATH, b"", _CLIENT_SECRET, timestamp=stale_ts,
    )
    r = client.get(
        _TEST_PATH,
        headers={
            "Authorization": f"Bearer {token}",
            "X-Agent-KeyId": _CLIENT_ID,
            "X-Timestamp":   str(ts),
            "X-Nonce":       nonce,
            "X-Signature":   sig,
        },
    )
    assert r.status_code == 401
    assert "stale" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# T-AA-13
# ---------------------------------------------------------------------------

def test_t_aa_13_future_timestamp_past_tolerance():
    """Step 7: timestamp 600s in the future (tolerance 300s) → 401."""
    client, _ = _build_app(clients=_phase_o0_clients())
    token = _make_token()

    future_ts = int(time.time()) + 600
    ts, nonce, sig = _sign_request(
        "GET", _TEST_PATH, b"", _CLIENT_SECRET, timestamp=future_ts,
    )
    r = client.get(
        _TEST_PATH,
        headers={
            "Authorization": f"Bearer {token}",
            "X-Agent-KeyId": _CLIENT_ID,
            "X-Timestamp":   str(ts),
            "X-Nonce":       nonce,
            "X-Signature":   sig,
        },
    )
    assert r.status_code == 401
    assert "stale" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# T-AA-14
# ---------------------------------------------------------------------------

def test_t_aa_14_replay_attack_rejected():
    """Step 8: same nonce twice within window → second attempt 401
    'replay detected'.
    """
    tracker = NonceDedupTracker(ttl_seconds=600)
    client, _ = _build_app(clients=_phase_o0_clients(), nonce_tracker=tracker)
    token = _make_token()

    ts, nonce, sig = _sign_request("GET", _TEST_PATH, b"", _CLIENT_SECRET)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Agent-KeyId": _CLIENT_ID,
        "X-Timestamp":   str(ts),
        "X-Nonce":       nonce,
        "X-Signature":   sig,
    }

    # First request: 200 (nonce registered)
    r1 = client.get(_TEST_PATH, headers=headers)
    assert r1.status_code == 200

    # Second request with SAME nonce: 401 replay
    r2 = client.get(_TEST_PATH, headers=headers)
    assert r2.status_code == 401
    assert "replay" in r2.json()["detail"].lower()


# ---------------------------------------------------------------------------
# T-AA-15
# ---------------------------------------------------------------------------

def test_t_aa_15_query_string_included_in_canonical_path():
    """Decision B4: PATH includes query string when present.

    Sign with PATH = path-only; verify against PATH = path+query →
    HMAC mismatch → 401. This catches an attacker who tries to swap
    query parameters within a valid signature window.
    """
    client, _ = _build_app(clients=_phase_o0_clients())
    token = _make_token()

    # Add a query parameter to the request URL
    request_path_with_query = f"{_TEST_PATH}?foo=bar"

    # Sign with PATH = "/protected" only (i.e., signer naively used
    # request.url.path WITHOUT query)
    ts, nonce, sig = _sign_request("GET", _TEST_PATH, b"", _CLIENT_SECRET)

    r = client.get(
        request_path_with_query,
        headers={
            "Authorization": f"Bearer {token}",
            "X-Agent-KeyId": _CLIENT_ID,
            "X-Timestamp":   str(ts),
            "X-Nonce":       nonce,
            "X-Signature":   sig,
        },
    )
    # The verifier signs against "/protected?foo=bar"; signer signed
    # against "/protected" → signature mismatch → 401
    assert r.status_code == 401
    assert "invalid" in r.json()["detail"].lower()

    # Sanity: signing with PATH = "/protected?foo=bar" succeeds
    ts2, n2, sig2 = _sign_request(
        "GET", request_path_with_query, b"", _CLIENT_SECRET,
    )
    r2 = client.get(
        request_path_with_query,
        headers={
            "Authorization": f"Bearer {token}",
            "X-Agent-KeyId": _CLIENT_ID,
            "X-Timestamp":   str(ts2),
            "X-Nonce":       n2,
            "X-Signature":   sig2,
        },
    )
    assert r2.status_code == 200, r2.text

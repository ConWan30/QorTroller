"""Phase O0 Stream 4-prep Session 1 — OAuth 2.1 client credentials issuer tests.

Verifies oauth_issuer.OAuthIssuer behavior per Pass 2C Section 5.1 +
Decisions A1, A2, A5, A6, A7. HS256 JWT format with sub/iss/aud/exp/iat/scope
claims; PyJWT for encode/decode; env-var-per-agent client credentials;
TTL bounded to 60-300 seconds.

Tests:
  T-OAUTH-1:  issue_token success — valid credentials + valid scope produce
              a JWT decodable to the same client_id and granted scope.
  T-OAUTH-2:  issue_token unknown client_id raises OAuthClientNotFound.
  T-OAUTH-3:  issue_token wrong client_secret raises OAuthValidationError
              via constant-time compare.
  T-OAUTH-4:  issue_token unauthorized scope raises OAuthInvalidScope.
  T-OAUTH-5:  issue_token with empty requested_scopes raises OAuthInvalidScope.
  T-OAUTH-6:  validate_token success — round-trip issued token and recover
              (client_id, granted_scopes).
  T-OAUTH-7:  validate_token expired token raises OAuthTokenExpired.
              Uses jwt.encode directly with exp in the past.
  T-OAUTH-8:  validate_token tampered signature raises OAuthValidationError.
  T-OAUTH-9:  validate_token wrong issuer / audience raises
              OAuthValidationError.
  T-OAUTH-10: validate_token insufficient required_scopes raises
              OAuthInvalidScope.
  T-OAUTH-11: JWT format conformance — token decodes to dict with
              required claims (sub, iss, aud, exp, iat, scope), HS256 alg.
  T-OAUTH-12: Constructor rejects empty signing secret (fail-closed).
  T-OAUTH-13: Constructor rejects ttl_seconds outside [60, 300] per
              Pass 2C Section 5.1 line 713.
  T-OAUTH-14: Config.get_oauth_clients reads env vars correctly: SENTRY
              and GUARDIAN env-var pairs map to dict entries with the
              Phase O0 read scope.
"""
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import jwt  # type: ignore[import-untyped]

from vapi_bridge.oauth_issuer import (  # noqa: E402
    OAuthIssuer,
    OAuthValidationError,
    OAuthClientNotFound,
    OAuthInvalidScope,
    OAuthTokenExpired,
)


# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

_SECRET = "test-issuer-signing-secret-32-bytes-min"
_CLIENT_ID = "vapi-anchor-sentry"
_CLIENT_SECRET = "sentry-shared-secret-not-real"
_PHASE_O0_SCOPES = ["bridge:agent:phases:read"]


def _make_issuer(ttl_seconds: int = 300) -> OAuthIssuer:
    return OAuthIssuer(
        secret=_SECRET,
        clients={_CLIENT_ID: (_CLIENT_SECRET, list(_PHASE_O0_SCOPES))},
        ttl_seconds=ttl_seconds,
    )


# ---------------------------------------------------------------------------
# T-OAUTH-1
# ---------------------------------------------------------------------------

def test_t_oauth_1_issue_token_success():
    """Valid credentials + valid scope mint a JWT carrying the same
    client_id and scope; token_type and expires_in match issuer config.
    """
    issuer = _make_issuer(ttl_seconds=300)
    token, token_type, expires_in, scope = issuer.issue_token(
        _CLIENT_ID, _CLIENT_SECRET, _PHASE_O0_SCOPES,
    )
    assert isinstance(token, str)
    assert token_type == "Bearer"
    assert expires_in == 300
    assert scope == "bridge:agent:phases:read"

    # Round-trip verifies all claims independently (no validate_token use).
    payload = jwt.decode(
        token, _SECRET, algorithms=["HS256"],
        audience="vapi-bridge-agent-endpoints",
        issuer="vapi-bridge-oauth",
    )
    assert payload["sub"] == _CLIENT_ID
    assert payload["scope"] == "bridge:agent:phases:read"


# ---------------------------------------------------------------------------
# T-OAUTH-2
# ---------------------------------------------------------------------------

def test_t_oauth_2_unknown_client_id_raises():
    """Unregistered client_id triggers OAuthClientNotFound."""
    issuer = _make_issuer()
    with pytest.raises(OAuthClientNotFound, match="unknown client_id"):
        issuer.issue_token("nonexistent-client", "any-secret", _PHASE_O0_SCOPES)


# ---------------------------------------------------------------------------
# T-OAUTH-3
# ---------------------------------------------------------------------------

def test_t_oauth_3_wrong_client_secret_raises():
    """Wrong client_secret triggers OAuthValidationError (NOT
    OAuthClientNotFound — the client exists but failed to authenticate).
    """
    issuer = _make_issuer()
    with pytest.raises(OAuthValidationError, match="client_secret mismatch"):
        issuer.issue_token(_CLIENT_ID, "wrong-secret", _PHASE_O0_SCOPES)


# ---------------------------------------------------------------------------
# T-OAUTH-4
# ---------------------------------------------------------------------------

def test_t_oauth_4_unauthorized_scope_raises():
    """Requesting a scope not in the client's authorized_scopes triggers
    OAuthInvalidScope. Phase O0 client only has 'bridge:agent:phases:read'.
    """
    issuer = _make_issuer()
    with pytest.raises(OAuthInvalidScope, match="not authorized"):
        issuer.issue_token(
            _CLIENT_ID,
            _CLIENT_SECRET,
            ["bridge:agent:agent-commit:write"],  # not in Phase O0
        )


# ---------------------------------------------------------------------------
# T-OAUTH-5
# ---------------------------------------------------------------------------

def test_t_oauth_5_empty_requested_scopes_raises():
    """Empty requested_scopes triggers OAuthInvalidScope (must request at
    least one scope to mint a useful token).
    """
    issuer = _make_issuer()
    with pytest.raises(OAuthInvalidScope, match="non-empty"):
        issuer.issue_token(_CLIENT_ID, _CLIENT_SECRET, [])


# ---------------------------------------------------------------------------
# T-OAUTH-6
# ---------------------------------------------------------------------------

def test_t_oauth_6_validate_token_success():
    """Issued token round-trips through validate_token to recover the
    same (client_id, granted_scopes).
    """
    issuer = _make_issuer()
    token, _, _, _ = issuer.issue_token(_CLIENT_ID, _CLIENT_SECRET, _PHASE_O0_SCOPES)
    client_id, granted_scopes = issuer.validate_token(token)
    assert client_id == _CLIENT_ID
    assert granted_scopes == _PHASE_O0_SCOPES


# ---------------------------------------------------------------------------
# T-OAUTH-7
# ---------------------------------------------------------------------------

def test_t_oauth_7_expired_token_raises():
    """A token with exp in the past triggers OAuthTokenExpired (not
    generic OAuthValidationError; expiration is a distinguished failure
    mode for caller diagnostics).
    """
    issuer = _make_issuer()
    # Build a token with exp in the past.
    payload = {
        "sub":   _CLIENT_ID,
        "iss":   "vapi-bridge-oauth",
        "aud":   "vapi-bridge-agent-endpoints",
        "exp":   int(time.time()) - 60,  # 60s ago
        "iat":   int(time.time()) - 360,
        "scope": "bridge:agent:phases:read",
    }
    expired_token = jwt.encode(payload, _SECRET, algorithm="HS256")
    if isinstance(expired_token, bytes):
        expired_token = expired_token.decode("ascii")
    with pytest.raises(OAuthTokenExpired):
        issuer.validate_token(expired_token)


# ---------------------------------------------------------------------------
# T-OAUTH-8
# ---------------------------------------------------------------------------

def test_t_oauth_8_tampered_signature_raises():
    """A token signed with a different secret triggers OAuthValidationError."""
    issuer = _make_issuer()
    payload = {
        "sub":   _CLIENT_ID,
        "iss":   "vapi-bridge-oauth",
        "aud":   "vapi-bridge-agent-endpoints",
        "exp":   int(time.time()) + 300,
        "iat":   int(time.time()),
        "scope": "bridge:agent:phases:read",
    }
    forged = jwt.encode(payload, "wrong-secret", algorithm="HS256")
    if isinstance(forged, bytes):
        forged = forged.decode("ascii")
    with pytest.raises(OAuthValidationError):
        issuer.validate_token(forged)


# ---------------------------------------------------------------------------
# T-OAUTH-9
# ---------------------------------------------------------------------------

def test_t_oauth_9_wrong_issuer_audience_raises():
    """Tokens with a different iss or aud trigger OAuthValidationError
    (PyJWT's InvalidIssuerError / InvalidAudienceError both subclass
    InvalidTokenError).
    """
    issuer = _make_issuer()

    # Wrong audience
    payload_a = {
        "sub": _CLIENT_ID, "iss": "vapi-bridge-oauth",
        "aud": "wrong-audience", "exp": int(time.time()) + 300,
        "iat": int(time.time()), "scope": "bridge:agent:phases:read",
    }
    bad_aud = jwt.encode(payload_a, _SECRET, algorithm="HS256")
    if isinstance(bad_aud, bytes):
        bad_aud = bad_aud.decode("ascii")
    with pytest.raises(OAuthValidationError):
        issuer.validate_token(bad_aud)

    # Wrong issuer
    payload_i = {
        "sub": _CLIENT_ID, "iss": "wrong-issuer",
        "aud": "vapi-bridge-agent-endpoints", "exp": int(time.time()) + 300,
        "iat": int(time.time()), "scope": "bridge:agent:phases:read",
    }
    bad_iss = jwt.encode(payload_i, _SECRET, algorithm="HS256")
    if isinstance(bad_iss, bytes):
        bad_iss = bad_iss.decode("ascii")
    with pytest.raises(OAuthValidationError):
        issuer.validate_token(bad_iss)


# ---------------------------------------------------------------------------
# T-OAUTH-10
# ---------------------------------------------------------------------------

def test_t_oauth_10_insufficient_required_scopes_raises():
    """A token granting only Phase O0 scopes fails the required_scopes
    check when callers require an additional scope.
    """
    issuer = _make_issuer()
    token, _, _, _ = issuer.issue_token(_CLIENT_ID, _CLIENT_SECRET, _PHASE_O0_SCOPES)
    with pytest.raises(OAuthInvalidScope, match="does not grant required"):
        issuer.validate_token(
            token, required_scopes=["bridge:agent:agent-commit:write"],
        )

    # Sanity: required = subset → no raise
    client_id, _ = issuer.validate_token(
        token, required_scopes=["bridge:agent:phases:read"],
    )
    assert client_id == _CLIENT_ID


# ---------------------------------------------------------------------------
# T-OAUTH-11
# ---------------------------------------------------------------------------

def test_t_oauth_11_jwt_format_conformance():
    """Issued token decodes to a payload dict carrying all six required
    claims; header announces alg=HS256 per Decision A2.
    """
    issuer = _make_issuer(ttl_seconds=120)
    token, _, _, _ = issuer.issue_token(_CLIENT_ID, _CLIENT_SECRET, _PHASE_O0_SCOPES)

    # Inspect header WITHOUT signature verification
    header = jwt.get_unverified_header(token)
    assert header["alg"] == "HS256"
    assert header["typ"] == "JWT"

    # Inspect payload claims (use _SECRET so signature verifies)
    payload = jwt.decode(
        token, _SECRET, algorithms=["HS256"],
        audience="vapi-bridge-agent-endpoints",
        issuer="vapi-bridge-oauth",
    )
    for claim in ("sub", "iss", "aud", "exp", "iat", "scope"):
        assert claim in payload, f"missing claim: {claim}"
    assert payload["iss"] == "vapi-bridge-oauth"
    assert payload["aud"] == "vapi-bridge-agent-endpoints"
    # exp should be exactly iat + ttl_seconds
    assert payload["exp"] - payload["iat"] == 120


# ---------------------------------------------------------------------------
# T-OAUTH-12
# ---------------------------------------------------------------------------

def test_t_oauth_12_constructor_rejects_empty_secret():
    """Empty signing secret would mint forgeable tokens. Fail-closed at
    construction.
    """
    with pytest.raises(ValueError, match="non-empty"):
        OAuthIssuer(secret="", clients={})


# ---------------------------------------------------------------------------
# T-OAUTH-13
# ---------------------------------------------------------------------------

def test_t_oauth_13_constructor_rejects_ttl_outside_60_300():
    """Pass 2C Section 5.1 line 713 freezes TTL range to [60, 300] seconds.
    """
    # Below range
    with pytest.raises(ValueError, match="60..300"):
        OAuthIssuer(secret=_SECRET, clients={}, ttl_seconds=30)
    # Above range
    with pytest.raises(ValueError, match="60..300"):
        OAuthIssuer(secret=_SECRET, clients={}, ttl_seconds=3600)
    # Boundaries are accepted
    OAuthIssuer(secret=_SECRET, clients={}, ttl_seconds=60)
    OAuthIssuer(secret=_SECRET, clients={}, ttl_seconds=300)


# ---------------------------------------------------------------------------
# T-OAUTH-14
# ---------------------------------------------------------------------------

def test_t_oauth_14_config_get_oauth_clients_reads_env(monkeypatch):
    """Config.get_oauth_clients reads OAUTH_CLIENT_ID_<AGENT> /
    OAUTH_CLIENT_SECRET_<AGENT> env-var pairs for SENTRY and GUARDIAN
    and returns a dict {client_id: (secret, [phase_o0_scope])}. Agents
    missing either env var are silently omitted.
    """
    from vapi_bridge.config import Config

    # Both pairs set
    monkeypatch.setenv("OAUTH_CLIENT_ID_SENTRY", "sentry-id-test")
    monkeypatch.setenv("OAUTH_CLIENT_SECRET_SENTRY", "sentry-sec-test")
    monkeypatch.setenv("OAUTH_CLIENT_ID_GUARDIAN", "guardian-id-test")
    monkeypatch.setenv("OAUTH_CLIENT_SECRET_GUARDIAN", "guardian-sec-test")

    cfg = Config()
    clients = cfg.get_oauth_clients()
    assert "sentry-id-test" in clients
    assert "guardian-id-test" in clients
    sec, scopes = clients["sentry-id-test"]
    assert sec == "sentry-sec-test"
    assert scopes == ["bridge:agent:phases:read"]

    # Missing GUARDIAN secret → only SENTRY in dict
    monkeypatch.delenv("OAUTH_CLIENT_SECRET_GUARDIAN")
    clients2 = cfg.get_oauth_clients()
    assert "sentry-id-test" in clients2
    assert "guardian-id-test" not in clients2

    # Both unset → empty dict (issue_token will raise OAuthClientNotFound)
    monkeypatch.delenv("OAUTH_CLIENT_ID_SENTRY")
    monkeypatch.delenv("OAUTH_CLIENT_SECRET_SENTRY")
    monkeypatch.delenv("OAUTH_CLIENT_ID_GUARDIAN")
    clients3 = cfg.get_oauth_clients()
    assert clients3 == {}

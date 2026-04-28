"""Phase O0 Stream 4-prep Session 1 — OAuth 2.1 client credentials issuer.

Mints HS256 JWT access tokens for VAPI's Operator Agents (vapi-anchor-sentry,
vapi-guardian) per OAuth 2.1 client credentials grant (RFC 6749 Section 4.4
with OAuth 2.1 hardening per draft-ietf-oauth-v2-1-09). Tokens authenticate
agent requests to the bridge's /agent/* endpoints; HMAC request signing
(see hmac_middleware.py) provides per-request integrity on top of the token.

Origin and design lineage:

  Pass 2A V2 Option B (architectural-details document) selected the OAuth 2.1
    client credentials + HMAC request signing combination over mTLS via
    SPIFFE/SPIRE for Phase O0. mTLS deferred to P3+ when KMS infrastructure
    matures for git signing keys.

  Pass 2C Section 5.1 (commit b9ddeeb2) ratified the implementation path:
    HS256 JWT token format with sub/iss/aud/exp/iat/scope claims, env-var
    per-agent client credentials, in-process token issuer module hosting
    (Pass 2C Q1 Option A — module within the existing bridge process,
    sharing the asyncio event loop). Process isolation deferred to P3+.

  Stream 4-prep Session 1 ships oauth_issuer.py + hmac_middleware.py as
    standalone authentication primitives. Session 2 wires them into bridge
    /agent/* endpoints via the FastAPI Depends(_check_agent_token) pattern
    (Pass 2C Section 5.1 lines 765-785). The two-session split keeps the
    auth primitives reviewable independently of endpoint integration.

  Decision A1 (Stream 4-prep Session 1) confirmed the two-module file
    structure (oauth_issuer.py + hmac_middleware.py) over Pass 2C's literal
    single-file `agent_auth.py` name. The functional split — issuance vs
    verification primitives — matches Pass 2C's intent; the FastAPI
    dependency that Pass 2C names `agent_auth.py` is integration glue and
    belongs in Session 2 per the operator's two-session scoping.

  Decision A2 (Stream 4-prep Session 1) confirmed HS256 JWT token format
    per Pass 2C Section 5.1 line 706-707. RS256 deferred to P3+.

  Decision A5 (Stream 4-prep Session 1) confirmed token TTL = 300 seconds
    (top of Pass 2C's "60-300 seconds per architecture document" range).

  Decision A6 (Stream 4-prep Session 1) confirmed env-var-per-agent client
    credentials storage (OAUTH_CLIENT_ID_<AGENT> / OAUTH_CLIENT_SECRET_<AGENT>)
    matching the existing OPERATOR_API_KEY pattern. No registry-file
    pattern is introduced.

  Decision A7 (Stream 4-prep Session 1) confirmed PyJWT (already a
    transitive dependency at version 2.10.1) for jwt.encode/jwt.decode
    with audience and issuer validation. Custom stdlib HS256 JWT was
    rejected as an unnecessary security-sensitive reinvention; PyJWT's
    constant-time signature compare and battle-tested edge-case handling
    are load-bearing properties.

JWT format (HS256, per Pass 2C Section 5.1 lines 709-716):

    payload = {
        "sub":   agent_id,                          // bytes32 hex (matches AgentRegistry)
        "iss":   "vapi-bridge-oauth",               // FROZEN per Pass 2C
        "aud":   "vapi-bridge-agent-endpoints",     // FROZEN per Pass 2C
        "exp":   issued_at + ttl_seconds,           // 300s default per Decision A5
        "iat":   issued_at,
        "scope": "scope1 scope2 ...",               // space-separated per RFC 6749
    }

    access_token = base64url(header) "." base64url(payload) "." base64url(HMAC-SHA256(...))

Phase O0 scope vocabulary (Pass 2C Section 5.1 line 801):

    "bridge:agent:phases:read"   — read-only access to /agent/* status +
                                    history endpoints (the 5 endpoints
                                    listed in Pass 2C lines 794-799)

    Write scopes (e.g., bridge:agent:agent-commit:write,
    bridge:agent:pda:write) deferred to P1+ when agents gain write
    authority. Phase O0 ships read-only scope only.

Authentication is OPERATIONAL infrastructure, NOT a FROZEN-v1 primitive.
The auth code may evolve across phases (token format changes, scope
vocabulary expansion, library upgrades) without breaking the protocol's
cryptographic commitments. No PV-CI invariants pin this module's surface.
"""
from __future__ import annotations

import hmac
import time
from typing import Optional

# PyJWT 2.10.1+ — already a transitive dep via the web3/eth stack.
# Decision A7: prefer battle-tested library over custom HS256 implementation.
import jwt  # type: ignore[import-untyped]


# Frozen JWT claim values per Pass 2C Section 5.1.
_JWT_ALGORITHM = "HS256"
_DEFAULT_ISSUER = "vapi-bridge-oauth"
_DEFAULT_AUDIENCE = "vapi-bridge-agent-endpoints"
_DEFAULT_TTL_SECONDS = 300  # Decision A5: top of Pass 2C's 60-300s range


# -----------------------------------------------------------------------
# Custom exceptions
# -----------------------------------------------------------------------

class OAuthValidationError(Exception):
    """Generic OAuth validation failure — invalid credentials, bad token."""


class OAuthClientNotFound(OAuthValidationError):
    """The provided client_id is not registered in the issuer's client map."""


class OAuthInvalidScope(OAuthValidationError):
    """Requested or token scope does not satisfy the policy check."""


class OAuthTokenExpired(OAuthValidationError):
    """Token's exp claim is in the past."""


# -----------------------------------------------------------------------
# OAuthIssuer
# -----------------------------------------------------------------------

class OAuthIssuer:
    """In-process OAuth 2.1 client credentials issuer + verifier.

    Per Pass 2C Q1 Option A: runs as a module within the existing bridge
    process, sharing the asyncio event loop. Process isolation through a
    separate service is deferred to P3+ when agents gain write authority.

    Construction:

        issuer = OAuthIssuer(
            secret="<HS256 signing key, OAUTH_ISSUER_SECRET env>",
            issuer="vapi-bridge-oauth",        # default; FROZEN per Pass 2C
            audience="vapi-bridge-agent-endpoints",  # default; FROZEN
            ttl_seconds=300,                   # default per Decision A5
            clients={
                "<client_id>": ("<client_secret>", ["<scope1>", "<scope2>", ...]),
                ...
            },
        )

    Mint and validate:

        access_token, token_type, expires_in, scope = issuer.issue_token(
            client_id, client_secret, requested_scopes,
        )

        client_id, granted_scopes = issuer.validate_token(
            access_token, required_scopes,
        )

    Both methods raise OAuth*Error on failure; callers should translate
    to HTTP 401 responses at the FastAPI dependency boundary (Session 2).
    """

    def __init__(
        self,
        secret: str,
        clients: "dict[str, tuple[str, list[str]]]",
        issuer: str = _DEFAULT_ISSUER,
        audience: str = _DEFAULT_AUDIENCE,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    ) -> None:
        if not secret:
            # An empty signing secret would mint forgeable tokens. Fail
            # closed at construction so misconfiguration cannot silently
            # disable auth.
            raise ValueError("OAuthIssuer requires a non-empty signing secret")
        if not (60 <= int(ttl_seconds) <= 300):
            # Pass 2C Section 5.1 line 713 freezes the TTL range.
            raise ValueError(
                f"ttl_seconds must be in 60..300 per Pass 2C, got {ttl_seconds}"
            )
        self._secret = secret
        self._issuer = issuer
        self._audience = audience
        self._ttl_seconds = int(ttl_seconds)
        self._clients = dict(clients)  # shallow copy so caller mutation is benign

    @property
    def ttl_seconds(self) -> int:
        return self._ttl_seconds

    def issue_token(
        self,
        client_id: str,
        client_secret: str,
        requested_scopes: "list[str]",
    ) -> "tuple[str, str, int, str]":
        """Mint an HS256 JWT access token.

        Returns (access_token, token_type="Bearer", expires_in, scope).
        scope is the space-separated string of granted scopes (= the
        intersection of requested with the client's authorized scopes;
        in Phase O0 this is the same as requested_scopes when valid,
        since requested_scopes is required to be a subset).

        Raises:
            OAuthClientNotFound:    client_id is not in the registered
                                    clients map.
            OAuthValidationError:   client_secret does not match the
                                    registered secret (constant-time
                                    compare).
            OAuthInvalidScope:      requested_scopes contains a scope
                                    the client is not authorized for,
                                    OR requested_scopes is empty.
        """
        if client_id not in self._clients:
            raise OAuthClientNotFound(f"unknown client_id: {client_id}")

        registered_secret, allowed_scopes = self._clients[client_id]

        # Constant-time compare to defeat timing oracles on the secret.
        if not hmac.compare_digest(client_secret, registered_secret):
            raise OAuthValidationError("client_secret mismatch")

        if not requested_scopes:
            raise OAuthInvalidScope("requested_scopes must be non-empty")

        # All requested scopes must be in the client's allowed_scopes.
        allowed_set = set(allowed_scopes)
        unauthorized = [s for s in requested_scopes if s not in allowed_set]
        if unauthorized:
            raise OAuthInvalidScope(
                f"client {client_id} is not authorized for scopes: {unauthorized}"
            )

        now = int(time.time())
        payload = {
            "sub":   client_id,
            "iss":   self._issuer,
            "aud":   self._audience,
            "exp":   now + self._ttl_seconds,
            "iat":   now,
            "scope": " ".join(requested_scopes),
        }
        access_token = jwt.encode(payload, self._secret, algorithm=_JWT_ALGORITHM)
        # PyJWT 2.x returns str directly; bytes-handling guard for older
        # PyJWT versions in case a stale install slips through CI.
        if isinstance(access_token, bytes):
            access_token = access_token.decode("ascii")
        return (access_token, "Bearer", self._ttl_seconds, " ".join(requested_scopes))

    def validate_token(
        self,
        access_token: str,
        required_scopes: "Optional[list[str]]" = None,
    ) -> "tuple[str, list[str]]":
        """Verify an HS256 JWT access token and return (client_id, granted_scopes).

        Validates signature, issuer, audience, and expiration. If
        required_scopes is provided, also enforces required ⊆ granted.

        Raises:
            OAuthTokenExpired:    exp claim is in the past.
            OAuthValidationError: signature / issuer / audience invalid,
                                  or token is malformed.
            OAuthInvalidScope:    required_scopes is not a subset of the
                                  token's granted scopes.
        """
        try:
            payload = jwt.decode(
                access_token,
                self._secret,
                algorithms=[_JWT_ALGORITHM],
                audience=self._audience,
                issuer=self._issuer,
            )
        except jwt.ExpiredSignatureError as exc:
            raise OAuthTokenExpired(str(exc)) from exc
        except jwt.InvalidTokenError as exc:
            # Catches InvalidSignatureError, InvalidAudienceError,
            # InvalidIssuerError, DecodeError, and any other PyJWT failure.
            raise OAuthValidationError(str(exc)) from exc

        client_id = payload.get("sub")
        if not client_id:
            raise OAuthValidationError("token missing sub claim")

        scope_claim = payload.get("scope", "")
        granted_scopes = scope_claim.split() if scope_claim else []

        if required_scopes:
            granted_set = set(granted_scopes)
            insufficient = [s for s in required_scopes if s not in granted_set]
            if insufficient:
                raise OAuthInvalidScope(
                    f"token does not grant required scopes: {insufficient}"
                )

        return (str(client_id), granted_scopes)

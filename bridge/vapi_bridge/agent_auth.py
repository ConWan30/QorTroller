"""Phase O0 Stream 4-prep Session 2 — agent_auth.py FastAPI dependency.

Composes oauth_issuer.py (HS256 JWT validation) and hmac_middleware.py
(per-request HMAC-SHA256 verification) into a single FastAPI dependency
`_check_agent_token` that gates the five Phase O0 read-only /agent/*
endpoints listed in Pass 2C Section 5.1 lines 794-799.

Origin and design lineage:

  Pass 2A V2 Option B selected OAuth 2.1 + HMAC over mTLS. Stream 4-prep
    Session 1 (commit 038740d2) shipped the protocol-level primitives.
    This Session 2 module is the integration glue.

  Pass 2C Section 5.1 lines 765-785 specifies the per-endpoint
    annotation pattern: `auth: dict = Depends(_check_agent_token)`.
    Failure of either OAuth or HMAC verification → HTTP 401.

  Decision B1-A (Stream 4-prep Session 2) confirmed dual-purpose
    secret usage: OAUTH_CLIENT_SECRET_<AGENT> serves BOTH as the OAuth
    client secret (used at token-mint time) AND as the HMAC signing
    secret (used at per-request signing time). Single secret per
    agent. Cryptographic binding via X-Agent-KeyId == OAuth token sub
    claim ensures the OAuth and HMAC layers cannot be desynchronized
    (an attacker holding only one of the two cannot mount a partial
    attack).

  Decision B2 (Stream 4-prep Session 2) added agent_registry_address
    config field (deferred-activation pattern) so /agent/agent-registry-status
    can return a coherent response before AgentRegistry is deployed.

  Decision B3 (Stream 4-prep Session 2) corrected the Session 2
    prompt's truncated endpoint paths (/agent/commit-history etc.)
    back to Pass 2C's locked specification with the agent- prefix
    (/agent/agent-commit-history, /agent/agent-registry-status).

  Decision B4 (Stream 4-prep Session 2) resolved a Pass 2C ambiguity
    on the canonical request's PATH content toward security: PATH
    includes query string when present. Both signer and verifier use:

        path = request.url.path + ("?" + request.url.query if request.url.query else "")

    Without query inclusion, an attacker holding a valid signature in
    the ±300s window could swap query parameters (e.g.,
    ?commit_hash=...) without invalidating the HMAC, mounting a
    read-data-tampering attack. With query inclusion, every URL
    variation requires its own signature. See compute_canonical_request
    in hmac_middleware.py for the field-order contract.

Validation sequence (FROZEN order — fail-closed at the earliest
detectable error so callers get the most-specific 401 message):

  Step 0:  OAuth not configured → 503 (mirrors _check_key pattern;
           bridge dev environments without auth setup work without
           crashing on agent-token requests).
  Step 1:  Authorization header present and well-formed (Bearer scheme).
  Step 2:  OAuth token validates with required scope
           bridge:agent:phases:read.
  Step 3:  All four HMAC headers present (X-Agent-KeyId, X-Timestamp,
           X-Nonce, X-Signature).
  Step 4:  X-Agent-KeyId == OAuth token sub (B1-A binding).
  Step 5:  X-Timestamp parses to integer Unix seconds.
  Step 6:  HMAC signature verifies against compute_canonical_request
           output using the agent's secret.
  Step 7:  Timestamp within ±cfg.hmac_timestamp_tolerance_seconds (300s
           default per Decision A4).
  Step 8:  Nonce not in dedup tracker (600s default window per Decision A4).

  Any failure raises HTTPException(401) with a specific error message
  for caller diagnostics. Step 0 raises HTTPException(503) because
  the bridge cannot honor any agent token at all in that state.

Authentication is OPERATIONAL infrastructure, NOT a FROZEN-v1 primitive.
This module's surface is not pinned by PV-CI invariants and may evolve
across phases.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from fastapi import Header, HTTPException, Request

from .hmac_middleware import (
    NonceDedupTracker,
    check_timestamp_freshness,
    compute_canonical_request,
    verify_hmac,
    HmacInvalidSignature,
    HmacReplayDetected,
    HmacStaleTimestamp,
)
from .oauth_issuer import (
    OAuthIssuer,
    OAuthClientNotFound,
    OAuthInvalidScope,
    OAuthTokenExpired,
    OAuthValidationError,
)


# Phase O0 hardcoded scope per Pass 2C Section 5.1 line 801.
_PHASE_O0_REQUIRED_SCOPE = "bridge:agent:phases:read"


@dataclass(slots=True)
class AgentIdentity:
    """Validated agent context returned by _check_agent_token on success.

    Fields:
      client_id:        OAuth token's sub claim (= AgentRegistry agentId
                        hex when populated by the issuer at mint time).
      agent_kid:        X-Agent-KeyId header value (verified == client_id).
      granted_scopes:   List of scopes the token was issued with.
    """
    client_id: str
    agent_kid: str
    granted_scopes: list = field(default_factory=list)


def make_check_agent_token(
    oauth_issuer: "OAuthIssuer | None",
    oauth_clients: "dict[str, tuple[str, list[str]]]",
    nonce_tracker: NonceDedupTracker,
    timestamp_tolerance_seconds: int = 300,
) -> Callable:
    """Build the FastAPI dependency callable.

    The factory pattern keeps agent_auth.py testable without spinning up
    the full bridge: tests can construct a tiny FastAPI app, instantiate
    OAuthIssuer + NonceDedupTracker directly, and inject them via this
    factory.

    Args:
        oauth_issuer:   OAuthIssuer instance, or None if OAuth is not
                        configured (cfg.oauth_issuer_secret empty OR
                        cfg.get_oauth_clients() returned empty). When
                        None, the dependency raises 503 on every call.
        oauth_clients:  The same {client_id: (secret, scopes)} dict
                        that was used to construct the OAuthIssuer.
                        Used to look up the per-agent HMAC signing
                        secret (Decision B1-A: same secret for both
                        OAuth and HMAC layers).
        nonce_tracker:  NonceDedupTracker shared across requests.
        timestamp_tolerance_seconds:  Passed to check_timestamp_freshness.

    Returns:
        An async function suitable as a FastAPI Depends(...) target.
    """

    async def _check_agent_token(
        request: Request,
        authorization: str = Header(default=""),
        x_agent_keyid: str = Header(default="", alias="x-agent-keyid"),
        x_timestamp: str = Header(default="", alias="x-timestamp"),
        x_nonce: str = Header(default="", alias="x-nonce"),
        x_signature: str = Header(default="", alias="x-signature"),
    ) -> AgentIdentity:
        # Step 0: OAuth configured?
        if oauth_issuer is None:
            raise HTTPException(
                503,
                "OAuth not configured — set OAUTH_ISSUER_SECRET and at least one "
                "OAUTH_CLIENT_ID_<AGENT> / OAUTH_CLIENT_SECRET_<AGENT> pair",
            )

        # Step 1: Authorization header well-formed
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                401,
                "missing or malformed Authorization header (expected 'Bearer <token>')",
            )
        token = authorization[len("Bearer "):].strip()
        if not token:
            raise HTTPException(401, "empty Bearer token")

        # Step 2: OAuth token validates with required scope
        try:
            client_id, granted_scopes = oauth_issuer.validate_token(
                token, required_scopes=[_PHASE_O0_REQUIRED_SCOPE],
            )
        except OAuthTokenExpired as exc:
            raise HTTPException(401, f"token expired: {exc}")
        except OAuthInvalidScope as exc:
            raise HTTPException(401, f"insufficient scope: {exc}")
        except OAuthValidationError as exc:
            raise HTTPException(401, f"invalid token: {exc}")

        # Step 3: HMAC headers all present
        missing = [
            name for name, value in (
                ("X-Agent-KeyId", x_agent_keyid),
                ("X-Timestamp",   x_timestamp),
                ("X-Nonce",       x_nonce),
                ("X-Signature",   x_signature),
            ) if not value
        ]
        if missing:
            raise HTTPException(
                401, f"missing HMAC headers: {', '.join(missing)}",
            )

        # Step 4: X-Agent-KeyId == OAuth token sub (Decision B1-A binding)
        if x_agent_keyid != client_id:
            raise HTTPException(
                401,
                "X-Agent-KeyId does not match OAuth token sub claim "
                "(OAuth/HMAC layer binding violation)",
            )

        # Step 5: parse X-Timestamp
        try:
            timestamp = int(x_timestamp)
        except ValueError:
            raise HTTPException(
                401, "X-Timestamp must be integer Unix seconds",
            )

        # Step 6 lookup: HMAC secret keyed by client_id (Decision B1-A:
        # same secret as OAuth client_secret).
        client_entry = oauth_clients.get(client_id)
        if client_entry is None:
            # Defense in depth: should not happen if OAuth validate_token
            # succeeded, but guards against drift between issuer's
            # internal client map and the dict passed to this factory.
            raise HTTPException(
                401, f"client_id {client_id} not in clients registry",
            )
        hmac_secret = client_entry[0]

        # Step 6: build canonical request (Decision B4: PATH includes query)
        body_bytes = await request.body()
        path = request.url.path
        if request.url.query:
            path = path + "?" + request.url.query
        canonical = compute_canonical_request(
            method=request.method,
            path=path,
            timestamp=timestamp,
            nonce=x_nonce,
            body_bytes=body_bytes,
        )

        # Step 6 verify
        try:
            verify_hmac(x_signature, canonical, hmac_secret)
        except HmacInvalidSignature as exc:
            raise HTTPException(401, f"HMAC signature invalid: {exc}")

        # Step 7: timestamp freshness (±tolerance both directions)
        try:
            check_timestamp_freshness(
                timestamp, tolerance_seconds=timestamp_tolerance_seconds,
            )
        except HmacStaleTimestamp as exc:
            raise HTTPException(401, f"stale timestamp: {exc}")

        # Step 8: nonce dedup (600s default window)
        try:
            nonce_tracker.check_and_register(x_nonce)
        except HmacReplayDetected as exc:
            raise HTTPException(401, f"replay detected: {exc}")

        # All eight steps passed — request is authenticated.
        return AgentIdentity(
            client_id=client_id,
            agent_kid=x_agent_keyid,
            granted_scopes=list(granted_scopes),
        )

    return _check_agent_token

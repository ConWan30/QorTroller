"""Phase O0 Stream 5-prep Session 2 — IPFS pinning (Pinata) for DID documents.

Pins populated VAPI Operator Agent DID documents to IPFS via Pinata's
commercial pinning service. Phase O0 invokes this module during Section
6.4 agent registration: after the operator runs ioIDRegistry.mint() to
generate the agent's `did:io:<address>`, the DID document template
(Stream 5-prep Session 1, commit 1457dec2) is populated with real values
(address, pubkey, agentId, TBA address, ISO8601 createdAt) and pinned
here. The resulting IPFS hash is recorded in AgentRegistry's
ipfs_did_uri field at registerAgent() time.

Origin and design lineage:

  Pass 2C Q7 (operator approved 2026-04-27): Pinata commercial
    service over Web3.storage and self-hosted IPFS node alternatives.
    Per-pin cost ~$0.001 USD; reliability over the alternatives at
    Phase O0 scale (2 agents → 2 pins). Self-hosting deferred to P3+
    if operational scale justifies. Pin URLs are recorded for audit
    reproducibility per Pass 2C line 1505.

  Pass 2C Section 6.1 lines 1022-1046 specifies the DID document
    JSON-LD structure. This module is the generic JSON pinner; it
    accepts any dict (the DID document being one specific case) and
    pins it. The DID-document-specific population happens upstream
    in Phase O0 Section 6.4 work.

  Decision D1-A (Stream 5-prep Session 2): Bearer JWT credential
    storage. Single PINATA_JWT env var matching OPERATOR_API_KEY
    single-secret pattern. Empty JWT triggers
    IpfsCredentialsNotConfigured before any HTTP call (deferred-
    activation pattern matching Stream 3-prep chain wrappers and
    Stream 4-prep OAuth issuer).

  Decision D2 (Stream 5-prep Session 2): urllib.request from stdlib
    over httpx/requests. Matches one-off external service caller
    precedent (alert_router.py, ioswarm_live_node_client.py). No new
    dependency. Synchronous interface is appropriate for the one-off
    setup operation (NOT in any asyncio hot path).

  Decision D3 acknowledged: Pinata API request body uses
    `pinataContent` for the document and `pinataMetadata.name` for
    audit-relevant labels (e.g., "vapi-anchor-sentry-did"). Pin
    metadata names match the agent definition file basename so
    operators auditing Pinata pin records can cross-reference against
    the .claude/agents/ directory.

  Decision D4 acknowledged: tests monkeypatch urllib.request.urlopen
    for controlled responses covering success, 401, 429, 500, URLError,
    JSONDecodeError, and invalid-input paths. No real Pinata API calls
    occur in the test suite per the critical constraint.

Pinata API contract:

  POST https://api.pinata.cloud/pinning/pinJSONToIPFS
  Headers:
    Authorization: Bearer <JWT>
    Content-Type: application/json
  Body:
    {
      "pinataContent":  <the JSON document to pin>,
      "pinataMetadata": {"name": "<audit label>"}
    }
  Success response (HTTP 200):
    {
      "IpfsHash":  "Qm...",       (CID v0 base58)
      "PinSize":   <int bytes>,
      "Timestamp": "<ISO 8601>"
    }

  Error responses follow standard HTTP semantics: 401/403 for auth
  failures, 429 for rate limiting (Retry-After header may be set),
  5xx for Pinata server errors.

Phase O0 status:

  Module ships as an importable Phase O0 primitive. Real pins occur
  only when the operator runs the registration sequence in Section
  6.4 work — that is gated on Stream 2-deploy landing AgentRegistry
  on IoTeX testnet (wallet >= 3 IOTX per Pass 2A V8; current 0.5525
  IOTX, deferred). Until then, this module is dormant; the pinning
  test suite verifies its behavior with mocked Pinata responses.

  IPFS pinning is OPERATIONAL infrastructure, NOT a FROZEN-v1
  primitive. No PV-CI invariants pin this module's surface; auth
  flows, error handling, and HTTP client choice may evolve across
  phases without breaking the protocol's cryptographic commitments.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional


log = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 30


# -----------------------------------------------------------------------
# Custom exceptions
# -----------------------------------------------------------------------

class IpfsPinError(Exception):
    """Generic IPFS pinning failure base class."""


class IpfsCredentialsNotConfigured(IpfsPinError):
    """Pinata JWT is empty — pinning is in deferred-activation state."""


class IpfsAuthenticationFailed(IpfsPinError):
    """Pinata returned 401 or 403 — JWT invalid, expired, or revoked."""


class IpfsRateLimited(IpfsPinError):
    """Pinata returned 429 — back off and retry per the Retry-After hint."""


class IpfsServerError(IpfsPinError):
    """Pinata returned 5xx — service is having issues; retry later."""


class IpfsNetworkError(IpfsPinError):
    """URLError / socket timeout / DNS failure / TLS handshake failure."""


class IpfsInvalidDocument(IpfsPinError):
    """Caller passed a document that fails preflight validation."""


# -----------------------------------------------------------------------
# PinataClient
# -----------------------------------------------------------------------

class PinataClient:
    """Pinata IPFS pinning client.

    Construction:

        client = PinataClient(
            jwt=cfg.pinata_jwt,                     # Decision D1-A
            api_base_url=cfg.pinata_api_base_url,   # default per config
            gateway_url=cfg.pinata_gateway_url,
            timeout_seconds=30,
        )

    Pin a DID document:

        ipfs_hash, timestamp = client.pin_did_document(
            did_document_dict, name="vapi-anchor-sentry-did",
        )

    Verify the pin is accessible (optional, for post-pin sanity check):

        client.verify_pin(ipfs_hash)  # raises IpfsPinError on failure

    Unpin (optional, for cleanup of stale pins):

        client.unpin_document(ipfs_hash)

    All methods raise specific Ipfs*Error subclasses on failure for
    caller diagnostic clarity. Empty JWT raises
    IpfsCredentialsNotConfigured before any HTTP call.
    """

    def __init__(
        self,
        jwt: str,
        api_base_url: str = "https://api.pinata.cloud",
        gateway_url: str = "https://gateway.pinata.cloud",
        timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._jwt = jwt
        # Strip trailing slash for clean URL composition.
        self._api_base_url = api_base_url.rstrip("/")
        self._gateway_url = gateway_url.rstrip("/")
        self._timeout = int(timeout_seconds)

    # -------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------

    def pin_did_document(
        self,
        document: "dict[str, Any]",
        name: str,
    ) -> "tuple[str, str]":
        """Pin a JSON document to IPFS via Pinata.

        Args:
            document:  The document to pin (any JSON-serializable dict;
                       typically a populated DID document).
            name:      Audit-relevant label stored in Pinata metadata.
                       Convention: "<agent-name>-did" so audit logs
                       cross-reference cleanly to .claude/agents/.

        Returns:
            (ipfs_hash, timestamp) — Pinata's IpfsHash field (CID v0)
            and Timestamp field (ISO 8601 string).

        Raises:
            IpfsCredentialsNotConfigured:   JWT is empty.
            IpfsInvalidDocument:            document is not a dict OR
                                            name is empty/whitespace.
            IpfsAuthenticationFailed:       HTTP 401/403 from Pinata.
            IpfsRateLimited:                HTTP 429 from Pinata.
            IpfsServerError:                HTTP 5xx from Pinata.
            IpfsNetworkError:               URLError / socket / TLS.
            IpfsPinError:                   Malformed response, missing
                                            IpfsHash, or other failure.
        """
        # Deferred-activation: empty JWT short-circuits before any HTTP.
        if not self._jwt:
            raise IpfsCredentialsNotConfigured(
                "PINATA_JWT not set — Pinata pinning is in deferred-activation "
                "state. Generate a Pinata JWT at "
                "https://app.pinata.cloud/developers/api-keys and set the "
                "PINATA_JWT env var."
            )

        # Preflight validation
        if not isinstance(document, dict):
            raise IpfsInvalidDocument(
                f"document must be dict, got {type(document).__name__}"
            )
        if not isinstance(name, str) or not name.strip():
            raise IpfsInvalidDocument("name must be a non-empty string")

        body = {
            "pinataContent":  document,
            "pinataMetadata": {"name": name},
        }
        url = f"{self._api_base_url}/pinning/pinJSONToIPFS"
        response_body = self._post_json(url, body)

        # Parse expected fields
        ipfs_hash = response_body.get("IpfsHash")
        timestamp = response_body.get("Timestamp")
        if not isinstance(ipfs_hash, str) or not ipfs_hash:
            raise IpfsPinError(
                f"Pinata response missing or empty IpfsHash: {response_body!r}"
            )
        if not isinstance(timestamp, str) or not timestamp:
            raise IpfsPinError(
                f"Pinata response missing or empty Timestamp: {response_body!r}"
            )
        log.info("ipfs_pinning: pinned name=%s ipfs_hash=%s", name, ipfs_hash)
        return (ipfs_hash, timestamp)

    def verify_pin(self, ipfs_hash: str) -> bool:
        """Fetch the pinned document from the public gateway to confirm
        accessibility. Returns True on 200 response; raises IpfsPinError
        on any failure.

        This is a best-effort sanity check — Pinata's CDN propagation
        can lag by several seconds after a successful pin. Callers
        should retry verify_pin a few times before treating a failure
        as authoritative.
        """
        if not isinstance(ipfs_hash, str) or not ipfs_hash:
            raise IpfsInvalidDocument("ipfs_hash must be a non-empty string")
        url = f"{self._gateway_url}/ipfs/{urllib.parse.quote(ipfs_hash, safe='')}"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                # Read at least one byte to confirm the response is real.
                _ = resp.read(1)
                return True
        except urllib.error.HTTPError as exc:
            raise IpfsPinError(
                f"verify_pin gateway HTTP {exc.code}: {exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            raise IpfsNetworkError(
                f"verify_pin network error: {exc.reason}"
            ) from exc

    def unpin_document(self, ipfs_hash: str) -> None:
        """Unpin a document from Pinata. Raises IpfsPinError on failure.

        Phase O0 does not use this in normal operation — DID document
        pins are durable artifacts. Provided for completeness and for
        operator-driven cleanup scripts.
        """
        if not self._jwt:
            raise IpfsCredentialsNotConfigured(
                "PINATA_JWT not set — cannot unpin"
            )
        if not isinstance(ipfs_hash, str) or not ipfs_hash:
            raise IpfsInvalidDocument("ipfs_hash must be a non-empty string")
        url = f"{self._api_base_url}/pinning/unpin/{urllib.parse.quote(ipfs_hash, safe='')}"
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {self._jwt}"},
            method="DELETE",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                _ = resp.read()
        except urllib.error.HTTPError as exc:
            self._classify_http_error(exc)
        except urllib.error.URLError as exc:
            raise IpfsNetworkError(
                f"unpin network error: {exc.reason}"
            ) from exc

    # -------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------

    def _post_json(self, url: str, body: "dict[str, Any]") -> "dict[str, Any]":
        """POST JSON body with Bearer auth; return parsed JSON response.

        Translates HTTP and URL errors to module-specific exceptions
        (Decision D4).
        """
        encoded_body = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=encoded_body,
            headers={
                "Authorization": f"Bearer {self._jwt}",
                "Content-Type":  "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            # Subclass of URLError — must be caught FIRST.
            self._classify_http_error(exc)
            return {}  # unreachable; _classify_http_error always raises
        except urllib.error.URLError as exc:
            raise IpfsNetworkError(
                f"network error contacting Pinata: {exc.reason}"
            ) from exc

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise IpfsPinError(
                f"Pinata returned non-JSON response: {raw[:200]!r}"
            ) from exc

    def _classify_http_error(self, exc: urllib.error.HTTPError) -> None:
        """Translate an urllib HTTPError to a module-specific exception.

        Always raises; never returns. The caller pattern is
        `self._classify_http_error(exc); return ...` with the return
        statement unreachable so callers don't need to thread an
        explicit `raise from` through every exception path.
        """
        code = exc.code
        try:
            err_body = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            err_body = "<no body>"
        if code in (401, 403):
            raise IpfsAuthenticationFailed(
                f"Pinata authentication failed (HTTP {code}): {err_body}"
            ) from exc
        if code == 429:
            retry_after = exc.headers.get("Retry-After", "") if exc.headers else ""
            raise IpfsRateLimited(
                f"Pinata rate limited (HTTP 429); Retry-After={retry_after!r}: "
                f"{err_body}"
            ) from exc
        if 500 <= code < 600:
            raise IpfsServerError(
                f"Pinata server error (HTTP {code}): {err_body}"
            ) from exc
        # Other 4xx (400, 404, 422, etc.) — generic IpfsPinError.
        raise IpfsPinError(
            f"Pinata HTTP {code}: {err_body}"
        ) from exc

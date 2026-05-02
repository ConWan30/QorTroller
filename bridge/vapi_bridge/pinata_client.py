"""Phase O0 Section 6.4 — Pinata IPFS pinning client for VAPI Operator agents.

This module provides the bridge-side integration with Pinata's IPFS pinning
service, established via Pass 2C Q7 confirmation (Pinata as the Phase O0
IPFS pinning provider). The bridge agents pin their populated DID documents,
audit Merkle roots, and provenance manifest snapshots through this client.

Design rationale (Section 6.4 implementation, H2c decision):

  PinataClient as a separate module for reusability per H2c. The
  cryptographic-signing skill (Section 6.3) and provenance-recording
  skill (Section 6.4+) both compose IPFS pinning; isolating it as a
  self-contained module enables reuse without circular dependencies.

  H3a (mock all external services): MockPinataClient ships alongside
  the real client to enable CI testing without real network calls.

Interface contract (composes with provenance-recording skill at
agents/skills/provenance-recording/SKILL.md, commit 52978771):

  async def pin_json(content: dict, name: str, cid_version: int = 1) -> dict
    Pins JSON content to IPFS via Pinata's pinJSONToIPFS endpoint.
    Returns dict with IpfsHash, PinSize, Timestamp, isDuplicate.

  async def list_pins(status: str = "pinned", page_limit: int = 100) -> dict
    Lists pinned content via Pinata's pinList endpoint.

  async def unpin(cid: str) -> str
    Unpins content via Pinata's unpin endpoint.

  async def test_auth() -> dict
    Verifies authentication via Pinata's testAuthentication endpoint.

  def gateway_url(cid: str) -> str
    Constructs gateway URL for fetching pinned content.

Configuration (env vars read at construction):

  PINATA_JWT — scoped JWT with minimum-privilege permissions
  PINATA_GATEWAY_URL — dedicated gateway subdomain

  Missing any required var → PinataClientConfigError at construction.

Cross-references:

  Pass 2C Section 6.4 + Q7 — architectural specifications
  agents/skills/provenance-recording/SKILL.md (commit 52978771) — capability spec
  agents/tools/ipfs-pin.md (commit 52978771) — tool spec
  bridge/.env.example (commit 2a127a30) — env var template
  bridge/vapi_bridge/mock_pinata_client.py — in-memory mock for testing
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

import httpx
from dotenv import load_dotenv
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# Idempotent dotenv load at import time (D-Config pattern from Section 6.3)
load_dotenv()

log = logging.getLogger(__name__)

# Pinata API endpoints
_PINATA_API_BASE = "https://api.pinata.cloud"
_PIN_JSON_ENDPOINT = f"{_PINATA_API_BASE}/pinning/pinJSONToIPFS"
_PIN_LIST_ENDPOINT = f"{_PINATA_API_BASE}/data/pinList"
_UNPIN_ENDPOINT_PREFIX = f"{_PINATA_API_BASE}/pinning/unpin"
_TEST_AUTH_ENDPOINT = f"{_PINATA_API_BASE}/data/testAuthentication"

# HTTP timeout per request (seconds)
_HTTP_TIMEOUT = 30.0

# Tenacity retry config for HTTP 429 rate limiting (free tier: 60 req/min)
_RETRY_ATTEMPTS = 4
_RETRY_MIN_WAIT = 1.0
_RETRY_MAX_WAIT = 30.0


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

class PinataClientError(Exception):
    """Base exception for all PinataClient failures."""


class PinataClientConfigError(PinataClientError):
    """Raised at construction when required env vars are missing or invalid."""


class PinataClientAuthError(PinataClientError):
    """Raised when Pinata returns 401/403 (JWT invalid, expired, or wrong scope)."""


class PinataClientRateLimitError(PinataClientError):
    """Raised when Pinata returns 429 after retry attempts exhausted."""


class PinataClientNotFoundError(PinataClientError):
    """Raised when CID does not exist on Pinata (404 from unpin)."""


class PinataClientHTTPError(PinataClientError):
    """Raised for other unexpected HTTP failures (5xx, network errors)."""


# ---------------------------------------------------------------------------
# Internal: classify HTTP errors into PinataClient exception hierarchy
# ---------------------------------------------------------------------------

def _classify_http_error(operation: str, response: httpx.Response) -> PinataClientError:
    status = response.status_code
    body = response.text[:500]  # truncate body for log safety
    if status in (401, 403):
        return PinataClientAuthError(
            f"{operation} auth failed: HTTP {status} ({body})"
        )
    elif status == 404:
        return PinataClientNotFoundError(
            f"{operation} not found: HTTP {status} ({body})"
        )
    elif status == 429:
        return PinataClientRateLimitError(
            f"{operation} rate-limited: HTTP {status} ({body})"
        )
    else:
        return PinataClientHTTPError(
            f"{operation} HTTP error: {status} ({body})"
        )


# ---------------------------------------------------------------------------
# PinataClient
# ---------------------------------------------------------------------------

class PinataClient:
    """Async httpx wrapper around Pinata's IPFS pinning API.

    Construction reads PINATA_JWT and PINATA_GATEWAY_URL from environment
    variables. Methods retry on HTTP 429 (rate limit) per tenacity exponential
    backoff.
    """

    def __init__(self):
        self._jwt = os.getenv("PINATA_JWT")
        self._gateway_url = os.getenv("PINATA_GATEWAY_URL")

        missing = []
        if not self._jwt:
            missing.append("PINATA_JWT")
        if not self._gateway_url:
            missing.append("PINATA_GATEWAY_URL")

        if missing:
            raise PinataClientConfigError(
                f"Missing required env vars: {', '.join(missing)}. "
                f"See bridge/.env.example for the full template."
            )

        # Validate JWT structural shape (eyJ-prefix, 3 dot-separated segments)
        if not self._jwt.startswith("eyJ"):
            raise PinataClientConfigError(
                f"PINATA_JWT does not start with 'eyJ' — likely not a valid JWT format"
            )
        if len(self._jwt.split(".")) != 3:
            raise PinataClientConfigError(
                f"PINATA_JWT does not have 3 dot-separated segments — not a valid JWT"
            )

        self._headers = {
            "Authorization": f"Bearer {self._jwt}",
            "Content-Type": "application/json",
        }

        log.info(
            "PinataClient constructed: gateway=%s, jwt_len=%d",
            self._gateway_url, len(self._jwt),
        )

    @retry(
        retry=retry_if_exception_type(PinataClientRateLimitError),
        stop=stop_after_attempt(_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=_RETRY_MIN_WAIT, max=_RETRY_MAX_WAIT),
        reraise=True,
    )
    async def pin_json(self, content: dict, name: str, cid_version: int = 1) -> dict:
        """Pin JSON content to IPFS via pinJSONToIPFS endpoint.

        Returns dict with IpfsHash, PinSize, Timestamp, isDuplicate.
        """
        log.info("pin_json: name=%s content_keys=%d", name, len(content))
        payload = {
            "pinataContent": content,
            "pinataMetadata": {"name": name},
            "pinataOptions": {"cidVersion": cid_version},
        }
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.post(_PIN_JSON_ENDPOINT, json=payload, headers=self._headers)
        if response.status_code != 200:
            err = _classify_http_error("pin_json", response)
            log.error("pin_json: failed name=%s err=%s", name, err)
            raise err
        result = response.json()
        log.info(
            "pin_json: success name=%s cid=%s size=%s",
            name, result.get("IpfsHash"), result.get("PinSize"),
        )
        return result

    @retry(
        retry=retry_if_exception_type(PinataClientRateLimitError),
        stop=stop_after_attempt(_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=_RETRY_MIN_WAIT, max=_RETRY_MAX_WAIT),
        reraise=True,
    )
    async def list_pins(self, status: str = "pinned", page_limit: int = 100) -> dict:
        """List pinned content via pinList endpoint."""
        log.info("list_pins: status=%s page_limit=%d", status, page_limit)
        params = {"status": status, "pageLimit": page_limit}
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.get(_PIN_LIST_ENDPOINT, params=params, headers=self._headers)
        if response.status_code != 200:
            err = _classify_http_error("list_pins", response)
            log.error("list_pins: failed err=%s", err)
            raise err
        result = response.json()
        log.info("list_pins: success count=%d", result.get("count", 0))
        return result

    @retry(
        retry=retry_if_exception_type(PinataClientRateLimitError),
        stop=stop_after_attempt(_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=_RETRY_MIN_WAIT, max=_RETRY_MAX_WAIT),
        reraise=True,
    )
    async def unpin(self, cid: str) -> str:
        """Unpin content via Pinata's unpin endpoint. Returns the CID on success."""
        log.info("unpin: cid=%s", cid)
        endpoint = f"{_UNPIN_ENDPOINT_PREFIX}/{cid}"
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.delete(endpoint, headers=self._headers)
        if response.status_code != 200:
            err = _classify_http_error("unpin", response)
            log.error("unpin: failed cid=%s err=%s", cid, err)
            raise err
        log.info("unpin: success cid=%s", cid)
        return cid

    async def test_auth(self) -> dict:
        """Verify authentication via testAuthentication endpoint.

        Returns dict like {"message": "Congratulations! You are communicating with the Pinata API!"}
        """
        log.info("test_auth: requesting Pinata authentication test")
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.get(_TEST_AUTH_ENDPOINT, headers=self._headers)
        if response.status_code != 200:
            err = _classify_http_error("test_auth", response)
            log.error("test_auth: failed err=%s", err)
            raise err
        result = response.json()
        log.info("test_auth: success message=%s", result.get("message", "?"))
        return result

    def gateway_url(self, cid: str) -> str:
        """Construct gateway URL for fetching pinned content. Sync helper (no I/O)."""
        return f"https://{self._gateway_url}/ipfs/{cid}"

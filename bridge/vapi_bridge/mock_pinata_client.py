"""Phase O0 Section 6.4 — MockPinataClient for testing without real Pinata API.

Mirrors the PinataClient interface but uses in-memory storage and produces
deterministic mock CIDs based on content hash. Per H3a decision: tests
verify integration code without real network calls.

Design rationale (matches F2b precedent from Section 6.3 KMS implementation):

  Deterministic CIDs (sha256-derived) so tests are reproducible across runs.
  Same content → same CID makes pin idempotency testable.

  Same exception hierarchy as PinataClient (imported from pinata_client) so
  callers handle errors uniformly across mock and real implementations.

  test_auth() always returns success (mock matches Pinata's "Congratulations!"
  response shape).

Cross-references:

  bridge/vapi_bridge/pinata_client.py — real PinataClient interface this mocks
  bridge/tests/test_pinata_client.py — tests that exercise this mock
  bridge/vapi_bridge/agent_registration.py — composes PinataClient (or mock)
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Optional

from .pinata_client import PinataClientNotFoundError

log = logging.getLogger(__name__)


def _deterministic_mock_cid(content: dict) -> str:
    """Generate deterministic mock CID from content hash.

    Format mirrors IPFS CIDv1: starts with "bafk" (base32 multibase + dag-pb),
    followed by 50 base32-encoded chars derived from SHA-256 of canonical JSON.
    Not a real CID (real IPFS CIDs encode multihash + codec); sufficient for
    tests that verify the CID-shape contract.
    """
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(canonical).digest()
    # Mock CIDv1: "bafk" prefix (CIDv1 dag-pb sha256 base32) + 50 base32 chars
    # Real CIDs are 59 chars total; we mirror that length structure
    base32_alphabet = "abcdefghijklmnopqrstuvwxyz234567"
    encoded = "".join(base32_alphabet[b % 32] for b in digest)
    return f"bafk{encoded[:55]}"


class MockPinataClient:
    """In-memory mock of PinataClient for testing without real Pinata API.

    Stores pinned content as {cid: {content, name, timestamp}}. Mock CIDs are
    deterministic SHA-256-derived strings that mirror IPFS CIDv1 shape.
    """

    _DEFAULT_GATEWAY = "mock-gateway.example.mypinata.cloud"

    def __init__(self, gateway_url: Optional[str] = None):
        """Construct mock with empty in-memory pin storage."""
        self._gateway_url = gateway_url or self._DEFAULT_GATEWAY
        self._pins: dict[str, dict] = {}  # cid -> {content, name, timestamp, size}
        log.info("MockPinataClient constructed: gateway=%s", self._gateway_url)

    async def pin_json(self, content: dict, name: str, cid_version: int = 1) -> dict:
        """Mock pin: store in-memory + return deterministic CID."""
        cid = _deterministic_mock_cid(content)
        canonical = json.dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8")
        size = len(canonical)
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())

        is_duplicate = cid in self._pins
        if not is_duplicate:
            self._pins[cid] = {
                "content": content,
                "name": name,
                "timestamp": timestamp,
                "size": size,
            }

        log.info(
            "MockPinata pin_json: name=%s cid=%s size=%d duplicate=%s",
            name, cid, size, is_duplicate,
        )
        return {
            "IpfsHash": cid,
            "PinSize": size,
            "Timestamp": timestamp,
            "isDuplicate": is_duplicate,
        }

    async def list_pins(self, status: str = "pinned", page_limit: int = 100) -> dict:
        """Mock list: return in-memory pins as Pinata pinList response shape."""
        rows = [
            {
                "ipfs_pin_hash": cid,
                "size": meta["size"],
                "date_pinned": meta["timestamp"],
                "metadata": {"name": meta["name"]},
            }
            for cid, meta in self._pins.items()
        ][:page_limit]
        log.info("MockPinata list_pins: count=%d", len(rows))
        return {"count": len(rows), "rows": rows}

    async def unpin(self, cid: str) -> str:
        """Mock unpin: remove from in-memory storage. Raises NotFoundError if absent."""
        if cid not in self._pins:
            raise PinataClientNotFoundError(
                f"Mock unpin: CID {cid!r} not in pin storage"
            )
        del self._pins[cid]
        log.info("MockPinata unpin: cid=%s", cid)
        return cid

    async def test_auth(self) -> dict:
        """Mock auth test: always success (matches Pinata response shape)."""
        log.info("MockPinata test_auth: success")
        return {
            "message": "Congratulations! You are communicating with the Pinata API!",
            "_mock": True,
        }

    def gateway_url(self, cid: str) -> str:
        """Construct mock gateway URL."""
        return f"https://{self._gateway_url}/ipfs/{cid}"

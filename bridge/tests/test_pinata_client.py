"""Phase O0 Section 6.4 — PinataClient + MockPinataClient tests.

Six tests covering:
  Test 1: PinataClient construction succeeds with all required env vars
  Test 2: PinataClient construction raises PinataClientConfigError when env vars missing
  Test 3: MockPinataClient pin-then-list round-trip
  Test 4: MockPinataClient unpin removes content
  Test 5: MockPinataClient deterministic CID for same content
  Test 6: PinataClient gateway_url construction

All six tests use MockPinataClient for storage operations (no real Pinata API
calls). Test 1 / Test 2 construct real PinataClient to validate env-var
consumption path; both pass without invoking Pinata APIs (httpx client creation
is lazy — no network calls).

Cross-references:
  bridge/vapi_bridge/pinata_client.py — real PinataClient
  bridge/vapi_bridge/mock_pinata_client.py — in-memory mock
  agents/skills/provenance-recording/SKILL.md — capability spec
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.mock_pinata_client import MockPinataClient
from vapi_bridge.pinata_client import (
    PinataClient,
    PinataClientConfigError,
    PinataClientNotFoundError,
)


# Sample valid-looking JWT (eyJ-prefix, 3 dot-separated segments) for construction test
_TEST_JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IlRlc3QifQ."
    "TJVA95OrM7E2cBab30RMHrHDcEfxjoYZgeFONFh7HgQ"
)


# ---------------------------------------------------------------------------
# Test 1: Construction succeeds with all env vars
# ---------------------------------------------------------------------------

def test_pinata_client_construction_succeeds_with_env_vars(monkeypatch):
    """PinataClient construction succeeds when PINATA_JWT and PINATA_GATEWAY_URL are present."""
    monkeypatch.setenv("PINATA_JWT", _TEST_JWT)
    monkeypatch.setenv("PINATA_GATEWAY_URL", "test-subdomain.mypinata.cloud")

    client = PinataClient()
    assert client is not None
    assert client._gateway_url == "test-subdomain.mypinata.cloud"
    assert client._jwt == _TEST_JWT


# ---------------------------------------------------------------------------
# Test 2: Construction fails without env vars
# ---------------------------------------------------------------------------

def test_pinata_client_construction_fails_without_env_vars(monkeypatch):
    """PinataClient construction raises PinataClientConfigError when env vars missing."""
    monkeypatch.delenv("PINATA_JWT", raising=False)
    monkeypatch.delenv("PINATA_GATEWAY_URL", raising=False)

    with pytest.raises(PinataClientConfigError) as exc_info:
        PinataClient()
    assert "Missing required env vars" in str(exc_info.value)
    assert "PINATA_JWT" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 3: pin-then-list round-trip
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mock_pinata_client_pin_then_retrieve_roundtrip():
    """MockPinataClient pin-then-list returns the same content."""
    client = MockPinataClient()
    content = {"agent": "anchor-sentry", "version": "1.0"}

    pin_result = await client.pin_json(content, name="test-pin")
    assert "IpfsHash" in pin_result
    assert pin_result["IpfsHash"].startswith("bafk")
    assert pin_result["isDuplicate"] is False
    assert pin_result["PinSize"] > 0

    list_result = await client.list_pins()
    assert list_result["count"] == 1
    cids = [row["ipfs_pin_hash"] for row in list_result["rows"]]
    assert pin_result["IpfsHash"] in cids


# ---------------------------------------------------------------------------
# Test 4: unpin removes content
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mock_pinata_client_unpin_removes_content():
    """MockPinataClient unpin removes content from in-memory storage."""
    client = MockPinataClient()
    content = {"agent": "guardian", "version": "1.0"}

    pin_result = await client.pin_json(content, name="test-pin")
    cid = pin_result["IpfsHash"]

    list_before = await client.list_pins()
    assert list_before["count"] == 1

    unpin_result = await client.unpin(cid)
    assert unpin_result == cid

    list_after = await client.list_pins()
    assert list_after["count"] == 0

    # Unpinning a non-existent CID raises NotFoundError
    with pytest.raises(PinataClientNotFoundError):
        await client.unpin(cid)


# ---------------------------------------------------------------------------
# Test 5: deterministic CID for same content
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mock_pinata_client_deterministic_cid_for_same_content():
    """Same content produces same CID; isDuplicate flips to True on re-pin."""
    client = MockPinataClient()
    content = {"key": "value", "nested": {"a": 1, "b": 2}}

    pin1 = await client.pin_json(content, name="first")
    pin2 = await client.pin_json(content, name="second")

    assert pin1["IpfsHash"] == pin2["IpfsHash"]  # deterministic
    assert pin1["isDuplicate"] is False
    assert pin2["isDuplicate"] is True

    # Different content produces different CID
    different_content = {"key": "value", "nested": {"a": 1, "b": 3}}
    pin3 = await client.pin_json(different_content, name="third")
    assert pin3["IpfsHash"] != pin1["IpfsHash"]
    assert pin3["isDuplicate"] is False


# ---------------------------------------------------------------------------
# Test 6: gateway_url construction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pinata_client_gateway_url_construction():
    """PinataClient.gateway_url constructs https://<gateway>/ipfs/<cid>."""
    # MockPinataClient version
    mock = MockPinataClient(gateway_url="my-subdomain.mypinata.cloud")
    cid = "bafkreigh2akiscaildcqabsyg3dfr6chu3fgpregiymsck7e7aqa4s52zy"
    url = mock.gateway_url(cid)
    assert url == f"https://my-subdomain.mypinata.cloud/ipfs/{cid}"

    # Real PinataClient version
    import os
    os.environ["PINATA_JWT"] = _TEST_JWT
    os.environ["PINATA_GATEWAY_URL"] = "real-subdomain.mypinata.cloud"
    try:
        real = PinataClient()
        real_url = real.gateway_url(cid)
        assert real_url == f"https://real-subdomain.mypinata.cloud/ipfs/{cid}"
    finally:
        # Cleanup env vars set above so they don't leak to other tests
        del os.environ["PINATA_JWT"]
        del os.environ["PINATA_GATEWAY_URL"]

"""Phase O0 Stream 5-prep Session 2 — IPFS pinning (Pinata) tests.

Verifies PinataClient behavior against MOCKED Pinata responses
(Decision D4: no real Pinata API calls in the test suite per the
critical constraint). Covers success, 401, 429, 500, URLError, and
malformed-response paths plus the deferred-activation behavior on
empty JWT.

Tests:
  T-IPFS-1:  pin_did_document success — returns (ipfs_hash, timestamp)
             with values from the mocked Pinata response.
  T-IPFS-2:  pin_did_document with empty JWT raises
             IpfsCredentialsNotConfigured BEFORE any HTTP call (verified
             via mock not being called).
  T-IPFS-3:  pin_did_document HTTP 401 raises IpfsAuthenticationFailed.
  T-IPFS-4:  pin_did_document HTTP 403 raises IpfsAuthenticationFailed
             (same exception, both auth-related codes).
  T-IPFS-5:  pin_did_document HTTP 429 raises IpfsRateLimited; the
             Retry-After header is preserved in the exception message.
  T-IPFS-6:  pin_did_document HTTP 500 raises IpfsServerError.
  T-IPFS-7:  pin_did_document URLError (network failure) raises
             IpfsNetworkError.
  T-IPFS-8:  pin_did_document non-JSON response raises IpfsPinError
             with response body in the message.
  T-IPFS-9:  pin_did_document JSON missing IpfsHash raises IpfsPinError.
  T-IPFS-10: pin_did_document non-dict input raises IpfsInvalidDocument
             before any HTTP call; empty-name input also raises.
  T-IPFS-11: pin_did_document populates request body correctly:
             pinataContent matches the document, pinataMetadata.name
             matches the name argument; Authorization header carries
             the JWT bearer token; Content-Type is application/json.
  T-IPFS-12: verify_pin success on HTTP 200 returns True; verify_pin
             on HTTPError raises IpfsPinError; on URLError raises
             IpfsNetworkError.
"""
import io
import json
import os
import sys
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.ipfs_pinning import (  # noqa: E402
    PinataClient,
    IpfsPinError,
    IpfsCredentialsNotConfigured,
    IpfsAuthenticationFailed,
    IpfsRateLimited,
    IpfsServerError,
    IpfsNetworkError,
    IpfsInvalidDocument,
)


# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

_JWT = "eyJtest.jwt.token"
_DOC = {
    "@context": ["https://www.w3.org/ns/did/v1"],
    "id":       "did:io:0xabcdef",
    "metadata": {"agentRole": "AnchorSentry", "modelClass": "claude-sonnet-4-6"},
}
_NAME = "vapi-anchor-sentry-did"
_PIN_RESPONSE = {
    "IpfsHash":  "QmTest123abcdef",
    "PinSize":   512,
    "Timestamp": "2026-04-28T12:00:00.000Z",
}


def _mock_urlopen_success(response_dict: "dict | None" = None):
    """Return a mock urlopen that yields a context manager with a JSON
    response body.
    """
    if response_dict is None:
        response_dict = _PIN_RESPONSE
    body = json.dumps(response_dict).encode("utf-8")

    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=body)))
    cm.__exit__ = MagicMock(return_value=False)

    mock_urlopen = MagicMock(return_value=cm)
    return mock_urlopen


def _mock_urlopen_raw(raw_body: bytes):
    """Return mock urlopen yielding a context manager with raw bytes."""
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=raw_body)))
    cm.__exit__ = MagicMock(return_value=False)
    return MagicMock(return_value=cm)


def _mock_http_error(code: int, body: bytes = b"", headers: dict | None = None):
    """Return a mock urlopen that raises urllib.error.HTTPError."""
    err = urllib.error.HTTPError(
        url="https://api.pinata.cloud/pinning/pinJSONToIPFS",
        code=code,
        msg=f"HTTP {code}",
        hdrs=headers if headers is not None else {},  # type: ignore[arg-type]
        fp=io.BytesIO(body),
    )
    return MagicMock(side_effect=err)


def _mock_url_error(reason: str = "Connection refused"):
    """Return a mock urlopen that raises urllib.error.URLError."""
    err = urllib.error.URLError(reason)
    return MagicMock(side_effect=err)


# ---------------------------------------------------------------------------
# T-IPFS-1
# ---------------------------------------------------------------------------

def test_t_ipfs_1_pin_success():
    client = PinataClient(jwt=_JWT)
    with patch("urllib.request.urlopen", _mock_urlopen_success()):
        ipfs_hash, timestamp = client.pin_did_document(_DOC, _NAME)
    assert ipfs_hash == "QmTest123abcdef"
    assert timestamp == "2026-04-28T12:00:00.000Z"


# ---------------------------------------------------------------------------
# T-IPFS-2
# ---------------------------------------------------------------------------

def test_t_ipfs_2_empty_jwt_short_circuits():
    """Empty JWT raises IpfsCredentialsNotConfigured BEFORE any HTTP call."""
    client = PinataClient(jwt="")
    mock = MagicMock()
    with patch("urllib.request.urlopen", mock):
        with pytest.raises(IpfsCredentialsNotConfigured, match="PINATA_JWT not set"):
            client.pin_did_document(_DOC, _NAME)
    # Zero HTTP calls — short-circuited deferred-activation
    mock.assert_not_called()


# ---------------------------------------------------------------------------
# T-IPFS-3
# ---------------------------------------------------------------------------

def test_t_ipfs_3_http_401_auth_failed():
    client = PinataClient(jwt=_JWT)
    mock = _mock_http_error(401, b'{"error": "Invalid JWT"}')
    with patch("urllib.request.urlopen", mock):
        with pytest.raises(IpfsAuthenticationFailed, match="HTTP 401"):
            client.pin_did_document(_DOC, _NAME)


# ---------------------------------------------------------------------------
# T-IPFS-4
# ---------------------------------------------------------------------------

def test_t_ipfs_4_http_403_auth_failed():
    client = PinataClient(jwt=_JWT)
    mock = _mock_http_error(403, b'{"error": "Forbidden"}')
    with patch("urllib.request.urlopen", mock):
        with pytest.raises(IpfsAuthenticationFailed, match="HTTP 403"):
            client.pin_did_document(_DOC, _NAME)


# ---------------------------------------------------------------------------
# T-IPFS-5
# ---------------------------------------------------------------------------

def test_t_ipfs_5_http_429_rate_limited():
    client = PinataClient(jwt=_JWT)
    mock = _mock_http_error(
        429, b'{"error": "Rate limited"}',
        headers={"Retry-After": "60"},
    )
    with patch("urllib.request.urlopen", mock):
        with pytest.raises(IpfsRateLimited) as excinfo:
            client.pin_did_document(_DOC, _NAME)
    msg = str(excinfo.value)
    assert "HTTP 429" in msg
    assert "60" in msg, f"Retry-After value '60' missing from message: {msg}"


# ---------------------------------------------------------------------------
# T-IPFS-6
# ---------------------------------------------------------------------------

def test_t_ipfs_6_http_500_server_error():
    client = PinataClient(jwt=_JWT)
    mock = _mock_http_error(500, b'<html>Internal Server Error</html>')
    with patch("urllib.request.urlopen", mock):
        with pytest.raises(IpfsServerError, match="HTTP 500"):
            client.pin_did_document(_DOC, _NAME)


# ---------------------------------------------------------------------------
# T-IPFS-7
# ---------------------------------------------------------------------------

def test_t_ipfs_7_url_error_network():
    client = PinataClient(jwt=_JWT)
    mock = _mock_url_error("Name or service not known")
    with patch("urllib.request.urlopen", mock):
        with pytest.raises(IpfsNetworkError, match="network error"):
            client.pin_did_document(_DOC, _NAME)


# ---------------------------------------------------------------------------
# T-IPFS-8
# ---------------------------------------------------------------------------

def test_t_ipfs_8_non_json_response():
    """Pinata returns HTML (e.g., a maintenance page); IpfsPinError with
    body fragment in message.
    """
    client = PinataClient(jwt=_JWT)
    mock = _mock_urlopen_raw(b"<html>503 Service Unavailable</html>")
    with patch("urllib.request.urlopen", mock):
        with pytest.raises(IpfsPinError, match="non-JSON"):
            client.pin_did_document(_DOC, _NAME)


# ---------------------------------------------------------------------------
# T-IPFS-9
# ---------------------------------------------------------------------------

def test_t_ipfs_9_response_missing_ipfs_hash():
    """Valid JSON but missing IpfsHash field — caller can't proceed."""
    client = PinataClient(jwt=_JWT)
    mock = _mock_urlopen_success({"PinSize": 100, "Timestamp": "2026-04-28T00:00:00Z"})
    with patch("urllib.request.urlopen", mock):
        with pytest.raises(IpfsPinError, match="missing or empty IpfsHash"):
            client.pin_did_document(_DOC, _NAME)


# ---------------------------------------------------------------------------
# T-IPFS-10
# ---------------------------------------------------------------------------

def test_t_ipfs_10_invalid_input():
    """Non-dict document or empty name raises IpfsInvalidDocument BEFORE
    any HTTP call.
    """
    client = PinataClient(jwt=_JWT)
    mock = MagicMock()
    with patch("urllib.request.urlopen", mock):
        # Non-dict document
        with pytest.raises(IpfsInvalidDocument, match="must be dict"):
            client.pin_did_document("not a dict", _NAME)
        # Empty name
        with pytest.raises(IpfsInvalidDocument, match="non-empty string"):
            client.pin_did_document(_DOC, "")
        # Whitespace-only name
        with pytest.raises(IpfsInvalidDocument, match="non-empty string"):
            client.pin_did_document(_DOC, "   ")
    mock.assert_not_called()


# ---------------------------------------------------------------------------
# T-IPFS-11
# ---------------------------------------------------------------------------

def test_t_ipfs_11_request_body_and_headers_correct():
    """Captured Request shows pinataContent matches document,
    pinataMetadata.name matches name arg, Authorization header carries
    JWT bearer, Content-Type is application/json.
    """
    client = PinataClient(jwt=_JWT)
    mock = _mock_urlopen_success()
    with patch("urllib.request.urlopen", mock):
        client.pin_did_document(_DOC, _NAME)

    # Inspect the Request object passed to urlopen
    call_args = mock.call_args
    request = call_args[0][0]  # first positional arg
    assert request.full_url.endswith("/pinning/pinJSONToIPFS")
    assert request.method == "POST"
    # Headers are case-insensitive; urllib stores capitalized
    headers = {k.lower(): v for k, v in request.header_items()}
    assert headers.get("authorization") == f"Bearer {_JWT}"
    assert headers.get("content-type") == "application/json"

    # Body decodes to expected JSON shape
    body = json.loads(request.data.decode("utf-8"))
    assert body["pinataContent"] == _DOC
    assert body["pinataMetadata"]["name"] == _NAME


# ---------------------------------------------------------------------------
# T-IPFS-12
# ---------------------------------------------------------------------------

def test_t_ipfs_12_verify_pin_paths():
    """verify_pin success returns True; HTTPError raises IpfsPinError;
    URLError raises IpfsNetworkError.
    """
    client = PinataClient(jwt=_JWT)

    # Success: 200 response with non-empty body
    mock_ok = _mock_urlopen_raw(b"x")  # one byte to satisfy the .read(1) check
    with patch("urllib.request.urlopen", mock_ok):
        assert client.verify_pin("QmABC123") is True

    # HTTPError (e.g., 404 — pin not yet propagated)
    mock_404 = _mock_http_error(404, b"not found")
    with patch("urllib.request.urlopen", mock_404):
        with pytest.raises(IpfsPinError, match="404"):
            client.verify_pin("QmABC123")

    # URLError (network)
    mock_net = _mock_url_error("DNS failure")
    with patch("urllib.request.urlopen", mock_net):
        with pytest.raises(IpfsNetworkError, match="network error"):
            client.verify_pin("QmABC123")

    # Empty hash rejected before any HTTP
    mock_unused = MagicMock()
    with patch("urllib.request.urlopen", mock_unused):
        with pytest.raises(IpfsInvalidDocument, match="non-empty"):
            client.verify_pin("")
    mock_unused.assert_not_called()

"""
sdk/tests/test_phase228_sdk.py
Phase 228 — SDK VAPIAllowlistGovernance.post_invariant_change() (4 tests)

T228-SDK-1: post_invariant_change() sends reason_category=invariant_change and vhp_token_id
T228-SDK-2: post_invariant_change() validates reason_text length (< 10 chars → error dict)
T228-SDK-3: post_invariant_change() with empty vhp_token_id still sends the request
T228-SDK-4: post_invariant_change() returns error dict on HTTP failure
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))


def make_governance():
    from vapi_sdk import VAPIAllowlistGovernance
    gov = VAPIAllowlistGovernance.__new__(VAPIAllowlistGovernance)
    gov._base = "http://localhost:8765"
    gov._key = "test"
    return gov


# ---------------------------------------------------------------------------
# T228-SDK-1: sends reason_category=invariant_change and vhp_token_id
# ---------------------------------------------------------------------------

def test_t228_sdk_1_sends_invariant_change_with_vhp_token():
    gov = make_governance()
    captured = {}

    import json, urllib.request

    class MockResponse:
        def read(self):
            return json.dumps({"row_id": 1, "accepted": True, "vhp_token_id": "42"}).encode()
        def __enter__(self): return self
        def __exit__(self, *a): pass

    def mock_urlopen(req, timeout):
        body = json.loads(req.data.decode())
        captured.update(body)
        return MockResponse()

    import unittest.mock
    with unittest.mock.patch("urllib.request.urlopen", mock_urlopen):
        result = gov.post_invariant_change(
            reason_text="Freeze INV-023 region for phase 228 governance",
            vhp_token_id="42",
        )

    assert captured.get("reason_category") == "invariant_change"
    assert captured.get("vhp_token_id") == "42"
    assert result.get("accepted") is True


# ---------------------------------------------------------------------------
# T228-SDK-2: validates reason_text length
# ---------------------------------------------------------------------------

def test_t228_sdk_2_validates_reason_text_length():
    gov = make_governance()

    result = gov.post_invariant_change(reason_text="short", vhp_token_id="1")
    assert "error" in result
    assert "10-200" in result["error"]

    result2 = gov.post_invariant_change(reason_text="x" * 201, vhp_token_id="1")
    assert "error" in result2
    assert "10-200" in result2["error"]


# ---------------------------------------------------------------------------
# T228-SDK-3: empty vhp_token_id still sends the request
# ---------------------------------------------------------------------------

def test_t228_sdk_3_empty_vhp_token_sends_request():
    gov = make_governance()
    captured = {}

    import json, urllib.request

    class MockResponse:
        def read(self):
            return json.dumps({"row_id": 2, "accepted": True, "vhp_token_id": None}).encode()
        def __enter__(self): return self
        def __exit__(self, *a): pass

    def mock_urlopen(req, timeout):
        body = json.loads(req.data.decode())
        captured.update(body)
        return MockResponse()

    import unittest.mock
    with unittest.mock.patch("urllib.request.urlopen", mock_urlopen):
        result = gov.post_invariant_change(
            reason_text="Refactor invariant gate for phase 228 empty vhp test",
            vhp_token_id="",
        )

    assert captured.get("reason_category") == "invariant_change"
    assert captured.get("vhp_token_id") == ""
    # No local validation error for empty vhp_token_id — gate is server-side
    assert "error" not in result


# ---------------------------------------------------------------------------
# T228-SDK-4: returns error dict on HTTP failure
# ---------------------------------------------------------------------------

def test_t228_sdk_4_returns_error_on_http_failure():
    gov = make_governance()

    import unittest.mock
    with unittest.mock.patch("urllib.request.urlopen", side_effect=RuntimeError("connection refused")):
        result = gov.post_invariant_change(
            reason_text="Phase 228 HTTP failure test for invariant change",
            vhp_token_id="99",
        )

    assert "error" in result
    assert "connection refused" in result["error"]

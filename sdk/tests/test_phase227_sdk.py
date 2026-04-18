"""
sdk/tests/test_phase227_sdk.py
Phase 227 — SDK VAPIAllowlistGovernance.on_chain_provenance_hash() (4 tests)

T227-SDK-1: on_chain_provenance_hash() parses governance_provenance_hash from status response
T227-SDK-2: on_chain_provenance_hash() returns "" when field missing from response
T227-SDK-3: on_chain_provenance_hash() returns "" on HTTP error (fail-open)
T227-SDK-4: on_chain_provenance_hash() returns "" when response is not a dict
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
# T227-SDK-1: parses governance_provenance_hash from status response
# ---------------------------------------------------------------------------

def test_t227_sdk_1_parses_governance_provenance_hash():
    gov = make_governance()
    expected_hash = "a" * 64

    def mock_get(path):
        assert path == "/agent/protocol-coherence-status"
        return {
            "governance_provenance_hash": expected_hash,
            "total_anchors": 5,
            "on_chain_confirmed": True,
        }

    gov._get = mock_get
    result = gov.on_chain_provenance_hash()
    assert result == expected_hash


# ---------------------------------------------------------------------------
# T227-SDK-2: returns "" when field missing from response
# ---------------------------------------------------------------------------

def test_t227_sdk_2_returns_empty_when_field_missing():
    gov = make_governance()

    def mock_get(path):
        return {"total_anchors": 3, "on_chain_confirmed": True}

    gov._get = mock_get
    result = gov.on_chain_provenance_hash()
    assert result == ""


# ---------------------------------------------------------------------------
# T227-SDK-3: returns "" on HTTP error (fail-open)
# ---------------------------------------------------------------------------

def test_t227_sdk_3_returns_empty_on_http_error():
    gov = make_governance()

    def mock_get(path):
        raise RuntimeError("connection refused")

    gov._get = mock_get
    result = gov.on_chain_provenance_hash()
    assert result == ""


# ---------------------------------------------------------------------------
# T227-SDK-4: returns "" when response is not a dict
# ---------------------------------------------------------------------------

def test_t227_sdk_4_returns_empty_when_response_not_dict():
    gov = make_governance()

    def mock_get(path):
        return None

    gov._get = mock_get
    result = gov.on_chain_provenance_hash()
    assert result == ""

"""
Phase 226 SDK tests — Invariant Scope Expansion (INV-019..022)

T226-SDK-1  VAPIInvariantGate.get_status() parses total_checked=22
T226-SDK-2  VAPIAllowlistGovernance.chain_intact() returns bool from chain_intact field
T226-SDK-3  InvariantGateResult dataclass has correct slots; 22 invariants reflected
T226-SDK-4  get_status() handles missing/extra keys gracefully (absent→default)
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


def _mock_urlopen(body: bytes) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# T226-SDK-1: VAPIInvariantGate.get_status() parses total_checked=22
def test_t226_sdk1_invariant_gate_22():
    from vapi_sdk import VAPIInvariantGate

    _body = json.dumps({
        "pv_ci_enabled": True,
        "gate_pass": True,
        "total_checked": 22,
        "failure_count": 0,
        "last_failures": [],
        "last_run_ts": 1713200000.0,
        "timestamp": 1713200000.0,
    }).encode()

    with patch("urllib.request.urlopen", return_value=_mock_urlopen(_body)):
        client = VAPIInvariantGate("http://localhost:8080", "test_key")
        result = client.get_status()

    assert result.total_checked == 22
    assert result.gate_pass is True
    assert result.failure_count == 0
    assert result.error is None


# T226-SDK-2: VAPIAllowlistGovernance.chain_intact() returns bool from response
def test_t226_sdk2_chain_intact():
    from vapi_sdk import VAPIAllowlistGovernance

    # chain_intact=True response
    _body_true = json.dumps({
        "entries": [],
        "total_entries": 0,
        "chain_intact": True,
        "timestamp": 1713200000.0,
    }).encode()

    with patch("urllib.request.urlopen", return_value=_mock_urlopen(_body_true)):
        gov = VAPIAllowlistGovernance("http://localhost:8080", "test_key")
        assert gov.chain_intact() is True

    # chain_intact=False response
    _body_false = json.dumps({
        "entries": [{"id": 1}],
        "total_entries": 1,
        "chain_intact": False,
        "timestamp": 1713200000.0,
    }).encode()

    with patch("urllib.request.urlopen", return_value=_mock_urlopen(_body_false)):
        gov = VAPIAllowlistGovernance("http://localhost:8080", "test_key")
        assert gov.chain_intact() is False


# T226-SDK-3: InvariantGateResult has correct slots
def test_t226_sdk3_result_slots():
    from vapi_sdk import InvariantGateResult

    r = InvariantGateResult()
    assert hasattr(r, "pv_ci_enabled")
    assert hasattr(r, "gate_pass")
    assert hasattr(r, "total_checked")
    assert hasattr(r, "failure_count")
    assert hasattr(r, "last_failures")
    assert hasattr(r, "last_run_ts")
    assert hasattr(r, "error")

    # Defaults
    assert r.pv_ci_enabled is False
    assert r.gate_pass is None
    assert r.total_checked == 0
    assert r.failure_count == 0
    assert r.last_failures == []
    assert r.error is None


# T226-SDK-4: get_status() handles missing keys gracefully
def test_t226_sdk4_missing_keys_default():
    from vapi_sdk import VAPIInvariantGate

    # Minimal response — only timestamp
    _body = json.dumps({"timestamp": 1713200099.0}).encode()

    with patch("urllib.request.urlopen", return_value=_mock_urlopen(_body)):
        client = VAPIInvariantGate("http://localhost:8080")
        result = client.get_status()

    assert result.total_checked == 0
    assert result.gate_pass is None
    assert result.failure_count == 0
    assert result.last_failures == []
    assert result.error is None

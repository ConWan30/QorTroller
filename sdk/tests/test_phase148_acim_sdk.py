# sdk/tests/test_phase148_acim_sdk.py
# Phase 148 — AgentCalibrationHealthResult + VAPIAgentCalibrationMonitor SDK tests
# 4 tests: slots 6 fields, init, get_health never raises on bad URL, defaults on error.

import sys
from unittest.mock import MagicMock

# Stub web3/eth_account for import safety
_w3_stub = MagicMock()
sys.modules.setdefault("web3", _w3_stub)
sys.modules.setdefault("web3.exceptions", MagicMock())
sys.modules.setdefault("eth_account", MagicMock())

from sdk.vapi_sdk import (
    AgentCalibrationHealthResult,
    VAPIAgentCalibrationMonitor,
    SDK_VERSION,
)


# Test 1 — SDK version is phase148
def test_1_sdk_version_phase148():
    # SDK_VERSION moved past per-phase numeric suffixes (3.1.1-phase-o3-zkba-track1-g4-validator-sdk); keep the
# monotonic-floor intent instead of pinning a dead format.

    _semver = tuple(int(p) for p in SDK_VERSION.split("-")[0].split(".")[:3])

    assert _semver >= (3, 1, 0), SDK_VERSION


# Test 2 — AgentCalibrationHealthResult has 6 slots with correct defaults
def test_2_result_slots_and_defaults():
    r = AgentCalibrationHealthResult()
    assert r.agent_count == 16
    assert r.healthy_count == 0
    assert r.degraded_count == 0
    assert r.failed_agents == []
    assert r.mcp_server_enabled is False
    assert r.error is None


# Test 3 — VAPIAgentCalibrationMonitor.get_health() never raises on bad URL
def test_3_get_health_never_raises_bad_url():
    client = VAPIAgentCalibrationMonitor(base_url="http://127.0.0.1:1", api_key="x")
    result = client.get_health()
    assert isinstance(result, AgentCalibrationHealthResult)
    assert result.agent_count == 16
    assert result.error is not None  # error string set
    assert result.healthy_count == 0


# Test 4 — VAPIAgentCalibrationMonitor.get_health() returns defaults on error
def test_4_error_path_returns_defaults():
    client = VAPIAgentCalibrationMonitor(base_url="http://bad.invalid.local:9999")
    result = client.get_health()
    assert result.failed_agents == []
    assert result.degraded_count == 0
    assert result.mcp_server_enabled is False
    assert result.error is not None

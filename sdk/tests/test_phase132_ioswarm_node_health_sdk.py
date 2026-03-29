"""Phase 132 SDK tests — IoSwarm Node Health. +4 (SDK 217 → 221)."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sdk.vapi_sdk import IoSwarmNodeHealthResult, VAPIIoSwarmNodeHealth, SDK_VERSION


def test_1_IoSwarmNodeHealthResult_6_slots():
    """IoSwarmNodeHealthResult has the 6 expected slot fields."""
    r = IoSwarmNodeHealthResult()
    assert r.nodes_configured == 0
    assert r.nodes_healthy == 0
    assert r.emulator_mode is True
    assert r.avg_latency_ms == -1.0
    assert r.health_log_count == 0
    assert r.error is None


def test_2_init_no_raise():
    """VAPIIoSwarmNodeHealth instantiation never raises."""
    client = VAPIIoSwarmNodeHealth(base_url="http://localhost:8000", api_key="test")
    assert client is not None


def test_3_bad_url_returns_error_not_none():
    """get_node_health on unreachable URL returns error field, never raises."""
    client = VAPIIoSwarmNodeHealth(base_url="http://127.0.0.1:19999", api_key="")
    result = client.get_node_health()
    assert isinstance(result, IoSwarmNodeHealthResult)
    assert result.error is not None


def test_4_error_path_emulator_mode_true():
    """On connection error the result has emulator_mode=True and nodes_healthy=0."""
    client = VAPIIoSwarmNodeHealth(base_url="http://127.0.0.1:19999", api_key="")
    result = client.get_node_health()
    assert result.emulator_mode is True
    assert result.nodes_healthy == 0
    assert result.nodes_configured == 0

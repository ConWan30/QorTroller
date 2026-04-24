"""
Phase 214 SDK tests — GraduationAutowatchBridge

T214-SDK-1  GraduationAutowatchResult dataclass has 7 fields with correct defaults
T214-SDK-2  VAPIGraduationAutowatch.get_status() parses graduation_autowatch_enabled
T214-SDK-3  VAPIGraduationAutowatch.get_status() parses trigger_count and evaluated_count
T214-SDK-4  VAPIGraduationAutowatch.get_status() handles missing keys gracefully (absent→default)
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# T214-SDK-1  GraduationAutowatchResult has 7 fields with correct defaults
# ---------------------------------------------------------------------------
def test_graduation_autowatch_result_fields():
    """GraduationAutowatchResult must have 7 slots with correct defaults."""
    from vapi_sdk import GraduationAutowatchResult

    r = GraduationAutowatchResult()
    # Verify all 7 fields exist and have expected defaults
    assert r.graduation_autowatch_enabled is True
    assert r.trigger_count == 0
    assert r.evaluated_count == 0
    assert r.last_trigger_probe_type is None
    assert r.last_preconditions_met is None
    assert r.timestamp == 0.0
    assert r.error is None

    # Verify slots count
    fields = [f for f in dir(r) if not f.startswith("_")]
    # At minimum the 7 documented fields must all be present
    expected = {
        "graduation_autowatch_enabled", "trigger_count", "evaluated_count",
        "last_trigger_probe_type", "last_preconditions_met", "timestamp", "error",
    }
    actual_fields = {f for f in expected if hasattr(r, f)}
    assert actual_fields == expected, f"Missing fields: {expected - actual_fields}"


# ---------------------------------------------------------------------------
# T214-SDK-2  VAPIGraduationAutowatch.get_status() parses graduation_autowatch_enabled
# ---------------------------------------------------------------------------
def test_vapigraduationautowatch_parses_enabled():
    """VAPIGraduationAutowatch.get_status() must parse graduation_autowatch_enabled correctly."""
    from vapi_sdk import VAPIGraduationAutowatch

    _body = json.dumps({
        "graduation_autowatch_enabled": True,
        "trigger_count": 2,
        "evaluated_count": 1,
        "last_trigger_probe_type": "tremor_resting",
        "last_preconditions_met": False,
        "timestamp": 1713200000.0,
    }).encode()

    mock_resp = MagicMock()
    mock_resp.read.return_value = _body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        client = VAPIGraduationAutowatch("http://localhost:8080", "test_key")
        result = client.get_status()

    assert result.graduation_autowatch_enabled is True
    assert result.error is None


# ---------------------------------------------------------------------------
# T214-SDK-3  VAPIGraduationAutowatch.get_status() parses trigger/evaluated counts
# ---------------------------------------------------------------------------
def test_vapigraduationautowatch_parses_counts():
    """VAPIGraduationAutowatch.get_status() must parse trigger_count, evaluated_count, and
    last_preconditions_met correctly."""
    from vapi_sdk import VAPIGraduationAutowatch

    _body = json.dumps({
        "graduation_autowatch_enabled": True,
        "trigger_count": 3,
        "evaluated_count": 2,
        "last_trigger_probe_type": "tremor_resting",
        "last_preconditions_met": True,
        "timestamp": 1713200001.5,
    }).encode()

    mock_resp = MagicMock()
    mock_resp.read.return_value = _body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        client = VAPIGraduationAutowatch("http://localhost:8080")
        result = client.get_status(probe_type="tremor_resting")

    assert result.trigger_count == 3
    assert result.evaluated_count == 2
    assert result.last_trigger_probe_type == "tremor_resting"
    assert result.last_preconditions_met is True
    assert result.timestamp == pytest.approx(1713200001.5)


# ---------------------------------------------------------------------------
# T214-SDK-4  get_status() handles absent keys gracefully (defaults)
# ---------------------------------------------------------------------------
def test_vapigraduationautowatch_absent_keys_default():
    """VAPIGraduationAutowatch.get_status() must return defaults for absent keys."""
    from vapi_sdk import VAPIGraduationAutowatch

    # Minimal response — missing most fields
    _body = json.dumps({"timestamp": 1713200099.0}).encode()

    mock_resp = MagicMock()
    mock_resp.read.return_value = _body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        client = VAPIGraduationAutowatch("http://localhost:8080")
        result = client.get_status()

    assert result.graduation_autowatch_enabled is True  # default=True
    assert result.trigger_count == 0                    # default=0
    assert result.evaluated_count == 0                  # default=0
    assert result.last_trigger_probe_type is None       # absent→None
    assert result.last_preconditions_met is None        # absent→None
    assert result.error is None

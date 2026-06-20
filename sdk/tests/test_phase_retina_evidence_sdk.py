"""SDK tests for VAPIRetinaEvidenceSlice (Retina observability goal)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))

from vapi_sdk import RetinaEvidenceSliceResult, VAPIRetinaEvidenceSlice  # noqa: E402


def test_t_sdk_1_happy_path_parse():
    """status() parses bindings and aggregate from JSON response."""
    body = {
        "schema": "vapi-retina-event-v1",
        "enabled": True,
        "bindings": [{"record_hash": "ab" * 32, "anomaly_count": 1}],
        "aggregate": {"rows_matched": 1, "total_trajectory_anomalies": 1},
        "device_id": "dev1",
        "timestamp": 123.0,
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(body).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = VAPIRetinaEvidenceSlice("http://localhost:8080").status("dev1")

    assert result.error == ""
    assert result.enabled is True
    assert json.loads(result.bindings)[0]["anomaly_count"] == 1
    assert json.loads(result.aggregate)["rows_matched"] == 1


def test_t_sdk_2_missing_keys_defaults():
    """Partial JSON body uses safe defaults."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"{}"
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = VAPIRetinaEvidenceSlice("http://localhost:8080").status("dev1")

    assert result.enabled is False
    assert json.loads(result.bindings) == []


def test_t_sdk_3_error_dict_on_failure():
    """Network failure sets error field."""
    with patch("urllib.request.urlopen", side_effect=OSError("refused")):
        result = VAPIRetinaEvidenceSlice("http://localhost:8080").status("dev1")
    assert result.error
    assert "refused" in result.error


def test_t_sdk_4_slots_dataclass():
    """RetinaEvidenceSliceResult uses slots."""
    r = RetinaEvidenceSliceResult(device_id="x")
    assert r.device_id == "x"
    assert hasattr(r, "__slots__")

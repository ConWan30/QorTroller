"""
Phase 187 — AttestationOpSecResult + VAPIAttestationOpSec SDK tests (4 tests).

Tests:
  T187-SDK-1: AttestationOpSecResult has 6 slots; enabled=False default; risk=LOW default
  T187-SDK-2: player_id kwarg in get_status URL
  T187-SDK-3: get_status populates from mock body correctly
  T187-SDK-4: error path returns safe defaults (enabled=False, risk=LOW, error set)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from unittest.mock import patch, MagicMock
import json

from vapi_sdk import AttestationOpSecResult, VAPIAttestationOpSec


# T187-SDK-1 — 6 slots, defaults
def test_1_result_has_6_slots_and_defaults():
    r = AttestationOpSecResult()
    assert r.mempool_opsec_enabled is False
    assert r.timing_disclosure_risk == "LOW"
    assert r.active_attestations == 0
    assert r.recommendation == "STANDARD_TX_OK"
    assert r.total_high_risk_events == 0
    assert r.error is None

    # Verify slots exist (dataclass with slots=True)
    assert hasattr(r, "__slots__")
    expected_slots = {
        "mempool_opsec_enabled", "timing_disclosure_risk",
        "active_attestations", "recommendation",
        "total_high_risk_events", "error",
    }
    assert expected_slots <= set(r.__slots__)


# T187-SDK-2 — player_id kwarg included in URL
def test_2_player_id_kwarg_in_url():
    client = VAPIAttestationOpSec("http://localhost:8000", api_key="testkey")
    captured_urls = []

    def fake_urlopen(url, timeout=10):
        captured_urls.append(str(url))
        m = MagicMock()
        m.__enter__ = lambda s: s
        m.__exit__ = MagicMock(return_value=False)
        m.read.return_value = json.dumps({
            "mempool_opsec_enabled": False,
            "timing_disclosure_risk": "LOW",
            "active_attestations": 0,
            "recommendation": "STANDARD_TX_OK",
            "total_high_risk_events": 0,
        }).encode()
        return m

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        client.get_status(player_id="P1")

    assert len(captured_urls) == 1
    assert "player_id=P1" in captured_urls[0]
    assert "api_key=testkey" in captured_urls[0]


# T187-SDK-3 — populates from mock body
def test_3_populates_from_body():
    client = VAPIAttestationOpSec("http://localhost:8000")
    mock_body = {
        "mempool_opsec_enabled": True,
        "timing_disclosure_risk": "HIGH",
        "active_attestations": 2,
        "recommendation": "USE_PRIVATE_MEMPOOL_OR_DELAY_TX",
        "total_high_risk_events": 5,
    }

    def fake_urlopen(url, timeout=10):
        m = MagicMock()
        m.__enter__ = lambda s: s
        m.__exit__ = MagicMock(return_value=False)
        m.read.return_value = json.dumps(mock_body).encode()
        return m

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = client.get_status()

    assert result.mempool_opsec_enabled is True
    assert result.timing_disclosure_risk == "HIGH"
    assert result.active_attestations == 2
    assert result.recommendation == "USE_PRIVATE_MEMPOOL_OR_DELAY_TX"
    assert result.total_high_risk_events == 5
    assert result.error is None


# T187-SDK-4 — error path returns safe defaults
def test_4_error_path_safe_defaults():
    client = VAPIAttestationOpSec("http://localhost:9999")  # unreachable

    with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError("refused")):
        result = client.get_status()

    assert result.mempool_opsec_enabled is False
    assert result.timing_disclosure_risk == "LOW"
    assert result.active_attestations == 0
    assert result.recommendation == "STANDARD_TX_OK"
    assert result.total_high_risk_events == 0
    assert result.error is not None
    assert len(result.error) > 0

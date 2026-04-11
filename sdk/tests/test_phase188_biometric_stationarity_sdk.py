"""
Phase 188 SDK tests — BiometricStationarityResult + VAPIBiometricStationarity.

Tests:
  T188S-1: BiometricStationarityResult has correct 6 slots with safe defaults
  T188S-2: biometric_stationarity_enabled=False default
  T188S-3: get_status populates result from HTTP response body
  T188S-4: error path returns safe defaults on network failure
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_sdk import BiometricStationarityResult, VAPIBiometricStationarity  # noqa: E402


# ---------------------------------------------------------------------------
# T188S-1: dataclass slots and defaults
# ---------------------------------------------------------------------------

def test_t188s_1_result_slots_and_defaults():
    """T188S-1: BiometricStationarityResult has correct 6 slots with safe defaults."""
    r = BiometricStationarityResult()
    assert r.biometric_stationarity_enabled is False
    assert r.p_genuine_drift == 0.0
    assert r.p_adversarial_window == 0.0
    assert r.stationarity_verdict == "STABLE"
    assert r.biometric_stationarity_confidence == 0.0
    assert r.error == ""
    # Confirm slots present
    assert hasattr(r, "__slots__")
    assert "biometric_stationarity_enabled" in r.__slots__
    assert "stationarity_verdict" in r.__slots__


# ---------------------------------------------------------------------------
# T188S-2: enabled=False default
# ---------------------------------------------------------------------------

def test_t188s_2_enabled_default_false():
    """T188S-2: biometric_stationarity_enabled=False by default (infrastructure-first)."""
    r = BiometricStationarityResult()
    assert r.biometric_stationarity_enabled is False


# ---------------------------------------------------------------------------
# T188S-3: get_status populates from body
# ---------------------------------------------------------------------------

def test_t188s_3_get_status_populates_from_body(monkeypatch):
    """T188S-3: get_status populates BiometricStationarityResult from HTTP response body."""
    import json

    _body = {
        "biometric_stationarity_enabled":   True,
        "player_id":                        "P1",
        "p_genuine_drift":                  0.72,
        "p_adversarial_window":             0.12,
        "stationarity_verdict":             "GENUINE_DRIFT",
        "biometric_stationarity_confidence": 0.72,
        "total_adversarial_alerts":         0,
        "timestamp":                        1744234567.0,
    }

    class _FakeResp:
        def read(self):
            return json.dumps(_body).encode()
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass

    import urllib.request as _req
    monkeypatch.setattr(_req, "urlopen", lambda *a, **kw: _FakeResp())

    client = VAPIBiometricStationarity(base_url="http://localhost:8000", api_key="test")
    result = client.get_status(player_id="P1")

    assert result.biometric_stationarity_enabled is True
    assert abs(result.p_genuine_drift - 0.72) < 1e-6
    assert abs(result.p_adversarial_window - 0.12) < 1e-6
    assert result.stationarity_verdict == "GENUINE_DRIFT"
    assert abs(result.biometric_stationarity_confidence - 0.72) < 1e-6
    assert result.error == ""


# ---------------------------------------------------------------------------
# T188S-4: error path returns safe defaults
# ---------------------------------------------------------------------------

def test_t188s_4_error_path_safe_defaults(monkeypatch):
    """T188S-4: get_status returns safe defaults (STABLE verdict) on network failure."""
    import urllib.request as _req

    def _raise(*a, **kw):
        raise ConnectionRefusedError("no bridge")

    monkeypatch.setattr(_req, "urlopen", _raise)

    client = VAPIBiometricStationarity(base_url="http://localhost:9999", api_key="")
    result = client.get_status()

    assert result.biometric_stationarity_enabled is False
    assert result.stationarity_verdict == "STABLE"
    assert result.p_genuine_drift == 0.0
    assert result.p_adversarial_window == 0.0
    assert result.biometric_stationarity_confidence == 0.0
    assert "no bridge" in result.error

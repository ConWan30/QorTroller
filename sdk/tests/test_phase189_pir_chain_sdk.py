"""
Phase 189 SDK tests — PIRChainResult + VAPIProtocolIntelligenceRecord.

Tests:
  T189S-1: PIRChainResult has correct 6 slots with safe defaults
  T189S-2: pir_chain_enabled=False default (infrastructure-first)
  T189S-3: get_status populates result from HTTP response body
  T189S-4: error path returns safe defaults on network failure
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_sdk import PIRChainResult, VAPIProtocolIntelligenceRecord  # noqa: E402


# ---------------------------------------------------------------------------
# T189S-1: dataclass slots and defaults
# ---------------------------------------------------------------------------

def test_t189s_1_result_slots_and_defaults():
    """T189S-1: PIRChainResult has correct 6 slots with safe defaults."""
    r = PIRChainResult()
    assert r.pir_chain_enabled is False
    assert r.total_pirs == 0
    assert r.chain_intact is True
    assert r.latest_cycle == 0
    assert r.latest_threat_forecast == ""
    assert r.error == ""
    # Confirm slots present
    assert hasattr(r, "__slots__")
    assert "pir_chain_enabled" in r.__slots__
    assert "chain_intact" in r.__slots__
    assert "latest_threat_forecast" in r.__slots__


# ---------------------------------------------------------------------------
# T189S-2: enabled=False default
# ---------------------------------------------------------------------------

def test_t189s_2_enabled_default_false():
    """T189S-2: pir_chain_enabled=False by default (infrastructure-first)."""
    r = PIRChainResult()
    assert r.pir_chain_enabled is False


# ---------------------------------------------------------------------------
# T189S-3: get_status populates from body
# ---------------------------------------------------------------------------

def test_t189s_3_get_status_populates_from_body(monkeypatch):
    """T189S-3: get_status populates PIRChainResult from HTTP response body."""
    import json

    _body = {
        "pir_chain_enabled":    True,
        "total_pirs":           2,
        "chain_intact":         True,
        "latest_cycle":         11,
        "latest_pir_hash":      "abcd1234" * 8,
        "latest_phase_produced": "189",
        "latest_threat_forecast": "pir_chain_integrity_attack",
        "latest_harness_score": 0.80,
        "records":              [],
        "timestamp":            1744234567.0,
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

    client = VAPIProtocolIntelligenceRecord(base_url="http://localhost:8000", api_key="test")
    result = client.get_status()

    assert result.pir_chain_enabled is True
    assert result.total_pirs == 2
    assert result.chain_intact is True
    assert result.latest_cycle == 11
    assert result.latest_threat_forecast == "pir_chain_integrity_attack"
    assert result.error == ""


# ---------------------------------------------------------------------------
# T189S-4: error path returns safe defaults
# ---------------------------------------------------------------------------

def test_t189s_4_error_path_safe_defaults(monkeypatch):
    """T189S-4: get_status returns safe defaults (chain_intact=True) on network failure."""
    import urllib.request as _req

    def _raise(*a, **kw):
        raise ConnectionRefusedError("no bridge")

    monkeypatch.setattr(_req, "urlopen", _raise)

    client = VAPIProtocolIntelligenceRecord(base_url="http://localhost:9999", api_key="")
    result = client.get_status()

    assert result.pir_chain_enabled is False
    assert result.total_pirs == 0
    assert result.chain_intact is True   # fail-open: chain_intact defaults True
    assert result.latest_cycle == 0
    assert result.latest_threat_forecast == ""
    assert "no bridge" in result.error

"""
Phase 115 — Epoch-Window Dual-Primitive Temporal Proof — SDK Tests (4)
"""
import pytest
from vapi_sdk import VHPDualGateResult, VAPIVHPDualGate, SDK_VERSION


# Test 1 — SDK_VERSION must be at least phase115 (may be newer after subsequent phases)
def test_sdk_version_phase115():
    assert int(SDK_VERSION.split("-phase")[1]) >= 115


# Test 2 — VHPDualGateResult still has exactly 6 slots (no new slots added)
def test_vhp_dual_gate_result_slots_unchanged():
    expected = {"device_id", "eligible", "poac_valid", "poad_valid", "mint_allowed", "error"}
    assert set(VHPDualGateResult.__slots__) == expected


# Test 3 — get_gate_log returns poad_age_seconds/epoch_window_ok from recent_logs
#           (bad URL returns error entry; entry does NOT have epoch keys since it comes
#            from error path, but SDK must not raise)
def test_vhp_dual_gate_sdk_error_path_no_raise():
    gate = VAPIVHPDualGate("http://localhost:1", "test-key")
    results = gate.get_gate_log()
    assert isinstance(results, list)
    assert len(results) == 1
    r = results[0]
    assert r.error is not None
    assert r.eligible is False


# Test 4 — VAPIVHPDualGate correctly passes epoch window query params in URL
def test_vhp_dual_gate_sdk_url_construction():
    """URL must include api_key and limit params."""
    import urllib.request as _ur
    import json as _j
    from unittest.mock import patch

    fake_body = _j.dumps({
        "dual_primitive_gate_enabled": False,
        "total_checks": 1,
        "eligible_count": 1,
        "mint_allowed_count": 1,
        "recent_logs": [
            {
                "device_id": "dev_x",
                "eligible": True,
                "poac_valid": True,
                "poad_valid": True,
                "mint_allowed": True,
                "poad_age_seconds": 3600.0,
                "epoch_window_ok": True,
            }
        ],
        "timestamp": 1711000000.0,
    }).encode()

    class _FakeResp:
        def read(self):
            return fake_body
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass

    gate = VAPIVHPDualGate("http://bridge.test", "mykey")
    captured_urls = []

    def _fake_urlopen(url, timeout=10):
        captured_urls.append(url)
        return _FakeResp()

    with patch.object(_ur, "urlopen", side_effect=_fake_urlopen):
        results = gate.get_gate_log(limit=5)

    assert len(results) == 1
    assert results[0].eligible is True
    assert len(captured_urls) == 1
    assert "api_key=mykey" in captured_urls[0]
    assert "limit=5" in captured_urls[0]

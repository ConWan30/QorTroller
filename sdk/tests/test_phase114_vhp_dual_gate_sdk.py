"""
Phase 114 — VHP Mint Dual-Primitive Gate — SDK Tests (4)
"""
import pytest
from vapi_sdk import VHPDualGateResult, VAPIVHPDualGate


# Test 1 — VHPDualGateResult has exactly 6 slots
def test_vhp_dual_gate_result_slots():
    expected = {"device_id", "eligible", "poac_valid", "poad_valid", "mint_allowed", "error"}
    assert set(VHPDualGateResult.__slots__) == expected


# Test 2 — VAPIVHPDualGate initialises without error
def test_vhp_dual_gate_sdk_init():
    gate = VAPIVHPDualGate("http://localhost:18080", "test-key")
    assert gate._base == "http://localhost:18080"
    assert gate._key == "test-key"


# Test 3 — bad URL → list with 1 error entry (error != None)
def test_vhp_dual_gate_sdk_bad_url_error():
    gate = VAPIVHPDualGate("http://localhost:1", "test-key")
    results = gate.get_gate_log()
    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0].error is not None


# Test 4 — error entry has all False fields
def test_vhp_dual_gate_sdk_error_defaults():
    gate = VAPIVHPDualGate("http://localhost:1", "test-key")
    r = gate.get_gate_log()[0]
    assert r.eligible is False
    assert r.poac_valid is False
    assert r.mint_allowed is False

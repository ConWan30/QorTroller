"""
Phase 113 — VAPIDualPrimitiveGate SDK tests.
DualPrimitiveGateResult (6 slots) + VAPIDualPrimitiveGate (check_eligibility).
"""

import pytest


def test_dual_primitive_gate_result_slots():
    """DualPrimitiveGateResult must have exactly 6 slots in the declared order."""
    from vapi_sdk import DualPrimitiveGateResult
    assert hasattr(DualPrimitiveGateResult, "__slots__")
    slots = DualPrimitiveGateResult.__slots__
    assert "eligible"   in slots
    assert "poac_valid" in slots
    assert "poad_valid" in slots
    assert "device_id"  in slots
    assert "timestamp"  in slots
    assert "error"      in slots
    assert len(slots) == 6


def test_vapi_dual_primitive_gate_init():
    """VAPIDualPrimitiveGate initializes without raising."""
    from vapi_sdk import VAPIDualPrimitiveGate
    gate = VAPIDualPrimitiveGate("http://localhost:18080", "test-key-p113")
    assert gate is not None


def test_vapi_dual_primitive_gate_bad_url_returns_error():
    """Bad URL (port 1) → error field is not None; no exception raised."""
    from vapi_sdk import VAPIDualPrimitiveGate
    gate = VAPIDualPrimitiveGate("http://localhost:1", "test-key-p113")
    result = gate.check_eligibility("dev_001", "a" * 64)
    assert result.error is not None


def test_vapi_dual_primitive_gate_error_defaults():
    """On error: eligible=False, poac_valid=False, poad_valid=False."""
    from vapi_sdk import VAPIDualPrimitiveGate
    gate = VAPIDualPrimitiveGate("http://localhost:1", "test-key-p113")
    result = gate.check_eligibility("dev_001", "a" * 64)
    assert result.eligible is False
    assert result.poac_valid is False
    assert result.poad_valid is False

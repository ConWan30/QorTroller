"""
Phase 198 — Biometric TTL Decay Scaling SDK tests.

BiometricTTLScalingResult slots + VAPIBiometricTTLScaling fail-closed behaviour.
"""
import pytest


# ---------------------------------------------------------------------------
# T198S-1: BiometricTTLScalingResult has all required slots with correct defaults
# ---------------------------------------------------------------------------

def test_t198s_1_result_slots():
    from vapi_sdk import BiometricTTLScalingResult
    r = BiometricTTLScalingResult(
        effective_ttl_days=180.0,
        base_ttl_days=90.0,
        scaling_factor=2.0,
        mean_decay_factor=1.0,
        scaling_enabled=True,
    )
    assert r.effective_ttl_days == 180.0
    assert r.base_ttl_days == 90.0
    assert abs(r.scaling_factor - 2.0) < 0.001
    assert r.scaling_enabled is True
    assert r.error is None  # default


# ---------------------------------------------------------------------------
# T198S-2: scaling_enabled=False returns base_ttl unchanged (disabled default)
# ---------------------------------------------------------------------------

def test_t198s_2_scaling_disabled_result():
    from vapi_sdk import BiometricTTLScalingResult
    r = BiometricTTLScalingResult(
        effective_ttl_days=90.0,
        base_ttl_days=90.0,
        scaling_factor=1.0,
        mean_decay_factor=0.5,
        scaling_enabled=False,
    )
    assert r.scaling_enabled is False
    assert abs(r.effective_ttl_days - r.base_ttl_days) < 0.001
    assert abs(r.scaling_factor - 1.0) < 0.001


# ---------------------------------------------------------------------------
# T198S-3: network error → fail-closed (scaling_enabled=False, error set)
# ---------------------------------------------------------------------------

def test_t198s_3_network_error_fail_closed():
    from vapi_sdk import VAPIBiometricTTLScaling
    ttl = VAPIBiometricTTLScaling("http://127.0.0.1:1", "key")
    result = ttl.get_status()
    assert result.scaling_enabled is False  # fail-closed
    assert result.error is not None
    assert abs(result.effective_ttl_days - 90.0) < 0.001  # safe default


# ---------------------------------------------------------------------------
# T198S-4: clamped max (4×) and min (0.25×) round-trip through slots
# ---------------------------------------------------------------------------

def test_t198s_4_clamp_values_round_trip():
    from vapi_sdk import BiometricTTLScalingResult
    # Max clamp: decay=2.0 → factor=4.0
    r_max = BiometricTTLScalingResult(
        effective_ttl_days=360.0,
        base_ttl_days=90.0,
        scaling_factor=4.0,
        mean_decay_factor=2.0,
        scaling_enabled=True,
    )
    assert abs(r_max.effective_ttl_days - 360.0) < 0.001
    assert abs(r_max.scaling_factor - 4.0) < 0.001

    # Min clamp: decay=0.0 → factor=0.25
    r_min = BiometricTTLScalingResult(
        effective_ttl_days=22.5,
        base_ttl_days=90.0,
        scaling_factor=0.25,
        mean_decay_factor=0.0,
        scaling_enabled=True,
    )
    assert abs(r_min.effective_ttl_days - 22.5) < 0.001
    assert abs(r_min.scaling_factor - 0.25) < 0.001

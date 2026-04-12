"""
Phase 199 SDK tests — ProbeGateConfigResult / VAPIProbeGateConfig
                      TremorRestingProbeResult / VAPITremorRestingProbe
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))

from vapi_sdk import (
    ProbeGateConfigResult,
    VAPIProbeGateConfig,
    TremorRestingProbeResult,
    VAPITremorRestingProbe,
)


# ---------------------------------------------------------------------------
# T199S-1: ProbeGateConfigResult has all required slots
# ---------------------------------------------------------------------------

def test_t199s_1_probe_gate_config_result_slots():
    """ProbeGateConfigResult must have all 5 required fields."""
    r = ProbeGateConfigResult(
        all_pairs_gate_enabled=True,
        min_separation_ratio=0.70,
        prototype_mode_active=False,
        separation_ok_threshold=0.70,
    )
    assert r.all_pairs_gate_enabled is True
    assert abs(r.min_separation_ratio - 0.70) < 1e-9
    assert r.prototype_mode_active is False
    assert abs(r.separation_ok_threshold - 0.70) < 1e-9
    assert r.error is None


# ---------------------------------------------------------------------------
# T199S-2: VAPIProbeGateConfig returns fail-closed result on network error
# ---------------------------------------------------------------------------

def test_t199s_2_probe_gate_config_fail_closed_on_network_error():
    """Network error must produce fail-closed result:
    all_pairs_gate_enabled=True (production default enforced), error set."""
    client = VAPIProbeGateConfig("http://127.0.0.1:19999", "test_key")
    result = client.get_status()
    assert isinstance(result, ProbeGateConfigResult)
    assert result.all_pairs_gate_enabled is True    # fail-closed: production mode
    assert result.prototype_mode_active is False
    assert result.error is not None


# ---------------------------------------------------------------------------
# T199S-3: TremorRestingProbeResult has all required slots
# ---------------------------------------------------------------------------

def test_t199s_3_tremor_resting_probe_result_slots():
    """TremorRestingProbeResult must have all 9 required fields."""
    r = TremorRestingProbeResult(
        probe_type="tremor_resting",
        enabled=False,
        capture_instructions="Hold still for 30 seconds",
        primary_features=["tremor_peak_hz", "tremor_band_power"],
        suppressed_features=["stick_autocorr_lag1"],
        target_duration_s=30,
        sessions_needed_per_player=5,
        all_pairs_gate_enabled=True,
        prototype_mode_active=False,
    )
    assert r.probe_type == "tremor_resting"
    assert r.enabled is False
    assert r.target_duration_s == 30
    assert r.sessions_needed_per_player == 5
    assert r.all_pairs_gate_enabled is True
    assert r.prototype_mode_active is False
    assert r.error is None


# ---------------------------------------------------------------------------
# T199S-4: VAPITremorRestingProbe returns fail-closed result on network error
# ---------------------------------------------------------------------------

def test_t199s_4_tremor_resting_probe_fail_closed_on_network_error():
    """Network error must produce fail-closed result: enabled=False, error set."""
    client = VAPITremorRestingProbe("http://127.0.0.1:19999", "test_key")
    result = client.get_status()
    assert isinstance(result, TremorRestingProbeResult)
    assert result.enabled is False
    assert result.probe_type == "tremor_resting"
    assert result.target_duration_s == 30
    assert result.sessions_needed_per_player == 5
    assert result.all_pairs_gate_enabled is True    # fail-closed: production default
    assert result.error is not None

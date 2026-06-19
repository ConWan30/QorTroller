"""Tests for daemon_health_monitor pure-function probes."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "bridge"))

from vapi_bridge.daemon_health_monitor import (  # noqa: E402
    HealthMonitorInput,
    HealthSeverity,
    HealthState,
    detect_device_id_firmware_drift,
    run_health_monitor,
)


def test_healthy_input_zero_findings():
    inp = HealthMonitorInput(
        gic_hours_since_last_link=1.0,
        claude_md_drift_count=0,
        frozen_ref_violation_count=0,
        invariant_count_live=176,
        device_id_formula_conflict=False,
    )
    assert run_health_monitor(inp) == []


def test_gic_stall_high():
    inp = HealthMonitorInput(gic_hours_since_last_link=48.0, invariant_count_live=176)
    findings = run_health_monitor(inp)
    gic = [f for f in findings if f.probe_id == "GIC-STALL"]
    assert len(gic) == 1
    assert gic[0].severity == HealthSeverity.HIGH


def test_device_id_conflict_critical():
    inp = HealthMonitorInput(device_id_formula_conflict=True)
    findings = run_health_monitor(inp)
    assert any(f.probe_id == "F-FW-2" and f.severity == HealthSeverity.CRITICAL for f in findings)


def test_device_id_firmware_drift_medium():
    inp = HealthMonitorInput(device_id_firmware_drift=True)
    findings = run_health_monitor(inp)
    drift = [f for f in findings if f.probe_id == "F-FW-2-DRIFT"]
    assert len(drift) == 1
    assert drift[0].severity == HealthSeverity.MEDIUM
    assert drift[0].state == HealthState.DRIFTED
    assert "atca_signer.c" in drift[0].evidence
    assert "Phase 1B" in drift[0].proposed_action


def test_detect_firmware_drift_on_live_repo():
    assert detect_device_id_firmware_drift(REPO_ROOT) is True


def test_invariant_drift():
    inp = HealthMonitorInput(invariant_count_live=174, invariant_count_baseline=176)
    findings = run_health_monitor(inp)
    assert any(f.probe_id == "INV-COUNT" and f.state == HealthState.DRIFTED for f in findings)

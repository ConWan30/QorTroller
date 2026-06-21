"""CCO Phase D — dormant CCO → PoEP bridge tests."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from vapi_bridge.cco_poep_bridge import (
    PoepRunnerInputs,
    assemble_poep_presence_status,
    build_poep_runner_inputs,
    build_poep_telemetry_from_probe,
    describe_poep_telemetry_readiness,
    resolve_capability_report_for_session,
)


@dataclass(frozen=True)
class _FakeReport:
    challenge_type_candidate: str = "adaptive_force"
    presence_ceiling_candidate: str = "P-T3"
    characterization_status: str = "PARTIAL_EDGE_ONLY"
    profile_id: str = "sony_dualshock_edge_v1"
    t2_t3_engine: str = "POEP"
    policy_ref: str = "CCO_T0_POLICY_v1_OPTION_C"


class TestBuildPoepRunnerInputs:
    def test_maps_capability_report(self):
        inp = build_poep_runner_inputs(
            _FakeReport(), device_id="abc123",
        )
        assert inp.challenge_type == "adaptive_force"
        assert inp.presence_ceiling_candidate == "P-T3"
        assert inp.device_id == "abc123"

    def test_none_report_fail_open(self):
        inp = build_poep_runner_inputs(None)
        assert inp.challenge_type is None
        assert inp.t2_t3_engine == "POEP"


class TestAssemblePoepPresenceStatus:
    def test_dormant_never_emits_present(self):
        poep = assemble_poep_presence_status(
            poep_enabled=False,
            capability_report=_FakeReport(),
            l6b_probe_count=59,
            l6b_gate_reached=True,
        )
        assert poep["dormant"] is True
        assert poep["enabled"] is False
        assert poep["verdict"] is None
        assert poep["challenge_type"] == "adaptive_force"
        assert poep["runner"]["profile_id"] == "sony_dualshock_edge_v1"

    def test_uncharacterized_challenge_type_in_runner(self):
        rep = _FakeReport(
            challenge_type_candidate="button_timing",
            characterization_status="UNCHARACTERIZED",
            presence_ceiling_candidate="P-T0",
        )
        poep = assemble_poep_presence_status(
            poep_enabled=False,
            capability_report=rep,
        )
        assert poep["challenge_type"] == "button_timing"
        assert poep["characterization_status"] == "UNCHARACTERIZED"

    def test_l6b_pending_status_string(self):
        poep = assemble_poep_presence_status(
            poep_enabled=False,
            capability_report=None,
            l6b_probe_count=12,
            l6b_gate_reached=False,
        )
        assert "pending L6B calibration" in poep["status"]
        assert poep["l6b_probe_count"] == 12


class TestBuildPoepTelemetryFromProbe:
    def test_rumble_imu_maps_probe_row(self):
        tel = build_poep_telemetry_from_probe(
            "rumble_imu",
            {
                "latency_ms": 185.5,
                "accel_delta_peak": 1200.0,
                "classification": "HUMAN",
            },
        )
        assert tel["reaction_features"]["reaction_latency_ms"] == 185.5
        assert tel["device_auth"]["classification"] == "HUMAN"
        assert tel["device_auth"]["accel_delta_peak"] == 1200.0

    def test_adaptive_force_liveness_only_no_device_auth(self):
        tel = build_poep_telemetry_from_probe(
            "adaptive_force",
            {"latency_ms": 290.0},
        )
        assert tel["reaction_features"]["reaction_latency_ms"] == 290.0
        assert tel["device_auth"] is None

    def test_missing_latency_returns_none(self):
        assert build_poep_telemetry_from_probe("rumble_imu", {}) == {
            "device_auth": None,
            "reaction_features": None,
        }


class TestResolveCapabilityReportForSession:
    def test_device_profile_id_dualsense_rumble_imu(self):
        from vapi_bridge.config import Config

        cfg = Config(device_profile_id="sony_dualsense_v1")
        rep = resolve_capability_report_for_session(cfg=cfg)
        assert rep.profile_id == "sony_dualsense_v1"
        assert rep.challenge_type_candidate == "rumble_imu"

    def test_default_edge_adaptive_force(self):
        from vapi_bridge.config import Config

        rep = resolve_capability_report_for_session(cfg=Config())
        assert rep.challenge_type_candidate == "adaptive_force"


class TestDescribePoepTelemetryReadiness:
    def test_rumble_imu_ready(self):
        tel = describe_poep_telemetry_readiness(
            "rumble_imu",
            {"latency_ms": 180.0, "accel_delta_peak": 900.0},
            device_auth={"classification": "HUMAN"},
            reaction_features={"reaction_latency_ms": 180.0},
        )
        assert tel["ready"] is True
        assert tel["gap"] is None

    def test_adaptive_force_honest_gap(self):
        tel = describe_poep_telemetry_readiness(
            "adaptive_force",
            {"latency_ms": 290.0},
            reaction_features={"reaction_latency_ms": 290.0},
        )
        assert tel["ready"] is False
        assert tel["gap"] == "adaptive_force_requires_live_trigger_signature"

    def test_assemble_poep_includes_telemetry_block(self):
        poep = assemble_poep_presence_status(
            poep_enabled=True,
            capability_report=_FakeReport(challenge_type_candidate="adaptive_force"),
            device_auth=None,
            reaction_features={"reaction_latency_ms": 290.0},
            latest_probe={"latency_ms": 290.0},
        )
        assert poep["telemetry"]["ready"] is False
        assert "adaptive_force_requires_live_trigger_signature" in poep["status"]

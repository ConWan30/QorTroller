"""CCO Phase B — L6B T0 wiring pure-module tests."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from vapi_bridge.cco_l6b_wiring import (
    L6bSkipReason,
    REFLEX_OBSERVED,
    assemble_cco_session_status,
    check_l6b_applicability,
    compute_l6b_probe_diagnostic,
    evaluate_l6b_r2_quiet_gate,
    format_l6b_skip_log,
    map_l6b_classification_to_reflex_verdict,
)
from controller.l6b_reflex_analyzer import L6bReflexAnalyzer


@dataclass(frozen=True)
class _FakeReport:
    t0_engine: str = "L6B"
    capabilities: dict[str, Any] | None = None
    profile_id: str = "sony_dualshock_edge_v1"
    policy_ref: str = "CCO_T0_POLICY_v1_OPTION_C"
    presence_ceiling_candidate: str = "P-T3"
    identity_class: str = "UNKNOWN"
    challenge_type_candidate: str = "adaptive_force"


def _edge_caps() -> dict[str, Any]:
    return {
        "has_accelerometer": True,
        "has_adaptive_triggers": True,
        "has_gyroscope": True,
    }


class TestL6bApplicability:
    def test_edge_full_stack_applicable(self):
        app = check_l6b_applicability(
            _FakeReport(capabilities=_edge_caps()),
            l6_driver_present=True,
            dualsense_handle_present=True,
        )
        assert app.applicable is True
        assert app.skip_reason is None

    def test_no_imu_xbox_class(self):
        app = check_l6b_applicability(
            _FakeReport(
                capabilities={
                    "has_accelerometer": False,
                    "has_adaptive_triggers": False,
                },
            ),
            l6_driver_present=True,
            dualsense_handle_present=True,
        )
        assert app.applicable is False
        assert app.skip_reason == L6bSkipReason.NO_IMU

    def test_no_adaptive_dualsense_class(self):
        app = check_l6b_applicability(
            _FakeReport(
                capabilities={
                    "has_accelerometer": True,
                    "has_adaptive_triggers": False,
                },
            ),
            l6_driver_present=True,
            dualsense_handle_present=True,
        )
        assert app.applicable is False
        assert app.skip_reason == L6bSkipReason.NO_ADAPTIVE_TRIGGER_PATH

    def test_dualsense_rumble_imu_applicable_without_adaptive(self):
        app = check_l6b_applicability(
            _FakeReport(
                capabilities={
                    "has_accelerometer": True,
                    "has_adaptive_triggers": False,
                    "has_gyroscope": True,
                },
                profile_id="sony_dualsense_v1",
                challenge_type_candidate="rumble_imu",
                presence_ceiling_candidate="P-T1",
            ),
            l6_driver_present=True,
            dualsense_handle_present=True,
        )
        assert app.applicable is True
        assert app.skip_reason is None

    def test_no_l6_driver(self):
        app = check_l6b_applicability(
            _FakeReport(capabilities=_edge_caps()),
            l6_driver_present=False,
            dualsense_handle_present=True,
        )
        assert app.skip_reason == L6bSkipReason.NO_L6_DRIVER

    def test_no_dualsense_handle(self):
        app = check_l6b_applicability(
            _FakeReport(capabilities=_edge_caps()),
            l6_driver_present=True,
            dualsense_handle_present=False,
        )
        assert app.skip_reason == L6bSkipReason.NO_DUALSENSE_HANDLE

    def test_no_capability_report(self):
        app = check_l6b_applicability(
            None,
            l6_driver_present=True,
            dualsense_handle_present=True,
        )
        assert app.skip_reason == L6bSkipReason.NO_CAPABILITY_REPORT

    def test_t0_engine_mismatch(self):
        app = check_l6b_applicability(
            _FakeReport(t0_engine="OTHER", capabilities=_edge_caps()),
            l6_driver_present=True,
            dualsense_handle_present=True,
        )
        assert app.skip_reason == L6bSkipReason.T0_ENGINE_MISMATCH


class TestReflexVerdictMapping:
    def test_human_maps_to_reflex_observed(self):
        assert map_l6b_classification_to_reflex_verdict("HUMAN") == REFLEX_OBSERVED

    @pytest.mark.parametrize("classification", ["BOT", "INCONCLUSIVE", "NO_RESPONSE"])
    def test_non_human_no_reflex_verdict(self, classification: str):
        assert map_l6b_classification_to_reflex_verdict(classification) is None


@dataclass(frozen=True)
class _FakeFrame:
    r2_trigger: int = 0


class TestL6bR2QuietGate:
    def test_dispatch_allowed_when_r2_below_threshold(self):
        frames = [_FakeFrame(0), _FakeFrame(8), _FakeFrame(14)]
        quiet_ok, r2_at_probe = evaluate_l6b_r2_quiet_gate(frames, quiet_threshold=15)
        assert quiet_ok is True
        assert r2_at_probe == 14

    def test_dispatch_blocked_when_r2_at_or_above_threshold(self):
        frames = [_FakeFrame(0), _FakeFrame(90), _FakeFrame(14)]
        quiet_ok, r2_at_probe = evaluate_l6b_r2_quiet_gate(frames, quiet_threshold=15)
        assert quiet_ok is False
        assert r2_at_probe == 90

    def test_empty_frames_not_quiet(self):
        quiet_ok, r2_at_probe = evaluate_l6b_r2_quiet_gate([], quiet_threshold=15)
        assert quiet_ok is False
        assert r2_at_probe is None


class TestSkipLogFormat:
    def test_format_skip_log(self):
        assert format_l6b_skip_log(L6bSkipReason.NO_IMU) == "L6B_SKIPPED/NO_IMU"


class TestAssembleCcoSessionStatus:
    def test_edge_connected_populates_oracle_and_applicability(self):
        cco = assemble_cco_session_status(
            capability_report=_FakeReport(capabilities=_edge_caps()),
            l6b_calibration_progress={
                "probe_count": 59,
                "target_n": 50,
                "gate_reached": True,
                "reflex_verdict_distribution": {"REFLEX_OBSERVED": 38},
                "latest_probe": {
                    "reflex_verdict": "REFLEX_OBSERVED",
                    "classification": "HUMAN",
                },
            },
            l6b_enabled=True,
            controller_connected=True,
        )
        assert cco["t0_engine"] == "L6B"
        assert cco["presence_ceiling_candidate"] == "P-T3"
        assert cco["profile_id"] == "sony_dualshock_edge_v1"
        assert cco["l6b_applicable"] is True
        assert cco["l6b_skip"] is None
        assert cco["reflex_verdict"] == REFLEX_OBSERVED
        assert cco["calibration"]["gate_reached"] is True

    def test_no_capability_report_honest_empty_oracle(self):
        cco = assemble_cco_session_status(
            capability_report=None,
            l6b_calibration_progress={"probe_count": 0, "target_n": 50, "gate_reached": False},
            l6b_enabled=False,
            controller_connected=False,
        )
        assert cco["t0_engine"] is None
        assert cco["presence_ceiling_candidate"] is None
        assert cco["l6b_applicable"] is False
        assert cco["calibration"]["probe_count"] == 0


class TestL6bProbeDiagnostic:
    def test_true_and_reflex_latency_from_t_mono(self):
        probe_ts = 1000.0
        pre = [{"ax": 100.0, "ay": 0.0, "az": 0.0}]
        post = [
            {"ax": 110.0, "ay": 0.0, "az": 0.0, "t_mono": 1000.05},
            {"ax": 160.0, "ay": 0.0, "az": 0.0, "t_mono": 1000.20},
            {"ax": 700.0, "ay": 0.0, "az": 0.0, "t_mono": 1000.25},
        ]
        diag = compute_l6b_probe_diagnostic(pre, post, probe_ts, legacy_latency_ms=16.0)
        assert diag.precursor_gap_ms == pytest.approx(200.0)
        assert diag.true_latency_ms == pytest.approx(250.0)
        assert diag.reflex_gap_ms == pytest.approx(50.0)
        assert diag.crossing_index == 2
        assert diag.precursor_index == 1

    def test_t_mono_keys_do_not_change_legacy_classification(self):
        probe_ts = 1000.0
        pre = [{"ax": 0.0, "ay": 0.0, "az": 0.0}]
        post_plain = [{"ax": 600.0, "ay": 0.0, "az": 0.0}] * 11
        post_mono = [
            {"ax": 600.0, "ay": 0.0, "az": 0.0, "t_mono": 1000.0 + i * 0.008}
            for i in range(11)
        ]
        analyzer = L6bReflexAnalyzer()
        r_plain = analyzer.analyze(pre, post_plain, probe_ts)
        r_mono = analyzer.analyze(pre, post_mono, probe_ts)
        assert r_plain.classification == r_mono.classification
        assert r_plain.latency_ms == r_mono.latency_ms

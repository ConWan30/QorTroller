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
    check_l6b_applicability,
    format_l6b_skip_log,
    map_l6b_classification_to_reflex_verdict,
)


@dataclass(frozen=True)
class _FakeReport:
    t0_engine: str = "L6B"
    capabilities: dict[str, Any] | None = None
    profile_id: str = "sony_dualshock_edge_v1"
    policy_ref: str = "CCO_T0_POLICY_v1_OPTION_C"


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


class TestSkipLogFormat:
    def test_format_skip_log(self):
        assert format_l6b_skip_log(L6bSkipReason.NO_IMU) == "L6B_SKIPPED/NO_IMU"

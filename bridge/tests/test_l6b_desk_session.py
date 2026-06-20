"""Tests for operator-fired L6B desk session helpers."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from vapi_bridge.l6b_desk_session import (
    DeskProbeConfig,
    DeskProbeOutcome,
    accel_report_from_snapshot,
    analyze_desk_probe,
    desk_device_id,
    enrich_diagnostic_json,
    expected_post_frames,
)


@dataclass
class _Snap:
    accel_x: float = 0.0
    accel_y: float = 0.0
    accel_z: float = 1.0


class TestAccelReport:
    def test_scales_g_to_lsb(self):
        row = accel_report_from_snapshot(_Snap(accel_x=0.1), accel_scale=8192.0, t_mono=100.0)
        assert row["ax"] == pytest.approx(819.2)
        assert row["t_mono"] == 100.0


class TestAnalyzeDeskProbe:
    def test_human_reflex_with_t_mono(self):
        pre = [{"ax": 0.0, "ay": 0.0, "az": 8192.0, "t_mono": 1.0}] * 10
        post = []
        t0 = 2.0
        for i in range(40):
            mag = 8192.0 if i < 5 else 9000.0
            post.append({"ax": 0.0, "ay": 0.0, "az": mag, "t_mono": t0 + 0.1 + i * 0.008})
        cfg = DeskProbeConfig(response_threshold_lsb=500.0)
        result, diag_json = analyze_desk_probe(pre, post, t0, cfg)
        diag = json.loads(diag_json)
        assert result.accel_delta_peak >= 500.0
        assert diag["true_latency_ms"] is not None
        assert diag["true_latency_ms"] >= 80.0


class TestDeskDeviceId:
    def test_sanitizes_player(self):
        assert desk_device_id("P1") == "desk-P1"
        assert desk_device_id(" desk test ") == "desk-desk_test"


class TestEnrichDiagnostic:
    def test_adds_session_meta(self):
        base = '{"probe_ts":1.0,"samples":[]}'
        out = enrich_diagnostic_json(base, session_meta={"protocol": "still"})
        payload = json.loads(out)
        assert payload["session_meta"]["protocol"] == "still"


class TestDeskProbeOutcome:
    def test_summary_includes_true_latency(self):
        from controller.l6b_reflex_analyzer import L6bReflexResult

        result = L6bReflexResult(
            latency_ms=120.0,
            accel_delta_peak=600.0,
            classification="HUMAN",
            confidence=0.9,
            probe_ts=1.0,
            valid=True,
        )
        diag = json.dumps(
            {
                "true_latency_ms": 115.0,
                "precursor_gap_ms": 20.0,
                "reflex_gap_ms": 95.0,
                "response_threshold_lsb": 500,
                "probe_r2_force": 128,
                "probe_mode": "rigid",
                "probe_hold_ms": 200,
            }
        )
        outcome = DeskProbeOutcome(
            probe_index=1,
            protocol="still",
            player="P1",
            device_id="desk-P1",
            result=result,
            diagnostic_json=diag,
            reflex_verdict="REFLEX_OBSERVED",
            probe_log_id=42,
            r2_at_probe=0,
            pre_sample_count=50,
            post_sample_count=50,
        )
        text = "\n".join(outcome.summary_lines())
        assert "true_latency_ms=115.0" in text
        assert "peak_delta=600.0" in text


class TestExpectedPostFrames:
    def test_400ms_at_8ms(self):
        assert expected_post_frames(400.0, 0.008) == 50

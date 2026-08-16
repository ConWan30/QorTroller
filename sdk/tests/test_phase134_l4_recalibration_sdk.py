"""Phase 134 — L4 Recalibration SDK Tests (4 tests)"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT / "sdk"))

from vapi_sdk import L4RecalibrationResult, VAPIL4Recalibration, SDK_VERSION


def test_1_l4_recalibration_result_7_slots():
    r = L4RecalibrationResult()
    assert r.in_progress is False
    assert r.sessions_processed == 0
    assert abs(r.new_anomaly_threshold - 7.009) < 0.001
    assert abs(r.new_continuity_threshold - 5.367) < 0.001
    assert r.stale is True
    assert r.last_run_ts == 0.0
    assert r.error is None


def test_2_vapil4_recalibration_init():
    client = VAPIL4Recalibration(base_url="http://localhost:9999", api_key="k")
    assert client._base == "http://localhost:9999"
    assert client._key == "k"


def test_3_get_status_bad_url_never_raises():
    client = VAPIL4Recalibration(base_url="http://localhost:19999", api_key="")
    result = client.get_status()
    assert isinstance(result, L4RecalibrationResult)
    assert result.error is not None
    assert result.in_progress is False


def test_4_sdk_version_phase135():
    # SDK_VERSION bumped to phase135 in same session
    # SDK_VERSION moved past per-phase numeric suffixes (3.1.1-phase-o3-zkba-track1-g4-validator-sdk); keep the
# monotonic-floor intent instead of pinning a dead format.

    _semver = tuple(int(p) for p in SDK_VERSION.split("-")[0].split(".")[:3])

    assert _semver >= (3, 1, 0), SDK_VERSION

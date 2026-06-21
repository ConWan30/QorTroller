"""Tests for the L9 Fusion v2 store mixin + config flags (Phase 5 wiring)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from bridge.vapi_bridge.config import Config  # noqa: E402
from bridge.vapi_bridge.store import Store  # noqa: E402


def _store():
    d = tempfile.mkdtemp()
    return Store(os.path.join(d, "l9fusion.db"))


def test_l9_fusion_table_created_and_empty():
    s = _store()
    status = s.get_l9_fusion_status("dev1")
    assert status["total_rows"] == 0 and status["entries"] == []


def test_insert_and_read_back():
    s = _store()
    rid = s.insert_l9_fusion_event(
        device_id="dev1", fusion_verdict="LIVE_COHERENT", record_hash_hex="abcd",
        coupling_score=0.85, negative_control=0.10, decoupled_energy=0.05,
        coherence_verdict="COHERENT", coherence_ratio=1.0, continuous_axis="COUPLED_CLEAN",
        capture_telemetry_json=json.dumps({"ema_fps": 59.5, "changes": 1}),
        report_json=json.dumps({"verdict": "LIVE_COHERENT"}),
    )
    assert rid > 0
    status = s.get_l9_fusion_status("dev1")
    assert status["total_rows"] == 1
    assert status["latest_fusion_verdict"] == "LIVE_COHERENT"
    assert status["latest_continuous_axis"] == "COUPLED_CLEAN"
    assert status["latest_capture_telemetry"]["ema_fps"] == 59.5


def test_device_scoping_and_global():
    s = _store()
    s.insert_l9_fusion_event(device_id="A", fusion_verdict="LIVE_COHERENT")
    s.insert_l9_fusion_event(device_id="B", fusion_verdict="REPLAY_OR_RELAY")
    assert s.get_l9_fusion_status("A")["total_rows"] == 1
    assert s.get_l9_fusion_status("B")["latest_fusion_verdict"] == "REPLAY_OR_RELAY"
    assert s.get_l9_fusion_status(None)["total_rows"] == 2  # global


def test_config_flags_present_and_defaults():
    cfg = Config()
    assert hasattr(cfg, "l9_fusion_v2_enabled") and cfg.l9_fusion_v2_enabled is False
    assert cfg.adaptive_capture_enabled is True
    assert cfg.l9_fusion_coherence_threshold == 0.70
    assert cfg.l9_fusion_neg_control_gap == 0.15

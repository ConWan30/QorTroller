"""Tests for bridge/vapi_bridge/retina_controller_embedder.py (Phase A)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

try:
    from retina import Event
    _HAS_RETINA = True
except ImportError:
    _HAS_RETINA = False

from vapi_bridge.retina_controller_embedder import (
    CONTROLLER_VEC_DIM,
    EVT_STICK_RADIAL_JUMP,
    EVT_TRAJECTORY_ANOMALOUS,
    EVT_TRIGGER_ONSET,
    embed_controller_window,
    snap_to_feature_vector,
    snaps_from_session_json,
    synthetic_snaps,
    write_events_jsonl,
)


@unittest.skipUnless(_HAS_RETINA, "trio-retina not installed")
class TestRetinaControllerEmbedder(unittest.TestCase):

    def test_feature_vector_dim(self):
        snap = synthetic_snaps(1)[0]
        v = snap_to_feature_vector(snap)
        self.assertEqual(v.shape, (CONTROLLER_VEC_DIM,))

    def test_trigger_onset_event(self):
        snaps = [
            {"right_stick_x": 128, "right_stick_y": 128, "l2_trigger": 0, "r2_trigger": 0,
             "left_stick_x": 128, "left_stick_y": 128,
             "gyro_x": 0, "gyro_y": 0, "gyro_z": 0, "accel_x": 0, "accel_y": 0, "accel_z": 1},
            {"right_stick_x": 128, "right_stick_y": 128, "l2_trigger": 128, "r2_trigger": 0,
             "left_stick_x": 128, "left_stick_y": 128,
             "gyro_x": 0, "gyro_y": 0, "gyro_z": 0, "accel_x": 0, "accel_y": 0, "accel_z": 1},
        ]
        result = embed_controller_window(snaps, source_id="test")
        types = [e.type for e in result.events]
        self.assertIn(EVT_TRIGGER_ONSET, types)
        self.assertEqual(result.world_state.entities[0].type, "game_controller")

    def test_aimbot_snap_trajectory_anomaly(self):
        snaps = synthetic_snaps(150, aimbot_snap_at=100)
        result = embed_controller_window(snaps, dynamics_horizon=5)
        traj = [e for e in result.events if e.type == EVT_TRAJECTORY_ANOMALOUS]
        self.assertGreater(len(traj), 0, "expected dynamics violation on aimbot snap")

    def test_radial_jump_on_large_delta(self):
        snaps = synthetic_snaps(10)
        snaps[-1]["right_stick_x"] = 250
        result = embed_controller_window(snaps)
        jumps = [e for e in result.events if e.type == EVT_STICK_RADIAL_JUMP]
        self.assertGreaterEqual(len(jumps), 1)

    def test_jsonl_roundtrip(self):
        snaps = synthetic_snaps(80)
        result = embed_controller_window(snaps)
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "events.jsonl")
            n = write_events_jsonl(result.events, path)
            self.assertEqual(n, len(result.events))
            lines = Path(path).read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), len(result.events))
            parsed = json.loads(lines[0])
            self.assertIn("type", parsed)
            self.assertIn("src", parsed)

    def test_snaps_from_session_json_shape(self):
        data = {
            "reports": [
                {"features": {"right_stick_x": 100, "accel_z": 1.0}},
                {"features": {"right_stick_x": 110, "accel_z": 1.0}},
            ]
        }
        snaps = snaps_from_session_json(data)
        self.assertEqual(len(snaps), 2)
        self.assertEqual(snaps[0]["right_stick_x"], 100)

    def test_empty_window_fail_open(self):
        result = embed_controller_window([])
        self.assertEqual(len(result.events), 0)
        self.assertEqual(result.latent_vec.shape, (CONTROLLER_VEC_DIM,))


if __name__ == "__main__":
    unittest.main()

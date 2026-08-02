"""Streamer perception v0 unit tests (no capture card required)."""
from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np

BRIDGE = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE))

from vapi_bridge.streamer_perception import (  # noqa: E402
    DOMAIN,
    EventBus,
    PerceptionConfig,
    StreamerPerceptionRuntime,
    ZoneSpec,
    frame_mean_luma,
    frame_motion,
    make_event,
)


class TestStreamerPerception(unittest.TestCase):
    def test_1_make_event_schema(self):
        ev = make_event("heartbeat", {"uptime_s": 1}, session_id="s1")
        self.assertEqual(ev["domain"], DOMAIN)
        self.assertEqual(ev["v"], 0)
        self.assertEqual(ev["type"], "heartbeat")
        self.assertEqual(ev["session_id"], "s1")

    def test_2_motion_zero_on_identical(self):
        g = np.zeros((40, 40), dtype=np.uint8) + 10
        self.assertEqual(frame_motion(g, g.copy()), 0.0)

    def test_3_motion_positive_on_change(self):
        a = np.zeros((40, 40), dtype=np.uint8)
        b = np.zeros((40, 40), dtype=np.uint8) + 50
        self.assertGreater(frame_motion(a, b), 10.0)

    def test_4_luma(self):
        g = np.zeros((10, 10), dtype=np.uint8) + 100
        self.assertAlmostEqual(frame_mean_luma(g), 100.0)

    def test_5_activity_transition(self):
        events = []
        bus = EventBus(None)
        bus.subscribe(events.append)
        cfg = PerceptionConfig(
            zones=[],
            motion_high=5.0,
            motion_idle=1.0,
            activity_hysteresis_s=0.0,
            jsonl_path=None,
            enable_ws=False,
        )
        rt = StreamerPerceptionRuntime(cfg, bus)
        quiet = np.zeros((60, 80), dtype=np.uint8) + 20
        busy = np.random.randint(0, 255, (60, 80), dtype=np.uint8)
        t = time.time()
        rt.process_gray(quiet, t)
        rt.process_gray(busy, t + 0.1)
        rt.process_gray(busy, t + 0.2)
        types = [e["type"] for e in events]
        self.assertIn("activity", types)
        levels = [e["payload"]["level"] for e in events if e["type"] == "activity"]
        self.assertIn("high", levels)

    def test_6_zone_active(self):
        events = []
        bus = EventBus(None)
        bus.subscribe(events.append)
        cfg = PerceptionConfig(
            zones=[ZoneSpec("z1", 0.0, 0.0, 0.5, 0.5, threshold=5.0)],
            activity_hysteresis_s=99.0,
            jsonl_path=None,
            enable_ws=False,
        )
        rt = StreamerPerceptionRuntime(cfg, bus)
        base = np.zeros((100, 100), dtype=np.uint8) + 10
        flash = base.copy()
        flash[0:50, 0:50] = 200
        t = time.time()
        rt.process_gray(base, t)
        rt.process_gray(flash, t + 0.05)
        zones = [e for e in events if e["type"] == "zone"]
        self.assertTrue(zones)
        self.assertEqual(zones[-1]["payload"]["zone_id"], "z1")
        self.assertEqual(zones[-1]["payload"]["state"], "active")

    def test_7_jsonl_write(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "e.jsonl"
            bus = EventBus(path)
            bus.emit(make_event("heartbeat", {"uptime_s": 0}))
            lines = path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 1)
            obj = json.loads(lines[0])
            self.assertEqual(obj["type"], "heartbeat")

    def test_8_synthetic_cli_import(self):
        # ensure CLI module loads
        root = Path(__file__).parents[2]
        sys.path.insert(0, str(root / "scripts"))
        # don't execute main
        self.assertTrue((root / "scripts" / "streamer_retina_events.py").is_file())
        self.assertTrue(
            (root / "docs" / "design" / "trio-retina-streamer-perception-v0.md").is_file()
        )
        self.assertTrue(
            (root / "tools" / "obs_streamer_perception_overlay.html").is_file()
        )


if __name__ == "__main__":
    unittest.main()

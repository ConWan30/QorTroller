"""Streamer perception v0 unit tests (no capture card required)."""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

BRIDGE = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE))

from vapi_bridge.streamer_perception import (  # noqa: E402
    DOMAIN,
    SOURCE_OBS_VIRTUAL,
    SOURCE_SYNTHETIC,
    SOURCE_UNKNOWN,
    SOURCE_UVC_CARD,
    DualStreamerRuntime,
    EventBus,
    PerceptionConfig,
    StaticPresenceProvider,
    StreamerPerceptionRuntime,
    TouchFilePresenceProvider,
    ZoneSpec,
    build_source_dict,
    classify_source_kind,
    clock_ns,
    decode_session_marker,
    frame_mean_luma,
    frame_motion,
    make_event,
    make_marker_digest,
    render_marker_text,
)


class _FakeCap:
    """Stand-in for cv2.VideoCapture in unit tests."""

    def __init__(self, frames, *, device: int = 0):
        self._frames = frames
        self._idx = 0
        self._released = False
        self.device = device

    def isOpened(self) -> bool:
        return not self._released

    def set(self, *args) -> None:
        pass

    def read(self):
        if self._idx < len(self._frames):
            f = self._frames[self._idx]
            self._idx += 1
            return True, f
        return False, None

    def release(self) -> None:
        self._released = True


def _bgr_frames(h=180, w=320, n=5, base=40):
    frames = []
    for i in range(n):
        f = np.full((h, w, 3), base, dtype=np.uint8)
        if i == 2:
            f[20:60, 20:100] = 200
        frames.append(f)
    return frames


class TestStreamerPerception(unittest.TestCase):
    def test_1_make_event_schema(self):
        ev = make_event("heartbeat", {"uptime_s": 1}, session_id="s1")
        self.assertEqual(ev["domain"], DOMAIN)
        self.assertEqual(ev["v"], 0)
        self.assertEqual(ev["type"], "heartbeat")
        self.assertEqual(ev["session_id"], "s1")
        self.assertIn("clock_ns", ev)
        self.assertIn("session_head_ns", ev)

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
        # WP-S5/S6: no provider => presence_sync_ok is False, never claims playing
        act = [e for e in events if e["type"] == "activity"][-1]
        self.assertIn("presence_sync_ok", act["payload"])
        self.assertFalse(act["payload"]["presence_sync_ok"])

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
            self.assertIn("clock_ns", obj)

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
        self.assertTrue(
            (root / "docs" / "design" / "trio-retina-obs-sync-v0.md").is_file()
        )

    def test_9_classify_source_kind_obs(self):
        self.assertEqual(
            classify_source_kind("OBS Virtual Camera"), SOURCE_OBS_VIRTUAL
        )
        self.assertEqual(
            classify_source_kind("obs-virtualcam"), SOURCE_OBS_VIRTUAL
        )
        self.assertEqual(
            classify_source_kind("Some USB Capture Card"), SOURCE_UVC_CARD
        )
        self.assertEqual(classify_source_kind(None), SOURCE_UNKNOWN)
        self.assertEqual(classify_source_kind("", synthetic=True), SOURCE_SYNTHETIC)
        self.assertEqual(
            classify_source_kind("OBS Virtual Camera", override="uvc_card"),
            SOURCE_UVC_CARD,
        )
        with self.assertRaises(ValueError):
            classify_source_kind(override="not-a-kind")

    def test_10_build_source_dict_kind(self):
        cfg = PerceptionConfig(
            device=1,
            device_name="OBS Virtual Camera",
            backend="msmf",
            enable_ws=False,
        )
        src = build_source_dict(cfg, backend="msmf")
        self.assertEqual(src["kind"], SOURCE_OBS_VIRTUAL)
        self.assertEqual(src["device"], 1)
        self.assertEqual(src["name"], "OBS Virtual Camera")
        self.assertEqual(src["backend"], "msmf")

    def test_11_activity_events_carry_source_kind(self):
        events = []
        bus = EventBus(None)
        bus.subscribe(events.append)
        cfg = PerceptionConfig(
            zones=[],
            motion_high=5.0,
            motion_idle=1.0,
            activity_hysteresis_s=0.0,
            device_name="Elgato 4K60",
            source_kind=None,
            jsonl_path=None,
            enable_ws=False,
        )
        rt = StreamerPerceptionRuntime(cfg, bus)
        rt._source_cache = build_source_dict(cfg)
        quiet = np.zeros((60, 80), dtype=np.uint8) + 20
        busy = np.random.randint(0, 255, (60, 80), dtype=np.uint8)
        t = time.time()
        rt.process_gray(quiet, t)
        rt.process_gray(busy, t + 0.1)
        acts = [e for e in events if e["type"] == "activity"]
        self.assertTrue(acts)
        self.assertEqual(acts[0]["source"]["kind"], SOURCE_UVC_CARD)

    def test_12_secondary_reserved_in_source(self):
        cfg = PerceptionConfig(
            device=0,
            device_name="Capture Card",
            secondary_device=2,
            secondary_device_name="OBS Virtual Camera",
            enable_ws=False,
        )
        src = build_source_dict(cfg)
        self.assertIn("secondary", src)
        self.assertEqual(src["secondary"]["kind"], SOURCE_OBS_VIRTUAL)
        self.assertFalse(src["secondary"]["opened"])

    # ------------------------------------------------------------------
    # WP-S2 dual open
    # ------------------------------------------------------------------
    def test_13_dual_open_runs_two_sources(self):
        events = []
        bus = EventBus(None)
        bus.subscribe(events.append)
        cfg = PerceptionConfig(
            device=0,
            device_name="Capture Card",
            secondary_device=1,
            secondary_device_name="OBS Virtual Camera",
            max_frames=3,
            stats_every_s=99.0,
            heartbeat_every_s=99.0,
            zones=[],
            enable_ws=False,
        )

        frames0 = _bgr_frames(n=5)
        frames1 = _bgr_frames(n=5, base=80)

        def _fake_open(device, width, height, fps, backend):
            if device == 0:
                return _FakeCap(frames0, device=0), "fake", frames0[0]
            return _FakeCap(frames1, device=1), "fake", frames1[0]

        with patch("vapi_bridge.streamer_perception.open_capture", _fake_open):
            rt = DualStreamerRuntime(cfg, bus)
            summary = rt.run()

        self.assertEqual(summary["sources_opened"], 2)
        self.assertGreater(summary["frames"], 0)
        starts = [e for e in events if e["type"] == "session_start"]
        self.assertEqual(len(starts), 2)
        devices = {e["source"]["device"] for e in starts}
        self.assertEqual(devices, {0, 1})

    def test_14_secondary_open_failure_is_fail_closed(self):
        events = []
        bus = EventBus(None)
        bus.subscribe(events.append)
        cfg = PerceptionConfig(
            device=0,
            device_name="Capture Card",
            secondary_device=1,
            secondary_device_name="OBS Virtual Camera",
            max_frames=2,
            stats_every_s=99.0,
            heartbeat_every_s=99.0,
            zones=[],
            enable_ws=False,
        )
        frames0 = _bgr_frames(n=3)

        def _fake_open(device, width, height, fps, backend):
            if device == 0:
                return _FakeCap(frames0, device=0), "fake", frames0[0]
            raise RuntimeError("secondary busy")

        with patch("vapi_bridge.streamer_perception.open_capture", _fake_open):
            rt = DualStreamerRuntime(cfg, bus)
            summary = rt.run()

        self.assertEqual(summary["sources_opened"], 1)
        fails = [e for e in events if e["type"] == "source_secondary_failed"]
        self.assertEqual(len(fails), 1)
        self.assertIn("secondary busy", fails[0]["payload"]["error"])

    # ------------------------------------------------------------------
    # WP-S3 session marker
    # ------------------------------------------------------------------
    def test_15_marker_text_render_and_digest(self):
        sid = "grind_235_v1"
        head = 1234567890123
        text = render_marker_text(sid, head)
        self.assertIn(sid, text)
        self.assertIn(make_marker_digest(sid, head), text)

    def test_16_decode_session_marker_fail_open(self):
        # no deps installed in CI? function returns method='none' without raising
        gray = np.zeros((100, 100), dtype=np.uint8)
        result = decode_session_marker(gray, "grind_235_v1|abcd1234")
        self.assertIn(result["method"], {"none", "qr", "text"})
        # Advisory decode may legitimately find nothing; the key is no exception
        self.assertIn("decoded", result)

    def test_17_decode_session_marker_no_config(self):
        gray = np.zeros((100, 100), dtype=np.uint8)
        result = decode_session_marker(gray, None)
        self.assertEqual(result["method"], "none")
        self.assertIsNone(result["match"])

    # ------------------------------------------------------------------
    # WP-S4 shared clock
    # ------------------------------------------------------------------
    def test_18_event_carries_clock_and_session_head(self):
        head = clock_ns()
        ev = make_event("heartbeat", {"uptime_s": 1}, session_id="s1", session_head_ns=head)
        self.assertIsInstance(ev["clock_ns"], int)
        self.assertGreaterEqual(ev["clock_ns"], head)
        self.assertEqual(ev["session_head_ns"], head)

    def test_19_session_start_sets_session_head(self):
        events = []
        bus = EventBus(None)
        bus.subscribe(events.append)
        cfg = PerceptionConfig(
            max_frames=2,
            stats_every_s=99.0,
            heartbeat_every_s=99.0,
            zones=[],
            enable_ws=False,
        )
        frames = _bgr_frames(n=3)

        with patch("vapi_bridge.streamer_perception.open_capture", lambda *a, **k: (_FakeCap(frames), "fake", frames[0])):
            rt = StreamerPerceptionRuntime(cfg, bus)
            rt.run()

        start = [e for e in events if e["type"] == "session_start"][0]
        self.assertIsNotNone(start["session_head_ns"])
        self.assertGreater(start["session_head_ns"], 0)
        for e in events:
            self.assertIn("clock_ns", e)

    # ------------------------------------------------------------------
    # WP-S5 presence-sync activity
    # ------------------------------------------------------------------
    def test_20_presence_sync_ok_with_recent_controller_input(self):
        events = []
        bus = EventBus(None)
        bus.subscribe(events.append)
        now = time.time()
        provider = StaticPresenceProvider(now)
        cfg = PerceptionConfig(
            zones=[],
            motion_high=5.0,
            motion_idle=1.0,
            activity_hysteresis_s=0.0,
            presence_timeout_s=2.0,
            enable_ws=False,
        )
        rt = StreamerPerceptionRuntime(cfg, bus, presence_provider=provider)
        quiet = np.zeros((60, 80), dtype=np.uint8) + 20
        busy = np.random.randint(0, 255, (60, 80), dtype=np.uint8)
        rt.process_gray(quiet, now)
        rt.process_gray(busy, now + 0.1)
        acts = [e for e in events if e["type"] == "activity"]
        self.assertTrue(acts)
        self.assertTrue(acts[-1]["payload"]["presence_sync_ok"])
        self.assertIsNotNone(acts[-1]["payload"]["last_controller_s_ago"])

    def test_21_presence_sync_ok_false_when_stale(self):
        events = []
        bus = EventBus(None)
        bus.subscribe(events.append)
        now = time.time()
        provider = StaticPresenceProvider(now - 100)  # stale
        cfg = PerceptionConfig(
            zones=[],
            motion_high=5.0,
            motion_idle=1.0,
            activity_hysteresis_s=0.0,
            presence_timeout_s=2.0,
            enable_ws=False,
        )
        rt = StreamerPerceptionRuntime(cfg, bus, presence_provider=provider)
        quiet = np.zeros((60, 80), dtype=np.uint8) + 20
        busy = np.random.randint(0, 255, (60, 80), dtype=np.uint8)
        rt.process_gray(quiet, now)
        rt.process_gray(busy, now + 0.1)
        acts = [e for e in events if e["type"] == "activity"]
        self.assertTrue(acts)
        self.assertFalse(acts[-1]["payload"]["presence_sync_ok"])

    def test_22_touch_file_provider_reads_mtime(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "presence.touch"
            path.write_text("x")
            now = time.time()
            provider = TouchFilePresenceProvider(path, timeout_s=60.0)
            ts = provider.last_input_ts()
            self.assertIsNotNone(ts)
            self.assertLessEqual(abs(ts - now), 5.0)

    # ------------------------------------------------------------------
    # WP-S6 non-merge tests
    # ------------------------------------------------------------------
    def test_23_optical_events_never_set_eligibility(self):
        events = []
        bus = EventBus(None)
        bus.subscribe(events.append)
        cfg = PerceptionConfig(
            zones=[],
            motion_high=5.0,
            motion_idle=1.0,
            activity_hysteresis_s=0.0,
            enable_ws=False,
        )
        rt = StreamerPerceptionRuntime(cfg, bus)
        busy = np.random.randint(0, 255, (60, 80), dtype=np.uint8)
        rt.process_gray(busy, time.time())
        forbidden = {"poep_enabled", "l6b_enabled", "l6_challenges", "candidate_ok", "eligible"}
        for ev in events:
            flat = json.dumps(ev)
            for f in forbidden:
                self.assertNotIn(f'"{f}":', flat, f"event must not set {f}")
                self.assertNotIn(f'"{f}"', flat, f"event must not mention {f}")

    def test_24_source_kind_is_not_humanity_proof(self):
        # source.kind tags are advisory; no claim of clean game / tournament grade
        cfg = PerceptionConfig(device_name="OBS Virtual Camera", enable_ws=False)
        src = build_source_dict(cfg)
        self.assertEqual(src["kind"], SOURCE_OBS_VIRTUAL)
        self.assertNotIn("humanity_proven", src)
        self.assertNotIn("tournament_grade", src)


if __name__ == "__main__":
    unittest.main()

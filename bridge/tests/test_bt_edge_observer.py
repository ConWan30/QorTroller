"""Unit tests for BT DualSense Edge observer decode (no hardware required)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

from vapi_bridge.bt_edge_observer import (  # noqa: E402
    decode_edge_report,
    path_is_bluetooth,
)


class TestBtEdgeDecode(unittest.TestCase):
    def test_1_bt_path_uuid(self):
        p = (
            b"\\\\?\\HID#{00001124-0000-1000-8000-00805f9b34fb}"
            b"_VID&0002054c_PID&0df2#8&1&0000#{4d1e55b2}"
        )
        self.assertTrue(path_is_bluetooth(p))
        self.assertFalse(path_is_bluetooth(b"\\\\?\\HID#VID_054C&PID_0DF2&MI_03"))

    def test_2_decode_report_31_face_buttons(self):
        # Minimal synthetic 0x31: sticks neutral-ish, cross pressed
        # payload[7] = 0x20 cross; rest zeros after sticks/triggers
        body = bytearray(77)
        body[0:6] = bytes([128, 128, 128, 128, 0, 0])
        body[7] = 0x20  # cross
        body[8] = 0x08  # R2 digital
        raw = bytes([0x31]) + bytes(body)
        s = decode_edge_report(raw, ts_ns=1)
        self.assertIsNotNone(s)
        assert s is not None
        self.assertEqual(s.report_id, 0x31)
        self.assertIn("cross", s.buttons)
        self.assertIn("R2", s.buttons)
        self.assertEqual(s.lx, 128)

    def test_3_decode_empty(self):
        self.assertIsNone(decode_edge_report(b""))

    def test_4_decode_report_01(self):
        body = bytearray(63)
        body[0:6] = bytes([10, 20, 30, 40, 50, 60])
        body[7] = 0x10  # square
        raw = bytes([0x01]) + bytes(body)
        s = decode_edge_report(raw)
        self.assertIsNotNone(s)
        assert s is not None
        self.assertEqual(s.report_id, 0x01)
        self.assertEqual(s.lx, 10)
        self.assertEqual(s.l2, 50)
        self.assertIn("square", s.buttons)

    def test_5_to_dict(self):
        raw = bytes([0x31]) + bytes([128] * 77)
        s = decode_edge_report(raw)
        assert s is not None
        d = s.to_dict()
        self.assertEqual(d["bus"], "bluetooth_hid")
        self.assertIn("buttons", d)


if __name__ == "__main__":
    unittest.main()

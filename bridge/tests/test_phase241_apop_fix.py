"""Phase 241-APOP-FIX — sampled frame_checkpoint write + time-based read.

Validates the fix for the codex shipment regression: APOP needed
frame_checkpoints during grind_mode but Phase 235 had disabled the writer
during grind. Fix samples writes at ~10/sec + adds time-based read query.
"""

import os
import sqlite3
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)


def _seed_record(db_path, device_id, record_hash):
    """Insert minimal device + record to satisfy frame_checkpoints FK."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "INSERT OR IGNORE INTO devices (device_id, pubkey_hex, first_seen, last_seen) "
        "VALUES (?,?,?,?)",
        (device_id, "pub", time.time(), time.time()),
    )
    conn.execute(
        "INSERT OR IGNORE INTO records "
        "(record_hash, device_id, counter, timestamp_ms, inference, action_code, "
        "confidence, battery_pct, status, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (record_hash, device_id, 1, int(time.time() * 1000),
         0x20, 0x01, 200, 80, "pending", time.time()),
    )
    conn.commit()
    conn.close()


class TestRecentCheckpointsForDevice(unittest.TestCase):
    def setUp(self):
        from vapi_bridge.store import Store
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "p241fix.db")
        self.store = Store(self.db)
        self.dev = "d" * 64

    def test_returns_empty_for_unknown_device(self):
        self.assertEqual(self.store.get_recent_frame_checkpoints_for_device("missing", 30), [])

    def test_returns_empty_for_blank_device(self):
        self.assertEqual(self.store.get_recent_frame_checkpoints_for_device("", 30), [])

    def test_round_trip_asc_order(self):
        # Seed 5 checkpoints with intentional time ordering
        for i in range(5):
            rh = f"{i:064x}"
            _seed_record(self.db, self.dev, rh)
            frames = [{"left_stick_x": 128 + i, "gyro_x": 0.5 * i}]
            self.store.store_frame_checkpoint(self.dev, rh, frames)
            time.sleep(0.01)
        result = self.store.get_recent_frame_checkpoints_for_device(self.dev, 30)
        self.assertEqual(len(result), 5)
        # ASC order — oldest first
        self.assertEqual(result[0]["record_hash"], "0" * 63 + "0")
        self.assertEqual(result[-1]["record_hash"], "0" * 63 + "4")
        # Frames preserved
        self.assertEqual(result[0]["frames"][0]["left_stick_x"], 128)
        self.assertEqual(result[-1]["frames"][0]["left_stick_x"], 132)

    def test_limit_respected_returns_most_recent_n(self):
        # Seed 10, request 3
        for i in range(10):
            rh = f"{i:064x}"
            _seed_record(self.db, self.dev, rh)
            self.store.store_frame_checkpoint(self.dev, rh, [{"i": i}])
            time.sleep(0.005)
        result = self.store.get_recent_frame_checkpoints_for_device(self.dev, 3)
        self.assertEqual(len(result), 3)
        # Should be the 3 most-recent in ASC order
        self.assertEqual(result[0]["frames"][0]["i"], 7)
        self.assertEqual(result[-1]["frames"][0]["i"], 9)

    def test_legacy_per_hash_helper_still_works(self):
        # Verify get_frame_checkpoints_for_records (preserved) still works
        for i in range(3):
            rh = f"{i:064x}"
            _seed_record(self.db, self.dev, rh)
            self.store.store_frame_checkpoint(self.dev, rh, [{"i": i}])
        legacy = self.store.get_frame_checkpoints_for_records(["0" * 64, "1" * 63 + "1"], 30)
        self.assertEqual(len(legacy), 1)  # only "0"*64 matches our seed pattern
        self.assertEqual(legacy[0]["record_hash"], "0" * 64)


if __name__ == "__main__":
    unittest.main()

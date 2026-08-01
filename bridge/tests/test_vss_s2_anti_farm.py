"""VSS-S2 — Anti-farm: one OPEN per key+channel; no empty OPEN."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

from vapi_bridge.vss_anti_farm import (  # noqa: E402
    can_open_seat,
    is_empty_open,
    load_state,
    record_transition,
    save_state,
)


class TestS2AntiFarm(unittest.TestCase):
    def test_1_empty_open_refused(self):
        self.assertTrue(is_empty_open(None, "OPEN"))
        self.assertTrue(is_empty_open("", "OPEN"))
        self.assertTrue(is_empty_open("  ", "OPEN"))
        self.assertFalse(is_empty_open("https://x.example/live", "OPEN"))
        self.assertFalse(is_empty_open(None, "CLOSED"))

    def test_2_first_open_allowed(self):
        ok, reason = can_open_seat(
            channel_id="ch1",
            signer_pubkey="aa" * 32,
            media_url="https://x.example/live",
            state={"seats": {}},
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")

    def test_3_double_open_refused(self):
        state = {"seats": {}}
        state = record_transition(
            state,
            channel_id="ch1",
            signer_pubkey="bb" * 32,
            seat_state="OPEN",
            media_url="https://x.example/live",
            event_id="e1",
        )
        ok, reason = can_open_seat(
            channel_id="ch1",
            signer_pubkey="bb" * 32,
            media_url="https://x.example/live",
            state=state,
        )
        self.assertFalse(ok)
        self.assertIn("already OPEN", reason)

    def test_4_close_then_reopen_allowed(self):
        state = {"seats": {}}
        pk = "cc" * 32
        state = record_transition(
            state, channel_id="ch1", signer_pubkey=pk, seat_state="OPEN",
            media_url="https://x.example/live", event_id="e1",
        )
        state = record_transition(
            state, channel_id="ch1", signer_pubkey=pk, seat_state="CLOSED",
            event_id="e2",
        )
        ok, reason = can_open_seat(
            channel_id="ch1",
            signer_pubkey=pk,
            media_url="https://x.example/other",
            state=state,
        )
        self.assertTrue(ok)

    def test_5_different_keys_independent(self):
        state = {"seats": {}}
        state = record_transition(
            state, channel_id="ch1", signer_pubkey="dd" * 32, seat_state="OPEN",
            media_url="https://x.example/live",
        )
        ok, _ = can_open_seat(
            channel_id="ch1",
            signer_pubkey="ee" * 32,
            media_url="https://x.example/live",
            state=state,
        )
        self.assertTrue(ok)

    def test_6_persist_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            state = record_transition(
                {"seats": {}},
                channel_id="ch",
                signer_pubkey="ff" * 32,
                seat_state="OPEN",
                media_url="https://x.example/live",
                event_id="e9",
            )
            save_state(path, state)
            loaded = load_state(path)
            ok, reason = can_open_seat(
                channel_id="ch",
                signer_pubkey="ff" * 32,
                media_url="https://x.example/live",
                state=loaded,
            )
            self.assertFalse(ok)
            self.assertIn("already OPEN", reason)


if __name__ == "__main__":
    unittest.main()

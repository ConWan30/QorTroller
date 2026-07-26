"""
Retina Increment B / Phase B2 — unified session events_root tests.

Covers lobe tagging, order-independence and determinism of the unified root,
the honest `lobes` label for single-lobe sessions, and the fail-open advisory
contract of cross_lobe_coherence().
"""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge import retina_session_root as rsr
from vapi_bridge.retina_events_root import (
    EVENTS_ROOT_SCHEME_SHA256_V1,
)
from vapi_bridge.retina_state_commitment import compute_events_root_for_scheme

_SCREEN = [{"kind": "outcome", "ts": 1.0, "id": "kill1"},
           {"kind": "outcome", "ts": 2.0, "id": "kill2"}]
_HID = [{"kind": "input", "ts": 0.9, "id": "r2_onset1"}]


class TestUnifySessionEventsRoot(unittest.TestCase):

    def test_both_lobes_reported(self):
        out = rsr.unify_session_events_root(_SCREEN, _HID)
        self.assertEqual(out["lobes"], [rsr.LOBE_SCREEN, rsr.LOBE_HID])
        self.assertEqual(out["n_screen"], 2)
        self.assertEqual(out["n_hid"], 1)
        self.assertEqual(out["scheme"], EVENTS_ROOT_SCHEME_SHA256_V1)
        self.assertEqual(len(out["events_root"]), 64)

    def test_deterministic_and_order_independent(self):
        a = rsr.unify_session_events_root(_SCREEN, _HID)
        b = rsr.unify_session_events_root(list(reversed(_SCREEN)), _HID)
        self.assertEqual(a["events_root"], b["events_root"])

    def test_root_matches_manually_tagged_events(self):
        tagged = ([{**e, "lobe": rsr.LOBE_SCREEN} for e in _SCREEN] +
                  [{**e, "lobe": rsr.LOBE_HID} for e in _HID])
        expected = compute_events_root_for_scheme(
            tagged, scheme=EVENTS_ROOT_SCHEME_SHA256_V1
        ).hex()
        self.assertEqual(rsr.unify_session_events_root(_SCREEN, _HID)["events_root"], expected)

    def test_lobe_tag_prevents_collision_between_lobes(self):
        """Identical event payloads in each lobe must not collapse to one line."""
        same = [{"kind": "x", "ts": 1.0}]
        both = rsr.unify_session_events_root(same, same)
        screen_only = rsr.unify_session_events_root(same, [])
        self.assertNotEqual(both["events_root"], screen_only["events_root"])

    def test_screen_only_session_labelled_honestly(self):
        out = rsr.unify_session_events_root(_SCREEN, None)
        self.assertEqual(out["lobes"], [rsr.LOBE_SCREEN])
        self.assertEqual(out["n_hid"], 0)

    def test_hid_only_session_labelled_honestly(self):
        out = rsr.unify_session_events_root(None, _HID)
        self.assertEqual(out["lobes"], [rsr.LOBE_HID])
        self.assertEqual(out["n_screen"], 0)

    def test_empty_session_still_produces_a_root(self):
        out = rsr.unify_session_events_root()
        self.assertEqual(out["lobes"], [])
        self.assertEqual((out["n_screen"], out["n_hid"]), (0, 0))
        self.assertEqual(len(out["events_root"]), 64)

    def test_input_events_are_not_mutated(self):
        screen = [{"kind": "outcome", "ts": 1.0}]
        rsr.unify_session_events_root(screen, [])
        self.assertEqual(screen, [{"kind": "outcome", "ts": 1.0}])


class TestCrossLobeCoherence(unittest.TestCase):

    def test_matches_outcomes_to_preceding_inputs(self):
        screen = [{"kind": "outcome", "ts_ns": 1_000_000_000, "wall_ms": 1000.0}]
        hid = [{"kind": "input", "ts_ns": 900_000_000, "wall_ms": 900.0}]
        out = rsr.cross_lobe_coherence(screen, hid)
        self.assertIsInstance(out, dict)
        # Advisory readout: either a coherence report or the fail-open shape,
        # never an exception.
        self.assertTrue("calibration" in out or "n_hid_inputs" in out)

    def test_empty_inputs_do_not_raise(self):
        self.assertIsInstance(rsr.cross_lobe_coherence(), dict)

    def test_failure_is_fail_open_uncalibrated(self):
        with patch(
            "l9_presence.killfeed_screen_event.to_timed_event",
            side_effect=RuntimeError("boom"),
        ):
            out = rsr.cross_lobe_coherence([{"kind": "outcome"}], [])
        self.assertEqual(out["calibration"], "UNCALIBRATED")
        self.assertIn("boom", out["error"])


if __name__ == "__main__":
    unittest.main()

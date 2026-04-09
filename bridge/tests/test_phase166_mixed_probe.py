"""Phase 166 — mixed_biometric_probe session type + configurable defensibility gate.

8 tests -> Bridge 1942 -> 1950.

Phase 166 addresses two related issues:
1. Touchpad-only sessions (corners/freeform/swipes) auto-exclude 5 features as
   zero-variance (trigger_resistance, trigger_onset_L2/R2, grip_asymmetry,
   press_timing_jitter), leaving only 8 active features.  The mixed_biometric_probe
   2-minute session (touchpad + trigger + button + stick segments) reactivates all 13.

2. The hardcoded 1.0 separation ratio gate is unachievable with a single shared
   physical controller (hardware variance is common to all 3 players, lowering the
   empirical ceiling).  min_separation_ratio=0.70 (configurable) is the new gate,
   set slightly above the current best (swipes: 0.644) to require improvement from
   the new probe type without requiring a ceiling that cannot be met.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from bridge.vapi_bridge.store import Store


def _make_store() -> Store:
    d = tempfile.mkdtemp()
    return Store(os.path.join(d, "test166.db"))


class TestPhase166MixedProbe(unittest.TestCase):

    def test_1_mixed_biometric_probe_in_structured_probe_types(self):
        """mixed_biometric_probe is included in STRUCTURED_PROBE_TYPES frozenset."""
        self.assertIn("mixed_biometric_probe", Store.STRUCTURED_PROBE_TYPES)

    def test_2_insert_defensibility_log_accepts_mixed_probe(self):
        """insert_separation_defensibility_log accepts mixed_biometric_probe session_type."""
        import json
        s = _make_store()
        row_id = s.insert_separation_defensibility_log(
            session_type="mixed_biometric_probe",
            n_sessions_total=6,
            n_per_player={"Player 1": 2, "Player 2": 2, "Player 3": 2},
            min_n_per_player=3,
            defensible=True,
            ratio=0.72,
            all_pairs_above_1=False,
        )
        self.assertIsNotNone(row_id)
        self.assertGreater(row_id, 0)

    def test_3_get_defensibility_status_returns_mixed_probe_row(self):
        """get_separation_defensibility_status returns mixed_biometric_probe row after insert."""
        import json
        s = _make_store()
        s.insert_separation_defensibility_log(
            session_type="mixed_biometric_probe",
            n_sessions_total=9,
            n_per_player={"Player 1": 3, "Player 2": 3, "Player 3": 3},
            min_n_per_player=3,
            defensible=True,
            ratio=0.75,
            all_pairs_above_1=False,
        )
        row = s.get_separation_defensibility_status(session_type="mixed_biometric_probe")
        self.assertIsNotNone(row)
        self.assertAlmostEqual(float(row["ratio"]), 0.75, places=2)

    def test_4_insert_rejects_invalid_session_type(self):
        """insert_separation_defensibility_log still rejects invalid session_type (W1-011)."""
        import json
        s = _make_store()
        with self.assertRaises(ValueError):
            s.insert_separation_defensibility_log(
                session_type="gameplay",
                n_sessions_total=5,
                n_per_player={"Player 1": 2},
                min_n_per_player=3,
                defensible=False,
                ratio=0.45,
                all_pairs_above_1=False,
            )

    def test_5_enrollment_guidance_includes_mixed_probe(self):
        """get_enrollment_capture_guidance includes mixed_biometric_probe in probe_types."""
        s = _make_store()
        guidance = s.get_enrollment_capture_guidance(min_n=3)
        self.assertIn("mixed_biometric_probe", guidance["probe_types"])

    def test_6_enrollment_guidance_exposes_min_separation_ratio(self):
        """get_enrollment_capture_guidance returns min_separation_ratio key."""
        s = _make_store()
        guidance = s.get_enrollment_capture_guidance(min_n=3)
        self.assertIn("min_separation_ratio", guidance)
        # Default stored attribute should be 0.70 (phase 166 gate)
        self.assertAlmostEqual(float(guidance["min_separation_ratio"]), 0.70, places=2)

    def test_7_defensibility_with_configurable_gate_070(self):
        """defensible=True is achievable at ratio=0.72 when gate=0.70 (not 1.0)."""
        import json
        s = _make_store()
        # Simulate a store with the phase 166 gate set
        s._min_separation_ratio = 0.70
        s.insert_separation_defensibility_log(
            session_type="mixed_biometric_probe",
            n_sessions_total=9,
            n_per_player={"Player 1": 3, "Player 2": 3, "Player 3": 3},
            min_n_per_player=3,
            defensible=True,
            ratio=0.72,
            all_pairs_above_1=False,
        )
        guidance = s.get_enrollment_capture_guidance(min_n=3)
        probe = guidance["guidance"].get("mixed_biometric_probe", {})
        # With ratio=0.72 >= gate=0.70 and all players at min_n=3, should be ready
        self.assertTrue(probe.get("all_players_ready", False))

    def test_8_endpoint_returns_mixed_probe_in_enrollment_guidance(self):
        """GET /agent/enrollment-capture-guidance includes mixed_biometric_probe."""
        from unittest.mock import MagicMock
        from fastapi.testclient import TestClient
        from bridge.vapi_bridge.operator_api import create_operator_app

        _s = _make_store()
        _cfg = MagicMock()
        _cfg.operator_api_key = "testkey166"
        _cfg.rate_limit_enabled = False
        _cfg.min_touchpad_sessions_per_player = 3
        _cfg.consent_ledger_enabled = False
        _cfg.min_separation_ratio = 0.70
        app = create_operator_app(_cfg, _s, None, None)
        client = TestClient(app)
        resp = client.get("/agent/enrollment-capture-guidance?api_key=testkey166")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("probe_types", data)
        self.assertIn("mixed_biometric_probe", data["probe_types"])


if __name__ == "__main__":
    unittest.main()

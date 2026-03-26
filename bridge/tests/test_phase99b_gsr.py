"""Phase 99B — L7 GSR Biometric Layer tests.

Tests:
  test_1  MockGSRGrip(seed=42) is deterministic — two instances same first output
  test_2  extract_l7_features returns 4 required keys
  test_3  extract_l7_features returns zeros for < 10 samples
  test_4  extract_l7_features never raises on malformed input
  test_5  store.insert_gsr_sample + get_gsr_samples retrieves correctly
  test_6  store.get_gsr_samples returns empty list for unknown device
  test_7  GSRRegistryAgent skips on-chain write when gsr_enabled=False (guard)
  test_8  _assess_gsr_risk returns empty dict on empty store (never raises)

Bridge count: 1378 → 1386 (+8)
"""
import asyncio
import tempfile
import time
import unittest
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vapi_bridge.store import Store
from vapi_bridge.gsr_feature_extractor import (
    MockGSRGrip, GSRSample, extract_l7_features,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store() -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p99b.db"))


def _make_cfg(gsr_enabled: bool = False):
    cfg = MagicMock()
    cfg.operator_api_key = "testkey99b"
    cfg.rate_limit_per_minute = 10000
    cfg.gsr_enabled = gsr_enabled
    cfg.gsr_sample_interval_s = 30
    cfg.gsr_registry_address = ""
    cfg.agent_model = "claude-sonnet-4-6"
    return cfg


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_window(n: int = 15) -> list:
    """Build a synthetic window of n GSRSample objects with deterministic values."""
    now = time.time()
    samples = []
    for i in range(n):
        # Inject an SCR event every 5 samples for realistic arousal pattern
        arousal = 0.6 if i % 5 == 0 else 0.05
        corr = 0.4 if arousal > 0.1 else 0.01
        samples.append(GSRSample(
            timestamp=now + i * 0.25,
            conductance_raw=5.0 + i * 0.01,
            arousal_index=arousal,
            correlation=corr,
        ))
    return samples


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMockGSRGrip(unittest.TestCase):

    def test_1_deterministic_with_same_seed(self):
        """MockGSRGrip(seed=42) is deterministic — two instances produce same first sample."""
        grip_a = MockGSRGrip(seed=42)
        grip_b = MockGSRGrip(seed=42)

        # Both grips have the same internal state, so get_sample() at identical
        # internal clocks should produce identical noise sequences.
        # We override time by patching to a fixed value so SCR injection is deterministic.
        with patch("vapi_bridge.gsr_feature_extractor.time") as mock_time:
            mock_time.time.return_value = 1_700_000_000.0
            s_a = grip_a.get_sample()
            mock_time.time.return_value = 1_700_000_000.0
            s_b = grip_b.get_sample()

        self.assertAlmostEqual(s_a.conductance_raw, s_b.conductance_raw, places=10)
        self.assertAlmostEqual(s_a.arousal_index, s_b.arousal_index, places=10)
        self.assertAlmostEqual(s_a.correlation, s_b.correlation, places=10)


class TestExtractL7Features(unittest.TestCase):

    def test_2_returns_4_required_keys(self):
        """extract_l7_features returns dict with 4 required feature keys."""
        window = _make_window(15)
        result = extract_l7_features(window)
        self.assertIn("sympathetic_arousal_index", result)
        self.assertIn("gsr_game_event_correlation", result)
        self.assertIn("baseline_conductance_drift", result)
        self.assertIn("cognitive_load_variance", result)
        # All values are floats
        for v in result.values():
            self.assertIsInstance(v, float)

    def test_3_returns_zeros_for_small_window(self):
        """extract_l7_features returns all-zero dict for window with < 10 samples."""
        small_window = _make_window(5)
        result = extract_l7_features(small_window)
        self.assertEqual(result["sympathetic_arousal_index"], 0.0)
        self.assertEqual(result["gsr_game_event_correlation"], 0.0)
        self.assertEqual(result["baseline_conductance_drift"], 0.0)
        self.assertEqual(result["cognitive_load_variance"], 0.0)

    def test_4_never_raises_on_malformed_input(self):
        """extract_l7_features never raises — returns zeros on error."""
        # Pass None elements — should not raise
        bad_inputs = [None, None, 42, "string", {}, [], None]
        result = extract_l7_features(bad_inputs)  # < 10, returns zeros
        self.assertIsInstance(result, dict)
        self.assertIn("sympathetic_arousal_index", result)

        # Pass a window where attribute access will fail
        class BadSample:
            timestamp = "not_a_float"
            @property
            def arousal_index(self):
                raise ValueError("bad sample")
            @property
            def correlation(self):
                raise ValueError("bad sample")
            @property
            def conductance_raw(self):
                raise ValueError("bad sample")

        bad_window = [BadSample()] * 15
        result2 = extract_l7_features(bad_window)
        self.assertIsInstance(result2, dict)
        # All zeros on exception
        self.assertEqual(result2["sympathetic_arousal_index"], 0.0)


class TestGSRStore(unittest.TestCase):

    def test_5_insert_and_retrieve_gsr_sample(self):
        """insert_gsr_sample + get_gsr_samples retrieves correctly."""
        store = _make_store()
        device_id = "dev_gsr_test"

        rid = store.insert_gsr_sample(
            device_id=device_id,
            arousal_index=0.65,
            correlation=0.42,
            conductance_raw=6.3,
            l7_features_json='{"sympathetic_arousal_index": 0.65}',
        )
        self.assertIsNotNone(rid)
        self.assertGreater(rid, 0)

        samples = store.get_gsr_samples(device_id)
        self.assertEqual(len(samples), 1)
        s = samples[0]
        self.assertEqual(s["device_id"], device_id)
        self.assertAlmostEqual(s["arousal_index"], 0.65, places=5)
        self.assertAlmostEqual(s["correlation"], 0.42, places=5)
        self.assertAlmostEqual(s["conductance_raw"], 6.3, places=5)

    def test_6_get_gsr_samples_unknown_device_returns_empty(self):
        """get_gsr_samples returns empty list for unknown device."""
        store = _make_store()
        result = store.get_gsr_samples("dev_never_seen")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)


class TestGSRRegistryAgent(unittest.TestCase):

    def test_7_skips_on_chain_write_when_gsr_disabled(self):
        """GSRRegistryAgent._collect_and_store() skips chain call when gsr_enabled=False."""
        store = _make_store()
        cfg = _make_cfg(gsr_enabled=False)

        # Mock chain object — should NOT be called
        mock_chain = MagicMock()
        mock_chain.record_gsr_sample_on_chain = MagicMock()

        from vapi_bridge.gsr_registry_agent import GSRRegistryAgent
        agent = GSRRegistryAgent(cfg, store, chain=mock_chain, bus=None)

        result = _run(agent._collect_and_store())

        # Result should be non-None (sample was collected and stored)
        self.assertIsNotNone(result)
        self.assertIn("device_id", result)
        self.assertIn("arousal_index", result)

        # chain.record_gsr_sample_on_chain must NOT have been called
        mock_chain.record_gsr_sample_on_chain.assert_not_called()

        # Verify the sample was written to SQLite
        samples = store.get_gsr_samples(result["device_id"])
        self.assertGreater(len(samples), 0)


class TestAssessGSRRisk(unittest.TestCase):

    def test_8_assess_gsr_risk_returns_empty_on_empty_store(self):
        """SessionAdjudicator._assess_gsr_risk returns empty dict on empty store. Never raises."""
        store = _make_store()
        cfg = _make_cfg(gsr_enabled=True)
        cfg.class_j_detection_enabled = True
        cfg.class_j_entropy_windows = 10
        cfg.enforcement_cert_ttl_s = 86400
        cfg.epistemic_consensus_enabled = False
        cfg.agent_dry_run_mode = True

        from vapi_bridge.session_adjudicator import SessionAdjudicator
        adj = SessionAdjudicator.__new__(SessionAdjudicator)
        adj._store = store
        adj._cfg = cfg
        adj._bus = None

        result = _run(adj._assess_gsr_risk("dev_no_gsr_data"))
        # Returns empty dict, never raises
        self.assertIsInstance(result, dict)
        self.assertEqual(result, {})

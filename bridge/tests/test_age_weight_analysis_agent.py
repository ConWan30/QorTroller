"""
Phase 175 — AgeWeightedRatioPersistenceAgent tests.

Covers the exponential age-decay weighting, the temporal drift index (TDI)
classification bands, the neutral-baseline write when no snapshots exist, and
the fail-safe STABLE defaults.
"""
import asyncio
import math
import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge import age_weight_analysis_agent as agent_mod
from vapi_bridge.age_weight_analysis_agent import AgeWeightedRatioPersistenceAgent

_DAY = 86400.0


def _cfg(enabled=True, halflife_days=90.0, probe_type="mixed_biometric_probe"):
    cfg = MagicMock()
    cfg.age_weight_analysis_enabled = enabled
    cfg.age_weight_halflife_days = halflife_days
    cfg.age_weight_probe_type = probe_type
    return cfg


def _store(rows):
    store = MagicMock()
    store.get_separation_defensibility_status.return_value = rows
    return store


def _agent(rows, **cfg_kwargs):
    store = _store(rows)
    bus = MagicMock()
    return AgeWeightedRatioPersistenceAgent(_cfg(**cfg_kwargs), store, bus), store, bus


class TestAgeWeightedRatio(unittest.TestCase):

    def test_empty_series_returns_zero(self):
        self.assertEqual(
            AgeWeightedRatioPersistenceAgent._compute_age_weighted_ratio([], [], 90.0, 0.0),
            0.0,
        )

    def test_non_positive_halflife_falls_back_to_plain_mean(self):
        value = AgeWeightedRatioPersistenceAgent._compute_age_weighted_ratio(
            [1.0, 3.0], [0.0, 0.0], 0.0, 100.0
        )
        self.assertEqual(value, 2.0)

    def test_equal_ages_reduce_to_plain_mean(self):
        now = 1_000_000.0
        value = AgeWeightedRatioPersistenceAgent._compute_age_weighted_ratio(
            [1.0, 2.0, 3.0], [now, now, now], 90.0, now
        )
        self.assertAlmostEqual(value, 2.0, places=6)

    def test_recent_snapshots_dominate_old_ones(self):
        now = 1_000_000.0
        halflife = 30.0
        ratios = [1.0, 3.0]
        timestamps = [now - 300 * _DAY, now]  # one very old, one fresh
        value = AgeWeightedRatioPersistenceAgent._compute_age_weighted_ratio(
            ratios, timestamps, halflife, now
        )
        self.assertGreater(value, 2.9)

        lam = math.log(2) / halflife
        w_old = math.exp(-lam * 300)
        expected = (1.0 * w_old + 3.0) / (w_old + 1.0)
        self.assertAlmostEqual(value, round(expected, 6), places=6)

    def test_one_halflife_old_snapshot_gets_half_weight(self):
        now = 1_000_000.0
        value = AgeWeightedRatioPersistenceAgent._compute_age_weighted_ratio(
            [0.0, 1.0], [now - 90 * _DAY, now], 90.0, now
        )
        # weights 0.5 and 1.0 → 1.0*1.0 / 1.5
        self.assertAlmostEqual(value, round(1.0 / 1.5, 6), places=6)

    def test_future_timestamps_are_clamped_to_zero_age(self):
        now = 1_000_000.0
        value = AgeWeightedRatioPersistenceAgent._compute_age_weighted_ratio(
            [2.0, 4.0], [now + 10 * _DAY, now], 90.0, now
        )
        self.assertAlmostEqual(value, 3.0, places=6)


class TestRunAssessment(unittest.TestCase):

    def test_disabled_short_circuits(self):
        agent, store, _ = _agent([], enabled=False)
        self.assertEqual(
            agent._run_assessment(),
            {"age_weight_analysis_enabled": False, "drift_direction": "STABLE"},
        )
        store.insert_age_weight_analysis_log.assert_not_called()

    def test_no_rows_writes_neutral_baseline(self):
        agent, store, _ = _agent([])
        result = agent._run_assessment()
        self.assertEqual(result["drift_direction"], "STABLE")
        store.insert_age_weight_analysis_log.assert_called_once()
        kwargs = store.insert_age_weight_analysis_log.call_args.kwargs
        self.assertEqual(kwargs["n_sessions_used"], 0)
        self.assertEqual(kwargs["raw_ratio"], 0.0)
        self.assertEqual(kwargs["probe_type"], "mixed_biometric_probe")

    def test_stable_when_ratio_flat(self):
        now = time.time()
        rows = [{"ratio": 2.0, "created_at": now - i * _DAY} for i in range(5)]
        agent, _, bus = _agent(rows)
        result = agent._run_assessment()
        self.assertEqual(result["drift_direction"], "STABLE")
        self.assertEqual(result["raw_ratio"], 2.0)
        self.assertEqual(result["n_sessions_used"], 5)
        self.assertAlmostEqual(result["temporal_drift_index"], 0.0, places=5)
        bus.publish.assert_not_called()

    def test_declining_recent_ratio_flags_nonstationarity(self):
        now = time.time()
        # recent snapshots much weaker than the old ones → weighted < raw → TDI > 0
        rows = [
            {"ratio": 3.0, "created_at": now - 300 * _DAY},
            {"ratio": 3.0, "created_at": now - 250 * _DAY},
            {"ratio": 1.0, "created_at": now},
        ]
        agent, store, bus = _agent(rows, halflife_days=30.0)
        result = agent._run_assessment()
        self.assertEqual(result["drift_direction"], "P1_NONSTATIONARITY")
        self.assertGreater(result["temporal_drift_index"], 0.05)
        bus.publish.assert_called_once()
        topic, payload = bus.publish.call_args[0]
        self.assertEqual(topic, "biometric_window_alert")
        self.assertEqual(payload["source"], "AgeWeightedRatioPersistenceAgent")
        store.insert_age_weight_analysis_log.assert_called_once()

    def test_improving_recent_ratio_is_not_alerted(self):
        now = time.time()
        rows = [
            {"ratio": 1.0, "created_at": now - 300 * _DAY},
            {"ratio": 1.0, "created_at": now - 250 * _DAY},
            {"ratio": 3.0, "created_at": now},
        ]
        agent, _, bus = _agent(rows, halflife_days=30.0)
        result = agent._run_assessment()
        self.assertEqual(result["drift_direction"], "IMPROVING")
        self.assertLess(result["temporal_drift_index"], -0.05)
        bus.publish.assert_not_called()

    def test_bus_publish_error_does_not_break_assessment(self):
        now = time.time()
        rows = [
            {"ratio": 3.0, "created_at": now - 300 * _DAY},
            {"ratio": 1.0, "created_at": now},
        ]
        agent, _, bus = _agent(rows, halflife_days=30.0)
        bus.publish.side_effect = RuntimeError("bus down")
        self.assertEqual(agent._run_assessment()["drift_direction"], "P1_NONSTATIONARITY")

    def test_store_read_error_returns_stable_defaults(self):
        agent, store, _ = _agent([])
        store.get_separation_defensibility_status.side_effect = RuntimeError("db gone")
        result = agent._run_assessment()
        self.assertEqual(result["drift_direction"], "STABLE")
        self.assertEqual(result["raw_ratio"], 0.0)
        self.assertEqual(result["temporal_drift_index"], 0.0)

    def test_missing_row_keys_default_to_zero(self):
        agent, _, _ = _agent([{}, {}])
        result = agent._run_assessment()
        self.assertEqual(result["raw_ratio"], 0.0)
        self.assertEqual(result["drift_direction"], "STABLE")


class TestPollLoop(unittest.TestCase):

    def test_assessment_exception_does_not_break_the_loop(self):
        agent, _, _ = _agent([])
        agent._run_assessment = MagicMock(side_effect=[RuntimeError("boom"), {}])

        sleeps = []

        async def _fake_sleep(delay):
            sleeps.append(delay)
            if len(sleeps) == 2:
                raise asyncio.CancelledError

        with patch.object(agent_mod.asyncio, "sleep", _fake_sleep), \
                self.assertRaises(asyncio.CancelledError):
            asyncio.run(agent.run_poll_loop())

        self.assertEqual(agent._run_assessment.call_count, 2)
        self.assertEqual(
            sleeps, [AgeWeightedRatioPersistenceAgent._POLL_INTERVAL_S] * 2
        )


if __name__ == "__main__":
    unittest.main()

"""Phase 159 — BiometricPrivacyComplianceAgent (agent #22) + BP-001 Temporal Decay.

8 tests → bridge 1886 → 1894.

Deliverables:
  BP-001: tbd_decay_factor() computes exponential decay with configurable half-life
  BiometricPrivacyComplianceAgent: monitors enrolled records and stores compliance reports
"""

import math
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

for _m in ["anthropic", "web3", "web3.exceptions", "eth_account",
           "pydualsense", "hidapi", "hid"]:
    if _m not in sys.modules:
        sys.modules[_m] = MagicMock()

os.chdir(tempfile.mkdtemp())

from bridge.vapi_bridge.store import Store
from bridge.vapi_bridge.biometric_privacy_compliance_agent import (
    BiometricPrivacyComplianceAgent,
    BP_001_HALF_LIFE_DAYS,
    BP_001_WARNING_THRESHOLD,
    tbd_decay_factor,
)


def _make_store() -> Store:
    db_dir = tempfile.mkdtemp()
    return Store(os.path.join(db_dir, "test_p159.db"))


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.operator_api_key              = "testkey159"
    cfg.rate_limit_per_minute         = 10000
    cfg.biometric_privacy_enabled     = True
    cfg.bp001_half_life_days          = 90.0
    cfg.fleet_consensus_enabled       = True
    cfg.validation_gate_n             = 100
    cfg.validation_max_divergence_rate = 1.0
    cfg.separation_ratio_current      = 1.261
    cfg.enforcement_cert_ttl_s        = 86400
    cfg.epistemic_consensus_enabled   = False
    cfg.agent_model                   = "claude-sonnet-4-6"
    cfg.mpc_ceremony_hash_cache       = None
    cfg.vhp_contract_address          = ""
    cfg.layerzero_endpoint_address    = ""
    cfg.warm_up_batch_size            = 5
    cfg.stiotx_token_address          = ""
    cfg.quicksilver_collateral_address = ""
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


class TestBP001TemporalDecay(unittest.TestCase):
    """BP-001: tbd_decay_factor() exponential decay mechanics."""

    def test_decay_at_zero_days_is_one(self):
        """Fresh record (age=0) has decay factor 1.0."""
        self.assertAlmostEqual(tbd_decay_factor(0.0), 1.0, places=6)

    def test_decay_at_one_half_life_is_half(self):
        """At τ_half = 90 days, decay factor ≈ 0.5."""
        df = tbd_decay_factor(BP_001_HALF_LIFE_DAYS)
        self.assertAlmostEqual(df, 0.5, places=5)

    def test_decay_at_two_half_lives_is_quarter(self):
        """At 2×τ_half = 180 days, decay factor ≈ 0.25 (warning threshold)."""
        df = tbd_decay_factor(2 * BP_001_HALF_LIFE_DAYS)
        self.assertAlmostEqual(df, 0.25, places=5)
        self.assertLessEqual(df, BP_001_WARNING_THRESHOLD + 0.001)

    def test_decay_negative_age_clamps_to_zero(self):
        """Negative age (clock skew protection) returns 0.0."""
        self.assertEqual(tbd_decay_factor(-10.0), 0.0)

    def test_decay_configurable_half_life(self):
        """Custom half_life_days changes the decay rate correctly."""
        df_30 = tbd_decay_factor(30.0, half_life_days=30.0)
        self.assertAlmostEqual(df_30, 0.5, places=5)


class TestBiometricPrivacyComplianceStore(unittest.TestCase):
    """Phase 159 store roundtrip and agent compliance report."""

    def test_privacy_compliance_log_roundtrip(self):
        """insert_privacy_compliance_log → get_privacy_compliance_status roundtrip."""
        store = _make_store()
        row_id = store.insert_privacy_compliance_log(
            records_monitored     = 11,
            records_expired       = 2,
            mean_decay_factor     = 0.87,
            oldest_session_days   = 42.5,
            privacy_budget_epsilon = 0.47,
            warning_triggered     = False,
        )
        self.assertIsInstance(row_id, int)
        self.assertGreater(row_id, 0)

        status = store.get_privacy_compliance_status()
        self.assertTrue(status["found"])
        self.assertEqual(status["records_monitored"], 11)
        self.assertEqual(status["records_expired"], 2)
        self.assertAlmostEqual(status["mean_decay_factor"], 0.87, places=4)
        self.assertFalse(status["warning_triggered"])

    def test_agent_compute_report_no_enrollments(self):
        """Agent compute report returns defaults when no enrolled sessions exist."""
        store = _make_store()
        cfg   = _make_cfg()
        agent = BiometricPrivacyComplianceAgent(cfg, store)
        report = agent._compute_compliance_report()

        self.assertEqual(report["records_monitored"], 0)
        self.assertAlmostEqual(report["mean_decay_factor"], 1.0, places=5)
        self.assertFalse(report["warning_triggered"])


class TestPhase159Endpoint(unittest.TestCase):
    """Phase 159 REST endpoint smoke test."""

    def test_endpoint_8_keys(self):
        """GET /agent/biometric-privacy-status returns 8 required keys."""
        store = _make_store()
        cfg   = _make_cfg()

        from bridge.vapi_bridge.operator_api import create_operator_app
        try:
            from starlette.testclient import TestClient
        except ImportError:
            from fastapi.testclient import TestClient

        app    = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/agent/biometric-privacy-status",
                          params={"api_key": "testkey159"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        for key in ("biometric_privacy_enabled", "bp001_half_life_days",
                    "records_monitored", "records_expired", "mean_decay_factor",
                    "warning_triggered", "privacy_budget_epsilon", "timestamp"):
            self.assertIn(key, body, f"Missing key: {key}")

        # Defaults when no records
        self.assertAlmostEqual(body["mean_decay_factor"], 1.0, places=4)
        self.assertAlmostEqual(body["bp001_half_life_days"], 90.0, places=2)


if __name__ == "__main__":
    unittest.main()

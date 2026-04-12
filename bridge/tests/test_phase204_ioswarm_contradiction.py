"""Phase 204 — IOSWARM_ACTIVE_NO_ADJUDICATIONS: 8th CONTRADICTION rule + Adjudication Primer.

WIF-038 W1 closure:
  When ioswarm_enabled=True AND ioswarm_adjudication_enabled=True but
  ioswarm_adjudication_log has zero entries (while consensus_log is active),
  FleetSignalCoherenceAgent fires IOSWARM_ACTIVE_NO_ADJUDICATIONS CONTRADICTION.

WIF-038 W2 closure:
  POST /agent/prime-ioswarm-adjudication seeds ioswarm_adjudication_log with
  5 emulator-mode entries, resolving the CONTRADICTION and unblocking
  VHP MINT_QUORUM=0.80 pathway.

Tests:
  T204-1  len(CONTRADICTION_RULES) == 8
  T204-2  IOSWARM_ACTIVE_NO_ADJUDICATIONS key exists + required fields present
  T204-3  guard dormant when ioswarm_enabled=False
  T204-4  guard dormant when ioswarm_adjudication_enabled=False
  T204-5  post_check False when total_adj > 0 (resolution already applied)
  T204-6  post_check False when consensus_count == 0 (ioSwarm never ran)
  T204-7  POST /agent/prime-ioswarm-adjudication → 409 when primer_enabled=False
  T204-8  POST /agent/prime-ioswarm-adjudication → success + seeds log when enabled
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Stub heavy optional dependencies before imports
for _mod in ("web3", "web3.exceptions", "eth_account"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from vapi_bridge.fleet_signal_coherence_agent import (  # noqa: E402
    CONTRADICTION_RULES,
    FleetSignalCoherenceAgent,
)


# ---------------------------------------------------------------------------
# T204-1  len(CONTRADICTION_RULES) == 8
# ---------------------------------------------------------------------------
class TestT204_1_RuleCount(unittest.TestCase):
    def test_contradiction_rules_length_is_8(self):
        self.assertEqual(
            len(CONTRADICTION_RULES),
            8,
            f"Expected 8 CONTRADICTION_RULES (added IOSWARM_ACTIVE_NO_ADJUDICATIONS "
            f"as 8th), got {len(CONTRADICTION_RULES)}: {list(CONTRADICTION_RULES)}",
        )


# ---------------------------------------------------------------------------
# T204-2  IOSWARM_ACTIVE_NO_ADJUDICATIONS key + required fields
# ---------------------------------------------------------------------------
class TestT204_2_RuleSchema(unittest.TestCase):
    def setUp(self):
        self.rule = CONTRADICTION_RULES.get("IOSWARM_ACTIVE_NO_ADJUDICATIONS")

    def test_rule_key_exists(self):
        self.assertIsNotNone(
            self.rule,
            "IOSWARM_ACTIVE_NO_ADJUDICATIONS not found in CONTRADICTION_RULES",
        )

    def test_required_fields(self):
        required = {"query", "params", "guard", "post_check",
                    "agents_involved", "severity", "explanation", "resolution"}
        missing = required - set(self.rule.keys())
        self.assertFalse(missing, f"Rule missing fields: {missing}")

    def test_severity_is_high(self):
        self.assertEqual(self.rule["severity"], "HIGH")

    def test_agents_involved(self):
        agents = self.rule["agents_involved"]
        self.assertIn("IoSwarmAdjudicationCoordinator", agents)
        self.assertIn("SessionAdjudicator", agents)

    def test_resolution_mentions_primer_endpoint(self):
        self.assertIn("/agent/prime-ioswarm-adjudication", self.rule["resolution"])


# ---------------------------------------------------------------------------
# T204-3  guard dormant when ioswarm_enabled=False
# ---------------------------------------------------------------------------
class TestT204_3_GuardIoSwarmDisabled(unittest.TestCase):
    def test_guard_returns_false_when_ioswarm_disabled(self):
        rule  = CONTRADICTION_RULES["IOSWARM_ACTIVE_NO_ADJUDICATIONS"]
        guard = rule["guard"]
        cfg   = MagicMock()
        cfg.ioswarm_enabled              = False
        cfg.ioswarm_adjudication_enabled = True
        self.assertFalse(
            guard(cfg),
            "Guard must return False when ioswarm_enabled=False "
            "(rule must be dormant — adjudication entries are not expected)",
        )


# ---------------------------------------------------------------------------
# T204-4  guard dormant when ioswarm_adjudication_enabled=False
# ---------------------------------------------------------------------------
class TestT204_4_GuardAdjudicationDisabled(unittest.TestCase):
    def test_guard_returns_false_when_adjudication_disabled(self):
        rule  = CONTRADICTION_RULES["IOSWARM_ACTIVE_NO_ADJUDICATIONS"]
        guard = rule["guard"]
        cfg   = MagicMock()
        cfg.ioswarm_enabled              = True
        cfg.ioswarm_adjudication_enabled = False
        self.assertFalse(
            guard(cfg),
            "Guard must return False when ioswarm_adjudication_enabled=False "
            "(adjudication entries not expected when adjudication is off)",
        )

    def test_guard_returns_true_when_both_enabled(self):
        rule  = CONTRADICTION_RULES["IOSWARM_ACTIVE_NO_ADJUDICATIONS"]
        guard = rule["guard"]
        cfg   = MagicMock()
        cfg.ioswarm_enabled              = True
        cfg.ioswarm_adjudication_enabled = True
        self.assertTrue(
            guard(cfg),
            "Guard must return True when both ioswarm_enabled=True "
            "and ioswarm_adjudication_enabled=True",
        )


# ---------------------------------------------------------------------------
# T204-5  post_check False when adj records exist (contradiction resolved)
# ---------------------------------------------------------------------------
class TestT204_5_PostCheckAdjExists(unittest.TestCase):
    def test_post_check_false_when_adj_records_exist(self):
        rule       = CONTRADICTION_RULES["IOSWARM_ACTIVE_NO_ADJUDICATIONS"]
        post_check = rule["post_check"]
        # adj exists → no contradiction
        row = {"total_adj": 3, "consensus_count": 10}
        self.assertFalse(
            post_check(row),
            "post_check must return False when total_adj > 0 "
            "(adjudication log is primed — no contradiction)",
        )


# ---------------------------------------------------------------------------
# T204-6  post_check False when consensus_count == 0 (ioSwarm never ran)
# ---------------------------------------------------------------------------
class TestT204_6_PostCheckNoConsensus(unittest.TestCase):
    def test_post_check_false_when_consensus_empty(self):
        rule       = CONTRADICTION_RULES["IOSWARM_ACTIVE_NO_ADJUDICATIONS"]
        post_check = rule["post_check"]
        # no consensus → ioSwarm has never run, so missing adj is expected
        row = {"total_adj": 0, "consensus_count": 0}
        self.assertFalse(
            post_check(row),
            "post_check must return False when consensus_count=0 "
            "(ioSwarm has not yet processed any sessions — missing adj is expected)",
        )

    def test_post_check_true_when_adj_zero_consensus_positive(self):
        rule       = CONTRADICTION_RULES["IOSWARM_ACTIVE_NO_ADJUDICATIONS"]
        post_check = rule["post_check"]
        # ioSwarm running (consensus > 0) but adj never fired → contradiction
        row = {"total_adj": 0, "consensus_count": 5}
        self.assertTrue(
            post_check(row),
            "post_check must return True when total_adj=0 AND consensus_count>0 "
            "(ioSwarm is active but adjudication was never invoked — contradiction)",
        )


# ---------------------------------------------------------------------------
# T204-7  POST /agent/prime-ioswarm-adjudication → 409 when primer disabled
# ---------------------------------------------------------------------------
class TestT204_7_PrimerEndpoint409(unittest.TestCase):
    def _make_app(self, primer_enabled: bool = False):
        """Build a minimal FastAPI test client with the operator_api wired."""
        from fastapi.testclient import TestClient
        from vapi_bridge.operator_api import create_operator_app

        cfg   = MagicMock()
        cfg.operator_api_key                     = "test-key"
        cfg.ioswarm_adjudication_primer_enabled   = primer_enabled
        cfg.rate_limit_requests_per_minute        = 600
        store = MagicMock()
        bus   = MagicMock()
        chain = MagicMock()
        app   = create_operator_app(cfg=cfg, store=store, bus=bus, chain=chain)
        return TestClient(app)

    def test_primer_returns_409_when_disabled(self):
        client = self._make_app(primer_enabled=False)
        resp   = client.post(
            "/agent/prime-ioswarm-adjudication",
            params={"api_key": "test-key"},
        )
        self.assertEqual(resp.status_code, 409)
        body = resp.json()
        self.assertIn("primer_disabled", str(body))


# ---------------------------------------------------------------------------
# T204-8  POST /agent/prime-ioswarm-adjudication → success + seeds log
# ---------------------------------------------------------------------------
class TestT204_8_PrimerEndpointSuccess(unittest.TestCase):
    def _make_app(self):
        from fastapi.testclient import TestClient
        from vapi_bridge.operator_api import create_operator_app

        cfg   = MagicMock()
        cfg.operator_api_key                     = "test-key"
        cfg.ioswarm_adjudication_primer_enabled   = True
        cfg.rate_limit_requests_per_minute        = 600
        cfg.ioswarm_classj_block_quorum           = 0.67
        cfg.ioswarm_triage_block_quorum           = 0.67
        cfg.ioswarm_poad_auto_anchor_enabled      = False

        store = MagicMock()
        store.get_ioswarm_adjudication_log.return_value = [{}] * 5
        store.insert_ioswarm_adjudication.return_value  = 1

        bus   = MagicMock()
        chain = MagicMock()
        app   = create_operator_app(cfg=cfg, store=store, bus=bus, chain=chain)
        return TestClient(app), store

    def test_primer_returns_success_and_seeds_log(self):
        client, store_mock = self._make_app()
        resp = client.post(
            "/agent/prime-ioswarm-adjudication",
            params={"api_key": "test-key"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(body.get("primer_enabled"))
        self.assertEqual(body.get("devices_primed"), 5)
        self.assertTrue(body.get("ioswarm_adjudication_log_seeded"))
        results = body.get("results", [])
        self.assertEqual(len(results), 5)
        # Verify device IDs follow primer naming convention
        for i, r in enumerate(results):
            self.assertEqual(r["device_id"], f"primer_device_{i:03d}")
        # Verify store.insert_ioswarm_adjudication was called 5 times
        self.assertEqual(store_mock.insert_ioswarm_adjudication.call_count, 5)


if __name__ == "__main__":
    unittest.main()

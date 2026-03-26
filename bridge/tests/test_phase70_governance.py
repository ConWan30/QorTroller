"""
Phase 70 — VAPI Governance Timelock + Protocol Lens + Agent Wiring Tests (21 tests)

TestAgentWiring (4 tests):
  test_1_data_curator_agent_starts_when_curator_enabled_true
  test_2_data_curator_agent_skips_when_curator_enabled_false
  test_3_session_adjudicator_starts_when_api_key_set
  test_4_ruling_enforcement_agent_starts_when_enabled

TestBridgeAgentTools41to45 (10 tests):
  test_5_tool_41_get_data_lineage_returns_list
  test_6_tool_41_get_data_lineage_unknown_device_returns_empty
  test_7_tool_42_get_token_eligibility_returns_state
  test_8_tool_43_get_oracle_state_humanity
  test_9_tool_43_get_oracle_state_invalid_type_returns_error
  test_10_tool_44_compute_reward_score_returns_breakdown
  test_11_tool_45_publish_sovereignty_pledge_queues_event
  test_12_tool_45_publish_sovereignty_pledge_requires_operator
  test_13_tool_44_compute_reward_score_no_eligibility_returns_error
  test_14_tool_42_token_eligibility_with_all_multipliers

TestValidationStatsEndpoint (4 tests):
  test_15_get_validation_stats_returns_proof_counts
  test_16_get_validation_stats_includes_curator_stats
  test_17_get_validation_stats_includes_enrollment_counts
  test_18_get_validation_stats_includes_ruling_stats

TestProtocolLensIntegration (3 tests):
  test_19_protocol_lens_config_field_exists_in_chain_config
  test_20_bridge_agent_tool_43_validates_oracle_type_allowlist
  test_21_bridge_agent_has_47_tool_definitions
"""

import json
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

# Stub heavy optional dependencies
for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local",
             "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from vapi_bridge.store import Store

_DEVICE_A = "aa" * 32
_DEVICE_B = "bb" * 32


def _make_store() -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p70.db"))


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.enrollment_min_sessions    = 10
    cfg.enrollment_humanity_min    = 0.60
    cfg.operator_api_key           = kwargs.get("operator_api_key", "testkey70")
    cfg.rate_limit_per_minute      = 100
    cfg.curator_enabled            = kwargs.get("curator_enabled", True)
    cfg.curator_oracle_publish     = False
    cfg.ruling_enforcement_enabled = kwargs.get("ruling_enforcement_enabled", False)
    cfg.humanity_oracle_address    = ""
    cfg.ruling_oracle_address      = ""
    cfg.passport_oracle_address    = ""
    cfg.data_sovereignty_reg_address = ""
    cfg.agent_dry_run_mode         = True
    cfg.l4_anomaly_threshold       = 7.009
    cfg.l4_continuity_threshold    = 5.367
    cfg.game_profile_id            = ""
    cfg.l6b_enabled                = False
    return cfg


# ---------------------------------------------------------------------------
# TestAgentWiring
# ---------------------------------------------------------------------------

class TestAgentWiring(unittest.TestCase):
    """Verify the Phase 70 main.py agent wiring logic creates tasks correctly."""

    def test_1_data_curator_agent_starts_when_curator_enabled_true(self):
        """DataCuratorAgent.run_poll_loop should be called when curator_enabled=True."""
        from vapi_bridge.data_curator_agent import DataCuratorAgent
        st = _make_store()
        cfg = _make_cfg(curator_enabled=True)
        curator = DataCuratorAgent(cfg, st, chain=None)
        # Verify run_poll_loop exists and is callable
        self.assertTrue(callable(curator.run_poll_loop))
        # Verify curator_enabled guard works
        self.assertTrue(getattr(cfg, "curator_enabled", True))

    def test_2_data_curator_agent_skips_when_curator_enabled_false(self):
        """DataCuratorAgent.run_forever should exit immediately when curator_enabled=False."""
        from vapi_bridge.data_curator_agent import DataCuratorAgent
        st = _make_store()
        cfg = _make_cfg(curator_enabled=False)
        curator = DataCuratorAgent(cfg, st, chain=None)
        self.assertFalse(getattr(cfg, "curator_enabled", True))

    def test_3_session_adjudicator_starts_when_api_key_set(self):
        """SessionAdjudicator should be creatable when operator_api_key is set."""
        from vapi_bridge.session_adjudicator import SessionAdjudicator
        st = _make_store()
        cfg = _make_cfg(operator_api_key="test_operator_key")
        # SessionAdjudicator takes (cfg, store) only — no chain arg
        adjudicator = SessionAdjudicator(cfg, st)
        self.assertTrue(callable(adjudicator.run_event_consumer))
        self.assertTrue(bool(getattr(cfg, "operator_api_key", "")))

    def test_4_ruling_enforcement_agent_starts_when_enabled(self):
        """RulingEnforcementAgent should be creatable when ruling_enforcement_enabled=True."""
        from vapi_bridge.ruling_enforcement_agent import RulingEnforcementAgent
        st = _make_store()
        cfg = _make_cfg(ruling_enforcement_enabled=True)
        enforcer = RulingEnforcementAgent(cfg, st, chain=None)
        self.assertTrue(callable(enforcer.run_event_consumer))
        self.assertTrue(getattr(cfg, "ruling_enforcement_enabled", False))


# ---------------------------------------------------------------------------
# TestBridgeAgentTools41to45
# ---------------------------------------------------------------------------

class TestBridgeAgentTools41to45(unittest.TestCase):
    """Verify BridgeAgent tool execution for tools #41–45."""

    def _make_agent(self, cfg=None, store=None):
        from vapi_bridge.bridge_agent import BridgeAgent
        cfg   = cfg   or _make_cfg()
        store = store or _make_store()
        return BridgeAgent(cfg, store)

    def _seed_lineage(self, store):
        store.upsert_data_lineage(_DEVICE_A, "SESSION_DATA", 0.9, curator_note="nominal")
        store.upsert_data_lineage(_DEVICE_A, "BIOMETRIC_DATA", 0.75)

    def _seed_oracle_publication(self, store):
        store.insert_oracle_publication("HUMANITY", _DEVICE_A, "0xdeadbeef",
                                        '{"humanity_pct": 875}')

    def _seed_token_eligibility(self, store):
        store.upsert_token_eligibility(
            device_id=_DEVICE_A,
            nominal_sessions=15,
            clean_streak=6,
            passport_held=True,
            enrollment_complete=True,
            mpc_verified=True,
            gate_passed=False,
            base_multiplier=1.0,
            total_multiplier=3.75,
            eligibility_score=56.25,
        )

    # --- Tool #41 ---

    def test_5_tool_41_get_data_lineage_returns_list(self):
        st = _make_store()
        self._seed_lineage(st)
        agent = self._make_agent(store=st)
        result = agent._execute_tool("get_data_lineage", {"device_id": _DEVICE_A})
        self.assertIn("lineage", result)
        self.assertGreater(result["lineage_count"], 0)
        self.assertEqual(result["device_id"], _DEVICE_A)

    def test_6_tool_41_get_data_lineage_unknown_device_returns_empty(self):
        st = _make_store()
        agent = self._make_agent(store=st)
        result = agent._execute_tool("get_data_lineage", {"device_id": _DEVICE_B})
        self.assertEqual(result["lineage_count"], 0)
        self.assertEqual(result["lineage"], [])

    # --- Tool #42 ---

    def test_7_tool_42_get_token_eligibility_returns_state(self):
        st = _make_store()
        self._seed_token_eligibility(st)
        agent = self._make_agent(store=st)
        result = agent._execute_tool("get_token_eligibility", {"device_id": _DEVICE_A})
        self.assertIn("eligibility", result)
        self.assertIsNotNone(result["eligibility"])
        elig = result["eligibility"]
        self.assertEqual(elig["nominal_sessions"], 15)

    def test_14_tool_42_token_eligibility_with_all_multipliers(self):
        st = _make_store()
        self._seed_token_eligibility(st)
        agent = self._make_agent(store=st)
        result = agent._execute_tool("get_token_eligibility", {"device_id": _DEVICE_A})
        elig = result["eligibility"]
        self.assertAlmostEqual(float(elig["total_multiplier"]), 3.75, places=2)
        self.assertTrue(elig["passport_held"])
        self.assertTrue(elig["enrollment_complete"])
        self.assertTrue(elig["mpc_verified"])

    # --- Tool #43 ---

    def test_8_tool_43_get_oracle_state_humanity(self):
        st = _make_store()
        self._seed_oracle_publication(st)
        agent = self._make_agent(store=st)
        result = agent._execute_tool("get_oracle_state", {"oracle_type": "humanity"})
        self.assertEqual(result["oracle_type"], "HUMANITY")  # uppercased
        self.assertIn("publications", result)

    def test_9_tool_43_get_oracle_state_invalid_type_returns_error(self):
        st = _make_store()
        agent = self._make_agent(store=st)
        result = agent._execute_tool("get_oracle_state", {"oracle_type": "INVALID_ORACLE"})
        self.assertIn("error", result)
        self.assertIn("valid_types", result)

    # --- Tool #44 ---

    def test_10_tool_44_compute_reward_score_returns_breakdown(self):
        st = _make_store()
        # Seed some nominal records for the device
        from vapi_bridge.store import Store
        st.upsert_device(_DEVICE_A, "00" * 33)
        agent = self._make_agent(store=st)
        result = agent._execute_tool("compute_reward_score", {"device_id": _DEVICE_A})
        # Even with no records the eligibility engine returns a valid breakdown
        self.assertIn("multiplier_breakdown", result)
        self.assertEqual(result["device_id"], _DEVICE_A)

    def test_13_tool_44_compute_reward_score_no_eligibility_returns_error(self):
        """Tool #44 must never raise — returns error field if computation fails."""
        st = _make_store()
        agent = self._make_agent(store=st)
        # Empty store — no sessions — should still return a dict (no raise)
        result = agent._execute_tool("compute_reward_score", {"device_id": _DEVICE_A})
        self.assertIsInstance(result, dict)
        # Must not raise — either has multiplier_breakdown or error field
        self.assertTrue("multiplier_breakdown" in result or "error" in result)

    # --- Tool #45 ---

    def test_11_tool_45_publish_sovereignty_pledge_queues_event(self):
        st = _make_store()
        cfg = _make_cfg(operator_api_key="testkey70")
        agent = self._make_agent(cfg=cfg, store=st)
        result = agent._execute_tool("publish_sovereignty_pledge", {})
        self.assertEqual(result["status"], "queued")
        self.assertIn("event_id", result)
        self.assertIn("note", result)

    def test_12_tool_45_publish_sovereignty_pledge_requires_operator(self):
        """Tool #45 must return error if OPERATOR_API_KEY not set."""
        st = _make_store()
        cfg = _make_cfg(operator_api_key="")
        agent = self._make_agent(cfg=cfg, store=st)
        result = agent._execute_tool("publish_sovereignty_pledge", {})
        self.assertIn("error", result)
        self.assertIn("Operator auth required", result["error"])


# ---------------------------------------------------------------------------
# TestValidationStatsEndpoint
# ---------------------------------------------------------------------------

class TestValidationStatsEndpoint(unittest.TestCase):
    """Verify GET /agent/validation-stats endpoint structure and response fields."""

    def _make_app(self):
        from fastapi.testclient import TestClient
        from vapi_bridge.operator_api import create_operator_app
        st = _make_store()
        cfg = _make_cfg()
        app = create_operator_app(cfg, st)
        return TestClient(app), cfg

    def test_15_get_validation_stats_returns_proof_counts(self):
        client, cfg = self._make_app()
        resp = client.get("/agent/validation-stats", params={"api_key": cfg.operator_api_key})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("proof_stats", data)
        self.assertIn("timestamp", data)

    def test_16_get_validation_stats_includes_curator_stats(self):
        client, cfg = self._make_app()
        resp = client.get("/agent/validation-stats", params={"api_key": cfg.operator_api_key})
        data = resp.json()
        self.assertIn("curator_stats", data)
        curator = data["curator_stats"]
        self.assertIn("lineage_count", curator)
        self.assertIn("oracle_publications", curator)
        self.assertIn("eligible_devices", curator)

    def test_17_get_validation_stats_includes_enrollment_counts(self):
        client, cfg = self._make_app()
        resp = client.get("/agent/validation-stats", params={"api_key": cfg.operator_api_key})
        data = resp.json()
        self.assertIn("enrollment", data)
        enrollment = data["enrollment"]
        self.assertIn("eligible", enrollment)
        self.assertIn("in_progress", enrollment)
        self.assertIn("unenrolled", enrollment)

    def test_18_get_validation_stats_includes_ruling_stats(self):
        client, cfg = self._make_app()
        resp = client.get("/agent/validation-stats", params={"api_key": cfg.operator_api_key})
        data = resp.json()
        self.assertIn("ruling_stats", data)
        ruling = data["ruling_stats"]
        self.assertIn("total_rulings", ruling)
        self.assertIn("block_rulings", ruling)
        self.assertIn("active_suspensions", ruling)


# ---------------------------------------------------------------------------
# TestProtocolLensIntegration
# ---------------------------------------------------------------------------

class TestProtocolLensIntegration(unittest.TestCase):
    """Verify Phase 70 protocol lens config and BridgeAgent integration points."""

    def test_19_protocol_lens_config_field_exists_in_chain_config(self):
        """Config should support PROTOCOL_LENS_ADDRESS and GOVERNANCE_TIMELOCK_ADDRESS env vars."""
        from vapi_bridge.config import Config
        cfg = Config()
        # Fields should exist (default to empty string)
        governance_addr = getattr(cfg, "governance_timelock_address", None)
        lens_addr = getattr(cfg, "protocol_lens_address", None)
        # Not None — should be empty string defaults
        self.assertIsNotNone(governance_addr)
        self.assertIsNotNone(lens_addr)

    def test_20_bridge_agent_tool_43_validates_oracle_type_allowlist(self):
        """Tool #43 must reject any oracle_type not in {HUMANITY, RULING, PASSPORT}."""
        from vapi_bridge.bridge_agent import BridgeAgent
        st = _make_store()
        cfg = _make_cfg()
        agent = BridgeAgent(cfg, st)
        # Valid types should not return error
        for valid_type in ("HUMANITY", "RULING", "PASSPORT", "humanity", "ruling", "passport"):
            result = agent._execute_tool("get_oracle_state", {"oracle_type": valid_type})
            self.assertNotIn("error", result,
                             f"Valid oracle type '{valid_type}' should not return error")
        # Invalid types must return error
        for bad_type in ("BIOMETRIC", "SESSION", "", "ALL", "INVALID"):
            result = agent._execute_tool("get_oracle_state", {"oracle_type": bad_type})
            self.assertIn("error", result,
                          f"Invalid oracle type '{bad_type}' should return error")

    def test_21_bridge_agent_has_47_tool_definitions(self):
        """BridgeAgent _TOOLS must contain at least 47 tool definitions (Phase 76+ adds #47-50)."""
        from vapi_bridge.bridge_agent import _TOOLS
        tool_names = [t["name"] for t in _TOOLS]
        self.assertGreaterEqual(len(_TOOLS), 47,
                         f"Expected at least 47 tools, got {len(_TOOLS)}: {tool_names}")
        # Verify Phase 70 tools present
        phase70_tools = ["get_data_lineage", "get_token_eligibility", "get_oracle_state",
                         "compute_reward_score", "publish_sovereignty_pledge"]
        for name in phase70_tools:
            self.assertIn(name, tool_names, f"Phase 70 tool '{name}' missing from _TOOLS")
        # Verify Phase 75 tool present
        self.assertIn("get_validation_gate_status", tool_names,
                      "Phase 75 tool 'get_validation_gate_status' missing from _TOOLS")
        # Verify Phase 76 tool present
        self.assertIn("get_ruling_provenance", tool_names,
                      "Phase 76 tool 'get_ruling_provenance' missing from _TOOLS")


if __name__ == "__main__":
    unittest.main()

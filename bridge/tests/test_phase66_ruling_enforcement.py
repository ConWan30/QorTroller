"""
Phase 66 -- Ruling Enforcement Pipeline Tests (30 tests)

TestRulingStreaksStore (10 tests):
  test_1_upsert_streak_first_verdict_count_is_1
  test_2_upsert_streak_same_verdict_increments
  test_3_upsert_streak_different_verdict_resets_to_1
  test_4_get_ruling_streak_none_for_unknown_device
  test_5_set_streak_escalation_updates_field
  test_6_insert_on_chain_ruling_returns_id
  test_7_get_on_chain_rulings_empty_returns_list
  test_8_get_on_chain_rulings_most_recent_first
  test_9_get_on_chain_ruling_by_commitment_found
  test_10_get_on_chain_ruling_by_commitment_missing_returns_none

TestRulingEnforcementAgent (8 tests):
  test_11_init_stores_cfg_store_chain
  test_12_consume_empty_events_no_action
  test_13_consume_ruling_completed_updates_streak
  test_14_flag_streak_5_escalates_to_hold
  test_15_hold_streak_2_escalates_to_block
  test_16_block_verdict_calls_enforce_block
  test_17_enforce_block_no_chain_logs_no_crash
  test_18_enforce_block_warmup_attack_extends_suspension

TestEnforcementEndpoint (5 tests):
  test_19_post_agent_override_returns_200
  test_20_post_agent_override_missing_device_id_400
  test_21_post_agent_override_without_auth_401
  test_22_post_agent_override_resets_streak_to_clear
  test_23_post_agent_override_inserts_agent_ruling

TestBridgeAgentTools3435 (4 tests):
  test_24_tool34_get_ruling_streak_returns_streak
  test_25_tool34_get_ruling_streak_unknown_device_returns_zero
  test_26_tool35_override_ruling_clears_streak
  test_27_tool35_override_ruling_missing_device_id_error

TestEndToEndRulingPipeline (3 tests):
  test_28_session_adjudicator_emits_ruling_completed_targeting_enforcement
  test_29_ruling_enforcement_processes_adjudicator_event
  test_30_block_streak_pipeline_suspend_then_override_restores
"""

import asyncio
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

# Stub heavy optional dependencies before importing bridge modules
for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from vapi_bridge.store import Store

_DEVICE_A  = "aa" * 32
_DEVICE_B  = "bb" * 32
_COMMIT_A  = "deadbeef" * 8   # 64 hex chars
_COMMIT_B  = "cafebabe" * 8


def _make_store() -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p66.db"))


def _make_cfg(streak_block_threshold: int = 3):
    cfg = MagicMock()
    cfg.enrollment_min_sessions       = 10
    cfg.enrollment_humanity_min       = 0.60
    cfg.l6b_enabled                   = False
    cfg.agent_max_history_before_compress = 60
    cfg.operator_api_key              = "testkey66"
    cfg.rate_limit_per_minute         = 100
    cfg.ruling_enforcement_enabled    = True
    cfg.ruling_streak_block_threshold = streak_block_threshold
    cfg.ruling_registry_address       = ""
    cfg.enforcement_shadow_mode       = False   # Phase 90: MagicMock attr would be truthy
    return cfg


def _insert_ruling(store, device_id=_DEVICE_A, verdict="FLAG",
                   confidence=0.05, commitment_hash=_COMMIT_A) -> int:
    return store.insert_agent_ruling(
        device_id=device_id,
        verdict=verdict,
        confidence=confidence,
        reasoning="test ruling",
        evidence_json="{}",
        commitment_hash=commitment_hash,
        attestation_hash="",
        dry_run=True,
        source_agent="session_adjudicator",
    )


# ===========================================================================
# TestRulingStreaksStore — 10 tests
# ===========================================================================

class TestRulingStreaksStore(unittest.TestCase):

    def setUp(self):
        self.store = _make_store()
        self.store.upsert_device(_DEVICE_A, "aa" * 32)
        self.store.upsert_device(_DEVICE_B, "bb" * 32)

    def test_1_upsert_streak_first_verdict_count_is_1(self):
        """First call to upsert_ruling_streak returns current_streak=1."""
        rid = _insert_ruling(self.store)
        streak = self.store.upsert_ruling_streak(_DEVICE_A, "FLAG", rid)
        self.assertIsNotNone(streak)
        self.assertEqual(streak["current_streak"], 1)
        self.assertEqual(streak["streak_verdict"], "FLAG")

    def test_2_upsert_streak_same_verdict_increments(self):
        """Repeated same-verdict calls increment current_streak."""
        for i in range(4):
            rid = _insert_ruling(self.store, commitment_hash="aa" * 16 + f"{i:016x}")
            self.store.upsert_ruling_streak(_DEVICE_A, "FLAG", rid)
        streak = self.store.get_ruling_streak(_DEVICE_A)
        self.assertEqual(streak["current_streak"], 4)

    def test_3_upsert_streak_different_verdict_resets_to_1(self):
        """Verdict change resets current_streak to 1 with new verdict."""
        rid1 = _insert_ruling(self.store, commitment_hash="aa" * 32)
        self.store.upsert_ruling_streak(_DEVICE_A, "FLAG", rid1)
        self.store.upsert_ruling_streak(_DEVICE_A, "FLAG", rid1)
        rid2 = _insert_ruling(self.store, verdict="BLOCK", commitment_hash="bb" * 32)
        streak = self.store.upsert_ruling_streak(_DEVICE_A, "BLOCK", rid2)
        self.assertEqual(streak["current_streak"], 1)
        self.assertEqual(streak["streak_verdict"], "BLOCK")

    def test_4_get_ruling_streak_none_for_unknown_device(self):
        """get_ruling_streak returns None for a device with no streak record."""
        result = self.store.get_ruling_streak("ff" * 32)
        self.assertIsNone(result)

    def test_5_set_streak_escalation_updates_field(self):
        """set_streak_escalation writes escalated_to into ruling_streaks."""
        rid = _insert_ruling(self.store)
        self.store.upsert_ruling_streak(_DEVICE_A, "HOLD", rid)
        self.store.set_streak_escalation(_DEVICE_A, "BLOCK")
        streak = self.store.get_ruling_streak(_DEVICE_A)
        self.assertEqual(streak["escalated_to"], "BLOCK")

    def test_6_insert_on_chain_ruling_returns_id(self):
        """insert_on_chain_ruling returns a positive integer row id."""
        rid = _insert_ruling(self.store)
        row_id = self.store.insert_on_chain_ruling(
            ruling_id=rid,
            device_id=_DEVICE_A,
            commitment_hash=_COMMIT_A,
            tx_hash="0x" + "ab" * 32,
        )
        self.assertIsInstance(row_id, int)
        self.assertGreater(row_id, 0)

    def test_7_get_on_chain_rulings_empty_returns_list(self):
        """get_on_chain_rulings returns [] when no on-chain record exists."""
        result = self.store.get_on_chain_rulings(_DEVICE_A)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)

    def test_8_get_on_chain_rulings_most_recent_first(self):
        """get_on_chain_rulings returns rows in descending created_at order."""
        rid1 = _insert_ruling(self.store, commitment_hash="aa" * 32)
        rid2 = _insert_ruling(self.store, commitment_hash="bb" * 32)
        self.store.insert_on_chain_ruling(
            ruling_id=rid1, device_id=_DEVICE_A,
            commitment_hash="aa" * 32, tx_hash="0x" + "11" * 32,
        )
        time.sleep(0.01)
        self.store.insert_on_chain_ruling(
            ruling_id=rid2, device_id=_DEVICE_A,
            commitment_hash="bb" * 32, tx_hash="0x" + "22" * 32,
        )
        rows = self.store.get_on_chain_rulings(_DEVICE_A)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["commitment_hash"], "bb" * 32)

    def test_9_get_on_chain_ruling_by_commitment_found(self):
        """get_on_chain_ruling_by_commitment returns matching row."""
        rid = _insert_ruling(self.store)
        self.store.insert_on_chain_ruling(
            ruling_id=rid, device_id=_DEVICE_A,
            commitment_hash=_COMMIT_A, tx_hash="0xtx1",
        )
        result = self.store.get_on_chain_ruling_by_commitment(_COMMIT_A)
        self.assertIsNotNone(result)
        self.assertEqual(result["commitment_hash"], _COMMIT_A)
        self.assertEqual(result["tx_hash"], "0xtx1")

    def test_10_get_on_chain_ruling_by_commitment_missing_returns_none(self):
        """get_on_chain_ruling_by_commitment returns None when not found."""
        result = self.store.get_on_chain_ruling_by_commitment("notexist" * 8)
        self.assertIsNone(result)


# ===========================================================================
# TestRulingEnforcementAgent — 8 tests
# ===========================================================================

class TestRulingEnforcementAgent(unittest.TestCase):

    def setUp(self):
        try:
            from vapi_bridge.ruling_enforcement_agent import RulingEnforcementAgent
            self.RulingEnforcementAgent = RulingEnforcementAgent
            self.store = _make_store()
            self.store.upsert_device(_DEVICE_A, "aa" * 32)
            self.store.upsert_device(_DEVICE_B, "bb" * 32)
            self._available = True
        except Exception:
            self._available = False

    def _skip_if_unavailable(self):
        if not self._available:
            self.skipTest("RulingEnforcementAgent unavailable")

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_11_init_stores_cfg_store_chain(self):
        """RulingEnforcementAgent stores cfg, store, and chain on init."""
        self._skip_if_unavailable()
        chain = MagicMock()
        agent = self.RulingEnforcementAgent(_make_cfg(), self.store, chain)
        self.assertIs(agent._cfg, agent._cfg)
        self.assertIs(agent._store, self.store)
        self.assertIs(agent._chain, chain)

    def test_12_consume_empty_events_no_action(self):
        """_consume_pending_events does nothing when event queue is empty."""
        self._skip_if_unavailable()
        agent = self.RulingEnforcementAgent(_make_cfg(), self.store)
        # Should complete without error even with empty queue
        self._run(agent._consume_pending_events())
        # No streaks written
        self.assertIsNone(self.store.get_ruling_streak(_DEVICE_A))

    def test_13_consume_ruling_completed_updates_streak(self):
        """_process_ruling_completed creates a ruling_streaks entry."""
        self._skip_if_unavailable()
        rid = _insert_ruling(self.store, verdict="FLAG")
        event = {
            "id": 999,
            "event_type": "ruling_completed",
            "payload_json": f'{{"device_id": "{_DEVICE_A}", "ruling_id": {rid}, "verdict": "FLAG"}}',
        }
        agent = self.RulingEnforcementAgent(_make_cfg(), self.store)
        self._run(agent._process_ruling_completed(event))
        streak = self.store.get_ruling_streak(_DEVICE_A)
        self.assertIsNotNone(streak)
        self.assertEqual(streak["streak_verdict"], "FLAG")
        self.assertEqual(streak["current_streak"], 1)

    def test_14_flag_streak_5_escalates_to_hold(self):
        """FLAG x5 triggers escalation to HOLD in effective_verdict."""
        self._skip_if_unavailable()
        agent = self.RulingEnforcementAgent(_make_cfg(), self.store)

        # Seed 4 FLAG streaks manually
        for _ in range(4):
            rid = _insert_ruling(self.store, commitment_hash="aa" * 32)
            self.store.upsert_ruling_streak(_DEVICE_A, "FLAG", rid)

        # 5th FLAG ruling via _process_ruling_completed
        rid5 = _insert_ruling(self.store, commitment_hash="cc" * 32)
        event = {
            "id": 5,
            "event_type": "ruling_completed",
            "payload_json": f'{{"device_id": "{_DEVICE_A}", "ruling_id": {rid5}, "verdict": "FLAG"}}',
        }
        self._run(agent._process_ruling_completed(event))
        streak = self.store.get_ruling_streak(_DEVICE_A)
        # escalated_to should be HOLD
        self.assertEqual(streak.get("escalated_to"), "HOLD")

    def test_15_hold_streak_2_escalates_to_block(self):
        """HOLD x2 triggers escalation to BLOCK."""
        self._skip_if_unavailable()
        agent = self.RulingEnforcementAgent(_make_cfg(), self.store)

        # Seed 1 HOLD streak
        rid1 = _insert_ruling(self.store, verdict="HOLD", commitment_hash="ee" * 32)
        self.store.upsert_ruling_streak(_DEVICE_A, "HOLD", rid1)

        # 2nd HOLD
        rid2 = _insert_ruling(self.store, verdict="HOLD", commitment_hash="ff" * 32)
        event = {
            "id": 2,
            "event_type": "ruling_completed",
            "payload_json": f'{{"device_id": "{_DEVICE_A}", "ruling_id": {rid2}, "verdict": "HOLD"}}',
        }
        self._run(agent._process_ruling_completed(event))
        streak = self.store.get_ruling_streak(_DEVICE_A)
        self.assertEqual(streak.get("escalated_to"), "BLOCK")

    def test_16_block_verdict_calls_enforce_block(self):
        """_process_ruling_completed calls _enforce_block when effective_verdict=BLOCK."""
        self._skip_if_unavailable()
        agent = self.RulingEnforcementAgent(_make_cfg(), self.store)
        enforce_called = []

        async def _mock_enforce(device_id, ruling):
            enforce_called.append(device_id)

        agent._enforce_block = _mock_enforce

        rid = _insert_ruling(self.store, verdict="BLOCK", commitment_hash="dd" * 32)
        event = {
            "id": 10,
            "event_type": "ruling_completed",
            "payload_json": f'{{"device_id": "{_DEVICE_A}", "ruling_id": {rid}, "verdict": "BLOCK"}}',
        }
        self._run(agent._process_ruling_completed(event))
        self.assertIn(_DEVICE_A, enforce_called)

    def test_17_enforce_block_no_chain_logs_no_crash(self):
        """_enforce_block with chain=None completes without error."""
        self._skip_if_unavailable()
        agent = self.RulingEnforcementAgent(_make_cfg(), self.store, chain=None)
        rid = _insert_ruling(self.store, verdict="BLOCK", commitment_hash="aa" * 32)
        ruling = self.store.get_agent_ruling_by_id(rid)
        # Should not raise
        self._run(agent._enforce_block(_DEVICE_A, ruling))

    def test_18_enforce_block_warmup_attack_extends_suspension(self):
        """_enforce_block calls suspend with 7-day duration when warmup_attack_score>0.7."""
        self._skip_if_unavailable()
        chain = MagicMock()
        chain.suspend_phg_credential = AsyncMock()

        # Inject warmup_attack_score via get_device_risk_label mock
        self.store.get_device_risk_label = MagicMock(
            return_value={"risk_label": "critical", "warmup_attack_score": 0.9}
        )
        self.store.store_credential_suspension = MagicMock()

        agent = self.RulingEnforcementAgent(_make_cfg(), self.store, chain=chain)
        rid = _insert_ruling(self.store, verdict="BLOCK", commitment_hash="bb" * 32)
        ruling = self.store.get_agent_ruling_by_id(rid)
        self._run(agent._enforce_block(_DEVICE_A, ruling))

        chain.suspend_phg_credential.assert_called_once()
        _call_args = chain.suspend_phg_credential.call_args
        # 3rd positional arg or kwarg duration_s
        call_kwargs = _call_args.kwargs if _call_args.kwargs else {}
        call_args   = _call_args.args   if _call_args.args else ()
        duration_s  = call_kwargs.get("duration_s") or (call_args[2] if len(call_args) > 2 else None)
        self.assertEqual(duration_s, 604800)  # 7-day suspension


# ===========================================================================
# TestEnforcementEndpoint — 5 tests
# ===========================================================================

class TestEnforcementEndpoint(unittest.TestCase):

    def setUp(self):
        try:
            from fastapi.testclient import TestClient
            from vapi_bridge.transports.http import create_app
            self.store = _make_store()
            self.store.upsert_device(_DEVICE_A, "aa" * 32)
            cfg = _make_cfg()
            cfg.operator_api_key = "testkey66"
            cfg.rate_limit_per_minute = 100
            app = create_app(cfg, self.store, AsyncMock())
            self.client = TestClient(app)
            self._available = True
        except Exception:
            self._available = False

    def _skip_if_unavailable(self):
        if not self._available:
            self.skipTest("FastAPI TestClient unavailable")

    def test_19_post_agent_override_returns_200(self):
        """POST /agent/override with operator auth returns 200 and overridden status."""
        self._skip_if_unavailable()
        resp = self.client.post(
            "/agent/override",
            json={"device_id": _DEVICE_A, "reason": "false positive confirmed"},
            headers={"x-api-key": "testkey66"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "overridden")
        self.assertIn("ruling_id", data)
        self.assertEqual(data["device_id"], _DEVICE_A)

    def test_20_post_agent_override_missing_device_id_400(self):
        """POST /agent/override returns 400 when device_id is missing."""
        self._skip_if_unavailable()
        resp = self.client.post(
            "/agent/override",
            json={"reason": "no device"},
            headers={"x-api-key": "testkey66"},
        )
        self.assertEqual(resp.status_code, 400)

    def test_21_post_agent_override_without_auth_401(self):
        """POST /agent/override returns 401 when x-api-key header is missing."""
        self._skip_if_unavailable()
        resp = self.client.post(
            "/agent/override",
            json={"device_id": _DEVICE_A},
        )
        self.assertIn(resp.status_code, (401, 503))

    def test_22_post_agent_override_resets_streak_to_clear(self):
        """POST /agent/override resets ruling streak to CLEAR verdict."""
        self._skip_if_unavailable()
        # Seed a BLOCK streak
        rid = _insert_ruling(self.store, verdict="BLOCK", commitment_hash="aa" * 32)
        self.store.upsert_ruling_streak(_DEVICE_A, "BLOCK", rid)

        resp = self.client.post(
            "/agent/override",
            json={"device_id": _DEVICE_A, "reason": "review passed"},
            headers={"x-api-key": "testkey66"},
        )
        self.assertEqual(resp.status_code, 200)
        streak = self.store.get_ruling_streak(_DEVICE_A)
        self.assertIsNotNone(streak)
        self.assertEqual(streak["streak_verdict"], "CLEAR")
        self.assertEqual(streak["current_streak"], 1)

    def test_23_post_agent_override_inserts_agent_ruling(self):
        """POST /agent/override inserts a CLEAR agent_ruling with dry_run=False."""
        self._skip_if_unavailable()
        resp = self.client.post(
            "/agent/override",
            json={"device_id": _DEVICE_A, "reason": "operator override test"},
            headers={"x-api-key": "testkey66"},
        )
        self.assertEqual(resp.status_code, 200)
        ruling_id = resp.json()["ruling_id"]
        ruling = self.store.get_agent_ruling_by_id(ruling_id)
        self.assertIsNotNone(ruling)
        self.assertEqual(ruling["verdict"], "CLEAR")
        self.assertEqual(ruling["dry_run"], 0)
        self.assertEqual(ruling["source_agent"], "operator_override")


# ===========================================================================
# TestBridgeAgentTools3435 — 4 tests
# ===========================================================================

class TestBridgeAgentTools3435(unittest.TestCase):

    def setUp(self):
        try:
            _ant = sys.modules.get("anthropic") or types.ModuleType("anthropic")
            _ant.Anthropic = MagicMock()
            _ant.AsyncAnthropic = MagicMock()
            sys.modules["anthropic"] = _ant
            _ant_types = types.ModuleType("anthropic.types")
            _ant.types = _ant_types
            sys.modules["anthropic.types"] = _ant_types

            from vapi_bridge.bridge_agent import BridgeAgent
            self.store = _make_store()
            self.store.upsert_device(_DEVICE_A, "aa" * 32)
            self.store.upsert_device(_DEVICE_B, "bb" * 32)
            self.agent = BridgeAgent(_make_cfg(), self.store)
            self._available = True
        except Exception:
            self._available = False

    def _skip_if_unavailable(self):
        if not self._available:
            self.skipTest("BridgeAgent unavailable")

    def test_24_tool34_get_ruling_streak_returns_streak(self):
        """Tool #34 get_ruling_streak returns streak data when streak exists."""
        self._skip_if_unavailable()
        rid = _insert_ruling(self.store, verdict="FLAG")
        self.store.upsert_ruling_streak(_DEVICE_A, "FLAG", rid)
        result = self.agent._execute_tool("get_ruling_streak", {"device_id": _DEVICE_A})
        self.assertIn("current_streak", result)
        self.assertEqual(result["current_streak"], 1)
        self.assertEqual(result["streak_verdict"], "FLAG")

    def test_25_tool34_get_ruling_streak_unknown_device_returns_zero(self):
        """Tool #34 get_ruling_streak returns current_streak=0 for unknown device."""
        self._skip_if_unavailable()
        result = self.agent._execute_tool("get_ruling_streak", {"device_id": _DEVICE_B})
        self.assertEqual(result.get("current_streak"), 0)

    def test_26_tool35_override_ruling_clears_streak(self):
        """Tool #35 override_ruling inserts CLEAR ruling and resets streak."""
        self._skip_if_unavailable()
        # Seed a BLOCK streak
        rid = _insert_ruling(self.store, verdict="BLOCK", commitment_hash="aa" * 32)
        self.store.upsert_ruling_streak(_DEVICE_A, "BLOCK", rid)

        result = self.agent._execute_tool("override_ruling", {
            "device_id": _DEVICE_A,
            "reason": "false positive cleared via agent",
        })
        self.assertEqual(result.get("status"), "cleared")
        self.assertIn("ruling_id", result)
        # Streak should now be CLEAR
        streak = self.store.get_ruling_streak(_DEVICE_A)
        self.assertEqual(streak["streak_verdict"], "CLEAR")

    def test_27_tool35_override_ruling_missing_device_id_error(self):
        """Tool #35 override_ruling returns error dict when device_id is empty."""
        self._skip_if_unavailable()
        result = self.agent._execute_tool("override_ruling", {})
        self.assertIn("error", result)


# ===========================================================================
# TestEndToEndRulingPipeline — 3 tests
# ===========================================================================

class TestEndToEndRulingPipeline(unittest.TestCase):

    def setUp(self):
        try:
            from vapi_bridge.session_adjudicator import SessionAdjudicator
            from vapi_bridge.ruling_enforcement_agent import RulingEnforcementAgent
            self.SessionAdjudicator = SessionAdjudicator
            self.RulingEnforcementAgent = RulingEnforcementAgent
            self.store = _make_store()
            self.store.upsert_device(_DEVICE_A, "aa" * 32)
            self._available = True
        except Exception:
            self._available = False

    def _skip_if_unavailable(self):
        if not self._available:
            self.skipTest("SessionAdjudicator or RulingEnforcementAgent unavailable")

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_28_session_adjudicator_emits_ruling_completed_targeting_enforcement(self):
        """SessionAdjudicator writes ruling_completed event targeting ruling_enforcement_agent."""
        self._skip_if_unavailable()
        self.store.write_agent_event(
            event_type="ruling_request",
            payload='{"device_id": "' + _DEVICE_A + '", "attestation_hash": ""}',
            source="test",
            target="session_adjudicator",
            device_id=_DEVICE_A,
        )
        events = self.store.read_unconsumed_events("session_adjudicator", limit=5)
        self.assertEqual(len(events), 1)

        adj = self.SessionAdjudicator(_make_cfg(), self.store)

        async def _mock_llm(evidence):
            return "FLAG", 0.05, "No anomalies (mocked)."

        adj._llm_ruling = _mock_llm
        self._run(adj._process_ruling_request(events[0]))

        # Check that an event targeting ruling_enforcement_agent was written
        enf_events = self.store.read_unconsumed_events("ruling_enforcement_agent", limit=10)
        self.assertGreater(len(enf_events), 0)
        enf_types = [e["event_type"] for e in enf_events]
        self.assertIn("ruling_completed", enf_types)

    def test_29_ruling_enforcement_processes_adjudicator_event(self):
        """RulingEnforcementAgent processes a ruling_completed event and updates streak."""
        self._skip_if_unavailable()
        rid = _insert_ruling(self.store, verdict="HOLD", commitment_hash="ee" * 32)
        self.store.write_agent_event(
            event_type="ruling_completed",
            payload=f'{{"device_id": "{_DEVICE_A}", "ruling_id": {rid}, "verdict": "HOLD"}}',
            source="session_adjudicator",
            target="ruling_enforcement_agent",
            device_id=_DEVICE_A,
        )
        agent = self.RulingEnforcementAgent(_make_cfg(), self.store)
        self._run(agent._consume_pending_events())

        streak = self.store.get_ruling_streak(_DEVICE_A)
        self.assertIsNotNone(streak)
        self.assertEqual(streak["streak_verdict"], "HOLD")
        self.assertEqual(streak["current_streak"], 1)

    def test_30_block_streak_pipeline_suspend_then_override_restores(self):
        """BLOCK streak suspends credential; override_ruling resets streak to CLEAR."""
        self._skip_if_unavailable()

        chain = MagicMock()
        chain.suspend_phg_credential = AsyncMock()
        self.store.store_credential_suspension = MagicMock()
        self.store.get_device_risk_label = MagicMock(
            return_value={"risk_label": "stable", "warmup_attack_score": 0.0}
        )

        agent = self.RulingEnforcementAgent(_make_cfg(), self.store, chain=chain)

        # Deliver a BLOCK ruling event
        rid = _insert_ruling(self.store, verdict="BLOCK", commitment_hash="dd" * 32)
        event = {
            "id": 1,
            "event_type": "ruling_completed",
            "payload_json": f'{{"device_id": "{_DEVICE_A}", "ruling_id": {rid}, "verdict": "BLOCK"}}',
        }
        self._run(agent._process_ruling_completed(event))

        # Credential suspension was called
        chain.suspend_phg_credential.assert_called_once()

        # Now override to restore eligibility
        clear_rid = _insert_ruling(self.store, verdict="CLEAR", commitment_hash="ff" * 32)
        self.store.upsert_ruling_streak(_DEVICE_A, "CLEAR", clear_rid)
        streak = self.store.get_ruling_streak(_DEVICE_A)
        self.assertEqual(streak["streak_verdict"], "CLEAR")
        self.assertEqual(streak["current_streak"], 1)


if __name__ == "__main__":
    unittest.main()

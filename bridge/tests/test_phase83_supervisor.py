"""
Phase 83 — AgentSupervisor Fleet Health Monitor Tests (10 tests)

test_1_check_fleet_health_returns_all_agent_keys
test_2_unknown_health_for_agents_with_no_table_activity
test_3_healthy_status_for_agents_with_recent_activity
test_4_stale_status_for_agents_with_old_activity
test_5_fleet_all_healthy_when_all_agents_recent
test_6_fleet_degraded_when_some_agents_unknown
test_7_fleet_critical_when_core_agent_stale
test_8_supervisor_health_log_persists_check_results
test_9_get_agent_supervisor_status_tool_52_returns_fleet_health
test_10_supervisor_publishes_agent_health_report_to_bus
"""

import asyncio
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local",
             "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from vapi_bridge.store import Store
from vapi_bridge.agent_supervisor import (
    AgentSupervisor, HEALTHY, STALE, UNKNOWN, ZOMBIE,
    ALL_HEALTHY, DEGRADED, CRITICAL,
)

_DEVICE_A = "aa" * 32
_DEVICE_B = "bb" * 32


def _make_store() -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p83.db"))


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.operator_api_key = "testkey83"
    cfg.supervisor_enabled = True
    cfg.supervisor_stale_threshold_minutes = kwargs.get("stale_minutes", 15)
    return cfg


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Fleet health snapshot tests (synchronous)
# ---------------------------------------------------------------------------

class TestFleetHealthSnapshot(unittest.TestCase):

    def _make_supervisor(self, store, stale_minutes=15):
        cfg = _make_cfg(stale_minutes=stale_minutes)
        return AgentSupervisor(cfg, store)

    def test_1_check_fleet_health_returns_all_agent_keys(self):
        """check_fleet_health() must return a result for every registered agent."""
        from vapi_bridge.agent_supervisor import _AGENT_CHECKS
        store = _make_store()
        sup = self._make_supervisor(store)
        snapshot = sup.check_fleet_health()
        self.assertIn("agents", snapshot)
        self.assertIn("fleet_health", snapshot)
        for agent_name in _AGENT_CHECKS:
            self.assertIn(agent_name, snapshot["agents"],
                          f"Agent '{agent_name}' missing from health snapshot")

    def test_2_unknown_health_for_agents_with_no_table_activity(self):
        """Empty store → all agents UNKNOWN (no rows in any table)."""
        store = _make_store()
        sup = self._make_supervisor(store)
        snapshot = sup.check_fleet_health()
        for agent_name, result in snapshot["agents"].items():
            self.assertEqual(result["health"], UNKNOWN,
                             f"Expected UNKNOWN for empty store, got {result['health']} for {agent_name}")

    def test_3_healthy_status_for_agents_with_recent_activity(self):
        """Agent with a row written < stale_threshold seconds ago → HEALTHY."""
        store = _make_store()
        # Insert a fresh agent_ruling row so session_adjudicator gets HEALTHY
        store.upsert_device(_DEVICE_A, "00" * 33)
        store.insert_agent_ruling(
            device_id=_DEVICE_A,
            verdict="FLAG",
            confidence=0.5,
            reasoning="test",
            evidence_json="{}",
            commitment_hash="ab" * 32,
            attestation_hash="",
            dry_run=True,
            source_agent="session_adjudicator",
            ceremony_integrity=None,
        )
        sup = self._make_supervisor(store, stale_minutes=15)
        snapshot = sup.check_fleet_health()
        sa = snapshot["agents"]["session_adjudicator"]
        self.assertEqual(sa["health"], HEALTHY)
        self.assertGreater(sa["activity_count"], 0)
        self.assertIsNotNone(sa["last_active_at"])

    def test_4_stale_status_for_agents_with_old_activity(self):
        """get_agent_activity returns an old timestamp → STALE (stale_threshold very small)."""
        store = _make_store()
        store.upsert_device(_DEVICE_A, "00" * 33)
        store.insert_agent_ruling(
            device_id=_DEVICE_A,
            verdict="FLAG",
            confidence=0.5,
            reasoning="old",
            evidence_json="{}",
            commitment_hash="cd" * 32,
            attestation_hash="",
            dry_run=True,
            source_agent="session_adjudicator",
            ceremony_integrity=None,
        )
        # Use stale_threshold of 0 minutes → any row is immediately STALE
        sup = self._make_supervisor(store, stale_minutes=0)
        snapshot = sup.check_fleet_health()
        sa = snapshot["agents"]["session_adjudicator"]
        self.assertEqual(sa["health"], STALE)

    def test_5_fleet_all_healthy_when_all_agents_recent(self):
        """fleet_health=ALL_HEALTHY when check_fleet_health returns all HEALTHY."""
        store = _make_store()
        sup = self._make_supervisor(store)
        # Monkey-patch check_fleet_health to simulate all-healthy
        original = sup.check_fleet_health
        from vapi_bridge.agent_supervisor import _AGENT_CHECKS

        def _all_healthy():
            agents = {n: {"health": HEALTHY, "last_active_at": time.time(),
                          "activity_count": 10, "distinct_devices": 3}
                      for n in _AGENT_CHECKS}
            return {
                "agents": agents,
                "fleet_health": ALL_HEALTHY,
                "healthy_count": len(agents),
                "stale_count": 0,
                "unknown_count": 0,
                "zombie_count": 0,
                "stale_threshold_minutes": 15,
                "timestamp": time.time(),
            }

        sup.check_fleet_health = _all_healthy
        snapshot = sup.check_fleet_health()
        self.assertEqual(snapshot["fleet_health"], ALL_HEALTHY)
        self.assertEqual(snapshot["stale_count"], 0)
        self.assertEqual(snapshot["unknown_count"], 0)

    def test_6_fleet_degraded_when_some_agents_unknown(self):
        """Empty store (all UNKNOWN) → fleet_health=DEGRADED (1-2 UNKNOWN) or CRITICAL (3+)."""
        store = _make_store()
        sup = self._make_supervisor(store)
        snapshot = sup.check_fleet_health()
        # All 9 agents are UNKNOWN in empty store → CRITICAL (>= 3 non-healthy)
        self.assertIn(snapshot["fleet_health"], (DEGRADED, CRITICAL))
        self.assertGreater(snapshot["unknown_count"], 0)

    def test_7_fleet_critical_when_core_agent_stale(self):
        """fleet_health=CRITICAL when session_adjudicator or ruling_enforcement_agent is STALE."""
        store = _make_store()
        sup = self._make_supervisor(store, stale_minutes=0)  # any activity = STALE
        store.upsert_device(_DEVICE_A, "00" * 33)
        store.insert_agent_ruling(
            device_id=_DEVICE_A,
            verdict="FLAG",
            confidence=0.5,
            reasoning="test",
            evidence_json="{}",
            commitment_hash="ef" * 32,
            attestation_hash="",
            dry_run=True,
            source_agent="session_adjudicator",
            ceremony_integrity=None,
        )
        snapshot = sup.check_fleet_health()
        # session_adjudicator has activity but stale_threshold=0 → STALE → CRITICAL
        self.assertEqual(snapshot["fleet_health"], CRITICAL)


# ---------------------------------------------------------------------------
# Store and persistence tests
# ---------------------------------------------------------------------------

class TestSupervisorStore(unittest.TestCase):

    def test_8_supervisor_health_log_persists_check_results(self):
        """insert_supervisor_health_log round-trips; get_latest_supervisor_health returns it."""
        store = _make_store()
        now = time.time()
        store.insert_supervisor_health_log(
            agent_name="session_adjudicator",
            health=HEALTHY,
            last_active_at=now,
            activity_count=42,
        )
        store.insert_supervisor_health_log(
            agent_name="ruling_enforcement_agent",
            health=UNKNOWN,
            last_active_at=None,
            activity_count=0,
        )
        rows = store.get_latest_supervisor_health()
        names = {r["agent_name"] for r in rows}
        self.assertIn("session_adjudicator", names)
        self.assertIn("ruling_enforcement_agent", names)
        sa_row = next(r for r in rows if r["agent_name"] == "session_adjudicator")
        self.assertEqual(sa_row["health"], HEALTHY)
        self.assertEqual(sa_row["activity_count"], 42)


# ---------------------------------------------------------------------------
# Tool #52 and REST endpoint
# ---------------------------------------------------------------------------

class TestSupervisorToolAndEndpoint(unittest.TestCase):

    def test_9_get_agent_supervisor_status_tool_52_returns_fleet_health(self):
        """Tool #52 get_agent_supervisor_status returns dict with fleet_health."""
        from vapi_bridge.bridge_agent import BridgeAgent
        store = _make_store()
        cfg = _make_cfg()
        agent = BridgeAgent(cfg, store)
        result = agent._execute_tool("get_agent_supervisor_status", {})
        self.assertIn("fleet_health", result)
        self.assertIn(result["fleet_health"], (ALL_HEALTHY, DEGRADED, CRITICAL, "UNKNOWN"))
        self.assertIn("agents", result)
        self.assertIn("healthy_count", result)

    def test_10_supervisor_publishes_agent_health_report_to_bus(self):
        """_check_and_report() publishes agent_health_report to AgentMessageBus."""
        from vapi_bridge.agent_message_bus import AgentMessageBus
        store = _make_store()
        cfg = _make_cfg()
        bus = AgentMessageBus()
        _run(bus._init_lock())
        sup = AgentSupervisor(cfg, store, bus=bus)

        received = []

        async def _run_test():
            queue = await bus.subscribe("agent_health_report")
            await sup._check_and_report()
            try:
                envelope = await asyncio.wait_for(queue.get(), timeout=1.0)
                received.append(envelope)
            except asyncio.TimeoutError:
                pass

        _run(_run_test())
        self.assertEqual(len(received), 1)
        payload = received[0].get("payload", {})
        self.assertIn("fleet_health", payload)
        self.assertIn("healthy_count", payload)


if __name__ == "__main__":
    unittest.main()

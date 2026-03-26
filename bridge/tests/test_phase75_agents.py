"""
Phase 75 — SessionAdjudicatorValidationAgent + CeremonyWatchdogAgent Tests (10 tests)

Tests the two Phase 75 autonomous agents and their supporting store/config primitives:

  test_1: _rule_fallback hard_cheat_codes → BLOCK/0.9
  test_2: _rule_fallback eligible enrollment → CERTIFY/0.8
  test_3: insert_validation_record stores row in ruling_validation_log
  test_4: get_validation_summary consecutive_clean correct (no divergences)
  test_5: get_validation_summary consecutive_clean resets at first divergence
  test_6: get_validation_gate_status returns recommended_action field
  test_7: _validate_ruling no divergence when verdicts match
  test_8: _validate_ruling divergence when verdicts differ AND conf delta > threshold
  test_9: _validate_ruling no divergence when verdicts differ but conf delta <= threshold
  test_10: CeremonyWatchdogAgent invalidates SA cache on fingerprint change
"""

import asyncio
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

# Stub heavy optional dependencies before any bridge imports
for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local",
             "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

# Stub SDK to avoid path issues in bridge test context
_sdk_stub = types.ModuleType("sdk")
_sdk_vapi_stub = types.ModuleType("sdk.vapi_sdk")
sys.modules.setdefault("sdk", _sdk_stub)
sys.modules.setdefault("sdk.vapi_sdk", _sdk_vapi_stub)

from vapi_bridge.store import Store
from vapi_bridge.session_adjudicator_validator import (
    SessionAdjudicatorValidationAgent,
    _rule_fallback,
)


def _make_store():
    tmp = tempfile.mkdtemp()
    db = os.path.join(tmp, "test_phase75.db")
    st = Store(db)
    st.upsert_device("0xdevice01", "pubkey_hex_01")
    return st


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.validation_divergence_threshold = kwargs.get("validation_divergence_threshold", 0.3)
    cfg.validation_gate_n = kwargs.get("validation_gate_n", 100)
    cfg.ceremony_registry_address = kwargs.get("ceremony_registry_address", "0xCeremony")
    cfg.iotex_rpc_url = kwargs.get("iotex_rpc_url", "https://babel-api.testnet.iotex.io")
    cfg.ceremony_watchdog_enabled = kwargs.get("ceremony_watchdog_enabled", True)
    return cfg


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ──────────────────────────────────────────────────────────────────
# Tests 1–2: _rule_fallback deterministic oracle
# ──────────────────────────────────────────────────────────────────

class TestRuleFallback(unittest.TestCase):

    def test_1_hard_cheat_codes_returns_block(self):
        """test_1: evidence with hard_cheat_codes → BLOCK, confidence 0.9."""
        verdict, confidence, _ = _rule_fallback({"hard_cheat_codes": ["0x28"]})
        self.assertEqual(verdict, "BLOCK")
        self.assertAlmostEqual(confidence, 0.9)

    def test_2_eligible_enrollment_returns_certify(self):
        """test_2: enrollment_status=eligible → CERTIFY, confidence 0.8."""
        verdict, confidence, _ = _rule_fallback({"enrollment_status": "eligible"})
        self.assertEqual(verdict, "CERTIFY")
        self.assertAlmostEqual(confidence, 0.8)


# ──────────────────────────────────────────────────────────────────
# Tests 3–6: Store primitives (ruling_validation_log)
# ──────────────────────────────────────────────────────────────────

class TestValidationStore(unittest.TestCase):

    def test_3_insert_validation_record_stores_row(self):
        """test_3: insert_validation_record writes to ruling_validation_log."""
        store = _make_store()
        # Insert a ruling first so FK reference is valid
        ruling_id = store.insert_agent_ruling(
            device_id="0xdevice01",
            verdict="FLAG",
            confidence=0.05,
            reasoning="test",
            evidence_json="{}",
            commitment_hash="0x" + "ab" * 32,
        )
        record_id = store.insert_validation_record(
            ruling_id=ruling_id,
            device_id="0xdevice01",
            llm_verdict="FLAG",
            fallback_verdict="FLAG",
            llm_confidence=0.05,
            fallback_confidence=0.05,
            divergence=0,
        )
        self.assertGreater(record_id, 0)

        summary = store.get_validation_summary(gate_n=10)
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["divergence_count"], 0)
        self.assertGreaterEqual(summary["consecutive_clean"], 1)

    def test_4_get_validation_summary_consecutive_clean_no_divergences(self):
        """test_4: N clean records → consecutive_clean == N."""
        store = _make_store()
        for i in range(5):
            rid = store.insert_agent_ruling(
                device_id="0xdevice01",
                verdict="FLAG",
                confidence=0.1,
                reasoning="test",
                evidence_json="{}",
                commitment_hash="0x" + f"{i:02x}" * 32,
            )
            store.insert_validation_record(
                ruling_id=rid,
                device_id="0xdevice01",
                llm_verdict="FLAG",
                fallback_verdict="FLAG",
                llm_confidence=0.1,
                fallback_confidence=0.1,
                divergence=0,
            )

        summary = store.get_validation_summary(gate_n=10)
        self.assertEqual(summary["total"], 5)
        self.assertEqual(summary["consecutive_clean"], 5)
        self.assertFalse(summary["gate_passed"])

    def test_5_get_validation_summary_consecutive_clean_resets_at_divergence(self):
        """test_5: divergence mid-sequence → consecutive_clean counts only trailing cleans."""
        store = _make_store()
        # 2 clean, 1 divergent, 3 clean → consecutive_clean = 3
        sequence = [0, 0, 1, 0, 0, 0]  # divergence=1 at index 2
        for i, div in enumerate(sequence):
            rid = store.insert_agent_ruling(
                device_id="0xdevice01",
                verdict="FLAG",
                confidence=0.1,
                reasoning="test",
                evidence_json="{}",
                commitment_hash="0x" + f"{i+10:02x}" * 32,
            )
            store.insert_validation_record(
                ruling_id=rid,
                device_id="0xdevice01",
                llm_verdict="BLOCK" if div else "FLAG",
                fallback_verdict="FLAG",
                llm_confidence=0.9 if div else 0.1,
                fallback_confidence=0.1,
                divergence=div,
            )

        summary = store.get_validation_summary(gate_n=20)
        self.assertEqual(summary["total"], 6)
        self.assertEqual(summary["divergence_count"], 1)
        self.assertEqual(summary["consecutive_clean"], 3)

    def test_6_get_validation_gate_status_has_recommended_action(self):
        """test_6: get_validation_gate_status includes recommended_action key."""
        store = _make_store()
        status = store.get_validation_gate_status(gate_n=100)
        self.assertIn("recommended_action", status)
        self.assertIn("gate_passed", status)
        self.assertIn("consecutive_clean", status)
        self.assertIn("total", status)


# ──────────────────────────────────────────────────────────────────
# Tests 7–9: SessionAdjudicatorValidationAgent._validate_ruling
# ──────────────────────────────────────────────────────────────────

class TestValidationAgent(unittest.TestCase):

    def _make_agent(self, threshold=0.3, gate_n=100):
        cfg = _make_cfg(validation_divergence_threshold=threshold, validation_gate_n=gate_n)
        store = _make_store()
        agent = SessionAdjudicatorValidationAgent(cfg, store)
        return agent, store

    def _make_ruling_row(self, store, verdict="FLAG", confidence=0.05,
                         evidence=None):
        """Insert a ruling and return the row dict."""
        ev = json.dumps(evidence or {})
        rid = store.insert_agent_ruling(
            device_id="0xdevice01",
            verdict=verdict,
            confidence=confidence,
            reasoning="test",
            evidence_json=ev,
            commitment_hash="0x" + "de" * 32,
        )
        with store._conn() as conn:
            row = conn.execute(
                "SELECT * FROM agent_rulings WHERE id=?", (rid,)
            ).fetchone()
        return dict(row)

    def test_7_no_divergence_when_verdicts_match(self):
        """test_7: LLM and fallback agree → divergence=0 in validation_log."""
        agent, store = self._make_agent()
        # FLAG/0.05 from LLM — _rule_fallback({}) also returns FLAG/0.05
        row = self._make_ruling_row(store, verdict="FLAG", confidence=0.05, evidence={})

        _run(agent._validate_ruling(row))

        with store._conn() as conn:
            rec = conn.execute(
                "SELECT * FROM ruling_validation_log WHERE ruling_id=?", (row["id"],)
            ).fetchone()
        self.assertIsNotNone(rec)
        self.assertEqual(rec["divergence"], 0)

    def test_8_divergence_when_verdicts_differ_and_large_conf_delta(self):
        """test_8: LLM=BLOCK/0.9 vs fallback=FLAG/0.05 → divergence=1."""
        agent, store = self._make_agent(threshold=0.3)
        # No hard_cheat_codes in evidence, so fallback=FLAG/0.05
        # LLM disagrees with high confidence
        row = self._make_ruling_row(
            store, verdict="BLOCK", confidence=0.9, evidence={}
        )

        _run(agent._validate_ruling(row))

        with store._conn() as conn:
            rec = conn.execute(
                "SELECT * FROM ruling_validation_log WHERE ruling_id=?", (row["id"],)
            ).fetchone()
        self.assertIsNotNone(rec)
        self.assertEqual(rec["divergence"], 1)

    def test_9_no_divergence_when_conf_delta_below_threshold(self):
        """test_9: verdicts differ but |conf_delta| <= threshold → divergence=0 (soft)."""
        agent, store = self._make_agent(threshold=0.5)
        # LLM=BLOCK/0.5, fallback(_rule_fallback({}))=FLAG/0.05 → delta=0.45 < threshold 0.5
        row = self._make_ruling_row(
            store, verdict="BLOCK", confidence=0.5, evidence={}
        )

        _run(agent._validate_ruling(row))

        with store._conn() as conn:
            rec = conn.execute(
                "SELECT * FROM ruling_validation_log WHERE ruling_id=?", (row["id"],)
            ).fetchone()
        self.assertIsNotNone(rec)
        self.assertEqual(rec["divergence"], 0)


# ──────────────────────────────────────────────────────────────────
# Test 10: CeremonyWatchdogAgent cache invalidation
# ──────────────────────────────────────────────────────────────────

class TestCeremonyWatchdog(unittest.TestCase):

    def test_10_watchdog_invalidates_sa_cache_on_fingerprint_change(self):
        """test_10: CeremonyWatchdogAgent._invalidate_ceremony_cache clears SA module cache."""
        from vapi_bridge.ceremony_watchdog import CeremonyWatchdogAgent
        import vapi_bridge.session_adjudicator as _sa_mod

        # Populate the SA module-level cache with a sentinel value
        _sa_mod._CEREMONY_CACHE["PitlSessionProof"] = {
            "data": {"on_chain_match": True},
            "ts": 9999999999.0,
        }
        self.assertIn("PitlSessionProof", _sa_mod._CEREMONY_CACHE)

        cfg = _make_cfg()
        store = _make_store()
        watchdog = CeremonyWatchdogAgent(cfg, store)
        watchdog._invalidate_ceremony_cache()

        # Cache must be empty after invalidation
        self.assertEqual(len(_sa_mod._CEREMONY_CACHE), 0)


if __name__ == "__main__":
    unittest.main()

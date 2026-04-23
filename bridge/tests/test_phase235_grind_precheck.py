"""
Pre-Grind Validation Tests — 2026-04-22

Category 2: LLM API Failure Modes (T235-GPC-1, T235-GPC-2)
Category 5: GIC Chain-Break Recovery — POST /operator/gic-reset (T235-GPC-3, T235-GPC-4)

These tests verify that:
  - The GIC chain is not blocked by LLM API unavailability (Category 2)
  - Operators can clear the gic_chain_broken flag via an authenticated endpoint (Category 5)

T235-GPC-1: _llm_ruling() catches any exception and returns deterministic fallback tuple
T235-GPC-2: When LLM fails, ruling_validation_log still writes with divergence=0 and
            consecutive_clean advances (given pcc_state=NOMINAL/EXCLUSIVE_USB)
T235-GPC-3: POST /operator/gic-reset requires valid operator api_key (401/403 without)
T235-GPC-4: POST /operator/gic-reset clears app._gic_chain_broken and returns JSON
"""

import asyncio
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)


def _make_store(tmp_dir=None):
    from vapi_bridge.store import Store
    td = tmp_dir or tempfile.mkdtemp()
    return Store(str(Path(td) / "test_pgv.db"))


def _make_cfg(**kwargs):
    from vapi_bridge.config import Config
    defaults = dict(
        grind_mode=True,
        grind_session_id="grind_test_pgv",
        operator_api_key="pgvtestkey",
    )
    defaults.update(kwargs)
    return Config(**defaults)


# ---------------------------------------------------------------------------
# T235-GPC-1: LLM exception → fallback executes, returns deterministic tuple
# ---------------------------------------------------------------------------

class TestLLMAPIFailureModes(unittest.TestCase):

    def test_1_llm_unavailable_fallback_executes_deterministically(self):
        """T235-GPC-1: When _llm_ruling raises any exception, fallback verdict returned.

        Modes covered: (a) no API key — anthropic raises AuthenticationError;
                       (c) network error — any connection exception.

        In both cases _rule_fallback(evidence) produces the same deterministic tuple
        independent of LLM availability.
        """
        # Stub anthropic module so import succeeds but the class raises
        _anth_stub = types.ModuleType("anthropic")

        class _FailingClient:
            def __init__(self):
                raise ConnectionError("Simulated network unreachable (Category 2 mode c)")

        _anth_stub.AsyncAnthropic = _FailingClient
        _anth_stub.AuthenticationError = Exception  # make it catch-able

        with patch.dict(sys.modules, {"anthropic": _anth_stub}):
            from vapi_bridge.session_adjudicator import SessionAdjudicator
            cfg = _make_cfg()
            store = _make_store()
            # Minimal SessionAdjudicator construction without full DI
            adj = SessionAdjudicator.__new__(SessionAdjudicator)
            adj._cfg = cfg
            adj._store = store
            adj._threshold = 0.30

            # Run the async _llm_ruling
            evidence = {}  # clean session, no anomalies
            result = asyncio.run(adj._llm_ruling(evidence))

        # Must have returned a 3-tuple (verdict, confidence, reasoning)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 3)
        verdict, confidence, reasoning = result

        # Verify it matches _rule_fallback output for a clean session
        from vapi_bridge.session_adjudicator import SessionAdjudicator as SA
        expected_verdict, expected_conf, _ = SA._rule_fallback(evidence)
        self.assertEqual(verdict, expected_verdict,
                         "LLM failure must produce same verdict as _rule_fallback")
        self.assertAlmostEqual(confidence, expected_conf, places=4,
                               msg="LLM failure must produce same confidence as _rule_fallback")

    def test_2_llm_fallback_ruling_produces_no_divergence_consecutive_clean_advances(self):
        """T235-GPC-2: When LLM fails and stores fallback as ruling verdict, the
        validator finds llm_verdict == fallback_verdict → divergence=0 → consecutive_clean+1.

        This is the critical grind-safety invariant: LLM unavailability must not
        break the grind streak or prevent GIC stamping.
        """
        store = _make_store()
        cfg = _make_cfg()

        # Simulate: LLM failed, so agent_rulings stores the fallback verdict
        # For a clean session: fallback = FLAG(0.05)
        store.upsert_device("dev_pgv", "00" * 32)
        ruling_id = store.insert_agent_ruling(
            device_id="dev_pgv",
            verdict="FLAG",       # fallback result stored as llm_verdict
            confidence=0.05,
            reasoning="rule fallback (LLM unavailable)",
            evidence_json="{}",
            commitment_hash="ab" * 32,
        )

        # Validator runs independently: re-derives fallback_verdict = FLAG(0.05)
        # llm_verdict(FLAG) == fallback_verdict(FLAG) → divergence=0
        val_row_id = store.insert_validation_record(
            ruling_id=ruling_id,
            device_id="dev_pgv",
            llm_verdict="FLAG",       # what was stored (from fallback)
            fallback_verdict="FLAG",  # what validator derives fresh
            llm_confidence=0.05,
            fallback_confidence=0.05,
            divergence=0,
            pcc_state="NOMINAL",
            pcc_host_state="EXCLUSIVE_USB",
        )
        self.assertGreater(val_row_id, 0)

        # consecutive_clean must advance
        summary = store.get_validation_summary(gate_n=100)
        self.assertEqual(summary["consecutive_clean"], 1,
                         "LLM failure must not block consecutive_clean advancement")
        self.assertEqual(summary["divergence_count"], 0)


# ---------------------------------------------------------------------------
# T235-GPC-3/4: POST /operator/gic-reset
# ---------------------------------------------------------------------------

class TestGICResetEndpoint(unittest.TestCase):

    def _make_client(self, broken=True):
        from fastapi.testclient import TestClient
        from vapi_bridge.operator_api import create_operator_app
        store = _make_store()
        cfg = _make_cfg()
        app_inst = create_operator_app(cfg, store)
        app_inst._gic_chain_broken = broken
        return TestClient(app_inst, raise_server_exceptions=False), app_inst

    def test_3_gic_reset_requires_valid_api_key(self):
        """T235-GPC-3: POST /operator/gic-reset returns 403 without valid key."""
        client, _ = self._make_client()
        # No key
        resp = client.post("/operator/gic-reset", params={"reason": "test recovery"})
        self.assertIn(resp.status_code, (401, 403, 503))

        # Wrong key
        resp = client.post("/operator/gic-reset",
                           params={"api_key": "wrongkey", "reason": "test recovery"})
        self.assertIn(resp.status_code, (401, 403))

    def test_4_gic_reset_clears_flag_and_returns_json(self):
        """T235-GPC-4: POST /operator/gic-reset with valid key clears app._gic_chain_broken."""
        client, app_inst = self._make_client(broken=True)
        self.assertTrue(app_inst._gic_chain_broken)

        resp = client.post(
            "/operator/gic-reset",
            params={"api_key": "pgvtestkey", "reason": "DB restored from clean backup"},
        )
        self.assertEqual(resp.status_code, 200, f"Response: {resp.text}")
        data = resp.json()

        self.assertTrue(data["accepted"])
        self.assertTrue(data["was_broken"], "was_broken must reflect pre-reset state")
        self.assertIn("reason", data)
        self.assertIn("timestamp", data)
        self.assertFalse(app_inst._gic_chain_broken,
                         "app._gic_chain_broken must be False after reset")


if __name__ == "__main__":
    unittest.main()

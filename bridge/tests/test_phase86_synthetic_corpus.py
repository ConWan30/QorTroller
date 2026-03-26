"""
Phase 86 — Synthetic Session Corpus Pipeline Tests (8 tests)

test_1_generate_session_has_required_fields
test_2_generated_session_has_nominal_evidence
test_3_rule_fallback_returns_certify_for_nominal_evidence
test_4_corpus_runner_returns_report
test_5_corpus_runner_all_sessions_pass_fallback
test_6_synthetic_sessions_store_round_trip
test_7_corpus_status_endpoint_returns_status
test_8_tool_54_get_corpus_status_returns_dict
"""

import asyncio
import sys
import tempfile
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
from vapi_bridge.synthetic_session_generator import SyntheticSessionGenerator
from vapi_bridge.session_adjudicator import SessionAdjudicator
from vapi_bridge.validation_corpus_runner import ValidationCorpusRunner


def _make_store() -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p86.db"))


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.operator_api_key = "testkey86"
    cfg.supervisor_enabled = True
    cfg.supervisor_stale_threshold_minutes = 15
    cfg.validation_gate_n = 100
    cfg.validation_max_divergence_rate = 1.0
    cfg.agent_dry_run_mode = True
    cfg.synthetic_corpus_enabled = True
    cfg.synthetic_corpus_size = kwargs.get("corpus_size", 5)
    return cfg


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# 1. SyntheticSessionGenerator — session structure
# ---------------------------------------------------------------------------

class TestSyntheticSessionGenerator(unittest.TestCase):

    def test_1_generate_session_has_required_fields(self):
        """generate_session() returns dict with all required keys."""
        gen = SyntheticSessionGenerator(seed=42)
        sess = gen.generate_session()
        for key in ("session_id", "device_id", "inference_code",
                    "humanity_score", "evidence", "evidence_json", "created_at"):
            self.assertIn(key, sess, f"Missing key: {key}")
        self.assertTrue(sess["session_id"].startswith("synthetic_"))
        self.assertTrue(sess["device_id"].startswith("synthetic_"))

    def test_2_generated_session_has_nominal_evidence(self):
        """Evidence has enrollment_status='eligible' and no hard_cheat_codes."""
        gen = SyntheticSessionGenerator(seed=7)
        sess = gen.generate_session()
        ev = sess["evidence"]
        self.assertEqual(ev["enrollment_status"], "eligible")
        self.assertEqual(ev["hard_cheat_codes"], [])
        self.assertEqual(ev["advisory_codes"], [])
        self.assertEqual(ev["inference_code"], 0x20)  # NOMINAL
        self.assertGreaterEqual(sess["humanity_score"], 0.60)
        self.assertLessEqual(sess["humanity_score"], 1.0)


# ---------------------------------------------------------------------------
# 2. rule_fallback on synthetic evidence
# ---------------------------------------------------------------------------

class TestRuleFallbackOnSyntheticEvidence(unittest.TestCase):

    def test_3_rule_fallback_returns_certify_for_nominal_evidence(self):
        """_rule_fallback on nominal synthetic evidence returns CERTIFY."""
        gen = SyntheticSessionGenerator(seed=1)
        corpus = gen.generate_corpus(10)
        for sess in corpus:
            verdict, confidence, _ = SessionAdjudicator._rule_fallback(sess["evidence"])
            self.assertEqual(verdict, "CERTIFY",
                             f"Expected CERTIFY, got {verdict} for session {sess['session_id']}")
            self.assertAlmostEqual(confidence, 0.8)


# ---------------------------------------------------------------------------
# 3. ValidationCorpusRunner
# ---------------------------------------------------------------------------

class TestValidationCorpusRunner(unittest.TestCase):

    def test_4_corpus_runner_returns_report(self):
        """run_corpus(n=3) returns dict with all required report keys."""
        store = _make_store()
        cfg = _make_cfg(corpus_size=3)
        runner = ValidationCorpusRunner(cfg, store)
        report = _run(runner.run_corpus(n=3))
        for key in ("generated", "passed_fallback", "failed_fallback",
                    "all_nominal", "duration_ms", "corpus_run_id", "corpus_size"):
            self.assertIn(key, report, f"Missing key: {key}")
        self.assertEqual(report["generated"], 3)
        self.assertEqual(report["corpus_size"], 3)
        self.assertIsNotNone(report["corpus_run_id"])

    def test_5_corpus_runner_all_sessions_pass_fallback(self):
        """All synthetic nominal sessions should return CERTIFY from rule_fallback."""
        store = _make_store()
        cfg = _make_cfg(corpus_size=5)
        runner = ValidationCorpusRunner(cfg, store)
        report = _run(runner.run_corpus(n=5))
        self.assertEqual(report["passed_fallback"], 5)
        self.assertEqual(report["failed_fallback"], 0)
        self.assertTrue(report["all_nominal"])


# ---------------------------------------------------------------------------
# 4. Store round-trip
# ---------------------------------------------------------------------------

class TestSyntheticSessionsStore(unittest.TestCase):

    def test_6_synthetic_sessions_store_round_trip(self):
        """insert_synthetic_session persists; get_corpus_status reflects it."""
        store = _make_store()
        # Empty store returns zeros
        status = store.get_corpus_status()
        self.assertEqual(status["total"], 0)
        self.assertEqual(status["passed"], 0)
        self.assertIn("isolation_note", status)

        # Insert 3 sessions
        for i in range(3):
            store.insert_synthetic_session(
                session_id=f"synthetic_{i:016x}",
                device_id=f"synthetic_{i:012x}",
                inference_code=0x20,
                humanity_score=0.80,
                fallback_verdict="CERTIFY",
                fallback_confidence=0.8,
                passed_fallback=1,
                corpus_run_id="testrun01",
            )
        status = store.get_corpus_status()
        self.assertEqual(status["total"], 3)
        self.assertEqual(status["passed"], 3)
        self.assertEqual(status["failed"], 0)
        self.assertEqual(status["run_count"], 1)

        # INSERT OR IGNORE — duplicate session_id is no-op
        store.insert_synthetic_session(
            session_id="synthetic_0000000000000000",
            device_id="synthetic_000000000000",
            inference_code=0x20,
            humanity_score=0.80,
            fallback_verdict="CERTIFY",
            fallback_confidence=0.8,
            passed_fallback=1,
            corpus_run_id="testrun01",
        )
        self.assertEqual(store.get_corpus_status()["total"], 3)  # still 3


# ---------------------------------------------------------------------------
# 5. REST endpoint + Tool #54
# ---------------------------------------------------------------------------

class TestCorpusEndpoints(unittest.TestCase):

    def test_7_corpus_status_endpoint_returns_status(self):
        """GET /agent/corpus-status returns status dict with required fields."""
        from fastapi.testclient import TestClient
        from vapi_bridge.operator_api import create_operator_app
        store = _make_store()
        cfg = _make_cfg()
        client = TestClient(create_operator_app(cfg, store))
        resp = client.get("/agent/corpus-status", params={"api_key": "testkey86"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("total", data)
        self.assertIn("passed", data)
        self.assertIn("failed", data)
        self.assertIn("isolation_note", data)

    def test_8_tool_54_get_corpus_status_returns_dict(self):
        """Tool #54 get_corpus_status returns dict with total, passed, isolation_note."""
        from vapi_bridge.bridge_agent import BridgeAgent
        store = _make_store()
        cfg = _make_cfg()
        agent = BridgeAgent(cfg, store)
        result = agent._execute_tool("get_corpus_status", {})
        self.assertIn("total", result)
        self.assertIn("passed", result)
        self.assertIn("isolation_note", result)
        self.assertIsInstance(result["total"], int)


if __name__ == "__main__":
    unittest.main()

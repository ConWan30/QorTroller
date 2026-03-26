"""
Phase 88 — Adjudication Campaign Tracker + Divergence Instrumentation Tests (6 tests)

test_1_campaign_status_empty_store_zero_progress
test_2_campaign_status_with_clean_sessions_counts_correctly
test_3_extract_divergence_fields_nominal_evidence_empty
test_4_extract_divergence_fields_detects_nonstandard_signals
test_5_campaign_status_endpoint_returns_required_fields
test_6_tool_55_get_campaign_status_returns_dict
"""

import json
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
from vapi_bridge.session_adjudicator_validator import _extract_divergence_fields


def _make_store() -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p88.db"))


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.operator_api_key = "testkey88"
    cfg.validation_gate_n = kwargs.get("gate_n", 100)
    cfg.validation_max_divergence_rate = kwargs.get("max_dr", 1.0)
    cfg.supervisor_enabled = False
    cfg.supervisor_stale_threshold_minutes = 15
    cfg.agent_dry_run_mode = True
    return cfg


def _insert_ruling(store: Store, ruling_id: int, device_id: str = "dev001",
                   verdict: str = "CERTIFY", divergence: int = 0,
                   divergence_reason: str = None):
    """Helper: insert a ruling_validation_log row."""
    store.insert_validation_record(
        ruling_id=ruling_id,
        device_id=device_id,
        llm_verdict=verdict,
        fallback_verdict=verdict,  # same as LLM for non-diverged
        llm_confidence=0.8,
        fallback_confidence=0.8,
        divergence=divergence,
        divergence_reason=divergence_reason,
    )


# ---------------------------------------------------------------------------
# 1. Empty store — zero progress
# ---------------------------------------------------------------------------

class TestCampaignStatusEmpty(unittest.TestCase):

    def test_1_campaign_status_empty_store_zero_progress(self):
        """Empty store: session_count=0, consecutive_clean=0, progress_pct=0.0, gate_passed=False."""
        store = _make_store()
        status = store.get_campaign_status(gate_n=100, max_divergence_rate=1.0)
        self.assertEqual(status["session_count"], 0)
        self.assertEqual(status["consecutive_clean"], 0)
        self.assertEqual(status["progress_pct"], 0.0)
        self.assertFalse(status["gate_passed"])
        self.assertIsNone(status["last_session_at"])
        self.assertIn("campaign_note", status)
        # Empty store note should mention 'No real sessions' or 'play'
        self.assertTrue(
            "No real sessions" in status["campaign_note"] or
            "campaign" in status["campaign_note"].lower(),
            f"Unexpected campaign_note: {status['campaign_note']}"
        )


# ---------------------------------------------------------------------------
# 2. Sessions with clean streak
# ---------------------------------------------------------------------------

class TestCampaignStatusWithSessions(unittest.TestCase):

    def test_2_campaign_status_with_clean_sessions_counts_correctly(self):
        """5 non-diverged CERTIFY sessions → consecutive_clean=5, progress_pct=5.0 (gate_n=100)."""
        store = _make_store()
        for i in range(1, 6):
            _insert_ruling(store, ruling_id=i, verdict="CERTIFY", divergence=0)

        status = store.get_campaign_status(gate_n=100)
        self.assertEqual(status["session_count"], 5)
        self.assertEqual(status["consecutive_clean"], 5)
        self.assertEqual(status["progress_pct"], 5.0)
        self.assertFalse(status["gate_passed"])
        self.assertIn("CERTIFY", status["verdict_breakdown"])
        self.assertEqual(status["verdict_breakdown"]["CERTIFY"], 5)
        # No divergences → empty divergence_breakdown
        self.assertEqual(status["divergence_count"], 0)
        # Estimated sessions to gate: ~95 at 0% divergence rate
        self.assertEqual(status["estimated_sessions_to_gate"], 95)
        self.assertIsNotNone(status["last_session_at"])
        # recent_sessions should have 5 rows (all of them)
        self.assertEqual(len(status["recent_sessions"]), 5)


# ---------------------------------------------------------------------------
# 3. _extract_divergence_fields — nominal evidence
# ---------------------------------------------------------------------------

class TestExtractDivergenceFieldsNominal(unittest.TestCase):

    def test_3_extract_divergence_fields_nominal_evidence_empty(self):
        """Fully nominal evidence (eligible enrollment, no cheats) → '{}'."""
        evidence = {
            "enrollment_status": "eligible",
            "hard_cheat_codes": [],
            "advisory_codes": [],
            "inference_code": 0x20,
            "humanity_score": 0.82,
        }
        result = _extract_divergence_fields(evidence)
        self.assertEqual(result, "{}")

        # Parsed JSON must also be empty dict
        parsed = json.loads(result)
        self.assertEqual(parsed, {})


# ---------------------------------------------------------------------------
# 4. _extract_divergence_fields — non-nominal evidence
# ---------------------------------------------------------------------------

class TestExtractDivergenceFieldsNonstandard(unittest.TestCase):

    def test_4_extract_divergence_fields_detects_nonstandard_signals(self):
        """Evidence with hard_cheat_codes + HIGH class_j risk → fields captured."""
        evidence = {
            "enrollment_status": "eligible",
            "hard_cheat_codes": ["0x28"],
            "advisory_codes": ["0x31"],
            "class_j_ml_bot_risk": "HIGH",
            "ml_bot_candidate": True,
            "ceremony_integrity_failed": False,
        }
        result = _extract_divergence_fields(evidence)
        parsed = json.loads(result)

        self.assertIn("hard_cheat_codes", parsed,
                      "hard_cheat_codes should be captured")
        self.assertIn("advisory_codes", parsed,
                      "advisory_codes should be captured")
        self.assertIn("class_j_ml_bot_risk", parsed,
                      "class_j_ml_bot_risk HIGH should be captured")
        self.assertEqual(parsed["class_j_ml_bot_risk"], "HIGH")
        self.assertTrue(parsed.get("ml_bot_candidate"),
                        "ml_bot_candidate should be captured")

        # LOW risk should NOT be captured
        evidence_low = {"class_j_ml_bot_risk": "LOW", "enrollment_status": "eligible"}
        result_low = _extract_divergence_fields(evidence_low)
        parsed_low = json.loads(result_low)
        self.assertNotIn("class_j_ml_bot_risk", parsed_low,
                         "LOW class_j_ml_bot_risk should not appear in divergence fields")


# ---------------------------------------------------------------------------
# 5. GET /agent/campaign-status endpoint
# ---------------------------------------------------------------------------

class TestCampaignStatusEndpoint(unittest.TestCase):

    def test_5_campaign_status_endpoint_returns_required_fields(self):
        """GET /agent/campaign-status returns all required CampaignStatus fields."""
        from fastapi.testclient import TestClient
        from vapi_bridge.operator_api import create_operator_app
        store = _make_store()
        cfg = _make_cfg()
        # Insert 3 clean sessions
        for i in range(1, 4):
            _insert_ruling(store, ruling_id=i, verdict="CERTIFY", divergence=0)

        client = TestClient(create_operator_app(cfg, store))
        resp = client.get("/agent/campaign-status", params={"api_key": "testkey88"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        for field in ("consecutive_clean", "gate_n", "progress_pct",
                      "session_count", "divergence_count", "divergence_rate",
                      "gate_passed", "estimated_sessions_to_gate",
                      "verdict_breakdown", "divergence_breakdown",
                      "recent_sessions", "campaign_note"):
            self.assertIn(field, data, f"Missing required field: {field}")

        self.assertEqual(data["session_count"], 3)
        self.assertEqual(data["consecutive_clean"], 3)
        self.assertFalse(data["gate_passed"])


# ---------------------------------------------------------------------------
# 6. Tool #55 get_campaign_status
# ---------------------------------------------------------------------------

class TestTool55GetCampaignStatus(unittest.TestCase):

    def test_6_tool_55_get_campaign_status_returns_dict(self):
        """Tool #55 get_campaign_status returns dict with consecutive_clean and campaign_note."""
        from vapi_bridge.bridge_agent import BridgeAgent
        store = _make_store()
        cfg = _make_cfg()
        agent = BridgeAgent(cfg, store)
        result = agent._execute_tool("get_campaign_status", {})
        self.assertIn("consecutive_clean", result)
        self.assertIn("gate_passed", result)
        self.assertIn("campaign_note", result)
        self.assertIsInstance(result["consecutive_clean"], int)
        self.assertIsInstance(result["gate_passed"], bool)


if __name__ == "__main__":
    unittest.main()

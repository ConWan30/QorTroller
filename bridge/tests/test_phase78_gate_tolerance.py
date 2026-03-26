"""
Phase 78 — Validation Gate Rate-Tolerance Tests (4 tests)

Tests the max_divergence_rate gate criterion added in Phase 78:

  test_1: get_validation_summary includes divergence_rate and window_size fields
  test_2: gate_passed=False when divergence_rate exceeds max_divergence_rate
  test_3: gate_passed=True when consecutive_clean >= gate_n AND rate <= max_divergence_rate
  test_4: get_validation_gate_status recommended_action mentions rate when rate exceeded

NOTE: Both criteria evaluated over trailing gate_n window — pre-gate divergences
do not permanently block the gate (W1 mitigation documented in store.py and config.py).
"""

import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local",
             "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

_sdk_stub = types.ModuleType("sdk")
_sdk_vapi_stub = types.ModuleType("sdk.vapi_sdk")
sys.modules.setdefault("sdk", _sdk_stub)
sys.modules.setdefault("sdk.vapi_sdk", _sdk_vapi_stub)

from vapi_bridge.store import Store


def _make_store():
    tmp = tempfile.mkdtemp()
    db = os.path.join(tmp, "test_phase78.db")
    st = Store(db)
    st.upsert_device("0xdevice01", "pubkey_hex_01")
    return st


def _insert_ruling(store, verdict="FLAG", confidence=0.05):
    return store.insert_agent_ruling(
        device_id="0xdevice01",
        verdict=verdict,
        confidence=confidence,
        reasoning="test",
        evidence_json="{}",
        commitment_hash="0x" + "ab" * 32,
    )


def _insert_val(store, ruling_id, divergence=0):
    store.insert_validation_record(
        ruling_id=ruling_id,
        device_id="0xdevice01",
        llm_verdict="FLAG",
        fallback_verdict="FLAG",
        llm_confidence=0.05,
        fallback_confidence=0.05,
        divergence=divergence,
    )


class TestGateTolerance(unittest.TestCase):

    def test_1_validation_summary_includes_rate_fields(self):
        """test_1: get_validation_summary includes divergence_rate, window_size, divergence_rate_ok."""
        store = _make_store()
        rid = _insert_ruling(store)
        _insert_val(store, rid, divergence=0)

        summary = store.get_validation_summary(gate_n=10, max_divergence_rate=0.1)
        self.assertIn("divergence_rate", summary)
        self.assertIn("divergence_rate_ok", summary)
        self.assertIn("max_divergence_rate", summary)
        self.assertIn("window_size", summary)
        self.assertEqual(summary["window_size"], 1)
        self.assertEqual(summary["divergence_rate"], 0.0)
        self.assertTrue(summary["divergence_rate_ok"])

    def test_2_gate_fails_when_divergence_rate_exceeds_max(self):
        """test_2: With 2 divergences in 10 rulings (rate=0.2) and max_rate=0.1, gate_passed=False."""
        store = _make_store()
        # Insert 10 rulings: 2 divergent, 8 clean
        for i in range(10):
            rid = _insert_ruling(store)
            _insert_val(store, rid, divergence=(1 if i < 2 else 0))

        summary = store.get_validation_summary(gate_n=10, max_divergence_rate=0.1)
        self.assertAlmostEqual(summary["divergence_rate"], 0.2)
        self.assertFalse(summary["divergence_rate_ok"])
        self.assertFalse(summary["gate_passed"])

    def test_3_gate_passes_when_clean_count_and_rate_both_satisfied(self):
        """test_3: 10 clean rulings, rate=0.0, max_rate=0.05 → gate_passed=True."""
        store = _make_store()
        for _ in range(10):
            rid = _insert_ruling(store)
            _insert_val(store, rid, divergence=0)

        summary = store.get_validation_summary(gate_n=10, max_divergence_rate=0.05)
        self.assertEqual(summary["consecutive_clean"], 10)
        self.assertEqual(summary["divergence_rate"], 0.0)
        self.assertTrue(summary["divergence_rate_ok"])
        self.assertTrue(summary["gate_passed"])

    def test_4_recommended_action_mentions_rate_when_exceeded(self):
        """test_4: When divergence_rate > max, recommended_action references the rate."""
        store = _make_store()
        # 3 divergent + 2 clean → rate = 0.6, exceeds 0.1 max
        for i in range(5):
            rid = _insert_ruling(store)
            _insert_val(store, rid, divergence=(1 if i < 3 else 0))

        status = store.get_validation_gate_status(gate_n=5, max_divergence_rate=0.1)
        # recommended_action should mention the rate issue
        self.assertIn("recommended_action", status)
        action = status["recommended_action"]
        # Should reference divergence rate or rate-related message
        self.assertTrue(
            "rate" in action.lower() or "divergence" in action.lower(),
            f"Expected rate-related action, got: {action}",
        )


if __name__ == "__main__":
    unittest.main()

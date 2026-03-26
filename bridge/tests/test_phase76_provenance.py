"""
Phase 76 — RulingProvenanceAnchorAgent Tests (6 tests)

Tests cryptographic provenance anchor computation and store primitives:

  test_1: compute_provenance_hash produces expected SHA-256 from known inputs
  test_2: identical inputs → identical hash (deterministic / reproducible)
  test_3: changed ceremony data → different provenance hash
  test_4: insert_provenance_anchor stores correctly and is idempotent
  test_5: get_provenance_anchor retrieves anchor by ruling_id
  test_6: Tool #47 get_ruling_provenance returns anchor data
"""

import hashlib
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

# Stub heavy optional dependencies
for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local",
             "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

# Stub SDK
_sdk_stub = types.ModuleType("sdk")
_sdk_vapi_stub = types.ModuleType("sdk.vapi_sdk")
sys.modules.setdefault("sdk", _sdk_stub)
sys.modules.setdefault("sdk.vapi_sdk", _sdk_vapi_stub)

from vapi_bridge.store import Store
from vapi_bridge.ruling_provenance_anchor_agent import compute_provenance_hash


def _make_store():
    tmp = tempfile.mkdtemp()
    db = os.path.join(tmp, "test_phase76.db")
    st = Store(db)
    st.upsert_device("0xdevice01", "pubkey_hex_01")
    return st


def _make_ruling(store, verdict="FLAG", confidence=0.05):
    return store.insert_agent_ruling(
        device_id="0xdevice01",
        verdict=verdict,
        confidence=confidence,
        reasoning="test",
        evidence_json='{"risk_label": "stable"}',
        commitment_hash="0x" + "ab" * 32,
        ceremony_integrity='{"on_chain_match": true, "contributor_count": 3, "beacon_block_number": 41723255, "error": null}',
    )


# ──────────────────────────────────────────────────────────────────
# Tests 1–3: compute_provenance_hash determinism and sensitivity
# ──────────────────────────────────────────────────────────────────

class TestComputeProvenanceHash(unittest.TestCase):

    _COMMITMENT = "0x" + "ab" * 32
    _CEREMONY = {"beacon_block_number": 41723255, "contributor_count": 3}
    _EVIDENCE = {"risk_label": "stable"}

    def test_1_provenance_hash_matches_manual_computation(self):
        """test_1: compute_provenance_hash matches independently computed SHA-256."""
        # Replicate canonical serialization exactly
        ceremony_canonical = json.dumps(
            {"beacon_block_number": 41723255, "contributor_count": 3},
            sort_keys=True, separators=(",", ":"),
        )
        evidence_canonical = json.dumps(
            {"risk_label": "stable"},
            sort_keys=True, separators=(",", ":"),
        )
        raw = "|".join([self._COMMITMENT, ceremony_canonical, evidence_canonical])
        expected = hashlib.sha256(raw.encode()).hexdigest()

        result = compute_provenance_hash(self._COMMITMENT, self._CEREMONY, self._EVIDENCE)
        self.assertEqual(result, expected)

    def test_2_identical_inputs_produce_identical_hash(self):
        """test_2: Two calls with the same inputs produce the same hash (deterministic)."""
        h1 = compute_provenance_hash(self._COMMITMENT, self._CEREMONY, self._EVIDENCE)
        h2 = compute_provenance_hash(self._COMMITMENT, self._CEREMONY, self._EVIDENCE)
        self.assertEqual(h1, h2)

    def test_3_changed_ceremony_produces_different_hash(self):
        """test_3: Changing beacon_block_number changes the provenance hash."""
        h1 = compute_provenance_hash(self._COMMITMENT, self._CEREMONY, self._EVIDENCE)
        different_ceremony = {"beacon_block_number": 99999999, "contributor_count": 3}
        h2 = compute_provenance_hash(self._COMMITMENT, different_ceremony, self._EVIDENCE)
        self.assertNotEqual(h1, h2)


# ──────────────────────────────────────────────────────────────────
# Tests 4–5: Store primitives
# ──────────────────────────────────────────────────────────────────

class TestProvenanceStore(unittest.TestCase):

    def test_4_insert_provenance_anchor_is_idempotent(self):
        """test_4: Inserting the same ruling_id twice does not raise (INSERT OR IGNORE)."""
        store = _make_store()
        ruling_id = _make_ruling(store)

        anchor_id_1 = store.insert_provenance_anchor(
            ruling_id=ruling_id,
            device_id="0xdevice01",
            provenance_hash="a" * 64,
            ceremony_hash="b" * 64,
            evidence_hash="c" * 64,
        )
        # Second insert on same ruling_id should not raise
        anchor_id_2 = store.insert_provenance_anchor(
            ruling_id=ruling_id,
            device_id="0xdevice01",
            provenance_hash="a" * 64,
            ceremony_hash="b" * 64,
            evidence_hash="c" * 64,
        )
        # First insert succeeds; second is ignored (returns 0 or same id)
        self.assertGreaterEqual(anchor_id_1, 1)
        # No exception raised — idempotency holds

    def test_5_get_provenance_anchor_retrieves_by_ruling_id(self):
        """test_5: get_provenance_anchor returns the stored anchor dict."""
        store = _make_store()
        ruling_id = _make_ruling(store)

        prov_hash = "d" * 64
        cer_hash = "e" * 64
        ev_hash = "f" * 64
        store.insert_provenance_anchor(
            ruling_id=ruling_id,
            device_id="0xdevice01",
            provenance_hash=prov_hash,
            ceremony_hash=cer_hash,
            evidence_hash=ev_hash,
        )
        anchor = store.get_provenance_anchor(ruling_id)
        self.assertIsNotNone(anchor)
        self.assertEqual(anchor["provenance_hash"], prov_hash)
        self.assertEqual(anchor["ceremony_hash"], cer_hash)
        self.assertEqual(anchor["evidence_hash"], ev_hash)
        self.assertEqual(anchor["ruling_id"], ruling_id)

        # Unknown ruling_id returns None
        self.assertIsNone(store.get_provenance_anchor(99999))


# ──────────────────────────────────────────────────────────────────
# Test 6: BridgeAgent Tool #47
# ──────────────────────────────────────────────────────────────────

class TestBridgeAgentTool47(unittest.TestCase):

    def test_6_tool_47_get_ruling_provenance_returns_anchor(self):
        """test_6: Tool #47 returns provenance anchor dict; unknown ruling_id returns error."""
        from vapi_bridge.bridge_agent import BridgeAgent
        store = _make_store()
        ruling_id = _make_ruling(store)

        # Insert anchor
        store.insert_provenance_anchor(
            ruling_id=ruling_id,
            device_id="0xdevice01",
            provenance_hash="aa" * 32,
            ceremony_hash="bb" * 32,
            evidence_hash="cc" * 32,
        )

        cfg = MagicMock()
        cfg.operator_api_key = "test-key"
        cfg.validation_gate_n = 100
        agent = BridgeAgent(cfg, store)

        # Known ruling_id → returns anchor
        result = agent._execute_tool("get_ruling_provenance", {"ruling_id": ruling_id})
        self.assertIn("provenance_hash", result)
        self.assertEqual(result["provenance_hash"], "aa" * 32)

        # Unknown ruling_id → returns error dict
        error_result = agent._execute_tool("get_ruling_provenance", {"ruling_id": 99999})
        self.assertIn("error", error_result)
        self.assertEqual(error_result["ruling_id"], 99999)


if __name__ == "__main__":
    unittest.main()

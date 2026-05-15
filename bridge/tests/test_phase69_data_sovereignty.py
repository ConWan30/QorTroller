"""
Phase 69 — Data Sovereignty Layer + DePIN Tokenomics Tests (30 tests)

TestDataCuratorStoreOperations (8 tests):
  test_1_list_known_devices_empty_returns_empty
  test_2_list_known_devices_returns_device_ids
  test_3_upsert_data_lineage_persists_row
  test_4_get_data_lineage_returns_classified_entries
  test_5_insert_oracle_publication_persists_row
  test_6_get_oracle_publications_filtered_by_type
  test_7_upsert_token_eligibility_persists_row
  test_8_get_token_eligibility_returns_state

TestDataCuratorAgentClassification (7 tests):
  test_9_classify_nominal_records_as_session_data
  test_10_classify_records_with_features_as_biometric
  test_11_classify_proof_records_as_proof_data
  test_12_quality_index_zero_for_empty_records
  test_13_quality_index_high_for_all_nominal
  test_14_quality_index_low_for_hard_cheat_records
  test_15_compute_eligibility_no_data_returns_defaults

TestDataCuratorEligibilityEngine (5 tests):
  test_16_passport_held_increases_multiplier
  test_17_enrollment_complete_increases_multiplier
  test_18_clean_streak_gte5_increases_multiplier
  test_19_all_multipliers_stack_correctly
  test_20_reward_score_sync_returns_breakdown

TestCuratorEndpoints (8 tests):
  test_21_data_lineage_endpoint_returns_200
  test_22_data_lineage_endpoint_wrong_key_returns_403
  test_23_token_eligibility_endpoint_returns_200
  test_24_token_eligibility_endpoint_no_data_returns_null
  test_25_oracle_state_endpoint_returns_200
  test_26_oracle_state_invalid_type_returns_400
  test_27_publish_oracle_endpoint_returns_queued
  test_28_curator_config_fields_have_defaults

TestSovereigntyDataAccessRules (2 tests):
  test_29_compute_reward_score_sdk_no_state_returns_error_field
  test_30_curator_poll_loop_disabled_when_flag_false
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
sys.path.insert(0, str(BRIDGE_DIR.parent / "sdk"))

# Stub heavy optional dependencies
for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from vapi_bridge.store import Store

_DEVICE_A = "aa" * 32
_DEVICE_B = "bb" * 32


def _make_store() -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p69.db"))


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.enrollment_min_sessions = 10
    cfg.enrollment_humanity_min = 0.60
    cfg.operator_api_key        = "testkey69"
    cfg.rate_limit_per_minute   = 100
    cfg.curator_enabled         = kwargs.get("curator_enabled", True)
    cfg.curator_oracle_publish  = kwargs.get("curator_oracle_publish", False)
    cfg.humanity_oracle_address = kwargs.get("humanity_oracle_address", "")
    cfg.ruling_oracle_address   = kwargs.get("ruling_oracle_address", "")
    cfg.passport_oracle_address = kwargs.get("passport_oracle_address", "")
    cfg.data_sovereignty_reg_address = kwargs.get("data_sovereignty_reg_address", "")
    return cfg


def _seed_device(store: Store, device_id: str = _DEVICE_A) -> None:
    """Register a device so list_known_devices() returns it."""
    store.upsert_device(device_id, "00" * 33)


# ---------------------------------------------------------------------------
# TestDataCuratorStoreOperations
# ---------------------------------------------------------------------------

class TestDataCuratorStoreOperations(unittest.TestCase):

    def test_1_list_known_devices_empty_returns_empty(self):
        st = _make_store()
        result = st.list_known_devices()
        self.assertEqual(result, [])

    def test_2_list_known_devices_returns_device_ids(self):
        st = _make_store()
        _seed_device(st, _DEVICE_A)
        _seed_device(st, _DEVICE_B)
        result = st.list_known_devices()
        self.assertIn(_DEVICE_A, result)
        self.assertIn(_DEVICE_B, result)

    def test_3_upsert_data_lineage_persists_row(self):
        st = _make_store()
        row_id = st.upsert_data_lineage(
            device_id=_DEVICE_A,
            taxonomy_class="SESSION_DATA",
            quality_index=0.85,
            curator_note="nominal session",
        )
        self.assertGreater(row_id, 0)

    def test_4_get_data_lineage_returns_classified_entries(self):
        st = _make_store()
        st.upsert_data_lineage(_DEVICE_A, "SESSION_DATA", 0.9)
        st.upsert_data_lineage(_DEVICE_A, "BIOMETRIC_DATA", 0.7)
        result = st.get_data_lineage(_DEVICE_A)
        classes = [r["taxonomy_class"] for r in result]
        self.assertIn("SESSION_DATA", classes)
        self.assertIn("BIOMETRIC_DATA", classes)

    def test_5_insert_oracle_publication_persists_row(self):
        st = _make_store()
        row_id = st.insert_oracle_publication(
            oracle_type="HUMANITY",
            device_id=_DEVICE_A,
            tx_hash="0x" + "ab" * 32,
            payload_json='{"humanity_pct": 875}',
        )
        self.assertGreater(row_id, 0)

    def test_6_get_oracle_publications_filtered_by_type(self):
        st = _make_store()
        st.insert_oracle_publication("HUMANITY", _DEVICE_A, None, "{}")
        st.insert_oracle_publication("RULING", _DEVICE_A, None, "{}")
        humanity_pubs = st.get_oracle_publications(oracle_type="HUMANITY")
        ruling_pubs   = st.get_oracle_publications(oracle_type="RULING")
        self.assertEqual(len(humanity_pubs), 1)
        self.assertEqual(len(ruling_pubs), 1)
        self.assertEqual(humanity_pubs[0]["oracle_type"], "HUMANITY")

    def test_7_upsert_token_eligibility_persists_row(self):
        st = _make_store()
        st.upsert_token_eligibility(
            device_id=_DEVICE_A,
            nominal_sessions=15,
            clean_streak=7,
            passport_held=True,
            enrollment_complete=True,
            mpc_verified=True,
            gate_passed=False,
            base_multiplier=1.0,
            total_multiplier=3.75,
            eligibility_score=56.25,
        )
        row = st.get_token_eligibility(_DEVICE_A)
        self.assertIsNotNone(row)
        self.assertEqual(row["nominal_sessions"], 15)
        self.assertEqual(row["clean_streak"], 7)
        self.assertTrue(row["passport_held"])
        self.assertAlmostEqual(row["total_multiplier"], 3.75, places=2)

    def test_8_get_token_eligibility_returns_state(self):
        st = _make_store()
        result = st.get_token_eligibility(_DEVICE_A)
        self.assertIsNone(result)  # no state yet


# ---------------------------------------------------------------------------
# TestDataCuratorAgentClassification
# ---------------------------------------------------------------------------

class TestDataCuratorAgentClassification(unittest.TestCase):

    def _make_curator(self, **cfg_kwargs):
        from vapi_bridge.data_curator_agent import DataCuratorAgent
        cfg = _make_cfg(**cfg_kwargs)
        st = _make_store()
        return DataCuratorAgent(cfg, st), st

    def _nominal_record(self, rec_hash="aa" * 32):
        return {
            "record_hash": rec_hash,
            "inference": 0x20,
            "l4_distance": 4.5,
            "mean_json": '{"f0": 0.1}',
            "pitl_proof_tx_hash": None,
            "pitl_proof_commitment": None,
            "created_at": time.time(),
        }

    def test_9_classify_nominal_records_as_session_data(self):
        from vapi_bridge.data_curator_agent import DataCuratorAgent
        curator, _ = self._make_curator()
        records = [self._nominal_record()]
        classified = curator._classify_records(_DEVICE_A, records)
        classes = [e["class"] for e in classified]
        self.assertIn("SESSION_DATA", classes)

    def test_10_classify_records_with_features_as_biometric(self):
        curator, _ = self._make_curator()
        records = [self._nominal_record()]
        classified = curator._classify_records(_DEVICE_A, records)
        classes = [e["class"] for e in classified]
        self.assertIn("BIOMETRIC_DATA", classes)

    def test_11_classify_proof_records_as_proof_data(self):
        curator, _ = self._make_curator()
        r = self._nominal_record()
        r["pitl_proof_tx_hash"] = "0x" + "cc" * 32
        classified = curator._classify_records(_DEVICE_A, [r])
        classes = [e["class"] for e in classified]
        self.assertIn("PROOF_DATA", classes)

    def test_12_quality_index_zero_for_empty_records(self):
        curator, _ = self._make_curator()
        qi = curator._compute_quality_index([])
        self.assertEqual(qi, 0.0)

    def test_13_quality_index_high_for_all_nominal(self):
        curator, _ = self._make_curator()
        records = [
            {"inference": 0x20, "l4_distance": 4.0}
            for _ in range(10)
        ]
        qi = curator._compute_quality_index(records)
        # 60% nominal (all), 30% features (all have l4_distance), 10% clean → 1.0
        self.assertAlmostEqual(qi, 1.0, places=2)

    def test_14_quality_index_low_for_hard_cheat_records(self):
        curator, _ = self._make_curator()
        records = [
            {"inference": 0x28, "l4_distance": None}  # DRIVER_INJECT
        ]
        qi = curator._compute_quality_index(records)
        # 60%×0 + 30%×0 + 10%×0 = 0.0
        self.assertEqual(qi, 0.0)

    def test_15_compute_eligibility_no_data_returns_defaults(self):
        curator, _ = self._make_curator()
        score = curator._compute_eligibility(_DEVICE_A, [])
        self.assertEqual(score.device_id, _DEVICE_A)
        self.assertEqual(score.nominal_sessions, 0)
        self.assertFalse(score.enrollment_complete)
        self.assertFalse(score.passport_held)


# ---------------------------------------------------------------------------
# TestDataCuratorEligibilityEngine
# ---------------------------------------------------------------------------

class TestDataCuratorEligibilityEngine(unittest.TestCase):

    def _make_curator(self):
        from vapi_bridge.data_curator_agent import DataCuratorAgent
        cfg = _make_cfg()
        st = _make_store()
        curator = DataCuratorAgent(cfg, st)
        return curator, st

    def _records(self):
        return [{"inference": 0x20, "l4_distance": 4.0, "pitl_proof_commitment": None}]

    def test_16_passport_held_increases_multiplier(self):
        from vapi_bridge.data_curator_agent import _MULT_PASSPORT
        curator, st = self._make_curator()
        # Simulate passport in store
        passport_row = {"on_chain": True, "passport_hash": "cc" * 32}
        st.get_tournament_passport = MagicMock(return_value=passport_row)
        st.get_enrollment = MagicMock(return_value={"nominal_sessions": 5, "status": "pending", "avg_humanity": 0.7})
        st.get_ruling_streak = MagicMock(return_value=None)
        score = curator._compute_eligibility(_DEVICE_A, self._records())
        self.assertTrue(score.passport_held)
        self.assertGreater(score.total_multiplier, 1.0)

    def test_17_enrollment_complete_increases_multiplier(self):
        curator, st = self._make_curator()
        st.get_tournament_passport = MagicMock(return_value=None)
        st.get_enrollment = MagicMock(return_value={"nominal_sessions": 15, "status": "eligible", "avg_humanity": 0.8})
        st.get_ruling_streak = MagicMock(return_value=None)
        score = curator._compute_eligibility(_DEVICE_A, self._records())
        self.assertTrue(score.enrollment_complete)
        self.assertGreater(score.total_multiplier, 1.0)

    def test_18_clean_streak_gte5_increases_multiplier(self):
        from vapi_bridge.data_curator_agent import _CLEAN_STREAK_MIN
        curator, st = self._make_curator()
        st.get_tournament_passport = MagicMock(return_value=None)
        st.get_enrollment = MagicMock(return_value={"nominal_sessions": 0, "status": "pending", "avg_humanity": 0.5})
        st.get_ruling_streak = MagicMock(return_value={"verdict": "NOMINAL", "count": 6})
        score = curator._compute_eligibility(_DEVICE_A, self._records())
        self.assertGreaterEqual(score.clean_streak, _CLEAN_STREAK_MIN)
        self.assertGreater(score.total_multiplier, 1.0)

    def test_19_all_multipliers_stack_correctly(self):
        """passport(1.5) × enrollment(2.0) × streak(2.5) × gate(3.0) = 22.5×
        gate_passed is auto-derived: enrollment_complete AND passport_held AND not suspended."""
        from vapi_bridge.data_curator_agent import DataCuratorAgent, EligibilityScore
        curator, st = self._make_curator()
        st.get_tournament_passport = MagicMock(return_value={"on_chain": True, "passport_hash": "00" * 32})
        st.get_enrollment = MagicMock(return_value={"nominal_sessions": 20, "status": "eligible", "avg_humanity": 0.9})
        st.get_ruling_streak = MagicMock(return_value={"verdict": "NOMINAL", "count": 6})
        score = curator._compute_eligibility(_DEVICE_A, self._records())
        # passport + enrollment + streak qualifies gate_passed automatically
        # 100 × 150/100 × 200/100 × 250/100 × 300/100 = 2250 → 22.50×
        self.assertTrue(score.gate_passed)
        self.assertAlmostEqual(score.total_multiplier, 22.5, places=2)

    def test_20_reward_score_sync_returns_breakdown(self):
        from vapi_bridge.data_curator_agent import DataCuratorAgent
        curator, st = self._make_curator()
        st.get_recent_records = MagicMock(return_value=self._records())
        st.get_tournament_passport = MagicMock(return_value=None)
        st.get_enrollment = MagicMock(return_value={"nominal_sessions": 10, "status": "eligible", "avg_humanity": 0.7})
        st.get_ruling_streak = MagicMock(return_value=None)
        result = curator.compute_reward_score_sync(_DEVICE_A)
        self.assertIn("multiplier_breakdown", result)
        self.assertIn("total_multiplier", result)
        self.assertEqual(result["device_id"], _DEVICE_A)


# ---------------------------------------------------------------------------
# TestCuratorEndpoints
# ---------------------------------------------------------------------------

class TestCuratorEndpoints(unittest.TestCase):

    def _make_test_app(self, **store_overrides):
        from fastapi.testclient import TestClient
        from vapi_bridge.operator_api import create_operator_app
        cfg = _make_cfg()
        st = _make_store()
        _seed_device(st, _DEVICE_A)
        app = create_operator_app(cfg, st)
        return TestClient(app), st

    def test_21_data_lineage_endpoint_returns_200(self):
        client, st = self._make_test_app()
        resp = client.get(f"/curator/data-lineage/{_DEVICE_A}?api_key=testkey69")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("lineage", data)
        self.assertEqual(data["device_id"], _DEVICE_A)

    def test_22_data_lineage_endpoint_wrong_key_returns_403(self):
        client, _ = self._make_test_app()
        resp = client.get(f"/curator/data-lineage/{_DEVICE_A}?api_key=wrong")
        self.assertEqual(resp.status_code, 403)

    def test_23_token_eligibility_endpoint_returns_200(self):
        client, st = self._make_test_app()
        st.upsert_token_eligibility(
            _DEVICE_A, 12, 5, True, True, False, False, 1.0, 3.0, 36.0
        )
        resp = client.get(f"/curator/token-eligibility/{_DEVICE_A}?api_key=testkey69")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("eligibility", data)

    def test_24_token_eligibility_endpoint_no_data_returns_null(self):
        client, _ = self._make_test_app()
        resp = client.get(f"/curator/token-eligibility/{_DEVICE_A}?api_key=testkey69")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsNone(data["eligibility"])

    def test_25_oracle_state_endpoint_returns_200(self):
        client, st = self._make_test_app()
        st.insert_oracle_publication("HUMANITY", _DEVICE_A, None, "{}")
        resp = client.get("/curator/oracle-state/HUMANITY?api_key=testkey69")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["oracle_type"], "HUMANITY")
        self.assertGreaterEqual(data["publication_count"], 1)

    def test_26_oracle_state_invalid_type_returns_400(self):
        client, _ = self._make_test_app()
        resp = client.get("/curator/oracle-state/INVALID?api_key=testkey69")
        self.assertEqual(resp.status_code, 400)

    def test_27_publish_oracle_endpoint_returns_queued(self):
        client, _ = self._make_test_app()
        resp = client.post(
            f"/curator/publish-oracle?device_id={_DEVICE_A}&oracle_type=HUMANITY&api_key=testkey69"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "queued")

    def test_28_curator_config_fields_have_defaults(self):
        import os
        os.environ.pop("CURATOR_ENABLED", None)
        os.environ.pop("CURATOR_ORACLE_PUBLISH", None)
        from vapi_bridge.config import Config
        cfg = Config(
            bridge_private_key="0x" + "aa" * 32,
            verifier_address="0x" + "bb" * 20,
            iotex_rpc_url="http://localhost:8545",
        )
        self.assertTrue(cfg.curator_enabled)
        self.assertFalse(cfg.curator_oracle_publish)
        # Env-agnostic: these fields default to "" but bridge/.env may populate
        # real deployed addresses. Assert type, not value, so CI is not
        # env-dependent.
        self.assertIsInstance(cfg.humanity_oracle_address, str)
        self.assertIsInstance(cfg.ruling_oracle_address, str)
        self.assertIsInstance(cfg.passport_oracle_address, str)
        self.assertIsInstance(cfg.data_sovereignty_reg_address, str)


# ---------------------------------------------------------------------------
# TestSovereigntyDataAccessRules
# ---------------------------------------------------------------------------

class TestSovereigntyDataAccessRules(unittest.TestCase):

    def test_29_compute_reward_score_sdk_no_state_returns_error_field(self):
        """SDK: compute_reward_score on device with no eligibility state returns error."""
        from vapi_data_curator import VAPIDataCurator
        curator = VAPIDataCurator(base_url="http://localhost:0", api_key="key")
        # No server running — _get will fail and return error dict
        result = curator.compute_reward_score(_DEVICE_A)
        self.assertIn("error", result)

    def test_30_curator_poll_loop_disabled_when_flag_false(self):
        """DataCuratorAgent.run_poll_loop exits immediately when curator_enabled=False."""
        from vapi_bridge.data_curator_agent import DataCuratorAgent
        cfg = _make_cfg(curator_enabled=False)
        st = _make_store()
        curator = DataCuratorAgent(cfg, st)
        # Should return without scheduling any sleep — no CancelledError
        asyncio.run(curator.run_poll_loop())
        # If we get here without hanging, the flag guard works correctly
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()

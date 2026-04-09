"""Phase 164 — ConsentSnapshotAnchor tests (WIF-023).

8 tests → Bridge 1926 → 1934.

WIF-023: On-chain SHA-256 hash is immutable; consent_ledger is mutable.
Post-commit revocations create N_consented divergence between chain attestation
and live API state. ConsentSnapshotAnchor records consent state at every ratio
commit so that delta = n_consented_at_commit - n_consented_live is auditable.
"""

import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from bridge.vapi_bridge.store import Store


def _make_store() -> Store:
    d = tempfile.mkdtemp()
    return Store(os.path.join(d, "test164.db"), consent_ledger_enabled=True)


class TestPhase164ConsentSnapshot(unittest.TestCase):

    def test_1_table_created_and_delta_empty(self):
        """consent_snapshot_log table exists; get_consent_snapshot_delta returns found=False."""
        s = _make_store()
        result = s.get_consent_snapshot_delta()
        self.assertFalse(result["found"])
        self.assertIsNone(result["commit_hash"])
        self.assertEqual(result["delta"], 0)
        self.assertEqual(result["n_consented_at_commit"], 0)
        self.assertEqual(result["n_consented_live"], 0)
        self.assertIsNone(result["snapshot_ts"])

    def test_2_insert_snapshot_roundtrip(self):
        """insert_consent_snapshot stores a row; get_consent_snapshot_delta returns it."""
        s = _make_store()
        commit_hash = "a" * 64
        s.insert_consent_snapshot(
            commit_hash=commit_hash,
            n_consented_at_commit=3,
            revoked_count_at_commit=0,
            erasure_count_at_commit=0,
        )
        result = s.get_consent_snapshot_delta()
        self.assertTrue(result["found"])
        self.assertEqual(result["commit_hash"], commit_hash)
        self.assertEqual(result["n_consented_at_commit"], 3)
        self.assertIsNotNone(result["snapshot_ts"])

    def test_3_delta_zero_when_no_live_consents(self):
        """delta = n_consented_at_commit - n_consented_live; with empty consent_ledger live=0."""
        s = _make_store()
        s.insert_consent_snapshot(
            commit_hash="b" * 64,
            n_consented_at_commit=3,
            revoked_count_at_commit=0,
            erasure_count_at_commit=0,
        )
        result = s.get_consent_snapshot_delta()
        # No live consent records → n_consented_live=0, delta=3
        self.assertEqual(result["n_consented_live"], 0)
        self.assertEqual(result["delta"], 3)

    def test_4_delta_zero_when_consent_unchanged(self):
        """delta=0 when live active consent count equals n_consented_at_commit."""
        s = _make_store()
        # Insert 2 active consent records
        s.insert_consent_record(device_id="dev_A", consent_given=True)
        s.insert_consent_record(device_id="dev_B", consent_given=True)
        s.insert_consent_snapshot(
            commit_hash="c" * 64,
            n_consented_at_commit=2,
            revoked_count_at_commit=0,
            erasure_count_at_commit=0,
        )
        result = s.get_consent_snapshot_delta()
        self.assertEqual(result["n_consented_live"], 2)
        self.assertEqual(result["delta"], 0)
        self.assertEqual(result["revoked_since_commit"], 0)

    def test_5_delta_positive_after_revocation(self):
        """delta > 0 after a consent revocation (chain overstates coverage)."""
        s = _make_store()
        s.insert_consent_record(device_id="dev_X", consent_given=True)
        s.insert_consent_record(device_id="dev_Y", consent_given=True)
        # Snapshot at commit time: both consented
        s.insert_consent_snapshot(
            commit_hash="d" * 64,
            n_consented_at_commit=2,
            revoked_count_at_commit=0,
            erasure_count_at_commit=0,
        )
        # Post-commit: dev_X revokes
        s.revoke_consent(device_id="dev_X")
        result = s.get_consent_snapshot_delta()
        self.assertEqual(result["n_consented_at_commit"], 2)
        self.assertEqual(result["n_consented_live"], 1)
        self.assertEqual(result["delta"], 1)
        self.assertEqual(result["revoked_since_commit"], 1)

    def test_6_latest_snapshot_returned(self):
        """get_consent_snapshot_delta returns the MOST RECENT snapshot by id DESC."""
        s = _make_store()
        s.insert_consent_snapshot("e" * 64, n_consented_at_commit=1,
                                  revoked_count_at_commit=0, erasure_count_at_commit=0)
        s.insert_consent_snapshot("f" * 64, n_consented_at_commit=5,
                                  revoked_count_at_commit=0, erasure_count_at_commit=0)
        result = s.get_consent_snapshot_delta()
        # Latest insert wins
        self.assertEqual(result["commit_hash"], "f" * 64)
        self.assertEqual(result["n_consented_at_commit"], 5)

    def test_7_endpoint_returns_9_keys(self):
        """GET /agent/consent-snapshot-delta returns 9 required keys."""
        from unittest.mock import MagicMock, patch
        from fastapi.testclient import TestClient
        from bridge.vapi_bridge.operator_api import create_operator_app

        _s = _make_store()
        _cfg = MagicMock()
        _cfg.operator_api_key = "testkey164"
        _cfg.rate_limit_enabled = False
        _cfg.consent_ledger_enabled = True
        app = create_operator_app(_cfg, _s, None, None)
        client = TestClient(app)
        resp = client.get("/agent/consent-snapshot-delta?api_key=testkey164")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        for key in ("consent_ledger_enabled", "found", "commit_hash",
                    "n_consented_at_commit", "n_consented_live",
                    "delta", "revoked_since_commit", "snapshot_ts", "timestamp"):
            self.assertIn(key, data, f"Missing key: {key}")

    def test_8_schema_version_164(self):
        """schema_versions table contains phase 164 consent_snapshot entry."""
        s = _make_store()
        version = s.get_schema_version()
        self.assertGreaterEqual(version, 164)


if __name__ == "__main__":
    unittest.main()

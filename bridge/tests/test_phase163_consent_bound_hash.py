"""Phase 163 — Consent-Bound Separation Ratio Commitment (WIF-022 closure) tests.

WIF-022 (W2, CLOSED): commit_separation_ratio() now binds N_consented into the SHA-256
  hash preimage: SHA-256(ratio_str + N + N_consented + players_sorted + ts_ns).
  This makes the on-chain proof cryptographically assert consent-filtered corpus.

Tests:
  test_1  n_consented column created (ALTER TABLE idempotent migration)
  test_2  insert_separation_ratio_registry_log roundtrip with n_consented
  test_3  INSERT OR IGNORE dedup preserves first row's n_consented
  test_4  Legacy rows without n_consented read DEFAULT 0
  test_5  schema_versions table has row for phase=163
  test_6  commit hash formula includes n_consented — different n_consented → different hash
  test_7  POST /agent/commit-separation-ratio returns 9 required keys including n_consented
  test_8  Tool #120 commit_separation_ratio returns commit_hash + n_consented + dry_run=True

Bridge count: 1918 -> 1926 (+8)
"""
import hashlib
import tempfile
import time
import unittest
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vapi_bridge.store import Store
from vapi_bridge.operator_api import create_operator_app

try:
    from starlette.testclient import TestClient
except ImportError:
    from fastapi.testclient import TestClient


def _make_store(consent_ledger_enabled: bool = True) -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p163.db"), consent_ledger_enabled=consent_ledger_enabled)


def _make_cfg():
    cfg = MagicMock()
    cfg.operator_api_key              = "testkey163"
    cfg.rate_limit_per_minute         = 10000
    cfg.agent_dry_run_mode            = True
    cfg.validation_gate_n             = 100
    cfg.validation_max_divergence_rate = 1.0
    cfg.enforcement_cert_ttl_s        = 86400
    cfg.epistemic_consensus_enabled   = False
    cfg.ioswarm_adjudication_enabled  = False
    cfg.ioswarm_vhp_mint_enabled      = False
    cfg.ioswarm_enabled               = False
    cfg.poad_registry_enabled         = False
    cfg.biometric_privacy_enabled     = True
    cfg.bp001_half_life_days          = 90.0
    cfg.consent_ledger_enabled        = True
    cfg.separation_ratio_on_chain_enabled = False
    cfg.separation_ratio_registry_address = ""
    cfg.agent_model                   = "claude-sonnet-4-6"
    return cfg


class TestConsentBoundHash(unittest.TestCase):

    def test_1_n_consented_column_created(self):
        """ALTER TABLE migration: n_consented column exists after Store.__init__."""
        import sqlite3
        store = _make_store()
        with store._conn() as con:
            cols = [r[1] for r in con.execute(
                "PRAGMA table_info(separation_ratio_registry_log)"
            ).fetchall()]
        self.assertIn("n_consented", cols)

    def test_2_insert_roundtrip_with_n_consented(self):
        """insert_separation_ratio_registry_log roundtrip preserves n_consented=5."""
        store = _make_store()
        fake_hash = hashlib.sha256(b"test163_insert").hexdigest()
        store.insert_separation_ratio_registry_log(
            commit_hash=fake_hash,
            ratio_millis=1261,
            n_sessions=11,
            n_players=3,
            n_consented=5,
        )
        row = store.get_separation_ratio_registry_status()
        self.assertIsNotNone(row)
        self.assertEqual(row["n_consented"], 5)
        self.assertEqual(row["ratio_millis"], 1261)

    def test_3_dedup_preserves_first_n_consented(self):
        """INSERT OR IGNORE: second insert with same hash leaves first n_consented intact."""
        store = _make_store()
        fake_hash = hashlib.sha256(b"test163_dedup").hexdigest()
        store.insert_separation_ratio_registry_log(
            commit_hash=fake_hash,
            ratio_millis=1261,
            n_sessions=11,
            n_players=3,
            n_consented=7,
        )
        # Second insert with same hash and different n_consented — should be ignored
        store.insert_separation_ratio_registry_log(
            commit_hash=fake_hash,
            ratio_millis=1261,
            n_sessions=11,
            n_players=3,
            n_consented=99,
        )
        row = store.get_separation_ratio_registry_status()
        self.assertEqual(row["n_consented"], 7)  # first value preserved

    def test_4_legacy_rows_default_to_zero(self):
        """Rows inserted without n_consented (via direct SQL) read DEFAULT 0."""
        import sqlite3
        store = _make_store()
        fake_hash = hashlib.sha256(b"test163_legacy").hexdigest()
        # Insert directly without n_consented column to simulate pre-163 row
        with store._conn() as con:
            con.execute(
                "INSERT OR IGNORE INTO separation_ratio_registry_log"
                " (commit_hash, ratio_millis, n_sessions, n_players, committed, created_at)"
                " VALUES (?,?,?,?,?,?)",
                (fake_hash, 1261, 11, 3, 0, time.time()),
            )
        row = store.get_separation_ratio_registry_status()
        self.assertEqual(row["n_consented"], 0)

    def test_5_schema_version_163_recorded(self):
        """schema_versions table contains phase=163 after Store init."""
        store = _make_store()
        with store._conn() as con:
            row = con.execute(
                "SELECT migration_name FROM schema_versions WHERE phase=163"
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertIn("consent_bound_separation_hash", row[0])

    def test_6_commit_hash_formula_includes_n_consented(self):
        """Hash invariant: same ratio/N/players/ts_ns but different n_consented → different hash."""
        store = _make_store()
        # Register two consented devices so n_consented=2
        store.insert_consent_record(device_id="dev163_a", consent_given=True)
        store.insert_consent_record(device_id="dev163_b", consent_given=True)
        ts_ns = time.time_ns()
        hash1, n_cons1 = store.compute_separation_ratio_commit_hash(
            ratio=1.261, n_sessions=11, players_sorted="P1,P2,P3", ts_ns=ts_ns,
        )
        # Manually compute what a hash with n_consented=0 would be (different)
        preimage_zero = f"1.261000:11:0:P1,P2,P3:{ts_ns}".encode()
        hash_zero = hashlib.sha256(preimage_zero).hexdigest()
        # n_consented=2 (2 registered devices), so hash1 should differ from hash_zero
        self.assertEqual(n_cons1, 2)
        self.assertNotEqual(hash1, hash_zero)
        # Verify formula manually
        preimage_expected = f"1.261000:11:{n_cons1}:P1,P2,P3:{ts_ns}".encode()
        self.assertEqual(hash1, hashlib.sha256(preimage_expected).hexdigest())

    def test_7_endpoint_returns_9_keys(self):
        """POST /agent/commit-separation-ratio returns 200 with 9 required keys including n_consented."""
        store = _make_store()
        cfg   = _make_cfg()
        app   = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post(
            "/agent/commit-separation-ratio",
            params={
                "api_key": "testkey163",
                "ratio": 1.261,
                "n_sessions": 11,
                "n_players": 3,
                "players_sorted": "P1,P2,P3",
            },
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        for key in (
            "separation_ratio_on_chain_enabled",
            "commit_hash",
            "n_consented",
            "n_sessions",
            "n_players",
            "committed",
            "on_chain_tx",
            "dry_run",
            "timestamp",
        ):
            self.assertIn(key, body, f"Missing key: {key}")
        self.assertFalse(body["separation_ratio_on_chain_enabled"])
        self.assertTrue(body["dry_run"])
        self.assertFalse(body["committed"])
        self.assertEqual(len(body["commit_hash"]), 64)  # valid SHA-256 hex

    def test_8_tool_120_returns_commit_hash_and_n_consented(self):
        """Tool #120 commit_separation_ratio returns dict with commit_hash, n_consented, dry_run=True."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from vapi_bridge.bridge_agent import BridgeAgent
        store = _make_store()
        cfg   = _make_cfg()
        agent = BridgeAgent(cfg=cfg, store=store)

        result = agent._execute_tool("commit_separation_ratio", {
            "ratio": 1.261,
            "n_sessions": 11,
            "n_players": 3,
            "players_sorted": "P1,P2,P3",
        })
        self.assertIsInstance(result, dict)
        self.assertIn("commit_hash", result)
        self.assertIn("n_consented", result)
        self.assertIn("dry_run", result)
        self.assertTrue(result["dry_run"])
        self.assertFalse(result["committed"])
        self.assertEqual(len(result["commit_hash"]), 64)


if __name__ == "__main__":
    unittest.main()

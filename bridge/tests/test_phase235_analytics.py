"""Phase 235-ANALYTICS — Grind Pipeline Analytics tests.

T235-ANL-1: Empty DB → success_rate=0.0, total_validated=0, projected_gic100_date="unknown"
T235-ANL-2: 10 stamped rows over 2 days → success_rate=1.0, sessions_per_day≈5.0
T235-ANL-3: 6 stamped + 4 unstamped → success_rate=0.6, blocking_reason_counts populated
T235-ANL-4: projected_gic100_date calculated correctly
T235-ANL-5: sessions_per_day=0 when all rows same second → projected_gic100_date="unknown"
T235-ANL-6: Different grind_session_id rows are filtered out
T235-ANL-7: GET /grind/analytics returns 200 with all 8 keys
T235-ANL-8: GET /grind/analytics requires auth (401 without x-api-key)
"""

import sys
import os
import time
import tempfile
import types
import datetime
import unittest
from pathlib import Path
from unittest.mock import MagicMock

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)
_web3_mod = sys.modules["web3"]
for _attr in ["AsyncWeb3", "AsyncHTTPProvider", "Web3"]:
    if not hasattr(_web3_mod, _attr):
        setattr(_web3_mod, _attr, MagicMock())
_web3_exc = sys.modules["web3.exceptions"]
for _attr in ["ContractLogicError", "TransactionNotFound"]:
    if not hasattr(_web3_exc, _attr):
        setattr(_web3_exc, _attr, Exception)
_eth_acc = sys.modules["eth_account"]
if not hasattr(_eth_acc, "Account"):
    setattr(_eth_acc, "Account", MagicMock())


def _make_store(tmp_dir=None):
    from vapi_bridge.store import Store
    td = tmp_dir or tempfile.mkdtemp()
    return Store(str(Path(td) / "test_analytics.db"))


def _make_cfg(**kwargs):
    from vapi_bridge.config import Config
    defaults = dict(
        grind_mode=True,
        grind_session_id="grind_analytics_test",
        grind_target=100,
        operator_api_key="anl-test-key",
    )
    defaults.update(kwargs)
    return Config(**defaults)


def _make_client(store, cfg):
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app
    app = create_operator_app(cfg, store)
    return TestClient(app, raise_server_exceptions=False)


def _insert_validation(store, session_id, stamped=False, pcc_state="NOMINAL",
                       pcc_host="EXCLUSIVE_USB", gameplay_ctx="ACTIVE_GAMEPLAY",
                       divergence=0, created_at=None):
    """Insert a ruling_validation_log row directly."""
    fake_ruling_id = _insert_validation._counter
    _insert_validation._counter += 1

    gic_hash = ("ab" * 32) if stamped else None
    gic_ts_ns = (time.time_ns()) if stamped else None
    ts = created_at if created_at is not None else time.time()

    with store._conn() as conn:
        row_id = conn.execute(
            "INSERT INTO ruling_validation_log "
            "(ruling_id, device_id, llm_verdict, fallback_verdict, "
            "llm_confidence, fallback_confidence, divergence, divergence_reason, "
            "pcc_state, pcc_host_state, gameplay_context, "
            "grind_chain_hash, gic_ts_ns, grind_session_id, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (fake_ruling_id, "DEV0", "FLAG", "FLAG", 0.05, 0.05,
             divergence, None, pcc_state, pcc_host, gameplay_ctx,
             gic_hash, gic_ts_ns, session_id if stamped else None, ts),
        ).lastrowid
    return row_id


_insert_validation._counter = 5000


class TestGrindAnalyticsStore(unittest.TestCase):

    def test_1_empty_db(self):
        """T235-ANL-1: empty ruling_validation_log → zero-state."""
        store = _make_store()
        result = store.get_grind_analytics("grind_analytics_test", 100)
        self.assertEqual(result["total_validated"], 0)
        self.assertEqual(result["stamped_count"], 0)
        self.assertEqual(result["success_rate"], 0.0)
        self.assertEqual(result["projected_gic100_date"], "unknown")
        self.assertEqual(result["blocking_reason_counts"], {})

    def test_2_all_stamped_success_rate_1(self):
        """T235-ANL-2: 10 stamped rows over 2 days → success_rate=1.0, sessions_per_day≈5."""
        store = _make_store()
        base_ts = time.time() - 2 * 86400  # 2 days ago
        for i in range(10):
            _insert_validation(store, "grind_analytics_test",
                               stamped=True, created_at=base_ts + i * 3600)

        result = store.get_grind_analytics("grind_analytics_test", 100)
        self.assertEqual(result["total_validated"], 10)
        self.assertEqual(result["stamped_count"], 10)
        self.assertAlmostEqual(result["success_rate"], 1.0, places=3)
        self.assertGreater(result["sessions_per_day"], 4.0)

    def test_3_mixed_stamped_unstamped(self):
        """T235-ANL-3: 6 stamped + 4 unstamped → success_rate=0.6, reasons populated."""
        store = _make_store()
        base_ts = time.time() - 86400
        for i in range(6):
            _insert_validation(store, "grind_analytics_test",
                               stamped=True, created_at=base_ts + i * 1000)
        # Unstamped: DISCONNECTED PCC
        _insert_validation(store, None, stamped=False, pcc_state="DISCONNECTED",
                           pcc_host="UNKNOWN", created_at=base_ts + 7000)
        # Unstamped: MENU_DETECTED
        _insert_validation(store, None, stamped=False, pcc_state="NOMINAL",
                           pcc_host="EXCLUSIVE_USB", gameplay_ctx="MENU_DETECTED",
                           created_at=base_ts + 8000)
        # Unstamped: DIVERGENT
        _insert_validation(store, None, stamped=False, pcc_state="NOMINAL",
                           pcc_host="EXCLUSIVE_USB", gameplay_ctx="ACTIVE_GAMEPLAY",
                           divergence=1, created_at=base_ts + 9000)
        # Unstamped: PCC_STATE_UNKNOWN (pcc_state=None)
        _insert_validation(store, None, stamped=False, pcc_state=None,
                           pcc_host=None, created_at=base_ts + 10000)

        result = store.get_grind_analytics("grind_analytics_test", 100)
        self.assertEqual(result["total_validated"], 10)
        self.assertEqual(result["stamped_count"], 6)
        self.assertAlmostEqual(result["success_rate"], 0.6, places=3)
        reasons = result["blocking_reason_counts"]
        self.assertIn("PCC_NOT_NOMINAL:DISCONNECTED", reasons)
        self.assertIn("MENU_DETECTED", reasons)
        self.assertIn("DIVERGENT", reasons)
        self.assertIn("PCC_STATE_UNKNOWN", reasons)

    def test_4_projected_date_calculation(self):
        """T235-ANL-4: 6 stamped in 2 days → projected_gic100 ≈ today + ~31 days."""
        store = _make_store()
        base_ts = time.time() - 2 * 86400
        for i in range(6):
            _insert_validation(store, "grind_analytics_test",
                               stamped=True, created_at=base_ts + i * 10000)

        result = store.get_grind_analytics("grind_analytics_test", 100)
        # sessions_per_day ≈ 3.0; remaining ≈ 94; days_left ≈ 31
        self.assertNotEqual(result["projected_gic100_date"], "unknown")
        projected = datetime.datetime.strptime(result["projected_gic100_date"], "%Y-%m-%d")
        days_from_now = (projected - datetime.datetime.utcnow()).days
        self.assertGreater(days_from_now, 10)

    def test_5_zero_velocity_unknown_projection(self):
        """T235-ANL-5: all rows same timestamp → sessions_per_day≈0 → projected='unknown'."""
        store = _make_store()
        ts = time.time()
        for _ in range(3):
            _insert_validation(store, "grind_analytics_test",
                               stamped=True, created_at=ts)

        result = store.get_grind_analytics("grind_analytics_test", 100)
        # All at same time → days_elapsed ≈ 0 → sessions_per_day=0 → unknown
        self.assertEqual(result["projected_gic100_date"], "unknown")

    def test_6_different_session_filtered(self):
        """T235-ANL-6: rows from a different session_id are excluded from analytics."""
        store = _make_store()
        base_ts = time.time() - 86400
        # Insert under correct session
        for i in range(5):
            _insert_validation(store, "grind_analytics_test",
                               stamped=True, created_at=base_ts + i * 1000)
        # Insert under different session — should be excluded
        for i in range(10):
            _insert_validation(store, "grind_OTHER_session",
                               stamped=True, created_at=base_ts + i * 500)

        result = store.get_grind_analytics("grind_analytics_test", 100)
        self.assertEqual(result["stamped_count"], 5)


class TestGrindAnalyticsEndpoint(unittest.TestCase):

    def test_7_endpoint_returns_200_all_keys(self):
        """T235-ANL-7: GET /grind/analytics returns 200 with all 8 keys."""
        store = _make_store()
        cfg = _make_cfg()
        client = _make_client(store, cfg)

        resp = client.get("/grind/analytics", headers={"x-api-key": "anl-test-key"})
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()

        for key in ("grind_session_id", "total_validated", "stamped_count",
                    "success_rate", "blocking_reason_counts",
                    "sessions_per_day", "projected_gic100_date", "timestamp"):
            self.assertIn(key, data, f"missing key: {key}")

        self.assertIsInstance(data["success_rate"], float)
        self.assertIsInstance(data["blocking_reason_counts"], dict)

    def test_8_endpoint_requires_auth(self):
        """T235-ANL-8: GET /grind/analytics without api-key → 401 or 403."""
        store = _make_store()
        cfg = _make_cfg()
        client = _make_client(store, cfg)

        resp = client.get("/grind/analytics")
        self.assertIn(resp.status_code, (401, 403))


if __name__ == "__main__":
    unittest.main()

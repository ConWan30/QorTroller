"""Phase 235-CONTENTION — BT Contention Pattern Intelligence tests.

T235-CON-1: get_bt_contention_analytics returns zero-state on empty capture_health_log
T235-CON-2: Single DEGRADED episode (2 rows, ~20s apart) → total_episodes=1
T235-CON-3: Two separate episodes (non-NOMINAL runs separated by >10s gap each) → total_episodes=2
T235-CON-4: NOMINAL-only log → total_episodes=0, mean_recovery_s=0.0
T235-CON-5: GET /grind/pcc-intelligence returns 200 with correct keys when transport attached
T235-CON-6: GET /grind/pcc-intelligence returns hid_counter_restarts=0 when transport not attached
"""

import sys
import os
import time
import tempfile
import types
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
    return Store(str(Path(td) / "test_contention.db"))


def _make_cfg(**kwargs):
    from vapi_bridge.config import Config
    defaults = dict(
        grind_mode=True,
        grind_session_id="grind_contention_test",
        grind_target=100,
        operator_api_key="con-test-key",
    )
    defaults.update(kwargs)
    return Config(**defaults)


def _make_client(store, cfg):
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app
    app = create_operator_app(cfg, store)
    return TestClient(app, raise_server_exceptions=False)


def _insert_health_event(store, capture_state, host_state, created_at):
    """Insert a capture_health_log row directly at a specific timestamp."""
    with store._conn() as conn:
        conn.execute(
            "INSERT INTO capture_health_log "
            "(capture_state, host_state, poll_rate_hz, transition_reason, "
            "grind_mode, session_id, prev_session_id, gap_duration_ms, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (capture_state, host_state, 1000.0 if capture_state == "NOMINAL" else 117.0,
             "test", 1, "grind_test", "", 0.0, created_at),
        )


class TestBTContentionAnalytics(unittest.TestCase):

    def test_1_empty_log_returns_zero_state(self):
        """T235-CON-1: empty capture_health_log → zero-state dict."""
        store = _make_store()
        result = store.get_bt_contention_analytics()
        self.assertEqual(result["total_episodes"], 0)
        self.assertEqual(result["mean_recovery_s"], 0.0)
        self.assertEqual(result["longest_episode_s"], 0.0)
        self.assertEqual(result["last_episode_ts"], 0.0)
        self.assertEqual(result["host_state_distribution"], {})

    def test_2_single_episode_detected(self):
        """T235-CON-2: DEGRADED → NOMINAL sequence → total_episodes=1, duration≈20s."""
        store = _make_store()
        base = time.time()
        # Enter DEGRADED
        _insert_health_event(store, "DEGRADED", "UNKNOWN", base)
        # Return to NOMINAL 20s later
        _insert_health_event(store, "NOMINAL", "EXCLUSIVE_USB", base + 20.0)

        result = store.get_bt_contention_analytics()
        self.assertEqual(result["total_episodes"], 1)
        self.assertGreater(result["mean_recovery_s"], 15.0)
        self.assertAlmostEqual(result["longest_episode_s"], result["mean_recovery_s"])
        # last_episode_ts should be approximately base+20
        self.assertAlmostEqual(result["last_episode_ts"], base + 20.0, delta=1.0)

    def test_3_two_episodes_counted(self):
        """T235-CON-3: two separate non-NOMINAL runs → total_episodes=2."""
        store = _make_store()
        base = time.time()
        # Episode 1: DEGRADED then NOMINAL
        _insert_health_event(store, "DEGRADED", "UNKNOWN", base)
        _insert_health_event(store, "NOMINAL", "EXCLUSIVE_USB", base + 15.0)
        # Episode 2 starts 30s later
        _insert_health_event(store, "DISCONNECTED", "UNKNOWN", base + 45.0)
        _insert_health_event(store, "NOMINAL", "EXCLUSIVE_USB", base + 65.0)

        result = store.get_bt_contention_analytics()
        self.assertEqual(result["total_episodes"], 2)

    def test_4_nominal_only_log(self):
        """T235-CON-4: NOMINAL-only entries → total_episodes=0, mean_recovery_s=0.0."""
        store = _make_store()
        base = time.time()
        for i in range(5):
            _insert_health_event(store, "NOMINAL", "EXCLUSIVE_USB", base + i * 10)

        result = store.get_bt_contention_analytics()
        self.assertEqual(result["total_episodes"], 0)
        self.assertEqual(result["mean_recovery_s"], 0.0)
        # host_state_distribution should have EXCLUSIVE_USB
        self.assertIn("EXCLUSIVE_USB", result["host_state_distribution"])


class TestPCCIntelligenceEndpoint(unittest.TestCase):

    def test_5_endpoint_returns_correct_keys_with_transport(self):
        """T235-CON-5: GET /grind/pcc-intelligence with transport attached → 200 + all keys."""
        store = _make_store()
        cfg = _make_cfg()
        client = _make_client(store, cfg)

        # Attach a mock transport with _hid_counter_restarts=3
        from vapi_bridge.operator_api import create_operator_app
        app = create_operator_app(cfg, store)
        mock_transport = MagicMock()
        mock_transport._hid_counter_restarts = 3
        app._transport = mock_transport

        from fastapi.testclient import TestClient
        c = TestClient(app, raise_server_exceptions=False)
        resp = c.get("/grind/pcc-intelligence", headers={"x-api-key": "con-test-key"})
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()

        for key in ("total_episodes", "mean_recovery_s", "longest_episode_s",
                    "host_state_distribution", "hid_counter_restarts", "timestamp"):
            self.assertIn(key, data, f"missing key: {key}")
        self.assertEqual(data["hid_counter_restarts"], 3)

    def test_6_endpoint_failopen_no_transport(self):
        """T235-CON-6: GET /grind/pcc-intelligence without transport → hid_counter_restarts=0."""
        store = _make_store()
        cfg = _make_cfg()
        client = _make_client(store, cfg)

        resp = client.get("/grind/pcc-intelligence", headers={"x-api-key": "con-test-key"})
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertEqual(data["hid_counter_restarts"], 0)
        self.assertIn("timestamp", data)


if __name__ == "__main__":
    unittest.main()

"""WMP UC-15 — GET /player/self-analytics endpoint tests.

Read-only self-view over the gamer's own verified history. Mirrors the /player/session-status test
pattern (real Store on tmpdir + TestClient). Pins: 200 + honest zeroed shape on an empty DB; the
self-view ceiling rails present; read-key auth enforced.
"""

import sys
import tempfile
import types
import unittest
from pathlib import Path

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local"]:
    if _mod not in sys.modules:
        try:
            __import__(_mod)
        except ImportError:
            sys.modules[_mod] = types.ModuleType(_mod)

_KEY = "satestkey"
_H = {"x-api-key": _KEY}


def _make_store():
    from vapi_bridge.store import Store
    return Store(str(Path(tempfile.mkdtemp()) / "test_self_analytics.db"))


def _make_cfg():
    from vapi_bridge.config import Config
    return Config(operator_api_key=_KEY, grind_session_id="grind_test_sa")


def _client(cfg, store):
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app
    return TestClient(create_operator_app(cfg, store))


class TestPlayerSelfAnalytics(unittest.TestCase):
    def setUp(self):
        self.store = _make_store()
        self.client = _client(_make_cfg(), self.store)

    def test_empty_db_returns_honest_zeroes(self):
        r = self.client.get("/player/self-analytics", headers=_H)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["schema"], "qortroller-wmp-self-analytics-v0")
        self.assertEqual(body["clean_streaks"]["total_sessions"], 0)
        self.assertEqual(body["session_cadence"]["total_sessions"], 0)
        self.assertEqual(body["authored_kills"]["authored_total"], 0)

    def test_self_view_ceiling_rails_present(self):
        body = self.client.get("/player/self-analytics", headers=_H).json()
        self.assertTrue(body["self_view_only"])
        self.assertFalse(body["cross_player_comparison"])
        self.assertFalse(body["population_certified"])
        self.assertTrue(body["advisory"])
        self.assertEqual(body["scope"], "developer_self")

    def test_read_key_required(self):
        r = self.client.get("/player/self-analytics", headers={"x-api-key": "wrong"})
        self.assertIn(r.status_code, (401, 403))


if __name__ == "__main__":
    unittest.main()

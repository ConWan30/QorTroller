"""VSS-1 — GET /vss/eligibility fail-closed probe.

Implements docs/design/buzz-vss-stream-seat-scope-v0.md §6 (Bridge surface).

Acceptance cases (from VSS-1 mandate):
  1. capture down → eligible=false, reason clear
  2. retina oracle process down → eligible=false, reason clear
  3. both up → eligible can be true (membership enforced at Buzz layer, not here)
  4. never asserts "human proven"
  5. no chain writes, no FROZEN wire changes, no media upload
"""
import sys
import tempfile
import types
import unittest
from pathlib import Path

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

# Stub web3/eth_account if not available (same pattern as test_player_session_status)
for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local"]:
    if _mod not in sys.modules:
        try:
            __import__(_mod)
        except ImportError:
            sys.modules[_mod] = types.ModuleType(_mod)

_KEY = "psstestkey"
_H = {"x-api-key": _KEY}


def _make_store():
    from vapi_bridge.store import Store
    return Store(str(Path(tempfile.mkdtemp()) / "test_vss.db"))


def _make_cfg(**kw):
    from vapi_bridge.config import Config
    defaults = dict(
        operator_api_key=_KEY,
        grind_session_id="grind_test_vss",
    )
    defaults.update(kw)
    return Config(**defaults)


def _client(cfg, store, chain=None):
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app
    app = create_operator_app(cfg, store, chain=chain)
    return TestClient(app, raise_server_exceptions=False)


def _make_app_with_monitor(cfg, store, capture_state, poll_rate):
    """Create the operator app with a fake PCC monitor attached."""
    from vapi_bridge.operator_api import create_operator_app
    app = create_operator_app(cfg, store)
    app._pcc_monitor = _FakePCCMonitor(capture_state, poll_rate)
    return app


class _FakePCCMonitor:
    """Minimal PCC monitor stub for VSS tests."""

    def __init__(self, capture_state="DISCONNECTED", poll_rate=0.0):
        self._state = capture_state
        self._rate = poll_rate

    def get_status(self):
        return {
            "capture_state": self._state,
            "host_state": "EXCLUSIVE_USB" if self._state == "NOMINAL" else "UNKNOWN",
            "poll_rate_hz": self._rate,
            "sustained_duration_s": 0.0,
            "grind_ready": False,
            "disconnect_reason": "",
            "sample_count": 0,
        }


class _FakePolicyState:
    """Minimal retina policy state stub."""

    def __init__(self, effective=False):
        self._effective = effective

    def to_dict(self):
        return {"effective_perception": self._effective}


class TestVSSEligibility(unittest.TestCase):
    """VSS-1 acceptance tests."""

    def test_1_capture_down_eligible_false(self):
        """Acceptance 1: capture down → eligible=false, reason mentions capture."""
        cfg = _make_cfg()
        store = _make_store()
        client = _client(cfg, store)
        r = client.get("/vss/eligibility", headers=_H)
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertFalse(j["eligible"])
        self.assertFalse(j["capture_up"])
        self.assertIn("capture", j["reason_if_closed"].lower())

    def test_2_retina_oracle_down_eligible_false(self):
        """Acceptance 2: retina oracle down → eligible=false, reason mentions oracle."""
        cfg = _make_cfg()
        store = _make_store()
        app = _make_app_with_monitor(cfg, store, "NOMINAL", 1000.0)
        from fastapi.testclient import TestClient
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/vss/eligibility", headers=_H)
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertFalse(j["eligible"])
        self.assertTrue(j["capture_up"])
        self.assertFalse(j["retina_oracle_running"])
        self.assertIn("oracle", j["reason_if_closed"].lower())

    def test_3_both_up_eligible_true(self):
        """Acceptance 3: both up → eligible=true (hardware side only)."""
        cfg = _make_cfg()
        store = _make_store()
        app = _make_app_with_monitor(cfg, store, "NOMINAL", 1000.0)
        app._retina_policy_state = _FakePolicyState(effective=True)
        from fastapi.testclient import TestClient
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/vss/eligibility", headers=_H)
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertTrue(j["eligible"])
        self.assertTrue(j["capture_up"])
        self.assertTrue(j["retina_oracle_running"])
        self.assertEqual(j["reason_if_closed"], "")

    def test_4_never_asserts_human_proven(self):
        """Acceptance 4: response never claims 'human proven' or humanity cert."""
        cfg = _make_cfg()
        store = _make_store()
        app = _make_app_with_monitor(cfg, store, "NOMINAL", 1000.0)
        app._retina_policy_state = _FakePolicyState(effective=True)
        from fastapi.testclient import TestClient
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/vss/eligibility", headers=_H)
        j = r.json()
        text = str(j).lower()
        for forbidden in ("human proven", "humanity_proven", "humanity cert",
                          "tournament-grade", "verified human"):
            self.assertNotIn(forbidden, text,
                             f"response must not claim '{forbidden}'")

    def test_5_honesty_block_present(self):
        """The honesty block is present and reports poep_enabled + advisory_oracle."""
        cfg = _make_cfg(poep_enabled=False)
        store = _make_store()
        client = _client(cfg, store)
        r = client.get("/vss/eligibility", headers=_H)
        j = r.json()
        self.assertIn("honesty", j)
        self.assertIn("poep_enabled", j["honesty"])
        self.assertIn("advisory_oracle", j["honesty"])
        self.assertFalse(j["honesty"]["poep_enabled"])
        self.assertTrue(j["honesty"]["advisory_oracle"])

    def test_6_degraded_capture_counts_as_up(self):
        """DEGRADED capture state still counts as capture_up (partial, not down)."""
        cfg = _make_cfg()
        store = _make_store()
        app = _make_app_with_monitor(cfg, store, "DEGRADED", 150.0)
        app._retina_policy_state = _FakePolicyState(effective=True)
        from fastapi.testclient import TestClient
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/vss/eligibility", headers=_H)
        j = r.json()
        self.assertTrue(j["capture_up"])
        self.assertTrue(j["eligible"])

    def test_7_disconnected_capture_not_up(self):
        """DISCONNECTED capture state → capture_up=false."""
        cfg = _make_cfg()
        store = _make_store()
        app = _make_app_with_monitor(cfg, store, "DISCONNECTED", 0.0)
        app._retina_policy_state = _FakePolicyState(effective=True)
        from fastapi.testclient import TestClient
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/vss/eligibility", headers=_H)
        j = r.json()
        self.assertFalse(j["capture_up"])
        self.assertFalse(j["eligible"])

    def test_8_no_auth_key_rejected(self):
        """Missing API key → 403 (not a silent pass)."""
        cfg = _make_cfg()
        store = _make_store()
        client = _client(cfg, store)
        r = client.get("/vss/eligibility")
        self.assertEqual(r.status_code, 403)

    def test_9_response_shape(self):
        """Response has exactly the VSS scope §6 shape."""
        cfg = _make_cfg()
        store = _make_store()
        client = _client(cfg, store)
        r = client.get("/vss/eligibility", headers=_H)
        j = r.json()
        for key in ("eligible", "capture_up", "retina_oracle_running",
                     "reason_if_closed", "honesty", "timestamp"):
            self.assertIn(key, j)
        self.assertIsInstance(j["eligible"], bool)
        self.assertIsInstance(j["capture_up"], bool)
        self.assertIsInstance(j["retina_oracle_running"], bool)
        self.assertIsInstance(j["reason_if_closed"], str)

    def test_10_no_ioid_required(self):
        """Response does not include any IoID field — it's never required per VSS §2."""
        cfg = _make_cfg()
        store = _make_store()
        client = _client(cfg, store)
        r = client.get("/vss/eligibility", headers=_H)
        j = r.json()
        for forbidden in ("ioid", "io_id", "iotex", "device_id"):
            self.assertNotIn(forbidden, j,
                             f"response must not include '{forbidden}' (IoID never required)")


if __name__ == "__main__":
    unittest.main()

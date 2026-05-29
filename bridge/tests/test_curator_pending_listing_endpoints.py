"""Data Economy Arc 3 Commit 3 — autonomy-ladder approval endpoints.

The approval_required / manual autonomy levels queue listing intents into
pending_listings (Commit 1). These endpoints are the gamer-facing
(operator-proxied) surface to review and act on that queue:

   T-CPE-1  GET /curator/pending-listings returns queued intents (auth required).
   T-CPE-2  POST /curator/approve-listing/{id} marks APPROVED + never broadcasts.
   T-CPE-3  POST /curator/reject-listing/{id} marks REJECTED.
   T-CPE-4  Unknown listing id → 404 on both approve and reject.
   T-CPE-5  Wrong api_key → 403 (auth enforced on all three endpoints).

A real Store on a tmp DB exercises the pending_listings table end-to-end.
"""
import sys
import tempfile
import types
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

for _mod in ("web3", "web3.exceptions", "eth_account", "hidapi", "hid", "pydualsense"):
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)
_web3_exc = sys.modules["web3.exceptions"]
for _attr in ("ContractLogicError", "TransactionNotFound"):
    if not hasattr(_web3_exc, _attr):
        setattr(_web3_exc, _attr, type(_attr, (Exception,), {}))
_web3_mod = sys.modules["web3"]
for _attr in ("AsyncWeb3", "AsyncHTTPProvider"):
    if not hasattr(_web3_mod, _attr):
        setattr(_web3_mod, _attr, MagicMock())
_eth_acct = sys.modules["eth_account"]
if not hasattr(_eth_acct, "Account"):
    _eth_acct.Account = MagicMock()

from fastapi.testclient import TestClient

from vapi_bridge.operator_api import create_operator_app
from vapi_bridge.store import Store

_API_KEY = "test-operator-key-arc3"
_DEVICE = "ab" * 32


def _cfg():
    cfg = MagicMock()
    cfg.operator_api_key = _API_KEY
    cfg.rate_limit_per_minute = 120  # MagicMock default int()→1 would 429 us
    return cfg


def _store():
    # Windows WAL: use mkdtemp not TemporaryDirectory (per repo gotcha).
    d = tempfile.mkdtemp()
    return Store(db_path=str(Path(d) / "arc3.db"))


def _intent(session_id="s1", autonomy="approval_required"):
    return {
        "session_id": session_id,
        "device_id": _DEVICE,
        "autonomy_level": autonomy,
        "consent_policy_hash": "0xabc",
        "allowed_categories": [1, 2],
        "ts_ns": time.time_ns(),
    }


class TestCuratorPendingListingEndpoints(unittest.TestCase):
    def setUp(self):
        self.store = _store()
        self.client = TestClient(create_operator_app(_cfg(), self.store))

    # ── T-CPE-1 ─────────────────────────────────────────────────────────────
    def test_T_CPE_1_list_pending(self):
        self.store.insert_pending_listing(_intent("s1"))
        self.store.insert_pending_listing(_intent("s2"))
        r = self.client.get("/curator/pending-listings", params={"api_key": _API_KEY})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["count"], 2)
        sids = {row["session_id"] for row in body["listings"]}
        self.assertEqual(sids, {"s1", "s2"})
        # allowed_categories json-decoded back to a list.
        self.assertEqual(body["listings"][0]["allowed_categories"], [1, 2])

    # ── T-CPE-2 ─────────────────────────────────────────────────────────────
    def test_T_CPE_2_approve_marks_approved_no_broadcast(self):
        lid = self.store.insert_pending_listing(_intent("s1"))
        r = self.client.post(f"/curator/approve-listing/{lid}",
                             params={"api_key": _API_KEY})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["status"], "approved")
        self.assertFalse(body["broadcast"])
        # No longer in the default 'pending' queue.
        pending = self.store.get_pending_listings(status="pending")
        self.assertEqual(pending, [])
        approved = self.store.get_pending_listings(status="approved")
        self.assertEqual(len(approved), 1)

    # ── T-CPE-3 ─────────────────────────────────────────────────────────────
    def test_T_CPE_3_reject_marks_rejected(self):
        lid = self.store.insert_pending_listing(_intent("s1"))
        r = self.client.post(f"/curator/reject-listing/{lid}",
                             params={"api_key": _API_KEY})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "rejected")
        self.assertEqual(self.store.get_pending_listings(status="pending"), [])
        self.assertEqual(len(self.store.get_pending_listings(status="rejected")), 1)

    # ── T-CPE-4 ─────────────────────────────────────────────────────────────
    def test_T_CPE_4_unknown_id_404(self):
        ra = self.client.post("/curator/approve-listing/9999",
                             params={"api_key": _API_KEY})
        rr = self.client.post("/curator/reject-listing/9999",
                             params={"api_key": _API_KEY})
        self.assertEqual(ra.status_code, 404)
        self.assertEqual(rr.status_code, 404)

    # ── T-CPE-5 ─────────────────────────────────────────────────────────────
    def test_T_CPE_5_wrong_key_403(self):
        lid = self.store.insert_pending_listing(_intent("s1"))
        bad = {"api_key": "wrong"}
        self.assertEqual(
            self.client.get("/curator/pending-listings", params=bad).status_code, 403)
        self.assertEqual(
            self.client.post(f"/curator/approve-listing/{lid}", params=bad).status_code, 403)
        self.assertEqual(
            self.client.post(f"/curator/reject-listing/{lid}", params=bad).status_code, 403)


if __name__ == "__main__":
    unittest.main()

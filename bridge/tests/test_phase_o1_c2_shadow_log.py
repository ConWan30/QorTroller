"""Phase O1 C2 — operator_agent_shadow_log table + helpers tests.

Validates the off-chain audit trail for Cedar evaluations in shadow mode.
"""

import os
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)


SENTRY_ID = "0xb21e1ec258d2d381c313f84944bd36fbc63badb2c9a24c2412212d3a27e3e42c"
SENTRY_BUNDLE_ROOT = "0xebe899279b230ff5d71db22dc4b80282c810ff5bd1a9d249db6e6d309af52e41"


def _make_store():
    from vapi_bridge.store import Store
    return Store(str(Path(tempfile.mkdtemp()) / "p_o1_c2_shadow.db"))


class TestShadowLogRoundTrip(unittest.TestCase):
    """T-O1-C2-SH-1: insert + read back."""

    def test_round_trip_basic(self):
        store = _make_store()
        rid = store.insert_operator_agent_shadow_log(
            agent_id=SENTRY_ID,
            action="skill:read",
            resource="lane://wiki/index.md",
            context_json='{"shadow_mode":true}',
            decision="permit",
            bundle_merkle_root=SENTRY_BUNDLE_ROOT,
            bundle_path="bridge/vapi_bridge/cedar_bundles/anchor_sentry_o1_shadow_v1.json",
            draft_payload_hash="0x" + "0" * 64,
            source="test",
        )
        self.assertGreater(rid, 0)
        rows = store.get_operator_agent_shadow_log(limit=10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["agent_id"], SENTRY_ID)
        self.assertEqual(rows[0]["decision"], "permit")
        self.assertEqual(rows[0]["bundle_merkle_root"], SENTRY_BUNDLE_ROOT)


class TestShadowLogIdempotency(unittest.TestCase):
    """T-O1-C2-SH-2: UNIQUE(agent_id, action, resource, evaluated_at_bucket)."""

    def test_same_bucket_returns_same_id(self):
        store = _make_store()
        kw = dict(
            agent_id=SENTRY_ID, action="skill:read",
            resource="lane://wiki/index.md", context_json="{}",
            decision="permit", bundle_merkle_root="0x" + "a" * 64,
            bundle_path="p", draft_payload_hash="0x" + "0" * 64, source="t",
        )
        a = store.insert_operator_agent_shadow_log(**kw)
        b = store.insert_operator_agent_shadow_log(**kw)  # same second
        self.assertEqual(a, b)
        self.assertEqual(len(store.get_operator_agent_shadow_log()), 1)


class TestShadowLogPagination(unittest.TestCase):
    """T-O1-C2-SH-3: limit cap + ordering."""

    def test_limit_capped_and_ordered_desc(self):
        store = _make_store()
        # Insert 5 distinct rows in distinct seconds (sleep 1s between)
        for i in range(5):
            store.insert_operator_agent_shadow_log(
                agent_id=SENTRY_ID,
                action=f"skill:read{i}",
                resource=f"lane://wiki/{i}.md",
                context_json="{}",
                decision="permit",
                bundle_merkle_root="0x" + str(i) * 63 + "0",
                bundle_path="p",
                draft_payload_hash="",
                source="t",
            )
            time.sleep(1.05)
        rows = store.get_operator_agent_shadow_log(limit=3)
        self.assertEqual(len(rows), 3)
        # DESC order — newest first
        self.assertEqual(rows[0]["action"], "skill:read4")
        self.assertEqual(rows[2]["action"], "skill:read2")


class TestShadowLogSummary(unittest.TestCase):
    """T-O1-C2-SH-4: aggregate decision counts."""

    def test_summary_counts_by_decision(self):
        store = _make_store()
        for i, dec in enumerate(["permit", "permit", "forbid_explicit_policy",
                                 "forbid_default_deny"]):
            store.insert_operator_agent_shadow_log(
                agent_id=SENTRY_ID,
                action=f"a{i}", resource=f"r{i}",
                context_json="{}",
                decision=dec, bundle_merkle_root="0x" + str(i) * 63 + "0",
                bundle_path="p", draft_payload_hash="", source="t",
            )
            time.sleep(1.05)
        summ = store.get_operator_agent_shadow_summary(agent_id=SENTRY_ID)
        self.assertEqual(summ["total"], 4)
        self.assertEqual(summ["by_decision"]["permit"], 2)
        self.assertEqual(summ["by_decision"]["forbid_explicit_policy"], 1)
        self.assertEqual(summ["by_decision"]["forbid_default_deny"], 1)


class TestShadowLogFiltering(unittest.TestCase):
    """T-O1-C2-SH-5: agent_id + decision filters."""

    def test_filters_independent(self):
        store = _make_store()
        other_agent = "0x" + "f" * 64
        for aid, dec in [(SENTRY_ID, "permit"),
                         (SENTRY_ID, "forbid_explicit_policy"),
                         (other_agent, "permit")]:
            store.insert_operator_agent_shadow_log(
                agent_id=aid, action=f"a-{aid[2:5]}-{dec}", resource="r",
                context_json="{}", decision=dec,
                bundle_merkle_root="0x" + "b" * 64, bundle_path="p",
                draft_payload_hash="", source="t",
            )
            time.sleep(1.05)
        # Filter by agent only
        self.assertEqual(
            len(store.get_operator_agent_shadow_log(agent_id=SENTRY_ID)), 2
        )
        # Filter by decision only
        self.assertEqual(
            len(store.get_operator_agent_shadow_log(decision_filter="permit")), 2
        )
        # Filter by both
        self.assertEqual(
            len(store.get_operator_agent_shadow_log(
                agent_id=SENTRY_ID, decision_filter="permit"
            )),
            1,
        )


if __name__ == "__main__":
    unittest.main()

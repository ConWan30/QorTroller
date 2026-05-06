"""Phase O1 C2 — cedar_shadow_runtime evaluator tests.

Validates the in-process Cedar evaluator with fail-open behavior and
correct decision dispatch.
"""

import asyncio
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)


SENTRY_ID = "0xb21e1ec258d2d381c313f84944bd36fbc63badb2c9a24c2412212d3a27e3e42c"
GUARDIAN_ID = "0xbd8c7fba08815b7ed343973c9c7300c062303b1acd19e8d9847a953ce5fa38d1"


def _live_cfg():
    """cfg pointing at the real Cedar bundle dir for happy-path tests."""
    return types.SimpleNamespace(
        cedar_bundle_dir="bridge/vapi_bridge/cedar_bundles",
        operator_agent_anchor_sentry_id=SENTRY_ID,
        operator_agent_guardian_id=GUARDIAN_ID,
    )


def _empty_cfg():
    """cfg with bogus bundle dir for missing-bundle tests."""
    return types.SimpleNamespace(
        cedar_bundle_dir="/nonexistent/path",
        operator_agent_anchor_sentry_id=SENTRY_ID,
        operator_agent_guardian_id=GUARDIAN_ID,
    )


def _make_store():
    from vapi_bridge.store import Store
    return Store(str(Path(tempfile.mkdtemp()) / "p_o1_c2_runtime.db"))


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestEvaluatorPermitPath(unittest.TestCase):
    """T-O1-C2-RT-1: Sentry reading wiki lane → permit per bundle."""

    def test_sentry_read_wiki_permits(self):
        from vapi_bridge.cedar_shadow_runtime import evaluate_agent_action
        from vapi_bridge.cedar_parser import CedarDecision
        cfg = _live_cfg()
        store = _make_store()
        result = _run(evaluate_agent_action(
            agent_id=SENTRY_ID,
            action="skill:read",
            resource="lane://wiki/index.md",
            context={"shadow_mode": True},
            cfg=cfg, store=store,
        ))
        self.assertIsNone(result.error)
        self.assertTrue(result.is_permit)
        self.assertEqual(
            result.decision,
            CedarDecision.PERMIT,
        )
        self.assertGreater(result.shadow_log_row_id, 0)
        self.assertTrue(result.bundle_merkle_root_hex.startswith("0x"))


class TestEvaluatorForbidPath(unittest.TestCase):
    """T-O1-C2-RT-2: Sentry git-push attempt → forbid_explicit_policy."""

    def test_sentry_git_push_forbidden(self):
        from vapi_bridge.cedar_shadow_runtime import evaluate_agent_action
        from vapi_bridge.cedar_parser import CedarDecision
        cfg = _live_cfg()
        store = _make_store()
        result = _run(evaluate_agent_action(
            agent_id=SENTRY_ID,
            action="tool:git-push",
            resource="lane://wiki/anything.md",
            cfg=cfg, store=store,
        ))
        self.assertEqual(result.decision, CedarDecision.FORBID_EXPLICIT_POLICY)
        self.assertTrue(result.is_forbid)


class TestEvaluatorFailOpenUnknownAgent(unittest.TestCase):
    """T-O1-C2-RT-3: Unknown agent → FORBID_DEFAULT_DENY + error annotation."""

    def test_unknown_agent_fails_open_deny(self):
        from vapi_bridge.cedar_shadow_runtime import evaluate_agent_action
        from vapi_bridge.cedar_parser import CedarDecision
        cfg = _live_cfg()
        store = _make_store()
        result = _run(evaluate_agent_action(
            agent_id="0x" + "f" * 64,
            action="skill:read",
            resource="lane://wiki/index.md",
            cfg=cfg, store=store,
        ))
        self.assertEqual(result.decision, CedarDecision.FORBID_DEFAULT_DENY)
        self.assertEqual(result.error, "no_bundle_mapping_for_agent_id")


class TestEvaluatorFailOpenMissingBundle(unittest.TestCase):
    """T-O1-C2-RT-4: Bundle file missing → FORBID_DEFAULT_DENY + error."""

    def test_missing_bundle_fails_open(self):
        from vapi_bridge.cedar_shadow_runtime import evaluate_agent_action
        from vapi_bridge.cedar_parser import CedarDecision
        cfg = _empty_cfg()
        store = _make_store()
        result = _run(evaluate_agent_action(
            agent_id=SENTRY_ID,
            action="skill:read",
            resource="lane://wiki/index.md",
            cfg=cfg, store=store,
        ))
        self.assertEqual(result.decision, CedarDecision.FORBID_DEFAULT_DENY)
        self.assertEqual(result.error, "bundle_file_missing")


class TestEvaluatorPersistsShadowLog(unittest.TestCase):
    """T-O1-C2-RT-5: Every evaluation writes a shadow log row."""

    def test_each_evaluation_persists_one_row(self):
        from vapi_bridge.cedar_shadow_runtime import evaluate_agent_action
        cfg = _live_cfg()
        store = _make_store()
        # Run 2 distinct evaluations 1+ sec apart
        _run(evaluate_agent_action(
            agent_id=SENTRY_ID, action="skill:read",
            resource="lane://wiki/a", cfg=cfg, store=store,
        ))
        import time
        time.sleep(1.05)
        _run(evaluate_agent_action(
            agent_id=SENTRY_ID, action="tool:git-push",
            resource="lane://wiki/b", cfg=cfg, store=store,
        ))
        rows = store.get_operator_agent_shadow_log(limit=10)
        self.assertEqual(len(rows), 2)


class TestEvaluatorMerkleRecomputed(unittest.TestCase):
    """T-O1-C2-RT-6 (INV-OPERATOR-AGENT-005): Merkle root in result matches recompute."""

    def test_merkle_root_matches_bundle_file(self):
        from vapi_bridge.cedar_shadow_runtime import evaluate_agent_action
        from vapi_bridge.cedar_parser import bundle_merkle_root
        cfg = _live_cfg()
        store = _make_store()
        result = _run(evaluate_agent_action(
            agent_id=SENTRY_ID, action="skill:read",
            resource="lane://wiki/index.md", cfg=cfg, store=store,
        ))
        # Independently compute expected
        bundle_path = Path(cfg.cedar_bundle_dir) / "anchor_sentry_o1_shadow_v1.json"
        raw = json.loads(bundle_path.read_text(encoding="utf-8"))
        expected = "0x" + bundle_merkle_root(raw).hex()
        self.assertEqual(result.bundle_merkle_root_hex.lower(), expected.lower())


if __name__ == "__main__":
    unittest.main()

"""Phase O1 C3 — Drift detection (BUNDLE_HASH + SCOPE_HASH_GOVERNANCE) tests.

Validates the operator-triggered sweep primitives that detect post-anchor
mutations of bundle files (BUNDLE_HASH_DRIFT) and on-chain operational/
governance divergence (SCOPE_HASH_GOVERNANCE_DRIFT).
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


def _make_store():
    from vapi_bridge.store import Store
    return Store(str(Path(tempfile.mkdtemp()) / "p_o1_c3_drift.db"))


def _seed_activation(store, agent_id, bundle_path, anchored_root):
    """Insert a synthetic activation_log row so drift detector has truth."""
    store.insert_operator_agent_activation(
        agent_id=agent_id,
        from_phase="O0_DORMANT",
        to_phase="O1_SHADOW",
        from_scope_root="0x" + "0" * 64,
        to_scope_root=anchored_root,
        bundle_path=str(bundle_path),
        governance_tx_hash="0x" + "1" * 64,
        operational_tx_hash="0x" + "2" * 64,
        governance_block_number=12345,
        operational_block_number=12340,
        operator_authority_hash="0x" + "3" * 64,
        reason_text="test seed",
    )


def _make_test_bundle(tmpdir: Path, agent_id: str) -> tuple[Path, str]:
    """Write a minimal valid Cedar bundle + return its Merkle root."""
    from vapi_bridge.cedar_parser import bundle_merkle_root
    bundle = {
        "bundle_id":  "test_bundle_v1",
        "version":    "v1",
        "agent_id":   agent_id,
        "phase":      "O1_SHADOW",
        "lane_prefixes": ["lane://wiki/"],
        "active_capabilities": ["skill:read"],
        "policies": [
            {"effect": "permit", "action": "skill:read",
             "resource": "lane://wiki/*"},
        ],
    }
    path = tmpdir / "test_bundle.json"
    canonical = json.dumps(bundle, sort_keys=True, separators=(",", ":"))
    path.write_text(canonical, encoding="utf-8")
    root_hex = "0x" + bundle_merkle_root(bundle).hex()
    return path, root_hex


class TestBundleHashDriftClean(unittest.TestCase):
    def test_clean_bundle_no_drift(self):
        from vapi_bridge.cedar_shadow_runtime import detect_bundle_hash_drift
        store = _make_store()
        tmpdir = Path(tempfile.mkdtemp())
        bundle_path, anchored_root = _make_test_bundle(tmpdir, SENTRY_ID)
        _seed_activation(store, SENTRY_ID, bundle_path, anchored_root)
        cfg = types.SimpleNamespace(
            operator_agent_anchor_sentry_id=SENTRY_ID,
            operator_agent_guardian_id="",
        )
        result = detect_bundle_hash_drift(cfg=cfg, store=store)
        self.assertEqual(result.agents_checked, 1)
        self.assertTrue(result.clean)
        self.assertEqual(len(result.findings), 0)


class TestBundleHashDriftMutation(unittest.TestCase):
    def test_mutated_bundle_drift(self):
        from vapi_bridge.cedar_shadow_runtime import detect_bundle_hash_drift
        store = _make_store()
        tmpdir = Path(tempfile.mkdtemp())
        bundle_path, anchored_root = _make_test_bundle(tmpdir, SENTRY_ID)
        _seed_activation(store, SENTRY_ID, bundle_path, anchored_root)
        # Mutate bundle post-anchor
        mutated = json.loads(bundle_path.read_text())
        mutated["policies"].append({
            "effect": "permit", "action": "tool:git-push",
            "resource": "lane://wiki/*",
        })
        bundle_path.write_text(
            json.dumps(mutated, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        cfg = types.SimpleNamespace(
            operator_agent_anchor_sentry_id=SENTRY_ID,
            operator_agent_guardian_id="",
        )
        result = detect_bundle_hash_drift(cfg=cfg, store=store)
        self.assertEqual(len(result.findings), 1)
        f = result.findings[0]
        self.assertEqual(f.drift_type, "BUNDLE_HASH_DRIFT")
        self.assertEqual(f.expected_value.lower(), anchored_root.lower())
        self.assertNotEqual(f.expected_value.lower(), f.actual_value.lower())
        rows = store.get_operator_agent_drift_log()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["drift_type"], "BUNDLE_HASH_DRIFT")


class TestBundleHashDriftMissingFile(unittest.TestCase):
    def test_missing_bundle_drift(self):
        from vapi_bridge.cedar_shadow_runtime import detect_bundle_hash_drift
        store = _make_store()
        tmpdir = Path(tempfile.mkdtemp())
        bundle_path, anchored_root = _make_test_bundle(tmpdir, SENTRY_ID)
        _seed_activation(store, SENTRY_ID, bundle_path, anchored_root)
        bundle_path.unlink()
        cfg = types.SimpleNamespace(
            operator_agent_anchor_sentry_id=SENTRY_ID,
            operator_agent_guardian_id="",
        )
        result = detect_bundle_hash_drift(cfg=cfg, store=store)
        self.assertEqual(len(result.findings), 1)
        self.assertEqual(result.findings[0].actual_value, "<file_missing>")


class TestScopeHashGovernanceDriftFailOpenNoChain(unittest.TestCase):
    def test_no_chain_returns_clean_with_error(self):
        from vapi_bridge.cedar_shadow_runtime import detect_scope_hash_governance_drift
        store = _make_store()
        cfg = types.SimpleNamespace(
            operator_agent_anchor_sentry_id=SENTRY_ID,
            operator_agent_guardian_id=GUARDIAN_ID,
        )

        async def run():
            return await detect_scope_hash_governance_drift(
                cfg=cfg, store=store, chain=None,
            )

        result = asyncio.get_event_loop().run_until_complete(run())
        self.assertEqual(result.error, "chain_not_configured")
        self.assertTrue(result.clean)


class TestDriftLogIdempotency(unittest.TestCase):
    def test_same_second_idempotent(self):
        from vapi_bridge.cedar_shadow_runtime import detect_bundle_hash_drift
        store = _make_store()
        tmpdir = Path(tempfile.mkdtemp())
        bundle_path, anchored_root = _make_test_bundle(tmpdir, SENTRY_ID)
        _seed_activation(store, SENTRY_ID, bundle_path, anchored_root)
        bundle_path.write_text(
            json.dumps({"different": True}, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        cfg = types.SimpleNamespace(
            operator_agent_anchor_sentry_id=SENTRY_ID,
            operator_agent_guardian_id="",
        )
        detect_bundle_hash_drift(cfg=cfg, store=store)
        detect_bundle_hash_drift(cfg=cfg, store=store)
        rows = store.get_operator_agent_drift_log()
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()

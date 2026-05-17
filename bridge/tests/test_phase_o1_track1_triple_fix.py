"""Phase O1 Track 1 — cedar_shadow_runtime triple-fix tests (C-2 + C-3 + C-4).

Confirms three Mythos-audit-surfaced source bugs are closed in
`bridge/vapi_bridge/cedar_shadow_runtime.py`:

  C-2: bundle_path resolution.  Pre-fix the drift detector wrapped the
       activation_log bundle_path field in Path() without prefixing the
       cedar_bundle_dir.  Anchors from 2026-05-09+ stored bare filenames
       like "anchor_sentry_o2_suggest_v2.json" so .exists() failed →
       87+ false BUNDLE_HASH_DRIFT bundle_file_missing findings per 24h.
       Real drift was at risk of being buried in alarm-fatigue noise.

  C-3: Curator outside drift coverage.  Pre-fix both
       detect_bundle_hash_drift and detect_scope_hash_governance_drift
       only iterated (sentry_id, guardian_id).  Curator (live since
       2026-05-09) was structurally invisible to drift detection despite
       carrying marketplace-listing-suspend authority at O3_ACTING.

  C-4: hardcoded O1_SHADOW v1 filenames.  Pre-fix _bundle_path_for_agent
       returned "_o1_shadow_v1.json" suffix regardless of phase.  Fleet
       was at O2_SUGGEST v2 since Track 2 C8 ceremony 2026-05-12.  Latent
       because polling was off; would have produced silent stale-policy
       evaluations the moment any operator endpoint or polling loop fired.
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

# Lightweight stubs so the module imports under test envs without web3.
for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)


SENTRY_ID = "0xb21e1ec258d2d381c313f84944bd36fbc63badb2c9a24c2412212d3a27e3e42c"
GUARDIAN_ID = "0xbd8c7fba08815b7ed343973c9c7300c062303b1acd19e8d9847a953ce5fa38d1"
CURATOR_ID = "0xed6a2df58e5ec50c1f88e127f6982a348f6855202b662b8ad73ffa1c1fda11a8"


def _make_store():
    from vapi_bridge.store import Store
    return Store(str(Path(tempfile.mkdtemp()) / "p_o1_track1.db"))


def _write_min_bundle(path: Path, agent_id: str, phase: str = "O1_SHADOW") -> str:
    """Write a minimal valid Cedar bundle + return its anchored Merkle root."""
    from vapi_bridge.cedar_parser import bundle_merkle_root
    bundle = {
        "bundle_id":  f"{phase.lower()}_test_v1",
        "version":    "v1",
        "agent_id":   agent_id,
        "phase":      phase,
        "lane_prefixes": ["lane://wiki/"],
        "active_capabilities": ["skill:read"],
        "policies": [
            {"effect": "permit", "action": "skill:read",
             "resource": "lane://wiki/*"},
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(bundle, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return "0x" + bundle_merkle_root(bundle).hex()


def _seed_activation(store, agent_id, bundle_path_str, anchored_root,
                     to_phase="O1_SHADOW"):
    """Insert one activation_log row keyed by agent_id."""
    store.insert_operator_agent_activation(
        agent_id=agent_id,
        from_phase="O0_DORMANT",
        to_phase=to_phase,
        from_scope_root="0x" + "0" * 64,
        to_scope_root=anchored_root,
        bundle_path=bundle_path_str,
        governance_tx_hash="0x" + "1" * 64,
        operational_tx_hash="0x" + "2" * 64,
        governance_block_number=12345,
        operational_block_number=12340,
        operator_authority_hash="0x" + "3" * 64,
        reason_text="track1 test seed",
    )


# ──────────────────────────────────────────────────────────────────
# C-2  ·  bundle_path resolution backward + forward compat
# ──────────────────────────────────────────────────────────────────

class TestTrack1C2BarefileResolved(unittest.TestCase):
    """T-O1-TRACK1-C2-1: bare-filename activation row resolves via bundle_dir."""

    def test_bare_filename_via_bundle_dir(self):
        from vapi_bridge.cedar_shadow_runtime import detect_bundle_hash_drift
        store = _make_store()
        bundle_dir = Path(tempfile.mkdtemp())
        # Write bundle as bare filename inside bundle_dir
        bare_name = "anchor_sentry_o2_suggest_v2.json"
        bundle_file = bundle_dir / bare_name
        anchored_root = _write_min_bundle(bundle_file, SENTRY_ID, "O2_SUGGEST")
        # Activation row stores ONLY the bare filename (2026-05-09+ standard)
        _seed_activation(store, SENTRY_ID, bare_name, anchored_root,
                         to_phase="O2_SUGGEST")
        cfg = types.SimpleNamespace(
            operator_agent_anchor_sentry_id=SENTRY_ID,
            operator_agent_guardian_id="",
            operator_agent_curator_id="",
            cedar_bundle_dir=str(bundle_dir),
        )
        result = detect_bundle_hash_drift(cfg=cfg, store=store)
        # Should be CLEAN — file exists, Merkle matches anchored root.
        self.assertEqual(result.agents_checked, 1)
        self.assertTrue(
            result.clean,
            msg=f"Expected clean; got findings={[f.actual_value for f in result.findings]}",
        )


class TestTrack1C2FullRelativePathBackwardCompat(unittest.TestCase):
    """T-O1-TRACK1-C2-2: 2026-05-03 full-relative-path activation row still resolves.

    Pre-Track-1 the Sentry+Guardian Phase O1 C1 anchors stored full
    relative paths like "bridge/vapi_bridge/cedar_bundles/...json".
    Track 1 C-2 fix must NOT regress that case.
    """

    def test_full_relative_path_used_as_is(self):
        from vapi_bridge.cedar_shadow_runtime import detect_bundle_hash_drift
        store = _make_store()
        tmpdir = Path(tempfile.mkdtemp())
        # Build a nested directory mirroring the 2026-05-03 storage form.
        # The activation row stores the relative path as-is; the actual file
        # lives at that resolved path from the test cwd.
        bundle_subdir = tmpdir / "fake_bridge_dir" / "cedar_bundles"
        bundle_subdir.mkdir(parents=True)
        bundle_file = bundle_subdir / "anchor_sentry_o1_shadow_v1.json"
        anchored_root = _write_min_bundle(bundle_file, SENTRY_ID, "O1_SHADOW")
        # Store the FULL relative path with directory component.
        full_rel = str(bundle_file)  # absolute-from-tempdir; counts as is_absolute
        _seed_activation(store, SENTRY_ID, full_rel, anchored_root)
        cfg = types.SimpleNamespace(
            operator_agent_anchor_sentry_id=SENTRY_ID,
            operator_agent_guardian_id="",
            operator_agent_curator_id="",
            cedar_bundle_dir="some/other/dir",  # explicitly unused for this case
        )
        result = detect_bundle_hash_drift(cfg=cfg, store=store)
        self.assertTrue(
            result.clean,
            msg=f"Expected clean; got findings={[f.actual_value for f in result.findings]}",
        )


class TestTrack1C2HelperUnit(unittest.TestCase):
    """T-O1-TRACK1-C2-3: _resolve_bundle_path helper unit semantics."""

    def test_bare_filename_prepends_bundle_dir(self):
        from vapi_bridge.cedar_shadow_runtime import _resolve_bundle_path
        cfg = types.SimpleNamespace(cedar_bundle_dir="bridge/vapi_bridge/cedar_bundles")
        out = _resolve_bundle_path("curator_o2_suggest_v2.json", cfg)
        self.assertEqual(
            out, Path("bridge/vapi_bridge/cedar_bundles") / "curator_o2_suggest_v2.json")

    def test_path_with_dir_used_as_is(self):
        from vapi_bridge.cedar_shadow_runtime import _resolve_bundle_path
        cfg = types.SimpleNamespace(cedar_bundle_dir="some/other/dir")
        out = _resolve_bundle_path("bridge/vapi_bridge/cedar_bundles/x.json", cfg)
        # Path has non-trivial parent → used as-is (NOT prepended).
        self.assertEqual(out, Path("bridge/vapi_bridge/cedar_bundles/x.json"))

    def test_absolute_path_used_as_is(self):
        from vapi_bridge.cedar_shadow_runtime import _resolve_bundle_path
        cfg = types.SimpleNamespace(cedar_bundle_dir="some/other/dir")
        abs_path = str(Path(tempfile.mkdtemp()) / "abs.json")
        out = _resolve_bundle_path(abs_path, cfg)
        self.assertEqual(out, Path(abs_path))


# ──────────────────────────────────────────────────────────────────
# C-3  ·  Curator included in drift candidates
# ──────────────────────────────────────────────────────────────────

class TestTrack1C3BundleCuratorCovered(unittest.TestCase):
    """T-O1-TRACK1-C3-1: bundle drift sweep iterates Curator + flags real Curator drift."""

    def test_curator_bundle_mutation_detected(self):
        from vapi_bridge.cedar_shadow_runtime import detect_bundle_hash_drift
        store = _make_store()
        bundle_dir = Path(tempfile.mkdtemp())
        bundle_file = bundle_dir / "curator_o2_suggest_v2.json"
        anchored_root = _write_min_bundle(bundle_file, CURATOR_ID, "O2_SUGGEST")
        _seed_activation(store, CURATOR_ID, "curator_o2_suggest_v2.json",
                         anchored_root, to_phase="O2_SUGGEST")
        # Mutate Curator bundle post-anchor (simulates real tampering).
        raw = json.loads(bundle_file.read_text())
        raw["policies"].append({
            "effect": "permit",
            "action": "tool:marketplace-listing-suspend",
            "resource": "chain://iotex-testnet",
        })
        bundle_file.write_text(
            json.dumps(raw, sort_keys=True, separators=(",", ":")), encoding="utf-8")

        cfg = types.SimpleNamespace(
            operator_agent_anchor_sentry_id="",
            operator_agent_guardian_id="",
            operator_agent_curator_id=CURATOR_ID,
            cedar_bundle_dir=str(bundle_dir),
        )
        result = detect_bundle_hash_drift(cfg=cfg, store=store)
        self.assertEqual(result.agents_checked, 1)
        self.assertEqual(len(result.findings), 1)
        finding = result.findings[0]
        self.assertEqual(finding.agent_id.lower(), CURATOR_ID.lower())
        self.assertEqual(finding.drift_type, "BUNDLE_HASH_DRIFT")
        self.assertNotEqual(
            finding.expected_value.lower(), finding.actual_value.lower())


class TestTrack1C3CandidatesAllThree(unittest.TestCase):
    """T-O1-TRACK1-C3-2: agents_checked counts all three when configured."""

    def test_all_three_agents_iterated(self):
        from vapi_bridge.cedar_shadow_runtime import detect_bundle_hash_drift
        store = _make_store()
        bundle_dir = Path(tempfile.mkdtemp())
        # Seed three clean activations
        for aid, fname in [
            (SENTRY_ID,   "anchor_sentry_o2_suggest_v2.json"),
            (GUARDIAN_ID, "guardian_o2_suggest_v2.json"),
            (CURATOR_ID,  "curator_o2_suggest_v2.json"),
        ]:
            bp = bundle_dir / fname
            anchored = _write_min_bundle(bp, aid, "O2_SUGGEST")
            _seed_activation(store, aid, fname, anchored, to_phase="O2_SUGGEST")
        cfg = types.SimpleNamespace(
            operator_agent_anchor_sentry_id=SENTRY_ID,
            operator_agent_guardian_id=GUARDIAN_ID,
            operator_agent_curator_id=CURATOR_ID,
            cedar_bundle_dir=str(bundle_dir),
        )
        result = detect_bundle_hash_drift(cfg=cfg, store=store)
        self.assertEqual(result.agents_checked, 3)
        self.assertTrue(result.clean)


class TestTrack1C3ScopeGovernanceCuratorCovered(unittest.TestCase):
    """T-O1-TRACK1-C3-3: scope governance sweep iterates Curator too."""

    def test_curator_in_scope_governance_candidates(self):
        """Without a chain stub the sweep returns chain_not_configured;
        the load-bearing assertion is candidates count BEFORE the chain hop."""
        from vapi_bridge.cedar_shadow_runtime import detect_scope_hash_governance_drift
        # Provide minimal chain stub that returns different op vs gov roots
        # to force divergence detection per candidate.

        class _StubChain:
            async def get_agent_scope_root(self, aid):
                # Different per-agent → forces 3 divergence findings
                return bytes.fromhex(("aa" * 32) if "ed6a2df5" in aid else
                                     ("bb" * 32) if "bd8c7fba" in aid else
                                     ("cc" * 32))
            async def get_agent_governance_scope(self, aid):
                # All gov roots differ from op roots → 3 findings expected
                return bytes.fromhex("dd" * 32)

        store = _make_store()
        cfg = types.SimpleNamespace(
            operator_agent_anchor_sentry_id=SENTRY_ID,
            operator_agent_guardian_id=GUARDIAN_ID,
            operator_agent_curator_id=CURATOR_ID,
        )
        result = asyncio.run(detect_scope_hash_governance_drift(
            cfg=cfg, store=store, chain=_StubChain(),
        ))
        # All three agents should produce divergence findings.
        self.assertEqual(result.agents_checked, 3)
        self.assertEqual(len(result.findings), 3)
        agent_ids_found = {f.agent_id.lower() for f in result.findings}
        self.assertIn(CURATOR_ID.lower(), agent_ids_found)
        self.assertIn(SENTRY_ID.lower(), agent_ids_found)
        self.assertIn(GUARDIAN_ID.lower(), agent_ids_found)


# ──────────────────────────────────────────────────────────────────
# C-4  ·  phase-aware bundle resolver
# ──────────────────────────────────────────────────────────────────

class TestTrack1C4PhaseAwareResolver(unittest.TestCase):
    """T-O1-TRACK1-C4-*: _bundle_path_for_agent reads activation_log when store provided."""

    def setUp(self):
        self.bundle_dir = Path(tempfile.mkdtemp())
        self.cfg = types.SimpleNamespace(
            operator_agent_anchor_sentry_id=SENTRY_ID,
            operator_agent_guardian_id=GUARDIAN_ID,
            operator_agent_curator_id=CURATOR_ID,
            cedar_bundle_dir=str(self.bundle_dir),
        )

    def test_o2_suggest_resolves_to_recorded_filename(self):
        from vapi_bridge.cedar_shadow_runtime import _bundle_path_for_agent
        store = _make_store()
        bp = self.bundle_dir / "anchor_sentry_o2_suggest_v2.json"
        anchored = _write_min_bundle(bp, SENTRY_ID, "O2_SUGGEST")
        _seed_activation(store, SENTRY_ID, "anchor_sentry_o2_suggest_v2.json",
                         anchored, to_phase="O2_SUGGEST")
        out = _bundle_path_for_agent(SENTRY_ID, self.cfg, store=store)
        self.assertEqual(out, bp)
        self.assertTrue(out.exists())

    def test_o3_acting_resolves_to_recorded_filename(self):
        from vapi_bridge.cedar_shadow_runtime import _bundle_path_for_agent
        store = _make_store()
        bp = self.bundle_dir / "guardian_o3_acting_v1.json"
        anchored = _write_min_bundle(bp, GUARDIAN_ID, "O3_ACTING")
        _seed_activation(store, GUARDIAN_ID, "guardian_o3_acting_v1.json",
                         anchored, to_phase="O3_ACTING")
        out = _bundle_path_for_agent(GUARDIAN_ID, self.cfg, store=store)
        self.assertEqual(out.name, "guardian_o3_acting_v1.json")

    def test_curator_o2_resolves_to_recorded_filename(self):
        from vapi_bridge.cedar_shadow_runtime import _bundle_path_for_agent
        store = _make_store()
        bp = self.bundle_dir / "curator_o2_suggest_v2.json"
        anchored = _write_min_bundle(bp, CURATOR_ID, "O2_SUGGEST")
        _seed_activation(store, CURATOR_ID, "curator_o2_suggest_v2.json",
                         anchored, to_phase="O2_SUGGEST")
        out = _bundle_path_for_agent(CURATOR_ID, self.cfg, store=store)
        self.assertEqual(out.name, "curator_o2_suggest_v2.json")

    def test_no_store_falls_back_to_o1_shadow_v1(self):
        """T-O1-TRACK1-C4-4: store=None preserves legacy default behavior."""
        from vapi_bridge.cedar_shadow_runtime import _bundle_path_for_agent
        out = _bundle_path_for_agent(SENTRY_ID, self.cfg, store=None)
        self.assertEqual(out.name, "anchor_sentry_o1_shadow_v1.json")

    def test_no_activation_row_falls_back_to_o1_shadow_v1(self):
        """T-O1-TRACK1-C4-5: empty activation_log → fail-open to O1_SHADOW v1."""
        from vapi_bridge.cedar_shadow_runtime import _bundle_path_for_agent
        store = _make_store()  # empty, no activations seeded
        out = _bundle_path_for_agent(CURATOR_ID, self.cfg, store=store)
        self.assertEqual(out.name, "curator_o1_shadow_v1.json")

    def test_unknown_agent_id_returns_none(self):
        """T-O1-TRACK1-C4-6: agent_id outside the 3-tuple still returns None."""
        from vapi_bridge.cedar_shadow_runtime import _bundle_path_for_agent
        store = _make_store()
        out = _bundle_path_for_agent("0x" + "9" * 64, self.cfg, store=store)
        self.assertIsNone(out)


if __name__ == "__main__":
    unittest.main()

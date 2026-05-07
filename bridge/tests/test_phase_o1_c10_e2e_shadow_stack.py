"""Phase O1 C10 — End-to-end integration test for the Cedar SHADOW stack.

Validates the C2/C3/C4/C6 layers as a SYSTEM, not just unit-by-unit.

Why this test exists:
The C9.1 path-shape bug (commit 9bbab6ed) slipped past every unit test
because no test exercised the layers together. C2 unit tests verified the
evaluator. C3 unit tests verified drift detection. C6 unit tests verified
FSCA rules. But nothing verified that an action evaluated by C2 lands in
the same shadow_log that C5/C8 reads, OR that a drift induced via the C3
sweeper surfaces as a C6 contradiction.

C10 closes that gap by running one scenario end-to-end:

  Setup    -> temp DB + on-disk bundle file + activation_log row
  Phase 1  -> evaluate_agent_action() with several decisions
              -> shadow_log entries persist with correct decisions
  Phase 2  -> detect_bundle_hash_drift() returns CLEAN (anchored == disk)
  Phase 3  -> mutate the bundle file on disk (the canary)
  Phase 4  -> detect_bundle_hash_drift() returns BUNDLE_HASH_DRIFT finding
              -> drift_log row persists
  Phase 5  -> FleetSignalCoherenceAgent._check_contradictions() fires
              BUNDLE_HASH_DRIFT_DETECTED rule with severity=HIGH

If any layer breaks the contract that the next layer depends on, this test
catches it BEFORE production activation. That's the empirical lesson from
C9.1 — system-level guarantees require system-level tests.
"""

import asyncio
import json
import logging
import sys
import tempfile
import time
import types as _types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

# Stub heavy optional deps before bridge import
for _mod in ["web3", "web3.exceptions", "eth_account", "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _types.ModuleType(_mod)

if "dotenv" not in sys.modules:
    _dotenv = _types.ModuleType("dotenv")
    _dotenv.load_dotenv = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules["dotenv"] = _dotenv


SENTRY_ID = "0xb21e1ec258d2d381c313f84944bd36fbc63badb2c9a24c2412212d3a27e3e42c"


def _make_bundle(agent_id: str, *, lane_prefixes=("wiki/",), policies=None) -> dict:
    """Build a minimal valid Cedar bundle (matches cedar_parser strict shape)."""
    return {
        "$schema":       "vapi-cedar-bundle-v1",
        "bundle_id":     "test_e2e_v1",
        "version":       1,
        "agent_id":      agent_id,
        "phase":         "O1_SHADOW",
        "issued_at_iso": "2026-05-07T00:00:00Z",
        "lane_prefixes": list(lane_prefixes),
        "policies":      policies or [
            {
                "id":         "P-001",
                "effect":     "permit",
                "principal":  {"agentId": agent_id},
                "action":     "skill:read-wiki",
                "resource":   "lane://wiki/**",
            },
            {
                "id":         "P-002",
                "effect":     "permit",
                "principal":  {"agentId": agent_id},
                "action":     "tool:kms-sign",
                "resource":   "draft://op/*",
                "constraint": {"shadow_mode": True},
            },
            {
                "id":         "F-001",
                "effect":     "forbid",
                "principal":  {"agentId": agent_id},
                "action":     "tool:git-push",
                "resource":   "*",
            },
        ],
    }


def _write_bundle_canonical(bundle: dict, path: Path) -> bytes:
    """Write bundle as canonical bytes (matches cedar_parser canonical_bytes)."""
    from vapi_bridge.cedar_parser import canonical_bytes
    cb = canonical_bytes(bundle)
    path.write_bytes(cb)
    return cb


def _make_cfg(bundle_dir: Path, sentry_id: str = SENTRY_ID) -> MagicMock:
    cfg = MagicMock()
    cfg.cedar_bundle_dir = str(bundle_dir)
    cfg.operator_agent_anchor_sentry_id = sentry_id
    cfg.operator_agent_guardian_id = ""  # only sentry in this test
    cfg.fleet_coherence_enabled = True
    cfg.dry_run = True
    cfg.ioswarm_enabled = False
    cfg.ioswarm_adjudication_enabled = False
    return cfg


class TestPhaseO1C10EndToEndShadowStack(unittest.TestCase):
    """Single class so all phases share the same DB + bundle state."""

    @classmethod
    def setUpClass(cls):
        from vapi_bridge.store import Store
        from vapi_bridge.cedar_parser import bundle_merkle_root

        cls._tmpdir = Path(tempfile.mkdtemp(prefix="phase_o1_c10_"))
        cls.bundle_dir = cls._tmpdir / "cedar_bundles"
        cls.bundle_dir.mkdir()

        # Bundle filename must match what evaluate_agent_action computes via
        # _bundle_path_for_agent. That helper looks up by sentry_id /
        # guardian_id config matching. To keep this test agnostic of the
        # exact filename heuristic, we point cfg at our temp dir AND seed
        # the activation_log so detect_bundle_hash_drift uses the seeded
        # bundle_path directly.
        cls.bundle_path = cls.bundle_dir / "anchor_sentry_o1_shadow_v1.json"

        cls.bundle = _make_bundle(SENTRY_ID)
        _write_bundle_canonical(cls.bundle, cls.bundle_path)

        cls.anchored_root_bytes = bundle_merkle_root(cls.bundle)
        cls.anchored_root_hex = "0x" + cls.anchored_root_bytes.hex()

        cls.db_path = str(cls._tmpdir / "phase_o1_c10.db")
        cls.store = Store(cls.db_path)
        cls.cfg = _make_cfg(cls.bundle_dir)

        # Seed activation_log so drift detector has anchored truth to compare against.
        cls.store.insert_operator_agent_activation(
            agent_id=SENTRY_ID,
            from_phase="O0_DORMANT",
            to_phase="O1_SHADOW",
            from_scope_root="0x" + "0" * 64,
            to_scope_root=cls.anchored_root_hex,
            bundle_path=str(cls.bundle_path),
            governance_tx_hash="0x" + "1" * 64,
            operational_tx_hash="0x" + "2" * 64,
            governance_block_number=12345,
            operational_block_number=12340,
            operator_authority_hash="0x" + "3" * 64,
            reason_text="phase_o1_c10_e2e_test_seed",
        )

    @classmethod
    def tearDownClass(cls):
        # Best-effort; Windows WAL may hold the DB briefly
        import shutil
        try:
            shutil.rmtree(cls._tmpdir, ignore_errors=True)
        except Exception:
            pass

    # ---------------------------------------------------------------- Phase 1
    def test_phase_1_evaluate_persists_shadow_log(self):
        """Run 3 evaluate_agent_action calls; verify shadow_log persists each."""
        from vapi_bridge.cedar_shadow_runtime import evaluate_agent_action

        # 3 evaluations: 1 permit + 1 shadow_constraint + 1 lane violation
        async def _run():
            r1 = await evaluate_agent_action(
                agent_id=SENTRY_ID,
                action="skill:read-wiki",
                resource="lane://wiki/index.md",
                context={},
                draft_payload_hash="",
                source="c10_test",
                cfg=self.cfg,
                store=self.store,
            )
            r2 = await evaluate_agent_action(
                agent_id=SENTRY_ID,
                action="tool:kms-sign",
                resource="draft://op/X",
                context={"shadow_mode": True},
                draft_payload_hash="hash_x",
                source="c10_test",
                cfg=self.cfg,
                store=self.store,
            )
            r3 = await evaluate_agent_action(
                agent_id=SENTRY_ID,
                action="skill:read-wiki",
                resource="lane://forbidden/path",  # outside lane_prefixes
                context={},
                draft_payload_hash="",
                source="c10_test",
                cfg=self.cfg,
                store=self.store,
            )
            return r1, r2, r3

        r1, r2, r3 = asyncio.get_event_loop().run_until_complete(_run())

        # Verify decisions match expected Cedar semantics
        self.assertEqual(r1.decision.value, "permit",
                         f"P-001 should PERMIT skill:read-wiki on lane://wiki/*; got {r1.decision}")
        self.assertEqual(r2.decision.value, "permit_with_shadow_constraint",
                         f"P-002 should be SHADOW_CONSTRAINT for kms-sign + shadow_mode:true; got {r2.decision}")
        self.assertEqual(r3.decision.value, "forbid_lane_violation",
                         f"lane://forbidden NOT in lane_prefixes should FORBID_LANE_VIOLATION; got {r3.decision}")

        # Verify all 3 persisted to shadow_log
        rows = self.store.get_operator_agent_shadow_log(SENTRY_ID, None, 100)
        self.assertGreaterEqual(
            len(rows), 3,
            f"Expected >=3 shadow_log rows after 3 evals; got {len(rows)}",
        )

    # ---------------------------------------------------------------- Phase 2
    def test_phase_2_drift_sweep_clean_initially(self):
        """detect_bundle_hash_drift returns 0 findings when bundle on disk == anchored."""
        from vapi_bridge.cedar_shadow_runtime import detect_bundle_hash_drift

        result = detect_bundle_hash_drift(cfg=self.cfg, store=self.store)
        self.assertEqual(
            len(result.findings), 0,
            f"CLEAN state should produce 0 findings; got {len(result.findings)}: {result.findings}",
        )

    # ---------------------------------------------------------------- Phase 3+4
    def test_phase_3_4_mutate_bundle_then_drift_fires(self):
        """Mutate the bundle file -> sweep finds BUNDLE_HASH_DRIFT -> drift_log persists."""
        from vapi_bridge.cedar_shadow_runtime import detect_bundle_hash_drift

        # Phase 3: mutate the bundle on disk (add a policy)
        mutated = dict(self.bundle)
        mutated["policies"] = list(mutated["policies"]) + [{
            "id":        "P-MUTATED",
            "effect":    "permit",
            "principal": {"agentId": SENTRY_ID},
            "action":    "skill:read-wiki",
            "resource":  "lane://wiki/extra/**",
        }]
        _write_bundle_canonical(mutated, self.bundle_path)

        # Phase 4: sweep should now detect drift
        result = detect_bundle_hash_drift(cfg=self.cfg, store=self.store)
        self.assertEqual(
            len(result.findings), 1,
            f"Mutated bundle should produce exactly 1 BUNDLE_HASH_DRIFT finding; got {len(result.findings)}",
        )
        finding = result.findings[0]
        self.assertEqual(finding.drift_type, "BUNDLE_HASH_DRIFT")
        self.assertEqual(finding.agent_id.lower(), SENTRY_ID.lower())
        self.assertEqual(finding.expected_value.lower(), self.anchored_root_hex.lower(),
                         "Expected value should be the anchored Merkle root")
        self.assertNotEqual(finding.actual_value.lower(), self.anchored_root_hex.lower(),
                            "Actual value (post-mutation) must differ from anchored")

        # Verify drift_log row persisted
        drift_rows = self.store.get_operator_agent_drift_log(SENTRY_ID, "BUNDLE_HASH_DRIFT", 10)
        self.assertGreaterEqual(
            len(drift_rows), 1,
            f"At least 1 drift_log row expected post-mutation; got {len(drift_rows)}",
        )

    # ---------------------------------------------------------------- Phase 5
    def test_phase_5_fsca_fires_bundle_drift_contradiction(self):
        """FSCA _check_contradictions fires BUNDLE_HASH_DRIFT_DETECTED rule."""
        from vapi_bridge.fleet_signal_coherence_agent import FleetSignalCoherenceAgent

        bus = MagicMock()
        logger = logging.getLogger("test_phase_o1_c10")
        agent = FleetSignalCoherenceAgent(
            store=self.store, config=self.cfg, bus=bus, logger=logger,
        )

        results = asyncio.get_event_loop().run_until_complete(
            agent._check_contradictions()
        )
        fired = [r for r in results if r.get("rule_name") == "BUNDLE_HASH_DRIFT_DETECTED"]
        self.assertEqual(
            len(fired), 1,
            f"BUNDLE_HASH_DRIFT_DETECTED should fire exactly once; got {len(fired)} "
            f"(other rules: {[r.get('rule_name') for r in results]})",
        )
        self.assertEqual(fired[0]["severity"], "HIGH",
                         f"Drift severity should be HIGH; got {fired[0]['severity']}")
        self.assertIn("CedarDriftSweeper", fired[0]["agents_involved"])

    # ---------------------------------------------------------------- Phase 6
    def test_phase_6_endpoints_match_codebase_convention(self):
        """Confirm route declarations include the /operator/ inner prefix.

        Static check that locks the C9.1 path-shape lesson into CI: any
        future contributor who removes the inner /operator/ prefix breaks
        this test, which fails BEFORE the bridge gets restarted in
        production.
        """
        import re
        operator_api_text = (BRIDGE_DIR / "vapi_bridge" / "operator_api.py").read_text(
            encoding="utf-8"
        )
        # All operator-agent-* routes must include the inner /operator/ prefix
        # to match codebase convention (see feedback_operator_route_doubled_prefix).
        pattern = r'@app\.(get|post)\("/operator/operator-agent-(activation|shadow|drift)-log"'
        matches = re.findall(pattern, operator_api_text)
        self.assertGreaterEqual(
            len(matches), 3,
            "Three /operator/operator-agent-{activation,shadow,drift}-log "
            "routes must be present with the doubled-prefix codebase convention. "
            "If you removed the inner /operator/ to 'clean it up', revert — "
            "the convention is the contract (see C9.1 incident).",
        )


if __name__ == "__main__":
    unittest.main()

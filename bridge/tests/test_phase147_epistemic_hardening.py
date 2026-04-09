"""
Phase 147 — Epistemic Threshold Hardening Tests (8 tests)

Closes Phase 98 W1: epistemic_consensus_threshold=0.60 was exactly reachable by
ClassJDetector alone (class_j_weight=0.40 + supervisor_weight=0.20 = 0.60).
An adversary suppressing triage escalation reduced the 3-agent gate to a 1-agent gate.

Mitigations applied (Phase 147):
1. Default threshold: 0.60 → 0.65 (ClassJ+Supervisor=0.60 < 0.65 → HOLD)
2. Default epistemic_triage_prereq_required: False → True

Tests:
1. epistemic_consensus_threshold default is 0.65 in Config
2. epistemic_triage_prereq_required default is True in Config
3. ClassJ alone (0.40 + Supervisor 0.20 = 0.60) does NOT reach threshold=0.65 → HOLD
4. triage_score=0.0 + prereq=True → proposed_verdict returned unchanged (prereq bypass)
5. triage_score > 0.0 + high consensus (≥ 0.65) → BLOCK confirmed
6. prereq_required=False → consensus runs without prereq; ClassJ+Supervisor=0.60 < 0.65 → HOLD
7. Explicit threshold=0.60 behavior preserved: ClassJ+Supervisor=0.60 >= 0.60 → BLOCK
8. Phase 98 W1 adversarial scenario blocked: new defaults prevent ClassJ-only BLOCK
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vapi_bridge.store import Store


def _make_store() -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p147.db"))


def _make_cfg(**kwargs):
    """Build mock cfg. Does NOT preset epistemic fields — tests control them explicitly."""
    cfg = MagicMock()
    cfg.operator_api_key = "testkey147"
    cfg.rate_limit_per_minute = 10000
    cfg.agent_dry_run_mode = True
    cfg.validation_gate_n = 100
    cfg.validation_max_divergence_rate = 1.0
    cfg.enforcement_cert_ttl_s = 86400
    cfg.epistemic_consensus_enabled = True
    cfg.epistemic_recommended_threshold = 0.65
    cfg.agent_model = "claude-sonnet-4-6"
    cfg.mpc_ceremony_hash_cache = None
    cfg.vhp_contract_address = ""
    cfg.layerzero_endpoint_address = ""
    cfg.warm_up_batch_size = 5
    cfg.stiotx_token_address = ""
    cfg.quicksilver_collateral_address = ""
    cfg.activation_auto_restore = True
    cfg.gsr_enabled = False
    cfg.ioswarm_enabled = False
    cfg.ioswarm_adjudication_enabled = False
    cfg.poad_registry_enabled = False
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


class TestEpistemicPhase147(unittest.TestCase):

    # -------------------------------------------------------------------------
    # Test 1: Config default threshold is 0.65
    # -------------------------------------------------------------------------
    def test_1_config_default_threshold_is_0_65(self):
        """epistemic_consensus_threshold default must be 0.65 (not 0.60) in Config."""
        # Import Config with no environment override for this field
        import importlib
        import vapi_bridge.config as cfg_mod
        cfg_class = cfg_mod.Config
        # Instantiate without any env override
        orig = os.environ.pop("EPISTEMIC_CONSENSUS_THRESHOLD", None)
        try:
            c = cfg_class()
            self.assertAlmostEqual(
                c.epistemic_consensus_threshold, 0.65,
                msg="Default threshold should be 0.65 (Phase 147 hardening)"
            )
        finally:
            if orig is not None:
                os.environ["EPISTEMIC_CONSENSUS_THRESHOLD"] = orig

    # -------------------------------------------------------------------------
    # Test 2: Config default triage_prereq_required is True
    # -------------------------------------------------------------------------
    def test_2_config_default_triage_prereq_required_is_true(self):
        """epistemic_triage_prereq_required default must be True in Config."""
        import vapi_bridge.config as cfg_mod
        orig = os.environ.pop("EPISTEMIC_TRIAGE_PREREQ_REQUIRED", None)
        try:
            c = cfg_mod.Config()
            self.assertTrue(
                c.epistemic_triage_prereq_required,
                "Default triage_prereq_required should be True (Phase 147 hardening)"
            )
        finally:
            if orig is not None:
                os.environ["EPISTEMIC_TRIAGE_PREREQ_REQUIRED"] = orig

    # -------------------------------------------------------------------------
    # Test 3: ClassJ alone 0.60 < threshold 0.65 → HOLD (W1 mitigation confirmed)
    # -------------------------------------------------------------------------
    def test_3_classj_alone_does_not_reach_0_65(self):
        """ClassJ(0.40)+Supervisor(0.20)=0.60 < threshold=0.65 → HOLD when prereq=False."""
        from vapi_bridge.session_adjudicator import SessionAdjudicator
        store = _make_store()

        # Seed class_j HIGH for device, no triage, prereq disabled so consensus runs
        store.insert_class_j_assessment(
            device_id="w1_device_147",
            risk_level="HIGH",
            entropy_variance=0.01,
            window_count=10,
        )
        # Score: ClassJ=0.40*1.0 + Triage=0.40*0.0 + Supervisor=0.20*1.0 = 0.60
        # threshold=0.65 (base, no PMI): 0.60 < 0.65 → HOLD (downgraded)
        cfg = _make_cfg(
            epistemic_consensus_threshold=0.65,
            epistemic_triage_prereq_required=False,  # disable prereq so consensus runs
        )
        sa = SessionAdjudicator(cfg, store)
        result = asyncio.get_event_loop().run_until_complete(
            sa._epistemic_consensus("w1_device_147", "BLOCK")
        )
        self.assertEqual(
            result, "HOLD",
            "ClassJ+Supervisor=0.60 should NOT reach threshold=0.65 → HOLD (W1 closed)"
        )

    # -------------------------------------------------------------------------
    # Test 4: triage_score=0.0 + prereq=True → proposed_verdict unchanged (bypass)
    # -------------------------------------------------------------------------
    def test_4_triage_prereq_true_no_triage_returns_unchanged(self):
        """triage_prereq_required=True + no triage signal → proposed_verdict returned as-is."""
        from vapi_bridge.session_adjudicator import SessionAdjudicator
        store = _make_store()

        store.insert_class_j_assessment(
            device_id="prereq_device_147",
            risk_level="HIGH",
            entropy_variance=0.02,
            window_count=10,
        )
        # prereq=True, no triage escalation → triage_score=0.0 → bypass consensus
        cfg = _make_cfg(
            epistemic_consensus_threshold=0.65,
            epistemic_triage_prereq_required=True,
        )
        sa = SessionAdjudicator(cfg, store)
        result = asyncio.get_event_loop().run_until_complete(
            sa._epistemic_consensus("prereq_device_147", "BLOCK")
        )
        # prereq not met → return proposed_verdict (BLOCK) unchanged
        self.assertEqual(result, "BLOCK")

    # -------------------------------------------------------------------------
    # Test 5: triage_score > 0.0 + consensus ≥ 0.65 → BLOCK confirmed
    # -------------------------------------------------------------------------
    def test_5_with_triage_signal_high_consensus_blocks(self):
        """With triage signal present, consensus ≥ 0.65 → BLOCK confirmed."""
        from vapi_bridge.session_adjudicator import SessionAdjudicator
        from vapi_bridge.divergence_triage_agent import DivergenceTriageAgent
        store = _make_store()
        device = "triage_present_147"

        # Seed class_j HIGH
        store.insert_class_j_assessment(
            device_id=device,
            risk_level="HIGH",
            entropy_variance=0.01,
            window_count=10,
        )
        # Seed triage escalation so triage_score > 0.0
        store.insert_divergence_triage_report(
            device_id=device,
            divergence_count=1,
            escalated=1,
            patterns=str(["ml_bot_cluster"]),
            ml_bot_high_count=2,
            cheat_count=0,
            enrollment_anomaly_count=0,
        )
        # consensus: ClassJ(0.40*1.0) + Triage(0.40*1.0) + Supervisor(0.20*1.0) = 1.00 ≥ 0.65
        cfg = _make_cfg(
            epistemic_consensus_threshold=0.65,
            epistemic_triage_prereq_required=True,
        )
        sa = SessionAdjudicator(cfg, store)
        result = asyncio.get_event_loop().run_until_complete(
            sa._epistemic_consensus(device, "BLOCK")
        )
        self.assertEqual(result, "BLOCK", "High consensus with triage present should BLOCK")

    # -------------------------------------------------------------------------
    # Test 6: prereq=False → consensus runs without prereq check
    # -------------------------------------------------------------------------
    def test_6_prereq_false_consensus_runs_without_prereq(self):
        """With prereq=False, consensus check runs even with no triage signal."""
        from vapi_bridge.session_adjudicator import SessionAdjudicator
        store = _make_store()

        store.insert_class_j_assessment(
            device_id="no_prereq_device_147",
            risk_level="HIGH",
            entropy_variance=0.01,
            window_count=10,
        )
        # prereq=False, threshold=0.65: ClassJ+Supervisor=0.60 < 0.65 → HOLD
        cfg = _make_cfg(
            epistemic_consensus_threshold=0.65,
            epistemic_triage_prereq_required=False,
        )
        sa = SessionAdjudicator(cfg, store)
        result = asyncio.get_event_loop().run_until_complete(
            sa._epistemic_consensus("no_prereq_device_147", "BLOCK")
        )
        self.assertEqual(
            result, "HOLD",
            "prereq=False + threshold=0.65 + no triage: 0.60 < 0.65 → HOLD"
        )

    # -------------------------------------------------------------------------
    # Test 7: Explicit threshold=0.60 preserves old behavior (ClassJ alone → BLOCK)
    # -------------------------------------------------------------------------
    def test_7_explicit_threshold_0_60_preserves_old_behavior(self):
        """Explicit threshold=0.60 + prereq=False: ClassJ+Supervisor=0.60 >= 0.60 → BLOCK."""
        from vapi_bridge.session_adjudicator import SessionAdjudicator
        store = _make_store()

        store.insert_class_j_assessment(
            device_id="old_threshold_device_147",
            risk_level="HIGH",
            entropy_variance=0.01,
            window_count=10,
        )
        # Old behavior: threshold=0.60, prereq=False
        cfg = _make_cfg(
            epistemic_consensus_threshold=0.60,
            epistemic_triage_prereq_required=False,
        )
        sa = SessionAdjudicator(cfg, store)
        result = asyncio.get_event_loop().run_until_complete(
            sa._epistemic_consensus("old_threshold_device_147", "BLOCK")
        )
        # ClassJ+Supervisor=0.60 >= 0.60 → BLOCK (old Phase 98 behavior)
        self.assertEqual(result, "BLOCK", "Explicit 0.60 threshold should preserve old BLOCK behavior")

    # -------------------------------------------------------------------------
    # Test 8: Phase 98 W1 adversarial scenario blocked by new defaults
    # -------------------------------------------------------------------------
    def test_8_phase98_w1_adversarial_scenario_blocked(self):
        """Phase 98 W1 scenario: adversary suppresses triage. New defaults prevent ClassJ-only BLOCK.

        W1 scenario: ClassJ HIGH, no triage escalation.
        Old behavior (threshold=0.60, prereq=False): ClassJ+Supervisor=0.60 >= 0.60 → BLOCK
        New behavior (threshold=0.65, prereq=False): ClassJ+Supervisor=0.60 < 0.65 → HOLD
        """
        from vapi_bridge.session_adjudicator import SessionAdjudicator
        store = _make_store()

        store.insert_class_j_assessment(
            device_id="adversary_device_147",
            risk_level="HIGH",
            entropy_variance=0.01,
            window_count=10,
        )
        # Verify old threshold=0.60 WOULD have BLOCK'd (W1 confirmed)
        cfg_old = _make_cfg(epistemic_consensus_threshold=0.60, epistemic_triage_prereq_required=False)
        sa_old = SessionAdjudicator(cfg_old, store)
        old_result = asyncio.get_event_loop().run_until_complete(
            sa_old._epistemic_consensus("adversary_device_147", "BLOCK")
        )
        self.assertEqual(old_result, "BLOCK", "Old threshold=0.60 should BLOCK (W1 confirmed)")

        # Verify new threshold=0.65 prevents the BLOCK (W1 closed)
        cfg_new = _make_cfg(epistemic_consensus_threshold=0.65, epistemic_triage_prereq_required=False)
        sa_new = SessionAdjudicator(cfg_new, store)
        new_result = asyncio.get_event_loop().run_until_complete(
            sa_new._epistemic_consensus("adversary_device_147", "BLOCK")
        )
        self.assertEqual(new_result, "HOLD", "New threshold=0.65 should downgrade to HOLD (W1 closed)")

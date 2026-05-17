"""
Tests for CoherenceRuleLoader — VAPI-EXT Step 4.

15+ tests covering:
  - load_all() returns exactly 39 VAPI_CORE rules
  - category counts: CONTRADICTION=29, ORPHAN=7, INVERSION=5
  - guard lambdas preserved (IOSWARM_ACTIVE_NO_ADJUDICATIONS has guard != None)
  - inject_rules() adds to FSCA's runtime dicts
  - injected rules appear in load_all()
  - scan_and_load_plugins() ignores vapi_core_rules
  - reset between tests
"""
from __future__ import annotations

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.coherence_rules.base import CoherenceRule
from vapi_bridge.coherence_rules.loader import CoherenceRuleLoader
from vapi_bridge.fleet_signal_coherence_agent import (
    CONTRADICTION_RULES,
    ORPHAN_RULES,
    INVERSION_RULES,
)


# ---------------------------------------------------------------------------
# Fixture: reset loader between tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_loader():
    CoherenceRuleLoader._reset()
    yield
    CoherenceRuleLoader._reset()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ext_rule(name: str = "EXT_TEST_RULE", category: str = "CONTRADICTION") -> CoherenceRule:
    return CoherenceRule(
        name=name,
        category=category,
        severity="LOW",
        agents_involved=["TestAgent"],
        explanation="Test external rule explanation.",
        resolution="Test resolution.",
        rule_dict={
            "query": "SELECT 1",
            "params": lambda cfg: (),
        },
        guard=None,
        sub_protocol="TEST_PROTO",
        phase_introduced=999,
    )


# ---------------------------------------------------------------------------
# T-EXT-RULE-1: load_all() returns all 39 VAPI_CORE rules
# ---------------------------------------------------------------------------

class TestLoadAll:
    def test_load_all_returns_18_rules(self):
        # 41 → 40 on 2026-05-16 (H-1 Option B dropped VPM_MANIFEST_HASH_DRIFT
        # from CONTRADICTION category). 40 → 41 on 2026-05-17 (STABILITY-9
        # stage 4b added DETECTOR_SILENT_24H_AFTER_DIVERGENCE to ORPHAN —
        # Q3 deliverable). Total = 28 CONTRADICTION + 8 ORPHAN + 5 INVERSION.
        rules = CoherenceRuleLoader.load_all()
        assert len(rules) == 41, f"Expected 41 rules, got {len(rules)}"

    def test_contradiction_count(self):
        # 29 → 28 on 2026-05-16 (H-1 Option B dropped VPM_MANIFEST_HASH_DRIFT).
        rules = CoherenceRuleLoader.load_all()
        contradictions = [r for r in rules if r.category == "CONTRADICTION"]
        assert len(contradictions) == 28, f"Expected 28 CONTRADICTION rules, got {len(contradictions)}"

    def test_orphan_count(self):
        # Stage 4b 2026-05-17: +DETECTOR_SILENT_24H_AFTER_DIVERGENCE → 8
        rules = CoherenceRuleLoader.load_all()
        orphans = [r for r in rules if r.category == "ORPHAN"]
        assert len(orphans) == 8, f"Expected 8 ORPHAN rules, got {len(orphans)}"

    def test_inversion_count(self):
        rules = CoherenceRuleLoader.load_all()
        inversions = [r for r in rules if r.category == "INVERSION"]
        assert len(inversions) == 5, f"Expected 5 INVERSION rules, got {len(inversions)}"

    def test_all_rules_are_coherence_rule_instances(self):
        rules = CoherenceRuleLoader.load_all()
        for r in rules:
            assert isinstance(r, CoherenceRule), f"Expected CoherenceRule, got {type(r)}"

    def test_all_rules_have_names(self):
        rules = CoherenceRuleLoader.load_all()
        for r in rules:
            assert r.name and isinstance(r.name, str)

    def test_all_rules_have_vapi_core_sub_protocol(self):
        rules = CoherenceRuleLoader.load_all()
        for r in rules:
            assert r.sub_protocol == "VAPI_CORE"


# ---------------------------------------------------------------------------
# T-EXT-RULE-2: Guard mechanism preservation (Phase 204 innovation)
# ---------------------------------------------------------------------------

class TestGuardPreservation:
    def test_at_least_one_rule_has_guard(self):
        rules = CoherenceRuleLoader.load_all()
        rules_with_guard = [r for r in rules if r.guard is not None]
        assert len(rules_with_guard) >= 1, "No rules with guard found — Phase 204 guard mechanism not preserved"

    def test_ioswarm_rule_has_guard(self):
        rules = CoherenceRuleLoader.load_all()
        ioswarm_rules = [r for r in rules if r.name == "IOSWARM_ACTIVE_NO_ADJUDICATIONS"]
        assert len(ioswarm_rules) == 1, "IOSWARM_ACTIVE_NO_ADJUDICATIONS not found"
        rule = ioswarm_rules[0]
        assert rule.guard is not None, "IOSWARM_ACTIVE_NO_ADJUDICATIONS guard is None — Phase 204 regression"

    def test_ioswarm_guard_callable(self):
        rules = CoherenceRuleLoader.load_all()
        rule = next(r for r in rules if r.name == "IOSWARM_ACTIVE_NO_ADJUDICATIONS")
        # Guard must be callable
        assert callable(rule.guard)

    def test_ioswarm_guard_returns_false_when_disabled(self):
        rules = CoherenceRuleLoader.load_all()
        rule = next(r for r in rules if r.name == "IOSWARM_ACTIVE_NO_ADJUDICATIONS")
        cfg = type("C", (), {
            "ioswarm_enabled": False,
            "ioswarm_adjudication_enabled": False,
        })()
        assert rule.guard(cfg) is False

    def test_ioswarm_guard_returns_true_when_enabled(self):
        rules = CoherenceRuleLoader.load_all()
        rule = next(r for r in rules if r.name == "IOSWARM_ACTIVE_NO_ADJUDICATIONS")
        cfg = type("C", (), {
            "ioswarm_enabled": True,
            "ioswarm_adjudication_enabled": True,
        })()
        assert rule.guard(cfg) is True

    def test_most_rules_have_no_guard(self):
        rules = CoherenceRuleLoader.load_all()
        rules_without_guard = [r for r in rules if r.guard is None]
        # Only 1 rule (IOSWARM_ACTIVE_NO_ADJUDICATIONS) has a guard; 40 should not
        # (39 → 40 on 2026-05-17 after STABILITY-9 stage 4b added
        # DETECTOR_SILENT_24H_AFTER_DIVERGENCE).
        assert len(rules_without_guard) == 40


# ---------------------------------------------------------------------------
# T-EXT-RULE-3: inject_rules() and FSCA runtime dict mutation
# ---------------------------------------------------------------------------

class TestInjectRules:
    def test_inject_contradiction_rule(self):
        rule = _make_ext_rule("EXT_CONTRADICTION", "CONTRADICTION")
        CoherenceRuleLoader.inject_rules([rule])
        assert "EXT_CONTRADICTION" in CONTRADICTION_RULES

    def test_inject_orphan_rule(self):
        rule = _make_ext_rule("EXT_ORPHAN", "ORPHAN")
        CoherenceRuleLoader.inject_rules([rule])
        assert "EXT_ORPHAN" in ORPHAN_RULES

    def test_inject_inversion_rule(self):
        rule = _make_ext_rule("EXT_INVERSION", "INVERSION")
        CoherenceRuleLoader.inject_rules([rule])
        assert "EXT_INVERSION" in INVERSION_RULES

    def test_injected_rule_appears_in_load_all(self):
        rule = _make_ext_rule()
        CoherenceRuleLoader.inject_rules([rule])
        all_rules = CoherenceRuleLoader.load_all()
        assert any(r.name == "EXT_TEST_RULE" for r in all_rules)

    def test_load_all_returns_18_plus_injected(self):  # noqa: D — count is now 41+1=42 after STABILITY-9 stage 4b
        rule = _make_ext_rule()
        CoherenceRuleLoader.inject_rules([rule])
        all_rules = CoherenceRuleLoader.load_all()
        # 41 core (40 + Stage 4b DETECTOR_SILENT_24H_AFTER_DIVERGENCE) + 1 injected
        assert len(all_rules) == 42

    def test_inject_rule_with_guard_preserved_in_fsca_dict(self):
        guard_fn = lambda cfg: getattr(cfg, "test_flag", False)
        rule = CoherenceRule(
            name="EXT_WITH_GUARD",
            category="CONTRADICTION",
            severity="LOW",
            agents_involved=["TestAgent"],
            explanation="Test guard rule.",
            resolution="Fix it.",
            rule_dict={"query": "SELECT 1", "params": lambda cfg: ()},
            guard=guard_fn,
            sub_protocol="TEST_PROTO",
        )
        CoherenceRuleLoader.inject_rules([rule])
        assert "EXT_WITH_GUARD" in CONTRADICTION_RULES
        assert CONTRADICTION_RULES["EXT_WITH_GUARD"].get("guard") is guard_fn

    def test_inject_same_rule_twice_is_idempotent(self):
        rule = _make_ext_rule()
        CoherenceRuleLoader.inject_rules([rule])
        CoherenceRuleLoader.inject_rules([rule])
        assert CONTRADICTION_RULES.get("EXT_TEST_RULE") is not None
        # Should only be injected once
        assert len([r for r in CoherenceRuleLoader._injected if r.name == "EXT_TEST_RULE"]) == 1


# ---------------------------------------------------------------------------
# T-EXT-RULE-4: reset cleans up injected rules
# ---------------------------------------------------------------------------

class TestReset:
    def test_reset_clears_injected_rules(self):
        rule = _make_ext_rule()
        CoherenceRuleLoader.inject_rules([rule])
        assert len(CoherenceRuleLoader._injected) == 1
        CoherenceRuleLoader._reset()
        assert len(CoherenceRuleLoader._injected) == 0

    def test_reset_leaves_core_rules_intact(self):
        CoherenceRuleLoader._reset()
        # VAPI_CORE rules are hardcoded in FSCA — reset doesn't affect them
        assert "TTL_COMMITTED_AT_MISMATCH" in CONTRADICTION_RULES
        assert "PERSONA_BREAK_UNATTESTED" in ORPHAN_RULES
        assert "CONTEXT_HASH_MISMATCH" in INVERSION_RULES

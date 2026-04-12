"""
CoherenceRuleLoader — VAPI-EXT Phase 204+

Plugin loader for FleetSignalCoherenceAgent coherence rules.

Sub-protocols add rules by:
  1. Dropping a `*_rules.py` file in bridge/vapi_bridge/coherence_rules/
  2. The file must define a `RULES: list[CoherenceRule]` variable.
  3. Calling CoherenceRuleLoader.inject_rules(RULES) at sub-protocol startup.

Injected rules are added to FleetSignalCoherenceAgent's runtime dicts
(CONTRADICTION_RULES, ORPHAN_RULES, INVERSION_RULES) — FSCA picks them up
on the next poll cycle without any further modification to FSCA.

VAPI_CORE rules are already hardcoded in FSCA — inject_rules() is for
sub-protocol rules only. load_all() returns ALL rules (core + injected).

The guard mechanism from Phase 204 is fully preserved: CoherenceRule.guard
is passed through to FSCA's _check_contradictions() via the rule_dict's
"guard" key. Discarding it would be a regression.
"""
from __future__ import annotations

import importlib
import logging
import pkgutil
from pathlib import Path
from typing import Optional

from .base import CoherenceRule

log = logging.getLogger(__name__)

_RULES_DIR = Path(__file__).parent  # bridge/vapi_bridge/coherence_rules/


class CoherenceRuleLoader:
    """Plugin loader for FleetSignalCoherenceAgent coherence rules.

    Usage:
        # Get all 18 VAPI_CORE rules:
        rules = CoherenceRuleLoader.load_all()

        # Sub-protocol adds rules:
        CoherenceRuleLoader.inject_rules(PRAGMA_JUDGE_RULES)

        # FSCA picks up sub-protocol rules automatically on next cycle.
    """

    # Sub-protocol rules injected at runtime via inject_rules()
    _injected: list[CoherenceRule] = []

    @classmethod
    def load_all(cls) -> list[CoherenceRule]:
        """Return all coherence rules: VAPI_CORE (18) + any injected sub-protocol rules.

        Loads VAPI_CORE rules from vapi_core_rules.py. Includes injected rules.
        """
        from .vapi_core_rules import RULES as VAPI_CORE_RULES
        return list(VAPI_CORE_RULES) + list(cls._injected)

    @classmethod
    def inject_rules(cls, rules: list[CoherenceRule]) -> None:
        """Inject sub-protocol rules into FleetSignalCoherenceAgent's runtime dicts.

        Rules are added to the CONTRADICTION_RULES / ORPHAN_RULES / INVERSION_RULES
        module-level dicts in fleet_signal_coherence_agent.py. FSCA iterates over
        these dicts at runtime — it picks up new rules on the next poll cycle with
        zero FSCA modification.

        Also stores them in _injected so load_all() can return the full set.

        Guard lambdas are preserved: rule.guard is stored as rule_dict["guard"]
        so FSCA's existing guard support in _check_contradictions() handles it.
        """
        from .. import fleet_signal_coherence_agent as _fsca

        for rule in rules:
            if rule.category == "CONTRADICTION":
                target_dict = _fsca.CONTRADICTION_RULES
            elif rule.category == "ORPHAN":
                target_dict = _fsca.ORPHAN_RULES
            elif rule.category == "INVERSION":
                target_dict = _fsca.INVERSION_RULES
            else:
                log.warning(
                    "CoherenceRuleLoader: unknown category '%s' for rule '%s' — skipped",
                    rule.category, rule.name,
                )
                continue

            if rule.name in target_dict:
                log.debug(
                    "CoherenceRuleLoader: rule '%s' already registered — skipped", rule.name
                )
                continue

            # Build rule dict compatible with FSCA's existing detection methods.
            # Critically: preserve guard lambda so FSCA's guard check fires correctly.
            rule_dict = dict(rule.rule_dict)  # shallow copy
            if rule.guard is not None:
                rule_dict["guard"] = rule.guard

            target_dict[rule.name] = rule_dict
            log.info(
                "CoherenceRuleLoader: injected '%s' (%s) from sub-protocol '%s'",
                rule.name, rule.category, rule.sub_protocol,
            )
            # Track in _injected (only if not already present — idempotent)
            if not any(r.name == rule.name for r in cls._injected):
                cls._injected.append(rule)

    @classmethod
    def get_external_rules(
        cls,
        category: Optional[str] = None,
    ) -> list[CoherenceRule]:
        """Return only injected (sub-protocol) rules, optionally filtered by category."""
        if category is None:
            return list(cls._injected)
        return [r for r in cls._injected if r.category == category]

    @classmethod
    def _reset(cls) -> None:
        """Test-only helper: clear injected rules and remove them from FSCA dicts."""
        from .. import fleet_signal_coherence_agent as _fsca
        for rule in cls._injected:
            if rule.category == "CONTRADICTION":
                _fsca.CONTRADICTION_RULES.pop(rule.name, None)
            elif rule.category == "ORPHAN":
                _fsca.ORPHAN_RULES.pop(rule.name, None)
            elif rule.category == "INVERSION":
                _fsca.INVERSION_RULES.pop(rule.name, None)
        cls._injected.clear()

    @classmethod
    def scan_and_load_plugins(cls) -> list[str]:
        """Discover and load all *_rules.py files in coherence_rules/ (except vapi_core_rules).

        Each file must define a `RULES: list[CoherenceRule]` variable.
        Returns the list of module names that were loaded.
        """
        loaded: list[str] = []
        for finder, modname, ispkg in pkgutil.iter_modules([str(_RULES_DIR)]):
            if not modname.endswith("_rules") or modname == "vapi_core_rules":
                continue
            full_name = f"vapi_bridge.coherence_rules.{modname}"
            try:
                mod = importlib.import_module(full_name)
                rules = getattr(mod, "RULES", None)
                if rules is None:
                    log.warning(
                        "CoherenceRuleLoader: '%s' has no RULES variable — skipped",
                        full_name,
                    )
                    continue
                cls.inject_rules(rules)
                loaded.append(full_name)
                log.info("CoherenceRuleLoader: loaded plugin '%s' (%d rules)", full_name, len(rules))
            except Exception as exc:
                log.error(
                    "CoherenceRuleLoader: failed to load plugin '%s': %s",
                    full_name, exc,
                )
        return loaded

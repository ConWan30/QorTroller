"""
CoherenceRule dataclass — VAPI-EXT Phase 204+

A plugin-loadable rule for FleetSignalCoherenceAgent. Sub-protocols drop a
`*_rules.py` file in bridge/vapi_bridge/coherence_rules/ containing a
`RULES: list[CoherenceRule]` variable. CoherenceRuleLoader picks them up.

The `guard` field preserves Phase 204's config-gated rule innovation: a
lambda that returns False will skip the rule entirely for the current config.
This is architecturally necessary for rules that should only fire under
specific runtime conditions (e.g., IOSWARM_ACTIVE_NO_ADJUDICATIONS only
fires when ioswarm_enabled=True AND ioswarm_adjudication_enabled=True).
"""
from __future__ import annotations

import dataclasses
from typing import Callable, Optional


@dataclasses.dataclass
class CoherenceRule:
    """Descriptor for a FleetSignalCoherenceAgent detection rule.

    Fields:
        name             — globally unique rule identifier (e.g., "IOSWARM_ACTIVE_NO_ADJUDICATIONS")
        category         — "CONTRADICTION", "ORPHAN", or "INVERSION"
        severity         — "CRITICAL", "HIGH", "MEDIUM", or "LOW"
        agents_involved  — list of agent names relevant to this rule
        explanation      — human-readable description of the failure mode
        resolution       — recommended remediation steps
        rule_dict        — the original rule dict used by FSCA (query/params/post_check/etc.)
        guard            — optional config-gating lambda: (cfg) → bool
                           If guard(cfg) returns False, the rule is skipped.
                           None = always active (default, backward compatible).
                           Preserves Phase 204's IOSWARM_ACTIVE_NO_ADJUDICATIONS innovation.
        evaluate         — optional callable for direct rule evaluation by sub-protocol agents.
                           VAPI_CORE rules leave this as None (FSCA handles evaluation natively).
        sub_protocol     — owning sub-protocol ("VAPI_CORE" for all baseline rules)
        phase_introduced — VAPI phase that added this rule
    """
    name: str
    category: str                    # "CONTRADICTION", "ORPHAN", "INVERSION"
    severity: str
    agents_involved: list
    explanation: str
    resolution: str
    rule_dict: dict                  # original FSCA rule dict — preserved for FSCA native execution
    guard: Optional[Callable] = None  # Phase 204 innovation — None = always active
    evaluate: Optional[Callable] = None  # optional sub-protocol callable
    sub_protocol: str = "VAPI_CORE"
    phase_introduced: int = 193

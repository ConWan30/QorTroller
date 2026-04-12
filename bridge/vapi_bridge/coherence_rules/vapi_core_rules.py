"""
VAPI_CORE coherence rules — VAPI-EXT Phase 204+

Wraps all 18 existing FleetSignalCoherenceAgent rules into CoherenceRule objects.
This module makes the VAPI_CORE rule set loadable by CoherenceRuleLoader without
duplicating rule logic — it imports directly from fleet_signal_coherence_agent.py.

Rule counts (Phase 204):
  CONTRADICTION: 8 rules
  ORPHAN:        6 rules
  INVERSION:     4 rules
  TOTAL:        18 rules

Sub-protocols add their own rules via separate *_rules.py files.
"""
from __future__ import annotations

from .base import CoherenceRule

# Import directly from FSCA to avoid any duplication. The rule dicts in FSCA
# remain the single source of truth for rule logic. This module only wraps them.
from ..fleet_signal_coherence_agent import (
    CONTRADICTION_RULES,
    ORPHAN_RULES,
    INVERSION_RULES,
)

# ---------------------------------------------------------------------------
# Phase numbers per category (matches phase history in CLAUDE.md)
# ---------------------------------------------------------------------------

_CONTRADICTION_PHASES: dict[str, int] = {
    "TTL_COMMITTED_AT_MISMATCH":               178,
    "DEFENSIBILITY_N_MISMATCH":                193,
    "CEREMONY_PARTICIPANT_MISMATCH":           193,
    "MATURITY_ELEVATION_READINESS_INVERSION":  193,
    "RENEWAL_WITHOUT_ATTESTATION":             193,
    "PERSONA_BREAK_ENROLLMENT_CONFLICT":       193,
    "SEPARATION_GATE_ACTIVATION_CONFLICT":     193,
    "IOSWARM_ACTIVE_NO_ADJUDICATIONS":         204,
}

_ORPHAN_PHASES: dict[str, int] = {
    "PERSONA_BREAK_UNATTESTED":             193,
    "MATURITY_ELEVATION_UNACKNOWLEDGED":    193,
    "BIOMETRIC_EXPIRED_GATE_NOT_UPDATED":   193,
    "ERASURE_CERT_NOT_ANCHORED":            193,
    "CORPUS_ENTROPY_WARNING_NO_AUTORESEARCH": 193,
    "RATIO_VELOCITY_NEGATIVE":              202,
}

_INVERSION_PHASES: dict[str, int] = {
    "COMMITMENT_PREDATES_CONSENT":    193,
    "BADGE_WITHOUT_RENEWAL_PARENT":   193,
    "RULING_PREDATES_CALIBRATION":    193,
    "CONTEXT_HASH_MISMATCH":          203,
}


def _wrap_contradiction(name: str, rule: dict) -> CoherenceRule:
    return CoherenceRule(
        name=name,
        category="CONTRADICTION",
        severity=rule["severity"],
        agents_involved=rule["agents_involved"],
        explanation=rule["explanation"],
        resolution=rule["resolution"],
        rule_dict=rule,
        guard=rule.get("guard"),       # Preserves Phase 204 guard mechanism
        evaluate=None,                 # FSCA handles CONTRADICTION evaluation natively
        sub_protocol="VAPI_CORE",
        phase_introduced=_CONTRADICTION_PHASES.get(name, 193),
    )


def _wrap_orphan(name: str, rule: dict) -> CoherenceRule:
    return CoherenceRule(
        name=name,
        category="ORPHAN",
        severity=rule["severity"],
        agents_involved=[rule.get("trigger_agent", ""), rule.get("response_agent", "")],
        explanation=rule["explanation"],
        resolution=rule["resolution"],
        rule_dict=rule,
        guard=rule.get("guard"),       # Most ORPHAN rules have no guard
        evaluate=None,
        sub_protocol="VAPI_CORE",
        phase_introduced=_ORPHAN_PHASES.get(name, 193),
    )


def _wrap_inversion(name: str, rule: dict) -> CoherenceRule:
    return CoherenceRule(
        name=name,
        category="INVERSION",
        severity=rule["severity"],
        agents_involved=rule["agents_involved"],
        explanation=rule["explanation"],
        resolution=rule["resolution"],
        rule_dict=rule,
        guard=rule.get("guard"),       # Most INVERSION rules have no guard
        evaluate=None,
        sub_protocol="VAPI_CORE",
        phase_introduced=_INVERSION_PHASES.get(name, 193),
    )


# ---------------------------------------------------------------------------
# RULES — all 18 VAPI_CORE CoherenceRule objects
# ---------------------------------------------------------------------------

RULES: list[CoherenceRule] = (
    [_wrap_contradiction(name, rule) for name, rule in CONTRADICTION_RULES.items()]
    + [_wrap_orphan(name, rule) for name, rule in ORPHAN_RULES.items()]
    + [_wrap_inversion(name, rule) for name, rule in INVERSION_RULES.items()]
)

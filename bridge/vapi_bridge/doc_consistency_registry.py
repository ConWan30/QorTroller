"""Canonical fact registry for document consistency audits.

Born 2026-05-19 from the WP v6 verification arc (commits 1b186dd2 →
d8a7045f → 7eacd1a6). Each registry entry tracks:
  - canonical fact name
  - current canonical value
  - superseded values (older values that should NOT appear in current
    documents — any match = stale residual)
  - verification command (how an evaluator can independently verify
    the canonical value from disk / chain / source code)
  - target document globs (which documents are checked for residuals)

The mythos_doc_number_consistency variant scans the target documents
for any occurrence of a superseded value and surfaces it as a MEDIUM
finding. This catches the asymmetric-update failure mode where a fact
updates in one register but stale residuals persist in others.

Discipline:
  - Add a new entry to REGISTRY when a canonical numeric fact changes
  - Add ALL prior values to superseded_values (not just the immediately
    previous one) so the registry traces full drift history
  - Never remove an entry — superseded values are forever drift candidates
  - Patterns should match the fact's BARE numeric occurrence; the variant
    handles context-checking to suppress false positives (e.g., "267"
    inside a date-like timestamp is not a stale corpus count)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True, slots=True)
class CanonicalFact:
    name: str
    current_value: str
    superseded_values: tuple[str, ...]
    verification_command: str
    target_doc_globs: tuple[str, ...]
    context_hints: tuple[str, ...] = field(default_factory=tuple)
    # Optional context substring that must appear in the matched line for
    # the match to count as a positive hit. Without context_hints, ANY
    # occurrence of a superseded value in a target document is flagged.
    exclusion_substrings: tuple[str, ...] = field(default_factory=tuple)
    # Optional exclusion substrings — if the matched line contains any of
    # these, the match is SKIPPED (treated as a false positive). Used to
    # exclude pedagogical references to deprecated values OR byte-count
    # contexts where a number coincidentally matches a corpus value.


# ──────────────────────────────────────────────────────────────────────
# Registry — seed entries from WP v6 verification arc.
# Each entry traces a fact that the verification-first discipline
# established has drifted historically + the discipline checks it
# continuously for re-drift.
# ──────────────────────────────────────────────────────────────────────

REGISTRY: list[CanonicalFact] = [
    # ─── WP v6 verification-arc lineage ──────────────────────────────
    CanonicalFact(
        name="terminal_calibration_corpus_total",
        current_value="267",
        superseded_values=("217", "153"),
        verification_command="ls sessions/human/terminal_cal_P*/*.json | wc -l",
        target_doc_globs=(
            "docs/qortroller-whitepaper-v6.md",
            "docs/qortroller-state-of-the-protocol-2026-05-19.md",
        ),
        # Context: "session" or "corpus" or "physical" near the number
        # catches the relevant references; standalone "217" elsewhere
        # (e.g., a date, a block number) won't be flagged
        context_hints=("session", "corpus", "physical", "terminal_cal"),
        # Exclude lines that intentionally reference the historical value
        # as a transparency marker (showing the drift to the reader
        # rather than silently correcting it). Same discipline as the
        # "12 primitives" exclusion: pedagogical drift-disclosure is
        # NOT a stale residual to flag.
        exclusion_substrings=(
            "historical pre-growth",
            "pre-WP-v6 reconciliation",
            "pre-reconciliation",
            "historical narrative",
            "drift history",
        ),
    ),
    CanonicalFact(
        name="hw_threshold_calibration_baseline_n",
        current_value="74",
        superseded_values=(),  # No prior values yet; future regressions tracked
        verification_command="ls sessions/human/hw_*.json | wc -l",
        target_doc_globs=(
            "docs/qortroller-whitepaper-v6.md",
            "docs/qortroller-state-of-the-protocol-2026-05-19.md",
        ),
        context_hints=("threshold", "Phase 57", "hw_*", "hardware calibration"),
    ),
    CanonicalFact(
        name="ait_separation_corpus_n",
        current_value="37",
        superseded_values=("24",),  # Pre-Phase-231 baseline
        verification_command="ls sessions/human/terminal_cal_P*/ait_*.json | wc -l",
        target_doc_globs=(
            "docs/qortroller-whitepaper-v6.md",
            "docs/qortroller-state-of-the-protocol-2026-05-19.md",
        ),
        context_hints=("AIT", "Active Isometric Trigger", "all-pairs"),
        # Exclude lines where '24' appears as a byte count or enum value
        # rather than the AIT corpus N. The ZKBA preimage discussion at
        # WP v6 §4.2 mentions "ZKBAClass ... AIT=1 ... total 24 + n×32
        # bytes" which trips both AIT context AND number match but is
        # clearly a byte-structure reference, not a corpus N.
        exclusion_substrings=(
            "byte", "bytes", "ZKBAClass", "n_components", "preimage",
        ),
    ),
    CanonicalFact(
        name="frozen_v1_commitment_family_count",
        # 2026-06-13 (HWFL-1 doc-consistency audit): KNOWN THREE-WAY DISCREPANCY,
        # intentionally left at "12" and surfaced for the operator — do NOT auto-bump.
        # Three different numbers are in play and they do NOT agree:
        #   (a) registry current_value = "12"  (this fact; pinned by test T-FREEZE-5)
        #   (b) code frozenset mythos_variants._PATTERN_017_FROZEN_TAGS = 13 entries
        #       (test T-FREEZE-4 asserts 12 and is ALREADY FAILING on a clean tree —
        #        a pre-existing failure independent of this audit)
        #   (c) CLAUDE.md/README narrative count = 14 (counts VAPI-CONSENT-v1 #13 +
        #       VAPI-TEMPORAL-BEACON-v1 #14 as FROZEN primitives)
        # The frozenset is governance-locked by INV-MYTHOS-FAMILIES-001 (crypto-drift
        # SCANNER set), so reconciling 12 vs 13 vs 14 is an operator/governance call:
        # likely (1) fix T-FREEZE-4 to match the real frozenset size, then (2) decide
        # whether the scanner set should track the documented family count or split
        # this fact into scanner_set vs documented_families. Surfaced, NOT auto-
        # resolved — silently editing any of the three would mask a governance gap.
        current_value="12",
        superseded_values=("11", "10"),  # "11" pre-O3-SUPERSEDE; "10" pre-PHYSICAL-DATA-ATTESTATION
        verification_command=(
            "Count of PATTERN-017 commitment-family entries — see WP v6 §4.1"
        ),
        target_doc_globs=(
            "docs/qortroller-whitepaper-v6.md",
            "docs/qortroller-state-of-the-protocol-2026-05-19.md",
        ),
        context_hints=(
            "commitment-family",
            "PATTERN-017",
            "FROZEN-v1 primitives",
            "FROZEN-v1 cryptographic primitives",
        ),
        # WP v6 §4.1 intentionally discusses the deprecated "12 primitives"
        # framing as a pedagogical correction. These lines should NOT fire
        # as drift findings — the document is using the deprecated value
        # to TEACH the precision, not to claim it.
        exclusion_substrings=(
            "would conflate",
            "flat statement",
            "R3 refinement",
            "operator's R3",
            "deprecated",
        ),
    ),
    CanonicalFact(
        name="bridge_test_count",
        # 2026-06-13 (HWFL-1 doc-consistency audit): STALE but NOT auto-corrected.
        # Sensor A v0.2 measured `pytest --collect-only` = 4712 (Cycle 12), which is
        # the COLLECTED ceiling, a different metric from this entry's PASSING count
        # (verification_command below). Refreshing this to the true passing count
        # needs a full bridge suite run (slow + Windows-flaky); deferred to a session
        # that runs the suite. "4377" is left as the last-known passing value but is
        # known-low by ~300+ vs the current collected count.
        current_value="4377",
        superseded_values=("4368", "4356", "4348", "4345", "4337", "4330"),
        verification_command="python -m pytest bridge/tests/ -q 2>&1 | tail -1",
        target_doc_globs=(
            "docs/qortroller-whitepaper-v6.md",
            "docs/qortroller-state-of-the-protocol-2026-05-19.md",
        ),
        context_hints=("bridge test", "bridge tests", "passing bridge"),
    ),
    CanonicalFact(
        name="mythos_variant_count",
        current_value="17",  # 2026-06-13 (HWFL-1 doc-consistency audit): grep -c '^async def mythos_' = 17. Variants #15 mythos_agent_utility_honesty + #16 mythos_path_a_spec_impl_parity (Sensor A v0.1) + a 17th landed since the registry last read "14".
        superseded_values=("16", "15", "14", "13", "12"),  # "11"/"10" omitted: "11" collides with
                                          # commitment-family primitive count name-namespace
                                          # so any line with both "Mythos audit" context AND
                                          # "11" can be a primitive reference, not a variant count
        verification_command=(
            "grep -c '^async def mythos_' bridge/vapi_bridge/mythos_variants.py"
        ),
        target_doc_globs=(
            "docs/qortroller-state-of-the-protocol-2026-05-19.md",
            "docs/qortroller-whitepaper-v6.md",
        ),
        context_hints=("Mythos variant", "Mythos guardrail", "Mythos audit"),
        # Exclude lines where the matched number is in a primitive-count context
        # (cross-context collision with "11 commitment-family" + "14 Mythos" on
        # same line). The abstract at WP v6 §Abstract cites both numbers
        # legitimately; flag only when "Mythos" context is the proximate one.
        exclusion_substrings=(
            "commitment-family",
            "POSEIDON",
            "PV-CI invariants, 14 Mythos",  # full abstract pattern post-update
        ),
    ),
    CanonicalFact(
        name="autonomous_agent_fleet_count",
        # Post-STABILITY-9 steward absorption (operator_steward_absorbed_agents.py
        # + agent_rationalization_v1.md): 9 formerly-standalone agents fold into
        # the 3 Operator Initiative stewards (Sentry 4 / Guardian 4 / Curator 1)
        # and run as steward-invoked skills. The _AGENT_IDS roster stays 38 (the
        # absorbed agents keep their registered IDs); the documented OPERATIONAL
        # fleet is "29 standalone + 3 stewards". Operator directive 2026-05-20:
        # no doc may claim "38 [autonomous] agents" as the live fleet size.
        current_value="29 standalone + 3 stewards (9 absorbed)",
        superseded_values=("38", "36", "35"),
        verification_command=(
            "python -c \"import sys; sys.path.insert(0,'bridge'); "
            "from vapi_bridge.protocol_coherence_agent import _AGENT_IDS; "
            "from vapi_bridge.operator_steward_absorbed_agents import "
            "SENTRY_ABSORBED, GUARDIAN_ABSORBED, CURATOR_ABSORBED; "
            "print('roster', len(_AGENT_IDS), 'absorbed', "
            "len(SENTRY_ABSORBED)+len(GUARDIAN_ABSORBED)+len(CURATOR_ABSORBED))\""
        ),
        target_doc_globs=(
            "docs/qortroller-whitepaper-v6.md",
            "docs/qortroller-state-of-the-protocol-2026-05-19.md",
            "README.md",
        ),
        # Only flag fleet-SIZE claims. The number must sit in an agent-fleet
        # context for a match to count.
        context_hints=(
            "autonomous agent", "agent fleet", "agents on", "standalone agent",
            "agent modules", "Hosts", "-agent fleet", "-agent asyncio",
        ),
        # Roster-index references ("agent #38", "slot #38"), the on-chain Merkle
        # leaf count ("38 leaves"), _AGENT_IDS growth rows, and historical phase
        # records legitimately carry these numbers and are NOT stale fleet-size
        # claims. Byte/block contexts excluded too.
        exclusion_substrings=(
            "#38", "#36", "#35", "leaves", "_AGENT_IDS", "Merkle", "slot",
            "block", "0x", "byte", "historical", "Phase 22", "Phase 23",
        ),
    ),
    CanonicalFact(
        name="mcp_tool_count",
        current_value="40",  # 2026-06-13 (HWFL-1 doc-consistency audit): grep -c '@tool(' vapi-mcp/unified_server.py = 40, up from the registry's stale "31".
        superseded_values=("31", "30", "29", "28", "27"),
        verification_command=(
            "grep -c '@tool(' vapi-mcp/unified_server.py"
        ),
        target_doc_globs=(
            "docs/qortroller-state-of-the-protocol-2026-05-19.md",
        ),
        context_hints=("MCP tool", "Tool #"),
    ),
    CanonicalFact(
        name="qortroller_commitment_family_count",
        # 2026-05-24 Phase B freeze ceremony: count of QORTROLLER-namespace
        # (QorTroller-branded / QRESCE) FROZEN commitment families. Currently 1:
        # QORTROLLER-IPACT-RENEWAL-v1 (the ③ iPACT renewal family — its GENESIS
        # tag is the SAME family, not a separate one). NOTE:
        # QORTROLLER-IPACT-CHALLENGE-v1 is a CAPABILITY, not a commitment family,
        # so it is explicitly NOT counted here. This fact is SEPARATE from
        # frozen_v1_commitment_family_count (the VAPI Layer-C count, which
        # stays 12) — the two namespaces are tracked independently.
        current_value="1",
        superseded_values=(),  # Brand-new fact; no prior values
        verification_command=(
            "Count of QORTROLLER-namespace (QorTroller-branded / QRESCE) FROZEN "
            "commitment families — currently 1 (QORTROLLER-IPACT-RENEWAL-v1; its "
            "GENESIS tag is the same family). QORTROLLER-IPACT-CHALLENGE-v1 is a "
            "capability, NOT a commitment family, and is not counted. Distinct "
            "from the VAPI Layer-C frozen_v1_commitment_family_count (12)."
        ),
        target_doc_globs=(
            "docs/qortroller-whitepaper-v6.md",
            "docs/qortroller-state-of-the-protocol-2026-05-19.md",
        ),
        context_hints=(
            "qortroller commitment",
            "QorTroller-namespace",
            "qortroller_commitment_family_count",
            "QORTROLLER-IPACT-RENEWAL",
        ),
        # Exclude the VAPI Layer-C count's own context so a line discussing the
        # 12-family VAPI count does not collide with this 1-family QorTroller
        # count, and exclude byte/preimage structure references.
        exclusion_substrings=(
            "Layer-C",
            "PATTERN-017",
            "VAPI commitment",
            "byte", "bytes", "preimage",
        ),
    ),
]


def get_registry() -> list[CanonicalFact]:
    """Return the canonical fact registry. Returned list is a defensive copy."""
    return list(REGISTRY)

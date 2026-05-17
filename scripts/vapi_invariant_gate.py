"""
vapi_invariant_gate.py — Phase 223/224/226/235-UR Protocol Invariant Gate

Hashes critical protocol regions in the source tree and compares against
an allowlist of known-good SHA-256 fingerprints.  Any drift signals a
potential invariant violation before it reaches production.

Phase 224 addition: allowlist hash is anchored as a virtual leaf in
ProtocolCoherenceAgent's Merkle tree.  Every --generate event requires
--reason (tamper-evident governance log).

Phase 226 addition: INV-019..INV-022 freeze the provenance hash computation
code itself (_compute_governance_provenance_hash, ts_ns.to_bytes inclusion,
_fetch_latest_provenance_hash, governance_provenance_chain store layer).

Phase 235-ULTRAREVIEW addition: INV-023..INV-026 freeze the GIC formula
(grind_chain.py genesis/compute functions), gic_ts_ns ordering in store,
_gic_chain_broken flag on Store, and _recompute() read-path enforcement in
capture_continuity.py.

Phase O0 Stream 3-prep Session 3 addition: INV-AGENT-COMMIT-001/002 and
INV-PDA-001/002 freeze the AGENT_COMMIT v1 and PHYSICAL_DATA_ATTESTATION v1
FROZEN-v1 primitives shipped in commits a7b61160 and 412a6f0e respectively.
Total allowlist entries: 32 (28 prior + 4 Phase O0). Per Pass 2C Section 1
commitment to expand allowlist 28 -> 32.

USAGE:
    python scripts/vapi_invariant_gate.py              # gate check (exit 0=pass, 1=fail)
    python scripts/vapi_invariant_gate.py --generate --reason "refactor: description"
    python scripts/vapi_invariant_gate.py --generate --reason "invariant_change: ..." --confirm-governance
    python scripts/vapi_invariant_gate.py --report     # human-readable report, no exit code

INVARIANTS CHECKED (32):
  1.  PoAC wire format (228-byte body + 64-byte sig) in codec.py
  2.  Chain link hash = SHA-256(raw[:164]) in codec.py
  3.  L4 anomaly threshold literal in store.py (7.009 / 5.367)
  4.  ZK circuit Poseidon(8) C3 constraint nPublic=5 in PitlSessionProof.circom
  5.  Phase 66 commitment formula SHA-256(verdict+evidence+attestation+ts_ns)
  6.  Phase 67 circuitId = sha3_256(circuitName.encode())
  7.  CHEAT_CODES hard set: 0x28/0x29/0x2A in dualshock_integration.py
  8.  Stable EMA update — NOMINAL sessions only
  9.  L6_CHALLENGES_ENABLED default=False in config.py
  10. GSR_ENABLED default=False in config.py
  11. L6B_ENABLED default=False in config.py
  12. Epistemic weights sum = 1.0 (ioswarm_enabled branch)
  13. Block quorum BLOCK_QUORUM=0.67 in ioswarm modules
  14. MINT_QUORUM=0.80 in ioswarm VHP mint
  15. 228-byte record in chain.py record_on_chain calls
  16. Allowlist hash included as virtual leaf in ProtocolCoherenceAgent (Phase 224)
  17. Audit script split regex — 4-space indent anchor, not column-0 (audit_endpoint_auth.py)
  18. Audit script block-search — full-body scan, no character-window limit (audit_endpoint_auth.py)
  19. Provenance hash computation function exists in gate script (Phase 226)
  20. ts_ns included as 8-byte big-endian in provenance hash — replay prevention (Phase 226)
  21. Latest provenance hash fetch function exists in gate script (Phase 226)
  22. governance_provenance_chain table + insert method in store (Phase 226)
  29. INV-AGENT-COMMIT-001 — compute_agent_commit_hash exists in agent_commit.py (Phase O0 Stream 3-prep Session 1)
  30. INV-AGENT-COMMIT-002 — VAPI-AGENT-COMMIT-v1 domain tag literal pinned in agent_commit.py (Phase O0)
  31. INV-PDA-001 — compute_pda_hash exists in physical_data_attestation.py (Phase O0 Stream 3-prep Session 2)
  32. INV-PDA-002 — VAPI-PHYSICAL-DATA-ATTESTATION-v1 domain tag literal pinned in physical_data_attestation.py (Phase O0)
  Note: items 23-28 (INV-023..026, INV-CORPUS-001/002) were added without
  enumeration entries by their respective sessions; back-filling that gap
  is intentionally out-of-scope for Session 3 (per Decision F5).
"""

import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).parent.parent
ALLOWLIST_PATH = REPO_ROOT / ".github" / "INVARIANTS_ALLOWLIST.json"

_VALID_REASON_CATEGORIES = frozenset({"refactor", "bugfix", "invariant_change", "ceremony_update"})
_REASON_PATTERN = re.compile(r"^(refactor|bugfix|invariant_change|ceremony_update): .{3,}$")
_GOVERNANCE_PHRASE = "I understand this changes a frozen protocol invariant"


class Invariant(NamedTuple):
    id: str
    description: str
    file: str
    pattern: str       # regex to locate the critical region
    min_matches: int   # minimum expected matches


INVARIANTS: list[Invariant] = [
    Invariant(
        id="INV-001",
        description="PoAC body = 164 bytes (wire format frozen)",
        file="bridge/vapi_bridge/codec.py",
        pattern=r"164",
        min_matches=1,
    ),
    Invariant(
        id="INV-002",
        description="Chain link hash = SHA-256(raw[:164])",
        file="bridge/vapi_bridge/codec.py",
        pattern=r"sha.*256.*164|SHA.256.*164|raw\[:164\]",
        min_matches=1,
    ),
    Invariant(
        id="INV-003",
        description="L4 anomaly threshold literal 7.009",
        file="bridge/vapi_bridge/store.py",
        pattern=r"7\.009",
        min_matches=1,
    ),
    Invariant(
        id="INV-004",
        description="L4 continuity threshold literal 5.367",
        file="bridge/vapi_bridge/store.py",
        pattern=r"5\.367",
        min_matches=1,
    ),
    Invariant(
        id="INV-005",
        description="Phase 62 ZK: Poseidon(8) / nPublic=5",
        file="contracts/circuits/PitlSessionProof.circom",
        pattern=r"Poseidon\(8\)|nPublic\s*=\s*5",
        min_matches=1,
    ),
    Invariant(
        id="INV-006",
        description="Hard cheat codes 0x28/0x29/0x2A in dualshock",
        file="bridge/vapi_bridge/dualshock_integration.py",
        pattern=r"0x28|DRIVER_INJECT",
        min_matches=1,
    ),
    Invariant(
        id="INV-007",
        description="Stable EMA updates NOMINAL sessions only",
        file="bridge/vapi_bridge/dualshock_integration.py",
        pattern=r"NOMINAL|stable.*ema|ema.*stable",
        min_matches=1,
    ),
    Invariant(
        id="INV-008",
        description="L6_CHALLENGES_ENABLED default=False",
        file="bridge/vapi_bridge/config.py",
        pattern=r"l6_challenges_enabled.*[Ff]alse|L6_CHALLENGES_ENABLED.*false",
        min_matches=1,
    ),
    Invariant(
        id="INV-009",
        description="GSR_ENABLED default=False",
        file="bridge/vapi_bridge/config.py",
        pattern=r"gsr_enabled.*[Ff]alse|GSR_ENABLED.*false",
        min_matches=1,
    ),
    Invariant(
        id="INV-010",
        description="L6B_ENABLED default=False",
        file="bridge/vapi_bridge/config.py",
        pattern=r"l6b_enabled.*[Ff]alse|L6B_ENABLED.*false",
        min_matches=1,
    ),
    Invariant(
        id="INV-011",
        description="BLOCK_QUORUM=0.67 in ioswarm modules",
        file="bridge/vapi_bridge/ioswarm_consensus_aggregator.py",
        pattern=r"0\.67|BLOCK_QUORUM",
        min_matches=1,
    ),
    Invariant(
        id="INV-012",
        description="MINT_QUORUM=0.80 in ioswarm VHP mint",
        file="bridge/vapi_bridge/session_adjudicator.py",
        pattern=r"0\.80|MINT_QUORUM",
        min_matches=1,
    ),
    Invariant(
        id="INV-013",
        description="PoAC record total 228 bytes in chain.py",
        file="bridge/vapi_bridge/chain.py",
        pattern=r"228",
        min_matches=1,
    ),
    Invariant(
        id="INV-014",
        description="Phase 66 commitment hash formula (verdict+evidence+attestation)",
        file="bridge/vapi_bridge/session_adjudicator.py",
        pattern=r"verdict.*evidence|commitment_hash|SHA.256.*verdict",
        min_matches=1,
    ),
    Invariant(
        id="INV-015",
        description="Phase 67 circuitId = sha3_256(circuitName.encode())",
        file="bridge/vapi_bridge/chain.py",
        pattern=r"sha3_256|circuitId|circuit_name",
        min_matches=1,
    ),
    Invariant(
        id="INV-016",
        description="Allowlist hash included as virtual leaf in ProtocolCoherenceAgent Merkle root",
        file="bridge/vapi_bridge/protocol_coherence_agent.py",
        pattern=r"allowlist.*leaf|virtual.*leaf|compute_allowlist_hash",
        min_matches=1,
    ),
    Invariant(
        id="INV-017",
        description="Audit script split regex — 4-space indent anchor (not column-0), prevents 800-char regression",
        file="scripts/audit_endpoint_auth.py",
        pattern=r"blocks.*re\.split|re\.split.*\(\?m\)",
        min_matches=1,
    ),
    Invariant(
        id="INV-018",
        description="Audit script block-search — full-body scan via _AUTH_CALLS, no character-window limit",
        file="scripts/audit_endpoint_auth.py",
        pattern=r"has_auth.*any.*_AUTH_CALLS",
        min_matches=1,
    ),
    # Phase 226 — freeze provenance hash computation code
    Invariant(
        id="INV-019",
        description="Provenance hash computation function exists in gate script (Phase 226)",
        file="scripts/vapi_invariant_gate.py",
        pattern=r"_compute_governance_provenance_hash",
        min_matches=1,
    ),
    Invariant(
        id="INV-020",
        description="ts_ns included as 8-byte big-endian in provenance hash — replay prevention (Phase 226)",
        file="scripts/vapi_invariant_gate.py",
        pattern=r"ts_ns.*to_bytes.*8.*big|to_bytes.*8.*big.*ts_ns",
        min_matches=1,
    ),
    Invariant(
        id="INV-021",
        description="Latest provenance hash fetch function exists in gate script (Phase 226)",
        file="scripts/vapi_invariant_gate.py",
        pattern=r"_fetch_latest_provenance_hash",
        min_matches=1,
    ),
    Invariant(
        id="INV-022",
        description="governance_provenance_chain table + insert method in store (Phase 226)",
        file="bridge/vapi_bridge/store.py",
        pattern=r"governance_provenance_chain|insert_governance_provenance",
        min_matches=1,
    ),
    # Phase 235-ULTRAREVIEW — freeze GIC formula and PCC read-path invariants
    Invariant(
        id="INV-023",
        description="GIC formula v1 byte layout frozen: prev(32)||ch(32)||verdict(1)||host(1)||ts_ns(8) (INV-GIC-001)",
        file="bridge/vapi_bridge/grind_chain.py",
        pattern=r"VAPI-GIC-GENESIS-v1|genesis_gic|compute_gic",
        min_matches=1,
    ),
    Invariant(
        id="INV-024",
        description="GIC ts_ns ordering: get_prev_grind_chain_hash orders by gic_ts_ns DESC (INV-GIC-002)",
        file="bridge/vapi_bridge/store.py",
        pattern=r"gic_ts_ns\s+DESC|ORDER\s+BY\s+gic_ts_ns",
        min_matches=1,
    ),
    Invariant(
        id="INV-025",
        description="GIC chain-broken flag on Store class with set method (INV-GIC-003)",
        file="bridge/vapi_bridge/store.py",
        pattern=r"_gic_chain_broken|set_gic_chain_broken",
        min_matches=1,
    ),
    Invariant(
        id="INV-026",
        description="PCC get_status and is_grind_ready call _recompute before reading state (INV-PCC-001)",
        file="bridge/vapi_bridge/capture_continuity.py",
        pattern=r"_recompute\(now\)",
        min_matches=2,
    ),
    # Phase 237.5 — freeze CORPUS-SNAPSHOT on-chain anchor primitives.
    # ZK-SEPPROOF eventual binding requires the anchor function signature
    # and the sourceType literal to be tamper-evident in the gate.
    Invariant(
        id="INV-CORPUS-001",
        description="anchor_corpus_snapshot async function exists in chain.py (Phase 237.5)",
        file="bridge/vapi_bridge/chain.py",
        pattern=r"async def anchor_corpus_snapshot",
        min_matches=1,
    ),
    Invariant(
        id="INV-CORPUS-002",
        description="VAPI_CORPUS_SNAPSHOT_v1 deviceIdHash literal pinned in chain.py (Phase 237.5 Path X — deployed bytecode reality)",
        file="bridge/vapi_bridge/chain.py",
        pattern=r'b"VAPI_CORPUS_SNAPSHOT_v1"',
        min_matches=1,
    ),
    # Phase O0 Stream 3-prep — freeze AGENT_COMMIT v1 and
    # PHYSICAL_DATA_ATTESTATION v1 primitives. Pass 2C Section 4.1 + 4.2
    # specify these four invariants. AGENT_COMMIT v1 shipped in commit
    # a7b61160 (Stream 3-prep Session 1, sixth FROZEN-v1 primitive);
    # PHYSICAL_DATA_ATTESTATION v1 shipped in commit 412a6f0e (Stream
    # 3-prep Session 2, seventh and final FROZEN-v1 primitive).
    Invariant(
        id="INV-AGENT-COMMIT-001",
        description="compute_agent_commit_hash function exists in agent_commit.py (Pass 2C Section 4.1 — sixth FROZEN-v1 primitive hash determinism)",
        file="bridge/vapi_bridge/agent_commit.py",
        pattern=r"def compute_agent_commit_hash",
        min_matches=1,
    ),
    Invariant(
        id="INV-AGENT-COMMIT-002",
        description="VAPI-AGENT-COMMIT-v1 domain tag literal pinned in agent_commit.py (Pass 2C Section 4.1 — DELTA-Pass2C)",
        file="bridge/vapi_bridge/agent_commit.py",
        pattern=r'b"VAPI-AGENT-COMMIT-v1"',
        min_matches=1,
    ),
    Invariant(
        id="INV-PDA-001",
        description="compute_pda_hash function exists in physical_data_attestation.py (Pass 2C Section 4.2 — seventh FROZEN-v1 primitive hash determinism)",
        file="bridge/vapi_bridge/physical_data_attestation.py",
        pattern=r"def compute_pda_hash",
        min_matches=1,
    ),
    Invariant(
        id="INV-PDA-002",
        description="VAPI-PHYSICAL-DATA-ATTESTATION-v1 domain tag literal pinned in physical_data_attestation.py (Pass 2C Section 4.2 — DELTA2-Pass2C)",
        file="bridge/vapi_bridge/physical_data_attestation.py",
        pattern=r'b"VAPI-PHYSICAL-DATA-ATTESTATION-v1"',
        min_matches=1,
    ),
    # Phase 235-PCC-SPC — freeze SPC classifier interface and 3-signal haptic-tolerance binding.
    # The SPC bands + outlier trim (INV-PCC-002), fail-closed disconnect precedence (INV-PCC-003),
    # 3-signal binding (INV-PCC-004), and frequency-band gate (INV-PCC-005) are all load-bearing
    # against bot exploits.  Tampering with any of these regions weakens the PCC integrity gate.
    Invariant(
        id="INV-PCC-002",
        description="update_sample signature includes kw-only-with-default game-context params (trigger_active, accel_var, tremor_peak_hz) preserving Phase 234.7 backward compat (Phase 235-PCC-SPC)",
        file="bridge/vapi_bridge/capture_continuity.py",
        pattern=r"trigger_active:\s*bool\s*=\s*False|accel_var:\s*float\s*=\s*0\.0|tremor_peak_hz:\s*float\s*=\s*0\.0",
        min_matches=3,
    ),
    Invariant(
        id="INV-PCC-003",
        description="signal_disconnect ALWAYS overrides SPC classification — explicit disconnect cannot be masked by in-control capability or haptic-tolerance binding (Phase 235-PCC-SPC fail-closed)",
        file="bridge/vapi_bridge/capture_continuity.py",
        pattern=r"if self\._spc_enabled and not self\._disconnect_reason:",
        min_matches=1,
    ),
    Invariant(
        id="INV-PCC-004",
        description="3-signal haptic-tolerance binding requires ALL of: trigger_active=True AND accel_var>=threshold AND frequency-band-valid AND tolerance_window<=cap (Phase 235-PCC-SPC Assurance A)",
        file="bridge/vapi_bridge/capture_continuity.py",
        pattern=r"def _haptic_tolerance_active",
        min_matches=1,
    ),
    Invariant(
        id="INV-PCC-005",
        description="haptic-tolerance frequency-band gate constrains tremor_peak_hz to [pcc_haptic_tremor_min_hz, pcc_haptic_tremor_max_hz] (Phase 235-PCC-SPC OTHER-class exclusion against low-frequency spoofing)",
        file="bridge/vapi_bridge/capture_continuity.py",
        pattern=r"self\._haptic_tremor_min_hz\s*<=\s*tp\s*<=\s*self\._haptic_tremor_max_hz",
        min_matches=1,
    ),
    # Phase O1 C1 — freeze Cedar bundle parser primitives (canonicalization,
    # Merkle root domain tag, frozen enum sets) and dual-anchor sequence.
    # The bundle Merkle root is the on-chain commitment for each phase
    # boundary; tampering with these regions silently invalidates every
    # bundle ever anchored.
    Invariant(
        id="INV-CEDAR-001",
        description="canonical_bytes function in cedar_parser.py — deterministic JSON encoding for Merkle root computation (Phase O1 C1 FROZEN-v1)",
        file="bridge/vapi_bridge/cedar_parser.py",
        pattern=r"def canonical_bytes\(bundle: dict\) -> bytes:",
        min_matches=1,
    ),
    Invariant(
        id="INV-CEDAR-002",
        description="VAPI-CEDAR-BUNDLE-v1 domain tag literal pinned in cedar_parser.py — any change requires Cedar bundle v2 + new tag (Phase O1 C1)",
        file="bridge/vapi_bridge/cedar_parser.py",
        pattern=r'b"VAPI-CEDAR-BUNDLE-v1"',
        min_matches=1,
    ),
    Invariant(
        id="INV-CEDAR-003",
        description="VALID_EFFECTS / VALID_CATEGORIES / VALID_SCHEMES / VALID_PHASES frozensets in cedar_parser.py — schema enums frozen, any addition is a bundle v2 break (Phase O1 C1)",
        file="bridge/vapi_bridge/cedar_parser.py",
        pattern=r"VALID_EFFECTS\s*=\s*frozenset|VALID_CATEGORIES\s*=\s*frozenset|VALID_SCHEMES\s*=\s*frozenset|VALID_PHASES\s*=\s*frozenset",
        min_matches=4,
    ),
    Invariant(
        id="INV-OPERATOR-AGENT-001",
        description="cedar_bundle_anchor.py operational-FIRST sequence: AgentScope.setAgentScopeRoot fires BEFORE AgentRegistry.updateAgentScope (D4 dual-anchor; reversal weakens governance trail)",
        file="bridge/vapi_bridge/cedar_bundle_anchor.py",
        pattern=r"AgentScope\.setAgentScopeRoot\s+—\s+operational layer FIRST",
        min_matches=1,
    ),
    Invariant(
        id="INV-OPERATOR-AGENT-002",
        description="operator_agent_activation_log UNIQUE(agent_id, to_scope_root) anti-replay constraint in store.py — each (agent, scope_root) tuple activated exactly once (Phase O1 C1)",
        file="bridge/vapi_bridge/store.py",
        pattern=r"UNIQUE\(agent_id, to_scope_root\)",
        min_matches=1,
    ),
    Invariant(
        id="INV-APOP-001",
        description="APOP_STATES + APOP_GATE_MODES frozensets in active_play_occupancy.py — 5 occupancy states + 3 gate modes frozen, any addition is APOP v2 break (Phase 241-APOP)",
        file="bridge/vapi_bridge/active_play_occupancy.py",
        pattern=r"APOP_STATES\s*=\s*frozenset|APOP_GATE_MODES\s*=\s*frozenset|APOP_COMPETITIVE_STATES\s*=\s*frozenset|APOP_STRICT_ELIGIBLE_STATES\s*=\s*frozenset",
        min_matches=4,
    ),
    Invariant(
        id="INV-APOP-002",
        description="APOP scoring weights formula in classify_active_play_occupancy — 0.35 stick + 0.20 button + 0.20 trigger + 0.15 imu + 0.10 physiology = 1.00 (sum invariant; weight rebalance is APOP v2)",
        file="bridge/vapi_bridge/active_play_occupancy.py",
        pattern=r"0\.35\s*\*\s*frame_metrics\[\"stick_score\"\]|0\.20\s*\*\s*frame_metrics\[\"button_score\"\]|0\.20\s*\*\s*frame_metrics\[\"trigger_score\"\]|0\.15\s*\*\s*frame_metrics\[\"imu_score\"\]|0\.10\s*\*\s*physiology_score",
        min_matches=5,
    ),
    Invariant(
        id="INV-OPERATOR-AGENT-003",
        description="operator_agent_shadow_log UNIQUE(agent_id, action, resource, evaluated_at_bucket) idempotency at second granularity — protects against retry-storm duplication while permitting distinct evaluations per second (Phase O1 C2)",
        file="bridge/vapi_bridge/store.py",
        pattern=r"UNIQUE\(agent_id, action, resource, evaluated_at_bucket\)",
        min_matches=1,
    ),
    Invariant(
        id="INV-OPERATOR-AGENT-004",
        description="cedar_shadow_runtime.evaluate_agent_action FAILS OPEN — any error path returns CedarDecision.FORBID_DEFAULT_DENY (safe default) but never raises; higher-level callers must not assume permission (Phase O1 C2)",
        file="bridge/vapi_bridge/cedar_shadow_runtime.py",
        pattern=r"INV-OPERATOR-AGENT-004",
        min_matches=1,
    ),
    Invariant(
        id="INV-OPERATOR-AGENT-005",
        description="cedar_shadow_runtime recomputes Bundle Merkle root every evaluation (not cached) — required for FSCA BUNDLE_HASH_DRIFT detection (Phase O1 C2/C3)",
        file="bridge/vapi_bridge/cedar_shadow_runtime.py",
        pattern=r"INV-OPERATOR-AGENT-005",
        min_matches=1,
    ),
    Invariant(
        id="INV-OPERATOR-AGENT-006",
        description="operator_agent_drift_log UNIQUE(agent_id, drift_type, detected_at_bucket) sweep idempotency — same drift in same second collapses to one row (Phase O1 C3)",
        file="bridge/vapi_bridge/store.py",
        pattern=r"UNIQUE\(agent_id, drift_type, detected_at_bucket\)",
        min_matches=1,
    ),
    Invariant(
        id="INV-OPERATOR-AGENT-007",
        description="cedar_shadow_runtime drift_type literals frozen — BUNDLE_HASH_DRIFT + SCOPE_HASH_GOVERNANCE_DRIFT are the canonical Phase O1 C3 drift signatures; new types are protocol additions requiring governance (Phase O1 C3)",
        file="bridge/vapi_bridge/cedar_shadow_runtime.py",
        pattern=r"\"BUNDLE_HASH_DRIFT\"|\"SCOPE_HASH_GOVERNANCE_DRIFT\"",
        min_matches=2,
    ),
    Invariant(
        id="INV-OPERATOR-AGENT-008",
        description="cedar_drift_sweeper dual-cadence default constants frozen — bundle 60s (cheap+frequent: local file SHA-256 + DB read) / scope 600s (expensive+rare: 2 chain RPC reads/agent). The split is invariant; the specific seconds are configurable (Phase O1 C4)",
        file="bridge/vapi_bridge/cedar_drift_sweeper.py",
        pattern=r"_BUNDLE_DRIFT_INTERVAL_DEFAULT_S = 60|_SCOPE_DRIFT_INTERVAL_DEFAULT_S = 600",
        min_matches=2,
    ),
    Invariant(
        id="INV-FRR-001",
        description="compute_fleet_readiness_root function exists in operator_initiative_advancement.py — eighth FROZEN-v1 cryptographic primitive (Phase O1-FRR Stream B)",
        file="bridge/vapi_bridge/operator_initiative_advancement.py",
        pattern=r"def compute_fleet_readiness_root\(",
        min_matches=1,
    ),
    Invariant(
        id="INV-FRR-002",
        description="FRR_DOMAIN_TAG = b\"VAPI-FRR-v1\" (11 bytes) — FROZEN-v1 domain tag for Fleet Readiness Root pre-image (Phase O1-FRR)",
        file="bridge/vapi_bridge/operator_initiative_advancement.py",
        pattern=r'FRR_DOMAIN_TAG = b"VAPI-FRR-v1"',
        min_matches=1,
    ),
    Invariant(
        id="INV-FRR-003",
        description="FRR pre-image byte-order frozen — agent_id (32B) || phase_code (1B) per agent, then ts_ns_be(8) at end. Encoded via to_bytes(8, \"big\") for ts_ns; pre.append(phase_code) for byte; pre.extend(id_bytes) for agent_id. Any rearrangement breaks downstream verifiers and requires FRR v2 + new domain tag (Phase O1-FRR)",
        file="bridge/vapi_bridge/operator_initiative_advancement.py",
        pattern=r'pre\.extend\(int\(ts_ns\)\.to_bytes\(8, "big"\)\)|pre\.append\(phase_code\)',
        min_matches=2,
    ),
    Invariant(
        id="INV-PARALLEL-ANCHOR-001",
        description="scripts/parallel_o2_anchor.py triple-gate pattern frozen — env CHAIN_SUBMISSION_PAUSED=false + env OPERATOR_INITIATIVE_O2_AUTHORIZED=true + --confirm CLI. All three required to fire txs; mirrors canary_corpus_snapshot_anchor.py defensive layer (Phase O1-FRR Stream E)",
        file="scripts/parallel_o2_anchor.py",
        pattern=r"OPERATOR_INITIATIVE_O2_AUTHORIZED|CHAIN_SUBMISSION_PAUSED|args\.confirm",
        min_matches=3,
    ),
    Invariant(
        id="INV-CURATOR-O2-001",
        description="curator_o2_suggest_v1.json bundle Merkle root frozen at 0xeb400a5c9b410c6f3035a595e2c36dee915f6b2447f822c72c46b164ccd5daa9 — validated 2026-05-09 prior to parallel O2 anchor; any policy edit re-anchors to a NEW Merkle root and breaks this invariant by design (governance event required) (Phase O1-FRR Stream A)",
        file="bridge/vapi_bridge/cedar_bundles/curator_o2_suggest_v1.json",
        pattern=r'"agent_id":\s*"0xed6a2df58e5ec50c1f88e127f6982a348f6855202b662b8ad73ffa1c1fda11a8"|"phase":\s*"O2_SUGGEST"',
        min_matches=2,
    ),
    Invariant(
        id="INV-CURATOR-O2-002",
        description="curator_o2_suggest_v1.json lane_prefix array preserves marketplace/, provenance/, events/, wiki/ — Curator's marketplace-curator-review skill scope is bounded to these prefixes; any expansion breaks the cross-agent skill-separation invariant (Phase O1-CURATOR C2)",
        file="bridge/vapi_bridge/cedar_bundles/curator_o2_suggest_v1.json",
        pattern=r'"marketplace/"|"provenance/"|"events/"|"wiki/"',
        min_matches=4,
    ),
    Invariant(
        id="INV-O3-WATCHER-001",
        description="Phase O3-ACT-WATCHER bundle filename phase resolver matches both _o3_acting_ (canonical) and _o3_act_ (legacy) substrings — preserves backward compatibility with legacy bundle naming while pinning canonical O3_ACTING phase recognition (Phase O3-WATCHER-LOCK)",
        file="bridge/vapi_bridge/operator_initiative_advancement.py",
        pattern=r"_o3_acting_|_o3_act_",
        min_matches=2,
    ),
    Invariant(
        id="INV-O3-WATCHER-002",
        description="Phase O3-ACT-WATCHER strengthened gate constants (draft_payload_min + disagreement_rate_max + false_positive_rate_max) — frozen O3 readiness thresholds enforce minimum draft payload, max LLM/fallback disagreement, and Curator-specific false-positive bound (Phase O3-WATCHER-LOCK)",
        file="bridge/vapi_bridge/operator_initiative_advancement.py",
        pattern=r"PHASE_O3_DRAFT_PAYLOAD_MIN|PHASE_O3_DISAGREEMENT_RATE_MAX|PHASE_O3_FALSE_POSITIVE_RATE_MAX",
        min_matches=3,
    ),
    Invariant(
        id="INV-O3-WATCHER-003",
        description="Phase O3-ACT-DRAFT bundle Merkle roots locked (Sentry + Guardian + Curator O3_ACTING) — three frozen Merkle roots pinned in test_phase_o3_act_draft_bundles.py; any policy edit re-anchors to NEW Merkle roots and breaks this invariant by design (governance event required) (Phase O3-WATCHER-LOCK)",
        file="bridge/tests/test_phase_o3_act_draft_bundles.py",
        pattern=r"c0bcdee8576e83f6b80e8c5ac89093cf08f153033037176cd03fc34fcedfd878|6f0fc77cc1dacaf3f79aeb0f27dd8c7b3d88e95b236f0806ad3588a06bb82225|d9d760c8b7b1088f2edd165fbfa6441abcb3bc3f921e8ba75a3339c0825fec24",
        min_matches=3,
    ),
    Invariant(
        id="INV-O3-SUPERSEDE-001",
        description="Phase O1-D-AUTO-SUPERSEDE FROZEN-v1 domain tag b\"VAPI-O3-SUPERSEDE-v1\" literal — distinguishes the Empirical-Evidence Supersession primitive commitments from all other PATTERN-017 family members; renaming silently breaks the byte-layout invariant of the attestation hash formula (Phase O1-D-AUTO-SUPERSEDE 2026-05-17)",
        file="bridge/vapi_bridge/operator_initiative_auto_supersede.py",
        pattern=r'b"VAPI-O3-SUPERSEDE-v1"',
        min_matches=1,
    ),
    Invariant(
        id="INV-O3-SUPERSEDE-002",
        description="Phase O1-D-AUTO-SUPERSEDE compute_supersede_attestation_hash function preserved + 92-byte preimage sanity check — guards against silent byte-layout drift in the FROZEN-v1 attestation hash formula; any change to the preimage byte order or field set requires bumping the domain tag to v2 (Phase O1-D-AUTO-SUPERSEDE 2026-05-17)",
        file="bridge/vapi_bridge/operator_initiative_auto_supersede.py",
        pattern=r"def compute_supersede_attestation_hash|len\(preimage\) != 92",
        min_matches=2,
    ),
    Invariant(
        id="INV-O3-SUPERSEDE-003",
        description="Phase O1-D-AUTO-SUPERSEDE operator_initiative_auto_supersede_log table + insert helper preserved — the cryptographic-attestation audit-trail backbone; without persistence the watcher's supersession events become unauditable (Phase O1-D-AUTO-SUPERSEDE 2026-05-17)",
        file="bridge/vapi_bridge/store.py",
        pattern=r"operator_initiative_auto_supersede_log|insert_operator_initiative_auto_supersede",
        min_matches=2,
    ),
    Invariant(
        id="INV-PATH-B-001",
        description="Phase O1-D-PATH-B v1 evaluate_live_write_authorization_for_agent function + four-gate safety contract (phase_o3_executor_kill_all + per-agent live_writes_enabled + O3_ACTING phase + daily budget) — load-bearing authorization layer for the live-write executor; removing this would allow unauthorized chain operations to fire (Phase O1-D-PATH-B 2026-05-17)",
        file="bridge/vapi_bridge/operator_initiative_live_write_executor.py",
        pattern=r"def evaluate_live_write_authorization_for_agent|phase_o3_executor_kill_all",
        min_matches=2,
    ),
    Invariant(
        id="INV-PATH-B-002",
        description="Phase O1-D-PATH-B v1 operator_agent_chain_spending_log table + insert_chain_spending_event + get_daily_chain_spending_for_agent helpers — the budget-enforcement audit backbone; without persistence the budget cap can be bypassed (Phase O1-D-PATH-B 2026-05-17)",
        file="bridge/vapi_bridge/store.py",
        pattern=r"operator_agent_chain_spending_log|insert_chain_spending_event|get_daily_chain_spending_for_agent",
        min_matches=3,
    ),
    Invariant(
        id="INV-PATH-B-003",
        description="Phase O1-D-PATH-B v1 per-agent live-writes cfg flags (all three default False) + emergency kill-all + per-agent daily IOTX budgets — the cfg surface that operators flip to opt-in autonomous execution per agent. Renaming or removing any of the 3 enable flags / 3 budget fields / kill-all would silently degrade operator control (Phase O1-D-PATH-B 2026-05-17)",
        file="bridge/vapi_bridge/config.py",
        pattern=r"phase_o3_anchor_sentry_live_writes_enabled|phase_o3_guardian_live_writes_enabled|phase_o3_curator_live_writes_enabled|phase_o3_executor_kill_all|phase_o3_anchor_sentry_daily_iotx_budget|phase_o3_guardian_daily_iotx_budget|phase_o3_curator_daily_iotx_budget",
        min_matches=7,
    ),
    Invariant(
        id="INV-O1-FRR-SDK-001",
        description="Phase O1-FRR-SDK VAPIFleetReadinessRoot client class exists in sdk/vapi_sdk.py — wraps GET /operator/fleet-readiness-root + GET /operator/operator-initiative-advancement-log; renaming or removing this class breaks the wire-contract parity discipline (endpoint -> SDK -> frontend -> NOTE) for the FRR primitive (Phase O1-FRR-SDK-LOCK)",
        file="sdk/vapi_sdk.py",
        pattern=r"class VAPIFleetReadinessRoot:",
        min_matches=1,
    ),
    Invariant(
        id="INV-O1-FRR-SDK-002",
        description="Phase O1-FRR-SDK three frozen dataclass names (AgentReadinessRow + FleetReadinessRootResult + AdvancementLogResult) — the slot-pinned shapes returned by VAPIFleetReadinessRoot methods; renaming would silently break downstream Python tooling that imports them (Phase O1-FRR-SDK-LOCK)",
        file="sdk/vapi_sdk.py",
        pattern=r"class AgentReadinessRow:|class FleetReadinessRootResult:|class AdvancementLogResult:",
        min_matches=3,
    ),
    Invariant(
        id="INV-O3-UI-DRAWER-001",
        description="Phase O1 C5 OperatorAgentsDrawer zIndex 20 (bottom-right) preserved — bottom of the three-drawer ordering; raising it above 21 collides with DraftReviewDrawer overlap (Phase O3-UI-LAYOUT-LOCK)",
        file="frontend/src/components/OperatorAgentsDrawer.jsx",
        pattern=r"zIndex:\s*20",
        min_matches=1,
    ),
    Invariant(
        id="INV-O3-UI-DRAWER-002",
        description="Phase O2-DRAFT-REVIEW-FRONTEND DraftReviewDrawer zIndex 21 (bottom-left) preserved — middle of the three-drawer ordering; below O3 Readiness (22) above Operator Agents (20) (Phase O3-UI-LAYOUT-LOCK)",
        file="frontend/src/components/DraftReviewDrawer.jsx",
        pattern=r"zIndex:\s*21",
        min_matches=1,
    ),
    Invariant(
        id="INV-O3-UI-DRAWER-003",
        description="Phase O3-READINESS-DASHBOARD O3ReadinessDrawer zIndex 22 (top-center) preserved — TOP of the three-drawer ordering above DraftReviewDrawer (21) and OperatorAgentsDrawer (20); ensures the strategic readiness view always layers correctly when multiple drawers are open (Phase O3-UI-LAYOUT-LOCK)",
        file="frontend/src/components/O3ReadinessDrawer.jsx",
        pattern=r"zIndex:\s*22",
        min_matches=1,
    ),

    # --- Phase O3-ZKBA-TRACK1 C5 — INV-ZKBA-001/002/003 (tenth FROZEN-v1 primitive) ---
    # ZKBA-ARTIFACT primitive (Phase O3-ZKBA-TRACK1 C2 commit 625007ab) pinned
    # at PV-CI level per VBDIP-0001 §7 canonical PATTERN-017 convention.
    Invariant(
        id="INV-ZKBA-001",
        description="compute_zkba_commitment function exists in bridge/vapi_bridge/zkba_artifact.py — the tenth FROZEN-v1 primitive compute function (Phase O3-ZKBA-TRACK1 C2; PATTERN-017 #10 per VBDIP-0001 §7 canonical convention)",
        file="bridge/vapi_bridge/zkba_artifact.py",
        pattern=r"def compute_zkba_commitment",
        min_matches=1,
    ),
    Invariant(
        id="INV-ZKBA-002",
        description="VAPI-ZKBA-ARTIFACT-v1 domain tag literal pinned in bridge/vapi_bridge/zkba_artifact.py — FROZEN-v1 21-byte domain separator for the ZKBA primitive pre-image; uniqueness verified against 11 pre-existing VAPI-*-v1 tags at C2 ship time (Phase O3-ZKBA-TRACK1)",
        file="bridge/vapi_bridge/zkba_artifact.py",
        pattern=r'b"VAPI-ZKBA-ARTIFACT-v1"',
        min_matches=1,
    ),
    Invariant(
        id="INV-ZKBA-003",
        description="vapi-zkba-manifest-v1 manifest schema string pinned in scripts/vsd_ui_compiler.py — FROZEN at v1.0 per VBDIP-0002 §9.2; identifies the projection manifest schema version that the deterministic UI compiler emits (Phase O3-ZKBA-TRACK1 C3)",
        file="scripts/vsd_ui_compiler.py",
        pattern=r'"vapi-zkba-manifest-v1"',
        min_matches=1,
    ),
    Invariant(
        id="INV-VPM-WRAPPER-001",
        description="vapi-vpm-manifest-v1 wrapper schema string pinned in scripts/vsd_vpm_wrapper.py — FROZEN at v1.0 per VBDIP-0002 Appendix B B.4 (v1.1 amendment); identifies the VPM wrapper manifest schema that wraps (does not replace) the FROZEN vapi-zkba-manifest-v1 ZKBA schema. Resolved via Operator Decision Matrix D-PV-VPM Option P3 (single-pin minimal form mirroring INV-ZKBA-003); ships 2026-05-12. Supplements G5b static guard tests (test_t_vpm_static_wrapper_schema_string_pinned_in_source) by elevating the FROZEN literal to PV-CI gate enforcement. VPM-HONESTY-001 (Appendix B B.5) remains a methodology-doc identifier; INV-VPM-WRAPPER-001 is the implementation-layer pin (distinct surfaces per reconciliation plan §4).",
        file="scripts/vsd_vpm_wrapper.py",
        pattern=r'"vapi-vpm-manifest-v1"',
        min_matches=1,
    ),
    # Phase O4-VPM-INTEGRATION close — 10 INV-VPM-* invariants per plan §4.1.
    # Pin load-bearing source-code regions across the entire VPM stack:
    # compiler engine, manifest schema literals, visual grammar enum,
    # bridge CSP headers, frontend sandbox literal, audit harness shape.
    Invariant(
        id="INV-VPM-COMPILER-001",
        description="compile_vpm_artifact function exists in scripts/vsd_ui_compiler.py — the Phase O4 Stream A.0 public entry-point that emits VPM artifacts under strict compiler discipline (no external resources / no runtime network / no randomness / no wall-clock / 9-field Integrity Label DOM). Sibling of compile_artifact() for the unwrapped ZKBA projection path. Pinned at v1.0 alongside the VPM artifact schema; signature change requires Phase O5+ governance event.",
        file="scripts/vsd_ui_compiler.py",
        pattern=r"def compile_vpm_artifact\(",
        min_matches=1,
    ),
    Invariant(
        id="INV-VPM-COMPILER-002",
        description="vapi-vpm-artifact-v1 VPM artifact schema literal pinned in scripts/vsd_ui_compiler.py — FROZEN at v1.0 per Phase O4 plan section 4.1. Distinct from vapi-zkba-manifest-v1 (ZKBA projection schema, INV-ZKBA-003) and vapi-vpm-manifest-v1 (wrapper schema, INV-VPM-WRAPPER-001). The three schemas form the Layer 7 stack: ZKBA -> VPM wrapper -> VPM artifact. Compiler version 0.1.0 bump or schema rename requires v2 governance ceremony.",
        file="scripts/vsd_ui_compiler.py",
        pattern=r'"vapi-vpm-artifact-v1"',
        min_matches=1,
    ),
    Invariant(
        id="INV-VPM-INTEGRITY-LABEL-001",
        description="9-field Integrity Nutrition Label tuple pinned in scripts/vsd_ui_compiler.py — _VPM_INTEGRITY_LABEL_FIELDS captures the FROZEN field set per VBDIP-0002 Appendix B section B.5: proof_type / capture_mode / raw_biometrics_exposed / consent_active / zk_verified / on_chain_anchor / proof_weight / revocation_status / limitations. The compiler's _verify_integrity_label_in_dom static guard refuses to write any emitted HTML missing any of these 9 data-vpm-field markers. Mirrored on frontend at scripts/vpm_visual_grammar.py:INTEGRITY_LABEL_FIELDS + frontend/src/components/VpmManifestPanel.jsx.",
        file="scripts/vsd_ui_compiler.py",
        pattern=r"_VPM_INTEGRITY_LABEL_FIELDS = \(",
        min_matches=1,
    ),
    Invariant(
        id="INV-VPM-VISUAL-STATES-001",
        description="6-element FROZEN Anti-Hype Visual Grammar state tuple pinned in scripts/vpm_visual_grammar.py — VISUAL_STATES = (live, dry-run, emulated, frozen-disabled, revoked, unverified) per VBDIP-0002 Appendix B section B.5 + Phase O4 plan section 5.1. The 6 states are protocol law; renaming or reordering requires VBDIP-0002 v1.2 amendment + corresponding update of the frontend VpmGrammarVerifier FROZEN signature matrix.",
        file="scripts/vpm_visual_grammar.py",
        pattern=r"^VISUAL_STATES = \(",
        min_matches=1,
    ),
    Invariant(
        id="INV-VPM-CAPTURE-MODES-001",
        description="5-element FROZEN VPM capture mode tuple pinned in scripts/vsd_ui_compiler.py — _VPM_CAPTURE_MODES = (live, dry-run, emulated, demo, frozen-disabled) per VBDIP-0002A section 4 wrapper schema. Mirrors the VPMCaptureMode enum in scripts/vsd_vpm_wrapper.py. Bridge validator endpoint validates manifest.capture_mode against this set.",
        file="scripts/vsd_ui_compiler.py",
        pattern=r"_VPM_CAPTURE_MODES = \(",
        min_matches=1,
    ),
    Invariant(
        id="INV-VPM-WRAPPER-SCHEMA-REF-001",
        description="VPM artifact manifest references the wrapper schema literally in scripts/vsd_ui_compiler.py — _VPM_WRAPPER_SCHEMA_REF = \"vapi-vpm-manifest-v1\" is the FROZEN reference (not replacement) link between the VPM artifact's manifest sidecar and the wrapper schema. Every compile_vpm_artifact-emitted manifest carries this string as its wrapper_schema field. Mirrors INV-VPM-WRAPPER-001 from the wrapper-module side; this invariant pins the consumer-module side of the same string.",
        file="scripts/vsd_ui_compiler.py",
        pattern=r'_VPM_WRAPPER_SCHEMA_REF = "vapi-vpm-manifest-v1"',
        min_matches=1,
    ),
    Invariant(
        id="INV-VPM-CSP-001",
        description="VPM HTML response FROZEN security headers pinned in bridge/vapi_bridge/operator_api.py — _VPM_HTML_RESPONSE_HEADERS dict carries the Phase O4 plan section 3 Stream B.2 CSP set: default-src 'none' / style-src 'unsafe-inline' / script-src 'unsafe-inline' / img-src data: / base-uri 'none' / frame-ancestors 'self' / form-action 'none'. The 'unsafe-inline' flags are INTENTIONAL — VPMs are self-contained single-file artifacts pre-validated by compile_vpm_artifact static guards; default-src 'none' + no connect-src makes runtime network impossible regardless of inline JS behavior.",
        file="bridge/vapi_bridge/operator_api.py",
        pattern=r"_VPM_HTML_RESPONSE_HEADERS = \{",
        min_matches=1,
    ),
    Invariant(
        id="INV-VPM-SANDBOX-001",
        description="VPM iframe FROZEN sandbox attribute pinned in frontend/src/components/VpmIframe.jsx — VPM_IFRAME_SANDBOX literal must equal 'allow-scripts allow-same-origin' exactly per Phase O4 plan section 3 Stream C.3. NO expansion permitted: allow-forms / allow-popups / allow-top-navigation / allow-modals / allow-pointer-lock / allow-presentation / allow-downloads / allow-storage-access-by-user-activation are ALL forbidden. allow-scripts is required (VPMs render inline JS); allow-same-origin is required for Layer 3 grammar verifier to read iframe contentDocument.",
        file="frontend/src/components/VpmIframe.jsx",
        pattern=r'"allow-scripts allow-same-origin"',
        min_matches=1,
    ),
    Invariant(
        id="INV-VPM-COMPILE-ENDPOINT-001",
        description="POST /operator/vpm-compile bridge endpoint route pinned in bridge/vapi_bridge/operator_api.py — Phase O4 Stream B.4 write endpoint that dispatches compile requests to one of 6 active VPM compilers per _VPM_COMPILER_REGISTRY and records the result row in vpm_artifact_log. Full operator key required (api_key query param matches cfg.operator_api_key). Worker-thread compile dispatch via asyncio.to_thread keeps the event loop responsive.",
        file="bridge/vapi_bridge/operator_api.py",
        pattern=r'@app\.post\("/operator/vpm-compile"\)',
        min_matches=1,
    ),
    Invariant(
        id="INV-VPM-AUDIT-SECTION-1-001",
        description="VPM audit harness Section 1 active compiler registry function pinned in scripts/vpm_audit.py — section_1_active_compiler_registry verifies all 6 active VPM compiler scripts exist on disk and export their declared build_*_artifact function. Companion sections 2..6 cover Draft Manifest registry / VBDIP-0002A section 10 lifecycle ladder / CFSS lane assignment / source discipline source-grep / visual grammar coverage. Pinning section 1's signature pins the audit harness shape; renaming Section 1 forces governance ceremony.",
        file="scripts/vpm_audit.py",
        pattern=r"def section_1_active_compiler_registry\b",
        min_matches=1,
    ),
    Invariant(
        id="INV-VPM-ANCHOR-CONTRACT-001",
        description="VPMAnchorRegistry.sol anchorVPM function declaration pinned. The function takes 3 args (bytes32 zkbaManifestHash, bytes32 vpmManifestHash, uint64 tsNs) — verified together with the immediately-following arg lines via INV-VPM-ANCHOR-ABI-001. Extends the FROZEN quadruple-bind into a quintuple-bind by wiring on-chain anchoring.",
        file="contracts/contracts/VPMAnchorRegistry.sol",
        pattern=r"function anchorVPM\(",
        min_matches=1,
    ),
    Invariant(
        id="INV-VPM-ANCHOR-CHAIN-CLIENT-001",
        description="chain.anchor_vpm bridge-side helper pinned. Async method consuming VPMAnchorRegistry.anchorVPM via the FROZEN ABI literal _VPM_ANCHOR_ABI. Kill-switch checked FIRST (CHAIN_SUBMISSION_PAUSED), then config + account presence, then hex normalization, then zero-hash upfront rejection, then build+sign+send with gas-estimate × 1.25 buffer. Never raises — fail-open (None, False) per the anchor_corpus_snapshot pattern.",
        file="bridge/vapi_bridge/chain.py",
        pattern=r"async def anchor_vpm\(",
        min_matches=1,
    ),
    Invariant(
        id="INV-VPM-ANCHOR-ABI-001",
        description="_VPM_ANCHOR_ABI literal name in chain.py pinned. The FROZEN 3-arg ABI descriptor for VPMAnchorRegistry.anchorVPM lives directly below this assignment. Selector + arg order MUST match the contract's anchorVPM signature byte-for-byte; drift breaks the wire format. Catches accidental selector / arg rename at PR time alongside T-VPM-ANCHOR-11.",
        file="bridge/vapi_bridge/chain.py",
        pattern=r"_VPM_ANCHOR_ABI\s*=\s*\[\{",
        min_matches=1,
    ),
    Invariant(
        id="INV-CFSS-SWEEPER-LOOP-001",
        description="run_cfss_drift_sweep_loop async entry-point pinned in cfss_drift_sweeper.py — the 27th-FSCA-rule data source. Opt-in via cfg.cfss_drift_sweep_enabled; cadence pinned at 60s per INV-OPERATOR-AGENT-008 cheap+frequent tier. Wraps audit_module.sweep_once() + persists CFSS_VIOLATION findings to cfss_lane_drift_log. Fail-open: any sweep error caught + logged; loop continues.",
        file="bridge/vapi_bridge/cfss_drift_sweeper.py",
        pattern=r"async def run_cfss_drift_sweep_loop\s*\(\s*\*,\s*cfg,\s*store\)",
        min_matches=1,
    ),
    Invariant(
        id="INV-CFSS-SWEEPER-CADENCE-001",
        description="_CFSS_DRIFT_INTERVAL_DEFAULT_S = 60 default cadence pinned in cfss_drift_sweeper.py — matches cedar_drift_sweeper bundle cadence per INV-OPERATOR-AGENT-008 cheap+frequent tier (file-only evaluation; no chain RPC). Operator can override via env CFSS_DRIFT_SWEEP_INTERVAL_S but the default is FROZEN at 60s.",
        file="bridge/vapi_bridge/cfss_drift_sweeper.py",
        pattern=r"_CFSS_DRIFT_INTERVAL_DEFAULT_S\s*=\s*60",
        min_matches=1,
    ),
    Invariant(
        id="INV-FSCA-CFSS-RULE-001",
        description="CFSS_LANE_AUTHORITY_DRIFT 27th contradiction rule pinned in fleet_signal_coherence_agent.py CONTRADICTION_RULES dict — CRITICAL severity; 4 agents involved (AnchorSentry + Guardian + Curator + CFSSDriftSweeper). Source: cfss_lane_drift_log populated by cfss_drift_sweeper. Closes the data-layer / policy-layer enforcement asymmetry for Cedar v2 CFSS.",
        file="bridge/vapi_bridge/fleet_signal_coherence_agent.py",
        pattern=r'"CFSS_LANE_AUTHORITY_DRIFT":\s*\{',
        min_matches=1,
    ),
    # Phase O4-W3B-POSEIDON-AS — pin the protocol-internal AssemblyScript
    # Poseidon(BN254) cryptographic capability. POSEIDON-BN254-AS is NOT an
    # 11th PATTERN-017 commitment family (the commitment-family count stays
    # 10): it is the hash-function capability that SUPPORTS PATTERN-017 #8
    # ZK-SEPPROOF and the Phase 62 PitlSessionProof circuit by making their
    # commitment computation verifiable inside the W3bstream applet. The AS
    # implementation is verified byte-identical to circomlibjs 0.1.7 across
    # 525 final-output vectors + 150 per-round vectors + 48100 intermediate
    # round-state elements (V.1 commit 0b6adc13 + V.2 commit a80f3fb4). AMBER
    # path: circomlibjs 0.1.7 is the single reference; V.3 cross-reference
    # triangulation is deferred pending ecosystem availability of a second
    # BN254-compatible Poseidon reference (P.0-confirmed 2026-05-14).
    # NOTE: the plan's PV.1 named INV-POSEIDON-AS-003 as a
    # POSEIDON_VECTORS_SHA256 *constant in poseidon_bn254.ts*; the I.1 agent
    # (correctly) did not pollute the production crypto module with test
    # metadata, so this invariant pins the vector-corpus hash where it
    # actually lives — the committed poseidon_test_vectors.sha256 — which is
    # the genuine tamper-evidence surface P.3's validator already checks.
    Invariant(
        id="INV-POSEIDON-AS-001",
        description="AS Poseidon(BN254) arity entry points poseidon_t2/t3/t9 exported from poseidon_bn254.ts (Phase O4-W3B-POSEIDON-AS) — the public surface validate_poac_record.ts wires to: t2=deviceIdHash (circomlib Poseidon(1)), t3=nullifierHash (Poseidon(2)), t9=featureCommitment (Poseidon(8)). min_matches=3 catches any single-arity rename.",
        file="scripts/w3bstream/poseidon_bn254.ts",
        pattern=r"export function poseidon_t[239]\(",
        min_matches=3,
    ),
    Invariant(
        id="INV-POSEIDON-AS-002",
        description="BN254 scalar field prime byte-literal pinned in poseidon_bn254.ts (Phase O4-W3B-POSEIDON-AS) — the top 8 big-endian bytes of p = 0x30644e72e131a029.... Any drift in the prime is a modular-reduction correctness break that silently invalidates every Poseidon output the applet produces.",
        file="scripts/w3bstream/poseidon_bn254.ts",
        pattern=r"0x30,\s*0x64,\s*0x4e,\s*0x72,\s*0xe1,\s*0x31,\s*0xa0,\s*0x29",
        min_matches=1,
    ),
    Invariant(
        id="INV-POSEIDON-AS-003",
        description="Poseidon test-vector corpus SHA-256 pinned in poseidon_test_vectors.sha256 (Phase O4-W3B-POSEIDON-AS) — the circomlibjs 0.1.7 ground-truth corpus that V.1/V.2 verify the AS implementation against (1000 random + 25 boundary + 50 per-round vectors per arity {t2,t3,t9}). Protects against silent vector-file tampering eroding the single-reference verification basis.",
        file="scripts/w3bstream/poseidon_test_vectors.sha256",
        pattern=r"9bfe035c83919af6047a196523c2396e85dd76fe5c4412102031131aeec99980",
        min_matches=1,
    ),
    # Phase O5-MYTHOS-MINIMAL M.3 — pin the Minimal-Mythos infrastructure.
    # Mythos variants find drift; PV-CI must protect Mythos itself from
    # drift. Three invariants form the trust ratchet: (1) the cadence
    # schedule dict, (2) the variant entry points, (3) the FROZEN-region
    # protection contract that prevents Mythos from ever auto-fixing
    # FROZEN material.
    Invariant(
        id="INV-MYTHOS-CADENCE-001",
        description="MYTHOS_CADENCE_SCHEDULE dict pinned in mythos_cadence_engine.py (Phase O5-MYTHOS-MINIMAL M.3). Defines which variants run at which cadence tier — daily / per_pr / per_phase_close / pre_ceremony / post_incident. Drift here changes the audit cadence silently.",
        file="bridge/vapi_bridge/mythos_cadence_engine.py",
        pattern=r"MYTHOS_CADENCE_SCHEDULE:\s*dict\[str,\s*list\[str\]\]\s*=\s*\{",
        min_matches=1,
    ),
    Invariant(
        id="INV-MYTHOS-VARIANTS-001",
        description="Mythos variant entry points pinned in mythos_variants.py (Phase O5-MYTHOS-MINIMAL M.3). The 2 async variant functions mythos_frozen_drift + mythos_stability_sweep are the public surface the cadence engine and MCP tools invoke. min_matches=2 catches any single-variant rename or removal.",
        file="bridge/vapi_bridge/mythos_variants.py",
        pattern=r"^async def mythos_(frozen_drift|stability_sweep)\(",
        min_matches=2,
    ),
    Invariant(
        id="INV-MYTHOS-FROZEN-PROTECTION-001",
        description="Store-layer enforcement of the FROZEN-region read-only invariant: insert_mythos_finding FORCES fix_authority_tier=3 whenever frozen_region=True, regardless of the variant's declared tier. Mythos NEVER auto-fixes FROZEN material — this invariant is the cryptographic safety property the plan named (verified by T-MYTHOS-M1-3). Drift here would let a malicious or buggy variant suggest tier-1 autofix on a FROZEN region and have it take effect.",
        file="bridge/vapi_bridge/store.py",
        pattern=r"INV-MYTHOS-FROZEN-PROTECTION-001",
        min_matches=1,
    ),
    # ---------------------------------------------------------------------------
    # Session 2026-05-15 Stream 4 PV-CI ceremony — pin the constructs shipped
    # across the day's 9 commits: Phase 243-SS2 Stream 1 (trigger force curve
    # scaffolding) + Phase 242-BT Stream 1 (BT-WITNESS v1 capability) +
    # Mythos OpInit variant + Priority 5 Full Mythos (Crypto/Methodology/Ceremony/
    # Corpus) + Mythos PR gate + O3 expedite arc (preflight + seeding + 2 new cfg
    # fields). 12 invariants total; 89 → 101 after this ceremony.
    # ---------------------------------------------------------------------------
    Invariant(
        id="INV-SS2-PROBE-TYPE-001",
        description="Phase 243-SS2 Stream 1: trigger_force_curve probe type registered in STRUCTURED_PROBE_TYPES frozenset (the 7th member after touchpad_corners + touchpad_freeform + touchpad_swipes + mixed_biometric_probe + tremor_resting + ait). T-PHASE243-1 verifies; Stage-A captures consume this routing key.",
        file="bridge/vapi_bridge/store.py",
        pattern=r'"trigger_force_curve"',
        min_matches=1,
    ),
    Invariant(
        id="INV-BT-WITNESS-DOMAIN-001",
        description='Phase 242-BT Stream 1: BT-WITNESS v1 FROZEN capability tag b"VAPI-BT-WITNESS-v1" (18 bytes). Width is asserted at module import; widening or narrowing requires a separate capability tag, NOT modification of this literal. Capability tag (NOT a new PATTERN-017 commitment family per the POSEIDON-BN254-AS reframe precedent).',
        file="bridge/vapi_bridge/bt_witness.py",
        pattern=r'BT_WITNESS_DOMAIN_TAG: bytes = b"VAPI-BT-WITNESS-v1"',
        min_matches=1,
    ),
    Invariant(
        id="INV-BT-WITNESS-TRANSPORT-001",
        description="Phase 242-BT Stream 1: BT_WITNESS_TRANSPORT_BR_EDR = 0x01 FROZEN transport-code literal. DualSense + DualSense Edge transport is Bluetooth Classic BR/EDR with HIDP per the v1.1 canonical anchor (NOT BLE/HOGP). Future BLE-HOGP variant requires a separate capability tag, not a different transport_code value.",
        file="bridge/vapi_bridge/bt_witness.py",
        pattern=r"BT_WITNESS_TRANSPORT_BR_EDR: int = 0x01",
        min_matches=1,
    ),
    Invariant(
        id="INV-BT-WITNESS-PREIMAGE-001",
        description="Phase 242-BT Stream 1: BT-WITNESS commitment preimage layout FROZEN at 18 + 20 + 32 + 32 + 32 + 1 + 8 = 143 bytes (domain tag + witness_pubkey + device_id + session_id + feature_root + transport_code + ts_ns). Any reordering or width change requires v2 capability tag. INV-BT-WITNESS-003 in the module's docstring describes this in detail.",
        file="bridge/vapi_bridge/bt_witness.py",
        pattern=r"18 \+ 20 \+ 32 \+ 32 \+ 32 \+ 1 \+ 8 == 143",
        min_matches=1,
    ),
    Invariant(
        id="INV-MYTHOS-OPINIT-ENTRY-001",
        description="Mythos-Operator-Initiative-Audit variant entry point pinned in mythos_variants.py (operator-authorized extension 2026-05-15). The async function mythos_operator_initiative_audit is the comprehensive 5-check-family audit; renaming or removing requires a governance ceremony.",
        file="bridge/vapi_bridge/mythos_variants.py",
        pattern=r"async def mythos_operator_initiative_audit",
        min_matches=1,
    ),
    Invariant(
        id="INV-MYTHOS-FAMILIES-001",
        description="Mythos-Crypto _PATTERN_017_FROZEN_TAGS frozenset declaration pinned (Priority 5). 11 commitment families per the empirical audit finding 2026-05-15 (CLAUDE.md previously stated 10; PHYSICAL_DATA_ATTESTATION v1 confirmed as 11th by its own module docstring). The frozenset declaration line is pinned; the contents are pinned by the per-family domain tag literals being checked by their own existing invariants.",
        file="bridge/vapi_bridge/mythos_variants.py",
        pattern=r"_PATTERN_017_FROZEN_TAGS: frozenset\[bytes\] = frozenset",
        min_matches=1,
    ),
    Invariant(
        id="INV-MYTHOS-METHODOLOGY-FILES-001",
        description="Mythos-Methodology _METHODOLOGY_REQUIRED_FILES tuple pinned (Priority 5). The methodology trust chain that protocol-layer surfaces inherit from depends on these 7 files (VBDIP-0001 + METHODOLOGY_LAYER_INTEGRATION_MAP + BT/sensor-stack v1.1 architectural revisions + 2 canonical-anchor PDFs + architect Ed25519 attestation). Mythos-Methodology surfaces HIGH on VBDIP/architect missing; MEDIUM elsewhere.",
        file="bridge/vapi_bridge/mythos_variants.py",
        pattern=r"_METHODOLOGY_REQUIRED_FILES: tuple\[str, \.\.\.\] =",
        min_matches=1,
    ),
    Invariant(
        id="INV-MYTHOS-CADENCE-SCHEDULE-001",
        description="MYTHOS_CADENCE_SCHEDULE 6-tier dict pinned in mythos_cadence_engine.py (extended to include operator_initiative + Priority 5 variants 2026-05-15). Tiers: daily/per_pr/per_phase_close/pre_ceremony/post_incident/weekly. Drift here changes which variants run at which cadence — affects FSCA finding-surface coverage windows.",
        file="bridge/vapi_bridge/mythos_cadence_engine.py",
        pattern=r"MYTHOS_CADENCE_SCHEDULE: dict\[str, list\[str\]\]",
        min_matches=1,
    ),
    Invariant(
        id="INV-MYTHOS-PR-GATE-BLOCKING-001",
        description="Mythos PR gate _is_blocking rule matrix pinned (Priority 5 Part 3, commit a756f95f). CRITICAL severity ALWAYS blocks PR merge; HIGH severity + frozen_region=True blocks; HIGH non-frozen + MEDIUM + LOW are informational. Drift here changes the effective PR enforcement boundary — must move through governance ceremony.",
        file="scripts/run_mythos_pr_gate.py",
        pattern=r'if finding\.severity == "CRITICAL":',
        min_matches=1,
    ),
    Invariant(
        id="INV-O3-EXPEDITE-CFG-001",
        description="O3 expedite arc 2026-05-15 cfg fields pinned in config.py: operator_dual_key_present (gate 5; all 3 agents) + github_app_oauth_tokens_valid (gate 7; Guardian-only). Promoted from getattr-fallback to first-class Config fields so operators can author the declarations via env vars OPERATOR_DUAL_KEY_PRESENT + GITHUB_APP_OAUTH_TOKENS_VALID.",
        file="bridge/vapi_bridge/config.py",
        pattern=r"operator_dual_key_present: bool = field",
        min_matches=1,
    ),
    Invariant(
        id="INV-O3-EXPEDITE-PREFLIGHT-001",
        description="O3 expedite preflight CLI entry point run_preflight pinned (commit 0e83a8ce). Reads watcher state + cfg flags + DB state; produces verdict ceremony_ready_to_fire / ceremony_ready_when_calendar_clears / READY-TO-FIRE / CALENDAR-WAITING / EXPEDITE-WORK-AVAILABLE. The single canonical operator-facing CLI for the O3 calendar window.",
        file="scripts/operator_initiative_o3_preflight.py",
        pattern=r"def run_preflight\(db_path: str, \*, strict: bool\)",
        min_matches=1,
    ),
    Invariant(
        id="INV-O3-EXPEDITE-SEEDING-TRIPLEGATE-001",
        description="O3 expedite seeding harness triple-gate authorization function pinned (commit 0e83a8ce). _check_triple_gate enforces (a) CHAIN_SUBMISSION_PAUSED=true env (kill-switch ARMED), (b) OPERATOR_INITIATIVE_SEED_DRAFTS_AUTHORIZED=true env (DISTINCT from O2/O3 anchor envs to prevent carry-over), (c) --confirm CLI flag. All three required for real seeding; otherwise dry-run.",
        file="scripts/operator_initiative_seed_drafts.py",
        pattern=r"def _check_triple_gate\(\*, confirm: bool\)",
        min_matches=1,
    ),
    # ---------------------------------------------------------------------------
    # Phase O5-MLGA Stage 5 PV-CI ceremony — pin the MLGA constructs from
    # session 2026-05-15 Stage 2 implementation. 7 invariants; 101 → 108.
    # See wiki/methodology/mlga_architectural_proposal_v1.md for the
    # architectural basis for each pin.
    # ---------------------------------------------------------------------------
    Invariant(
        id="INV-MLGA-DOMAIN-TAG-001",
        description='Phase O5-MLGA: MLGA_SESSION_DOMAIN_TAG = b"VAPI-MLGA-SESSION-v1" FROZEN literal in bridge/vapi_bridge/mlga_capture.py (20 bytes). Capability tag distinguishing MLGA session dataproofs from PATTERN-017 commitment families + every other capability tag. Width asserted at module import; widening or narrowing requires a separate capability tag, NOT modification of this literal.',
        file="bridge/vapi_bridge/mlga_capture.py",
        pattern=r'MLGA_SESSION_DOMAIN_TAG: bytes = b"VAPI-MLGA-SESSION-v1"',
        min_matches=1,
    ),
    Invariant(
        id="INV-MLGA-CAPABILITY-NOT-FAMILY-001",
        description='Phase O5-MLGA: b"VAPI-MLGA-SESSION-v1" must appear in _KNOWN_CAPABILITY_TAGS in bridge/vapi_bridge/mythos_variants.py (NOT in _PATTERN_017_FROZEN_TAGS). MLGA is a capability tag per the POSEIDON-BN254-AS reframe precedent; commitment-family count stays 10 + PHYSICAL_DATA_ATTESTATION = 11 (per the Mythos-Crypto empirical correction). MLGA-LESSON-001 ratified.',
        file="bridge/vapi_bridge/mythos_variants.py",
        pattern=r'b"VAPI-MLGA-SESSION-v1"',
        min_matches=1,
    ),
    Invariant(
        id="INV-MLGA-DATAPROOF-PREIMAGE-001",
        description="Phase O5-MLGA: compute_mlga_session_dataproof byte layout FROZEN at 20 + 8 + 8 + 8 + 4 + 4 + 32 + 1 + 4 = 89 bytes preimage. Any reordering or width change requires a v2 capability tag. The 89-byte assert is the load-bearing line of defense against silent layout drift.",
        file="bridge/vapi_bridge/mlga_capture.py",
        pattern=r"20 \+ 8 \+ 8 \+ 8 \+ 4 \+ 4 \+ 32 \+ 1 \+ 4 == 89",
        min_matches=1,
    ),
    Invariant(
        id="INV-MLGA-VARIANT-ENTRY-001",
        description="Phase O5-MLGA: mythos_live_gameplay_audit async function entry point pinned in bridge/vapi_bridge/mythos_variants.py — the 9th Mythos variant. Cadence: per_session tier (8th cadence tier, also pinned by INV-MLGA-CADENCE-001). Mythos finding routing goes through this entry; renaming or removing requires governance ceremony.",
        file="bridge/vapi_bridge/mythos_variants.py",
        pattern=r"async def mythos_live_gameplay_audit",
        min_matches=1,
    ),
    Invariant(
        id="INV-MLGA-CADENCE-001",
        description='Phase O5-MLGA: per_session cadence tier registered in MYTHOS_CADENCE_SCHEDULE with live_gameplay variant (8th tier; added 2026-05-15 alongside the 9th variant). Drift here changes when MLGA fires; tied to operator-runtime hardware-capture sessions.',
        file="bridge/vapi_bridge/mythos_cadence_engine.py",
        pattern=r'"per_session":\s+\["live_gameplay"\]',
        min_matches=1,
    ),
    Invariant(
        id="INV-MLGA-STORE-TABLE-001",
        description="Phase O5-MLGA: mlga_session_log table migration registered in store.py (Phase 1102 migration; UNIQUE(session_id, dataproof_hex) anti-replay). Schema is the single canonical record for MLGA gameplay sessions; drift here breaks the unblock-harness export consumers (Phase 243-SS2 + 242-BT + 229).",
        file="bridge/vapi_bridge/store.py",
        pattern=r"CREATE TABLE IF NOT EXISTS mlga_session_log",
        min_matches=1,
    ),
    Invariant(
        id="INV-MLGA-UNBLOCK-MAPPING-001",
        description="Phase O5-MLGA: unblock-harness export script maps to the 3 currently-blocked phases (243-SS2-Stage-A / 242-BT-Stage-2 / 229-AIT-Corpus). Pin the 3 phase keys + the consumer references so future PRs cannot silently drop a target phase. Per MLGA architectural proposal §3.",
        file="scripts/mlga_unblock_export.py",
        pattern=r"phase_243_ss2_stage_a|phase_242_bt_stage_2|phase_229_ait_corpus",
        min_matches=3,
    ),
    # ---------------------------------------------------------------------------
    # Phase O5-MLGA Stage 3 PV-CI pins (2 new invariants; 108 → 110).
    # These cover the runtime session tracker that operationalizes the MLGA
    # capability — without these, MLGA was paper. After Stage 3, gameplay
    # sessions auto-track + dataproof + persist.
    # ---------------------------------------------------------------------------
    Invariant(
        id="INV-MLGA-TRACKER-ENTRY-001",
        description="Phase O5-MLGA Stage 3 — MLGASessionTracker class + run_mlga_session_tracker_loop async entry-point pinned in bridge/vapi_bridge/mlga_session_tracker.py. The tracker is the runtime wiring that operationalizes the MLGA capability (Stage 2 commit cee77070). Without these entry points, MLGA is paper — Stage 3 is the operational unblock. Renaming or removing requires governance ceremony.",
        file="bridge/vapi_bridge/mlga_session_tracker.py",
        pattern=r"class MLGASessionTracker:|async def run_mlga_session_tracker_loop",
        min_matches=2,
    ),
    Invariant(
        id="INV-MLGA-TRACKER-LIFECYCLE-001",
        description="Phase O5-MLGA Stage 3 — session lifecycle methods pinned: open_session + close_session + poll_once. These are the 3 public methods that compose the polling-based session lifecycle (open on capture_state=NOMINAL; close on DISCONNECTED or max_duration; poll_once accumulates from records/APOP/GIC tables between events). Changing the method shape changes how MLGA sessions are bounded — drift here invalidates the dataproof semantics.",
        file="bridge/vapi_bridge/mlga_session_tracker.py",
        pattern=r"def (open_session|close_session|poll_once)\(",
        min_matches=3,
    ),
    # ---------------------------------------------------------------------------
    # Phase O5-MLGA Stage 4 PV-CI pins (3 new; 110 → 113).
    # These wire the MLGA dataproof primitive (shipped Stage 2 commit cee77070)
    # into the Phase O4 VPM compiler discipline so each closed gameplay session
    # becomes a tamper-evident HTML artifact in the existing VPM Registry +
    # the new DeveloperView MLGA drawer. Without these pins, the VPM bridge
    # could regress silently (e.g., schema rename, missing close-hook).
    # ---------------------------------------------------------------------------
    Invariant(
        id="INV-MLGA-COMPILER-ENTRY-001",
        description="Phase O5-MLGA Stage 4: build_mlga_session_artifact entry point pinned in scripts/mlga_compile_session_artifact.py. Mirrors zkba_compile_gic_ledger.py pattern. Caller is bridge/vapi_bridge/mlga_session_tracker.py close_session() hook + the CLI entry. Renaming this function silently breaks Stage 4 wiring; PV-CI prevents that.",
        file="scripts/mlga_compile_session_artifact.py",
        pattern=r"def build_mlga_session_artifact\(",
        min_matches=1,
    ),
    Invariant(
        id="INV-MLGA-VPM-SCHEMA-001",
        description='Phase O5-MLGA Stage 4: MLGA_VPM_WRAPPER_SCHEMA = "vapi-mlga-session-artifact-v1" FROZEN literal in scripts/mlga_compile_session_artifact.py. Persisted to vpm_artifact_log.wrapper_schema column on every close — frontend useMlgaArtifacts filters by this schema. Renaming the schema breaks downstream queries silently; PV-CI prevents that.',
        file="scripts/mlga_compile_session_artifact.py",
        pattern=r'MLGA_VPM_WRAPPER_SCHEMA: str = "vapi-mlga-session-artifact-v1"',
        min_matches=1,
    ),
    Invariant(
        id="INV-MLGA-CLOSE-HOOK-001",
        description="Phase O5-MLGA Stage 4: close_session() in mlga_session_tracker.py invokes build_mlga_session_artifact + persists via insert_vpm_artifact post dataproof persist. Pattern matches the 2 critical call sites in close_session — the compiler invocation + the vpm_artifact_log insert. Drift here means the VPM artifact stops getting produced + persisted at session close. PV-CI prevents silent regression.",
        file="bridge/vapi_bridge/mlga_session_tracker.py",
        pattern=r"build_mlga_session_artifact\(|self\._store\.insert_vpm_artifact\(",
        min_matches=2,
    ),
    # ---------------------------------------------------------------------------
    # VBDIP-0006 PV-CI pins (4 new; 113 → 117).
    # VAPI Firmware Reference Implementation specification — the canonical
    # document any VAPI-Native Controller manufacturer reads + builds against.
    # Pins the load-bearing structural claims that the spec's v1.0 makes.
    # Stream 4-style ceremony per VBDIP-0001 + VBDIP-0002 precedent.
    # ---------------------------------------------------------------------------
    Invariant(
        id="INV-VBDIP-0006-001",
        description="VBDIP-0006 v1.0 Section 1 scope claim — the trust-boundary-shift the spec defines (Layer 0 cryptographic trust at the input source via at-source ECDSA-P256 signing inside the controller's secure element). Drift here would broaden what v1.0 firmware claims; governance ceremony required.",
        file="wiki/methodology/VBDIP-0006-vapi-firmware-reference-implementation.md",
        pattern=r"VAPI-Native Controllers.*ECDSA-P256 signed inside the controller's secure element",
        min_matches=1,
    ),
    Invariant(
        id="INV-VBDIP-0006-002",
        description="VBDIP-0006 v1.0 Section 3 FROZEN cryptographic primitives list — the 228-byte PoAC wire format reference + GIC chain genesis tag b\"VAPI-GIC-GENESIS-v1\" + hard cheat code 0x28 DRIVER_INJECT firmware emission. Adding a new FROZEN primitive that firmware must implement requires governance ceremony.",
        file="wiki/methodology/VBDIP-0006-vapi-firmware-reference-implementation.md",
        pattern=r'b"VAPI-GIC-GENESIS-v1"|228 bytes total|0x28.*DRIVER_INJECT',
        min_matches=3,
    ),
    Invariant(
        id="INV-VBDIP-0006-003",
        description="VBDIP-0006 v1.0 Section 6 VAPI Mode HID descriptor — Interface 3 with Usage Page 0xFF00, Report ID 0x01 carrying 228-byte PoAC records at 1000 Hz. The descriptor is consumed by both firmware (emit) + bridge (read); drift breaks both sides simultaneously.",
        file="wiki/methodology/VBDIP-0006-vapi-firmware-reference-implementation.md",
        pattern=r"Usage Page 0xFF00|Report ID.*0x01.*228",
        min_matches=2,
    ),
    Invariant(
        id="INV-VBDIP-0006-004",
        description="VBDIP-0006 v1.0 Section 8 conformance test suite specification — 100 deterministic test vectors covering random (20) + edge case (20) + hard-cheat (20) + GIC continuity (20) + counter rollover (20). Ensures the certification harness scope cannot silently shrink. Cited by VAPIHardwareCertRegistry cert_level=1 requirement.",
        file="wiki/methodology/VBDIP-0006-vapi-firmware-reference-implementation.md",
        pattern=r"100 deterministic test vectors|test_vbdip_0006_conformance",
        min_matches=2,
    ),
    # ------------------------------------------------------------------
    # Phase O5-PUBLIC-VIEWER — public forensic surface + browser-side
    # crypto verifier catalog. 5 invariants pin (1) auth-leak prevention
    # in the public sub-app, (2) mount path, (3) verifier function
    # registry size, (4) FROZEN-v1 domain tag presence in the JS verifier
    # catalog, (5) router minimum-route presence so the public route
    # cannot silently disappear during a refactor.
    # ------------------------------------------------------------------
    Invariant(
        id="INV-PUBLIC-FORENSIC-001",
        description="public_forensic_api.py MUST NOT contain any _check_key( or _check_read_key( substring. The public sub-app is by-design unauthenticated; an accidental auth gate on a route declared public would silently change the integrity contract. Static grep CI guard.",
        file="bridge/vapi_bridge/public_forensic_api.py",
        # NEGATIVE invariant: pattern matches the FORBIDDEN substring; the
        # gate test is implemented separately as test_t_pub_noauth_*
        # because the standard min_matches contract doesn't express
        # "MUST NOT occur". We pin the absence-statement instead.
        pattern=r"INV-PUBLIC-FORENSIC-001 violated|NO `_check_key",
        min_matches=1,
    ),
    Invariant(
        id="INV-PUBLIC-FORENSIC-002",
        description="public sub-app MUST be mounted at exactly /public in main.py (not /pub, /v1/public, etc.). Pinned literal so router-path drift surfaces immediately.",
        file="bridge/vapi_bridge/main.py",
        pattern=r'app\.mount\("/public",',
        min_matches=1,
    ),
    Invariant(
        id="INV-CRYPTO-VERIFIER-CATALOG-001",
        description="frontend/src/crypto/vapi_verifier.js MUST export exactly 15 verifier functions (14 FROZEN-v1 primitives + Cedar Merkle). Pinned function names ensure the browser-side catalog cannot shrink below the Python algorithm count without an invariant change.",
        file="frontend/src/crypto/vapi_verifier.js",
        pattern=r"export async function verify\w+",
        min_matches=15,
    ),
    Invariant(
        id="INV-CRYPTO-VERIFIER-FROZEN-TAGS-001",
        description="frontend/src/crypto/vapi_verifier.js MUST reference all 13 FROZEN-v1 domain tags (the catalog in public_forensic_api._FROZEN_V1_ALGORITHMS). Cross-file consistency: every domain tag the bridge publishes is replayable in browser.",
        file="frontend/src/crypto/vapi_verifier.js",
        pattern=r"VAPI-(GIC-GENESIS|MLGA-SESSION|WEC-GENESIS|VAME|CORPUS-SNAPSHOT|CONSENT|BIOMETRIC-SNAPSHOT|LISTING|FRR|ZKBA-ARTIFACT|AGENT-COMMIT|PHYSICAL-DATA-ATTESTATION|BT-WITNESS)-v1",
        min_matches=13,
    ),
    Invariant(
        id="INV-PUBLIC-ROUTE-001",
        description="frontend/src/main.jsx MUST wire BrowserRouter with both the public session route (/session/:commitmentHex) and the default operator route (/). Pinned together so neither route can silently disappear in a refactor.",
        file="frontend/src/main.jsx",
        pattern=r"BrowserRouter|/session/:commitmentHex",
        min_matches=2,
    ),
]


# ---------------------------------------------------------------------------
# VBD invariants (Phase O1-VBDIP-0001 Step 5; VAD bridge sub-discipline)
#
# Per VBDIP-0001 §4 + §9: at v1.0 freeze the Python check function bodies
# remain `pass` stubs; programmatic enforcement is deferred to VBDIP-0003.
# Each entry pattern-matches the function signature documented in
# VBDIP-0001's §4.1/§4.2/§4.3 markdown code blocks — that's how we
# "register" the invariant's existence in canonical methodology while
# the harness check is markdown-normative.
#
# VBD-INV-4 (retroactive CFSS rename) is reserved but NOT registered here
# because INV-CFSS-001 does not yet exist in the allowlist (Volume 2
# §20.1 ships it at Phase O1-VSD-BOOTSTRAP). Registration follows when
# CFSS lands.
# ---------------------------------------------------------------------------

VBD_INVARIANTS: list[Invariant] = [
    Invariant(
        id="VBD-INV-001",
        description="Continuous deployer-verified provenance under fleet expansion — bridge wallet 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692 is the load-bearing identity anchor for all VAPI work across all sub-disciplines; check_vbd_inv_1 signature documented in VBDIP-0001 §4.1 (markdown-normative; programmatic check deferred to VBDIP-0003)",
        file="wiki/methodology/VBDIP-0001-vad-framework-introduction.md",
        pattern=r"def check_vbd_inv_1\(repo_root",
        min_matches=1,
    ),
    Invariant(
        id="VBD-INV-002",
        description="Fleet-domain replication discipline — new operator domains must follow the structural pattern established by the synthesis fleet's relationship to the protocol fleet; check_vbd_inv_2 signature documented in VBDIP-0001 §4.2 (markdown-normative; programmatic check deferred to VBDIP-0003)",
        file="wiki/methodology/VBDIP-0001-vad-framework-introduction.md",
        pattern=r"def check_vbd_inv_2\(repo_root",
        min_matches=1,
    ),
    Invariant(
        id="VBD-INV-003",
        description="Primitive composition discipline — every FROZEN-v1 primitive in PATTERN-017 must declare its composition path with other primitives or explicitly state composition-terminal; check_vbd_inv_3 signature documented in VBDIP-0001 §4.3 (markdown-normative; programmatic check deferred to VBDIP-0003)",
        file="wiki/methodology/VBDIP-0001-vad-framework-introduction.md",
        pattern=r"def check_vbd_inv_3\(repo_root",
        min_matches=1,
    ),
]

# Synthesis invariants — stub list. VSD-INV-1..VSD-INV-23 ship at Phase
# O1-VSD-BOOTSTRAP Stream B per Volume 2 §22. Empty here so the --proposal-type
# flag has a registry to filter against; bootstrap populates.
SYNTHESIS_INVARIANTS: list[Invariant] = []


def _select_invariants_for_proposal_type(proposal_type: str) -> list[Invariant]:
    """Select the invariant registry to check based on --proposal-type flag.

    Choices (VBDIP-0001 §7):
      protocol  : INVARIANTS (existing protocol-side; default; backward-compat)
      bridge    : VBD_INVARIANTS (VBD sub-discipline; VBD-INV-* entries)
      synthesis : SYNTHESIS_INVARIANTS (empty stub; ships at Phase O1-VSD-BOOTSTRAP)
      all       : union of all three
      both      : DEPRECATED alias for 'all' (Volume 2 §22 legacy; preserved)
    """
    if proposal_type == "protocol":
        return INVARIANTS
    elif proposal_type == "bridge":
        return VBD_INVARIANTS
    elif proposal_type == "synthesis":
        return SYNTHESIS_INVARIANTS
    elif proposal_type in ("all", "both"):
        return INVARIANTS + VBD_INVARIANTS + SYNTHESIS_INVARIANTS
    else:
        raise ValueError(
            f"unknown --proposal-type: {proposal_type!r}; "
            "choices are protocol, bridge, synthesis, all (or deprecated 'both')"
        )


def compute_allowlist_hash() -> str:
    """Return SHA-256 of canonicalized INVARIANTS_ALLOWLIST.json. Returns 64 zeros if missing."""
    if not ALLOWLIST_PATH.exists():
        return "0" * 64
    content = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _hash_file_region(path: Path, pattern: str) -> tuple[str, int]:
    """Hash all lines matching pattern in file. Returns (hex_digest, match_count)."""
    if not path.exists():
        return ("FILE_NOT_FOUND", 0)
    text = path.read_text(encoding="utf-8", errors="replace")
    matches = [line for line in text.splitlines() if re.search(pattern, line, re.IGNORECASE)]
    digest = hashlib.sha256("\n".join(matches).encode()).hexdigest()
    return (digest, len(matches))


def check_invariants(proposal_type: str = "protocol") -> list[dict]:
    """Run invariant checks for the given proposal-type. Returns list of result dicts.

    Phase O1-VBDIP-0001 Step 5: extended to accept proposal_type per VBDIP-0001
    §3.4 / §7. Default 'protocol' preserves backward compatibility (the original
    63 INVARIANTS run by default).
    """
    invariants = _select_invariants_for_proposal_type(proposal_type)
    results = []
    for inv in invariants:
        path = REPO_ROOT / inv.file
        digest, count = _hash_file_region(path, inv.pattern)
        result = {
            "id": inv.id,
            "description": inv.description,
            "file": inv.file,
            "digest": digest,
            "match_count": count,
            "file_found": path.exists(),
            "pattern_matched": count >= inv.min_matches,
        }
        results.append(result)
    return results


def load_allowlist() -> dict:
    """Load allowlist from .github/INVARIANTS_ALLOWLIST.json. Returns {} if missing."""
    if not ALLOWLIST_PATH.exists():
        return {}
    return json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))


def _fetch_latest_provenance_hash() -> str:
    """GET latest governance_provenance_hash from bridge. Returns '0'*64 if unreachable."""
    import urllib.request as _urlreq
    try:
        req = _urlreq.Request(
            "http://localhost:8080/agent/allowlist-governance-history?limit=1",
            headers={"Content-Type": "application/json"},
        )
        with _urlreq.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read().decode())
            entries = body.get("entries", [])
            if entries:
                return str(entries[0].get("governance_provenance_hash", "0" * 64))
    except Exception:
        pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip
    return "0" * 64


def _compute_governance_provenance_hash(
    prev_prov: str, new_hash: str, category: str, text: str
) -> str:
    """SHA-256(prev_prov_bytes || new_hash_bytes || category_bytes || text_bytes || ts_ns_8b).

    Forms a tamper-evident hash-linked audit trail (Phase 225).
    """
    ts_ns = time.time_ns()
    digest = hashlib.sha256(
        prev_prov.encode() +
        new_hash.encode() +
        category.encode() +
        text.encode() +
        ts_ns.to_bytes(8, "big")
    ).hexdigest()
    return digest


def _post_governance_event(prev: str, new: str, category: str, text: str) -> None:
    """POST governance event to bridge. Fail-open: logs warning if bridge unreachable."""
    import urllib.request as _urlreq
    # Phase 225: build tamper-evident provenance chain hash before POSTing.
    prev_prov_hash = _fetch_latest_provenance_hash()
    governance_provenance_hash = _compute_governance_provenance_hash(
        prev_prov_hash, new, category, text
    )
    payload = json.dumps({
        "previous_hash": prev,
        "new_hash": new,
        "reason_category": category,
        "reason_text": text,
        "governance_provenance_hash": governance_provenance_hash,
        "previous_provenance_hash":  prev_prov_hash,
    }).encode()
    try:
        req = _urlreq.Request(
            "http://localhost:8080/agent/allowlist-governance-event",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        _urlreq.urlopen(req, timeout=5)
        print(f"[invariant_gate] Governance event posted to bridge (prov_hash={governance_provenance_hash[:12]}...).")
    except Exception as exc:
        print(
            f"[invariant_gate] WARNING: bridge not reachable ({exc}). "
            "Governance event not stored — run bridge and POST manually."
        )


def generate_allowlist(results: list[dict], reason_category: str = "", reason_text: str = "") -> None:
    """Write current digests as the new allowlist. Captures prev/new hash for governance log."""
    previous_hash = compute_allowlist_hash()
    allowlist = {r["id"]: {"digest": r["digest"], "description": r["description"]} for r in results}
    ALLOWLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    ALLOWLIST_PATH.write_text(json.dumps(allowlist, indent=2) + "\n", encoding="utf-8")
    new_hash = compute_allowlist_hash()
    print(f"[invariant_gate] Allowlist written: {ALLOWLIST_PATH} ({len(allowlist)} entries)")
    if reason_category and reason_text:
        _post_governance_event(previous_hash, new_hash, reason_category, reason_text)


def run_gate(report_only: bool = False, proposal_type: str = "protocol") -> int:
    """Run invariant gate. Returns 0=pass, 1=fail.

    Phase O1-VBDIP-0001 Step 5: proposal_type filters which invariant
    registry to check (protocol / bridge / synthesis / all).
    """
    results = check_invariants(proposal_type=proposal_type)
    allowlist = load_allowlist()
    failures = []

    for r in results:
        if not r["file_found"]:
            failures.append(f"{r['id']} — FILE NOT FOUND: {r['file']}")
            continue
        if not r["pattern_matched"]:
            failures.append(
                f"{r['id']} — PATTERN NOT MATCHED (0 lines): {r['description']}"
            )
            continue
        if allowlist and r["id"] in allowlist:
            expected = allowlist[r["id"]]["digest"]
            if r["digest"] != expected:
                failures.append(
                    f"{r['id']} — DIGEST DRIFT: {r['description']}\n"
                    f"    expected={expected[:16]}... got={r['digest'][:16]}..."
                )

    if report_only:
        print(f"[invariant_gate] Checked {len(results)} invariants")
        for r in results:
            status = "OK" if r["pattern_matched"] else "FAIL"
            print(f"  {r['id']} {status:4s} matches={r['match_count']:2d}  {r['description']}")
        if failures:
            print(f"\n[invariant_gate] FAILURES ({len(failures)}):")
            for f in failures:
                print(f"  {f}")
        else:
            print("\n[invariant_gate] All invariants pass.")
        return 0  # report mode always exits 0

    if failures:
        print(f"[invariant_gate] INVARIANT GATE FAILED ({len(failures)} violations):")
        for f in failures:
            print(f"  {f}")
        return 1

    print(f"[invariant_gate] PASS — {len(results)} invariants verified.")
    return 0


def _parse_proposal_type_arg() -> str:
    """Parse --proposal-type from sys.argv. Default 'protocol' (backward-compat).

    Handles both forms:
      --proposal-type bridge   (space-separated)
      --proposal-type=bridge   (equals-form)

    Phase O1-VBDIP-0001 Step 5: VBDIP-0001 §7 introduces --proposal-type
    with choices [protocol, bridge, synthesis, all]; 'both' is preserved
    as a deprecated alias for 'all'.
    """
    val: str | None = None
    for i, arg in enumerate(sys.argv):
        if arg == "--proposal-type":
            if i + 1 >= len(sys.argv):
                print("[invariant_gate] ERROR: --proposal-type requires a value.")
                sys.exit(2)
            val = sys.argv[i + 1]
            break
        if arg.startswith("--proposal-type="):
            val = arg.split("=", 1)[1]
            break
    if val is None:
        return "protocol"
    if val not in ("protocol", "bridge", "synthesis", "all", "both"):
        print(
            f"[invariant_gate] ERROR: invalid --proposal-type: {val!r}\n"
            "Choices: protocol | bridge | synthesis | all  (or deprecated 'both')"
        )
        sys.exit(2)
    if val == "both":
        print(
            "[invariant_gate] WARNING: --proposal-type=both is a deprecated alias for 'all'. "
            "Use --proposal-type=all directly."
        )
    return val


if __name__ == "__main__":
    proposal_type = _parse_proposal_type_arg()

    if "--generate" in sys.argv:
        # Phase 224: --reason is required for all --generate calls
        if "--reason" not in sys.argv:
            print(
                "[invariant_gate] ERROR: --reason is required for --generate.\n"
                "Usage: python scripts/vapi_invariant_gate.py --generate "
                '--reason "<category>: <description>"\n'
                "Categories: refactor | bugfix | invariant_change | ceremony_update"
            )
            sys.exit(2)

        reason_idx = sys.argv.index("--reason")
        if reason_idx + 1 >= len(sys.argv):
            print("[invariant_gate] ERROR: --reason requires a value.")
            sys.exit(2)
        reason_raw = sys.argv[reason_idx + 1]

        if not _REASON_PATTERN.match(reason_raw) or not (10 <= len(reason_raw) <= 200):
            print(
                f"[invariant_gate] ERROR: invalid --reason value: {reason_raw!r}\n"
                "Must match: <category>: <description> (10-200 chars)\n"
                "Categories: refactor | bugfix | invariant_change | ceremony_update\n"
                "Example: refactor: renamed _hash_region helper without semantic change"
            )
            sys.exit(2)

        colon_idx = reason_raw.index(":")
        reason_category = reason_raw[:colon_idx].strip()
        reason_text = reason_raw[colon_idx + 1:].strip()

        if reason_category == "invariant_change" and "--confirm-governance" not in sys.argv:
            print(
                "[invariant_gate] ERROR: reason_category='invariant_change' requires --confirm-governance.\n"
                "This category signals an intentional change to a frozen protocol invariant.\n"
                "Re-run with: --confirm-governance"
            )
            sys.exit(2)

        if "--confirm-governance" in sys.argv:
            print(
                "[GOVERNANCE WARNING] You are about to change a frozen protocol invariant.\n"
                "This action will be logged as a tamper-evident governance event on-chain.\n"
                "Every node in the network will observe this change in the next Merkle anchor."
            )
            time.sleep(3)
            try:
                phrase = input("Type confirmation phrase: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[invariant_gate] Governance confirmation aborted.")
                sys.exit(3)
            if phrase != _GOVERNANCE_PHRASE:
                print(
                    f"[invariant_gate] Confirmation phrase mismatch.\n"
                    f'Expected: "{_GOVERNANCE_PHRASE}"'
                )
                sys.exit(3)

        results = check_invariants(proposal_type=proposal_type)
        generate_allowlist(results, reason_category=reason_category, reason_text=reason_text)

    elif "--report" in sys.argv:
        sys.exit(run_gate(report_only=True, proposal_type=proposal_type))
    else:
        sys.exit(run_gate(proposal_type=proposal_type))

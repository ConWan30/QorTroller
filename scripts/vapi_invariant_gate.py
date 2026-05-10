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
]


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


def check_invariants() -> list[dict]:
    """Run all invariant checks. Returns list of result dicts."""
    results = []
    for inv in INVARIANTS:
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
        pass
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


def run_gate(report_only: bool = False) -> int:
    """Run invariant gate. Returns 0=pass, 1=fail."""
    results = check_invariants()
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


if __name__ == "__main__":
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

        results = check_invariants()
        generate_allowlist(results, reason_category=reason_category, reason_text=reason_text)

    elif "--report" in sys.argv:
        sys.exit(run_gate(report_only=True))
    else:
        sys.exit(run_gate())

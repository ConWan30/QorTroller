---
title: "VEDIP-0001: Verified Engineering Discipline Retrospective"
date: 2026-05-11
proposal_type: VEDIP
proposal_number: "0001"
status: "RETROSPECTIVE-SPEC v1.0"
scope: "VAPI-internal engineering methodology"
authority: "VAPI Architect; bridge wallet 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692"
depends_on:
  - "VBDIP-0001-vad-framework-introduction.md"
related_commits:
  - "44c26ce0"
  - "4ddeb43c"
  - "79dacc88"
  - "2cde36a3"
  - "d6830525"
  - "0791c935"
  - "c2510883"
  - "7341ee66"
wallet_impact: "0 IOTX"
chain_impact: "none"
---

# VEDIP-0001: Verified Engineering Discipline Retrospective

## 0. Reading Note

VEDIP-0001 is retrospective. It does not authorize a new chain action, does not
change a Cedar bundle, does not regenerate the PV-CI allowlist, and does not
rename any invariant in source control.

This document names the engineering discipline that VAPI has already been
practicing across protocol work: V-checks before mutation, P-checks between
streams, atomic commits, operator Decision blocks, provenance capture,
wallet-risk separation, and PV-CI freeze gates.

VBDIP-0001 introduced the top-level VAD framework and named VED as the
engineering-domain sub-discipline. VEDIP-0001 supplies the missing
retrospective record for that sub-discipline.

## 1. Executive Statement

The Verified Engineering Discipline (VED) governs VAPI's protocol-side
engineering work.

VED is not a new engineering process invented after the fact. It is the name
for the process that was already operating during:

- Phase O0 Operator Initiative bootstrap
- Phase O1-FRR-PARALLEL
- Stream J live-data correction
- Parallel O2 SUGGEST anchor
- VBDIP-0001 secure methodology integration
- Phase O3-ZKBA-TRACK1 engineering surface

The discipline is simple but load-bearing:

1. Verify the current state before writing.
2. Preserve drift findings instead of editing them away.
3. Make each meaningful boundary locally revertible.
4. Separate filesystem-only work from wallet-risk work.
5. Require explicit operator authorization at chain boundaries.
6. Freeze protocol-critical surfaces with PV-CI invariants.
7. Keep source identifiers stable; use methodology aliases only in docs.

VED makes VAPI's engineering history auditable as engineering, not merely as a
sequence of commits.

## 2. Scope

VED governs protocol-side artifacts:

- bridge service code
- store migrations and helper APIs
- SDK wire contracts
- operator API endpoints
- Cedar bundle authoring and validation
- operator-agent advancement scripts
- on-chain deployment and anchoring procedures
- PV-CI invariant checks
- FROZEN-v1 primitive implementation work
- tournament-integrity and biometric-corpus engineering
- controller calibration and probe-pipeline engineering

VED does not govern synthesis notes as primary artifacts. Synthesis notes remain
VSD-governed, even when they describe engineering work. VED also does not govern
bridge-composition primitives whose purpose is to compose VSD and VED surfaces;
those are VBD-governed.

## 3. What VED Names

### 3.1 V-check Discipline

A V-check is the pre-mutation verification pass. It asks: what is true in the
tree, the store schema, the chain state, the tests, and the active docs right
now?

VED treats a failed assumption as information. The Stream J canonical-name
versus Q9-hex mismatch is the canonical example: the watcher was correct in
tests but wrong against production-shaped data. VED did not hide the mismatch;
it converted the mismatch into a regression test and a design rule.

### 3.2 P-check Discipline

A P-check is the inter-stream coherence pass. It asks whether one stream's
output breaks another stream's assumptions.

Phase O1-FRR-PARALLEL used this repeatedly: FRR, watcher helpers, gas-buffer
hardening, the parallel anchor script, and the runbook were separate surfaces,
but each had to preserve the same phase-alignment model.

### 3.3 Atomic Commit Boundaries

VED prefers small, meaningful commits over large narrative bundles. The ideal
commit is:

- reversible with `git revert`
- scoped to one engineering boundary
- accompanied by tests or an explicit no-test reason
- explicit about wallet and chain impact
- linked to the operator decision or V-check that justified it

This is why the VBDIP-0001 integration landed as five separate steps instead
of one large migration commit.

### 3.4 Decision Blocks

VED uses Decision blocks at irreversible or policy-relevant boundaries:

- missing artifact disposition
- contract-count reconciliation
- numbering decisions
- chain submission authorization
- kill-switch lift
- signing or key-generation boundaries

Decision blocks preserve operator authority procedurally. They are not merely
polite pauses.

### 3.5 Wallet-Risk Separation

VED treats wallet impact as a first-class engineering dimension. A filesystem
phase and a chain phase are different categories of work even when they are part
of the same feature arc.

Phase O3-ZKBA-TRACK1 is the current model: Track 1 shipped the sidecar spec,
primitive, store schema, deterministic compiler, MCP tools, SDK client, PV-CI
invariants, bridge HTTP endpoints, and whitepaper sync with zero wallet impact.
Track 2 remains gated because it includes Cedar v2 re-anchoring and direct
wallet risk.

### 3.6 PV-CI Freeze Discipline

PV-CI invariants are not decorations around the code. They are the frozen memory
of protocol-critical byte layouts, constants, gate patterns, and wire-contract
names.

VED uses PV-CI to make "future refactor safety" mechanical. If a future edit
changes a frozen surface, the invariant gate breaks before the change becomes
quiet drift.

## 4. Retrospective Corpus

### 4.1 Phase O0 Operator Initiative Bootstrap

Phase O0 closed on 2026-05-03 at commit `44c26ce0`, with eighteen commits
across five streams and 44 total commits at closure.

VED retroactively recognizes Phase O0 as engineering-discipline work because
the phase already used the core VED practices:

- V-checks before execution
- P-checks between streams
- atomic commit boundaries
- explicit operator Decision blocks
- hold-for-approval gates between meaningful checkpoints
- wallet-risk accounting

The later VAD naming did not create this discipline. It named what the phase
had already proved viable.

### 4.2 Phase O1-FRR-PARALLEL

Phase O1-FRR-PARALLEL shipped in commit `4ddeb43c`.

VED recognizes this as the first fully visible engineering-discipline exemplar
after Phase O0. It shipped:

- Fleet Readiness Root (FRR) as a FROZEN-v1 primitive
- production store helpers that previously existed only in tests
- advancement log persistence
- gas-buffer hardening for storage-heavy Cedar anchoring
- `scripts/parallel_o2_anchor.py` with a triple-gate operator pattern
- Curator mainnet-migration runbook
- PV-CI invariants for FRR, parallel-anchor gating, and Curator O2 bundle scope

The FRR work matters methodologically because it joined live operator-agent
phase state, store state, deterministic hashing, and operator-facing scripts
without requiring a contract change.

### 4.3 Stream J Empirical Correction

Stream J landed in commit `79dacc88`.

It closed two live-data findings:

- production activation rows use Q9-frozen agent IDs while watcher logic had
  been querying by canonical names
- `next_alignment_target` incorrectly resolved from readiness counts instead of
  actual current phase after the fleet reached O2_SUGGEST

VED classifies Stream J as a verification-gap closure. It is the clearest
example of why tests must include production-shaped identifiers, not only
friendly canonical names.

Resulting VED rule: any future feature touching activation, shadow, or drift
tables must either accept Q9 hex directly or pass through the canonical-to-Q9
resolver.

### 4.4 Parallel O2 SUGGEST Anchor

The parallel O2 SUGGEST anchor landed in commit `2cde36a3`.

VED recognizes this as wallet-risk engineering, not merely an execution event.
The phase advanced Sentry, Guardian, and Curator from O1_SHADOW to O2_SUGGEST
through six sequential dual-anchor transactions under the triple-gate pattern:

- `CHAIN_SUBMISSION_PAUSED=false` in process scope
- `OPERATOR_INITIATIVE_O2_AUTHORIZED=true` in process scope
- `--confirm` at the CLI boundary

The phase also verified scope roots on chain and wrote advancement-log state.
The kill-switch returned to true after execution. This established the current
VED standard for chain-facing operator scripts.

### 4.5 VBDIP-0001 Integration Lessons

VBDIP-0001 itself is a VBD document, but its integration procedure produced
VED lessons:

- hash the deferred input state before moving or editing artifacts
- land the provenance witness before normalization
- normalize inventory as a separate reversible commit
- reconcile state drift in one named amendment commit
- create the signing chain before freezing a signed proposal
- freeze only after PV-CI passes against the final state

The file `wiki/methodology/INTEGRATION_PROVENANCE_2026-05-10.md` is therefore
also a VED pattern: a deferral-boundary witness for engineering integration.

### 4.6 Phase O3-ZKBA-TRACK1 Engineering Surface

Phase O3-ZKBA-TRACK1 is VBD-governed at the category level because ZKBA bridges
protocol primitives into visual proof artifacts. Its implementation, however,
contains VED-governed engineering:

- `bridge/vapi_bridge/zkba_artifact.py`
- `zkba_artifact_log` store schema
- deterministic compiler checks
- bridge HTTP endpoints for `VAPIZKBA`
- SDK result dataclasses and fail-open client behavior
- endpoint and SDK round-trip tests
- PV-CI invariants `INV-ZKBA-001` through `INV-ZKBA-003`

The key VED lesson is the same as the Track 1 / Track 2 split: proof-artifact
read surfaces can ship wallet-free, while chain anchoring must remain behind
explicit activation gates.

## 5. VED-INV-N Mapping Discipline

`VED-INV-N` is a documentation alias.

It is not a source-code rename. It does not modify
`.github/INVARIANTS_ALLOWLIST.json`. It does not change
`scripts/vapi_invariant_gate.py`. It does not require future invariant IDs to
start with `VED-`.

At VBDIP-0001 authoring, the existing protocol-invariant set was described as
55 VED-governed invariants. By VEDIP-0001 authoring, the unified PV-CI allowlist
contains 69 entries:

- 66 engineering/protocol entries, documented here as `VED-INV-001` through
  `VED-INV-066`
- 3 bridge-composition entries, natively named `VBD-INV-001` through
  `VBD-INV-003`

The Appendix A table is the canonical VEDIP-0001 mapping at this authoring
boundary. Future VEDIPs may append to the mapping, but they must not rewrite
native PV-CI IDs.

## 6. Boundary With VBD

VED governs engineering execution. VBD governs bridge composition.

Examples:

- Implementing `compute_fleet_readiness_root` is VED work.
- Composing FRR with VRR into CDRR is VBD work.
- Implementing the ZKBA store schema is VED work.
- Defining ZKBA as a bridge category between proof manifests, visual
  projections, and stakeholder trust is VBD work.
- Adding a PV-CI invariant for a frozen domain tag is VED work.
- Naming primitive composition discipline across PATTERN-017 is VBD work.

This boundary prevents VED from absorbing the whole methodology. The VAD
framework remains one framework with three domains.

## 7. Acceptance Criteria

VEDIP-0001 is complete when:

1. The retrospective corpus is named.
2. The VED practices are described as engineering practices, not synthesis
   practices.
3. `VED-INV-N` is locked as a documentation alias only.
4. The current PV-CI mapping is captured without renaming native IDs.
5. Wallet impact is zero.
6. Chain impact is zero.
7. `CHAIN_SUBMISSION_PAUSED=true` remains unchanged.

## 8. Decision Blocks

### K1: VED Recognition

Decision: VED is recognized as the engineering-domain sub-discipline under VAD.

Rationale: The engineering process already existed across Phase O0, FRR, Stream
J, and O2 anchoring. Naming it improves auditability without changing the
process.

### K2: Documentation Alias

Decision: `VED-INV-N` is a documentation alias over engineering/protocol PV-CI
entries.

Rationale: Native invariant IDs carry phase and surface history. Renaming them
would destroy useful provenance and produce churn without safety benefit.

### K3: Wallet Boundary

Decision: VED separates wallet-free implementation from wallet-risk execution.

Rationale: VAPI's strongest operational discipline is knowing exactly when an
engineering action becomes a chain action.

### K4: Drift Preservation

Decision: V-check drift findings remain part of the record.

Rationale: Drift findings are evidence. Editing them away would weaken the
methodology's ability to learn from live-state mismatches.

### K5: VBD Boundary

Decision: VED does not absorb VBD-native bridge-composition invariants.

Rationale: VBD exists because composition between protocol and synthesis became
load-bearing enough to require its own domain.

## 9. Future VED Work

VEDIP-0001 is retrospective. Future VEDIPs may be prospective.

Likely future documents:

- VEDIP-0002: Chain-Facing Operator Script Standard
- VEDIP-0003: Store Migration and Helper API Standard
- VEDIP-0004: SDK Wire-Contract Parity Standard
- VEDIP-0005: Hardware-Capture Phase Boundary Standard

Those documents should be authored only when a repeated engineering pattern has
enough evidence to justify standardization.

## Appendix A: PV-CI Mapping at VEDIP-0001 Authoring Boundary

The table below maps engineering/protocol PV-CI entries to VED documentation
aliases. Native IDs remain unchanged in source control.

| VED alias | Native PV-CI ID | Frozen surface |
|-----------|-----------------|----------------|
| VED-INV-001 | INV-001 | PoAC body = 164 bytes (wire format frozen) |
| VED-INV-002 | INV-002 | Chain link hash = SHA-256(raw[:164]) |
| VED-INV-003 | INV-003 | L4 anomaly threshold literal 7.009 |
| VED-INV-004 | INV-004 | L4 continuity threshold literal 5.367 |
| VED-INV-005 | INV-005 | Phase 62 ZK: Poseidon(8) / nPublic=5 |
| VED-INV-006 | INV-006 | Hard cheat codes 0x28/0x29/0x2A in dualshock |
| VED-INV-007 | INV-007 | Stable EMA updates NOMINAL sessions only |
| VED-INV-008 | INV-008 | L6_CHALLENGES_ENABLED default=False |
| VED-INV-009 | INV-009 | GSR_ENABLED default=False |
| VED-INV-010 | INV-010 | L6B_ENABLED default=False |
| VED-INV-011 | INV-011 | BLOCK_QUORUM=0.67 in ioswarm modules |
| VED-INV-012 | INV-012 | MINT_QUORUM=0.80 in ioswarm VHP mint |
| VED-INV-013 | INV-013 | PoAC record total 228 bytes in chain.py |
| VED-INV-014 | INV-014 | Phase 66 commitment hash formula (verdict+evidence+attestation) |
| VED-INV-015 | INV-015 | Phase 67 circuitId = sha3_256(circuitName.encode()) |
| VED-INV-016 | INV-016 | Allowlist hash included as virtual leaf in ProtocolCoherenceAgent Merkle root |
| VED-INV-017 | INV-017 | Audit script split regex: 4-space indent anchor, not column-0 |
| VED-INV-018 | INV-018 | Audit script block-search through `_AUTH_CALLS`; no character-window limit |
| VED-INV-019 | INV-019 | Provenance hash computation function exists in gate script |
| VED-INV-020 | INV-020 | `ts_ns` included as 8-byte big-endian in provenance hash |
| VED-INV-021 | INV-021 | Latest provenance hash fetch function exists in gate script |
| VED-INV-022 | INV-022 | `governance_provenance_chain` table and insert method exist |
| VED-INV-023 | INV-023 | GIC formula v1 byte layout frozen |
| VED-INV-024 | INV-024 | GIC `ts_ns` ordering uses `gic_ts_ns DESC` |
| VED-INV-025 | INV-025 | GIC chain-broken flag and setter exist on Store |
| VED-INV-026 | INV-026 | PCC status and readiness paths recompute before reads |
| VED-INV-027 | INV-CORPUS-001 | `anchor_corpus_snapshot` async function exists in `chain.py` |
| VED-INV-028 | INV-CORPUS-002 | `VAPI_CORPUS_SNAPSHOT_v1` deviceIdHash literal pinned |
| VED-INV-029 | INV-AGENT-COMMIT-001 | `compute_agent_commit_hash` function exists |
| VED-INV-030 | INV-AGENT-COMMIT-002 | `VAPI-AGENT-COMMIT-v1` domain tag literal pinned |
| VED-INV-031 | INV-PDA-001 | `compute_pda_hash` function exists |
| VED-INV-032 | INV-PDA-002 | `VAPI-PHYSICAL-DATA-ATTESTATION-v1` domain tag literal pinned |
| VED-INV-033 | INV-PCC-002 | PCC `update_sample` preserves backward-compatible game-context params |
| VED-INV-034 | INV-PCC-003 | Explicit disconnect overrides SPC classification |
| VED-INV-035 | INV-PCC-004 | Haptic-tolerance binding requires all three signals |
| VED-INV-036 | INV-PCC-005 | Haptic-tolerance tremor band is bounded |
| VED-INV-037 | INV-CEDAR-001 | `canonical_bytes` exists for Cedar Merkle determinism |
| VED-INV-038 | INV-CEDAR-002 | `VAPI-CEDAR-BUNDLE-v1` domain tag literal pinned |
| VED-INV-039 | INV-CEDAR-003 | Cedar schema frozensets are pinned |
| VED-INV-040 | INV-OPERATOR-AGENT-001 | Cedar bundle anchor operational-first sequence is preserved |
| VED-INV-041 | INV-OPERATOR-AGENT-002 | `operator_agent_activation_log` anti-replay constraint is preserved |
| VED-INV-042 | INV-APOP-001 | APOP states and gate modes are frozen |
| VED-INV-043 | INV-APOP-002 | APOP scoring weights sum to 1.00 |
| VED-INV-044 | INV-OPERATOR-AGENT-003 | Shadow log idempotency is preserved |
| VED-INV-045 | INV-OPERATOR-AGENT-004 | Cedar shadow runtime fails open to default deny |
| VED-INV-046 | INV-OPERATOR-AGENT-005 | Cedar shadow runtime recomputes bundle Merkle root per evaluation |
| VED-INV-047 | INV-OPERATOR-AGENT-006 | Drift log sweep idempotency is preserved |
| VED-INV-048 | INV-OPERATOR-AGENT-007 | Drift-type literals are frozen |
| VED-INV-049 | INV-OPERATOR-AGENT-008 | Cedar drift sweeper dual-cadence defaults are frozen |
| VED-INV-050 | INV-FRR-001 | `compute_fleet_readiness_root` function exists |
| VED-INV-051 | INV-FRR-002 | `FRR_DOMAIN_TAG = b"VAPI-FRR-v1"` |
| VED-INV-052 | INV-FRR-003 | FRR pre-image byte order is frozen |
| VED-INV-053 | INV-PARALLEL-ANCHOR-001 | `parallel_o2_anchor.py` triple-gate pattern is frozen |
| VED-INV-054 | INV-CURATOR-O2-001 | Curator O2 bundle Merkle root is frozen |
| VED-INV-055 | INV-CURATOR-O2-002 | Curator O2 lane-prefix array is preserved |
| VED-INV-056 | INV-O3-WATCHER-001 | O3 watcher bundle filename phase resolver is backward-compatible |
| VED-INV-057 | INV-O3-WATCHER-002 | O3 watcher gate thresholds are frozen |
| VED-INV-058 | INV-O3-WATCHER-003 | O3 ACTING bundle Merkle roots are locked |
| VED-INV-059 | INV-O1-FRR-SDK-001 | `VAPIFleetReadinessRoot` SDK client class exists |
| VED-INV-060 | INV-O1-FRR-SDK-002 | FRR SDK dataclass names are frozen |
| VED-INV-061 | INV-O3-UI-DRAWER-001 | OperatorAgentsDrawer z-index 20 is preserved |
| VED-INV-062 | INV-O3-UI-DRAWER-002 | DraftReviewDrawer z-index 21 is preserved |
| VED-INV-063 | INV-O3-UI-DRAWER-003 | O3ReadinessDrawer z-index 22 is preserved |
| VED-INV-064 | INV-ZKBA-001 | `compute_zkba_commitment` function exists |
| VED-INV-065 | INV-ZKBA-002 | `VAPI-ZKBA-ARTIFACT-v1` domain tag literal is pinned |
| VED-INV-066 | INV-ZKBA-003 | `vapi-zkba-manifest-v1` manifest schema string is pinned |
| VED-INV-067 | INV-VPM-WRAPPER-001 | `vapi-vpm-manifest-v1` wrapper schema string is pinned (added 2026-05-12 per Operator Decision Matrix D-PV-VPM Option P3) |

## Appendix B: VBD-Native Entries Present in the Same Allowlist

These entries live in the unified PV-CI allowlist but are not VED aliases.
They remain VBD-native because they govern bridge-composition discipline.

| Native ID | Frozen surface |
|-----------|----------------|
| VBD-INV-001 | Continuous deployer-verified provenance under fleet expansion |
| VBD-INV-002 | Fleet-domain replication discipline |
| VBD-INV-003 | Primitive composition discipline |

## Appendix C: Authoring Boundary

Authoring boundary:

- repository branch: `main`
- preceding pushed commit: `7341ee66`
- bridge tests at boundary: 2942
- SDK tests at boundary: 550
- Hardhat tests at boundary: 528
- PV-CI entries at boundary: 69
- wallet impact of this document: 0 IOTX
- on-chain impact of this document: none
- kill-switch posture verified locally: `CHAIN_SUBMISSION_PAUSED=true`

This document intentionally does not run a signing ceremony. The architect
signing chain established by VBDIP-0001 remains available for any future
operator-authorized formal manifest.

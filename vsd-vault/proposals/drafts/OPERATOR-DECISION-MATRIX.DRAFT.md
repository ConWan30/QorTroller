---
title: "VAPI Operator Decision Matrix — Pending Decisions Consolidated"
date: 2026-05-12
proposal_type: OPERATOR-INDEX
proposal_number: "DM-2026-05-12"
status: "DRAFT / OPERATOR-FACING"
scope: "Documentation-only. No PV-CI mutation. No code change. No execution."
authority: "VAPI Architect; bridge wallet 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692"
wallet_impact: "0 IOTX"
chain_impact: "none"
---

# VAPI Operator Decision Matrix — Pending Decisions Consolidated

## 0. Reading Note

This document is an INDEX, not a decision. It surfaces every pending
operator decision across the VAPI methodology surface as of 2026-05-12
into a single addressable artifact, grouped by gating dependency. Each
decision row references its source proposal / sidecar document and
captures the cost-if-acted vs risk-if-deferred trade-off.

The matrix is a "next-session entry artifact": an operator returning
to VAPI work can read this document first and see the entire decision
landscape without re-discovering it from scattered commit messages,
§18 status logs, or sidecar drafts.

This document is operator-facing. It does not execute any decision.
Each decision row points to the source proposal that, when operator-
authorized, ships the resolution as a follow-up commit. Some decisions
have explicit DRAFT proposals already authored; others are documented
here for the first time.

---

## 1. Decision Landscape Overview

**Sixteen pending operator decisions** organized into five clusters by
gating dependency:

| Cluster | Decisions | Why grouped |
|---|---|---|
| **A. Numbering** | D-NUM | Foundational; gates multiple downstream decisions |
| **B. Schema names** | D-SCHEMA-A, D-SCHEMA-B | §9.2 V-check finding resolution |
| **C. Sidecar residuals** | D-SIDECAR-0002A | VBDIP-0002A §§6,8,10 long-term fate |
| **D. PV-CI candidates** | D-PV-VPM | Programmatic enforcement of VPM wrapper FROZEN constants |
| **E. Track 2 activation** | D-TRACK2-G6, D-TRACK2-G7, D-TRACK2-G8, D-TRACK2-G9, D-TRACK2-C6, D-TRACK2-C7, D-TRACK2-C8, D-TRACK2-KILLSWITCH, D-TRACK2-WALLET, D-TRACK2-FSCA | Track 2 §16 + B.8 activation criteria; gated on operator authorization + kill-switch lift + ≥1.0 IOTX |
| **F. Lane B expansion** | D-LANE-B-G3 | When DEMO/FROZEN_DISABLED/marketplace ZKBA classes ship |

Total: 16 decisions. Wallet impact across all 16: 0 IOTX for clusters
A/B/C/D/F; ~0.23 IOTX projected for cluster E if all Track 2 gates
clear.

---

## 2. Cluster A — Numbering

### D-NUM — N1 / N2' / N3 numbering for VBDIP-0002

**Source documents:**
- `wiki/methodology/VBDIP-0002-zkba-visual-projections.md` §1.3 + §16 G2 + G9
- Appendix B (v1.1 amendment) B.8 G2

**The question:** What canonical proposal number does VBDIP-0002
claim?

| Option | Action | Effect |
|---|---|---|
| **N1** | Amend VBDIP-0001 to relocate Phase O1-VAD-MIGRATE to VBDIP-0004+ | VBDIP-0002 owns the 0002 slot permanently |
| **N2'** | Renumber VBDIP-0002 → VBDIP-0004 (or later; not 0003 per VBDIP-0001 §3.3) | Preserves VBDIP-0001 reservations; introduces numbering gap |
| **N3** | Keep as indefinite sidecar (`VBDIP-XXXX-ZKBA-DRAFT`) | Safest; no lineage commitment; citation-drift risk |

**Status:** PENDING — operator-decision only.
**Cost if acted on:** Methodology-only. ~30 minutes of cross-doc cite
updates per choice. No PV-CI / no code / no chain.
**Risk if deferred:** Citation drift accumulates over time as more
methodology docs reference VBDIP-0002 by uncommitted number.
**Dependencies:** None upstream. Downstream: D-TRACK2-G9 (Numbering
Decision Applied) gates Track 2 final activation.

---

## 3. Cluster B — Schema Names

### D-SCHEMA-A — VBDIP-0002 §9.2 schema-name drift resolution

**Source document:**
- `vsd-vault/proposals/drafts/VBDIP-0002-schema-name-reconciliation.DRAFT.md`
  (commit `f17622c0`)

**The question:** How is the §9.2-text-vs-implementation drift
resolved?

| Layer | Schema name literal |
|---|---|
| §9.2 spec design-time text | `zkba.projection_manifest.v1` |
| `scripts/vsd_ui_compiler.py:58` implementation | `vapi-zkba-manifest-v1` |
| PV-CI INV-ZKBA-003 pin | `vapi-zkba-manifest-v1` |

**Options analyzed in the proposal:**

- **Option A** Edit §9.2 in place — REJECTED (violates supersession)
- **Option B** Migrate implementation to spec name — requires governance ceremony + ~12 file edits
- **Option C** Codify bilateral acceptance via v1.2 amendment Appendix C — **RECOMMENDED**
- **Option D** Defer indefinitely — REJECTED (methodology-integrity debt)

**Status:** PENDING — proposal authored; awaiting operator authorization
of one of A/B/C/D.
**Cost if acted on:** Option C is methodology-only (~150-line Appendix
C addition). Option B is operator-authorized governance ceremony +
multi-file change. Options A/D are not recommended.
**Risk if deferred:** Validator's `schema_name_form` field continues
to surface drift to external tooling without canonical resolution.
**Dependencies:** None upstream.

### D-SCHEMA-B — VPM wrapper schema (vapi-vpm-manifest-v1)

**Source document:**
- `wiki/methodology/VBDIP-0002-zkba-visual-projections.md` Appendix B
  B.4 (v1.1 amendment)
- `scripts/vsd_vpm_wrapper.py` (G5b implementation, commit `72b056e8`)

**The question:** Does VPM wrapper schema name `vapi-vpm-manifest-v1`
need a PV-CI invariant pin (analogous to INV-ZKBA-003 for ZKBA
manifest schema)?

**Status:** PENDING — see D-PV-VPM (cluster D) for the PV-CI question.
The schema name itself is FROZEN in the wrapper module + tested by
static guards at G5b; the open question is whether to elevate it to a
PV-CI invariant.
**Cost if acted on:** See D-PV-VPM.
**Risk if deferred:** Low. Wrapper module's own static guard tests
verify the FROZEN literal at every test run; PV-CI elevation would
add CI gate enforcement but is not load-bearing for the validator's
mechanical enforcement.
**Dependencies:** None.

---

## 4. Cluster C — Sidecar Residuals

### D-SIDECAR-0002A — VBDIP-0002A §§6, 8, 10 long-term fate

**Source document:**
- `vsd-vault/proposals/drafts/VBDIP-0002A-verified-projection-media.DRAFT.md`
  (PARTIALLY ABSORBED at commit `3461b636`)

**The question:** What happens to the three sections retained in
VBDIP-0002A sidecar after the v1.1 D-MERGE absorbed the other nine?

The three retained sections:

- §6 Stakeholder Utility Layer (audience-specific framing)
- §8 Curator Marketplace Lane (Curator agent-specific behavior)
- §10 VPM Projection Registry (10 Reserved VPM IDs + lifecycle ladder)

**Options:**

| Option | Action |
|---|---|
| **S1** | Keep as VBDIP-0002A indefinite sidecar; reference from VBDIP-0002 by path |
| **S2** | Defer to future VBDIP-0002B numbered proposal once VPM registry stabilizes (registry IDs transition Reserved → Active) |
| **S3** | Absorb into VBDIP-0002 via v1.x amendment once registry IDs mature |

**Status:** PENDING — no urgency. Sidecar pattern is methodologically
valid; D-MERGE-SELECTIVE chose S1 as the working state per reconciliation
plan §3.
**Cost if acted on:** Each option is docs-only.
**Risk if deferred:** Low. The three retained sections are
stakeholder-framing + registry-maintenance content; they don't gate
any downstream work.
**Dependencies:** None.

---

## 5. Cluster D — PV-CI Candidates

### D-PV-VPM — INV-VPM-WRAPPER-001 candidate

**Source documents:**
- `scripts/vsd_vpm_wrapper.py` (G5b implementation, commit `72b056e8`)
- `wiki/methodology/VBDIP-0002-zkba-visual-projections.md` B.5
  (VPM-HONESTY-001 namespace lock)
- `vsd-vault/proposals/drafts/VBDIP-0002-vs-0002A-reconciliation.DRAFT.md`
  §4 (VPM-HONESTY-001 stays methodology-doc identifier)

**The question:** Should a new PV-CI invariant pin the VPM wrapper
FROZEN constants (schema name `vapi-vpm-manifest-v1`, version
`0.1.0`, 5 FROZEN closed enums)?

**Context:** VPM-HONESTY-001 is locked as a methodology-doc
identifier per reconciliation plan §4 — it does NOT enter the PV-CI
allowlist. But that lock was about the VPM-HONESTY-001 IDENTIFIER,
not about whether the WRAPPER itself gets PV-CI coverage. The
distinction matters: VPM-HONESTY-001 names the visual-honesty
discipline (methodology); INV-VPM-WRAPPER-001 (if introduced) would
pin the wrapper's FROZEN literals (implementation).

**Options:**

| Option | Action | Discipline alignment |
|---|---|---|
| **P1** | Author INV-VPM-WRAPPER-001 pinning `vapi-vpm-manifest-v1` + wrapper version + 5 enum value sets in `scripts/vsd_vpm_wrapper.py` | Mirrors INV-ZKBA-001/002/003 pattern; ~5-7 new PV-CI entries; allowlist regen requires `--confirm-governance` ceremony |
| **P2** | Defer; rely on G5b static guard tests (already shipped) for FROZEN-literal enforcement | No governance ceremony; no PV-CI allowlist change |
| **P3** | Author single INV-VPM-WRAPPER-001 pinning only the schema name string `vapi-vpm-manifest-v1` (mirroring INV-ZKBA-003 minimal-pin form) | One new PV-CI entry; minimal governance ceremony |

**Status:** PENDING — operator-decision required for `--confirm-governance`
ceremony.
**Cost if acted on:** Option P1 ~5-7 entries; Option P3 one entry.
Both require governance ceremony with phrase "I understand this
changes a frozen protocol invariant" + 3-second pause.
**Risk if deferred:** Low. G5b static guard tests (T-VPM-static-no-forbidden-imports,
T-VPM-static-wrapper-schema-string-pinned-in-source) already verify
the FROZEN literal at every test run. PV-CI elevation provides CI
gate enforcement at the protocol-invariant layer but is not
load-bearing for the wrapper's mechanical enforcement.
**Dependencies:** None.

---

## 6. Cluster E — Track 2 Activation

Track 2 ships Cedar v2 bundles + anchor script + ceremony per the
i-authorize-yours-to-precious-scone plan §6 (commits C6/C7/C8 in that
plan). Track 2 activation requires **ten** operator authorizations or
state verifications enumerated below.

### D-TRACK2-G6 — AgentScope / Cedar Permissions Authorized

**Source:** VBDIP-0002 §16 G6 (gate text); Appendix B B.8 G6.

**The question:** Have Sentry / Guardian / Curator each been
authorized via AgentScope / Cedar policy with phase-appropriate
permissions for their Section 8 lane actions?

**Status:** PENDING. Operator decision per agent. Three sub-decisions:

| Sub | Agent | Required action |
|---|---|---|
| G6-Sentry | Sentry | Authorize provenance lane writes via Cedar v2 bundle |
| G6-Guardian | Guardian | Authorize audit lane writes via Cedar v2 bundle |
| G6-Curator | Curator | Authorize marketplace lane writes via Cedar v2 bundle |

**Cost if acted on:** Operator-authorized Cedar bundle re-anchoring
ceremony per agent at ~0.05 IOTX per anchor.
**Risk if deferred:** Track 2 cannot proceed. Validator + visual
honesty surfaces all work without G6, but no agent can actually
write to the corresponding lanes on-chain.
**Dependencies:** None upstream. Downstream: gates D-TRACK2-C6.

### D-TRACK2-G7 — Curator Review Readiness

**Source:** VBDIP-0002 §16 G7; Appendix B B.8 G7.

**The question:** Can Curator classify proof weight, detect visual
dishonesty, and recommend quarantine WITHOUT mutating anchors or
consent state? Compatible with Phase 238-DRAFT-REVIEW-FRONTEND
surface?

**Status:** PENDING — operator-verification of Curator agent
capability. Phase 238 frontend surface already exists; verification
is whether Curator agent process is wired correctly to consume it.
**Cost if acted on:** Operator review of Curator agent code + frontend
integration; no wallet impact.
**Risk if deferred:** Track 2 cannot proceed.
**Dependencies:** Curator agent process must be running (currently at
O1_SHADOW; advances to O2_SUGGEST per separate operator-track ladder).

### D-TRACK2-G8 — Internal Projection First

**Source:** VBDIP-0002 §16 G8; Appendix B B.8 G8.

**The question:** Do GIC Continuity Ledger (§10.1) and CDRR DAG
(§10.3) ship BEFORE consumer ZKBA Market Card (§10.4)?

**Status:** PARTIALLY SATISFIED. GIC Continuity Ledger ships at G4
commit `3b3081d3` (Z4). CDRR DAG is post-bootstrap (Phase
O1-VSD-BOOTSTRAP) work — not Track 2 ZKBA scope.
**Cost if acted on:** CDRR DAG ship is post-bootstrap work; outside
Track 2 envelope.
**Risk if deferred:** Track 2 anchor ceremony may proceed without CDRR
DAG completion; operator decision required on whether G8 satisfaction
requires both targets or just GIC.
**Dependencies:** Phase O1-VSD-BOOTSTRAP for CDRR DAG.

### D-TRACK2-G9 — Numbering Decision Applied

**Source:** VBDIP-0002 §16 G9; Appendix B B.8 G9.

**The question:** Has D-NUM been resolved and the canonical proposal
number applied to all cross-references?

**Status:** PENDING — depends on D-NUM resolution.
**Cost if acted on:** Methodology-only doc updates after D-NUM picks
N1/N2'/N3.
**Risk if deferred:** Track 2 cannot reach activation under a
specific lineage member.
**Dependencies:** D-NUM (cluster A).

### D-TRACK2-C6 — Cedar v2 Bundles + FSCA Contradiction Rules

**Source:** Plan `i-authorize-yours-to-precious-scone.md` §6 C6
(streams A1 + A2).

**The question:** Author + ship the three Cedar v2 bundles + FSCA
contradiction rules for ZKBA?

**Streams:**

- **A1** Three new v2 bundle files at `bridge/vapi_bridge/cedar_bundles/`:
  - `anchor_sentry_o2_suggest_v2.json` adds `zk_artifacts/` lane
  - `guardian_o2_suggest_v2.json` adds `zk_verifications/` lane
  - `curator_o2_suggest_v2.json` adds `zk_listings/` lane
- **A2** Three new contradiction rules in
  `bridge/vapi_bridge/fleet_signal_coherence_agent.py`:
  - `ZKBA_PROOF_WEIGHT_MISMATCH` (HIGH)
  - `ZKBA_LANE_VIOLATION` (HIGH)
  - `ZKBA_VERIFICATION_KEY_STALE` (MEDIUM)

**Status:** PENDING — operator authorization required.
**Cost if acted on:** Cedar bundle Merkle root recomputation +
bundle.json authoring + FSCA rule code. Wallet 0 IOTX at A1/A2 (no
anchor yet). PV-CI candidate INV-ZKBA-004 (bundle schema hash;
design TBD at C6 execution).
**Risk if deferred:** Track 2 cannot proceed.
**Dependencies:** D-NUM (for v2 bundle naming consistency); D-TRACK2-G6
(authorization for the bundles to be anchored).

### D-TRACK2-C7 — Anchor Script + Draft Generator

**Source:** Plan §6 C7 (stream A3).

**The question:** Author `scripts/parallel_zkba_anchor.py` (triple-gate
operator-gated script) + extend `bridge/vapi_bridge/chain.py` with
`anchor_zkba_artifact` + wire Sentry/Guardian/Curator draft generators?

**Status:** PENDING — operator authorization.
**Cost if acted on:** ~0.05 IOTX per ZKBA anchor when fired (operator-
bounded; only when authorized).
**Risk if deferred:** Track 2 cannot anchor ZKBA artifacts on-chain.
**Dependencies:** D-TRACK2-C6 (bundles must exist before anchor script
references them).

### D-TRACK2-C8 — Cedar Bundle Re-Anchoring Ceremony

**Source:** Plan §6 C8 (stream A4).

**The question:** Execute the parallel-fleet dual-anchor ceremony for
the three v2 bundles?

**Status:** PENDING — operator authorization + kill-switch lift +
wallet ≥1.0 IOTX + no HIGH/CRITICAL FSCA contradictions.
**Cost if acted on:** ~0.18 IOTX (3 bundles × dual anchor; matches
VBDIP-0001 VAD-MIGRATE cost estimate).
**Risk if deferred:** Track 2 cannot reach full activation.
**Dependencies:** D-TRACK2-C7 (anchor script exists); D-TRACK2-KILLSWITCH;
D-TRACK2-WALLET; D-TRACK2-FSCA.

### D-TRACK2-KILLSWITCH — Kill-Switch Lift

**Source:** VBDIP-0002 §16 + plan §3 constraint 1.

**The question:** Set `CHAIN_SUBMISSION_PAUSED=false` AND
`OPERATOR_ZKBA_ANCHOR_AUTHORIZED=true` in process environment AND
pass `--confirm` at the CLI boundary?

**Status:** PENDING — operator three-factor authorization.
**Cost if acted on:** No code change. Process-env variables set.
**Risk if deferred:** Track 2 anchor ceremony cannot fire.
**Dependencies:** Independent of other gates; operator-only.

### D-TRACK2-WALLET — Wallet Balance ≥ 1.0 IOTX

**Source:** VBDIP-0002 §16 + plan §8 criterion 4.

**The question:** Is the bridge wallet
`0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` balance ≥ 1.0 IOTX at
ceremony time?

**Status:** SATISFIED at ~15.44 IOTX (67× margin against ~0.23 IOTX
projected cost).
**Cost if acted on:** No action (already satisfied).
**Risk if deferred:** N/A — already satisfied.
**Dependencies:** None.

### D-TRACK2-FSCA — No HIGH/CRITICAL FSCA Contradictions

**Source:** VBDIP-0002 §16 + plan §8 criterion 6.

**The question:** Are there active HIGH/CRITICAL contradictions in
`fleet_coherence_log`?

**Status:** OPERATOR-VERIFICATION REQUIRED at ceremony time. Query:
`GET /operator/fsca/contradictions?severity=HIGH,CRITICAL`.
**Cost if acted on:** Operator verification call.
**Risk if deferred:** Track 2 anchor ceremony may execute over an
unresolved contradiction window — methodologically unsound.
**Dependencies:** None upstream. Operator-verification at ceremony
moment.

---

## 7. Cluster F — Lane B Expansion

### D-LANE-B-G3 — Future ZKBA class shipping (DEMO / FROZEN_DISABLED / marketplace)

**Source:** B.8 G3 PARTIAL satisfaction (commit `aaaa1653`); §9.3 rules
2, 3, 4 N/A for GIC's CHAIN_ONLY profile.

**The question:** When do DEMO / FROZEN_DISABLED / marketplace
artifact classes get their compiler targets + visual honesty tests?

**Context:** §9.3 rules 2 (DEMO watermark), 3 (FROZEN_DISABLED never
active), 4 (revoked consent invalidates marketplace) require
capture_mode variations that GIC Continuity Ledger doesn't exhibit.
These rules become testable when DEMO / FROZEN_DISABLED / marketplace
classes ship with their own compile_zkba_*.py scripts.

**Options:**

| Option | Trigger |
|---|---|
| **L1** | Ship classes only when external demand surfaces (event-driven) |
| **L2** | Ship one representative class per quarter to expand coverage |
| **L3** | Defer indefinitely; B.8 G3 closes with "PARTIAL SATISFIED — active artifact set covered" forever |

**Status:** PENDING — operator-decision on cadence.
**Cost if acted on:** Per-class compile target ship: ~300-400 LOC +
~10-15 tests. Wallet 0 IOTX per ship (Track 1 work).
**Risk if deferred:** Visual honesty coverage stays incomplete for
non-CHAIN_ONLY profiles.
**Dependencies:** None.

---

## 8. Decision Sequencing — Suggested Order

For operator review session efficiency, the suggested sequencing:

### 8.1 First-pass decisions (no ceremony required)

1. **D-SCHEMA-A** §9.2 drift resolution — Option C recommended;
   methodology-only follow-up commit
2. **D-NUM** numbering — pick N1 / N2' / N3
3. **D-SIDECAR-0002A** sidecar fate — pick S1 / S2 / S3
4. **D-LANE-B-G3** expansion cadence — pick L1 / L2 / L3

These four decisions unblock subsequent work without requiring PV-CI
ceremony or wallet authorization.

### 8.2 Second-pass decisions (governance ceremony)

5. **D-PV-VPM** INV-VPM-WRAPPER-001 — pick P1 / P2 / P3; requires
   `--confirm-governance` ceremony if P1 or P3

### 8.3 Third-pass decisions (Track 2 activation cluster)

6. **D-TRACK2-G6** Cedar authority — three sub-decisions (Sentry /
   Guardian / Curator)
7. **D-TRACK2-G7** Curator review readiness verification
8. **D-TRACK2-G8** Internal Projection First verification (GIC
   already satisfies; CDRR DAG is post-bootstrap)
9. **D-TRACK2-G9** Numbering Decision Applied (depends on D-NUM)

These four gate the actual Track 2 ship.

### 8.4 Track 2 ship sequence (after gates clear)

10. **D-TRACK2-C6** Cedar v2 bundles + FSCA rules (wallet 0 IOTX)
11. **D-TRACK2-C7** Anchor script + draft generator (wallet 0 IOTX)
12. **D-TRACK2-FSCA** verify no HIGH/CRITICAL contradictions
13. **D-TRACK2-WALLET** verify ≥1.0 IOTX (already SATISFIED at 15.44)
14. **D-TRACK2-KILLSWITCH** three-factor authorization
15. **D-TRACK2-C8** ceremony fires (~0.18 IOTX)

### 8.5 Open-ended ongoing

16. **D-SCHEMA-B** VPM wrapper schema name — covered by D-PV-VPM
   resolution

---

## 9. Risk Posture

This matrix lists 16 pending decisions; cumulative risk if NONE are
acted on:

- **Methodology-integrity debt** grows: §9.2 drift, numbering drift,
  sidecar references drift
- **Track 2 cannot ship**: cluster E gates remain unresolved
- **Future operators face larger re-derivation cost** when returning
  to the work

Cumulative risk if **ALL** are acted on at once:

- **Operator review fatigue**: 16 decisions in one session is large
- **Coupled commit cost**: some decisions are coupled (D-NUM → D-TRACK2-G9);
  resolving out-of-order requires re-work

**Recommended posture:** First-pass (4 decisions; cluster B + A + C +
F) in one operator session. Second-pass (1 decision; cluster D) after
operator considers governance ceremony cost. Third-pass (4 decisions;
cluster E gates) when Track 2 ship is operator-authorized. Track 2
ship sequence (cluster E commits) follows once gates clear.

---

## 10. What This Matrix Does NOT Do

- Does not change any current state (FROZEN documents stay FROZEN;
  drafts stay drafts; partial-absorption status preserved).
- Does not authorize any decision.
- Does not re-author content from the source proposals (referenced
  by path; readers consult source for full detail).
- Does not propose new decisions beyond what's surfaced in source
  proposals or §18 status logs.
- Does not regenerate `.github/INVARIANTS_ALLOWLIST.json`.
- Does not run a signing ceremony.

This matrix is an INDEX. Each decision row points to a source
proposal that, when authorized, ships the resolution as a follow-up
commit.

---

## 11. Cross-References

Within VAPI methodology documents:

- `wiki/methodology/VBDIP-0001-vad-framework-introduction.md` (FROZEN)
- `wiki/methodology/VBDIP-0002-zkba-visual-projections.md` (FROZEN-SPEC
  v1.0 + v1.1 amendment Appendix B)
- `wiki/methodology/VEDIP-0001-engineering-discipline-retrospective.md`
- `vsd-vault/proposals/drafts/VBDIP-0002A-verified-projection-media.DRAFT.md`
  (PARTIALLY ABSORBED)
- `vsd-vault/proposals/drafts/VBDIP-0002-vs-0002A-reconciliation.DRAFT.md`
  (precedent reconciliation plan)
- `vsd-vault/proposals/drafts/VBDIP-0002-schema-name-reconciliation.DRAFT.md`
  (§9.2 drift resolution proposal)

Plan documents:

- `C:\Users\Contr\.claude\plans\i-authorize-yours-to-precious-scone.md`
  (Track 2 activation plan §6 + §8 activation criteria)

Architectural references:

- VBDIP-0002 §16 (9 activation gates) + Appendix B B.8 (11 sub-gates
  post v1.1 amendment)
- VEDIP-0001 Appendix A (PV-CI mapping)
- VBDIP-0001 §6.2 (vsd-vault/ → vad-vault/ deferred migration)

Drift trace commits (G4 reach trio):

- `210f841b` G4 validator (drift discovered)
- `53553047` MCP tool (drift surfaced via schema_name_form)
- `4f63c5d5` bridge HTTP (drift surfaced via schema_name_form)
- `e4ad7cde` SDK (drift surfaced via schema_name_form)
- `f17622c0` §9.2 reconciliation proposal authored

Authoring boundary:

- repository branch: `main`
- preceding pushed commit: `f17622c0`
- bridge tests at boundary: 3051
- SDK tests at boundary: 562
- Hardhat tests at boundary: 528
- PV-CI entries at boundary: 69
- wallet impact: 0 IOTX
- on-chain impact: none
- `CHAIN_SUBMISSION_PAUSED=true` verified

---

**End of Operator Decision Matrix draft.**

Sixteen decisions surfaced. Five clusters by gating dependency. Three
suggested review passes. Each decision row points to its source
proposal. Operator authorization controls which decisions advance;
this matrix changes none of them.

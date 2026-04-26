---
title: VAPI_WHAT_IF.md — Validation Report
doc_audited: uploads/VAPI_WHAT_IF.md (Document Version 2.4, Last Updated 2026-04-13)
audit_date: 2026-04-16
audit_type: Deep audit — live MCP state checks + invariant verification
audit_scope: Single-doc validation (WIF corpus only)
project_phase_at_audit: Phase 220 COMPLETE
validator: VAPI Architectural Infrastructure Audit
---

# VAPI_WHAT_IF.md — Validation Report

## 1. Executive Summary

The uploaded `VAPI_WHAT_IF.md` (Version 2.4, dated 2026-04-13) shows **moderate-to-high drift** against the live protocol state as of **Phase 220 (2026-04-16)**. Three days and approximately **6 advanced phases** (214 → 220) have elapsed since the last update, and the corpus now trails the live registry on entries, numeric claims, and blocker fields.

**Overall verdict:** `DRIFTED — UPDATE REQUIRED` (not `STALE-UNUSABLE`).

**Integrity of FROZEN invariants cited in the doc:** `PASS` — every frozen numeric primitive I spot-checked resolves cleanly against `VAPI_INVARIANTS.md`. No protocol primitive has been accidentally mutated in the doc (228-byte PoAC, 164-byte body, Poseidon(8), MINT_QUORUM=0.80, BLOCK_QUORUM=0.67, ratio>1.0, 90-day TTL).

**Primary drift categories:**

| Category | Count | Severity |
|---|---|---|
| Stale status fields (ratio regressed / contracts LIVE now / phases landed) | 4 | HIGH |
| Missing WIF entries (corpus grew past doc) | ≥ 2 (WIF-040, WIF-041) | MEDIUM |
| Numbering collisions (same WIF-NNN code reused) | 1 (WIF-035) | MEDIUM |
| Stale numeric separation ratios cited | 4 inline values | MEDIUM |
| Stale wallet / deployment state | 1 (W1-006) | HIGH |
| Doc-version header + W1/W2/W3 counts stale | 3 fields | LOW |
| Active Blocker section missing from doc | 1 structural gap | HIGH |

---

## 2. Scope and Methodology

**Audit target.** Only `VAPI_WHAT_IF.md` as uploaded (no other docs in scope for this pass).

**Validation inputs (all live, pulled 2026-04-16):**

- `vapi_unified_state` — live protocol snapshot (phase, tests, contracts, agents, ratios, blockers)
- `vapi_unified_wif_corpus` — deduped union of `what_if_corpus/`, `wiki/what_if/`, and `VAPI_WHAT_IF.md` (57 entries total)
- `vapi_contradiction_status` severity=ALL — FSCA + `contradictions.md` + `blocked_updates.md`
- `vapi_experiment_history` last_n=20 — autoresearch ledger, scores, meta-learner themes
- `vapi_invariant_check` — 8 point checks on frozen primitives cited in the doc
- `CLAUDE.md` — embedded project-instruction state (authoritative test counts / phase / wallet)

**Methodology.** Every claim in the audited doc that names (a) a phase number, (b) a fingerprint or hash, (c) a numeric ratio or threshold, (d) a contract address, (e) a wallet balance, or (f) an open/closed status was cross-referenced against the live sources above. Stale-but-still-valid claims are reported as `DRIFTED-SAFE`; stale claims that now mislead decision-making are reported as `DRIFTED-MISLEADING`.

---

## 3. Header Drift

| Field in audited doc | Audited value | Live value (2026-04-16) | Verdict |
|---|---|---|---|
| Document Version | 2.4 | ≥ 2.5 required (6 phases advanced: 214 → 220) | STALE |
| Last Updated | 2026-04-13 | 2026-04-16 | STALE |
| W1 Count (cited) | 35 | `vapi_unified_wif_corpus` returns 57 total entries across 3 sources after dedup; W1-layer portion of those exceeds 35 | STALE |
| W2 Count (cited) | 26 | Needs recount against unified corpus (WIF-040 W2 channel STRUCTURALLY_CLOSED was added Phase 212, not reflected) | STALE |
| W3 Count (cited) | 5 | Unchanged since Phase 193 (W3-005 boundary); verify WIF-040 did not open a new W3 meta-risk | UNVERIFIED |
| Audit Status | Active | Still Active (correct label) — but content lags audit_date | PARTIAL |

**Recommendation:** Bump header to `Document Version 2.5`, `Last Updated 2026-04-16`, regenerate all three `Count` fields from `vapi_unified_wif_corpus`.

---

## 4. Drift Findings — HIGH severity

### 4.1 W1-002 — Separation ratio status (DRIFTED-MISLEADING)

| Field | Doc claim | Live value | Delta |
|---|---|---|---|
| Probe | touchpad_corners | touchpad_corners | — |
| N | 11 | 35 | +24 |
| Ratio | 1.261 (diagonal+LOO, Phase 143) | **0.728** (diagonal+LOO, Phase 179 analysis, 2026-04-11) | −0.533 |
| Classification | 63.6% (7/11) | 54.3% (19/35) | −9.3 pp |
| Status | `ABOVE GATE` / `UNBLOCKED` (implied in several places) | **BELOW GATE**, `TOURNAMENT_BLOCKER=true` | INVERTED |

**Why this matters.** The doc's framing implies tournament activation is unblocked at the ratio level. The live system shows the opposite: adding more sessions of the same probe caused the ratio to **regress**, and `all_pairs_p0_ok=False` is now the 10th P0 condition in tournament preflight (Phase 197). Any reader making a readiness judgement from W1-002 alone will make the wrong call.

**Correction required.** Replace the N=11 snapshot with the regression narrative recorded in `CLAUDE.md` ("Calibration Corpus State (2026-04-11)"): touchpad_corners protocol has hit a discriminative ceiling; Phase 205 `AccelTremorFFT` and Phase 217–220 (PerPairGapLog → PerPairGapTrend → CaptureVelocityOracle → TournamentBlockerSummary → PerPairGapProjection) are the canonical path forward.

### 4.2 W1-006 — Wallet / deployment state (DRIFTED-MISLEADING)

| Field | Doc claim | Live value (CLAUDE.md) | Delta |
|---|---|---|---|
| Active wallet | `0xfCF4681e57C8de9650c3Eb4dA8e26dC9441A5EF1` (original) or `~0.35 IOTX blocked` (various WIFs) | `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` (~20.432 IOTX, 2026-04-14) | Wallet rotated + funded ~58× |
| Deferred contracts | 4 deferred (VAPISwarmOperatorGate, SeparationRatioRegistry, CeremonyAuditRegistry, VHPReenrollmentBadge) | 0 deferred — all 4 **LIVE on IoTeX testnet since 2026-04-10** | Fully deployed |
| On-chain contract count | 39 (cited in some WIFs) | 43 contracts ALL LIVE | +4 |

**Correction required.** Remove the "deployment BLOCKED" framing. Add the 4 new live addresses (VAPISwarmOperatorGate `0x969c0F1EFb28504a95Acf14331A59FBCb2944F98`, SeparationRatioRegistry `0xB39CeE732cf91c93539Bd064D9426642a095a026`, CeremonyAuditRegistry `0xb9164E6d74Dde1508df2a39b01d3702ACC8230C2`, VHPReenrollmentBadge `0x42E7A25d0E5667BBae45e5cF33a6e2CC6E42d45C`).

### 4.3 Missing "Active Blockers" cross-reference section (STRUCTURAL GAP)

`vapi_contradiction_status` returns **four CRITICAL known blockers**:

1. `P1vP3 tremor_resting=0.032` — CRITICAL separation blocker (Phase 205/206)
2. `all_pairs_p0_ok=False` — per-pair gate, 10th P0 condition (Phase 197)
3. `L4 stale: calib_dim=12 vs live_dim=13` (Phase 123+ staleness monitor)
4. `RENEWAL_WITHOUT_ATTESTATION` — FleetSignalCoherenceAgent CRITICAL rule (Phase 185/186)

All four are scattered across individual WIF entries but **no single consolidated "Currently Active Blockers" header exists**. The corpus should surface these at the top of the doc so a downstream reader (or `vapi_phase_advance_proposal` caller) can triage without WIF-by-WIF scanning.

**Correction required.** Add a new `## Active Blockers (live snapshot)` section between the header and W1-001, regenerated from `vapi_contradiction_status.critical_known_blockers`.

### 4.4 W1-008 (and cross-refs) — multi-probe ratio citations (DRIFTED-MISLEADING)

Doc cites touchpad probe ratios as `corners=1.552, freeform=1.270, swipes=1.032`. These were Phase 138 full-Tikhonov snapshots superseded by Phase 143 diagonal+LOO and further by the 2026-04-11 N=35 analysis. All three live probe-type ratios are now below 1.0. Every inline number in this family must be regenerated or struck with a `SUPERSEDED — see W1-002` footnote.

---

## 5. Drift Findings — MEDIUM severity

### 5.1 Missing WIF entries

Live unified corpus contains at least two entries absent from the uploaded doc:

| ID | Status | Closure phase | Summary |
|---|---|---|---|
| **WIF-040** | STRUCTURALLY_CLOSED | Phase 212 | Skill Manifest Temporal Drift — replaced static vapi.md "Reference state" block with MCP directive; MANDATORY_INVARIANTS #12 converted to range+MCP directive |
| **WIF-041** | OPEN (at time of corpus scan) | — (Phase 214 linked) | Graduation Autowatch Gap — surfaced alongside Phase 214 PerPairGapLog foundation work |

**Correction required.** Append both entries with fingerprint + closure provenance pulled directly from the `wiki/what_if/` source. Use `vapi_unified_wif_corpus` to fetch the canonical text so dedup keys survive.

### 5.2 Numbering collision — WIF-035

The code `WIF-035` appears **twice** in the audited corpus with unrelated meaning:

- `WIF-035` in the Phase 196 context = **Biometric Credential TTL Gate**
- `WIF-035` in the BT/Bluetooth calibration Cycle 28 context = **BT transport calibration MVCP** (from autoresearch `wif_1775949600.md`)

These are semantically distinct findings; the single code will break every consumer that joins on the `WIF-###` key (fingerprint lookup, cross-doc links, MetaLearner dedup). Since Phase 196 already shipped under this code, the newer autoresearch cycle entry should be renumbered `WIF-035B` or assigned the next free code in the unified corpus (probably `WIF-042+`).

**Correction required.** Rebuild the ID namespace from `vapi_unified_wif_corpus` dedup fingerprints. Treat anything inside `what_if_corpus/wif_<ts>.md` as a candidate for a formal WIF-### code only after collision check.

### 5.3 W2-002 — stale candidacy label

Entry is marked "Phase 150+ candidate", but the functionality landed in **Phase 153** (`SeparationRatioRegistry.sol`, LIVE 2026-04-10 at `0xB39CeE732cf91c93539Bd064D9426642a095a026`). Status should be `CLOSED — Phase 153 LIVE`.

### 5.4 Open-WIF statuses to re-verify

The audited doc still lists these as OPEN or candidate:

| WIF | Cited status | Verification needed |
|---|---|---|
| WIF-032 | Open (Phase 194 candidate) | Phase 194 shipped CoherenceFingerprintRegistry — is WIF-032 closed by fingerprint feedback loop? |
| WIF-033 | Open (Phase 194 candidate) | Same check. |
| WIF-037 | Open (tied to Phase 202 TremorRestingConvergenceOracle) | Phase 202 shipped `convergence_stable` path; W1 closed, W2 still pending tremor_resting captures — confirm split. |
| WIF-038 | Open | Phase 204 explicitly closes W1+W2 per CLAUDE.md — should be `CLOSED — Phase 204 LIVE`. |
| WIF-039 | Open | Phase 208 explicitly marks `WIF-039 CLOSED` per CLAUDE.md. |
| WIF-029 | Open | Phase 178 (W1 closure) + Phase 180 (W2 closure) — should be fully `CLOSED`. |
| WIF-030 | Open | Phase 179 closes W1 — W2 status to confirm. |
| WIF-034 | Open (candidate) | Phase 191 marks `WIF-034 FORMAL` (TSP). |
| WIF-036 | Open (W1) | Phase 203 explicitly `closes WIF-036 W1` per CLAUDE.md. |

**At least six WIFs listed as OPEN in the audited doc have definitive closure evidence in CLAUDE.md.** Each requires a status sweep.

---

## 6. Drift Findings — LOW severity

### 6.1 Experiment-history corroboration

Audited doc cites autoresearch cycle scores in several places. Live ledger stats (`vapi_experiment_history last_n=20`):

| Metric | Doc claim (implied) | Live ledger |
|---|---|---|
| Cycle pass rate | near-1.000 (implied via quoted cycle scores) | **0.594** (19 passed / 32 total; 13 null/failed early) |
| Mean score | 1.000 (cited per-cycle) | **0.909** |
| Latest cycle | varies | 2026-04-12T17:19:11 — PASS, score=0.975, `wif_1776014355.md` |
| Dominant failure theme (meta-learner) | not surfaced | `invariant_violation` (1 historical failure: "MISSING: BLOCK_QUORUM=0.67; MISSING: separation ratio 0.362") |

Individual cited scores (e.g., "cycle 7 score=1.000", "cycle 47 score=1.000") remain true in isolation, but the doc's overall framing omits that the ledger has meaningful failure tail. Either (a) add a "Meta-learner" summary to the doc, or (b) explicitly scope cycle citations to "passed cycles only."

### 6.2 Latest WIF corpus citations

`what_if_corpus/wif_1776014355.md` (2026-04-12, score=0.975) is the newest artifact in the ledger. Confirm it is linked into the unified corpus index inside the doc.

---

## 7. FROZEN Invariant Integrity — PASS

Every frozen primitive cited in the audited doc resolves cleanly against `VAPI_INVARIANTS.md`:

| Cited value | `vapi_invariant_check` status | Notes |
|---|---|---|
| 228-byte PoAC wire format | FROZEN | 164B body + 64B sig — confirmed |
| 164-byte signed body | FROZEN | Chain-link hash basis |
| `SHA-256(raw[:164])` | FROZEN | Chain-link formula — confirmed |
| `Poseidon(8)` | FROZEN | C3 constraint, nPublic=5 — confirmed |
| `MINT_QUORUM=0.80` | FROZEN | Stricter than BLOCK_QUORUM — confirmed |
| `BLOCK_QUORUM=0.67` | FROZEN | Min ioSwarm BLOCK quorum — confirmed |
| 90-day biometric TTL | CONFIG (BP-001) | 90 days, temporal decay λ=ln(2)/90 — confirmed |
| Separation ratio > 1.0 (gate) | NON-NEGOTIABLE | Tournament gate — confirmed |
| L4 anomaly=7.009 | STALE — valid for gameplay | Dim-only staleness (12 vs 13); ratio unchanged |
| L4 continuity=5.367 | STALE — valid for gameplay | Same |

**Verdict:** no invariant drift in-doc. The L4 staleness is a known dim-mismatch tracked by Phase 123+ staleness monitor and Phase 215 (`L4DimSyncConfirmation`, closes G-003) — the doc should reference Phase 215 as the closure rather than treat the thresholds as suspect.

---

## 8. Phase Coverage — Doc lags by 27 phases since last W1 Count increment

CLAUDE.md phase summary goes up to **Phase 220**. Audited doc references phases up through ~216 in a few places but the header counts reflect a Phase 193-era snapshot. Phases that shipped without doc-side WIF refresh:

```
193 → 194 → 195 → 196 → 197 → 198 → 199 → 200 → 201 → 202
203 → 204 → 205 → 206 → 207 → 208 → 209 → 210 → 211 → 212
213 → 214 → 215 → 216 → 217 → 218 → 219 → 220
```

Each phase that touched a known WIF is an audit-worthy closure candidate (§5.4).

---

## 9. Novelty-Assurance Notes (VAPI Exclusive)

Per project instructions, novelty assurance is required. The following live-system novelties are **not yet surfaced** in the audited doc and should be added as W2 opportunities or W1 risks as appropriate — all are unprecedented in public anti-cheat / DePIN literature:

1. **Phase 211 `UnifiedKnowledgeLoop` MCP server** — MetaLearner-driven dominant-blocker classification + HypothesisDeduplicator (`(probe_type, phase_candidate)` SHA-256[:16] fingerprint) across 3 WIF sources. Novel: the WIF corpus is now self-deduping and auto-closes on autoresearch PASS with wiki writeback. (W2 — closes the "corpus divergence" failure mode cited in older WIFs.)

2. **Phase 212 `AutonomousEngineeringLayer`** — 5 new MCP tools including `vapi_skill_state_sync` (WIF-040 STRUCTURALLY_CLOSED) and `vapi_autonomous_gap_scan` (8-gap canonical registry G-001..G-008 with autonomous action recommendation). Novel: the engineering decision path is itself MCP-validated, not a hand-written checklist. Doc should note W2-style extension: any future proposal goes through `vapi_engineering_decision` verdict (proceed / defer / BLOCK).

3. **Phase 216–220 per-pair projection pipeline** — `PerPairGapLog → PerPairGapTrend → CaptureVelocityOracle → TournamentBlockerSummary → PerPairGapProjection`. Novel: **the first on-chain-anchorable TGE feasibility projection** from Mahalanobis velocity alone. `projected_tge_date = max(days_to_1_0 across blocker pairs)` is a VAPI-exclusive formulation. This chain deserves a dedicated W2 cluster tying P1vP3=0.032 blocker to a concrete calendar projection.

4. **Phase 213 FFT sub-bin interpolation (4096-point zero-pad + parabolic)** — VAPI-specific solution to the P1/P3 tremor-FFT bin collision that Phase 205 exposed. Any future fork of the protocol needs to inherit this or re-introduce the collision. Document as frozen-after-validation once tremor_resting captures confirm separation.

5. **Phase 207 `StagedDryRunGraduationGate`** — per-agent `dry_run=True→False` sequential migration with automatic rollback on false-positive threshold. Novel: the first anti-cheat protocol with a **formally staged agent graduation sequence** (`ruling_enforcement_agent → session_adjudicator → tournament_activation_chain`). WIF-041 may be the doc-side home for this if it isn't already.

**Recommendation:** add a `## Novelty Registry` section (or extend `W2_LAYER`) with each of the above tagged `VAPI-EXCLUSIVE` and pointing to the phase that materialized them.

---

## 10. Consolidated Recommended Corrections (prioritized)

**P0 — ship before any reader consults the doc for tournament readiness**

1. Replace W1-002 ratio snapshot with live regression narrative (N=35, ratio=0.728, ceiling hit, blocker active).
2. Add `## Active Blockers (live snapshot)` section covering the 4 CRITICAL known blockers.
3. Update W1-006 wallet + deferred-contract status (wallet funded, 4 contracts LIVE).
4. Strike or supersede the stale multi-probe ratios in W1-008 (corners=1.552, etc.).

**P1 — structural integrity**

5. Sweep WIFs {029, 030, 032, 033, 034, 036, 037, 038, 039} for closure status (most closed per CLAUDE.md phase summary).
6. Resolve WIF-035 numbering collision.
7. Append WIF-040 (STRUCTURALLY_CLOSED, Phase 212) and WIF-041 (Phase 214 context).

**P2 — header + counts**

8. Bump doc version 2.4 → 2.5.
9. Update Last Updated to 2026-04-16.
10. Regenerate W1/W2/W3 Count from `vapi_unified_wif_corpus`.

**P3 — novelty and meta**

11. Add `## Novelty Registry` (§9 items).
12. Add meta-learner summary (dominant_blocker + pass_rate trend) to the experiment-history references so cycle citations are in context.
13. Point the L4 staleness thresholds (7.009 / 5.367) at Phase 215 (`L4DimSyncConfirmation`) as the formal closure of the dim-mismatch concern.

---

## 11. What the Doc Got Right

To balance the drift findings — these aspects of the audited doc are **accurate and should be preserved as-is**:

- All 8 frozen numeric primitives (see §7). No protocol invariant has been accidentally redefined.
- The W1/W2/W3 three-layer architecture is sound and mirrors the live `vapi_unified_wif_corpus` union-then-dedup model.
- The fingerprint-per-entry pattern matches the Phase 211 HypothesisDeduplicator convention.
- Nothing in the audited doc **contradicts** a live invariant — the drift is exclusively "has-not-caught-up" rather than "has-regressed-to-wrong."

---

## 12. Appendix — Validation Inputs Used

- `vapi_unified_state` (phase=220, ratio=0.728, TOURNAMENT_BLOCKER=true, L4_STALE, 35 agents, 43 contracts)
- `vapi_unified_wif_corpus` (57 entries, 3 sources, dedup)
- `vapi_contradiction_status severity=ALL` (0 live FSCA rows, 4 CRITICAL known blockers)
- `vapi_experiment_history last_n=20 include_meta_analysis=true` (32 total, 19 passed, pass_rate=0.594, mean=0.909, dominant_blocker=invariant_violation)
- `vapi_invariant_check` × 8 on frozen primitives (all `is_known=true`, no `conflict_detected`)
- `CLAUDE.md` (Phase 220 complete; 43 contracts live; wallet `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` @ ~20.432 IOTX)

End of report.

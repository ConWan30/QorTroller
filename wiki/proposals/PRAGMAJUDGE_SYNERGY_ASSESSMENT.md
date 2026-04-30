# PragmaJudge × VAPI Phase 200+ — Synergy Assessment

**Status**: EXPLORATORY · NON-BINDING · MV+N DESIGN-PASS INPUT.

This document is parallel exploratory work to the architectural
commitment held in `wiki/proposals/PRAGMAJUDGE_DESIGN_PASS_MV.md`.
Its findings are seeds for future MV+N design passes. **None of the
novelty enhancements proposed here are committed by the present
design pass.** The MV doc remains the single architectural
commitment held for operator approval at the post-implementation
verification checkpoint per Verification-First Discipline.

**Discipline class**: assessment-mode work — no code, contract, or
configuration changes follow from this artifact. Each novelty
enhancement enumerated would seed its own dedicated design pass
before any implementation work.

**Scope**: phase-by-phase mapping of (1) what VAPI shipped between
Phase 200 and Phase 238 / Phase O0 pause, (2) what PragmaJudge MV
inherits free under the architecture in `PRAGMAJUDGE_DESIGN_PASS_MV.md`,
and (3) the novelty enhancement that would bring PragmaJudge into
structural accord with that VAPI substrate.

**Date**: 2026-04-30

**Sibling document**: `PRAGMAJUDGE_DESIGN_PASS_MV.md` (architectural
commitment, held for operator approval).

---

## Cluster A — Foundational Substrate (Phase 200, 201, 203, 209–212)

**VAPI shipped**: ioSwarm activation in emulator mode (200); LLM
agent prompt modernization to Phase 200 (201); `AgentContextRegistry`
registering SHA-256 of every LLM agent's system prompt (203); MCP
autonomous sync auto-reading CLAUDE.md (209-210); `vapi-unified` MCP
server with 12-tool MetaLearner + UnifiedWIFCorpus + WikiFeedback
(211); Autonomous Engineering Layer extending unified server to 17
tools (212).

**MV inherits free**: Sub-protocol extensibility infrastructure
(live since 204). `pragmajudge/` namespace registers cleanly.
PRAGMA-prefixed bus events propagate through `federation_bus`
without modification. MV's two agents auto-register their system-
prompt SHA-256 in `agent_context_log` per Phase 203 —
`CONTEXT_HASH_MISMATCH` FSCA rule applies to PragmaJudge agents
identically.

**Novelty enhancement for PragmaJudge** — *Pragma MetaLearner
Federation*: extend `vapi-unified` server with two PRAGMA-prefixed
tools (#212.P1 `pragma_unified_state`, #212.P2 `pragma_validate_proposal`)
that thread PragmaJudge contradiction patterns into the autoresearch
loop. PRAGMA-C1 violations cluster into a 6th MetaLearner theme
alongside the existing 5 (invariant_violation / separation_ratio /
what_if_quality / phase_coherence / gap_advancement). Cost: ~80
lines added to `vapi-unified/unified_server.py`-pattern in MV+N.
Outcome: PragmaJudge contradictions feed VAPI's autonomous
engineering proposals, closing the recursive-improvement loop
(property d) without shipping property d's full RBTS infrastructure.

---

## Cluster B — Calibration Drift & Capture Velocity (Phase 202, 205, 213–220)

**VAPI shipped**: `TremorRestingConvergenceOracle` with velocity-
based stability detection (202); `AccelTremorFFT` fallback for
still-hold sessions (205); zero-padded 4096-pt FFT + parabolic
sub-bin interpolation closing G-001 P1vP3=0.032 ambiguity (213);
`PerPairGapLog` / `Trend` / `Projection` / `Summary` /
`CaptureVelocityOracle` (216-220) — full per-pair Mahalanobis gap
analytics surfaced via `/agent/per-pair-gap-*` endpoints with TGE-
blocker projection.

**MV inherits free**: Inherits VAPI's calibrated L4 thresholds
(7.009 / 5.367) and AIT separation 1.199 transitively through VHP
gate. Per-pair gap analytics are not directly consumed but inform
whether `isFullyEligible(deviceId)` returns `true` — when
`all_pairs_p0_ok=False`, VHP issuance is blocked upstream.

**Novelty enhancement for PragmaJudge** — *Per-Speech-Act Fidelity
Gap Analytics*: directly correlate Phase 216-220's per-pair-gap
pattern to the analogous PragmaJudge structure — pairs of
(speech_act_code, prompt-class) where fidelity_score consistently
lands near threshold. Implement `pragma_speech_act_gap_log`,
`pragma_speech_act_trend`, `pragma_speech_act_projection` mirroring
the per-pair tables; surface via tools #209-#211 in MV+1 (reserved
range). Diagnostic value: identifies which speech-act-code ×
prompt-class buckets have mis-calibrated thresholds — DIRECTIVE
prompts may cluster differently than ASSERTIVE prompts. Direct
architectural homology to Phase 220's `projected_tge_date`
calculation: `projected_threshold_recalibration_date` per
(speech_act, class) bucket.

Sub-novelty — **Parabolic interpolation for fidelity-score sub-bin
resolution**: VAPI Phase 213's parabolic interpolation closed the
0.6-Hz tremor ambiguity by adding sub-bin resolution at the FFT
peak. PragmaJudge's 16-bit fidelity quantization has the same kind
of structural ambiguity — when a prompt's fidelity lands at exactly
the threshold value, MV's binary verdict (`SATISFIED ≥ threshold`
vs `FAILED < threshold`) flips on a single quantization step. Add
parabolic interpolation around the threshold — three samples (lower-
quantized / threshold / upper-quantized) of the local fidelity
gradient — to disambiguate edge-case verdicts before commitment.
Adds ~40 ZK constraints (in MV+N circuit revision) but pulls
"near-threshold" cases out of the ambiguous zone. Cost: budget
tradeoff against the 640-constraint headroom in Section 3.4.4 of
the MV doc.

---

## Cluster C — Governance + On-Chain Anchoring (Phase 221, 222, 223, 224, 225, 226, 227, 228)

**VAPI shipped**: `ProtocolCoherenceRegistry` LIVE at
`0xfAfe4E8B...` (221) anchoring 36-agent + 1-allowlist Merkle root;
`VAPIBiometricGovernance` LIVE at `0x06782293...` (222) gating
governance proposals on proposer's live VHP; PV-CI invariant gate
`scripts/vapi_invariant_gate.py` with 22 invariants + GitHub
Actions workflow (223); on-chain allowlist anchor +
`--reason / --confirm-governance` ceremony for invariant changes
(224); `governance_provenance_chain` table chaining governance
events via prev-hash → new-hash (225); INV-019..022 freezing the
provenance-hash computation code itself (226);
`anchorCoherenceWithProvenance` extending the registry to bind
governance to coherence anchor (227); VHP-gated invariant_change
category (228).

**MV inherits free**: Sub-Merkle parent-leaf composition (Section
2.8 of MV doc) inserts PragmaJudge's two agents into VAPI's Merkle
tree without touching `_AGENT_IDS`. INV-PRAGMA-01..04 register
through existing `vapi_invariant_gate.py` infrastructure.
PragmaJudge governance ceremonies use the same `--reason` /
`--confirm-governance` pattern.

**Novelty enhancement for PragmaJudge** — *PragmaJudge Sub-
Coherence Anchor (P-PCA)*: extend Phase 227's
`anchorCoherenceWithProvenance` pattern with a parallel PragmaJudge
anchor cycle. Every 1 hour (default
`pragma_coherence_anchor_interval_s=3600` mirroring Phase 221),
`PragmaCoherenceAgent` (a new MV+1 lightweight agent in the
reserved #63 slot) computes
`pragma_sub_root = SHA-256(sorted PragmaJudge agent leaves || pragma_governance_provenance_hash)`
and anchors it via `AdjudicationRegistry.recordAdjudication` with
`deviceIdHash=SHA-256(b"PRAGMA_SUB_COHERENCE_v1")` (PJ3-D-compliant
— settlement reuse, no new contract). Outcome: PragmaJudge gets the
same per-anchor provenance binding VAPI uses, attesting "as of
block N, the PragmaJudge fleet had this exact agent-set with this
exact governance state." Closes the audit-trail loop EU AI Act
buyers (Section 5.1 of MV doc) need.

Sub-novelty — **VHP-Gated Threshold Recalibration**: Phase 228's
pattern (invariant_change requires VHP) directly maps to
PragmaJudge's most sensitive operator action — modifying
`fidelity_threshold`. In MV+1, threshold-recalibration governance
events must include a `vhp_token_id` of the operator-as-end-user
proposing the change. Closes threat T5 (operator collusion)
substantially: the operator who would inflate threshold to fail
more sessions cannot do so without a VHP credential they themselves
are biometrically attested for. This is a stronger guarantee than
purely off-chain operator authentication.

---

## Cluster D — AIT Separation + Stage 1 Graduation (Phase 229, 230, 231, 207, 214)

**VAPI shipped**: AIT 4-feature pipeline `[accel_tremor_peak_hz,
roll_cos, roll_sin, pitch_cos]` achieving ratio=1.199 with all-
pairs-above-1 = True (229); AIT P0 gate wire-up to
`separation_defensibility_log` (230); AIT defensibility P0 condition
(11th P0) cleared with N=37 corpus all players ≥10 sessions (231);
`StagedDryRunGraduationGate` per-agent sequential dry_run-to-live
transition with auto-rollback (207); `GraduationAutowatchBridge`
observes `all_pairs_p0_ok` False→True transitions (214).

**MV inherits free**: Defensibility test cleared upstream — VHP
credentials issued post-2026-04-20 are defensible under the most
stringent intra-fleet separation test. PragmaJudge MV inherits the
strength via VHP composability without re-implementing any
separation logic.

**Novelty enhancement for PragmaJudge** — *Pragma Staged Live-Mode
Graduation*: mirror Phase 207 verbatim for PragmaJudge agents.
`PRAGMA_GRADUATION_SEQUENCE = (PromptIntentExtractor, OutputFidelityJudge)`.
Stage 1 graduates `PromptIntentExtractor` to live mode (writes to
`pragma_intent_records` but no on-chain action); after 50 clean
dry-run sessions, Stage 2 graduates `OutputFidelityJudge`. Auto-
rollback at `n_false_positives ≥ 2` within 10-session window. P0
gate: `pragma_judge_enabled = True AND fidelity_threshold ∈
[0.60, 0.95] AND pragma_circuit_compiled = True`. Maps directly
onto PragmaJudge MV Stream 3 (PJ9 confirmed) — Stream 3's "operator
explicit decision to flip dry_run=False per agent" becomes the
staged graduation primitive rather than a manual config flip.
Outcome: turns Stream 3 into a programmatic gate rather than a
single-flag flip.

---

## Cluster E — Grind Integrity Foundation (Phase 234, 234.5, 234.7, 235-A, 235-B, 235-GAD, 235-GPC, 235-ANALYTICS, 235-CONTENTION, 235-DASH-UPGRADE-3)

**VAPI shipped**: `InsightSynthesizer` Mode 6 `asyncio.to_thread`
fix preventing event loop stalls during startup (234); consecutive_
clean semantics audit canonicalizing the divergence formula and
streak-break conditions (234.5); PCC (Physical Capture Continuity)
capture state monitor with `NOMINAL/DEGRADED/DISCONNECTED` and
`EXCLUSIVE_USB/EXCLUSIVE_BT/CONTESTED/UNKNOWN` host inference
(234.7); GIC v1 FROZEN cryptographic chain over 100 grind sessions
per `GIC_N = SHA-256(prev||commitment||verdict||host_state||ts_ns_be)`
(235-A); PCC attestation slot in `ruling_validation_log` requiring
`pcc_state=NOMINAL AND pcc_host_state in (EXCLUSIVE_USB, UNKNOWN)`
for `consecutive_clean` advance (235-B); Gameplay Activity
Discrimination binary trigger gate making `MENU_DETECTED` break
streak (235-GAD); pre-grind validation 10-category checklist +
`gic-reset` operator endpoint with `≥10 chars reason` audit gate
(235-GPC); grind pipeline analytics surfacing `success_rate /
blocking_reason_counts / sessions_per_day / projected_gic100_date`
via `/grind/analytics` (235-ANALYTICS); BT contention episode
analytics with mean recovery time + longest episode + host-state
distribution (235-CONTENTION); per-player AIT analytics for
Developer/Manufacturer dashboards including `per_player_tremor_hz /
roll_angle_deg / pitch_angle_deg` (235-DASH-UPGRADE-3).

**MV inherits free**: Physical-attestation framework complete.
PragmaJudge MV's verdicts inherit timestamp monotonicity discipline
from `INV-GIC-002` pattern (apply same `time.time_ns() +
monotonicity guard` pattern in `compute_pragma_verdict_commitment`).
Pre-grind validation `gic-reset` operator-endpoint pattern
(`api_key + reason ≥ 10 chars`) is the canonical recovery primitive
PragmaJudge MV reuses for any future `pragma-chain-reset`
recovery action.

**Novelty enhancement for PragmaJudge** — *PragmaJudge Integrity
Chain (PIC) v1 — Ninth FROZEN-v1 Primitive*: directly mirror GIC
v1's structure for PragmaJudge sessions. Per-deviceId cryptographic
chain:
`PIC_N = SHA-256(prev_pic(32) || pragma_verdict_commitment(32) || verdict_code(1) || vhp_state_code(1) || ts_ns_be(8))`.
Genesis tag: `b"VAPI-PRAGMA-PIC-GENESIS-v1"`. Domain tag:
`b"VAPI-PRAGMA-PIC-v1"`. VHP_STATE_CODES = `{ELIGIBLE: 0x01,
ELIGIBLE_PENDING_RENEWAL: 0x02, INELIGIBLE: 0x10}`. Adds
INV-PRAGMA-05..07 for the FROZEN formula, monotonicity guard, and
chain-break detection. Becomes the ninth FROZEN-v1 primitive (after
GIC, WEC, VAME, CORPUS-SNAPSHOT, CONSENT, AGENT_COMMIT,
PHYSICAL_DATA_ATTESTATION, PRAGMA-VERDICT). Per-deviceId chain
attests "this user had N consecutive defensible PragmaJudge
sessions" — equivalent of `chain_length` for grind. The metric
becomes EU AI Act buyer's "uninterrupted compliance record" KPI.

Sub-novelty — **Engagement Activity Discrimination (EAD)**: direct
analog of GAD (235-GAD). Binary gate on prompt composition:
`prompt_composition_human` = HID input events (keystrokes / clicks /
touch) ≥ N during the time window in which the prompt was being
composed. `MENU_DETECTED` analog is `PROMPT_AUTO_INJECTED` — zero
input events during composition window means the prompt arrived
programmatically. Doesn't need full PIL stack (PJ10-A defers that);
only needs a tiny side-channel that observes whether a human was at
the keyboard. Adds `gameplay_context`-equivalent column
`composition_context` to `pragma_sessions` with three values:
`HUMAN_COMPOSED / PROMPT_AUTO_INJECTED / NULL`. `NULL` (pre-EAD
rows) passes through; `PROMPT_AUTO_INJECTED` breaks the PIC streak
the same way `MENU_DETECTED` breaks `consecutive_clean`. Closes a
soft-but-real attack: AI agent (with stolen VHP credential) submits
prompts auto-generated; EAD catches that the user was nowhere near
their keyboard.

Sub-novelty — **PragmaJudge Pipeline Analytics (P-ANALYTICS)**:
mirror Phase 235-ANALYTICS verbatim. `success_rate = SATISFIED /
total`, `blocking_reason_counts` (consent_missing, vhp_invalid,
threshold_failed, proof_failed, ead_auto_injected),
`sessions_per_day`, `projected_recalibration_date` (per speech-act
bucket from Cluster B novelty), `mean_proof_compile_time_ms`,
`mean_fidelity_score`. Surface via `/pragma/analytics` endpoint —
operator dashboard for buyer-onboarded AI services. Direct port of
`store.get_grind_analytics()` mechanics; ~120 lines of code in
MV+N.

---

## Cluster F — FROZEN-v1 Primitive Family (Phase 236-WATCHDOG, 236-VAME, 236-CORPUS-SNAPSHOT, 237-CONSENT, 237-EXTEND, 237.5)

**VAPI shipped**: WEC v1 + bridge watchdog supervisor
`scripts/bridge_watchdog.py` with three guards
(chain_intact / grind_session_id drift / 3-restart-per-hour ceiling)
(236-WATCHDOG); VAME v1 sidecar response headers per-endpoint
cryptographic stamping (236-VAME); CORPUS-SNAPSHOT v1 commitment
over wiki + agent root + ratio + N + ts_ns (236-CS); CONSENT v1
with deployed `VAPIConsentRegistry` at `0xA82dB0eF...` + per-
category enum + frontend wallet-write surface (237 + EXTEND);
CHAIN_SUBMISSION_PAUSED kill-switch + AdjudicationRegistry corpus-
snapshot anchor with constant `deviceIdHash=SHA-256(b"VAPI_CORPUS_SNAPSHOT_v1")`
(237.5 Path C+).

**MV inherits free**: VAME stamping on `/pragma/*` endpoints
automatic (Section 2.10 of MV doc). CHAIN_SUBMISSION_PAUSED kill-
switch automatic (Section 2.11). ANONYMIZED_RESEARCH consent
binding (PJ12-A, Section 2.6).

**Novelty enhancement for PragmaJudge** — *PragmaJudge Watchdog
Chain (P-WD) — Tenth FROZEN-v1 Primitive*: extend Phase 236-
WATCHDOG to a parallel PragmaJudge supervisor that monitors the
`OutputFidelityJudge` agent specifically. P-WEC (PragmaJudge
Watchdog Event Chain) records each OFJ proof-generation cycle:
`P_WEC_N = SHA-256(prev || event_code(1) || verdict_code(1) || proof_compile_time_ms_be(2) || ts_ns_be(8))`.
Event codes: `OFJ_HEALTHY=0x01, OFJ_PROOF_FAILED=0x10,
OFJ_THRESHOLD_DRIFT_DETECTED=0x20, OFJ_HALTED=0xFF`. Detects
degraded proof generation early — a circuit that compiles but
produces invalid proofs would otherwise fail silently until a
verifier rejection.

Sub-novelty — **PragmaJudge Calibration Snapshot (P-CS)**: mirror
Phase 236-CORPUS-SNAPSHOT. Periodic snapshot (every 24h or every
1000 sessions) of `fidelity_threshold + P_REDUCE_v1_hash +
speech_act_classifier_fingerprint + circuit_source_sha256 + ts_ns`.
Domain tag `b"VAPI-PRAGMA-CALIBRATION-v1"`. Anchors via
`AdjudicationRegistry.recordAdjudication` with
`deviceIdHash=SHA-256(b"PRAGMA_CALIBRATION_v1")`. Becomes the
canonical "fidelity_threshold at time T was X, with P_REDUCE_v1
fingerprint Y" reference for dispute resolution. Buyer value: when
an EU AI Act audit asks "what threshold was active when verdict V
was issued," operator points to the calibration-snapshot anchor at
the appropriate block.number.

Sub-novelty — **CONSENT v2 enum extension proposal pre-work**:
PJ12-A defers adding `PRAGMA_JUDGMENT` enum position. But MV+1 with
paying customers will hit the case where ANONYMIZED_RESEARCH framing
is no longer accurate — a paid PragmaJudge service is commercial,
not research. Pre-work: a v2 enum extension proposal with positions
`[..., PRAGMA_JUDGMENT=4, ...]` ready for governance ceremony when
buyer-volume justifies. The pre-work itself (formal
`governance_provenance_chain` proposal draft) can be drafted now,
even if not submitted.

---

## Cluster G — FSCA Wiring & Phase O0 Substrate (Phase 238 + Phase O0 paused)

**VAPI shipped**: MetaLearner FSCA wiring direct sqlite read of
`fleet_coherence_log` filtered to severity ≥ HIGH within 24h,
threaded into autoresearch prompt (238); Phase O0 source-and-tests
work for `vapi-anchor-sentry` + `vapi-guardian` + AGENT_COMMIT v1
(sixth FROZEN-v1) + PHYSICAL_DATA_ATTESTATION v1 (seventh
FROZEN-v1) — paused at Section 6.2 GitHub Apps registration awaiting
wallet refill.

**MV inherits free**: Phase 238 wiring picks up PRAGMA-C1
contradictions automatically. When MV's coherence rule fires at
HIGH severity, the autoresearch agent's next cycle includes
`[HIGH] PRAGMA-C1 (agents: output_fidelity_judge): Explanation:
SATISFIED verdict with fidelity_score < threshold` in its prompt
context.

**Novelty enhancement for PragmaJudge** — *PragmaJudge Agent-
Commit Binding*: when Phase O0 unpauses and AGENT_COMMIT v1 deploys
as the sixth FROZEN-v1 primitive on `AgentAdjudicationRegistry`,
PragmaJudge's two agents become **first-class consumers** of
AGENT_COMMIT. Every `PromptIntentExtractor.on_session_initiated`
call and every `OutputFidelityJudge.judge` call carries an
AGENT_COMMIT proof — the agent itself attests to its action via
`AgentAdjudicationRegistry`. This closes T5 (operator collusion)
substantially: an operator running a tampered OFJ cannot produce
valid AGENT_COMMITs from the canonical agent identity if the
agent's KMS-backed signing key is held by the agent's GitHub App,
not the operator. Effectively, operator-collusion mitigation lands
as a free composition once Phase O0 deploys.

Sub-novelty — **PHYSICAL_DATA_ATTESTATION v1 binding**: when the
seventh FROZEN-v1 primitive deploys (Phase O0 Stream-2-deploy),
PragmaJudge's prompt-attestation chain extends into the physical
layer: every `PromptIntentExtractor.on_session_initiated` carries a
`physical_data_attestation_hash` proving the prompt originated from
a physically-attested device session, not from a software process
simulating one. Closes the "stolen VHP + replay attack" path: even
if an attacker captures a valid VHP credential, replaying it
without a fresh PHYSICAL_DATA_ATTESTATION proof is detectable.

---

## Synergy Synthesis — Programmatic + Spec Interoperability Map

| VAPI cluster   | MV doc coverage                                                  | MV+1 enhancement                                  | MV+N enhancement                                                                |
| -------------- | ---------------------------------------------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------- |
| A — MCP/AEL    | Section 2 (consumes vapi-unified discovery)                       | Pragma MetaLearner Federation                      | Closes property (d) recursive-improvement loop                                  |
| B — Capture    | None (separate analytic surface)                                  | Per-Speech-Act Fidelity Gap Analytics              | Parabolic interpolation in circuit (constraint budget tradeoff)                 |
| C — Governance | Sections 2.8, 2.9 (sub-Merkle, INV-PRAGMA-01..04)                 | VHP-Gated Threshold Recalibration                  | P-PCA (PragmaJudge Sub-Coherence Anchor)                                        |
| D — AIT        | Section 2.1 (VHP gate inheritance)                                | Pragma Staged Live-Mode Graduation                 | (Stream 3 becomes programmatic, not manual)                                     |
| E — Grind      | None (audit-only character)                                       | PIC v1 (ninth FROZEN-v1 primitive)                 | EAD (Engagement Activity Discrimination) + P-ANALYTICS                          |
| F — FROZEN     | Sections 2.10, 2.11 (VAME, kill-switch)                           | P-WD (tenth FROZEN-v1) + P-CS                      | CONSENT v2 enum proposal pre-work                                               |
| G — FSCA/O0    | Section 2.5 (PRAGMA-C1 picked up by FSCA)                         | (auto-inherits when Phase O0 unpauses)             | AGENT_COMMIT + PHYSICAL_DATA_ATTESTATION binding closes T5 substantially         |

**Hardest dependency**: Cluster G novelty closes threat T5
(operator collusion, currently MV-deferred per PJ7-confirm)
**for free** once Phase O0 unpauses. This is the single most
consequential synergy in the assessment — it converts MV's biggest
deferred risk into a pre-paid future closure.

**Easiest near-term win**: Cluster D novelty (Pragma Staged Live-
Mode Graduation). Mirrors Phase 207 verbatim; ~150 lines of code;
converts Stream 3's manual flag-flip into a programmatic state
machine with auto-rollback. Drop-in for MV+1.

**Highest-novelty addition**: Cluster E PIC v1 — joins the
FROZEN-v1 primitive family as the ninth member, gives PragmaJudge a
per-user audit chain isomorphic to GIC. Shifts PragmaJudge from
"audit log per session" to "audit chain per user" — a meaningful
product upgrade for EU AI Act / Moffatt compliance buyers.

---

## End of Assessment

**Self-attestation**: this artifact is exploratory analysis. Each
named novelty enhancement (Pragma MetaLearner Federation, Per-
Speech-Act Fidelity Gap Analytics, P-PCA, VHP-Gated Threshold
Recalibration, Pragma Staged Live-Mode Graduation, PIC v1, EAD,
P-ANALYTICS, P-WD, P-CS, CONSENT v2 enum extension, AGENT_COMMIT
binding, PHYSICAL_DATA_ATTESTATION binding) would seed its own
dedicated MV+N design pass before any implementation work.

The architectural commitment for PragmaJudge MV remains
`PRAGMAJUDGE_DESIGN_PASS_MV.md`. This assessment does not modify
that commitment; it identifies adjacent territory the operator may
choose to traverse in subsequent passes.

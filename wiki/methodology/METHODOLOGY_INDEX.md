---
title: "VAPI Methodology Layer — Authoritative Index"
date: 2026-05-14
proposal_type: METHODOLOGY-INDEX
status: "v1.0 / TIER-2 IN-FLIGHT"
scope: "Documentation-only. Three-tier governance catalog. No PV-CI mutation. No code change. No FROZEN content modified."
authority: "VAPI Architect; bridge wallet 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692"
wallet_impact: "0 IOTX"
chain_impact: "none"
kill_switch: "CHAIN_SUBMISSION_PAUSED=true (held)"
companion_document: "CLOSED_LOOP_FOUNDATIONAL_ARCHITECTURE.md"
governance_tier: "Tier 2 — in-flight reference; may be promoted to Tier 1 via future operator-authorized architect Ed25519 ceremony"
---

# VAPI Methodology Layer — Authoritative Index

## §0 Purpose

This document is the authoritative catalog of every methodology artifact comprising
the VAPI Methodology Layer (Layer 7 of the protocol stack). It applies the three-tier
governance discipline established by the operator at synthesis-authoring time
(2026-05-14): every methodology document belongs to exactly one tier, the tier
governs how that document may be composed against by future work, and the
catalog is the canonical reference for which tier a given document inhabits.

The index is companion to `CLOSED_LOOP_FOUNDATIONAL_ARCHITECTURE.md` (the synthesis
essay). The synthesis composes against this index; the index does not depend on the
synthesis. The two documents ship as one atomic methodology-only commit with zero
wallet impact, zero chain impact, and zero modification of any FROZEN content.

This index is itself a **Tier 2 in-flight reference** at first commit. Promotion to
Tier 1 would require future operator-authorized architect Ed25519 signature ceremony
following the procedure established by VBDIP-0001 Step 4–5
(`vsd-vault/eval/architect_key_attestation.json` is the existing signing-chain anchor;
the manifest would land at `vsd-vault/manifests/methodology-INDEX-v1.0/001.manifest.json`).
The deferred promotion is named, scoped, and operator-gated; it ships when operator
authorization allows.

---

## §1 Three-Tier Governance Model

The methodology corpus operates under three tiers of governance status. Each tier
governs how synthesis may compose against documents in that tier. The tiers are
not a quality ranking; they are an authority ranking under the supersession
discipline established by VBDIP-0001 §11.

**Tier 1 — FROZEN methodology.** Documents that carry FROZEN canonical hashes,
architect Ed25519 signatures (or inherited trust through the signing chain), and
serve as normative authority for what methodology IS. Synthesis composes against
Tier 1 documents as ingredient sources; the synthesis manifest's
`gathered_assertions` array carries the ingredient's `manifest_hash` (where present)
or canonical commit hash (where pre-VBDIP-0001 signing chain). Tier 1 content
cannot be paraphrased as new authorship; cannot be modified except by ceremony
with architect signature over a new canonical hash plus PV-CI invariant update
plus explicit supersession documentation. Synthesis is not ceremony.

**Tier 2 — Active proposals and drafts.** Documents in evolving status —
reconciliation plans, decision matrices, future-VBDIP/VEDIP drafts, in-flight
amendments. Synthesis cites Tier 2 documents with explicit revision pinning
(commit hash at citation time, or document version + freeze date). The synthesis
that composes against Tier 2 content carries dependency risk that the Tier 2
content may evolve before freezing.

**Tier 3 — Operational artifacts.** Phase-boundary snapshots, integration maps,
retrospective documents, provenance pins, state assessments. These document
methodology layer state at specific moments rather than canonical methodology
specification. Synthesis cites Tier 3 documents to establish "what state existed
at moment X" or "what reasoning produced decision Y" — never as normative
authority for what methodology IS. Tier 1 plus Tier 2 are normative; Tier 3 is
descriptive.

The three-tier model is itself a methodology layer discipline. It is not in the
PV-CI allowlist at v1.0 of this index (the five layer-level markdown-normative
invariants documented at `METHODOLOGY_LAYER_INTEGRATION_MAP.md §5` cover related
but distinct ground). Future VBDIPs may elevate the three-tier discipline to
programmatic PV-CI enforcement; that elevation is operator-authorized future work.

---

## §2 Tier 1 Catalog — FROZEN Methodology (Ingredient Sources)

The Tier 1 corpus comprises five canonical methodology documents. Three of them
were FROZEN within the architect Ed25519 signing chain established by VBDIP-0001;
two predate the signing chain and are FROZEN by the supersession-discipline
convention they themselves established.

### 2.1 VBDIP-0001 — VAPI Architectural Discipline (VAD) Framework Introduction

| Field | Value |
|---|---|
| Canonical path | `wiki/methodology/VBDIP-0001-vad-framework-introduction.md` |
| FROZEN at | commit `d6830525` (Phase O1-VBDIP-0001-INTEGRATION Step 5), 2026-05-10 |
| Spec content | v1.0 §§1–10 + §11 metadata (byte-identical) |
| Amendments | v1.1 Appendix A (2026-05-12, additive; ratifies D-NUM Option N1) |
| Active content | v1.0 spec + v1.1 amendment |
| Manifest | `vsd-vault/manifests/proposals-VBDIP-0001/001.manifest.json` |
| Canonical hash | `56da19e2…8ea27` |
| Architect Ed25519 signature | `ea59071b…e103` |
| Architect pubkey | `056e695f2995070198a0db1a6c264d8234fb88bf5cf6332c354f58a096a78ca8` |
| Bridge wallet attestation | `vsd-vault/eval/architect_key_attestation.json` |
| EIP-191 wallet signature | `0xb21a94de…3731b` |
| Bridge wallet | `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` |
| Role as ingredient | Establishes the VAD framework (top-level), the three sub-disciplines (VSD/VED/VBD), four VBD invariants (1: deployer-anchored provenance under fleet expansion; 2: fleet-domain replication; 3: primitive composition; 4: cross-fleet skill-separation as retroactive INV-CFSS-001 rename), the unified harness `--proposal-type` extension, and the deferred-migration discipline for `vsd-vault/ → vad-vault/`. |
| Citation convention | `VBDIP-0001 §X.Y [Tier 1; manifest 001.manifest.json; hash 56da19e2…8ea27]` |

### 2.2 VBDIP-0002 — ZKBA Visual Projections

| Field | Value |
|---|---|
| Canonical path | `wiki/methodology/VBDIP-0002-zkba-visual-projections.md` |
| FROZEN at | v1.0 FROZEN-SPEC (Phase O3-ZKBA-TRACK1 C1) |
| Amendments | v1.1 Appendix B (commit `3461b636`, 2026-05-12, absorbs VBDIP-0002A §§1,2,3,4,5,7,9,11,12); v1.2 Appendix C (commit `a501d6f1`, bilateral schema-name acceptance — `vapi-zkba-manifest-v1` canonical for new emissions, `zkba.projection_manifest.v1` recognized for read-only legacy) |
| Active content | v1.0 + v1.1 Appendix B + v1.2 Appendix C |
| Manifest | Not authored at v1.2 ship per supersession discipline; signing-chain trust inherited via VBDIP-0001 anchor |
| Role as ingredient | Specifies ZKBA primitive (PATTERN-017 member #10 with domain tag `b"VAPI-ZKBA-ARTIFACT-v1"`); VPM wrapper layer (`vapi-vpm-manifest-v1` schema with 9-field Integrity Label, 5 FROZEN closed enums, 3-layer Anti-Hype Visual Grammar); G4 manifest validator with 7-class coverage; Lane B activation gates G1–G11; numbering reservation table (extended by VBDIP-0001 v1.1). |
| Tracks | Track 1 (wallet-free) CLOSED at v1.2 ship. Track 2 (Cedar v2 anchor + ceremony ~0.18 IOTX) shipped at commit chain `755fac33`→`531dbc6b`→`2a91c564`→`85fc4551` with 3-of-3 dual anchors LIVE on IoTeX 2026-05-12 |
| Citation convention | `VBDIP-0002 §X [Tier 1; v1.2 active content; ship commit a501d6f1]` |

### 2.3 VEDIP-0001 — Verified Engineering Discipline Retrospective

| Field | Value |
|---|---|
| Canonical path | `wiki/methodology/VEDIP-0001-engineering-discipline-retrospective.md` |
| FROZEN at | RETROSPECTIVE-SPEC v1.0 (commit `0791c935`), 2026-05-11 |
| Manifest | Not authored at v1.0 ship per VEDIP §C signing-deferral note ("intentionally does not run a signing ceremony"); architect signing chain remains available |
| Role as ingredient | Names the seven engineering disciplines retroactively (V-check, P-check, atomic commit, decision blocks, wallet-risk separation, PV-CI freeze, source-stable IDs); maps VED-INV-001 through VED-INV-067 documentation aliases over engineering/protocol PV-CI entries; documents retrospective corpus (Phase O0, FRR, Stream J, parallel O2 SUGGEST, VBDIP-0001 integration, Phase O3-ZKBA-TRACK1 engineering surface); locks five Decision blocks K1–K5 (VED recognition, documentation alias, wallet boundary, drift preservation, VBD boundary). |
| Note | `VED-INV-N` is documentation-only count abstraction. Native PV-CI IDs (e.g., `INV-FRR-001`, `INV-OPERATOR-AGENT-001`, `INV-ZKBA-002`) remain unchanged in source control. No code or allowlist-file rename performed under VED prefix. |
| Citation convention | `VEDIP-0001 §X [Tier 1 retrospective; FROZEN at commit 0791c935]` |

### 2.4 VSDIP-0001 — VSD Methodology v1.0 FINAL

| Field | Value |
|---|---|
| Canonical path | `wiki/methodology/vsd_methodology_v1_FINAL.md` |
| FROZEN at | v1.0 FINAL freeze (pre-Phase-O1-VSD-BOOTSTRAP) |
| Manifest | Predates VBDIP-0001 signing chain; FROZEN by self-declared supersession discipline ("no in-place amendments"; future numbered evolutions update internal references at the phase boundary) |
| Role as ingredient | Seven-step VSD bootstrap procedure; 16 VSD invariants (VSD-INV-1 through VSD-INV-16); twelve note-type schema (claim/ingredient/synthesis/PBSA/decision/adversarial/eigenspace/study/industry/verification/MCP/CDRR notes); provenance triple per VSD-2 (every claim carries `ingredient_id` + `manifest_uri` + `manifest_hash`); SHA-256 note-byte hash discipline per VSD-INV-4; harness-gated commitment per VSD-1 (immutable harness, editable orchestrator). |
| Citation convention | `VSDIP-0001 §X [Tier 1; v1.0 FINAL freeze]` |

### 2.5 VSDIP-0002 — VSD Volume 2 FINAL

| Field | Value |
|---|---|
| Canonical path | `wiki/methodology/vsd_volume_2_final.md` |
| FROZEN at | v2.0 FINAL freeze (pre-Phase-O1-VSD-BOOTSTRAP) |
| Manifest | Predates VBDIP-0001 signing chain; FROZEN by self-declared supersession discipline |
| Role as ingredient | 8-stream VSD bootstrap procedure; 7 additional VSD invariants (VSD-INV-17 through VSD-INV-23, total 23); MCP-primary index pattern; VRR primitive introduction (VAPI Readiness Root); CDRR primitive introduction (Composed Domain Readiness Root, composing FRR + VRR); INV-CFSS-001 cross-fleet skill-separation (later retroactively renamed VBD-INV-4 per VBDIP-0001 §4.4); fleet-domain replication discipline (later formalized as VBD-INV-2). Volume 2 expands the synthesis-discipline novelty axis count from five (v1.0 §10) to nine. |
| Citation convention | `VSDIP-0002 §X [Tier 1; Volume 2 FINAL freeze]` |

### 2.6 Tier 1 Composition Discipline Summary

When the synthesis composes against Tier 1 documents:

1. Each ingredient citation includes the tier classification + the manifest hash (where present) or commit pin.
2. Each ingredient appears in the gathered_assertions array of the synthesis manifest (when/if the synthesis is promoted to Tier 1 via future signing ceremony).
3. Paraphrase of Tier 1 content without ingredient reference is forbidden per VSD ingredient discipline (would produce orphan synthesis failing VSD-INV-3).
4. Modification of Tier 1 content is forbidden per supersession discipline; requires ceremony with architect signature over a new canonical hash plus PV-CI invariant update plus explicit supersession documentation.
5. Tier 1 documents have FROZEN status; future numbered evolutions reference them by canonical hash, do not rewrite them.

---

## §3 Tier 2 Catalog — Active Proposals and Drafts (Revision-Pinned References)

Tier 2 documents carry in-flight status. Synthesis cites with revision pinning so
future operators can resolve which version of the in-flight content was composed
against.

### 3.1 VBDIP-0002-vs-0002A Reconciliation Plan (DRAFT)

| Field | Value |
|---|---|
| Path | `vsd-vault/proposals/drafts/VBDIP-0002-vs-0002A-reconciliation.DRAFT.md` |
| Status | Reconciliation plan; D-MERGE-SELECTIVE recommendation executed at commit `3461b636` (VBDIP-0002 v1.1 amendment) |
| Authoring commit | `f47763fe` (commit `f47763fe`) |
| Execution status | Plan authored at `f47763fe`; executed at `3461b636`; VBDIP-0002A §§1,2,3,4,5,7,9,11,12 absorbed; §§6,8,10 retained as sidecar |
| Cite-discipline | Pin commit hash at citation time; flag in-flight if cited |
| Citation convention | `VBDIP-0002 vs 0002A reconciliation §X [Tier 2 DRAFT; revision f47763fe → executed 3461b636]` |

### 3.2 VBDIP-0002A — Verified Projection Media (DRAFT, PARTIALLY ABSORBED)

| Field | Value |
|---|---|
| Path | `vsd-vault/proposals/drafts/VBDIP-0002A-verified-projection-media.DRAFT.md` |
| Status | PARTIALLY ABSORBED (post commit `3461b636`) |
| Cite-discipline | Cite as historical sidecar; explicit absorption note required; §§6,8,10 remain authoritative sidecar content |
| Citation convention | `VBDIP-0002A §X [Tier 2 PARTIALLY ABSORBED; absorbed sections superseded by VBDIP-0002 v1.1 Appendix B]` |

### 3.3 VBDIP-0002 Schema Name Reconciliation (DRAFT, RESOLVED)

| Field | Value |
|---|---|
| Path | `vsd-vault/proposals/drafts/VBDIP-0002-schema-name-reconciliation.DRAFT.md` |
| Status | RESOLVED via VBDIP-0002 v1.2 Appendix C (Option C bilateral acceptance) |
| Resolution commit | `a501d6f1` |
| Cite-discipline | Cite as drift surface that produced Option C; supersession noted |
| Citation convention | `VBDIP-0002 schema-name reconciliation §X [Tier 2 RESOLVED; superseded by v1.2 Appendix C at a501d6f1]` |

### 3.4 Operator Decision Matrix (DRAFT)

| Field | Value |
|---|---|
| Path | `vsd-vault/proposals/drafts/OPERATOR-DECISION-MATRIX.DRAFT.md` |
| Authoring commit | `56fe99a2` |
| Status | Active; 16 decisions consolidated across 5 clusters |
| Resolution status at synthesis time (2026-05-14) | 15 of 16 resolved (D-SCHEMA-A, D-NUM, D-SIDECAR-0002A, D-LANE-B-G3, D-PV-VPM, D-SCHEMA-B implicitly closed, D-TRACK2-C6, D-TRACK2-C7, D-TRACK2-G9 via D-NUM, D-TRACK2-C8 ceremony fired, D-TRACK2-KILLSWITCH, D-TRACK2-FSCA, D-TRACK2-G6 partial via post-ceremony audit, D-PV-VPM, plus the C8 ceremony execution itself); D-TRACK2-G7 (Curator review readiness) remains operator-runtime observation work |
| Cite-discipline | Pin commit hash at citation time; identify which decisions are cited and their resolution status at citation time |
| Citation convention | `OPERATOR-DECISION-MATRIX §X [Tier 2; revision 56fe99a2; D-NUM resolved at 2026-05-12]` |

### 3.5 Future-VBDIP / VEDIP Reservations

Per VBDIP-0001 §11 metadata + v1.1 Appendix A.2 numbering reservation table:

| Reserved number | Reserved for | Reservation source | Status |
|---|---|---|---|
| VBDIP-0003 | Post-bootstrap discovery requiring VBD invariant adjustment | VBDIP-0001 §3.4 (v1.0) | Reserved; not authored |
| VBDIP-0004 | Phase O1-VAD-MIGRATE (`vsd-vault/` → `vad-vault/`) | VBDIP-0001 v1.1 Appendix A.2 | Reserved; not authored |
| VEDIP-0002 | Chain-Facing Operator Script Standard | VEDIP-0001 §9 | Reserved; not authored |
| VEDIP-0003 | Store Migration and Helper API Standard | VEDIP-0001 §9 | Reserved; not authored |
| VEDIP-0004 | SDK Wire-Contract Parity Standard | VEDIP-0001 §9 | Reserved; not authored |
| VEDIP-0005 | Hardware-Capture Phase Boundary Standard | VEDIP-0001 §9 | Reserved; not authored |
| VSDIP-0003 | Pre-bootstrap strengthening | VSDIP-0002 / Volume 2 §V4 + VBDIP-0001 §10 | Reserved; pending authoring as follow-up to VBDIP-0001 |

Future-VBDIP/VEDIP reservations are not citable at v1.0 of this index because they
have no content. They are listed here so operators can verify reservation
integrity when authoring future proposals.

---

## §4 Tier 3 Catalog — Operational Artifacts (Historical Record)

Tier 3 documents are descriptive, not normative. Synthesis cites Tier 3 to
establish state at a specific moment or to document reasoning that produced a
specific decision. Tier 3 citations carry explicit `[Tier 3 HISTORICAL]`
annotation when used in synthesis composition.

### 4.1 Methodology Layer Integration Map

| Field | Value |
|---|---|
| Path | `wiki/methodology/METHODOLOGY_LAYER_INTEGRATION_MAP.md` |
| Authoring commit | `aa436f9b` (2026-05-12) |
| Captures | Layer 7 architectural elevation snapshot; layer components map (VAD framework + PATTERN-017 #10 ZKBA + VPM wrapper + manifest validator + reach trio + signing chain + 6 PV-CI invariants + 5 layer-level markdown-normative invariants) |
| Cite-discipline | State-establishment: "Layer 7 was architecturally elevated to peer status by commit `aa436f9b`" |
| Citation convention | `METHODOLOGY_LAYER_INTEGRATION_MAP §X [Tier 3 HISTORICAL; snapshot 2026-05-12]` |

### 4.2 Integration Provenance Witness (2026-05-10)

| Field | Value |
|---|---|
| Path | `wiki/methodology/INTEGRATION_PROVENANCE_2026-05-10.md` |
| Authoring commit | `2aea877a` (Step 1 of VBDIP-0001 integration) |
| Captures | Deferral-boundary witness for VBDIP-0001 integration; pre/post artifact hashes for byte-preservation verification across Steps 1–5 |
| Cite-discipline | State-establishment: "Step 1 of VBDIP-0001 integration landed at commit `2aea877a`" |
| Citation convention | `INTEGRATION_PROVENANCE_2026-05-10 §X [Tier 3 HISTORICAL; deferral-boundary witness 2026-05-10]` |

### 4.3 Layer 7 7-of-7 Closure (2026-05-13)

| Field | Value |
|---|---|
| Path | `wiki/methodology/layer7_closure_2026-05-13.md` |
| Anchor commit | `ece17f4f` (HARDWARE Participation Card) |
| Captures | 7-of-7 ZKBA artifact class coverage; 3 architectural firsts (manufacturer-bound audience tier, 3-agent CFSS Cedar policy triangle closure, Layer 7 7-of-7 invariant `T-ZKBA-HW-10`); per-axis distribution (proof weights 3/6, audiences 4/4, CFSS lanes 3/3, composition depths 3/3) |
| Cite-discipline | State-establishment: "Layer 7 reached 7-of-7 ZKBA class coverage at commit `ece17f4f`" |
| Citation convention | `layer7_closure_2026-05-13 §X [Tier 3 HISTORICAL; closure snapshot 2026-05-13]` |

### 4.4 Phase O1 VSD Bootstrap Canonical

| Field | Value |
|---|---|
| Path | `wiki/methodology/phase_o1_vsd_bootstrap_canonical.md` |
| Captures | Phase O1 bootstrap canonical state; bridge wallet attestation chain reference; refresh of state references at VBDIP-0001 integration |
| Cite-discipline | State-establishment for Phase O1 bootstrap context |
| Citation convention | `phase_o1_vsd_bootstrap_canonical §X [Tier 3 HISTORICAL; Phase O1 bootstrap canonical state]` |

### 4.5 Claude Code Master Resumption Prompt

| Field | Value |
|---|---|
| Path | `wiki/methodology/claude_code_master_resumption_prompt.md` |
| Captures | Master resumption procedure; revised D1→D2 at VBDIP-0001 Step 3 (commit `be13de49`) |
| Cite-discipline | Operational reference for session resumption; not a synthesis ingredient |
| Citation convention | `claude_code_master_resumption_prompt §X [Tier 3 HISTORICAL; procedure reference]` |

### 4.6 BT Calibration v1.1 Architectural Revision

| Field | Value |
|---|---|
| Path | `wiki/methodology/bt_calibration_v1_1_architectural_revision.md` |
| Status | Canonical per CLAUDE.md "BT Calibration: Canonical Prerequisite Anchor" section |
| Captures | Four corrections against v1.0 proposal; BR/EDR transport reality; BlueShield FN floor baseline (5.84% CFO, 8.72% RSSI, 2.37% combined FP per Wu et al. RAID 2020); witness device tier discipline; same-controller separability constraint per `CROSS-LESSON-001` |
| Supersedes | v1.0 BT proposal (BLE-derived L4 features); `BT-CALIB-LESSON-001` lesson in `lessons.md` |
| Cite-discipline | Architectural prerequisite anchor for any BT-related design work |
| Citation convention | `bt_calibration_v1_1_architectural_revision §X [Tier 3 HISTORICAL; canonical BT prerequisite anchor]` |

### 4.7 Sensor Stack v2.1 Architectural Revision

| Field | Value |
|---|---|
| Path | `wiki/methodology/sensor_stack_v2_1_architectural_revision.md` |
| Status | Canonical per CLAUDE.md "Sensor Stack v2: Canonical Prerequisite Anchor" section |
| Captures | Six surface-tier assignments (Surface 1 trigger force-curve → PRIMARY DISCRIMINATOR; Surface 2 touchpad → CO-SIGNAL; Surface 3 microphone array → DROPPED on privacy-falsification grounds; Surface 4 lightbar → CO-SIGNAL as challenge-response witness; Surface 5 battery → ADVISORY; Surface 6 split sticks); Stage A measurement gates (Empirical Unknown #1, #4); ALPS Alpine potentiometer-based stick fact correction |
| Supersedes | v2.0 sensor-stack ideation (microphone multi-mic array claims); `TRACK1-LESSON-002`, `TRACK1-LESSON-003` lessons in `lessons.md` |
| Cite-discipline | Architectural prerequisite anchor for any DualSense Edge sensor-stack design work |
| Citation convention | `sensor_stack_v2_1_architectural_revision §X [Tier 3 HISTORICAL; canonical sensor-stack prerequisite anchor]` |

### 4.8 VAPI State Assessment (2026-05-10)

| Field | Value |
|---|---|
| Path | `wiki/assessments/vapi_state_assessment_2026_05_10.md` |
| Captures | Phase-Boundary State Assessment (PBSA pattern per VSD-4 native output type); Executive Summary + Protocol Position + Architectural State + Empirical Validation + Wallet/On-Chain Health + Risk Register + Engineering Discipline + Forward Roadmap + Strategic Themes + Bright-Future Programming Checklist |
| Cite-discipline | State-establishment for protocol position at the date of the assessment |
| Citation convention | `vapi_state_assessment_2026_05_10 §X [Tier 3 HISTORICAL; PBSA snapshot 2026-05-10]` |

### 4.9 CCO × PoEP Fusion v4 — Universal Presence Framework

| Field | Value |
|---|---|
| Path | `wiki/methodology/CCO_POEP_FUSION_v4.md` |
| Status | Draft — verification-discipline artifact (not an implementation spec) |
| Date | 2026-06-19 |
| Captures | Controller Capability Oracle (v3) + Proof of Embodied Presence fusion (v4); two-axis identity×presence grid; repo-graded maturity matrix; findings F-V3-001 (on-chain tier repurposing overstated), F-V3-002 (**CLOSED** Option C — `CCO_T0_POLICY_v1.md`); Phase A–G execution path |
| Companions | `DEVICE_ID_CANON_v1.md`, `sensor_stack_v2_1_architectural_revision.md`, `bt_calibration_v1_1_architectural_revision.md`, `l9_presence/POEP_SCOPE.md` |
| Supersedes | Conceptual CCO v3 strategic reframe (prose only; no prior methodology file) |
| Cite-discipline | Architectural prerequisite anchor for universal-controller presence / CCO×PoEP design work (Track B); do not conflate with Track A live path |
| Citation convention | `CCO_POEP_FUSION_v4 §X [Tier 3 DRAFT; verification artifact 2026-06-19]` |

### 4.10 CCO T0 Presence Policy v1

| Field | Value |
|---|---|
| Path | `wiki/methodology/CCO_T0_POLICY_v1.md` |
| Status | Operator decision — closes F-V3-002 |
| Date | 2026-06-19 |
| Captures | Option C: L6B → P-T0 `REFLEX_OBSERVED`; PoEP bundle → P-T2/T3 `PRESENT`; activation gates unchanged |
| Parent | `CCO_POEP_FUSION_v4.md` §5 F-V3-002 |
| Citation convention | `CCO_T0_POLICY_v1 §X [Tier 3 DRAFT; operator decision 2026-06-19]` |

### 4.11 CCO Phase A — Capability Oracle Output Contract v1

| Field | Value |
|---|---|
| Path | `wiki/methodology/CCO_PHASE_A_ORACLE_CONTRACT_v1.md` |
| Status | Scope + V-check — **no bridge code** until hold lifts |
| Date | 2026-06-19 |
| Captures | `CapabilityReport` field contract; six-profile V-check table; `CapabilityOracle.resolve()` read-only semantics |
| Parent | `CCO_POEP_FUSION_v4.md` Phase A; `CCO_T0_POLICY_v1.md` |
| Citation convention | `CCO_PHASE_A_ORACLE_CONTRACT_v1 §X [Tier 3 DRAFT; Phase A scope 2026-06-19]` |

### 4.12 CCO Phase B — L6B T0 Wiring Design v1

| Field | Value |
|---|---|
| Path | `wiki/methodology/CCO_PHASE_B_DESIGN_v1.md` |
| Status | B.1 merged main; B.2 session-status + B.3 runbook complete (2026-06-20) |
| Date | 2026-06-20 |
| Captures | CCO→L6B wiring; applicability predicate (IMU + DualSense haptic); `REFLEX_OBSERVED` telemetry path; DECON-2 store split (`_core.py` schema, `calibration.py` insert); findings F-PHASE-B-001..005; B.1–B.3 sub-phases (B.2 `cco` session-status; B.3 activation runbook) |
| Parent | `CCO_POEP_FUSION_v4.md`; `CCO_T0_POLICY_v1.md`; `CCO_PHASE_A_ORACLE_CONTRACT_v1.md` |
| Citation convention | `CCO_PHASE_B_DESIGN_v1 §X [Tier 3 DRAFT; Phase B design 2026-06-20]` |

### 4.13 L6B Desk Calibration — True-Latency Classifier v1

| Field | Value |
|---|---|
| Path | `wiki/methodology/L6B_DESK_CALIBRATION_ANALYZER_v1.md` |
| Status | DRAFT — analyzer fix shipped; desk `human_max=350` recommendation |
| Date | 2026-06-20 |
| Captures | Candidate A (classify on `true_latency_ms`); Candidate B (desk `human_max_ms=350`); N≥50 gate assessment (59 probes @ force=200); mechanical `reflex_gap` guard |
| Parent | `CCO_PHASE_B_DESIGN_v1.md` §5; F-L6B-CAL-005 |
| Citation convention | `L6B_DESK_CALIBRATION_ANALYZER_v1 §X [Tier 3 DRAFT; desk calibration 2026-06-20]` |

### 4.14 CCO Phase E — Identity Grid Session Surfacing v1

| Field | Value |
|---|---|
| Path | `wiki/methodology/CCO_POEP_FUSION_v4.md` §Phase E; `bridge/vapi_bridge/cco_identity_grid.py` |
| Status | COMPLETE (2026-06-20) |
| Date | 2026-06-20 |
| Captures | Two-axis grid `{identity_class, presence_ceiling_candidate, signing_path, path_a_eligible}` on GET `/player/session-status`; F-V4-003 Path B honesty note; `composable_on_chain=false` (Phase F deploy-hold) |
| Parent | `CCO_POEP_FUSION_v4.md`; `CCO_PHASE_A_ORACLE_CONTRACT_v1.md` |
| Citation convention | `CCO_POEP_FUSION_v4 §Phase E [Tier 3; identity grid 2026-06-20]` |

### 4.15 CCO Phase F — On-Chain Composability Prep v1

| Field | Value |
|---|---|
| Path | `wiki/methodology/CCO_POEP_FUSION_v4.md` §Phase F; `bridge/vapi_bridge/cco_composability.py` |
| Status | COMPLETE (2026-06-20) |
| Date | 2026-06-20 |
| Captures | Option F1 off-chain `VAPI-COMPOSABLE-CLAIM-v1` candidate hash; PoEP registry commitment view helper; optional Lens `isFullyEligible` sub-check; session-status `identity_grid.composability`; `composable_on_chain=false` deploy-hold |
| Parent | `CCO_POEP_FUSION_v4.md` §4.1; `cco_identity_grid.py` Phase E |
| Citation convention | `CCO_POEP_FUSION_v4 §Phase F [Tier 3; composability prep 2026-06-20]` |

---

## §5 Supersession Chain Documentation

The methodology corpus has accumulated supersession events. The chain is documented
here so future operators can trace which document supersedes which.

### 5.1 VBDIP-0002A → VBDIP-0002 v1.1 Appendix B

**Event:** VBDIP-0002A `§§1,2,3,4,5,7,9,11,12` absorbed into VBDIP-0002 as Appendix B
(B.1 through B.9) per VBDIP-0002 v1.1 amendment at commit `3461b636` (2026-05-12).
VBDIP-0002A `§§6,8,10` retained as sidecar content. VBDIP-0002A header status:
DRAFT → PARTIALLY ABSORBED. Activation gate G5 split into G5a/G5b/G5c. Decision
blocks K-series extended K1–K7 → K1–K14 (B.9 absorbed L1–L7). §16 gate count
9 → 11.

**Discipline:** Additive amendment per supersession discipline. v1.0 spec
§§1–17 + Appendix A byte-identical. VPM-HONESTY-001 locked at B.5 as
methodology-doc identifier (NOT a PV-CI invariant) per reconciliation plan §4.

### 5.2 §9.2 Schema-Name Drift → VBDIP-0002 v1.2 Appendix C

**Event:** §9.2 spec design-time schema name `zkba.projection_manifest.v1`
diverged from implementation FROZEN schema name `vapi-zkba-manifest-v1` (PV-CI
`INV-ZKBA-003` pin). Resolved via Option C bilateral acceptance at commit
`a501d6f1`: `vapi-zkba-manifest-v1` CANONICAL for new emissions;
`zkba.projection_manifest.v1` RECOGNIZED for read-only legacy validation.
Validator surfaces drift via `schema_name_form` field per request.

**Discipline:** v1.2 amendment additive per supersession discipline.

### 5.3 D-NUM Resolution → VBDIP-0001 v1.1 Appendix A

**Event:** VBDIP-0002 reservation moved from "Phase O1-VAD-MIGRATE" (v1.0 §3.4
line 79 + §6.1 line 240) to "ZKBA visual projections" (Option N1 per Operator
Decision Matrix D-NUM). Phase O1-VAD-MIGRATE relocated to VBDIP-0004. v1.0
text byte-identical; v1.1 amendment ratifies working operational state across
17+ commits.

**Discipline:** Additive amendment per supersession discipline. Closes
VBDIP-0002 §16 G2 + G9 gates.

### 5.4 D-PV-VPM Resolution → INV-VPM-WRAPPER-001 PV-CI Addition

**Event:** Operator Decision Matrix D-PV-VPM Option P3 resolved by adding
`INV-VPM-WRAPPER-001` to PV-CI allowlist pinning `vapi-vpm-manifest-v1` wrapper
schema literal. Ceremony: phrase "I understand this changes a frozen protocol
invariant" piped to `--confirm-governance`. Allowlist regenerated 69 → 70
entries. VED-INV-067 alias added to VEDIP-0001 Appendix A.

**Discipline:** PV-CI invariant change via governance ceremony per VED-INV-N
aliasing discipline.

### 5.5 VED-INV-N Aliasing Convention

**Event:** VBDIP-0001 §5.1 introduced `VED-INV-N` as documentation alias over
engineering/protocol PV-CI entries. VEDIP-0001 §5 and Appendix A locked the
convention: `VED-INV-N` is documentation-only count abstraction. Native PV-CI
IDs (e.g., `INV-FRR-001`, `INV-OPERATOR-AGENT-001`, `INV-ZKBA-002`) remain
unchanged in source control. No code or allowlist-file rename performed under
VED prefix.

**Discipline:** Documentation-aliasing discipline; not a code-level rename.
Future PV-CI invariants continue to use phase-anchored IDs; `VED-INV-N` appears
only in methodology cross-references where count abstraction is useful.

### 5.6 BT v1.0 → BT v1.1 Architectural Revision

**Event:** Original BT calibration proposal naming BLE-derived L4 features
(`connection_interval_jitter`, `advertisement_period_drift`,
BLE-specific `retransmission_rate`) superseded by canonical anchor and v1.1
architectural revision. DualSense and DualSense Edge transport is BR/EDR with
HIDP, not BLE/HOGP. `[SUPERSEDED-BT-CALIB-LESSON-001]` annotation
established. Verification gap documented in `lessons.md` entry
`BT-CALIB-LESSON-001`.

**Discipline:** Supersession with `[SUPERSEDED-{version}]` annotation per
`Architectural revisions live in wiki/methodology/bt_calibration_v*.md with
monotonic version numbers` discipline.

### 5.7 Sensor Stack v2.0 → v2.1 Architectural Revision

**Event:** Original sensor-stack ideation naming microphone array as multi-mic
acoustic-fingerprinting surface superseded. The DualSense exposes a single mono
UAC1 stream post-DSP, not a multi-mic array; multi-mic literature does not
transfer. Privacy-falsification path (BIPA litigation, GDPR Art. 9, CIPA
two-party-consent) explicitly named. `[SUPERSEDED-TRACK1-LESSON-002]` and
`[SUPERSEDED-TRACK1-LESSON-003]` annotations established.

**Discipline:** Supersession with `[SUPERSEDED-{version}]` annotation per
`Architectural revisions live in wiki/methodology/sensor_stack_v*.md with
monotonic version numbers` discipline.

---

## §6 Reading-Order Guidance

For operators new to the methodology layer, the recommended reading order
across the corpus is the following dependency-resolved path.

**Tier 1 first, in framework order:**

1. `VSDIP-0001` (`vsd_methodology_v1_FINAL.md`) — foundational synthesis discipline; 16 VSD invariants
2. `VSDIP-0002` (`vsd_volume_2_final.md`) — Volume 2 expansion; 7 additional invariants; VRR/CDRR primitives; CFSS
3. `VBDIP-0001` (`VBDIP-0001-vad-framework-introduction.md`) — VAD top-level framework; three sub-disciplines; four VBD invariants; signing chain
4. `VBDIP-0002` (`VBDIP-0002-zkba-visual-projections.md`) — ZKBA primitive + VPM wrapper + Anti-Hype Visual Grammar
5. `VEDIP-0001` (`VEDIP-0001-engineering-discipline-retrospective.md`) — seven engineering disciplines; VED-INV-N alias mapping

**Tier 3 second, for state-establishment context:**

6. `METHODOLOGY_LAYER_INTEGRATION_MAP.md` — Layer 7 architectural elevation snapshot
7. `layer7_closure_2026-05-13.md` — 7-of-7 ZKBA coverage closure
8. `INTEGRATION_PROVENANCE_2026-05-10.md` — VBDIP-0001 integration provenance witness
9. `vapi_state_assessment_2026_05_10.md` — PBSA snapshot

**Closed-loop synthesis last:**

10. `CLOSED_LOOP_FOUNDATIONAL_ARCHITECTURE.md` — companion synthesis essay (composes against all above)

**Tier 2 references** (operator-discretion; cite as needed):

- `vsd-vault/proposals/drafts/VBDIP-0002-vs-0002A-reconciliation.DRAFT.md`
- `vsd-vault/proposals/drafts/OPERATOR-DECISION-MATRIX.DRAFT.md`
- `vsd-vault/proposals/drafts/VBDIP-0002-schema-name-reconciliation.DRAFT.md` (RESOLVED)
- `vsd-vault/proposals/drafts/VBDIP-0002A-verified-projection-media.DRAFT.md` (PARTIALLY ABSORBED)

**Architectural prerequisite anchors** (for sub-domain work):

- BT-related design: `bt_calibration_v1_1_architectural_revision.md`
- Sensor-stack design: `sensor_stack_v2_1_architectural_revision.md`
- Universal-controller presence / CCO×PoEP fusion: `CCO_POEP_FUSION_v4.md`, `CCO_T0_POLICY_v1.md`, `CCO_PHASE_A_ORACLE_CONTRACT_v1.md`

---

## §7 Whitepaper Anchors and External References

The methodology corpus interfaces with the protocol's public-facing documentation
through two anchors.

### 7.1 Whitepaper v4 §9.29 — Methodology Layer Integration

The canonical successor whitepaper at `docs/vapi-whitepaper-v4.md` integrates the
Methodology Layer at §9.29 (commit `e8cc40ca`). The integration captures the
Layer 7 architectural elevation at the protocol-spec level: VAD framework,
PATTERN-017 #10 ZKBA, VPM wrapper, manifest validator, reach trio, signing chain,
PV-CI invariant coverage.

Synthesis composing against Whitepaper v4 §9.29 treats it as **outward-facing
restatement** of the Methodology Layer Integration Map (Tier 3). The whitepaper
is not Tier 1 methodology authority; it is the public-facing translation of
methodology layer state.

### 7.2 Whitepaper Versioning Discipline

`docs/WHITEPAPER_VERSIONING.md` establishes the whitepaper versioning convention.
The current canonical successor is v4 (architecture anchor `e81e04aa`, documentation
revamp `9f8581cd`, precision tuning `9a335c1b`). The v3 Zenodo DOI
`10.5281/zenodo.18966169` is preserved as historical baseline.

Synthesis cites whitepaper versions by canonical commit hash plus version number.

### 7.3 Bridge Wallet Anchor

The bridge wallet `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` is the load-bearing
identity anchor for all VAPI methodology work across all sub-disciplines per
VBD-INV-001 (continuous deployer-verified provenance under fleet expansion).
Any methodology document carrying signed authorship must chain to this wallet
either directly (secp256k1 signatures by the wallet) or through the architect
Ed25519 key chain (Ed25519 key signed once by the wallet at bootstrap establishing
the deployer-anchored synthesis key).

---

## §8 Cross-References

### 8.1 Within Methodology Layer

All documents listed in §2 (Tier 1), §3 (Tier 2), §4 (Tier 3).

### 8.2 Within VAPI Protocol

- `bridge/vapi_bridge/zkba_artifact.py` — ZKBA primitive module (PATTERN-017 #10)
- `bridge/vapi_bridge/store.py` — `zkba_artifact_log` table + Phase 1200 VPM migrations
- `bridge/vapi_bridge/operator_api.py` — ZKBA + VPM endpoints
- `scripts/vsd_ui_compiler.py` — deterministic UI compiler with FROZEN static guards
- `scripts/vsd_vpm_wrapper.py` — VPM wrapper module
- `scripts/zkba_manifest_validator.py` — G4 manifest validator
- `scripts/zkba_compile_*.py` — 7 per-class compilers (AIT/GIC/VHP/HARDWARE/CONSENT/TOURNAMENT/MARKET)
- `scripts/vpm_audit.py` — VPM observability audit
- `scripts/vpm_visual_grammar.py` — FROZEN 6-state DOM signature matrix
- `scripts/layer7_coverage_audit.py` — 7-of-7 coverage mechanical verification
- `scripts/replay_artifact.py` — Reproducibility Receipt verifier
- `sdk/vapi_sdk.py` — `VAPIZKBA` + `VAPIZKBAValidator` clients
- `vapi-mcp/knowledge_server.py` — 4 ZKBA MCP tools
- `scripts/vapi_invariant_gate.py` — PV-CI gate (`--proposal-type=all` runs all three sub-discipline invariants)
- `.github/INVARIANTS_ALLOWLIST.json` — 83 entries at synthesis-authoring time (66 protocol + 7 ZKBA + VPM + FRR + parallel-anchor + Curator-O2 + O3-watcher + UI-drawer + VPM-anchor + CFSS-sweeper + FSCA-CFSS-rule + 3 VBD-native)

### 8.3 Architect Signing Chain

- `vsd-vault/architect_key.pem` (gitignored; private key never committed)
- `vsd-vault/architect_pubkey.pem` (public key, committed)
- `vsd-vault/eval/architect_key_attestation.json` (bridge wallet EIP-191 attestation)
- `vsd-vault/manifests/proposals-VBDIP-0001/001.manifest.json` (first signed methodology manifest)

### 8.4 External Anchors

- IoTeX testnet (chain ID 4690)
- Bridge wallet `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`
- 49 LIVE contracts at `contracts/deployed-addresses.json`
- ProtocolCoherenceRegistry LIVE `0xfAfe4E8BEE45be22836b90D542045510dDd927Dd` (Phase 221, 2026-04-17)
- AdjudicationRegistry LIVE `0x44CF981f46a52ADE56476Ce894255954a7776fb4` (Phase 111, 2026-03-27)
- Zenodo whitepaper v3 DOI `10.5281/zenodo.18966169`

---

## §9 What This Index Does NOT Do

The index is a catalog. It does not author new methodology content. Explicit
non-doings:

- Does not modify any FROZEN Tier 1 content.
- Does not modify any Tier 2 in-flight document.
- Does not propose new PV-CI invariants.
- Does not authorize Track 2 activation for any future ceremony.
- Does not resolve any remaining decisions in `OPERATOR-DECISION-MATRIX.DRAFT.md`.
- Does not run a signing ceremony at first commit (Tier 2 status preserved).
- Does not change the unified `vapi_invariant_gate.py` harness configuration.
- Does not change `.github/INVARIANTS_ALLOWLIST.json`.
- Does not produce any chain submission.
- Does not consume any IOTX from the bridge wallet.
- Does not edit `CLAUDE.md` (project-level operator memory remains canonical).
- Does not promote any Tier 2 document to Tier 1.
- Does not author any new VBDIP / VEDIP / VSDIP proposal.

The index's value is consolidation: future operators reading any single
methodology document now have a single tier-classified reference showing how
their document composes against the broader corpus.

---

## §10 Authoring Boundary

- Repository branch: `main`
- Preceding pushed commit: at synthesis-authoring time, post `48e177e5` (Stream A Wave 1 ABI/CONSENT/DEVICE_ID closures)
- Bridge tests at boundary: 3469 (Stream A post-fix count per CLAUDE.md NOTE 2026-05-14)
- SDK tests at boundary: 562
- Hardhat tests at boundary: 668
- PV-CI entries at boundary: 83
- Wallet impact of this document: 0 IOTX
- On-chain impact of this document: none
- Kill-switch posture verified locally: `CHAIN_SUBMISSION_PAUSED=true`
- Companion document: `CLOSED_LOOP_FOUNDATIONAL_ARCHITECTURE.md` (ships in same atomic commit)
- Tier classification of this document: **Tier 2 in-flight reference**
- Signing posture: deferred; promotion to Tier 1 via future operator-authorized
  architect Ed25519 ceremony at `vsd-vault/manifests/methodology-INDEX-v1.0/001.manifest.json`

This document intentionally does not run a signing ceremony. The architect
signing chain established by VBDIP-0001 remains available for any future
operator-authorized formal manifest.

---

**End of Methodology Layer Authoritative Index v1.0.**

The methodology corpus is now tier-classified at the document level. Every
methodology document has an explicit tier, a defined cite-discipline, and a
documented role in the corpus. Future operators reading any single methodology
document can resolve from this index which tier the document inhabits and how
synthesis may compose against it.

The companion document `CLOSED_LOOP_FOUNDATIONAL_ARCHITECTURE.md` advances the
synthesis claim that this index supports: the methodology layer is one element
of a six-segment verifiable pathway with four preserved source-of-truth
boundaries. The two documents ship as one atomic methodology-only commit.

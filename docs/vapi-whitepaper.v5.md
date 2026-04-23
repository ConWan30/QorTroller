# VAPI: Verified Autonomous Physical Intelligence
## A Controller-Native, Cryptographically Governed Human-Eligibility Protocol for Competitive Gaming

**Author:** Contravious Battle  
**Repository:** https://github.com/ConWan30/vapi-pebble-prototype  
**Version:** 5.0 - Phase 229 Canonical Draft  
**Date:** 2026-04-19  
**Status:** Supersedes the narrative emphasis of `vapi-whitepaper.v4.md` while preserving `v4` as a historical document

---

## Preface

Earlier VAPI whitepapers correctly established the project's core evidence primitive, agent fleet, credential system, and on-chain architecture. They also reflected the state of the project at the time they were written: a protocol centered on cryptographic human-presence proof, Agentic-as-a-Service (AGaaS), Verified Human Proof (VHP), and DePIN-oriented infrastructure.

By Phase 229, the real identity of VAPI has become narrower, sharper, and more defensible.

**VAPI is a controller-native, cryptographically governed human-eligibility protocol for competitive gaming.**

It transforms physical controller evidence into a machine-verifiable decision about whether a gameplay session is defensibly attributable to the claimed enrolled human competitor. It then governs that decision with frozen invariants, provenance anchoring, contradiction monitoring, and staged enforcement controls.

That shift matters. Tournament organizers do not ultimately need a generic "agent platform," a generalized DePIN story, or a broad anti-cheat brand. They need a high-trust eligibility primitive that answers one operational question:

> Can we defend the claim that the controller session we are seeing came from the claimed human competitor, under explicit protocol assumptions, with a public and auditable evidence trail?

This whitepaper is organized around that question.

---

## Executive Summary

Competitive gaming still lacks a rigorous eligibility layer. Existing anti-cheat systems can often detect known software cheats, but they do not provide a public, machine-verifiable basis for saying that a gameplay session is attributable to the claimed human competitor. They detect software anomalies; they do not prove human eligibility.

VAPI addresses that gap by combining five elements:

1. A frozen 228-byte cryptographic evidence primitive called the Proof of Autonomous Cognition (PoAC).
2. A controller-native sensing surface rooted in the physical behavior of a certified controller and the body operating it.
3. A layered Physical Input Trust Layer (PITL) that evaluates structural integrity, passive physics coupling, temporal regularity, and biometric behavior.
4. A governance stack that anchors protocol coherence, invariant changes, and governance provenance on-chain.
5. A staged enforcement model that refuses to collapse research milestones into premature live blocking.

This version of the paper is written after the key Phase 229 milestone:

- The Active Isometric Trigger (AIT) probe is the first VAPI probe type to achieve `all_pairs_above_1=True`.
- The measured AIT separation ratio is `1.199` at `N=24` sessions on 2026-04-18.
- All three player-pair distances exceed `1.0`:
  - `P1vP2 = 1.850`
  - `P1vP3 = 1.846`
  - `P2vP3 = 1.349`
- Leave-one-out classification accuracy is `66.7% (16/24)`.
- Full covariance is now statistically supported for this probe (`N/p = 6.0 > 3.0`).

This does **not** mean VAPI has solved universal biometric identity in gaming. It **does** mean the project has crossed a crucial threshold: it has demonstrated, on a live protocol path, the first probe type whose inter-person defensibility clears the all-pairs gate required for tournament-facing eligibility logic.

At the same time, VAPI remains operationally honest:

- The protocol is **post-separation-breakthrough**.
- It is still **pre-live-enforcement**.
- Dry-run graduation and tournament preflight remain staged and gated.
- The bridge remains the weakest trust boundary.
- Zero-knowledge session proofs and some operator-facing documents still require further production alignment.

The right way to understand VAPI now is not as "just anti-cheat," and not as "just a DePIN product." It is a controller-native human-eligibility layer with cryptographic evidence, biometric separation, self-auditing governance, and controlled activation.

---

## Table of Contents

1. [The Proof Gap in Competitive Gaming](#1-the-proof-gap-in-competitive-gaming)
2. [What VAPI Is](#2-what-vapi-is)
3. [The PoAC Evidence Primitive](#3-the-poac-evidence-primitive)
4. [The Physical Input Trust Layer](#4-the-physical-input-trust-layer)
5. [Inter-Person Separation Is the Real Scientific Problem](#5-inter-person-separation-is-the-real-scientific-problem)
6. [Governance: Proving the Verifier](#6-governance-proving-the-verifier)
7. [Staged Enforcement and Operational Honesty](#7-staged-enforcement-and-operational-honesty)
8. [System Architecture and Current Deployment](#8-system-architecture-and-current-deployment)
9. [VAPI-Specific Novelty Claims](#9-vapi-specific-novelty-claims)
10. [Security Model and Threat Boundaries](#10-security-model-and-threat-boundaries)
11. [Current State at Phase 229](#11-current-state-at-phase-229)
12. [Integrations, Credentials, and Ecosystem Consequences](#12-integrations-credentials-and-ecosystem-consequences)
13. [Limitations and Next Milestones](#13-limitations-and-next-milestones)
14. [Conclusion](#14-conclusion)
15. [Appendix A: Technical Reference](#appendix-a-technical-reference)
16. [Appendix B: Canonical Disclosure Statement](#appendix-b-canonical-disclosure-statement)

---

## 1. The Proof Gap in Competitive Gaming

### 1.1 Anti-cheat is not the same thing as eligibility

Traditional anti-cheat systems answer questions like:

- Is known cheat software running?
- Does player input look suspicious?
- Is a process or kernel path behaving abnormally?

These are useful questions, but they are not sufficient for tournament-grade trust.

Tournament operators, regulators, league administrators, and dispute reviewers eventually need a different answer:

> Is this gameplay session defensibly attributable to the claimed human competitor?

That is an eligibility question, not just a cheat-detection question.

### 1.2 Why existing approaches cannot close the gap

Most anti-cheat systems are software-native. They observe game memory, process behavior, operating system state, or network signatures. They can be effective against known cheats and many classes of software abuse. But they do not reach the physical boundary where a real controller, real muscles, real posture, and real timing interact.

That leaves a structural proof gap:

- A hardware intermediary can manipulate controller signals without looking like a conventional software cheat.
- Remote play, boosting, account sharing, or human substitution can preserve "human-like" input while defeating player attribution.
- Behavioral anomaly scoring can say "this looks strange" without creating a public, machine-verifiable audit trail that tournament operators can defend.

VAPI exists because probability alone is not enough for high-stakes eligibility.

### 1.3 The correct problem statement

The core problem is not:

> "Can we detect whether something looks bot-like?"

The core problem is:

> "Can we construct a protocol in which controller evidence is cryptographically intact, physiologically plausible, and sufficiently separable across players to support a defensible eligibility decision?"

This formulation has three parts:

- **Cryptographic integrity**: the evidence stream must be signed, ordered, replay-resistant, and tamper-evident.
- **Physical plausibility**: the evidence must remain consistent with a real human body operating a real certified controller.
- **Inter-person defensibility**: the resulting behavioral evidence must not merely look human in the abstract; it must be defensibly attributable to the claimed enrolled competitor under the protocol's measurement regime.

That third requirement is what ultimately forced VAPI to evolve from a generic "human presence" story into a sharper human-eligibility protocol.

---

## 2. What VAPI Is

### 2.1 Canonical definition

VAPI is a controller-native, cryptographically governed human-eligibility protocol for competitive gaming.

Its purpose is to convert physical controller evidence into a machine-verifiable eligibility decision about whether a session is defensibly attributable to the claimed enrolled human competitor, then govern that decision with provenance, invariant controls, and staged enforcement.

### 2.2 One-sentence purpose

**VAPI exists to create a public, auditable eligibility layer for competitive gaming, where entry is granted only when controller evidence is cryptographically intact, physiologically plausible, and defensibly separable from other players.**

### 2.3 What VAPI proves, measures, governs, and does not yet claim

| Category | VAPI provides today | Notes |
|----------|---------------------|-------|
| Cryptographic proof | Signed, hash-linked, replay-resistant PoAC evidence | This is the hard evidence rail. |
| Empirical measurement | PITL layer outputs, structured probe statistics, pairwise separation metrics | These are measurements and protocol judgments, not metaphysical proof of "humanness." |
| Governance assurance | Protocol coherence anchors, invariant gates, governance provenance chains, contradiction monitoring | The verifier itself is placed under protocol discipline. |
| Enforcement control | Dry-run logging, staged graduation, rollback-aware activation | Enforcement is intentionally not treated as all-or-nothing. |
| Not yet claimed | Universal biometric identity, full production live blocking, complete elimination of bridge trust, fully mature ZK enforcement | These remain bounded limitations. |

### 2.4 Why controller-native matters

VAPI is "controller-native" because its evidence surface is rooted in the controller itself:

- USB HID reports
- trigger dynamics
- analog stick behavior
- accelerometer and gyroscope measurements
- posture and grip-linked physics
- challenge-response paths on supported hardware features

This matters because controller-native evidence is closer to the physical act being evaluated. VAPI is not trying to infer player truth only from software state or generic telemetry. It is trying to attach the eligibility claim to the physical interface through which competitive gaming actually happens.

### 2.5 Why the protocol is governed, not merely deployed

By Phase 229, VAPI is no longer just "a set of contracts and services." It is a governed protocol in which:

- certain formulas are frozen,
- certain file regions are invariant-gated,
- governance events produce chained provenance hashes,
- protocol coherence is anchored on-chain,
- and some classes of governance changes can themselves require biometric presence.

This is central to the project. VAPI now treats the integrity of the verifier as part of the protocol, not as an off-chain operational assumption to be ignored.

---

## 3. The PoAC Evidence Primitive

### 3.1 The Proof of Autonomous Cognition record

The foundational data structure of VAPI is the Proof of Autonomous Cognition (PoAC) record.

Each PoAC record is a frozen 228-byte structure:

| Field | Bytes | Description |
|-------|-------|-------------|
| Body | 164 | Previous-link material, sensor commitment, model and world-model commitments, inference and control fields, counters, timestamp, location, bounty metadata |
| Signature | 64 | ECDSA-P256 signature over the body |

This format is intentionally frozen. The protocol treats the 228-byte wire format as an invariant because the evidence rail must remain stable across firmware, bridge, SDK, and contract layers.

### 3.2 Core PoAC invariants

The most important invariants are:

- `record_hash = SHA-256(raw[:164])` — body ONLY, never the full 228-byte record
- The 228-byte format is frozen.
- Device identity is derived from the certified key material, not from mutable session metadata.

The body hash covers the 164-byte signed body only. The 64-byte ECDSA-P256 signature is excluded from the hash input. Computing a hash over the full 228 bytes is explicitly forbidden — doing so would include the signature in the commitment, violating the separation between the signed evidence and the chain link.

### 3.3 What the PoAC rail actually guarantees

PoAC gives VAPI its hardest guarantees:

- **Origin under stated key assumptions**: the evidence came from the key authorized to sign the record.
- **Ordering**: records form an ordered, hash-linked evidence stream.
- **Tamper evidence**: modification, deletion, or substitution breaks integrity checks.
- **Replay resistance**: monotonic counters, timestamps, and related replay protections constrain reuse.

These are strong guarantees, but they are not the entire protocol. PoAC proves the integrity of the evidence rail. It does not, by itself, prove that the person operating the controller is the claimed human competitor. That is why PITL, structured probes, separation analysis, and governance layers exist.

### 3.4 Privacy-preserving consistency proofs

VAPI includes a zero-knowledge session proof path for privacy-preserving consistency checks. In its intended form, the ZK layer is meant to prove consistency between commitments and selected public facts without revealing raw biometric features on-chain.

However, the correct production framing is careful:

- the ZK path is part of the protocol architecture,
- it improves privacy and commitment binding,
- but it should not be described as if it already closes every raw-to-feature-to-inference gap end-to-end under all deployment modes.

VAPI's bridge trust boundary remains the weakest link precisely because some of the strongest future assurances still depend on full production alignment of ZK and bridge behavior.

### 3.5 Why the evidence primitive matters

PoAC is the reason VAPI can make public, machine-verifiable claims at all. Without a fixed evidence primitive, the project would collapse into application logic and off-chain heuristics. With PoAC, VAPI becomes a protocol: an evidence rail first, and a verdict system second.

---

## 4. The Physical Input Trust Layer

### 4.1 Overview

The Physical Input Trust Layer (PITL) is the detection and attribution engine that reasons over controller evidence.

Its layers include structural checks, passive physics-coupling checks, advisory biometric analysis, temporal analysis, and optional active challenge-response paths.

At a high level:

| Layer | Role | Nature |
|-------|------|--------|
| Structural layers | Verify hardware presence, protocol compliance, and chain integrity | Hard gate |
| Coupling layers | Evaluate whether input remains physically consistent with a held controller | Hard or high-weight advisory |
| Behavioral layers | Detect suspicious timing and movement regularities | Mixed |
| Biometric layers | Measure consistency and separability of player-linked features | Advisory, but strategically central |
| Challenge layers | Perturb the system and measure response | Strong differentiator where supported |

### 4.2 Passive physics coupling

The core intuition behind PITL is that software-only manipulation has difficulty satisfying all controller-native physical channels simultaneously.

Examples include:

- HID behavior without consistent inertial behavior
- button or trigger events without plausible motion coupling
- motion noise without causal relation to actuation
- regular timing that compresses human variance too aggressively

No single passive signal is treated as infallible. Instead, VAPI relies on layered inconsistency. The more channels an adversary must fake simultaneously, the more expensive and brittle the attack becomes.

### 4.3 Advisory versus hard layers

A mature eligibility protocol cannot reduce every signal to a single binary gate. VAPI therefore separates:

- **Hard failures**: structural conditions whose breakage is immediately disqualifying.
- **Advisory evidence**: signals that contribute longitudinal evidence, anomaly patterns, or biometric distance judgments without automatically forcing a block on a single observation.

This is one of VAPI's better design decisions. It avoids pretending that every biometric deviation is dispositive while still preserving strong fail-closed behavior where structural integrity is actually broken.

### 4.4 Why structured probes became necessary

The early VAPI story focused heavily on general gameplay telemetry. Real corpus work showed that this was not enough.

Certain game genres and input profiles leave many candidate features structurally inactive:

- touchpad channels can remain zero,
- dual-trigger features may never engage,
- right-stick tremor features can collapse when the right stick sits in the dead zone,
- pooled corpus analysis can bury meaningful within-probe structure.

This forced a conceptual advance: **structured probes** are not peripheral tools; they are a first-class scientific method inside the protocol.

Structured probes let VAPI deliberately activate discriminative behavior under controlled conditions rather than hoping that normal gameplay exercises the right feature set.

### 4.5 Why this matters in NCAA College Football 26

VAPI's primary corpus is NCAA College Football 26. That title exposed a critical truth:

- generic gameplay can be sufficient for anomaly detection,
- but it may be inadequate for tournament-defensible inter-person separation.

The project therefore had to evolve beyond "extract more features from ordinary play" into "design probe regimes whose physics and posture produce stable, player-distinct signal."

This is one of the key intellectual transitions that led directly to Phase 229.

---

## 5. Inter-Person Separation Is the Real Scientific Problem

### 5.1 Intra-player anomaly detection is not enough

Earlier versions of VAPI often described L4 Mahalanobis biometric analysis as a major layer of the protocol. That remains true, but the interpretation has changed.

A biometric oracle that says:

> "this session looks different from your usual sessions"

is useful for anomaly detection.

But tournament eligibility requires something stronger:

> "this session is defensibly attributable to the claimed enrolled competitor rather than another player or another source of human-like input."

That is an inter-person separation problem.

### 5.2 What the early corpus revealed

Early inter-person analysis was blunt and humbling.

The March 8, 2026 inter-person report over 64 usable sessions found:

- mean intra-player distance: `0.635`
- mean inter-player distance: `0.230`
- separation ratio: `0.362`
- leave-one-out accuracy: `42.2%`

The conclusion was explicit: **no separation**.

Later analysis improved the picture, but not enough to justify a tournament gate. Even when ratios improved, pairwise weakness remained. One probe could show a ratio above `1.0` while still failing the all-pairs criterion because one player pair remained too close.

### 5.3 Why global ratio was not the correct gate

This is one of the most important conceptual lessons in VAPI.

Global or pooled ratios can be misleading because:

- one pair can remain a blocker while the average looks healthy,
- mixed session types can inflate intra-player variance,
- a favorable outlier can dominate the mean,
- and a global scalar hides the operational reality of tournament disputes, which occur pairwise and individually.

That is why VAPI evolved toward the `all_pairs_above_1=True` gate and away from a naive obsession with pooled ratio alone.

The project learned, correctly, that a lower global ratio with all pairs clearing the threshold is more defensible than a higher global ratio with a hidden weak pair.

### 5.4 The decision framework

The separation decision framework formalized this learning:

- pooled corpus ratio is **not** the tournament metric,
- per-type analysis is the defensible unit,
- convergence and non-convergence must be tracked explicitly,
- commitment requires more than "ratio looks good."

This was not just documentation. It represented a methodological correction inside the protocol.

### 5.5 The AIT breakthrough

Phase 229 introduced the Active Isometric Trigger (AIT) probe.

AIT is simple in concept and strong in consequence:

- the player holds `L2` at roughly 50 percent analog force (`90-180`) for 30 seconds,
- the controller remains in a stable normal playing posture,
- the system extracts a compact 4-feature fingerprint:
  - `accel_tremor_peak_hz`
  - `roll_cos`
  - `roll_sin`
  - `pitch_cos`

These features matter because they combine:

- tremor information from a still-hold condition,
- posture-derived gravity orientation,
- circular encoding that avoids angle wraparound,
- and a probe structure that is intentionally designed to expose stable inter-person differences.

### 5.6 Why AIT worked

AIT succeeded because it did not ask ordinary gameplay to accidentally reveal the right biometric axes. It deliberately created a controlled biomechanical state:

- the trigger force is constrained,
- the controller posture is stabilized,
- the right stick can remain neutral,
- tremor can be extracted from accelerometer magnitude via a 4096-point FFT,
- and gravity orientation becomes a usable anatomical signal.

This is not an incidental optimization. It is the first probe design in VAPI that fully reflects the lesson that inter-person separation requires probe design, not just generic telemetry harvesting.

### 5.7 What Phase 229 actually proved

As of 2026-04-18:

- `separation_ratio = 1.199`
- `all_pairs_above_1 = True`
- `P1vP2 = 1.850`
- `P1vP3 = 1.846`
- `P2vP3 = 1.349`
- `LOO accuracy = 66.7%`
- `N = 24`

This means:

- VAPI has crossed its first all-pairs gate on a real probe path.
- The protocol now has an empirically supported argument that at least one probe regime produces tournament-relevant inter-person defensibility.
- The project has moved beyond "interesting anomaly detection research" into an early but real eligibility primitive.

It does **not** mean:

- that VAPI has solved universal biometric identity,
- that every game and every probe will perform this way,
- that the live tournament path should be activated without staged validation,
- or that further player-count expansion is optional.

The correct reading is: **breakthrough, not completion**.

---

## 6. Governance: Proving the Verifier

### 6.1 Why this chapter exists

Many systems are content to ask users to trust the verifier. VAPI is increasingly unwilling to do that.

If a protocol makes eligibility decisions with economic and competitive consequences, then the integrity of the verifier cannot remain an informal operational assumption. It has to become part of the protocol surface.

This is why the recent governance phases matter so much. They are not peripheral administration. They are an extension of the same worldview that produced PoAC:

- evidence should be anchored,
- state changes should be attributable,
- critical logic should be frozen where appropriate,
- and dangerous changes should leave a tamper-evident trail.

### 6.2 Protocol Coherence

Protocol Coherence introduced an on-chain Merkle anchor over the fleet state. Later phases extended that anchor with governance provenance hashes so that the protocol does not only say "the fleet was coherent," but also "the current governance provenance is the one that was actually anchored."

This is a strong conceptual move. It turns the verifier from:

> "software we say was running"

into:

> "a protocol state whose coherence and governance provenance are themselves evidence-bearing objects."

### 6.3 Invariant gates and frozen code regions

VAPI now has a Protocol Invariant Continuous Integration gate that:

- hashes critical code regions,
- stores allowlisted digests,
- requires explicit reasoning for changes,
- and treats some formulas and structures as frozen protocol constants rather than casual implementation details.

This is especially important because VAPI's strongest claims depend on exact semantics:

- PoAC layout
- hash functions
- separation-related formulas
- provenance-hash construction
- and governance workflows

A protocol that claims rigor but allows silent drift in these regions has already undermined itself.

### 6.4 Governance provenance chain

Governance changes in VAPI now form a chained provenance history:

- each change can carry a previous provenance hash,
- the resulting governance hash is committed to a chain,
- coherence anchors can include governance provenance,
- and broken governance links can be detected as contradictions or inversions.

That means the question:

> "How did the protocol become this protocol?"

has a structured answer inside the system.

### 6.5 VHP-gated invariant changes

One of the most distinctive governance moves in Phase 228 is the introduction of VHP-gated invariant change authorization.

When enabled, invariant-category governance changes can require live VHP evidence from the proposer.

This matters because it aligns the governance layer with the eligibility layer:

- the same protocol that demands human-linked evidence from players can also demand human-linked evidence from high-risk governance actions,
- reducing the asymmetry where user-facing trust is strict but protocol-editing trust is soft.

### 6.6 Contradiction, orphan, and inversion monitoring

FleetSignalCoherenceAgent and the broader coherence tooling matter because they operationalize verifier self-critique.

The system now tracks and reacts to:

- contradictions,
- orphaned conditions,
- and inversion patterns.

This is not merely observability. It is a protocol metabolism: a way of saying that unresolved verifier inconsistencies are themselves first-class protocol facts.

### 6.7 The deeper point

VAPI is unusual not just because it asks players to produce evidence, but because it increasingly asks the verifier to produce evidence about itself.

That is one of the project's most serious and underappreciated strengths.

---

## 7. Staged Enforcement and Operational Honesty

### 7.1 Why VAPI should not rush live blocking

A protocol like this can fail in two ways:

- it can be too weak and admit bad actors,
- or it can be too eager and block legitimate competitors on incomplete calibration.

VAPI's staged enforcement model is designed to avoid the second failure while the first is still being studied.

### 7.2 Dry-run is not a weakness; it is a discipline

Dry-run mode means:

- evidence is collected,
- verdicts are logged,
- governance and preflight logic can operate,
- but consequences are not yet universally forced.

This is often misread as incompleteness. In reality, for a protocol making claims this strong, dry-run is a form of scientific and operational discipline. It lets the system observe the consequences of its logic before turning them into irreversible player-facing action.

### 7.3 Graduation is staged and rollback-aware

The graduation system does not enable all agents simultaneously. It stages activation in sequence and includes rollback criteria tied to false positives.

That matters because the transition from research protocol to live eligibility gate is precisely where reputational and operational damage can occur if the protocol overreaches.

### 7.4 The real tournament preconditions

The current project state makes it clear that tournament activation requires more than a single favorable metric.

The meaningful commitment gate includes conditions such as:

| Condition | Why it matters |
|-----------|----------------|
| `separation_ok` | The probe's measured ratio must clear the threshold. |
| `all_pairs_p0_ok` | Every player pair must clear the defensibility floor. |
| `biometric_ttl_ok` | Eligibility evidence must remain fresh and renewable. |
| `non_convergence_clear` | The ratio path cannot be declining or unstable in a way that invalidates confidence. |
| `staged_graduation_enabled` | Enforcement must be intentionally activated, not assumed. |

This is the right kind of conservatism.

### 7.5 The correct state statement for Phase 229

The most accurate summary of the protocol today is:

**VAPI is post-separation-breakthrough, pre-live-enforcement.**

That statement is honest, strong, and strategically useful. It acknowledges the breakthrough without pretending that a research success instantly equals production maturity.

---

## 8. System Architecture and Current Deployment

### 8.1 High-level architecture

VAPI currently spans four primary layers:

1. **Controller-native evidence generation**
2. **Bridge and evidence-processing runtime**
3. **On-chain verification, credential, and governance contracts**
4. **SDK and operator-facing integration surfaces**

### 8.2 The bridge runtime

The bridge is the operational heart of the system:

- it receives and processes controller-native evidence,
- computes and stores protocol state,
- exposes operator and analytic endpoints,
- coordinates the agent fleet,
- and interacts with IoTeX contracts.

It is also the weakest trust boundary. VAPI's governance phases are best understood as partially compensating for this fact rather than denying it.

### 8.3 The agent fleet

The older VAPI narrative centered on a 20-agent fleet. By Phase 229, the operational environment has expanded significantly and includes at least 38 named background agents and monitors across calibration, corpus curation, coherence, governance, protocol anchoring, and adjudication-related duties.

The important point is not the count. The important point is that the fleet now serves three distinct functions:

- **evidence interpretation**
- **protocol self-monitoring**
- **governance and rollout control**

### 8.4 The contract stack

As of 2026-04-19:

- 45 contracts are live on IoTeX testnet (`chain_id = 4690`)
- the active deployer and bridge wallet is `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`

The live contract categories include:

| Category | Examples |
|----------|----------|
| Evidence and verification | `PoACVerifier`, `PITLSessionRegistry`, `PassportOracle` |
| Eligibility and credentials | `PHGRegistry`, `PHGCredential`, `VAPIVerifiedHumanProof`, `TournamentGate` variants |
| Separation and readiness | `SeparationRatioRegistry`, `VAPIProtocolLens`, supporting gate contracts |
| Governance and protocol integrity | `VAPIGovernanceTimelock`, `ProtocolCoherenceRegistry`, `VAPIBiometricGovernance` |
| Ceremony and audit | `CeremonyRegistry`, `CeremonyAuditRegistry` |

### 8.5 Public and operator-facing surfaces

VAPI exposes a growing set of operator and SDK surfaces, including status endpoints for:

- tournament blockers,
- per-pair gap status,
- protocol coherence,
- invariant gate state,
- governance history,
- and AIT separation status.

This is another important evolution. The project is no longer just implementing protocol logic; it is publishing the state required to reason about whether the protocol itself should trust its own next step.

---

## 9. VAPI-Specific Novelty Claims

This section does **not** claim an exhaustive survey of every external project in gaming, DePIN, or anti-cheat. Instead, it states the novelty claims that define VAPI's own design and what, taken together, makes its architecture unusually distinctive.

### 9.1 Novelty 1: Controller-native human eligibility

VAPI does not stop at anti-cheat detection or generic human-presence signaling. Its explicit target is a defensible eligibility decision rooted in controller-native evidence.

The novelty is not just "uses controller telemetry." It is:

- a frozen evidence primitive,
- a controller-rooted sensing surface,
- and a protocol whose purpose is eligibility rather than mere suspicion scoring.

### 9.2 Novelty 2: Inter-person separation as a first-class protocol gate

Many systems are satisfied when something looks human-like. VAPI's Phase 197 and later logic make `all_pairs_p0_ok` a first-class gate.

That is a major conceptual distinction.

The protocol is not satisfied with:

- generic humanness,
- intra-player anomaly detection,
- or global average improvement.

It explicitly demands pairwise defensibility.

### 9.3 Novelty 3: Structured probe methodology inside the protocol

AIT demonstrates that VAPI is not merely passively observing gameplay. It can define structured probe regimes whose purpose is to expose stable inter-person signal under game-specific and device-specific constraints.

This makes VAPI's biometric layer more protocol-like and less ad hoc.

### 9.4 Novelty 4: The verifier is itself under cryptographic governance

Protocol coherence anchors, invariant gates, provenance chains, and VHP-gated governance changes mean that VAPI does not simply verify players. It increasingly verifies the integrity of its own verification process.

That is one of the strongest candidates for a VAPI-exclusive conceptual contribution.

### 9.5 Novelty 5: Staged autonomous enforcement instead of immediate autonomy theater

Plenty of systems claim automation. VAPI's more interesting move is that it binds automation to:

- dry-run stages,
- explicit preconditions,
- rollback criteria,
- and measured tournament blockers.

That is a more mature notion of autonomy than simply saying "agents are running."

### 9.6 Novelty 6: Credentials, AGaaS, and DePIN become consequences, not premises

Earlier narratives led with VHP, AGaaS, and DePIN. The stronger interpretation is that these are consequences of the underlying eligibility architecture:

- VHP is the credentialized output,
- AGaaS is one delivery model,
- DePIN is one economic and deployment expression.

They are important, but they are no longer the thesis.

---

## 10. Security Model and Threat Boundaries

### 10.1 Threats VAPI is built to resist

VAPI is strongest against classes of attacks where the adversary must fake controller-native evidence without actually satisfying the underlying physical conditions. This includes many forms of:

- software-only input injection,
- timing-regular macros,
- inertial stripping,
- threshold-aware simplifications that fail multivariate consistency,
- and governance changes without proper protocol provenance.

The project also has increasingly strong protocol-level defenses against silent verifier drift.

### 10.2 Threats VAPI can partially resist but does not fully solve

Professional adversarial analysis already showed that some attacks can defeat individual features or batch proxies while remaining exposed elsewhere.

This is the correct way to read the security stack:

- no single feature is "the" defense,
- single-feature mimicry can succeed,
- but multi-layer inconsistency remains hard to sustain.

### 10.3 Known blind spots and bounded weaknesses

Important known boundaries include:

- biometric transplant or replay-like attacks with sufficiently faithful coupling
- invasive hardware compromise or key extraction
- bridge trust and mock-mode paths
- incomplete universalization of AIT-scale success across player populations and games

VAPI should not overclaim beyond these boundaries.

### 10.4 Why this threat posture is still meaningful

A protocol does not need to solve every adversary class to be valuable. It needs to:

- make meaningful attack classes harder,
- make disputes more evidentiary,
- reduce ambiguity around eligibility,
- and state honestly where the boundary still lies.

On that standard, VAPI is already significant.

---

## 11. Current State at Phase 229

### 11.1 Canonical snapshot

| Item | Status |
|------|--------|
| Current phase | `229 COMPLETE` |
| Device focus | DualShock Edge (Sony CFI-ZCP1) |
| Primary corpus title | NCAA College Football 26 |
| Contracts live | 45 |
| Key governance additions | Protocol Coherence, invariant gate, governance provenance, VHP-gated invariant changes |
| Separation milestone | AIT achieved first `all_pairs_above_1=True` |
| AIT ratio | `1.199` |
| AIT session count | `N = 24` |
| AIT LOO accuracy | `66.7%` |
| Operational state | Post-separation-breakthrough, pre-live-enforcement |

### 11.2 Test and validation posture

The repository now supports over 3,300 automated tests across bridge, contract, SDK, hardware, and end-to-end suites, with the bridge and SDK layers especially mature. This matters because VAPI is not just making claims in prose; it is increasingly surrounding those claims with automated protocol checks.

### 11.3 Why Phase 229 is a turning point

Phase 229 is not just another feature release. It is the first phase in which the project's most important open scientific blocker was crossed on at least one real protocol path.

That changes the right public story.

Before Phase 229, the project could honestly say:

> "The protocol architecture is strong, but the key biometric gate remains unproven."

After Phase 229, the project can honestly say:

> "The protocol has demonstrated its first all-pairs-clearing inter-person probe, and now the next task is disciplined scaling and controlled activation."

That is a materially stronger position.

---

## 12. Integrations, Credentials, and Ecosystem Consequences

### 12.1 Tournament operators

For tournament operators, the value proposition is direct:

- a public evidence rail,
- a structured eligibility story,
- a protocol that distinguishes measurement from activation,
- and a path toward defensible entry gating.

VAPI's most relevant operator-facing output is not a vague anti-cheat score. It is a protocol-governed basis for saying whether a competitor should be treated as eligible.

### 12.2 Developers and platforms

For developers, VAPI offers:

- an SDK layer,
- bridge endpoints,
- a composable integration surface,
- and the possibility of treating eligibility as an infrastructural primitive rather than custom one-off anti-cheat logic.

### 12.3 Hardware manufacturers

For controller manufacturers and accessory partners, the sharper framing is actually better.

"VAPI certified" hardware no longer just means "compatible with an anti-cheat platform." It means:

- the device contributes to a controller-native evidence primitive,
- it can participate in structured human-eligibility probes,
- and it can become part of a protocol where both user evidence and verifier governance are auditable.

That is a more serious certification story.

### 12.4 Credentials and VHP

Verified Human Proof remains important, but in the Phase 229 framing it should be understood as:

- the protocol credentialized output of VAPI's evidence and eligibility logic,
- not the sole identity of the protocol.

VHP is what the protocol issues. Human-eligibility is what the protocol is for.

### 12.5 AGaaS and DePIN

AGaaS and DePIN remain relevant, but they now belong later in the narrative:

- AGaaS describes one architectural delivery mode for a complex multi-agent service.
- DePIN describes one economic and deployment interpretation of controller and bridge infrastructure.

These are meaningful consequences. They should not obscure the core claim.

---

## 13. Limitations and Next Milestones

### 13.1 AIT must be scaled, not merely celebrated

The AIT breakthrough is real, but the next steps are clear:

- expand player count,
- expand session count,
- validate across calendar time,
- confirm transferability across comparable contexts,
- and connect the breakthrough cleanly into the live readiness and graduation path.

### 13.2 The bridge trust boundary still matters

The bridge remains the weakest trust boundary in the architecture. Continued work on ZK alignment, on-chain binding, and verifier discipline remains important.

### 13.3 Not every game will reveal signal the same way

NCAA College Football 26 forced VAPI to discover that some genres suppress useful biometric channels. The lesson is not that VAPI failed; it is that the protocol must remain structured-probe aware and game-aware.

### 13.4 Full live enforcement remains intentionally gated

The project should resist the temptation to convert Phase 229 directly into live tournament blocking without completing staged graduation and operational validation.

### 13.5 Documentation must catch up to protocol reality

Several operator- and developer-facing documents still reflect older readiness narratives. This whitepaper is part of the broader correction: the protocol story must now be updated to match the actual Phase 229 state.

---

## 14. Conclusion

VAPI's most defensible identity is now clear.

It is not best understood as a generic anti-cheat stack, and not best understood as a generic DePIN or agent platform. It is a controller-native, cryptographically governed human-eligibility protocol for competitive gaming.

Its foundation is the PoAC evidence rail.
Its scientific bottleneck is inter-person separation.
Its current breakthrough is AIT.
Its trust model now extends to the verifier itself through protocol coherence, invariant gates, and governance provenance.
Its operational discipline is staged graduation rather than premature enforcement theater.

That combination is what gives VAPI its seriousness.

The project has not solved everything. It has, however, crossed the point where its central claim can be stated much more sharply:

> A controller session can be turned into a public, protocol-governed eligibility artifact whose integrity is cryptographic, whose attribution is physiological and statistical, and whose verifier is increasingly forced to justify itself as rigorously as the player.

That is the real meaning of VAPI at Phase 229.

---

## Appendix A: Technical Reference

### A.1 Core constants and facts

| Item | Value |
|------|-------|
| PoAC size | 228 bytes |
| Body size | 164 bytes |
| Signature size | 64 bytes |
| `record_hash` | `SHA-256(raw[:164])` — body only, frozen invariant |
| Primary device | DualShock Edge CFI-ZCP1 |
| Chain | IoTeX Testnet |
| Chain ID | 4690 |

### A.2 Phase 229 AIT reference

| Metric | Value |
|--------|-------|
| Features | `accel_tremor_peak_hz`, `roll_cos`, `roll_sin`, `pitch_cos` |
| Hold condition | `L2` at 50 percent analog (`90-180`) |
| Duration | 30 seconds |
| FFT | 4096-point zero-padded accelerometer FFT |
| Search band | 4.0-15.0 Hz |
| Separation ratio | 1.199 |
| Pair distances | 1.850, 1.846, 1.349 |
| `all_pairs_above_1` | True |
| LOO accuracy | 66.7 percent |

### A.3 Governance stack reference

Recent governance and verifier-integrity milestones include:

- Phase 221: Protocol Coherence registry
- Phase 222: VAPIBiometricGovernance
- Phase 223: PV-CI invariant gate
- Phase 224: allowlist governance and on-chain anchor
- Phase 225: governance provenance chain
- Phase 226: invariant-scope expansion for provenance logic
- Phase 227: governance provenance included in coherence anchor
- Phase 228: optional VHP-gated invariant change authorization
- Phase 229: AIT probe path and first all-pairs-clearing separation milestone

---

## Appendix B: Canonical Disclosure Statement

The following statement may be reused in operator, investor, or partner materials:

> VAPI is a controller-native, cryptographically governed human-eligibility protocol for competitive gaming. It is not yet in universal live tournament enforcement. As of Phase 229, the protocol has achieved its first all-pairs-clearing inter-person separation breakthrough on the AIT probe path, while continuing to operate under staged enforcement and explicit governance controls. The protocol's current state is best described as post-separation-breakthrough and pre-live-enforcement.


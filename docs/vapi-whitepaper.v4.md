# VAPI: Verified Autonomous Physical Intelligence
## A Protocol for Cryptographically Proven Human Presence in Competitive Gaming

**Author:** Contravious Battle  
**Contact:** kamazi.shotta@icloud.com  
**Repository:** https://github.com/ConWan30/vapi-pebble-prototype  
**Version:** 4.0 — Canonical Reference  
**Date:** April 2026  
**Classification:** Public

---

## Executive Summary

*For the non-technical reader: This document describes a new kind of proof — a mathematical guarantee that a real, living human being played a video game using a physical controller. Today, no such proof exists. VAPI creates it.*

Online competitive gaming has a fundamental trust problem. Tournament organizers cannot prove that the person holding a controller is actually human. Sophisticated bots — software programs that play video games automatically — can pass every existing anti-cheat system because those systems only detect *known cheats*, not *the absence of a human*.

VAPI (Verified Autonomous Physical Intelligence) solves this at the root. It does not attempt to detect cheats after the fact. Instead, it continuously generates a chain of cryptographic evidence that proves — mathematically and physically — that the inputs being sent to a game originated from a living person's hands, not from software.

Each fraction of a second, VAPI's certified hardware captures physics measurements only a real human body can produce: the micro-tremors in a grip, the electrical conductance of skin under pressure, the causal timing between a finger's decision to press a button and the muscle movement that follows. These measurements are bundled into a 228-byte cryptographic record, signed by the device, hash-chained to the previous record, and eventually anchored to a public blockchain. The result is a tamper-evident evidence trail that can be verified by any third party, anywhere in the world, without access to the original hardware.

**What VAPI enables:**
- Tournament operators can require cryptographic proof of human presence as a condition of entry
- Players earn a "Verified Human Proof" — a non-transferable credential that confirms their eligibility
- The entire detection stack runs autonomously: 20 specialized AI agents operate continuously in the background, analyzing sessions, detecting anomalies, and managing credentials without human intervention

**Where VAPI stands today:**
- The core cryptographic system is complete and live on a public blockchain test network
- The agent fleet is operational
- The primary open challenge is biometric calibration across a larger player population — a well-understood engineering problem, not a fundamental limitation
- The protocol is not yet in live tournament enforcement mode; it operates in a validated research deployment

This document describes VAPI in full — what it is, how it works, what it has proven, what it has not yet proven, and where it is headed.

---

## Table of Contents

1. [The Problem: Gaming Anti-Cheat Has a Proof Gap](#1-the-problem)
2. [The VAPI Solution: Physics-Backed Cryptographic Proof](#2-the-vapi-solution)
3. [Core Cryptographic Foundation](#3-core-cryptographic-foundation)
4. [The Physical Input Trust Layer](#4-the-physical-input-trust-layer)
5. [The Autonomous Agent Fleet](#5-the-autonomous-agent-fleet)
6. [On-Chain Architecture and Smart Contracts](#6-on-chain-architecture)
7. [The Verified Human Proof Credential](#7-the-verified-human-proof)
8. [DePIN Integration and Economic Model](#8-depin-integration)
9. [Security Analysis and Threat Model](#9-security-analysis)
10. [Evaluation and Current State](#10-evaluation-and-current-state)
11. [Open Challenges and Honest Limitations](#11-open-challenges)
12. [Vision and Roadmap](#12-vision-and-roadmap)
13. [Technical Reference](#13-technical-reference)

---

## 1. The Problem

### 1.1 The Trust Gap in Competitive Gaming

Competitive online gaming is a rapidly growing industry. Global esports prize pools exceeded $1 billion in 2023. Casual tournaments, collegiate competitions, and community leagues represent billions more in entry fees, wagers, and sponsorship value. Yet the fundamental integrity of every one of these competitions rests on an assumption that cannot currently be verified: *that the player holding the controller is a human being.*

Modern anti-cheat systems — Epic Games' Easy Anti-Cheat, BattlEye, Riot Games' Vanguard — operate by signature detection. They maintain databases of known cheat software and inject protective code into the game process. When a known cheat is detected, the player is banned. This approach works well against *known* cheats. It fails categorically against unknown cheats, and it provides no defense at all against the most sophisticated attack: direct hardware injection.

A hardware injection attack places a programmable microcontroller between a legitimate gaming controller and the console. The microcontroller intercepts and modifies or replaces the physical button press and movement signals before they reach the game. From the game's perspective, the inputs look exactly like a human player. From the anti-cheat software's perspective, there is nothing to detect — no unauthorized code is running, no process is modified. The controller is legitimate; the player, for all intents and purposes, does not exist.

### 1.2 Why Existing Approaches Cannot Close This Gap

The detection gap is architectural, not a failure of execution. Existing anti-cheat systems live in software — inside the game process or the operating system kernel. They can detect software anomalies. They cannot observe the physical world. If an adversary operates entirely in the physical layer (a hardware device between controller and console, BLE signal injection, custom firmware on a certified controller), software-only detection has no signal to work with.

Statistical behavioral analysis improves on pure signature detection but cannot close the proof gap. A system that says "this player's mouse movements look too precise" produces a probability, not a proof. Tournament-level adjudication requires evidence, not statistics — particularly when prize money and competitive standing are at stake.

The only way to close the gap is to extend the evidence chain into the physical world and anchor it cryptographically. This is precisely what VAPI does.

### 1.3 The Human-Controller Attestation Problem

We define the problem formally:

> **Human-Controller Attestation**: Given a player who claims to have performed a gaming session on a physical controller, how can a tournament operator — with no access to the player's hardware — verify the *provenance* and *physical plausibility* of the player's controller input stream?

"Provenance" means the inputs actually originated from the certified device, not from software. "Physical plausibility" means the input patterns are consistent with human neuromuscular physiology, not algorithmic generation. Both requirements must be satisfied simultaneously. Neither is sufficient alone.

VAPI answers this question with a system that:
1. Generates a cryptographic evidence record tied to physics measurements at each moment of play
2. Anchors those records on a public blockchain
3. Runs an autonomous fleet of detection agents that continuously evaluate the evidence
4. Issues a non-transferable credential when a player's evidence consistently passes

---

## 2. The VAPI Solution

### 2.1 Overview

VAPI stands for **Verified Autonomous Physical Intelligence**. The name encodes the system's three defining properties:

- **Verified**: Every claim is backed by cryptographic evidence that can be independently audited. No trust in VAPI's operators is required — the evidence chain is public and self-verifiable.
- **Autonomous**: Detection, analysis, credential management, and enforcement are handled by a fleet of 20 specialized AI agents operating continuously without human intervention. The system does not require an operator to manually review sessions.
- **Physical**: The evidence chain is rooted in measurements of physical reality — hardware sensors, body physics, neuromuscular timing — that software alone cannot replicate.

The protocol produces a single, composable output: `isFullyEligible()`. This is a smart contract function that any tournament application can call, for any player's device ID, and receive a Boolean answer: *is this player eligible to compete, right now, based on cryptographic evidence?* The entire 20-agent detection stack, all seven layers of behavioral analysis, and the full biometric fingerprint operate behind this single call.

### 2.2 The Central Design Principle: Evidence Over Probability

VAPI does not produce a "cheating score" or a "suspicion level." It produces a **cryptographic commitment** — a mathematical object that either passes or fails a verification check. This distinction matters enormously:

- A probability score can be argued over. "My 0.73 cheating score is wrong — I just have unusual mouse movements." Courts and tournament arbiters cannot adjudicate probability.
- A cryptographic commitment either verifies or it does not. The chain hash either matches the stored value or it does not. The ECDSA-P256 signature is either valid or it is not. These are binary facts, not opinions.

The entire VAPI architecture is oriented around producing commitments, not scores. Behavioral analysis informs the verdict; the verdict itself is commitment-backed.

### 2.3 How It Works — The Player's Experience

*For the non-technical reader: here is what actually happens when VAPI is running.*

A player connects their certified DualShock Edge controller to their PC. VAPI's bridge software starts automatically. From the player's perspective, nothing is different — they play their game normally.

Invisibly, every millisecond, the controller is generating sensor data: the precise pressure on each adaptive trigger, the orientation of the controller in three-dimensional space (from gyroscope and accelerometer chips), the timing of every button press, and the pattern of micro-tremors produced by the living muscles in their hands. This sensor data is captured, processed, and assembled into compact 228-byte cryptographic records at a rate of many records per second.

Each record is signed with a key that only the certified device holds. Each record's hash is included in the next record, creating an unbreakable chain — like a blockchain of evidence records. If anyone tampers with any record anywhere in the chain, the hash breaks, and the entire chain is invalidated.

After each gaming session, VAPI's detection agents analyze the evidence. They look for 20+ behavioral signals across seven analytical layers — from simple hardware presence checks to sophisticated Mahalanobis biometric fingerprinting. Sessions that pass all checks accumulate toward a "streak" of confirmed-human sessions. When a player has accumulated sufficient verified sessions, their evidence is committed to the IoTeX blockchain, and they receive their Verified Human Proof (VHP) — a non-transferable, on-chain credential proving they are who they claim to be.

Tournament operators integrate VAPI by adding a single call to their smart contracts: `isFullyEligible(deviceId)`. Players with valid VHPs pass. Players without valid VHPs do not enter.

### 2.4 The Agentic-as-a-Service Architecture

VAPI introduces the concept of **Agentic-as-a-Service (AGaaS)** — the idea that a complex, multi-layer detection and credentialing system can be delivered as a single, composable on-chain function backed by an autonomous agent fleet.

Traditional software services are reactive: they respond to requests. VAPI's agents are proactive: they run continuously, monitoring evidence streams, detecting pattern changes, and managing credentials without being asked. This is what makes `isFullyEligible()` possible — the single on-chain call represents the synthesized output of 20 agents that have been running analysis continuously in the background.

The AGaaS model has important economic implications: VAPI's value is not delivered once (at the point of verification) but continuously (through ongoing surveillance and analysis). This enables novel token utility models where value accrues with usage, not just at credential issuance.

---

## 3. Core Cryptographic Foundation

### 3.1 The Proof of Autonomous Cognition Record

The Proof of Autonomous Cognition (PoAC) is the foundational data structure of VAPI. Every other component in the system either produces, verifies, or reasons about PoAC records.

**Structure** (228 bytes total, frozen — never modified):

| Field | Bytes | Description |
|-------|-------|-------------|
| Body | 164 | Sensor data, inference state, model manifests, hash chain link |
| ECDSA-P256 Signature | 64 | Device signature over the 164-byte body |

The 228-byte structure is cryptographically frozen — any change to the format would invalidate every existing record and every deployed contract. This is a deliberate design choice: the record format is a protocol constant, not a software version.

**Key invariants:**
- `record_hash = SHA-256(raw[0:164])` — the chain hash covers the 164-byte body only, not the signature. This allows the hash chain to be verified independently of signature validity.
- `deviceId = keccak256(pubkey)` — device identity is derived from the public key, not from any mutable field.
- Records are hash-linked: each record's body includes the hash of the previous record, creating a tamper-evident chain.
- Records are ECDSA-P256 signed: the device's private key signs each record, proving the record originated from the certified hardware.

### 3.2 Chain Integrity

VAPI's chain integrity model draws inspiration from blockchain technology but operates at the session level. Each gaming session produces a sequence of PoAC records where:

```
record[n].chain_hash = SHA-256(record[n-1].raw_body[0:164])
```

This means:
- Deleting any record breaks the chain at that point
- Inserting a fabricated record breaks the chain (the fabricated record's hash would not match)
- Modifying any record body invalidates both its own signature and the chain link in the next record

The chain integrity check is performed by VAPI's L1 structural layer — one of seven detection layers. A session that fails the chain integrity check is immediately flagged, regardless of behavioral analysis results.

### 3.3 Zero-Knowledge Session Proof

For each gaming session, VAPI generates a Zero-Knowledge (ZK) proof using Groth16 on the BN254 elliptic curve. The ZK circuit (`PitlSessionProof.circom`) encodes the following:

```
Public inputs (5 values):
  pub[0] = deviceId
  pub[1] = sessionId  
  pub[2] = featureCommitment = Poseidon(8)(scaledFeatures[0..6], inferenceCodeFromBody)
  pub[3] = inferenceCode
  pub[4] = timestamp

Private witness:
  rawFeatures[12] (L4 biometric fingerprint values)
  computedInference (must equal inferenceCodeFromBody from PoAC record body)
```

The ZK proof serves two purposes:
1. **Commitment**: It cryptographically commits to the feature values without revealing them. A tournament operator can verify the commitment without learning the player's biometric signature.
2. **Integrity binding (C3 constraint)**: The `inferenceCode` in the public output must equal the `inferenceCodeFromBody` field in the PoAC record body. This links the ZK proof to the actual evidence record, preventing a player from generating a "clean" ZK proof that does not correspond to their actual session data.

The ZK trusted setup was performed with 3 contributors over a multi-party computation (MPC) ceremony anchored to IoTeX testnet block #41723255, independently verifiable on-chain via CeremonyRegistry.sol.

---

## 4. The Physical Input Trust Layer

The Physical Input Trust Layer (PITL) is the detection engine of VAPI. It consists of seven independent analytical layers, each targeting a different class of adversarial behavior. The layers are designed to be *complementary* — no single layer is sufficient on its own, but their combination creates defense-in-depth that no known attack fully defeats.

### 4.1 Architecture Overview

```
L0: Structural — HID device presence and protocol compliance
L1: Structural — PoAC chain integrity verification
L2: Hard Cheat — IMU gravity baseline + HID/XInput pipeline discrepancy
L3: Hard Cheat — TinyML behavioral pattern classifier  
L2B: Advisory — IMU-button causal latency analysis
L2C: Advisory — Stick-IMU temporal cross-correlation
L4: Advisory — Mahalanobis biometric fingerprint (12 features)
L5: Advisory — Temporal rhythm analysis (CV, entropy, quantization)
L6: Advisory — Active haptic challenge-response (disabled by default)
```

**Hard layers** (L0–L3) produce binary signals: pass or fail. A failure at any hard layer triggers immediate flagging regardless of other results.

**Advisory layers** (L2B–L6) contribute weighted evidence to a humanity probability score. A single advisory anomaly does not block a player; sustained anomaly patterns across multiple sessions drive escalation.

**Detection inference codes** (frozen, never modified):
- `0x28 DRIVER_INJECT` — software injection of HID signals detected (hard, blocks tournament)
- `0x29 WALLHACK` — illegal game state access pattern (hard, blocks tournament)
- `0x2A AIMBOT` — precision timing pattern consistent with automated aim (hard, blocks tournament)
- `0x2B TEMPORAL_BOT` — temporal rhythm too regular for human motor variance (advisory)
- `0x30 BIOMETRIC_ANOMALY` — L4 Mahalanobis distance outside calibrated range (advisory)
- `0x31 IMU_PRESS_DECOUPLED` — button press not preceded by measurable IMU impulse (advisory)
- `0x32 STICK_IMU_DECOUPLED` — stick movement uncorrelated with body physics (advisory)
- `0x33 GSR_CORRELATION_ABSENT` — galvanic skin response absent during expected arousal events (advisory, requires GSR hardware)

### 4.2 Layer Details

**L0 — Structural: HID Device Presence**
Verifies that a recognized controller is connected via USB, producing valid HID reports at the expected polling rate. The DualShock Edge CFI-ZCP1 polls at 1,002 Hz — a rate achievable only with direct USB connection. Bluetooth or USB hub injection produces polling patterns inconsistent with this signature.

**L1 — Structural: PoAC Chain Integrity**
Verifies the hash chain across all records in a session. Any gap, insertion, or modification breaks the chain. L1 is evaluated before any behavioral analysis begins — a broken chain terminates session processing.

**L2 — Hard Cheat: IMU-HID Discrepancy**
The DualShock Edge contains a 6-axis IMU (accelerometer + gyroscope). When a player picks up and holds a physical controller, the IMU records a characteristic gravity signature in the accelerometer channels — the device is oriented in space, and gravity pulls on it continuously. Software injection — a program sending fake HID button signals — cannot reproduce this gravity signature because it has no access to the physical IMU. The injection detection margin on real hardware is measured at **14,000×**: an injected signal would need to fake IMU readings with 14,000 times more precision than measurement noise to pass undetected.

**L2B — Advisory: IMU-Button Causal Latency**
A living human muscle produces a characteristic causal sequence: neural signal → muscle activation → finger motion → button press → controller movement impulse (measured by IMU). This sequence has a characteristic latency — typically 15–80ms from first IMU impulse to button press completion. An automated system pressing a button generates the button signal without any preceding IMU impulse, or with an implausibly short causal latency. L2B measures this relationship across all button types throughout a session.

*Note: L2C (stick-IMU correlation) is inactive for games where stick movements dominate dead-zone territory, such as NCAA College Football 26. The dead zone produces structurally zero correlation regardless of human vs. bot play, making L2C non-diagnostic for this game genre.*

**L4 — Advisory: Mahalanobis Biometric Fingerprint**
This is VAPI's most technically sophisticated detection layer. L4 computes a 12-dimensional vector of behavioral features from each gaming session — micro-tremor characteristics, grip pressure dynamics, trigger onset velocities, stick autocorrelation, temporal jitter patterns — and measures the Mahalanobis distance between the current session's feature vector and the player's enrolled behavioral centroid.

*The Mahalanobis distance* is a way of measuring how unusual a data point is, corrected for the fact that some measurement dimensions vary more than others. A human player's sessions cluster around their personal behavioral centroid; anomalous sessions (bot-injected, or a different player using the device) land far from the centroid.

Key values (calibrated from 74 real sessions, 3 players):
- Anomaly threshold: **7.009** (sessions outside this boundary are flagged)
- Continuity threshold: **5.367** (sessions near but inside this boundary are monitored)

*Important limitation*: L4 currently functions as a per-player anomaly detector — it detects when *this player's device is being operated differently than usual*. It does not yet reliably distinguish between *different players* using the same device. This is the primary open challenge described in Section 11.

**L5 — Advisory: Temporal Rhythm Analysis**
Human button-pressing patterns have characteristic temporal signatures: inter-press intervals follow a distribution with measurable coefficient of variation (CV), information entropy, and absence of machine-like quantization. Bots executing scripted actions produce press intervals that are either perfectly regular (zero variance) or quantized to frame multiples. L5 detects both signatures. The analysis is game-aware: different game genres produce different baseline rhythms, and VAPI's game profiling system adjusts the analysis accordingly.

**L6 — Active Challenge-Response: Adaptive Trigger Profiling**
*This layer is disabled by default (L6_CHALLENGES_ENABLED=false) and will not be enabled until N ≥ 50 real sessions have been captured under the L6 protocol.*

The DualShock Edge contains motorized adaptive triggers that can provide variable resistance. L6 issues silent challenges: during play, the trigger resistance is varied according to a pseudo-random schedule. The player's natural response curve — the way grip force adapts to unexpected resistance — is a physiological signature that bots cannot replicate (they have no sensory feedback loop). A bot either ignores the resistance variation (producing a flat response curve) or produces an unnaturally fast adaptation.

**L6b — Reactive Neuromuscular Probe**
*This layer is disabled by default (L6B_ENABLED=false) and will not be enabled until N ≥ 50 dedicated calibration sessions have been captured.*

L6b uses sub-perceptual haptic pulses (10ms at sub-threshold amplitude) to trigger involuntary neuromuscular grip reflexes. Human reflex latency is 80–280ms; automated systems register 0–15ms. This is a *reactive involuntary probe* — the player cannot consciously prepare for it, and the response cannot be faked by software.

**L7 — Advisory: Galvanic Skin Response (Hardware Add-on)**
*This layer requires specialized GSR grip hardware (not yet in production) and is not enabled in current deployments (GSR_ENABLED=false).*

A purpose-designed grip accessory for the DualShock Edge incorporates Ag/AgCl dry electrodes to measure galvanic skin response (GSR) — electrical conductance of the skin, which correlates with sympathetic arousal. Human players show characteristic physiological responses to in-game events (goal scored, close play, competitive moment); automated bots have no nervous system and produce flat GSR readings. The 0x33 advisory code (`GSR_CORRELATION_ABSENT`) will be issued when GSR readings fail to correlate with game events — but this code is **advisory only and never a hard tournament gate** until the inter-person separation ratio required for this signal exceeds 1.0 through empirical calibration.

### 4.3 The Humanity Probability Formula

The advisory layers are combined into a single humanity probability score used to inform the epistemic consensus verdict:

```
humanity_probability = 0.28·p_L4 + 0.27·p_L5 + 0.20·p_enrollment 
                     + 0.15·p_L2B + 0.10·p_L2C
```

*Note: p_L2C resolves to 0.5 (neutral prior) in dead-zone stick games like NCAA College Football 26. The formula operates effectively as a 4-signal in practice for this game corpus.*

When L6 is active (not in current deployments):
```
humanity_probability = 0.23·p_L4 + 0.22·p_L5 + 0.15·p_enrollment 
                     + 0.15·p_L6 + 0.15·p_L2B + 0.10·p_L2C
```

### 4.4 Game Genre Certification

The PITL's biometric layers depend critically on the nature of player interaction with the controller. Different game genres activate different biometric signals, making some layers diagnostic and others uninformative for specific games.

VAPI defines four certification tiers for game genres:

| Tier | Name | Requirements | Example |
|------|------|--------------|---------|
| FULL | Full Certification | All 7 layers fully diagnostic | Fighting games (Tekken, Street Fighter) |
| STANDARD | Standard Certification | L4 diagnostic with ≥ 8 active features | Third-person action games |
| LIMITED | Limited Certification | L4 diagnostic with ≥ 3 features; intra-player only | Sports simulations (NCAA CFB 26) |
| NOT RECOMMENDED | Not Suitable | Too few diagnostic signals | Casual games with minimal controller input |

**NCAA College Football 26** (the primary development corpus for VAPI) holds **LIMITED CERTIFICATION**: 3 active L4 features (vs. 10 in fighting games), L4 operates as intra-player anomaly detection only, and L2C is structurally inactive. This means VAPI can detect *this player doing something unusual* but cannot yet reliably distinguish *this player from a different player*. The path to FULL CERTIFICATION for football requires dedicated touchpad probe session capture to close the inter-person separation gap.

---

## 5. The Autonomous Agent Fleet

### 5.1 Overview

VAPI's operational intelligence is delivered by a fleet of 20 specialized AI agents running as concurrent background services. Each agent has a specific responsibility, a defined polling interval, and a structured interface to the SQLite evidence database and the blockchain.

The agents are organized into three functional layers:

**Layer 1 — Reflexive Agents** (millisecond response): Triggered directly by session events; handle immediate structural verification, hard-cheat detection, and chain integrity.

**Layer 2 — Deliberative Agents** (minute-to-hour response): Analyze patterns across sessions; handle biometric fingerprinting, behavioral archaeology, epistemic consensus, and calibration intelligence.

**Layer 3 — Strategic Agents** (hour-to-day response): Monitor long-term trends, manage credentials, orchestrate enrollment, and maintain system health.

### 5.2 The 20-Agent Fleet

| # | Agent | Purpose | Poll Interval |
|---|-------|---------|---------------|
| 1 | InsightSynthesizer | Synthesizes multi-layer behavioral signals into session verdict | Per session |
| 2 | CalibrationIntelligenceAgent | Monitors L4 threshold drift; recommends recalibration | 30 min |
| 3 | BehavioralArchaeologist | Long-horizon pattern analysis across all sessions | 5 min |
| 4 | NetworkCorrelationDetector | Cross-device timing pattern correlation | 5 min |
| 5 | FederationBroadcastAgent | Broadcasts confirmed threat signals to federated peers | Event-driven |
| 6 | AlertRouter | Routes anomaly alerts to operator endpoints | Event-driven |
| 7 | DivergenceTriageAgent | Identifies multi-session escalation patterns | 5 min |
| 8 | ShadowEnforcementLayer | Logs would-have-suspended decisions for false-positive analysis | Per ruling |
| 9 | ProtocolIntelligenceAgent | Synthesizes tournament readiness score (0–100) | 5 min |
| 10 | LiveModeActivationPipeline | Monitors conditions for live enforcement transition | 5 min |
| 11 | ClassJDetector | ML-bot entropy variance detection (GaussianHMM adversary) | 5 min |
| 12 | SessionAdjudicatorValidation | Cross-validates AI verdicts against rule-based fallback | 5 min |
| 13 | CeremonyWatchdog | Monitors ZK ceremony integrity; triggers re-ceremony if needed | 5 min |
| 14 | VHPRenewalAgent | Manages credential expiry and automatic renewal | 6 hours |
| 15 | SeparationRatioMonitor | Monitors inter-person biometric separation ratio | 5 min |
| 16 | TournamentActivationChain | Orchestrates tournament activation conditions | Event-driven |
| 17 | PoAdAnchorAgent | Anchors Proof-of-Adjudication hashes on-chain | 60 sec |
| 18 | AgentCalibrationIntegrityMonitor (ACIM) | Runs 16 self-tests across all agents every 15 min | 15 min |
| 19 | ControllerHardwareIntelligenceAgent | Manages per-controller tier profiles and threshold tracks | Per session |
| 20 | EnrollmentAutoGuidanceAgent | Synthesizes enrollment velocity, stagnation, and defensibility | 60 min |

### 5.3 The Epistemic Consensus Protocol

A critical design decision in VAPI is that no single agent has the authority to issue a final verdict. Instead, VAPI uses an **Epistemic Consensus Protocol** where multiple agents vote on contested verdicts.

When the primary session analysis proposes a BLOCK verdict (most severe), the verdict is escalated to an epistemic consensus vote:

```
consensus_score = 0.40 × ClassJ_score 
                + 0.40 × DivergenceTriage_score 
                + 0.20 × AgentSupervisor_score
```

*(When ioSwarm consensus is active: 0.35/0.35/0.15/0.15 weights)*

A BLOCK verdict is confirmed only if `consensus_score ≥ 0.65`. Sessions scoring below this threshold are downgraded to HOLD — monitored but not immediately blocked. This threshold was deliberately set at 0.65 (not 0.60) because 0.60 was found to be reachable by a single agent class alone, creating a single-point-of-failure attack vector. The 0.65 threshold requires genuine multi-agent agreement.

Additionally, `triage_prereq_required=True` — a prerequisite triage score > 0 must exist before any blocking verdict is issued. An agent that produces a BLOCK signal without prior triage escalation is suppressed, preventing false positives from novel adversarial patterns that trick one layer while appearing clean to others.

### 5.4 Agent Calibration Integrity Monitor (ACIM)

Agent #18, the ACIM, is a meta-agent that monitors the health of all other agents. It runs 16 self-tests every 15 minutes, checking that each agent's calibration invariants are consistent with the stored ground truth. This prevents a class of attacks where an adversary corrupts a single detection agent's calibration data — the ACIM provides Byzantine fault tolerance by cross-validating each agent's state independently.

---

## 6. On-Chain Architecture

### 6.1 Blockchain Selection: IoTeX

VAPI is deployed on the **IoTeX blockchain** (chain ID 4690 for testnet, 4689 for mainnet). IoTeX was selected for several specific reasons:

1. **DePIN-native**: IoTeX is designed specifically for Decentralized Physical Infrastructure Networks — systems where IoT devices interact with on-chain logic. VAPI's controllers are IoT devices; the architecture fits naturally.

2. **ioID**: IoTeX's native device identity system allows each controller to have a registered decentralized identity (DID) — `did:io:0x<address>` — that persists across sessions and connects hardware to on-chain credentials.

3. **W3bstream**: IoTeX's W3bstream layer provides a managed pipeline for IoT data to smart contracts, enabling VAPI's PoAC records to flow from hardware to blockchain without custom infrastructure.

4. **EVM compatibility**: IoTeX uses the Ethereum Virtual Machine (EVM), meaning standard Solidity contracts, OpenZeppelin security patterns, and existing Ethereum tooling all work directly.

5. **Realms app-specific chains**: When VAPI reaches production scale (≥100,000 PoAC submissions per day), migration to an IoTeX Realm (application-specific chain) is planned to provide dedicated throughput and governance.

### 6.2 The 39-Contract Stack

VAPI has deployed 39 smart contracts to IoTeX testnet. These are organized into functional layers:

**Identity and Device Registration:**
- `VAPIioIDRegistry.sol` — registers device DIDs, links hardware to on-chain identity
- `VAPIHardwareCertRegistry.sol` — certifies hardware by type (certLevel 1: controller only; certLevel 2: controller + GSR grip)

**Evidence and Proof:**
- `PITLSessionRegistryV2.sol` — stores ZK proof commitments for each gaming session
- `CeremonyRegistry.sol` — anchors the ZK trusted setup ceremony beacon on-chain
- `AdjudicationRegistry.sol` — stores Proof-of-Adjudication (PoAd) hashes; anti-replay via UNIQUE constraint
- `GateAttestationAnchor.sol` — stores cryptographic proof-of-gate attestations for tournament entry
- `SeparationRatioRegistry.sol` — stores committed biometric separation ratio measurements
- `FederatedThreatRegistry.sol` — distributed threat signal registry for cross-operator threat sharing

**Oracle Layer:**
- `HumanityOracle.sol` — native VAPI oracle, queryable by any IoTeX tournament contract
- `RulingOracle.sol` — exposes current enforcement ruling state
- `PassportOracle.sol` — exposes tournament passport eligibility state
- `VAPIProtocolLens.sol` — synthesizes all oracle contracts into `DeviceProtocolState`; exposes `isFullyEligible()`

**Credentials and Token:**
- `VAPIVerifiedHumanProof.sol` — ERC-4671 soulbound VHP token; all transfer functions revert ("soulbound")
- `VAPIVerifiedHumanProofBridge.sol` — LayerZero V2 OApp for cross-chain VHP accessibility
- `VAPIToken.sol` — ERC-20 utility token (1B fixed supply); mint sealed after TGE
- `VAPIOperatorRegistry.sol` — operator staking (minimum 10,000 VAPI); slash/burn mechanism
- `VAPIDualPrimitiveGate.sol` — composable gate requiring both PoAC + PoAd validity

**Governance:**
- `VAPIGovernanceTimelock.sol` — 48-hour queued operator transitions; co-signer cancel
- `PHGRegistry.sol`, `PHGCredential.sol` — Player Hardware Gaming credential lifecycle

**Data Economy:**
- `DataSovereigntyRegistry.sol` — immutable on-chain data sovereignty pledge
- `VAPIDataMarketplace.sol` — three-tier data licensing (70% device pool / 30% treasury)
- `VAPIRewardDistributor.sol` — stacked DePIN reward multipliers (up to 3.0×)
- `VAPIQuickSilverCollateral.sol` — stIOTX liquid staking as operator collateral

*(Full address list: `contracts/deployed-addresses.json`)*

### 6.3 The Composable Proof Triple

VAPI's most architecturally novel feature is its **composable proof triple**: three independent cryptographic proofs that can each be verified on-chain independently, and combined to form a single high-assurance eligibility gate.

**Proof of Autonomous Cognition (PoAC)**: The 228-byte hash-chained evidence record, anchored via `PITLSessionRegistryV2.sol`. Proves the controller session happened on certified hardware with valid behavioral signals.

**Proof of Adjudication (PoAd)**: A SHA-256 hash of the autonomous agent fleet's adjudication verdict: `SHA-256(sorted_verdicts + quorum + ts_ns)`. Anchored via `AdjudicationRegistry.sol`. Proves that the agent fleet reached consensus that the session was legitimate.

**Proof of Fleet Consensus (PoFC)** *(designed, implementation pending)*: A SHA-256 hash representing the entire fleet's current agreement: `SHA-256(sorted(agent_verdicts) + separation_ratio + ts_ns)`. Will be anchored via a `FleetConsensusSnapshotAgent` extension to `SeparationRatioRegistry.sol`. Proves Byzantine fault-tolerant fleet consensus.

Tournament contracts can require any or all three proofs:
```solidity
require(VAPIProtocolLens.isFullyEligible(deviceId));         // PoAC
require(AdjudicationRegistry.isRecorded(poadHash));          // PoAd
require(FleetConsensusRegistry.isFleetConsensus(pfcHash));   // PoFC (planned)
```

This triple-proof composability is unique to VAPI. No other gaming anti-cheat protocol or DePIN system has achieved this depth of cryptographic composability for human presence verification.

### 6.4 The VHPDualPrimitiveGate

`VAPIDualPrimitiveGate.sol` (deployed at `0xd7b1465Aad8F815C67b24681c9c022CED24FB876`) is a pure-view smart contract that enforces simultaneous PoAC + PoAd validity:

```solidity
function isDualEligible(bytes32 deviceIdHash, bytes32 poadHash)
    external view returns (bool eligible, bool poac_valid, bool poad_valid)
```

This is the first dual-proof composability gate in any on-chain gaming protocol. It enables tournament operators to require both physiological evidence (PoAC) and adjudication consensus (PoAd) as simultaneous conditions for entry.

---

## 7. The Verified Human Proof Credential

### 7.1 What the VHP Is

The Verified Human Proof (VHP) is a **soulbound, non-transferable on-chain token** that represents a player's cryptographically verified eligibility to compete. It is implemented as an ERC-4671 token — a standard specifically designed for non-transferable credentials — deployed at a known address on the IoTeX blockchain.

"Soulbound" means the token cannot be transferred to another address. All transfer functions on the contract revert. Unlike a standard NFT that represents an asset that can be bought and sold, a VHP represents a cryptographic fact about a specific player-device combination. It cannot be sold because it is not property — it is proof.

### 7.2 VHP Structure

Each VHP contains:

```
deviceIdHash    — keccak256(deviceId), links to certified hardware
certLevel       — 1 (controller only) or 2 (controller + GSR grip)
consecutiveClean — count of consecutive anomaly-free sessions
confidenceScore — weighted behavioral confidence (0.0–1.0)
issuedAt        — block timestamp of issuance
expiresAt       — issuedAt + 90 days (renewable)
mpcCeremonyHash — links VHP to the ZK trusted setup ceremony
```

A VHP expires after 90 days and must be renewed by submitting fresh evidence. This is intentional: a VHP is not a permanent certification — it is a living proof of ongoing trustworthy behavior. A player who stops playing, or whose behavioral patterns change significantly, will not be able to renew.

### 7.3 The Mint Gate

Minting a VHP requires passing five sequential gates:

1. **Audit Gate**: The activation audit summary must confirm N ≥ 100 validated sessions with zero false positives
2. **Certificate Gate**: A valid Enforcement Readiness Certificate must be present and unexpired
3. **Live Mode Gate**: The system must be operating in live (non-simulation) mode
4. **Dual-Primitive Gate** (when enabled): Both PoAC and PoAd must be valid and current
5. **Epoch Window Gate** (when enabled): The most recent PoAd must be within the configured time window (default: 24 hours)

These gates are enforced in the bridge service's `POST /agent/mint-vhp` endpoint and validated on-chain via `VAPIProtocolLens.isFullyEligible()`.

### 7.4 LayerZero Cross-Chain Bridge

`VAPIVerifiedHumanProofBridge.sol` implements a LayerZero V2 OApp, enabling VHPs minted on IoTeX to be verified on other EVM-compatible chains (Ethereum, Polygon, Arbitrum, etc.). This is critical for tournament operators who may be deploying their smart contracts on chains other than IoTeX.

The bridge uses standard LayerZero V2 patterns:
- `setPeer()` establishes trusted remote endpoints
- `abi.encode` for message encoding
- Per-message nonces for anti-replay protection

### 7.5 ioSwarm Quorum Authorization

*(Infrastructure complete; live node registration pending)*

VHP minting in the production system will require authorization from a distributed network of independent ioSwarm operator nodes. The authorization gate requires:

- **MINT_QUORUM = 0.80** (80% of registered nodes must authorize) — deliberately stricter than other quorum thresholds because VHP minting is an irreversible soulbound action
- **Fail-CLOSED**: If the ioSwarm network is unavailable, minting is blocked (not permitted). A system that defaults to allowing minting when its authorization network is down would be insecure.

The ioSwarm integration uses a dual-quorum adjudication model:
- ClassJ (ML-bot detection) requires BLOCK_QUORUM = 0.67 (67%) to issue a BLOCK verdict
- Triage assessment requires the same 0.67 threshold
- Both quorums must agree (dual-veto) before a BLOCK verdict is issued

---

## 8. DePIN Integration and Economic Model

### 8.1 VAPI as DePIN Infrastructure

DePIN — Decentralized Physical Infrastructure Networks — is an emerging category of blockchain-based systems where real-world physical devices contribute to a shared network and earn token rewards for doing so. VAPI is a DePIN protocol: certified gaming controllers are IoT devices that contribute cryptographic evidence to the network and earn rewards for doing so honestly.

The VAPI DePIN model has three value layers:

**Hardware Layer**: The certified DualShock Edge controller is a DePIN node. It contributes PoAC records to the network. When the GSR grip add-on is deployed, it contributes physiological data as a second DePIN data stream.

**Compute Layer**: The bridge service running on the player's machine is a DePIN edge compute node. It handles local processing, feature extraction, and agent communication. This is the AGaaS execution environment.

**Settlement Layer**: IoTeX L1 is the settlement layer where evidence records, credentials, and token rewards are finalized.

### 8.2 VAPI Token Utility

The VAPI token (ticker: VAPI) is a utility token with the following mechanics:

**Staking** (demand driver): Tournament operators must stake a minimum of 10,000 VAPI in `VAPIOperatorRegistry.sol` to operate an adjudication node. Stakes are slashed for misbehavior:
- 50% burned (deflationary pressure)
- 50% to the claimant (incentive for honest reporting)

**Hardware Certification** (demand driver): Manufacturers pay VAPI tokens to register new hardware profiles in `VAPIHardwareCertRegistry.sol`.

**Data Marketplace** (circulation): When players consent to data licensing, 70% of marketplace revenue flows to the device pool (VAPI rewards for contributing devices) and 30% to the treasury.

**Reward Multipliers** (circulation): Players earn VAPI tokens for contributing verified session data. Multipliers stack:

| Condition | Multiplier |
|-----------|-----------|
| Base rate | 1.0× |
| IoTeX Passport holder | 1.5× |
| Enrolled (10+ verified sessions) | 2.0× |
| CERTIFY streak active | 2.5× |
| MPC ceremony contributor | 1.25× |
| Gate attestation on-chain | 3.0× |
| GSR grip enrolled *(future)* | 1.75× |

**Token Launch Gate** (non-negotiable sequencing constraint): The VAPI token TGE will not occur until:
1. Inter-person biometric separation ratio > 1.0 is confirmed empirically across a representative player population
2. N ≥ 100 live, non-simulation adjudications with zero confirmed false positives
3. VHP end-to-end flow demonstrated on testnet

This constraint is architecturally enforced: `VAPIToken.sol`'s `completeTGE()` function cannot be called while the separation ratio gate is blocked.

### 8.3 The Data Sovereignty Model

VAPI implements a three-tier data licensing model via `DataSovereigntyRegistry.sol`:

- **MANUFACTURER tier**: Hardware makers can license aggregated behavioral data to improve controller firmware (e.g., trigger calibration curves)
- **DEVELOPER tier**: Game studios can license session-level feature data to improve AI game testing and bot detection in their own titles
- **GAMER tier**: Individual players can license their personal session data and earn VAPI rewards

Data sovereignty pledges are immutable on-chain commitments. Players who pledge their data cannot retroactively revoke it — but future sessions require fresh consent. Data marketplace participation is entirely opt-in.

### 8.4 QuickSilver Staking Integration

VAPI integrates with IoTeX's QuickSilver liquid staking protocol, allowing operators to stake `stIOTX` (liquid-staked IOTX) as an alternative to VAPI tokens for operator registry collateral. This reduces the opportunity cost of operating a node — the staked IOTX continues earning staking rewards while simultaneously serving as VAPI operator collateral, creating a double-yield mechanism.

---

## 9. Security Analysis and Threat Model

### 9.1 Adversary Classification

VAPI classifies adversaries by their capabilities and attack vectors:

| Class | Attack Type | Current Detection |
|-------|-------------|------------------|
| A–F | Casual input manipulation | L0–L3 structural + behavioral layers |
| G | Randomized bot (random action timing with natural variance simulation) | L4 (batch: 0%, live: 100% via L4+L2B) |
| H | Threshold-aware bot (knows L4 thresholds, stays within bounds) | L4 (100% — threshold awareness alone insufficient) |
| I | Spectral mimicry (matches frequency characteristics of human play) | L2B reactive (0% batch, live: via IMU-button causality) |
| J | ML-bot (GaussianHMM temporal state machine, learns from human sessions) | ClassJDetector (HIGH confidence via temporal state entropy variance) |
| K | GSR spoofer (synthetic EDA generator injecting plausible skin response signals) | **NOT YET DEFINED** — open gap; mitigation requires hardware challenge-response |

### 9.2 Class J — Machine Learning Bot Detection

Class J adversaries are the most sophisticated currently modeled: they use machine learning models (specifically GaussianHMM — Hidden Markov Models with Gaussian emission distributions) trained on human session data to generate temporally plausible button-press sequences. Unlike Classes A–I, Class J bots do not simply replicate human timing — they *learn* human timing patterns.

The `ClassJDetector` (agent #11) detects Class J by analyzing **temporal state transition entropy variance** — the rate at which the entropy of state transitions changes across session windows. Human players naturally shift strategies, react to game state changes, and show non-stationary behavioral patterns. A GaussianHMM trained on human data does not exhibit the same non-stationarity — it reverts to its training distribution. The entropy variance signal exploits this difference.

Detection principle:
- Human: `temporal_state_transition_entropy_variance > 0.15` (changing patterns)
- Class J ML-bot: `variance ≤ 0.05` (stationary distribution)
- Threshold: HIGH risk at ≤ 0.05, MEDIUM at ≤ 0.15, LOW above

### 9.3 Attack Vectors on Protocol Economics

**Stake griefing**: An adversary acquires minimal VAPI tokens, registers as an operator, then intentionally miscategorizes sessions to have their stake slashed — sending 50% to the claimant (themselves, using a different address). Mitigation: minimum stake threshold (10,000 VAPI) makes this economically unfavorable; the attacker loses 50% of their stake in the process.

**VHP replay**: Pre-computing adjudication hashes to mint VHPs with expired evidence. Mitigation: epoch window gate (configurable, default 24 hours) — `poad_age_seconds > epoch_window_seconds` rejects stale PoAd anchors.

**Enrollment count-gate bypass** *(open, Phase 157 target)*: The enrollment activation event fires when session count threshold is met, without verifying that the biometric separation ratio is defensible. An adversary could capture exactly the minimum session count without achieving the separation quality needed for tournament-grade biometrics. Mitigation (in progress): dual-condition enforcement requiring both count AND defensibility.

### 9.4 Biometric Spoofing

The most sophisticated class of attack — spoofing the physical biometric signals — is addressed by defense-in-depth:

**IMU-level spoofing**: Would require a hardware device that exactly replicates the controller's IMU signal while simultaneously injecting bot inputs. The 14,000× injection detection margin means the injected signal would need to be imperceptibly accurate. The causal timing relationship between IMU and button press (L2B) is additionally difficult to fake because it requires predicting which muscle will fire and when — without any sensory feedback loop.

**L4 biometric spoofing**: Knowing the L4 thresholds (7.009 anomaly / 5.367 continuity) and feature space allows a sophisticated adversary to attempt to stay within the Mahalanobis distance boundary. However, the 12-feature space is high-dimensional, and the per-player calibration means an adversary would need to know not just the general thresholds but the specific enrolled player's behavioral centroid — which is never published.

**Hardware anti-tamper** *(in design)*: The planned GSR grip uses ATECC608A secure element hardware for HMAC signing of GSR packets, preventing Class K injection of synthetic EDA signals into the BLE stream.

### 9.5 Protocol Governance Security

`VAPIGovernanceTimelock.sol` enforces a 48-hour delay on all operator transitions affecting the evidence registry and oracle layer. Changes cannot take immediate effect — there is always a 48-hour window in which:
1. Community members can observe proposed changes
2. A co-signer can cancel transactions that appear malicious
3. Automated monitoring can flag anomalies

`PHGCredential.sol` is explicitly excluded from the 48-hour timelock — player suspensions must take effect immediately when a hard cheat is confirmed. Suspending a cheater should not be delayed by governance procedure.

---

## 10. Evaluation and Current State

### 10.1 Cryptographic Performance

| Operation | Latency | Notes |
|-----------|---------|-------|
| PoAC record generation | < 1 ms | Per cognitive cycle at 1 kHz |
| SHA-256 chain hash | 0.3 µs | 164-byte body |
| ECDSA-P256 sign | ~0.5 ms | Per-session boundary |
| Groth16 ZK proof (Poseidon(8)) | ~8 ms | Per session, local prover |
| ZK on-chain verify | ~21,000 gas | `PITLSessionRegistryV2.verifyProof()` |
| L4 Mahalanobis distance | < 1 ms | 12-feature, full covariance when N/p ≥ 3 |

### 10.2 Anti-Cheat Detection Results

Real hardware adversarial validation against three white-box attack classes:

| Attack Class | Batch Detection | Live Detection | Notes |
|---|---|---|---|
| G: Randomized bot | 0% | 100% | Live L4 detects sustained behavioral drift |
| H: Threshold-aware bot | 100% | 100% | L4 threshold awareness alone insufficient |
| I: Spectral mimicry | 0% | ~100% | Live L2B (IMU causal latency) is primary detector |
| J: GaussianHMM ML-bot | HIGH confidence | HIGH | Temporal entropy variance discriminates cleanly |

*Note*: Batch detection rates reflect analysis of pre-recorded sessions where all features are available post-hoc. Live detection rates reflect real-time analysis during active sessions. The gap for Classes G and I reflects the difference between retrospective statistical analysis and real-time single-session classification.

### 10.3 Biometric Separation Analysis

*This is the primary quantitative metric and the primary open challenge.*

**Inter-person separation ratio**: The ratio of mean inter-player Mahalanobis distance to mean intra-player Mahalanobis distance. A ratio > 1.0 is required for tournament-grade biometric identification (the ability to distinguish between different players). A ratio < 1.0 means the system cannot reliably identify that a different person is using the same device.

**Current measurements** (touchpad_corners probe type, diagonal covariance, proper LOO classification):
- Separation ratio: **1.261** (N=11 sessions, 3 players, Phase 143 result)
- Classification accuracy: **63.6%** (7/11 sessions correctly attributed, proper leave-one-out)
- Per-pair distances: P1 vs P2: 2.868 | P1 vs P3: 3.276 | P2 vs P3: 2.243
- Status: **Conditionally above the 1.0 gate** — but N=11 is thin (minimum 10 sessions per player required for defensibility)

**Free-form gameplay corpus** (N=127 sessions, full mixed corpus):
- Separation ratio: **0.417** — below the 1.0 gate
- Status: **TOURNAMENT BLOCKER** — free-form gameplay sessions alone are insufficient for biometric identification
- Root cause confirmed: free-form sessions plateau in a separation regime that cannot exceed 1.0; touchpad-specific structured probes are the only viable path

*What this means in plain language*: VAPI can currently detect when this-device-is-behaving-unusually (L4 anomaly detection) with high confidence. VAPI cannot yet reliably confirm that this-device-is-being-operated-by-this-specific-player-not-someone-else at scale. The structured touchpad probe sessions (N=11) show this capability is achievable with the right data collection approach, but 11 sessions is not yet enough for a defensible production claim. This is the primary engineering challenge before tournament deployment.

**Covariance analysis note**: The 1.261 ratio is computed with diagonal covariance (the Mahalanobis distance formula uses only variance, not cross-correlations between features). This is statistically appropriate at N=11 with 8 active features (N/p = 1.375, below the 3.0 stability threshold). Using full covariance at this sample size would introduce noise that artificially suppresses the P1/P3 distance by up to 97%. The diagonal covariance result is honest; the full covariance result at small N is misleading.

### 10.4 Test Coverage

| Test Suite | Count | Coverage |
|---|---|---|
| Bridge service (Python) | 1,868 | All API endpoints, agents, store methods |
| Smart contracts (Hardhat/Solidity) | 468 | All 39 deployed contracts |
| SDK (Python) | 265 | All client-facing SDK classes |
| Hardware (DualShock Edge) | 37 | Requires physical controller |
| End-to-end | 14 | Requires live Hardhat node |
| **Total** | **~2,572** | |

The CI pipeline excludes hardware and E2E tests (require physical devices and live blockchain nodes), running 2,521 tests automatically on each commit across Python 3.11/3.12/3.13 and Node.js 18/20.

### 10.5 Gas Cost Analysis

| Operation | Estimated Gas | Notes |
|---|---|---|
| VHP mint | ~150,000 | 90-day soulbound credential |
| Ruling record | ~80,000 | Per enforcement decision |
| ZK proof verify | ~21,000 | Groth16 on BN254 |
| Gate attestation | ~100,000 | On-chain activation proof |
| Adjudication record | ~80,000 | Per PoAd hash |

At current IoTeX gas prices (~0.001 IOTX per gas), a VHP mint costs approximately 0.15 IOTX. At mainnet prices, this remains economically viable for tournament entry fees of any meaningful size.

---

## 11. Open Challenges and Honest Limitations

This section documents, without qualification or minimization, the gaps between VAPI's current state and its production deployment target.

### 11.1 The Inter-Person Separation Gap

*Severity: Critical blocker for tournament deployment*

The separation ratio of 1.261 from touchpad_corners sessions (N=11) is above the 1.0 gate but below defensible thresholds (minimum 10 sessions per player). The free-form gameplay corpus at 0.417 is firmly below the gate and confirmed to be in a plateau regime that cannot be resolved by more free-form data.

**What is needed**: Each of the three enrolled players needs approximately 7 more touchpad_corners capture sessions (current: P1=3, P2=4, P3=4; target: P1=P2=P3=10+). This is a data collection task, not a technical limitation — the analysis infrastructure is complete and the signal is present.

**What this blocks**: Token launch, live tournament enforcement mode, and the defensibility of any on-chain separation ratio commitment.

**Honest assessment of the path**: With dedicated touchpad capture sessions, this gap can be closed. The protocol, infrastructure, and enrollment guidance agents are all in place. The only remaining work is capturing and processing the sessions.

### 11.2 L4 Operates as Intra-Player Anomaly Detection Only

*Severity: Known limitation, well-documented*

L4's 12-feature Mahalanobis fingerprint detects *when a device's behavioral signature has changed* relative to its enrolled baseline. It does not yet reliably detect *which person is using the device*. This is the mathematical statement of the separation ratio gap.

Practically: if Player A's DualShock Edge is used by Player B, L4 may flag the session as anomalous if their styles differ significantly — but this is behavioral anomaly detection, not biometric identification. A Player B who has studied Player A's style could potentially evade detection.

The touchpad_corners structured probe sessions show that biometric identification IS achievable with VAPI's hardware and feature set, at least for the current 3-player corpus. The path from detection to identification is clear; it requires more enrollment data.

### 11.3 GSR Hardware Not Yet Deployed

*Severity: Significant capability gap, hardware-blocked*

The L7 GSR (Galvanic Skin Response) layer is the most physiologically direct of all VAPI's detection signals. A living nervous system produces measurable electrodermal response to in-game events; no automated system does. However, the GSR grip accessory is a prototype hardware design, not yet in production. All current deployments operate without GSR capability.

The L7 feature extraction code (`gsr_feature_extractor.py`) and the registry contract (`VAPIGSRRegistry.sol`) are complete and deployed. The hardware design is complete. Manufacturing has not begun.

**GSR flag**: The code uses `MockGSRGrip(seed=42)` for testing — a scipy-based synthetic EDA generator. This is deliberate and transparent code-before-hardware development, following established VAPI convention. No production claims are made based on simulated GSR signals.

### 11.4 Live Enforcement Mode Not Active

*Severity: Deployment milestone, not a fundamental limitation*

The system currently operates in `dry_run=True` mode. All detection, analysis, and scoring happens in real time; verdicts are recorded to the database and the blockchain. However, no player credentials have been suspended based on live adjudication results, and no tournament contract has been configured with `isFullyEligible()` as a hard gate.

Transitioning to live mode requires:
1. N ≥ 100 validated sessions with zero false positives (validation corpus in progress)
2. Enforcement Readiness Certificate issued and valid
3. Operator deliberate activation via `POST /agent/config?dry_run=false`

This is a deliberate safety gate — VAPI will not accidentally begin blocking real players. Live mode is activated by explicit operator decision only.

### 11.5 L4 Calibration Dimension Staleness

*Severity: Low — known and monitored*

L4's calibration was performed on 12 features using 74 sessions. The live feature space currently has 13 features (touchpad_spatial_entropy was added). The calibration dimension mismatch (calib_dim=12 vs live_dim=13) is flagged as "stale" by the `CalibrationStalenessMonitor` — but the practical impact is low because touchpad_spatial_entropy initializes to 0.0 for non-touchpad sessions, effectively not affecting the Mahalanobis distance calculation for standard gameplay. Recalibration should occur after the touchpad enrollment gap is closed.

### 11.6 ioSwarm Nodes Not Yet Registered

*Severity: Deployment milestone, infrastructure ready*

The ioSwarm integration (decentralized quorum authorization for VHP minting) is architecturally complete in the codebase. The node emulators, coordinator logic, and smart contract bindings are all present. However, no live ioSwarm operator nodes have been registered with the protocol. The system operates in emulator mode (`ioswarm_enabled=false`).

Live ioSwarm requires operator nodes to be recruited, staked, and registered before the quorum mechanism is meaningful.

---

## 12. Vision and Roadmap

### 12.1 The VAPI Vision

VAPI's long-term vision is to become the universal cryptographic proof layer for human presence in competitive gaming — across games, platforms, and controller types. Just as SSL/TLS became the universal trust layer for web communication (enabling commerce, banking, and private communication), VAPI aims to become the trust layer for competitive gaming (enabling prize pools, verified rankings, and anti-cheat enforcement with mathematical certainty).

The single on-chain call — `isFullyEligible()` — is the expression of this vision. A tournament operator in any jurisdiction, on any supported blockchain, with no knowledge of VAPI's internal architecture, can call `isFullyEligible(deviceId)` and receive a cryptographic guarantee. The 20-agent fleet, the biometric calibration, the epistemic consensus, the ZK proofs — all invisible behind a single Boolean.

### 12.2 Multi-Controller Ecosystem

The current prototype is calibrated exclusively for the Sony DualShock Edge CFI-ZCP1. The `ControllerHardwareIntelligenceAgent` (agent #19) introduces the infrastructure for multi-controller support, with two certification tiers:

**Attested Tier** (DualShock Edge): Full PITL stack (L0–L6), all seven detection layers active, eligibility for all VAPI tournaments.

**Standard Tier** (Xbox Elite, Nintendo Pro, etc.): L0–L5 stack; L6 haptic challenge-response not available on non-Edge controllers. Eligible for VAPI standard tournaments (not requiring L6).

Each controller type requires its own calibration corpus before certification. The enrollment guidance infrastructure for multi-controller support is in place.

### 12.3 Platform and Game Expansion

Current prototype scope:
- Platform: Windows 11 (PC)
- Controller: DualShock Edge via USB-C
- Game: NCAA College Football 26 (LIMITED CERTIFICATION)

Planned expansion:
- **PlayStation 5 native**: Direct PS5 integration bypassing the PC bridge requirement
- **Additional game genres**: Fighting games (which provide the highest biometric signal density), FPS titles, strategy games
- **Mobile gaming**: Touch-based biometric fingerprinting via accelerometer and touchscreen pressure patterns

Game genre certification requires dedicated calibration data per genre — the infrastructure is ready; the data collection is the limiting factor.

### 12.4 The Token Launch Gate

The VAPI token economy will not launch until the following conditions are met simultaneously:

1. **Biometric defensibility**: `defensible=True` from `separation_defensibility_log` — all enrolled players at N ≥ 10 touchpad_corners sessions, ratio > 1.0, all inter-player pairs > 1.0
2. **Adjudication validation**: N ≥ 100 live, non-simulation adjudications with zero confirmed false positives
3. **VHP end-to-end**: Complete VHP mint, transfer (cross-chain via LayerZero), and tournament verification demonstrated on testnet
4. **ioSwarm quorum**: At least 3 independent ioSwarm operator nodes registered and producing consistent verdicts

These conditions are non-negotiable. Launching a token before biometric defensibility is confirmed would mean selling an economic asset backed by an unproven security claim — precisely the kind of speculative positioning VAPI is designed to avoid.

### 12.5 Realms Migration

When VAPI reaches scale (≥100,000 PoAC submissions per day), migration to an IoTeX Realm (application-specific blockchain) is planned. All smart contracts deployed are built with OpenZeppelin TransparentUpgradeableProxy patterns to support migration without service interruption. The Realm provides dedicated throughput, governance, and fee structures for VAPI's specific workload.

### 12.6 Competitive Landscape

VAPI occupies a novel category. The closest adjacent systems are:

| System | Approach | VAPI Difference |
|--------|----------|-----------------|
| Easy Anti-Cheat / BattlEye | Software signature detection | VAPI detects hardware injection; EAC cannot |
| Overwolf / ESL Faceit | Third-party client monitoring | Client-side; cannot detect hardware injection |
| Anti-cheat blockchain projects | On-chain reporting, no physics | VAPI physics-backs the evidence |
| Biometric gaming hardware | Local analysis, no blockchain | VAPI is verifiable by any third party |

No currently deployed system combines: physics-backed evidence + cryptographic commitment + public blockchain anchoring + autonomous agent fleet + cross-chain composable credential.

---

## 13. Technical Reference

### 13.1 Core Protocol Constants (Frozen)

These values are protocol constants. They cannot be changed without invalidating the entire evidence chain and all deployed contracts.

| Constant | Value | Purpose |
|----------|-------|---------|
| PoAC record size | 228 bytes | Wire format |
| Body size | 164 bytes | Chain hash input |
| Chain hash function | SHA-256(raw[0:164]) | Tamper detection |
| Device identity | keccak256(pubkey) | On-chain device ID |
| ZK circuit | Groth16, BN254 | Session proof |
| ZK hash function | Poseidon(8) | Feature commitment |
| ZK public inputs | nPublic = 5 | Proof verification |
| BLOCK_QUORUM | 0.67 | ioSwarm blocking threshold |
| MINT_QUORUM | 0.80 | VHP authorization threshold |
| Epistemic threshold | 0.65 | Minimum consensus for BLOCK |

### 13.2 Inference Code Registry

| Code | Name | Type | Tournament Effect |
|------|------|------|-------------------|
| 0x28 | DRIVER_INJECT | Hard | Blocks tournament entry |
| 0x29 | WALLHACK | Hard | Blocks tournament entry |
| 0x2A | AIMBOT | Hard | Blocks tournament entry |
| 0x2B | TEMPORAL_BOT | Advisory | Accumulates toward escalation |
| 0x30 | BIOMETRIC_ANOMALY | Advisory | Accumulates toward escalation |
| 0x31 | IMU_PRESS_DECOUPLED | Advisory | Accumulates toward escalation |
| 0x32 | STICK_IMU_DECOUPLED | Advisory | Accumulates toward escalation |
| 0x33 | GSR_CORRELATION_ABSENT | Advisory (L7) | Never a hard gate |

### 13.3 L4 Calibration Values

| Parameter | Value | Corpus |
|-----------|-------|--------|
| Anomaly threshold | 7.009 | N=74, 3 players, Phase 57 |
| Continuity threshold | 5.367 | N=74, 3 players, Phase 57 |
| Feature dimensions (calibration) | 12 | Original feature set |
| Feature dimensions (live) | 13 | +touchpad_spatial_entropy |
| Human false positive rate | ~2.9% | Expected at 3σ threshold |

Active L4 features: trigger_onset_velocity_L2, trigger_onset_velocity_R2, micro_tremor_accel_variance, grip_asymmetry, stick_autocorr_lag1, stick_autocorr_lag5, tremor_peak_hz, tremor_band_power, accel_magnitude_spectral_entropy, press_timing_jitter_variance. (trigger_resistance_change_rate and touch_position_variance are structurally zero in current corpus and excluded.)

### 13.4 Separation Ratio Status

| Corpus | Ratio | N | Status |
|--------|-------|---|--------|
| Touchpad corners, diagonal LOO | 1.261 | 11 | Conditionally above gate (N thin) |
| Free-form gameplay (pooled) | 0.417 | 127 | TOURNAMENT BLOCKER |
| Historical diagonal reference | 0.362 | 74 | Pre-touchpad baseline |

### 13.5 Key Deployed Contract Addresses (IoTeX Testnet, Chain ID 4690)

| Contract | Address |
|----------|---------|
| AdjudicationRegistry | 0x44CF981f46a52ADE56476Ce894255954a7776fb4 |
| VAPIDualPrimitiveGate | 0xd7b1465Aad8F815C67b24681c9c022CED24FB876 |
| RulingRegistry | 0xa3A2356C90E642a7c510d0C726EC515EA720c621 |
| CeremonyRegistry | 0x739B5fae312834bA2a7e44525bA5f54853C5672f |
| VAPIProtocolLens | 0x1972bf756aFE0FFCfaF9842e2FbBb2B084352EAf |
| GateAttestationAnchor | 0xA39d00D3FF8C579840Fa02C01Adf06162630a449 |
| DataSovereigntyRegistry | 0xd928d95321Fff9b9003331082A8F6b75114793C9 |
| HumanityOracle | 0x84069312B5363Ef8ce6d1e2e312C4A1a8596a45d |
| VAPIioIDRegistry | 0xF7885B... |

*(Full address list: `contracts/deployed-addresses.json`)*

### 13.6 SDK Quick Reference

```python
# Check tournament eligibility
from vapi_sdk import VAPIProtocolMaturity
client = VAPIProtocolMaturity(base_url="http://localhost:8000", api_key="...")
maturity = client.get_maturity()
print(maturity.pmi_label, maturity.activation_committed)

# Monitor ruling stream
from vapi_sdk import VAPIRulingStream
async for event in VAPIRulingStream(base_url=..., api_key=...).stream():
    print(event.device_id, event.verdict, event.confidence)

# Check player eligibility  
from vapi_sdk import VAPITournamentClient
client = VAPITournamentClient(base_url=..., api_key=...)
eligibility = client.check_player(device_id="...")
print(eligibility.is_eligible, eligibility.has_valid_vhp)
```

---

## Appendix A: Contribution and Collaboration

VAPI is an independent research project. Contributions are welcome in the following areas:

**GSR Hardware**: The GSR grip accessory requires PCB design, ESP32-S3 firmware, and enclosure manufacturing. Electronics engineers and hardware prototypers are invited to collaborate on the reference design.

**Player Enrollment**: The biometric separation challenge is a data problem. Researchers and players willing to contribute structured touchpad probe sessions would directly advance the system toward tournament readiness.

**Security Research**: Adversarial testing of the PITL stack, particularly for Class K (GSR spoofing) and novel ML-bot architectures, is actively sought.

**Game Genre Certification**: Game studios and esports operators interested in certifying titles for VAPI deployment can contribute calibration data and game-specific profile definitions.

---

## Appendix B: Glossary

**Adversary Classes (A–K)**: Classification of anti-cheat adversaries by attack sophistication. A–F are basic; G–I are scripted; J is ML-based; K (GSR spoofing) is hardware-based.

**AGaaS (Agentic-as-a-Service)**: VAPI's architecture model — complex detection delivered as a single composable on-chain call backed by an autonomous agent fleet.

**Biometric Defensibility**: The property of a separation ratio measurement where all enrolled players have ≥ minimum sessions (10), ratio > 1.0, and all inter-player pairs > 1.0. Required for tournament-grade biometric identification.

**DePIN (Decentralized Physical Infrastructure Network)**: A blockchain-based network where physical devices contribute to a shared service and earn token rewards. VAPI's controllers are DePIN nodes.

**Enrollment**: The process of capturing sufficient structured probe sessions (currently touchpad_corners) to establish a player's biometric baseline. Required before VHP eligibility.

**Epistemic Consensus**: VAPI's multi-agent voting protocol for contested verdicts. Requires ≥ 0.65 weighted agreement across ClassJDetector + DivergenceTriage + AgentSupervisor.

**ioSwarm**: IoTeX's decentralized autonomous operator node network. VAPI uses ioSwarm for distributed VHP mint authorization.

**Mahalanobis Distance**: A statistical measure of how unusual a data point is relative to a distribution, accounting for correlations between dimensions. Used in L4 biometric fingerprinting.

**PoAC (Proof of Autonomous Cognition)**: VAPI's 228-byte cryptographic evidence record. Contains sensor commitments, model manifests, and inference results, signed by the device.

**PoAd (Proof of Adjudication)**: SHA-256 hash of the agent fleet's adjudication verdict, anchored on-chain.

**PoFC (Proof of Fleet Consensus)**: SHA-256 hash of the full agent fleet's current agreement state. Designed; implementation pending.

**PoHBG (Proof of Hardware-Bound GSR)**: Planned fourth composable proof — SHA-256 of HMAC-signed GSR sensor batches, hardware-bound via ATECC608A secure element.

**Separation Ratio**: Mean inter-player Mahalanobis distance ÷ mean intra-player Mahalanobis distance. Must exceed 1.0 for reliable player identification. Current best: 1.261 (touchpad_corners, N=11).

**Soulbound**: A non-transferable on-chain token. All transfer functions revert. The VHP is soulbound — it represents proof about a specific player, not a transferable asset.

**VHP (Verified Human Proof)**: VAPI's soulbound ERC-4671 credential. Expires after 90 days; renewable through continued verified play. The cryptographic output of the entire VAPI system.

**W3bstream**: IoTeX's layer for IoT data pipelines to smart contracts. VAPI uses W3bstream applets to process PoAC records and GSR packets from device to blockchain.

---

*Document Version: 4.0 — Canonical Reference*  
*Last Updated: April 2026*  
*Supersedes: vapi-whitepaper-v3.md*  
*Next review: Upon separation ratio defensibility gate (defensible=True)*

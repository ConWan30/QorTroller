# VAPI: Verifiable Controller Input Provenance with Physics-Backed Liveness for Competitive Gaming

**Authors:** Contravious Battle

Independent Researcher

**Contact:** kamazi.shotta@icloud.com

**DOI:** https://doi.org/10.5281/zenodo.18966169

---

## Abstract

**Part 1 — Provenance.**
VAPI provides a cryptographically verifiable evidence rail for controller input. Each gaming session produces a signed, hash-chained stream of 228-byte evidence records whose origin (ECDSA-P256 signature), ordering (monotonic counter + hash linkage), and integrity (hash-chain verification) can be confirmed by any third party on a public blockchain without access to the original device.

**Part 2 — Physics.**
Software-only injection is made empirically infeasible by a nine-level Physical Input Trust Layer (PITL) that binds committed evidence to physics-coupled controller signals — IMU gravity baseline, IMU-button causal latency, stick-IMU temporal cross-correlation, biometric kinematic fingerprinting (12 features, Mahalanobis distance), temporal rhythm analysis, and active haptic challenge-response using the DualShock Edge's motorized adaptive triggers. Live hardware validation on a DualShock Edge CFI-ZCP1 confirms a 14,000× injection detection margin.

**Part 3 — Status.**
The prototype spans ~225 files with ~1,671 automated tests (1207 bridge, 396 contract, **63 SDK**, 14 E2E, 28 hardware). Twenty-three contracts are ALL LIVE on IoTeX testnet — RulingRegistry (`0xa3A2356C90E642a7c510d0C726EC515EA720c621`) and CeremonyRegistry (`0x739B5fae312834bA2a7e44525bA5f54853C5672f`) both deployed Phase 68, MPC ceremony complete (IoTeX block #41723255 beacon, 3 circuits × 3 contributors, `verifyCeremony()` confirmed on-chain). Phase 69 introduces the Data Sovereignty Layer: DataSovereigntyRegistry (immutable on-chain pledge, 3-tier MANUFACTURER/DEVELOPER/GAMER licensing), HumanityOracle/RulingOracle/PassportOracle (native VAPI oracles queryable by any IoTeX contract), VAPIRewardDistributor (DePIN token distribution, stacked multipliers up to ~15.75×), VAPIDataMarketplace (three-tier data exchange, 70% device pool / 30% treasury), and DataCuratorAgent (Python background agent, 7-class taxonomy, 5-minute poll, lineage builder + eligibility engine + oracle publisher). Phase 70 adds governance infrastructure: VAPIGovernanceTimelock (48-hour queued operator transitions, co-signer cancel, CEI pattern), VAPIProtocolLens (pure-view single eth_call synthesizing all four oracle contracts into `DeviceProtocolState`; `isFullyEligible()` is the tournament integration gate), full agent wiring (DataCuratorAgent + SessionAdjudicator + RulingEnforcementAgent all started in the main asyncio event loop), BridgeAgent tools #41–45, and GET /agent/validation-stats unified observability endpoint. Living calibration (Mode 6, Phase 38) autonomously evolves L4 thresholds from verified session data every 6 hours using exponential decay weighting. All PITL thresholds are empirically calibrated from N=74 real sessions across 3 distinct players. Phase 63 introduces L6b — the first reactive involuntary probe: a sub-perceptual 10ms haptic pulse triggers an involuntary neuromuscular grip reflex measured as IMU accel-magnitude latency (human 80–280ms; bot 0–15ms). Phase 65 introduces the Autonomous Intelligence Layer (AIL): VAPIAgent (SDK) + SessionAdjudicator (bridge) produce PoAC-gated commitment-hash rulings (FLAG/HOLD/BLOCK/CERTIFY/CLEAR) bound to SDKAttestation trust anchor. Phase 66 closes the enforcement loop: RulingEnforcementAgent applies streak escalation (FLAG×5→HOLD, HOLD×2→BLOCK), anchors commitment_hash on-chain via RulingRegistry.sol (anti-replay, IoTeX testnet 4690), and suspends PHGCredential on confirmed BLOCK streaks. Phase 67 replaces the single-contributor ZK ceremony with a 3-contributor MPC trusted setup anchored to an IoTeX testnet block hash — the ceremony beacon is independently verifiable on-chain via CeremonyRegistry.sol, eliminating the ZK ceremony as an external trust assumption. The primary current limitation is single-population calibration: L4 functions as a per-player anomaly detector rather than a cross-player identifier (inter-person separation ratio 0.362).

**Keywords:** proof of cognition, gaming anti-cheat, verifiable gaming intelligence,
physical human controller input, PHCI certification, adaptive trigger attestation,
federated threat detection, on-chain verification

**ACM CCS Concepts:** Security and privacy → Authentication; Computer systems
organization → Embedded and cyber-physical systems; Computing methodologies →
Multi-agent systems

---

## 1. Introduction

Competitive online gaming operates without any cryptographic guarantee that the person
pressing the buttons is a human. Game servers trust client-reported inputs; anti-cheat
software (Easy Anti-Cheat, BattlEye, Vanguard) detects known cheat signatures at the
kernel level but cannot prove human operation — only the absence of *known* automated
tools. A sufficiently sophisticated bot can pass every existing client-side check by
injecting inputs directly into the HID driver stack, bypassing behavioral analysis
entirely. Professional esports competitions worth millions of dollars in prize money
have no cryptographic defense against this class of attack.

We identify the root gap as the **human-controller attestation problem**: given a player
who claims to have performed a gaming session on a physical controller, how can a
tournament operator — with no access to the player's hardware — verify the provenance
and physical plausibility of a player's controller input stream?

This paper makes five contributions toward solving this problem:

**1. Proof of Autonomous Cognition (PoAC).** A 228-byte cryptographic evidence rail that
chains sensor commitments, model manifests, world-model hashes, and inference results into
a tamper-evident, hash-linked sequence. Each record attests not just to *what* a device
sensed but to *why* it acted — capturing the decision context through a commitment to
accumulated agent state (§4). (PoAC proves commitment to cognitive context, not correctness
of cognition.)

**2. Physical Input Trust Layer (PITL).** A nine-level physics-backed liveness detection
stack combining hard structural checks (HID-XInput pipeline discrepancy, PoAC chain
integrity) with adaptive behavioral analysis (biometric Mahalanobis fingerprinting,
temporal rhythm analysis, behavioral archaeology, network correlation) and active physical
challenge-response (randomized adaptive trigger resistance profiling with motor-response
curve classification). Five of the nine layers exploit signals that cannot be replicated
by software injection (§7.5.1, §7.5.2). Section §7.5.2.1 derives game genre
certification requirements: L4 biometric activation depends on controller usage
patterns specific to game genre, producing four deployment tiers (FULL/STANDARD/LIMITED/NOT
RECOMMENDED). NCAA Football 26 is classified LIMITED CERTIFICATION (3 active features;
L4 operates as intra-player anomaly detector only, not inter-player identifier).

**3. PHG Humanity Credential.** A soulbound, non-transferable on-chain credential
(ERC-5192-inspired, `locked()=true`) whose validity reflects continuous behavioral
surveillance. Credentials are provisionally suspended when a device accumulates
consecutive critical behavioral windows and automatically reinstated when it clears —
making the credential a *living proof* of ongoing trustworthy behavior, not a one-time
certification (§7.5.4).

**4. Adaptive Detection Feedback Loop.** An anti-cheat system where retrospective behavioral
memory directly drives forward detection policy: devices labeled `critical` have their L4
Mahalanobis detection threshold tightened by 30% for subsequent sessions. The loop is
bounded (minimum multiplier floor 0.5×), reversible (label changes auto-restore the
threshold), and cryptographically bounded (the 228-byte PoAC wire format is unchanged)
(§7.5.5). Phase 38 adds Mode 6 living calibration: thresholds evolve autonomously from
verified session data every 6 hours using exponential decay weighting (α=0.95), bounded
to ±15% per cycle.

**5. Federated Cross-Instance Threat Correlation.** A privacy-preserving federation
protocol that exchanges cluster fingerprints (16-char SHA-256 hashes, non-reversible)
between independent bridge instances, enabling detection of bot farms that deliberately
distribute devices across shards to stay below each instance's local threshold (§7.5.6).

Together these contributions form **VAPI** (Verified Autonomous Physical Intelligence).
The primary certified device is the **DualShock Edge** (Sony CFI-ZCP1), whose motorized
adaptive trigger surface creates a detection surface that software cannot cross. The
primary blockchain is **IoTeX L1**, leveraging its native P256 precompile for
gas-efficient ECDSA verification. A secondary IoTeX Pebble Tracker integration
(§7.5.9) validates protocol extensibility to DePIN sensor domains — the same 228-byte
wire format operates unchanged.

The remainder of this paper is organized as follows. §2 surveys related work. §3
formalizes the system model. §4 presents the PoAC protocol. §5 describes the agent
architecture. §6 introduces the DePIN economic layer. §7 details the implementation,
with §7.5 presenting the complete DualShock Edge anti-cheat subsystem organized
by conceptual layer rather than development chronology. §8 presents evaluation results.
§9 analyzes security and threat models. §10 discusses limitations and future directions.
§11 concludes.

*VAPI is an independent research project. The DualShock Edge (CFI-ZCP1) is a trademark of Sony Interactive Entertainment. VAPI is not affiliated with, endorsed by, or sponsored by Sony Interactive Entertainment. The DualShock Edge is used as a research platform under fair use.*

---

## 2. Background and Related Work

### 2.1 Gaming Anti-Cheat: The Detection Gap

Existing anti-cheat systems (Easy Anti-Cheat, BattlEye, Vanguard) operate as kernel
drivers that scan for known cheat signatures in process memory and loaded modules.
They detect *what software is running* but cannot detect *whether inputs are human-generated*.
A driver-level HID injection attack — spoofing the USB report stream that the game
receives — defeats all signature-based detection because it operates below the HID
driver abstraction layer and produces reports indistinguishable from a real controller.

The literature on game bot detection focuses on behavioral analysis of input sequences [19]
and statistical anomaly detection over timing distributions [20]. VAPI complements these
approaches by adding a cryptographic layer: behavioral signals are committed and
chain-linked, making their provenance verifiable to a third party who was not present
during the session.

### 2.2 Decentralized Physical Infrastructure Networks

DePIN protocols incentivize the deployment and operation of physical infrastructure
through token rewards. Helium [2] pioneered Proof of Coverage for wireless networks.
Hivemapper [3] rewards dashcam operators for contributing street-level imagery.
These systems verify *presence* or *data quality* but none verify the *cognitive process*
by which a device interprets its environment. VAPI's DePIN extensibility (§7.5.9)
demonstrates that PoAC fills this gap for environmental monitoring devices, but the
primary contribution of this paper is gaming anti-cheat.

### 2.3 Trusted Execution and Remote Attestation

ARM TrustZone [6] and Intel SGX [9] verify *what code is running* but not *what the
code perceives or decides*. PoAC complements platform attestation by extending the
trust chain from code identity to cognitive content — committing actual sensor readings,
model weights, accumulated state, and inference outputs.

### 2.4 Verifiable Computation and zkML

Verifiable computation systems [11] allow proving correct execution of arbitrary programs.
Recent zkML efforts [12, 13] apply zero-knowledge proofs to ML inference. While
theoretically powerful, zkML faces severe practical barriers on microcontrollers: proof
generation requires minutes for small models on desktop hardware. PoAC adopts a
pragmatic alternative: rather than proving *correct execution* of inference (zkML), we
prove *commitment to the complete cognitive context*, trading zero-knowledge guarantees
for real-time feasibility. VAPI does integrate a Groth16 ZK circuit for PITL session
proofs (§7.5.3), but at the session level (one proof per gaming session, not per
cognition cycle).

### 2.5 Autonomous Agent Architectures

The BDI model [16] decomposes agent reasoning into beliefs, desires, and intentions.
Subsumption architectures [17] layer reactive behaviors with priority-based arbitration.
VAPI's three-layer architecture (reflexive/deliberative/strategic) draws on both: the
world model encodes beliefs, bounty evaluation encodes desires, and PoAC records encode
intentions. Critically, VAPI operates entirely on-device with no cloud dependency for
core cognition.

---

## 3. System Model and Definitions

**Definition 1 (Embodied Agent).** An embodied agent $\mathcal{A}$ is a tuple
$(\mathcal{S}, \mathcal{M}, \mathcal{W}, \mathcal{D}, \mathcal{K})$ where $\mathcal{S}$
is a sensor suite, $\mathcal{M}$ is an inference model, $\mathcal{W}$ is a world model
(accumulated state), $\mathcal{D}$ is a decision function, and $\mathcal{K}$ is a
signing keypair.

**Definition 2 (Cognition Cycle).** A single cognition cycle $c_i$ at time $t_i$ consists of:
1. **Perception**: $s_i \leftarrow \text{sense}(\mathcal{S}, t_i)$
2. **Commitment**: $h_s \leftarrow H(s_i)$, $h_m \leftarrow H(\mathcal{M})$, $h_w \leftarrow H(\mathcal{W})$
3. **Inference**: $(y_i, p_i) \leftarrow \mathcal{M}(s_i)$
4. **Decision**: $a_i \leftarrow \mathcal{D}(y_i, p_i, \mathcal{W})$
5. **Attestation**: $\rho_i \leftarrow \text{sign}(\mathcal{K}, [h_{i-1} \| h_s \| h_m \| h_w \| y_i \| a_i \| \text{ctx}_i])$
6. **Update**: $\mathcal{W} \leftarrow \mathcal{W} \cup \{(s_i, y_i, a_i)\}$

**Definition 3 (PoAC Chain).** A PoAC chain for device $d$ is an ordered sequence
$\langle \rho_0, \rho_1, \ldots, \rho_n \rangle$ where $\rho_i.\text{prev\_hash} = \text{SHA-256}(\rho_{i-1}.\text{body}_{164})$
and $\rho_i.\text{ctr} > \rho_{i-1}.\text{ctr}$, forming a hash-linked, monotonically-ordered
evidence log. Note: the chain link hash uses the 164-byte signed body only; the 64-byte
ECDSA signature is excluded from the hash to match `PoACVerifier.sol`.

**Definition 4 (PHG Credential State).** A device's PHG credential is in one of three
states: `stable` (actively accumulating humanity evidence), `suspended` (credential
provisionally revoked due to consecutive critical behavioral windows), or `cleared`
(previously suspended, now exhibiting clean behavior). Transitions are driven by
`InsightSynthesizer` (§7.5.5) and recorded on-chain.

**Threat Model.** We consider an adversary who: (T1) fabricates PoAC records without
the device key; (T2) replays valid records out of order; (T3) selectively omits records
to hide unfavorable evidence; (T4) injects synthetic sensor data to a legitimate device;
(T5) claims rewards for work not performed; (T6) executes a warm-up attack — gradually
training a bot to produce human-like behavioral signals over many sessions;
(T7) distributes a bot farm across multiple bridge shards to stay below each instance's
local detection threshold. We assume the device hardware is not physically compromised
and that the blockchain provides standard finality guarantees.

### What VAPI Proves vs What It Infers

The following table distinguishes cryptographic guarantees from empirical inferences and
explicit non-claims. Understanding this distinction is essential to honest evaluation of
the system.

**Table: What VAPI Proves vs What It Infers**

| Property | Guarantee Type | Mechanism |
|----------|----------------|-----------|
| Record origin (signed by registered key) | Cryptographic | ECDSA-P256 signature, key in CryptoCell-310 secure element |
| Record ordering (no reordering/insertion) | Cryptographic | Monotonic counter + hash-chain linkage |
| Replay resistance | Cryptographic | Monotonic counter + ZK nullifier/epoch |
| Chain integrity (omission detectable) | Cryptographic (verifiable gaps) | Missing counter values visible to any chain verifier |
| Physical human operation of controller | Empirical inference | PITL L0–L6 physics-coupled signals |
| Software injection absence | Empirical inference | IMU noise floor, gravity, causal coupling, temporal rhythm |
| Player identity across sessions | NOT currently proven — game-genre dependent | Separation ratio 0.362 for NCAA CFB 26 (3 active features); FPS/Racing genres expected > 2.0 ratio with 9–10 active features. See §7.5.2.1. |
| Biometric pipeline correctness (end-to-end) | NOT proven on-chain | ZK proof binds feature commitment and nullifier; raw→feature transformation is trusted |
| Inference code on-chain | Enforced via ZK circuit C2 (Phase 41) | `pub[2]=inferenceCode` in PITLSessionRegistry.sol; circuit constraint `inferenceResult ∉ [40,42]` makes cheat-code proofs ungenerable. Inference also committed off-chain in bridge SQLite. |
| Bridge execution honesty | Trust assumption (constrained) | Withholding detectable via chain gaps; computation constrained by ZK circuit; enforcement mediated |

---

## 4. The Proof of Autonomous Cognition Protocol

### 4.1 Record Structure

Each PoAC record is a fixed-size 228-byte structure: a 164-byte signed body and a
64-byte ECDSA-P256 signature. The fixed-size design eliminates parsing ambiguity, enables
zero-copy deserialization, and fits within a single NB-IoT uplink frame.

**Table 1: PoAC Record Wire Format (228 bytes, FROZEN)**

| Offset | Field | Size | Description |
|--------|-------|------|-------------|
| `0x00` | `prev_poac_hash` | 32 B | SHA-256 of previous record's 164-byte body (genesis: `0x00...0`) |
| `0x20` | `sensor_commitment` | 32 B | $H(\text{raw\_sensor\_buffer})$ |
| `0x40` | `model_manifest_hash` | 32 B | $H(\text{weights} \| \text{version} \| \text{arch\_id})$ |
| `0x60` | `world_model_hash` | 32 B | $H(\mathcal{W})$ — agent state *before* update |
| `0x80` | `inference_result` | 1 B | Encoded classification output |
| `0x81` | `action_code` | 1 B | Agent action |
| `0x82` | `confidence` | 1 B | Model confidence $\in [0, 255]$ |
| `0x83` | `battery_pct` | 1 B | Remaining energy $\in [0, 100]$ |
| `0x84` | `monotonic_ctr` | 4 B | Strictly increasing counter (big-endian) |
| `0x88` | `timestamp_ms` | 8 B | Unix epoch milliseconds |
| `0x90` | `latitude` | 8 B | WGS84 latitude |
| `0x98` | `longitude` | 8 B | WGS84 longitude |
| `0xA0` | `bounty_id` | 4 B | On-chain bounty reference |
| `0xA4` | `signature` | 64 B | ECDSA-P256: $r \| s$ |

> **Hashing invariants (CRITICAL):**
> - `record_hash` = SHA-256(raw[0:164]) — the 164-byte signed body; this value is stored as `prev_poac_hash` in the *next* record and as `lastRecordHash` in `PoACVerifier.sol`
> - `chain_hash` = SHA-256(raw[0:228]) — the full-record hash including signature; used as an off-chain convenience for indexing and de-duplication only; NOT used for chain linkage
> - These are different values. Using `chain_hash` as a chain link produces verification failures against `PoACVerifier.sol`.

The four 32-byte hash commitments (offsets `0x00`–`0x7F`) distinguish PoAC from simple
signed telemetry: they capture not just *what* was observed but the complete cognitive
context of *why* a particular action was chosen.

### 4.2 Chain Integrity

The `PoACVerifier` contract enforces four properties per submitted record:
- `submission.monotonicCtr > chainState.lastCounter` (ordering)
- `submission.prevPoACHash == chainState.lastRecordHash` (linkage)
- `|submission.timestampMs - block.timestamp × 1000| ≤ maxTimestampSkew` (freshness)
- Valid ECDSA-P256 signature over the 164-byte body (authenticity)

### 4.3 PITL Inference Codes

| Code | Name | Layer | Type |
|------|------|-------|------|
| `0x20` | NOMINAL | — | Normal human |
| `0x28` | DRIVER_INJECT | L2 | Hard cheat — blocks PHG, SkillOracle, tournament |
| `0x29` | WALLHACK_PREAIM | L3 | Hard cheat |
| `0x2A` | AIMBOT_BEHAVIORAL | L3 | Hard cheat |
| `0x2B` | TEMPORAL_ANOMALY | L5 | Advisory — committed but not blocking |
| `0x30` | BIOMETRIC_ANOMALY | L4 | Advisory — committed but not blocking |
| `0x31` | IMU_BUTTON_DECOUPLED | L2B | Advisory — IMU precursor absent before button press |
| `0x32` | STICK_IMU_DECOUPLED | L2C | Advisory — stick-IMU temporal correlation absent |

Hard codes `{0x28, 0x29, 0x2A}` are rejected by `TeamProofAggregator` and trigger
a −200-point `SkillOracle` penalty. Advisory codes `{0x2B, 0x30}` accumulate as
on-chain statistical evidence without directly affecting rating or eligibility.

---

## 5. Agent Architecture

VAPI implements a three-layer cognitive architecture adapted for resource-constrained
gaming controller hardware.

### 5.1 Layer 1: Reflexive (Period: 1 ms at 1 kHz gaming input rate)

The reflexive layer executes the core sense-infer-attest loop. For the DualShock Edge
subsystem: capture a 50-byte `InputSnapshot`, extract a 30-dimensional feature vector
(stick positions, velocities, accelerations, trigger values, button timing statistics,
IMU features, touchpad features, temporal features), run the INT8-quantized classifier
(30→64→32→6), generate a PoAC record, and submit to the batch queue.

**Detection thresholds** (invariant to adaptive policy):
- Hard cheat: confidence ≥ 180/255 (≈70%) triggers `CHEAT_ALERT` state
- Resolution: 10 consecutive clean windows required to exit `CHEAT_ALERT`

### 5.2 Layer 2: Deliberative (Period: 60 s)

Trend analysis, EWC world model updates, behavioral archaeology signals, and PHG
checkpoint commit decisions. If behavioral scores (warmup, burst) exceed thresholds,
the PHG score delta is multiplied by `max(0.0, 1.0 − warmup×0.8 − burst×0.5)` before
on-chain submission.

### 5.3 Layer 3: Strategic (Period: 5 min)

Bridge sync, session proof generation, ZK PITL proof submission. The autonomy guard
prevents external systems from disabling PoAC generation.

---

## 6. DePIN Economic Layer

The DePIN layer demonstrates PoAC extensibility to non-gaming sensor domains. Devices
autonomously evaluate, accept, and preempt environmental monitoring bounties using a
greedy knapsack optimizer (§6.3 of the original paper). Each economic decision is itself
a PoAC-attested record. This layer is not the primary contribution of this paper; see
Appendix A for complete details.

---

## 7. System Implementation

### 7.1 Overview

VAPI spans four implementation layers: firmware (C, Zephyr RTOS and ESP-IDF), smart
contracts (Solidity, Hardhat, IoTeX), a Python asyncio bridge service, and a DualShock
Edge controller anti-cheat subsystem. The prototype comprises ~220 files (~1,413 automated
tests total, ~1,385 in CI excluding hardware).

**Table 2: Implementation Component Summary**

| Component | Language | Key Dependencies |
|-----------|----------|-----------------|
| Firmware | C (Zephyr) | nRF Connect SDK, PSA Crypto, CryptoCell-310 |
| Controller | C (ESP-IDF) / Python | ESP-NN, TFLite Micro, pydualsense |
| Contracts | Solidity | OpenZeppelin, Hardhat, IoTeX P256 precompile |
| Bridge | Python | asyncio, Web3.py, aiomqtt, FastAPI, anthropic |
| SDK | Python + C99 | pytest, VAPISession, VAPIVerifier |

### 7.2 Smart Contract Stack

**Core verification:**
- `PoACVerifier` — P256 signature verification via IoTeX precompile `0x0100`, batch
  verification up to 10 records, chain state enforcement
- `TieredDeviceRegistry` — device identity, staking, reputation
  ($R = R_{\text{raw}} \times 10000 / (R_{\text{raw}} + 1000)$ with diminishing returns)

**Gaming intelligence:**
- `PHGRegistry` — PHG score checkpoints; `commitCheckpoint(deviceId, scoreDelta, count, biometricHash)`
- `PHGCredential` — soulbound credential; `suspend(bytes32,bytes32,uint256)`, `reinstate(bytes32)`, `isActive(bytes32)`
- `TournamentGateV3` — wraps V2's cumulative+velocity gates with `phgCredential.isActive()` as a third condition
- `SkillOracle` — ELO-inspired on-chain skill rating; NOMINAL/SKILLED increment, cheat −200 penalty
- `ProgressAttestation` — verifiable proof of improvement between two PoAC records
- `TeamProofAggregator` — Merkle-root team attestation; rejects records with hard cheat codes
- `PITLSessionRegistry` — ZK PITL session proofs; anti-replay via `usedNullifiers`. In production mode
  (`pitlVerifier ≠ address(0)`), the Groth16 proof cryptographically enforces feature commitment,
  humanity probability, nullifier uniqueness, and epoch binding. Known limitation: the inference code
  (`inferenceResult`) is passed as pub[2]=0 and not currently enforced on-chain; it is committed
  off-chain in the bridge SQLite store.

**Federation:**
- `FederatedThreatRegistry` — immutable on-chain anchor for cross-confirmed cluster hashes

### 7.3 Bridge Service

The bridge is a Python asyncio application providing three transport ingestion channels
(MQTT, CoAP, HTTP), a batch accumulator (bounded `asyncio.Queue(maxsize=1000)`), six
intelligence background tasks, and two API sub-applications.

**Background tasks:**
1. `ChainReconciler` — confirms PHG checkpoint receipts every 30 s
2. `ProactiveMonitor` — bot-farm cluster + high-risk trajectory + eligibility surveillance every 60 s
3. `FederationBus` — peer cluster fingerprint exchange every 120 s
4. `InsightSynthesizer` — 6-mode longitudinal synthesis (Mode 6: living calibration) + detection policies every 6 h
5. `AlertRouter` — webhook dispatch for enforcement events every 30 s
6. `BridgeAgent` — LLM-powered operator intelligence (on-demand, not polled)

---

## 7.5 DualShock Edge: Proof of Human Gaming

### 7.5.1 The Adaptive Trigger Detection Surface

The DualShock Edge (CFI-ZCP1) is the production PHCI (Physical Human Controller Input)
certified device. Its defining hardware feature is the motorized L2/R2 adaptive trigger
system, generating programmable resistance force profiles at approximately 200 Hz.

Unlike every other controller sensor — stick axes, gyroscope, accelerometer, buttons —
the trigger resistance dynamics emerge from a mechanical actuator whose behavior is
governed by physical laws (spring constants, friction, thermal noise, electromagnetic
hysteresis) that software cannot replicate or inject. A cheating player using
software-injected inputs can reproduce stick trajectories and button timings, but cannot
reproduce the micro-jitter, onset velocity profile, and grip-force ratio that a real
human hand produces against a real adaptive trigger.

The DualShock Edge adaptive trigger surface is a physics-backed liveness detection surface
that cannot be crossed by software-only injection.

**Sensor commitment schema v2** (kinematic/haptic) commits into every PoAC record's
32-byte `sensor_commitment` field:
- Left/right stick axes (4 × int16)
- Trigger depression values (2 × uint8)
- **Trigger resistance effect mode** (2 × uint8) — read from controller ADC, not writable
  from host HID stack
- Gyroscope (3 × int16)
- Accelerometer (3 × int16)
- Timestamp (int64)

**L6 challenge extension (conditional, +4 bytes → 52 bytes total).** When L6 Active
Physical Challenge-Response is enabled and a challenge is in flight, the sensor
commitment preimage is extended with: challenge `profile_id` (uint8), 16-bit SHA-256
profile fingerprint (uint16), and `l6_score_int` = ⌊p_human_L6 × 100⌋ (uint8). When
L6 is disabled or no challenge is pending, the preimage remains 48 bytes — producing
byte-identical commitments to any pre-L6 record. The extension is conditional and
non-breaking.

Any software injection that fails to reproduce physical resistance dynamics produces a
measurably different sensor commitment, breaking hash-chain consistency.

### 7.5.2 Physical Input Trust Layer

VAPI implements a nine-level detection stack. Each level is independent; detections at
any level produce PITL inference codes committed into the PoAC record. L2B and L2C are
independent advisory oracles within the L2 detection band, exploiting temporal coupling
physics absent from software injection.

**Table 3: PITL Architecture (nine-level)**

| Layer | Module | Code | Type | Signal |
|-------|--------|------|------|--------|
| L0 | Physical presence | — | Structural | Controller must be HID-connected, live input |
| L1 | PoAC chain integrity | — | Structural | SHA-256 linkage, monotonic counter, timestamp freshness |
| L2 | `hid_xinput_oracle.py` | `0x28` | Hard cheat | HID report vs. XInput API discrepancy + gravity-absent signal (mean accel < 100 LSB) |
| L3 | `tinyml_backend_cheat.py` | `0x29`, `0x2A` | Hard cheat | 9-feature temporal behavioral analysis (30→64→32→6 INT8 net) |
| L2B | `l2b_imu_press_correlation.py` | `0x31` | Advisory | IMU micro-disturbance absent in 5–80ms precursor window before button rising edge |
| L2C | `l2c_stick_imu_correlation.py` | `0x32` | Advisory | Max Pearson cross-corr of stick velocity vs. gyro_z at causal lags 10–60ms < 0.15 |
| L4 | `tinyml_biometric_fusion.py` | `0x30` | Advisory | 11-signal Mahalanobis kinematic fingerprint: triggers, tremor FFT (8–12 Hz), touchpad biometric |
| L5 | `temporal_rhythm_oracle.py` | `0x2B` | Advisory | CV < 0.08, Shannon entropy < 1.0 bits, 60 Hz quantization > 0.55; fires on ≥ 2/3 |
| L6 | `l6_trigger_driver.py` + `l6_response_analyzer.py` | — | Advisory | Randomized trigger resistance challenge; human motor onset/settle/grip-variance curve |

**L2 — HID injection detection.**
Software injection attacks (SendInput, XInput emulation, vJoy, DS4Windows spoofing)
cannot produce physical IMU readings. The oracle fires `0x28` when:
```
imu_noise = std(gyro) over 50 reports < 0.001 rad/s
AND
stick_magnitude > 0.15 of full range
```
The 0.001 rad/s threshold is below any real controller's noise floor (typically
0.01–0.05 rad/s at rest). A physical controller always exceeds this floor due to hand
micro-tremors. **Live measurement on DualShock Edge CFI-ZCP1:** stationary gyro std
< 50 LSB (≈ 0.05 rad/s, confirmed via `test_imu_noise_floor`); active play gyro std =
201 LSB (≈ 0.22 rad/s) — a **10,000× margin** above the 0.02 LSB (0.001 rad/s)
injection threshold.

**Gravity-signal extension.** A second, independent L2 signal fires on any session
regardless of active-frame count: `mean(||accel||) < 100 LSB`. Real controllers under
gravity always read ≈2,048–2,150 LSB total accel magnitude; injected frames zero all
three accel channels, producing magnitude ≈ 0. This signal closes the idle-start gap
(sessions where the player was in a lobby with no active trigger inputs): validated at
100% injection detection after adding this signal (up from 80% pre-fix).

**L3 — Behavioral ML.**
The 9-feature temporal classifier (velocity-stop events, jerk-correction lag,
aim-settling variance, button timing σ², stick autocorrelation, reaction-time proxy)
targets `MACRO` (σ² < 1.0 ms²) and `AIMBOT` (ballistic jerk > 2.0) patterns that
survive the L2 IMU check.

**L4 — Biometric Mahalanobis fingerprinting.**
Twelve kinematic features per 50-report window are compared against a per-device *stable EMA
baseline* — updated only on clean NOMINAL sessions to prevent fingerprint poisoning.
The 12-feature space (Phase 17 expansion from 7; index 9 replaced Phase 46; index 11 added Phase 57): `trigger_resistance_change_rate`,
`trigger_onset_velocity_L2/R2`, `micro_tremor_accel_variance`, `grip_asymmetry`,
`stick_autocorr_lag1/5`, `tremor_peak_hz`, `tremor_band_power` (tremor FFT 8–12 Hz band),
`accel_magnitude_spectral_entropy` (Phase 46; replaces structurally-zero `touchpad_active_fraction`), `touch_position_variance`,
`press_timing_jitter_variance` (Phase 57; normalised IBI variance — human physiological jitter 0.001–0.05; bot macro < 0.00005). `accel_magnitude_spectral_entropy` is the Shannon entropy of the 0–500 Hz power spectrum of the gravity-invariant accel magnitude ||accel||; computed from a 1024-sample ring buffer (0.977 Hz/bin at 1000 Hz). Per-player entropy means are nearly identical across the N=69 calibration corpus (P1: 4.878 bits, P2: 4.882 bits, P3: 4.767 bits) — this feature is a **bot-vs-human discriminator, not an inter-player identifier**. It does not contribute to inter-person separation. Human range: 0.93–8.59 bits (mean 4.93, std 1.30); static-zero injection: 0.0 (variance guard); random-noise injection: ~9.0 bits. The stable-vs-candidate architecture
is the key security property: an adversary who gradually shifts the EMA over many borderline
sessions cannot poison the stable reference.

`fingerprint_drift_velocity` (L2 norm between candidate and stable means) is an
additional contamination signal surface-able via the `BridgeAgent` tool
`get_behavioral_report`.

**L5 — Temporal rhythm oracle.**
Bot scripts produce near-constant inter-press intervals. The oracle characterizes
the inter-event timing distribution over a 120-event deque (min 20 samples) and fires
`0x2B TEMPORAL_ANOMALY` when ≥ 2 of 3 signals are suspicious:
- Coefficient of variation (CV) < 0.08 — near-zero timing variance
- Shannon entropy < 1.0 bits — few distinct interval values (hardware-calibrated N=69, 3 players; human baseline: ~4.56 bits mean)
- 60 Hz quantization score > 0.55 — intervals cluster at 16.67 ms multiples

L5 uses four-button tracking via `push_snapshot()` rising-edge detection: Cross (X), L2_dig, R2,
and Triangle — in descending IBI-CV priority (1.373, 1.333, 1.176, 1.138). When no single button
accumulates ≥ 20 inter-press intervals, a pooled IBI fallback merges all buttons with ≥ 5 samples
into one sequence. This reduces genre-dependent exclusion from 24.6 % (R2-only, Phase 16B) to
near-zero across N=69 real sessions. The `source` field ('cross', 'l2_dig', 'r2', 'triangle',
'pooled') is persisted in PITL metadata for operator visibility.

`rhythm_humanity_score = (cv_humanity + entropy_score + non_quant) / 3.0 ∈ [0,1]`
contributes to the PHG humanity probability as a positive signal for high-variance,
high-entropy timing.

**L6 — Active physical challenge-response.**
L0–L5 are *passive* — they observe sensor signals generated by normal play.
L6 is *active*: the host generates a randomized adaptive trigger resistance
profile (one of 8 named profiles spanning Off, Rigid 80–255 N, Pulse slow/fast,
asymmetric, and buildup patterns), writes it to the DualShock Edge via USB output
report 0x02, and measures the controller's HID input stream for the human motor
response over the following 3-second window.

Human motor response to a resistance change is governed by involuntary
biomechanics: the hand requires 40–300 ms onset latency (neuromuscular delay
+ motor-planning time), produces measurable grip-force variance (accel magnitude
variance > 0 from hand micro-tremors adjusting to the new resistance), and
exhibits natural settling as muscles adapt. Software injection — which cannot
feel resistance it cannot sense — cannot replicate any of these properties.

The classifier produces `p_human_L6 ∈ [0.0, 1.0]` from four metrics:
- `onset_ms`: frames until trigger ADC delta > 5 LSB after challenge sent
- `peak_delta`: max |r2_post − r2_pre_mean| in the response window
- `settle_ms`: frames until r2 returns within 10% of pre-challenge mean
- `grip_variance`: variance of `||accel||` during response window

**Attack G (challenge-invariant injection) signature:** `grip_variance == 0.0`
(zeroed accelerometer) → `p_human_L6 = 0.0`; `onset_ms < 5 ms` (sub-neurological
latency) → `p_human_L6 ≤ 0.2`. Both are impossible for physical human operation.

**Safety invariants:** L6 is disabled by default (`L6_CHALLENGES_ENABLED=false`).
Challenges are never dispatched during idle windows (r2 = l2 = 0 for last 10 reports)
to avoid disrupting gameplay. Triggers restore to BASELINE_OFF (no resistance) within
3 seconds and always on session shutdown. The null signal (no response received) returns
`p_human_L6 = 0.5` — conservative, non-penalizing.

**Current status:** L6 is fully implemented and unit-tested (33 tests), including
Attack G synthetic adversarial validation. Human motor response baseline calibration
— characterizing real onset/settle/grip-variance distributions from real DualShock
Edge challenge sessions — has not yet been performed. Section §10.6 describes this
as the immediate next hardware validation milestone.

### 7.5.2.1 Game Genre Certification Requirements for PITL Biometric Activation

Each of the twelve L4 biometric features is conditional on specific controller
usage patterns that vary substantially by game genre. A session in which the player
never moves the right stick, never presses L2, and never triggers simultaneous
dual-grip produces feature vectors with up to 8 of 12 fields structurally zero —
not because the human is unusual, but because the game did not elicit the relevant
motor behavior. (`accel_magnitude_spectral_entropy` is active in all held-device sessions
regardless of game genre and therefore is not structurally zero in this scenario.) This section derives minimum controller-usage requirements for each
L4 feature, characterizes which game genres satisfy them, and defines VAPI tournament
deployment certification tiers.

**Empirical basis:** Per-feature symmetric KL divergence computed from N=64 real
DualShock Edge sessions (3 players, NCAA Football 26) in
`docs/interperson-separation-analysis-v2.md §Phase 41`. In that dataset, 5 of 12
features are structurally zero (Phase 46 replaced `touchpad_active_fraction` at index 9
with `accel_magnitude_spectral_entropy`, which is active in all sessions — zero-fraction 0%
across N=69 calibration windows; Phase 57 added `press_timing_jitter_variance` at index 11)
and only `stick_autocorr_lag1/5` provides meaningful
inter-player information — solely because Player 3 uses the right stick far less than
Players 1/2, not because of individual physiological differences.

---

#### Minimum Controller-Usage Requirements per Feature

**Table 7.5.2.1-A: L4 Feature Activation Requirements**

| Feature | Required Controller Behavior | Minimum Threshold | Notes |
|---------|------------------------------|-------------------|-------|
| `trigger_resistance_change_rate` | Game must send mid-session adaptive trigger effect changes via USB output report 0x02 | ≥ 1 effect-mode transition per session | Requires DualShock Edge firmware + game support. Structurally zero in any game with static trigger profiles. |
| `trigger_onset_velocity_L2` | L2 trigger must be depressed from rest (ADC ≤ 5) to engagement (ADC > 200) as distinct press events | ≥ 50 rising-edge events per session | NCAA Football 26: ~5–20 formation-select presses. Below threshold for onset statistics. |
| `trigger_onset_velocity_R2` | R2 trigger must exhibit onset cycles; continuous hold does NOT register new onset events | ≥ 50 rising-edge events per session | Sprint (hold) does not count. Requires repeated fire/brake/throw actions. |
| `micro_tremor_accel_variance` | Device must have still-frame windows (gyro_mag < 20 LSB) during active session; accel variance computed only during those frames | ≥ 10 still-frame passes per session | Present in most genres during brief pauses, menus, or low-movement moments. Gyro gate is empirically calibrated at 20 LSB (raw HID). |
| `grip_asymmetry` | L2 and R2 must both exceed 10 ADC simultaneously (dual-press frame) | ≥ 10 dual-press frames per session | Requires mechanical co-activation: ADS+shoot (FPS), brake+accelerate (racing), or parry+strike (action). Any game where L2 and R2 are contextually exclusive yields grip_asymmetry = 1.000 for all sessions. |
| `stick_autocorr_lag1` | right_stick_x must deviate from dead-zone center (128) with temporal persistence | ≥ 100 non-dead-zone right-stick reports per session | Captures characteristic micro-correction patterns in sustained aim or camera movement. Spiky one-off movements contribute less than smooth persistent input. |
| `stick_autocorr_lag5` | Same as lag1; lag5 captures longer motor persistence | ≥ 200 non-dead-zone frames | Requires continuous right-stick engagement, not single-frame panning. |
| `tremor_peak_hz` | right_stick_x must accumulate ≥ 1025 non-dead-zone frames in the extractor's ring buffer | ≥ 1025 consecutive non-dead-zone reports (ring buffer fills in ~1.0s of continuous aim) | Physiological tremor is 8–12 Hz. Bot scripts that precisely track a target produce near-zero tremor. FFT resolution: 0.977 Hz/bin at 1000 Hz with 1024 velocity samples — 4 bins across the 8–12 Hz tremor band (Phase 49). |
| `tremor_band_power` | Same as `tremor_peak_hz` | ≥ 1025 frames | Collapses to 0 when FFT is inactive. Correlated with `tremor_peak_hz`. |
| `accel_magnitude_spectral_entropy` | Device must be physically held during gameplay (accel variance > 4 LSB²); requires 1024-sample ring buffer to warm up (~1s at 1000 Hz) | 1024 cumulative report frames | Gravity-invariant (||accel|| eliminates orientation dependence). Active in all genres where the device is physically held. Per-player means are nearly identical (P1: 4.878, P2: 4.882, P3: 4.767 bits) — bot-vs-human discriminator only, not inter-player identifier. Replaces structurally-zero `touchpad_active_fraction` (Phase 46). |
| `touch_position_variance` | Session must be captured with Phase 17+ `capture_session.py` (adds `touch_active` field); requires ≥ 3 touch-active frames for variance to be non-trivial | Post-Phase-17 capture, ≥ 3 touch-active frames | Captures per-player characteristic thumb resting position (high-value biometric once populated). |

---

#### Game Genre Certification Table

Certification tier is determined by the number of L4 features **active** in typical play
for that genre. "Active" means the feature is expected to have non-zero variance across
sessions from the same player — sufficient to inform the Mahalanobis fingerprint.
Feature 11 (`touch_position_variance`) is counted only for post-Phase-17 captures. Feature 10 (`accel_magnitude_spectral_entropy`) is counted for all captures (active regardless of game genre).

**Tiers:**
- **FULL CERTIFICATION (≥ 9/11):** L4 operates as a full inter-player biometric identifier. Intra-player anomaly detection and cross-player transplant detection are both reliable.
- **STANDARD CERTIFICATION (6–8/11):** L4 inter-player discrimination is partial. Intra-player anomaly detection reliable; transplant detection viable with N ≥ 20 sessions per player.
- **LIMITED CERTIFICATION (3–5/11):** L4 operates as intra-player anomaly detector only. Zero inter-player discriminability expected. L1, L2, L2B/C, L3, and L5 remain fully active for cheat detection; L4 adds session-consistency evidence but cannot identify the player.
- **NOT RECOMMENDED (≤ 2/11):** L4 biometric layer is effectively inactive. PITL integrity is provided by L1/L2/L3/L5 only. Not suitable for tournament deployment where biometric identity binding is required.

**Table 7.5.2.1-B: Per-Genre L4 Feature Activation**

| Genre | Rep. Titles | 1 `trg_resist` | 2 `onset_L2` | 3 `onset_R2` | 4 `micro_tremor` | 5 `grip_asym` | 6 `autocorr_lag1` | 7 `autocorr_lag5` | 8 `tremor_hz` | 9 `tremor_power` | 10 `accel_ent` | 11 `tp_var` | **Active** | **Tier** |
|-------|-------------|:--------------:|:------------:|:------------:|:----------------:|:-------------:|:-----------------:|:-----------------:|:-------------:|:----------------:|:-----------:|:-----------:|:----------:|----------|
| FPS / Battle Royale | COD Black Ops 6, Halo Infinite, Apex Legends, Fortnite | ⚠️¹ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓² | ✓² | **9–10** | **FULL** |
| Racing (Simulation) | Gran Turismo 7, Forza Motorsport, F1 24 | ✓³ | ✓ | ✓ | ✓ | ✓ | ⚠️⁴ | ⚠️⁴ | ⚠️⁴ | ⚠️⁴ | ✓² | ✓² | **7–9** | **STANDARD–FULL** |
| Action-Adventure / RPG | Elden Ring, God of War, Spider-Man 2 | ⚠️⁵ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓² | ✓² | **8–10** | **FULL** |
| Adaptive-Trigger Native | Returnal, Ratchet & Clank: Rift Apart, Astro's Playroom | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓² | ✓² | **10–11** | **FULL** |
| Fighting | Street Fighter 6, Mortal Kombat 1, Tekken 8 | ✗ | ⚠️⁶ | ⚠️⁶ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓² | ✓² | **3–5** | ⚠️ **LIMITED** |
| Sports — Real-Time Aim | NBA 2K25, MLB The Show 24 (pitching/hitting) | ✓³ | ✓ | ✓ | ✓ | ✓ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ✓² | ✓² | **6–8** | **STANDARD** |
| Sports — Sim Football (NCAA CFB, Madden) | NCAA Football 26, Madden NFL 25 | ✗ | ✗ | ✗⁷ | ✓ | ✗ | ✗⁸ | ✗⁸ | ✗⁸ | ✗⁸ | ✓² | ✓² | **2–3** | ⛔ **NOT REC.** / ⚠️ LIMITED |
| Platformer / Narrative | Crash Bandicoot, Astro Bot, Death Stranding | ✗ | ⚠️ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓² | ✓² | **3–5** | ⚠️ **LIMITED** |

¹ FPS games vary: COD on PlayStation uses adaptive trigger support (Haptic Feedback mode); PC-origin ports (Apex, Fortnite) typically do not.<br>
² `touch_position_variance` (feature 11) requires post-Phase-17 session capture. For pre-Phase-17 captures, subtract 1 from active count. Feature 10 (`accel_magnitude_spectral_entropy`) is active in all held-device sessions regardless of capture script version. Feature 12 (`press_timing_jitter_variance`, Phase 57) activates after ≥4 inter-button-press intervals are accumulated.<br>
³ Gran Turismo 7, Forza Motorsport, and NBA 2K use resistance profiles for ABS/grip feedback; feature activates reliably.<br>
⁴ Racing right-stick (camera) is often held static during race focus. Feature activates in camera-heavy moments (replays, cornering). Autocorr and tremor are partial.<br>
⁵ Game-dependent; adaptive trigger support varies. God of War: no. Horizon FW: yes (bow draw). Spider-Man 2: yes (web-shooter modulation).<br>
⁶ L2/R2 are medium/heavy attacks in many fighting games; ≥50 presses per session is achievable in high-level play but not guaranteed at lower engagement.<br>
⁷ R2 is sprint in NCAA Football 26 and is held continuously, not pressed in repeated onset cycles. Onset velocity requires release-and-re-press events.<br>
⁸ Right stick is near-stationary (128 dead zone) throughout almost all NCAA Football 26 sessions. From N=64 sessions: only 1/38 P1 sessions had any non-zero `tremor_peak_hz`.

---

#### NCAA Football 26: LIMITED CERTIFICATION

Based on N=64 hardware-validated sessions (Phase 41 post-analysis), NCAA Football 26
with the DualShock Edge is assigned **LIMITED CERTIFICATION** for VAPI tournament deployment.

**What the protocol proves in this configuration:**
- L1 PoAC chain integrity — every record cryptographically signed, ordered, and linked. Tampering, reordering, and omission are detectable.
- L2 injection detection (`0x28`) — IMU noise floor and gravity-absent signal fully active. Software injection is detected regardless of game.
- L2B/L2C advisory oracles (`0x31`, `0x32`) — IMU-button causal coupling and stick-IMU temporal cross-correlation. Functional for button events; L2C is limited by right-stick dead-zone (68/69 sessions static stick, both confirmed in N=69 Phase 17 and N=64 Phase 41 data).
- L3 behavioral ML (`0x29`, `0x2A`) — Fully active. Bot macro/aimbot patterns are detectable.
- L5 temporal rhythm oracle (`0x2B`) — Fully active on Cross, L2_dig, R2, Triangle button inter-press intervals. Multi-button pooled fallback covers low-press-frequency play styles.

**What L4 provides in this configuration:**
L4 operates as **intra-player session consistency detector only** — not as an inter-player identifier.

| Property | Status in NCAA CFB 26 |
|----------|----------------------|
| Intra-player session anomaly detection (is this session consistent with this device's history?) | **ACTIVE** — 3 active features (micro_tremor, stick_autocorr_lag1/5) inform the EMA fingerprint. Unusual play behavior within a single player's session history is detectable. |
| Cross-player transplant detection (is this a different player using this credential?) | **NOT ACTIVE** — separation ratio 0.362 (threshold > 2.0). P1/P2 are statistically indistinguishable across all 5 active features. L4 cannot detect one player's sessions submitted under another's device ID. |
| Structural zero-variance features (trigger_resistance_change_rate, trigger_onset_velocity_L2/R2, tremor_peak_hz, tremor_band_power, touch_position_variance) | **INERT** — auto-excluded by ZERO_VAR_THRESHOLD = 1e-4 in BiometricFusionClassifier. These features do not contribute false-positive 0x30 signals; they simply do not contribute. |
| `accel_magnitude_spectral_entropy` (index 9, Phase 46) | **ACTIVE — bot-vs-human only.** Non-zero across all N=69 sessions (mean 4.93 bits, zero-fraction 0%). Per-player means P1/P2/P3 are nearly identical (4.878/4.882/4.767 bits). Contributes to intra-player anomaly detection and bot discrimination; does **not** contribute to inter-player separation. |

**Recommended use:** VAPI-certified NCAA Football 26 tournaments are appropriate where the
integrity requirements are: (a) verifying that a real controller was physically operated
(not software-injected), (b) detecting automated bot scripts via L5 timing anomalies, and
(c) establishing a tamper-evident PoAC evidence chain per session. They are **not** appropriate
where the requirement is to verify that the same human operated the device across all sessions —
that guarantee requires FULL or STANDARD CERTIFICATION (FPS, Racing, Action-Adventure genres).

---

#### Upgrade Path to FULL CERTIFICATION for Football Titles

Any future football title that implements the following mechanics will upgrade from LIMITED
to STANDARD or FULL CERTIFICATION without protocol changes:

1. **Implement adaptive trigger resistance profiles** for kick-power meters, tackle strength, or catch trajectories. This activates `trigger_resistance_change_rate`.
2. **Require L2 as a non-formation action** (e.g., receiver route adjustments post-snap, secondary defensive commands). This produces ≥50 L2 onset events per session and activates `trigger_onset_velocity_L2`.
3. **Map right stick to a continuous action** (spin move, juke direction, camera rotation during replays with player control). This fills the 513-frame FFT ring buffer and activates `tremor_peak_hz`, `tremor_band_power`, and strengthens `stick_autocorr_lag1/5`.
4. **Enable simultaneous L2+R2 mechanics** (e.g., a precision kick charge requiring both triggers). This activates `grip_asymmetry`.

Alternatively, a VAPI-certified multi-genre session structure (one FPS session + one CFB session per hour) would satisfy the feature activation requirements through the FPS session, with the CFB session contributing L1/L2/L3/L5 evidence to the same device's PHG credential stream.

---

*Derived from per-feature KL divergence analysis in `docs/interperson-separation-analysis-v2.md §Phase 41 Post-Analysis`. Separation thresholds based on Gaussian KL divergence ≥ 0.5 = discriminating, Cohen's d ≥ 0.5 = meaningfully separated. Game genre assignments are protocol-author assessments based on published control schemes; individual game configuration may vary.*

### 7.5.3 Zero-Knowledge PITL Session Proof

The bridge generates a Groth16 proof (BN254, ~1,820 constraints, 2^11 powers-of-tau)
at session shutdown, establishing four cryptographic invariants without revealing raw
sensor features on-chain:

**Public inputs (5):**
- `featureCommitment` — Poseidon(7)(scaledFeatures[0..6])
- `humanityProbInt` — humanity_prob × 1000 ∈ [0, 1000]
- `inferenceResult` — 8-bit inference code (see known limitation below)
- `nullifierHash` — Poseidon(deviceIdHash, epoch) — anti-replay binding
- `epoch` — block.number / EPOCH_BLOCKS

**Circuit constraints enforced:**
- C1: featureCommitment = Poseidon of exactly the 7 secret L4 biometric features
- C3: humanityProbInt ∈ [0, 1000]
- C4: nullifierHash = Poseidon(deviceIdHash, epoch) — session uniqueness
- C5: L5 rhythm score ∈ [0, 1000]

**Known limitation — inference code not bound on-chain:**
Circuit constraint C2 (inferenceResult range check) exists in the circom circuit, but
`PITLSessionRegistry.sol` passes `pub[2] = 0` to the on-chain verifier. The inference
code is committed off-chain in the bridge SQLite store (`records.inference`). This means
the ZK proof does not currently prevent the bridge from submitting a proof with any
inference code — the circuit cannot distinguish. This is documented in
`PITLSessionRegistry.sol` and will be corrected when the circuit is upgraded.

**What the proof does NOT establish:**
- That the raw sensor data was transformed into features correctly
- That the bridge executed the biometric pipeline honestly end-to-end
- That the inference code in the PoAC record matches the inference the circuit was given

`PITLSessionRegistry.sol` (deployed at `0x8da0A497234C57914a46279A8F938C07D3Eb5f12`, testnet)
accepts 256-byte proofs, enforces `usedNullifiers` anti-replay, and tracks per-device
`latestHumanityProb` and `sessionCount`. The real Groth16 verifier (`PitlSessionProofVerifier`,
`0x07D3ca1548678410edC505406f022399920d4072`) is set and active; mock mode is disabled on
the live deployment.

Phase 67 upgrades the trusted setup to a 3-contributor MPC ceremony using the Hermez
`powersOfTau28_hez_final_15.ptau` Phase 1 source with an IoTeX-block-anchored Phase 2
beacon. Ceremony provenance is registered on-chain in `CeremonyRegistry.sol` (§10.3).

### 7.5.4 PHG Credential and Economic Enforcement

**PHG humanity probability fusion.**
Per session, three signals are fused into `humanity_probability ∈ [0,1]`:
```
p_L4   = exp(−max(0, d_L4 − 2.0))              # biometric match (11-signal)
p_L5   = rhythm_humanity_score                  # timing humanity
p_E4   = exp(−drift / 3.0)                     # cognitive stability
p_L2B  = imu_press_oracle.humanity_score()      # IMU-button causal coupling [0,1]
p_L2C  = stick_imu_oracle.humanity_score()      # stick-IMU cross-correlation [0,1]

# Without L6 (default):
humanity_probability = 0.28·p_L4 + 0.27·p_L5 + 0.20·p_E4 + 0.15·p_L2B + 0.10·p_L2C
```

**L6 reweighting.** When L6 is active, the humanity probability fuses six independent
signals: `p_human = 0.23·p_L4 + 0.22·p_L5 + 0.15·p_E4 + 0.15·p_L6 + 0.15·p_L2B + 0.10·p_L2C`.
When L6 is disabled (default), the five-signal formula above applies. L2B and L2C
default to 0.5 (neutral) before oracle warmup, preserving [0,1] boundedness.
L6 participation in the ZK PITL circuit (§7.5.3) is noted as future work. The
multi-contributor ceremony (§10.3) is complete as of Phase 67.

**L2C dead-zone note.** `p_L2C` carries its full discriminative weight only when
right-stick velocity is non-zero (real-time aim-based games). In dead-zone stick
game genres — e.g. NCAA College Football 26, where 68/69 calibration sessions have
`right_stick_x = 128` throughout — the `StickImuCorrelationOracle` returns `None`
because the Pearson cross-correlation is undefined over a constant signal. The bridge
assigns `p_L2C = 0.5` (neutral prior), making the `0.10·p_L2C` term a fixed `+0.05`
offset carrying no discriminative information. The formula result remains bounded in
`[0,1]` and its weighted coefficients still sum to 1.0; the effective discriminative
formula reduces to four active signals for this game context. The `l2c_inactive` flag
is emitted per cycle in the bridge's PITL metadata and surfaced in the operator
dashboard to make this state explicit.

**PHG score weighting.**
PHG score deltas are weighted by `humanity_probability` (+50% bonus at p=1.0) and by
behavioral analysis: `delta × max(0.0, 1.0 − warmup×0.8 − burst×0.5)`. This makes
the on-chain PHG score reflect *quality* of human activity, not merely volume.

**On-chain credential lifecycle.**
`PHGCredential.sol` (soulbound, ERC-5192-inspired):
- Minted: `mintCredential(deviceId, nullifierHash, featureCommitment, humanityProbInt)`
  when a device has both a PHG checkpoint and a PITL session proof
- Active: credential contributes to `TournamentGateV3.isEligible()`
- Suspended: `suspend(deviceId, evidenceHash, durationSeconds)` — provisional
  revocation by bridge when `InsightSynthesizer` Mode 5 fires
- Reinstated: `reinstate(deviceId)` — automatic when device is labeled `cleared`

**PHGCredential suspension (Mode 5 enforcement).**
`InsightSynthesizer._synthesize_credential_enforcement()` runs each 6-hour cycle:
- For each device labeled `critical`: increment `consecutive_critical` counter
- If `consecutive_critical ≥ 2` AND has active credential AND not already suspended:
  compute suspension duration = `min(base_s × 2^(consecutive−2), max_s)`
  where `base_s = 604800` (7d), `max_s = 2419200` (28d)
- Call `chain.suspend_phg_credential(device_id, evidence_hash, duration_s)`
- Evidence hash = `SHA-256(f"{device_id}:{digest_id}")` — anchored to immutable digest row
- For each device labeled `cleared`: call `chain.reinstate_phg_credential()`
- For each device labeled `stable` or `warming`: reset `consecutive_critical` to 0

**Tournament gate hierarchy:**
- `TournamentGateV1` — minimum PHG cumulative score only
- `TournamentGateV2` — cumulative score AND recent velocity (time-qualified)
- `TournamentGateV3` — V2 gates AND `PHGCredential.isActive()` (suspension-aware)

**Biometric-anchored session continuity.**
A player who gets a new controller inherits their PHG history if:
`diagonal_mahalanobis(old_fingerprint, new_fingerprint) < 5.367`
(the continuity threshold is tighter than the 7.009 anomaly threshold; both re-derived from the N=74 calibration corpus in Phase 57). The PHG score
is transferred on-chain via `PHGRegistry.inheritScore()`; the source is zeroed to
prevent double-counting. Each device can be a continuity source and destination
exactly once.

### 7.5.5 Longitudinal Intelligence and Adaptive Feedback

**Behavioral archaeology.**
`BehavioralArchaeologist` performs longitudinal analysis of per-session PITL readings
using pure numpy (no LLM, always available):

*Warm-up attack detection:*
```
warmup_score = σ(drift_slope × humanity_slope × 20000 − 1.0)
```
where σ is sigmoid and slopes are computed by least-squares regression over record index
(invariant to adversarial timestamp manipulation). Stable human players:
warmup_score < 0.3. Coordinated warm-up (rising drift + rising humanity over sessions):
warmup_score > 0.7.

*Burst farming detection:*
```
burst_score = min(1.0, CV_inter_checkpoint / 2.0)
```
High gap-CV indicates bursty PHG checkpoint accumulation followed by inactivity.

*Biometric certificates (long-term):*
- `biometric_stability_cert`: mean drift velocity < 0.5 over last 20 sessions
- `l4_consistency_cert`: L4 distance CV < 0.3 over last 20 sessions

**Network correlation detection.**
`NetworkCorrelationDetector` builds an N×N pairwise biometric distance matrix across
all fingerprinted devices, then applies BFS DBSCAN (ε = 1.0, min_samples = 3).
Devices in clusters where `avg_intra_distance < ε/2` are flagged as potential bot farms:
genuine human players have idiosyncratic kinematic profiles; bots running the same
automation software cluster tightly in biometric space.

`farm_suspicion_score = min(1.0, (size−2)/5 + (ε−avg_d)/ε)`

**InsightSynthesizer (6-hour cycle).**
Six synthesis modes run independently each cycle:
- **Mode 1**: Rolling 24h/7d/30d window digests (bot_farm_count, high_risk_count,
  federated_count, anomaly_count, dominant_severity, top_5_devices, narrative text)
- **Mode 2**: Per-device risk trajectory labels via deterministic state machine:
  `_risk_label(bot, high_risk, fed, anomaly, prior) → {stable, warming, critical, cleared}`
- **Mode 3**: Federation topology fingerprints for clusters confirmed across ≥2 bridge instances
- **Mode 4**: Detection policy synthesis — translates risk labels into L4 threshold multipliers:
  `{critical: 0.70, warming: 0.85, stable: 1.00, cleared: 1.00}`
- **Mode 5**: PHGCredential enforcement (suspension / reinstatement) as described in §7.5.4
- **Mode 6**: Living calibration — exponential decay weighted threshold evolution from NOMINAL records (Phase 38)

**Adaptive L4 feedback loop.**
After `classify()` returns None (no hard cheat), the bridge checks the device's active
detection policy:
```python
if multiplier < 1.0:
    effective_thresh = 3.0 * multiplier
    if last_distance > effective_thresh:
        synthesize(0x30, confidence=min(255, 180 + int(excess*30)))
```
The loop is bounded (floor multiplier = 0.5 → max tightening 50%), reversible (label
change on next synthesis cycle auto-restores threshold), and non-fatal (policy lookup
always wrapped in bare `except Exception: pass`). Hard cheat codes `0x28/0x29/0x2A`
are never affected by this mechanism.

**Mode 6 — Living Calibration (Phase 38).** Every 6-hour synthesis cycle,
`InsightSynthesizer._synthesize_living_calibration()` recomputes L4 Mahalanobis thresholds
from the last 200 NOMINAL warmed records using exponential decay weighting (α=0.95, index
0 = most recent = weight 1.0):

```
weights[i] = 0.95^i / sum(0.95^j for j in range(n))
w_mean = sum(d[i] * weights[i])
w_std  = sqrt(sum(weights[i] * (d[i] - w_mean)^2))
candidate_anomaly    = w_mean + 3.0 * w_std
candidate_continuity = w_mean + 2.0 * w_std
```

Updates are bounded to ±15% per cycle to prevent oscillation, with a minimum threshold
floor of 3.0. Updates are applied live to the running config without a bridge restart.

Per-player profiles are computed for devices with ≥30 NOMINAL records:
- `personal_anomaly = min(w_mean + 3.0 * w_std, global_anomaly)` — tighter-than-global, enforced by `min()`
- `personal_continuity = min(w_mean + 2.0 * w_std, global_continuity)`
- Profiles persist in the `player_calibration_profiles` SQLite table

During L4 classification, `DualShockIntegration._get_effective_l4_threshold(device_id)`
returns `min(global_threshold, personal_threshold)`, fetching personal profiles from a
6-hour cache. Per-player thresholds can only tighten detection — they can never loosen it.

Calibration health is self-monitored every cycle: (1) stale data alert if newest NOMINAL
record is >48h old; (2) distribution shift alert if recent 20 records differ from historical
80 by >25% of mean. Both fire as `calibration_health_*` insights in the `protocol_insights`
table.

**SessionAdjudicator Ceremony Integrity Enrichment (Phase 73).**
Before each `claude-opus-4-6` ruling call, `SessionAdjudicator._process_ruling_request()`
enriches the evidence summary with on-chain ceremony provenance via
`VAPIZKProof.verify_ceremony_integrity()`. The result is fetched once per hour
per circuit name (module-level `_CEREMONY_CACHE`, TTL=3600s) to avoid a blocking
`eth_call` per device per adjudication cycle. Three enrichment outcomes are possible:

1. **Registry reachable, `on_chain_match=True`**: ceremony key is live and matches
   the on-chain commitment. No additional evidence flags are set. The full ceremony
   record (`contributor_count`, `beacon_block_number`) is stored in the
   `ceremony_integrity` JSON column of `agent_rulings`.

2. **Registry unreachable or RPC error**: `error` field is populated in the ceremony
   dict. The ruling proceeds normally — a transient network failure does not block
   adjudication. The error is stored in `ceremony_integrity` for audit.

3. **Registry reachable, `on_chain_match=False`, no error**: ceremony key mismatch
   without a network explanation. This indicates the verifying key may have been
   tampered or a ceremony re-run was not registered on-chain.
   `evidence_summary["ceremony_integrity_failed"] = True` is set, surfacing the
   mismatch directly to the LLM for ruling consideration.

This closes the trust chain from physical controller input to AI ruling: DualShock
Edge → PoAC 228B → SHA-256(164B) → Groth16 proof → MPC ceremony key (3 contributors)
→ CeremonyRegistry.sol → IoTeX block beacon → SessionAdjudicator ruling commitment.
Every link is independently verifiable on-chain.

**CeremonyWatchdogAgent (Phase 75).**
The 1-hour `_CEREMONY_CACHE` TTL creates a latency window: if a new ceremony key
is registered on-chain, the SessionAdjudicator will not detect it for up to 60 minutes.
`CeremonyWatchdogAgent` closes this window autonomously. It polls `CeremonyRegistry`
every 5 minutes via `VAPIZKProof.verify_ceremony_integrity()`, comparing the
`beacon_block_number + contributor_count` fingerprint against the last known state.
On detecting a change (key rotation):

1. `_sa_mod._CEREMONY_CACHE.clear()` — collapses the blind window from ≤60 min to
   ≤5 min. The next adjudication cycle will fetch fresh ceremony data.
2. `ceremony_key_rotated` agent event is emitted to `bridge_agent` — the operator
   is immediately notified via BridgeAgent's event stream.
3. Any `FLAG` ruling from the last 10 minutes receives a
   `ceremony_integrity_recheck_required` event — the operator is prompted to re-review
   these rulings under the new key context, since the ceremony data they were enriched
   with may now be stale.

The watchdog never raises — all errors are logged and polling continues.

**SessionAdjudicatorValidationAgent — Dry-Run Gate (Phase 75).**
Enabling live enforcement (`AGENT_DRY_RUN=false`) requires confidence that the LLM
adjudicator is calibrated correctly. `SessionAdjudicatorValidationAgent` provides the
first autonomous AI-validates-AI safety primitive in competitive gaming.

Every 5 minutes, the agent fetches `agent_rulings` entries not yet present in
`ruling_validation_log` (via `LEFT JOIN`) and cross-validates each LLM ruling against
the deterministic `_rule_fallback()` oracle — the same rule engine SessionAdjudicator
uses when the LLM is unavailable. A *divergence* is declared when:
- The LLM verdict differs from the fallback verdict **AND**
- `|llm_confidence − fallback_confidence| > VALIDATION_DIVERGENCE_THRESHOLD` (default 0.3)

The second condition prevents false divergences from semantically equivalent but
confidence-level-different rulings (e.g., both output FLAG but LLM at 0.4 vs fallback at 0.05).

The agent tracks a `consecutive_clean` counter: the length of the most recent
unbroken streak of non-divergent rulings. When `consecutive_clean ≥ VALIDATION_GATE_N`
(default 100), a `dry_run_gate_passed` agent event is emitted. `GET /agent/validation-gate`
(Tool #46) exposes this state to the operator in real time with a `recommended_action`
field. The gate is a one-time advisory — the operator must explicitly set
`AGENT_DRY_RUN=false` via `POST /agent/config`; enforcement does not activate automatically.

**RulingProvenanceAnchorAgent — AI Cognitive Audit Trail (Phase 76).**
VAPI is the first competitive gaming anti-cheat system to produce a cryptographically
verifiable audit trail for AI-generated rulings. `RulingProvenanceAnchorAgent` binds
three independent evidence streams into a single `provenance_hash` per ruling:

```
provenance_hash = SHA-256(
    commitment_hash_hex                          # Phase 66 ruling commitment (on-chain)
  + "|" + JSON({beacon_block_number, contributor_count}, sort_keys)  # Ceremony anchor
  + "|" + JSON(evidence_dict, sort_keys)        # Evidence presented to LLM
)
```

Canonical serialization rules (W1 mitigation — deterministic across Python versions):
`beacon_block_number` and `contributor_count` are cast to `int()` before serialization,
preventing float-vs-integer JSON divergence. All dicts use `sort_keys=True` and
`separators=(",", ":")`. Two independent implementations of this formula applied to the
same inputs will always produce the same hash.

This creates the first verifiable AI cognitive audit trail in competitive gaming: any third
party holding the ruling evidence, ceremony data, and commitment hash can recompute
`provenance_hash` and confirm it matches the stored anchor. The anchor is exposed via
`GET /agent/ruling-provenance/{ruling_id}` and BridgeAgent Tool #47. On-chain publication
(opt-in via `RULING_PROVENANCE_PUBLISH_ENABLED`) creates a second IoTeX trace per ruling
at the cost of ~0.02 IOTX gas per anchor.

**Validation Gate Rate-Tolerance — Phase 78.**
The Phase 75 dry-run gate required only `consecutive_clean ≥ VALIDATION_GATE_N` (default 100).
A subtle weakness remained: early operational divergences — accumulated before the gate threshold
is in sight — do not reset the consecutive counter but could still indicate systematic LLM
miscalibration. Phase 78 adds a complementary rate-based criterion evaluated over the
*trailing* `gate_n` window only:

```
divergence_rate = (divergences in trailing gate_n window) / window_size
gate_passed = (consecutive_clean ≥ gate_n) AND (divergence_rate ≤ VALIDATION_MAX_DIVERGENCE_RATE)
```

`VALIDATION_MAX_DIVERGENCE_RATE` defaults to `1.0` (no rate limit — full backward
compatibility). Operators who want a tighter gate can set e.g. `0.1` to require fewer than
10% divergences in the trailing window. Critically, both criteria are evaluated *only over
the trailing gate_n window* — pre-gate early divergences do not permanently block enforcement
activation (W1 mitigation). `GET /agent/validation-gate` (Tool #46) now exposes `divergence_rate`,
`divergence_rate_ok`, `max_divergence_rate`, and `window_size` in addition to the Phase 75
fields. When the rate criterion is exceeded, `recommended_action` specifically references
the divergence rate so the operator knows which condition is blocking gate passage.

### 7.5.6 AgentMessageBus + Live Mode Gate + Federated Threat Broadcast

**AgentMessageBus — Phase 79.** Phases 79–81 introduce a zero-latency in-process
pub/sub backbone that decouples agent communication from the 5-minute SQLite polling
cycle. `AgentMessageBus` maintains per-topic `asyncio.Queue` lists (maxsize=100); multiple
subscribers receive independent copies (fan-out); `QueueFull` is caught and logged without
raising. SQLite `agent_events` remains the durable audit log — the bus provides the fast
path only.

The architectural fix removes a fragile tight coupling: `CeremonyWatchdogAgent` previously
called `_sa_mod._CEREMONY_CACHE.clear()` via a direct module import. Phase 79 replaces this
with bus publication of `ceremony_key_rotated`; `SessionAdjudicator` subscribes and clears
its own cache — zero module-level coupling.

```
Publisher                   Event Type                  Subscribers
──────────────────────────────────────────────────────────────────
CeremonyWatchdogAgent   → ceremony_key_rotated       → SessionAdjudicator (cache clear)
SessionAdjudicatorVal.  → dry_run_gate_passed        → LiveModeActivationAgent
RulingEnforcementAgent  → ruling_block_committed     → FederationBroadcastAgent (Phase 80)
ClassJDetector          → class_j_high_risk_detected → SessionAdjudicator (Phase 82 reactive interrupt)
```

**LiveModeActivationAgent — Phase 79.** Evaluates a multi-condition readiness checklist
before any dry-run → live enforcement transition. All 5 conditions must pass simultaneously
for `ready_for_live_mode=True`:

1. `validation_gate_passed` — `consecutive_clean ≥ gate_n` AND `divergence_rate ≤ tolerance`
2. `no_recent_operator_overrides` — no manual `ruling_override` events in the trailing window
3. `no_recent_key_rotation` — no `ceremony_key_rotated` event in the last 24 hours
4. `divergence_rate_within_tolerance` — rate criterion from Phase 78
5. `consecutive_clean_met` — `consecutive_clean ≥ gate_n`

The agent is advisory only — it never activates live mode automatically. It emits a
`live_mode_candidate` advisory to `agent_events` when conditions pass. The operator must
explicitly set `AGENT_DRY_RUN=false` via `POST /agent/config`. `GET /agent/live-mode-status`
(Tool #48) exposes the full checklist as a `LiveModeStatus` response.

**FederationBroadcastAgent — Phase 80.** The first purely event-driven agent in the VAPI
fleet — no polling loop. Subscribes to `ruling_block_committed` on `AgentMessageBus` and
broadcasts BLOCK rulings to configured peer bridge instances in <100ms.

Propagation improvement:
```
BEFORE: BLOCK → SQLite event → poll (≤5 min) → broadcast → peer polls (≤5 min)
        Total: 10–15 minutes

AFTER:  BLOCK → bus.publish (<1ms) → broadcast (~100ms) → IoTeX block (~3s)
        Total: < 5 seconds  [150× faster]
```

W1 mitigation against network partitions: the signal is inserted into
`federation_threat_signals` (with `broadcast_at=NULL`) *before* the HTTP call. On startup,
`_recover_unbroadcast()` retries any unsent rows, preventing silent loss across crashes.
HMAC-SHA256 authentication (`X-Federation-HMAC` header) prevents unauthorized injection.
`UNIQUE` constraint on `commitment_hash` ensures replay attacks are rejected by the DB.

`FederatedThreatRegistry.sol` (Phase 80) provides on-chain immutability.
`isThreatSignaled(address deviceId)` is a pure view callable by any tournament gate
contract — same composability pattern as `VAPIProtocolLens.isFullyEligible()`.

**ClassJDetector — Phase 81.** GaussianHMM ML-bots (Class J) evade L4 Mahalanobis because
their feature distribution is fitted to human data. The discriminating signal is
*temporal entropy variance*: human psychomotor control produces rhythmically structured
state transitions (variance > 0.15); HMM sampling produces pathologically uniform
transitions (variance < 0.02).

`ClassJDetector` maintains a rolling deque of N=10 session entropy windows per device.
`_temporal_state_transition_entropy_variance` computes sample variance over the deque.
Risk classification: HIGH ≤ 0.05, MEDIUM ≤ 0.15, LOW > 0.15. On HIGH, publishes
`class_j_high_risk_detected` to the bus. **Phase 82 (Reactive Adjudication Interrupt)**
wires this signal to an immediate out-of-cycle LLM ruling, bypassing the 5-minute poll.

`SessionAdjudicator` enriches LLM evidence with `class_j_ml_bot_risk` and
`class_j_entropy_variance` before each ruling. When `risk_level == "HIGH"`, sets
`ml_bot_candidate=True` in evidence, increasing BLOCK confidence for ML-bot candidates.

**Phase 82 — Reactive Adjudication Interrupt.** `SessionAdjudicator` subscribes to
`class_j_high_risk_detected` on `AgentMessageBus`. On receipt, `_adjudicate_device_directly()`
assembles evidence (enrollment, trajectory, recent records, Class J entropy context) and
calls `claude-opus-4-6` immediately — without waiting for the next 5-minute poll cycle.
A W1-mitigation token bucket (`_ReactiveAdjudicationBucket`, default max 2 calls/60s)
prevents bus-flooding from exhausting the Anthropic rate limit; suppressed calls are logged
to `reactive_adjudication_log` with `was_deferred=1`. After ruling, `reactive_ruling_completed`
is published to the bus and the ruling is forwarded to `RulingEnforcementAgent` for streak
escalation and on-chain commit.

End-to-end latency: Class J HIGH detected → bus publish (< 1ms) → reactive LLM ruling
(~2–5s) → enforcement → federation broadcast (< 100ms) → on-chain IoTeX block (~3s).
**Total: < 10 seconds.** Prior polling path: 15–25 minutes.

The reactive interrupt log is accessible via `GET /agent/reactive-adjudication-log`
and Tool #51 `get_reactive_adjudication_status` on `BridgeAgent`.

Previous federated cross-instance threat correlation (Phase 34): `FederationBus` exchanged
privacy-preserving cluster fingerprints. `FederatedThreatRegistry.sol` has been updated
to the Phase 80 per-ruling design; `isThreatSignaled()` replaces the `MultiVenueConfirmed`
pattern.

### 7.5.7 AgentSupervisor — Fleet Health Monitor

**Phase 83** introduces `AgentSupervisor` — the ninth autonomous agent, responsible
for monitoring the health of all other eight agents in the fleet. This is the
foundational component for an AGaaS (Agentic as a Service) SLA: a tournament operator
cannot reasonably trust automated rulings from a fleet of unknown operational health.

`AgentSupervisor` polls SQLite activity signals every 5 minutes. For each of the 9
registered agents, it queries the agent's primary activity table and reports:

| Status | Meaning |
|--------|---------|
| `HEALTHY` | Activity written within `SUPERVISOR_STALE_THRESHOLD_MINUTES` (default 15) |
| `STALE` | No activity written within the threshold window |
| `UNKNOWN` | No rows exist in the agent's table (agent never ran or store empty) |
| `ZOMBIE` | Rows exist but to 0 distinct devices — agent looping on no-op writes (W1) |

**Fleet-level health** aggregates per-agent status:
- `ALL_HEALTHY` — all 9 agents HEALTHY
- `DEGRADED` — 1–2 agents non-HEALTHY
- `CRITICAL` — ≥3 agents non-HEALTHY, or either core agent (`session_adjudicator`,
  `ruling_enforcement_agent`) is STALE

The `ZOMBIE` status implements the W1 mitigation from Phase 83 design: timestamp-alone
liveness is insufficient because a misconfigured agent can write garbage rows (non-zero
count, non-null last_active_at) while processing no real events. `distinct_devices > 0`
confirms genuine multi-device processing.

Fleet health is exposed via `GET /agent/supervisor-status` and Tool #52
`get_agent_supervisor_status` on `BridgeAgent`. `AgentSupervisor` also publishes
`agent_health_report` to `AgentMessageBus` after each cycle, enabling future notification
agents to alert operators on fleet degradation without polling.

### 7.5.8 Live Mode Gate Completion + Adjudication Warm-Up

**Phase 84** closes the dry-run → live-mode activation arc with two new primitives and the
first on-chain cryptographic proof that an AI enforcement fleet achieved autonomous
self-calibration.

**`GateAttestationAnchor.sol`** is a new IoTeX L1 contract that accepts
`attestation_hash = SHA-256(consecutive_clean || gate_n || divergence_rate || timestamp_ns)`.
This hash binds the fleet's gate readiness state — how many consecutive non-divergent
adjudications were accumulated, under what divergence rate tolerance, at what threshold —
immutably to IoTeX testnet. The first `recordGateAttestation()` transaction is the
first cryptographic proof of autonomous AI fleet self-calibration in competitive gaming.
Anti-replay is enforced by unique constraint on `attestationHash`.

**`AdjudicationWarmUpRunner`** allows the operator to fire a pre-activation dry-run batch
against the N most recently active devices before setting `AGENT_DRY_RUN=false`. The
`WarmUpReport` exposes `llm_available: bool` (W1 mitigation) — if `False`, the Anthropic
client is missing and warm-up ran via `_rule_fallback` only. The operator must confirm
`llm_available=true` before any live ruling is issued.

**`GET /agent/gate-readiness`** is a composite endpoint aggregating three signals:

| Signal | Source | Role |
|--------|--------|------|
| `validation_gate` | `store.get_validation_gate_status()` | consecutive_clean / gate_n progress |
| `fleet_health` | `AgentSupervisor.check_fleet_health()` | ALL_HEALTHY / DEGRADED / CRITICAL |
| `gate_attestations_count` | `gate_attestations` SQLite table | on-chain proof count |

`overall_ready = gate_passed AND fleet_health not in (CRITICAL, UNKNOWN)`. Tool #53
`get_gate_readiness` exposes the same composite to the BridgeAgent LLM for natural-language
queries. Post-Phase-84, the operator has a single authoritative primitive to answer:
*"Is this fleet ready for live enforcement?"*

**End-to-end gate activation sequence:**
```
1. Run POST /agent/warm-up  → confirm llm_available=true, completed > 0
2. Check GET /agent/gate-readiness → confirm overall_ready=true
3. SET AGENT_DRY_RUN=false via POST /agent/config
4. Record attestation_hash on GateAttestationAnchor.sol → irreversible on-chain proof
```

**Phase 87** completes the on-chain publication path. `AdjudicationWarmUpRunner.run_warm_up(chain=chain_client)` now accepts an optional chain client: after the adjudication batch it calls `_anchor_gate_on_chain()`, which reads the current validation gate state, computes
`attestation_hash = compute_gate_attestation_hash(consecutive_clean, gate_n, divergence_rate, timestamp_ns)`,
calls `chain.record_gate_attestation_on_chain()`, and on success stores the row in `gate_attestations` with the confirmed `on_chain_tx`. The `WarmUpReport` exposes two new fields: `on_chain_published: bool` and `on_chain_tx: str | None`.

W1 invariant: the `attestation_hash_hex` is computed once and passed identically to both the chain call and the SQLite insert — it is never recomputed between the two, ensuring the on-chain record and the SQLite row are cryptographically identical regardless of any config drift.

`chain.py` method `record_gate_attestation_on_chain()` converts `divergence_rate` to `uint32` millis (`int(rate * 1000)`) and `timestamp_ns` to `uint64` seconds to match `GateAttestationAnchor.sol`'s integer-only storage.

**GateAttestationAnchor.sol LIVE: `0xA39d00D3FF8C579840Fa02C01Adf06162630a449`** (IoTeX testnet, deployed Phase 87, operator verified).

Bridge: 1282→1288 (+6 Phase 84 tests) → 1296→1300 (+4 Phase 87 tests). Hardhat: 404→408 (+4 Phase 84 tests). Contracts: 32 ALL LIVE.

**Phase 88** adds the Adjudication Campaign Tracker and Divergence Instrumentation layer. The `ruling_validation_log` table gains a `divergence_reason TEXT` column populated by the new `_extract_divergence_fields(evidence)` function in `session_adjudicator_validator.py`. When a divergence is recorded, `_extract_divergence_fields` captures which non-nominal evidence signals drove the LLM away from `_rule_fallback`: `hard_cheat_codes`, `advisory_codes`, `class_j_ml_bot_risk` (when ≠ LOW), `ml_bot_candidate`, `ceremony_integrity_failed`, `enrollment_status` (when ≠ eligible), and `risk_label`. Fully nominal evidence returns `"{}"` — the expected baseline for real human sessions.

`store.get_campaign_status(gate_n, max_divergence_rate)` provides a single-call campaign snapshot: `consecutive_clean`, `progress_pct` (consecutive_clean / gate_n × 100), `estimated_sessions_to_gate` (⌈remaining / (1 − divergence_rate)⌉), `verdict_breakdown`, `divergence_breakdown` (aggregated non-nominal fields across all diverged sessions), `recent_sessions` (last 10 rows), and a human-readable `campaign_note`. All fields are derived atomically from the same `get_validation_summary()` snapshot (W1 mitigation: no drift between `consecutive_clean` and divergence counts).

The campaign tracker is exposed as `GET /agent/campaign-status` and as Tool #55 `get_campaign_status` on `BridgeAgent`, giving operators and the LLM a single endpoint for campaign health at any point in the N=100 validation run.

Bridge: 1300→1306 (+6 Phase 88 tests).

**Phase 89** introduces the `ProtocolIntelligenceAgent` — the first unified protocol health synthesizer in VAPI. Rather than requiring operators to consult six separate endpoints (validation gate, fleet health, corpus status, Class J assessments, shadow log, triage report), Phase 89 collapses all streams into a single `protocol_health_score` (0–100). The formula is: `100 × (0.35·gate_progress + 0.25·fleet_health + 0.20·divergence_clarity + 0.10·corpus_pass + 0.10·class_j_confidence)`, plus up to +5 bonus from Phase 90 `shadow_pass_score` and +5 from Phase 91 `triage_confidence_score` (capped at 100). `ready_for_live_mode = score ≥ 85 AND gate_passed AND fleet ≠ CRITICAL/UNKNOWN`. The `bottleneck` field names the lowest-scoring component, giving operators a single actionable target. Reports are persisted to `protocol_intelligence_reports` and exposed via `GET /agent/protocol-intelligence` and Tool #56 `get_protocol_intelligence`.

**Phase 90** closes the enforcement validation loop with Live Mode Shadow Enforcement. When `ENFORCEMENT_SHADOW_MODE=true`, BLOCK verdicts from `RulingEnforcementAgent` are logged to `shadow_enforcement_log` instead of calling `PHGCredential.suspend()`. Each row records `device_id`, `ruling_id`, `commitment_hash`, `would_have_suspended=1`, `duration_s` (24h default, 7d for confirmed warmup attackers), and `warmup_attack_score`. Operators review `GET /agent/shadow-enforcement-log` to validate the false-positive rate before setting `ENFORCEMENT_SHADOW_MODE=false` for real enforcement. The `shadow_pass_score` (fraction of shadow blocks where warmup_attack_score < 0.7) feeds into Phase 89's `protocol_health_score` as a bonus component, creating a synergistic readiness signal: shadow mode data automatically improves the protocol intelligence score as the system accumulates clean BLOCK evidence.

**Phase 91** adds the `DivergenceTriageAgent` — cross-session adversarial pattern detection built on Phase 88's `divergence_reason` data. Every 5 minutes, the agent queries `ruling_validation_log` for devices with recorded divergences and classifies each into three pattern tiers: **ML-bot cluster** (≥2 sessions with `class_j_ml_bot_risk=HIGH`), **cheat cluster** (≥1 session with non-empty `hard_cheat_codes`), and **enrollment anomaly** (≥3 sessions with `enrollment_status≠eligible`). Devices crossing any threshold are flagged `escalated=1` as immediate SessionAdjudicator ruling candidates. The `triage_confidence_score` (fraction of triage reports with no escalation) feeds into Phase 89's `protocol_health_score`, completing the synergistic chain: Phase 88 instruments divergence → Phase 91 classifies patterns → Phase 89 synthesizes health → operator sees single readiness number.

Bridge: 1306→1330 (+8 Phase 89 + +8 Phase 90 + +8 Phase 91 tests).

**Phase 92** introduces the `LiveModeActivationPipeline` — a tamper-evident audit trail for enforcement activation decisions. Every 5 minutes, the pipeline reads Phase 89's `ready_for_live_mode` and records the result to `live_mode_activation_log` with the full `protocol_health_score`, `bottleneck`, and `blocking_conditions`. When an operator is ready to activate live enforcement, `POST /agent/request-activation` records their intent in the audit log before they set `AGENT_DRY_RUN=false`. This creates a verifiable sequence: Phase 89 report (readiness evidence) → activation log entry (operator intent) → GateAttestationAnchor.sol on-chain record (cryptographic proof) — a full tamper-evident activation audit trail across SQLite and IoTeX L1.

**Phase 93** adds the Protocol Health Score dashboard panel to the frontend. The `useProtocolIntelligence` hook polls `GET /agent/protocol-intelligence` every 30 seconds and renders a `ProtocolHealthPanel` with a live circular score gauge (0–100, color-coded green/orange/red), per-component percentage bars (gate_progress, fleet_health, divergence_clarity, corpus_pass, class_j_confidence), a `ready_for_live_mode` READY/NOT READY indicator, and a triage escalation count badge from `GET /agent/triage-report`. Operators can see the complete enforcement readiness state at a glance without querying eight separate endpoints.

**Phase 94** closes the reactive triage loop: `DivergenceTriageAgent` already publishes `divergence_pattern_detected` to the bus when a device crosses an escalation threshold. Phase 94 adds a `_listen_triage_bus()` subscriber in `SessionAdjudicator` that fires an immediate out-of-cycle `_adjudicate_device_directly()` ruling when a triage escalation arrives. A per-device `_TriageRateBucket` (token bucket, 1/hour default, 1000-entry LRU cap to prevent memory leaks from synthetic device_ids) ensures the reactive path cannot be flooded. Every escalation attempt — whether it fires a ruling or is rate-limited — is logged to `escalation_ruling_log` (`was_deferred=1` for rate-limited entries). The full Phase 91→94 chain latency is: divergence detected → triage pattern classified → bus publish (<1ms) → reactive adjudication (<10s) — collapsing the previous 10-minute polling gap to under 15 seconds end-to-end.

Bridge: 1330→1344 (+8 Phase 92 + 0 Phase 93 + 6 Phase 94 tests).

**Phase 95** introduces the Activation Audit Verifier — the final link in the enforcement readiness chain. `store.get_activation_audit_summary()` cross-references two independent data sources: (1) `live_mode_activation_log` (Phase 92), specifically the timestamp of the first `ready_for_live_mode=True` entry, and (2) `gate_attestations` (Phase 84/87), specifically the count and latest timestamp of on-chain gate attestations. `audit_valid=True` is returned only when all three conditions hold: a `ready_for_live_mode=True` entry exists, an on-chain gate attestation exists, and the ready-check timestamp precedes the attestation timestamp — verifying that the protocol was independently assessed as ready before the cryptographic anchor was created. A chronological violation (`attestation_at < first_ready_check_at`) returns `audit_valid=False` with an explicit `predates` message.

The `GET /agent/activation-audit` endpoint (Tool #61 `get_activation_audit`) exposes this summary to operators and CI pipelines. `VAPITournamentGate.verify_activation_audit()` (SDK Phase 95) wraps the endpoint into `ActivationAuditResult` — a fail-safe dataclass that never raises. Tournament CI pipelines can call `gate.verify_activation_audit().audit_valid` as a pre-condition gate for setting `AGENT_DRY_RUN=false`, creating a complete programmable enforcement readiness certificate.

The full Phase 89→95 readiness chain is: **Phase 89** synthesizes health score → **Phase 90** validates shadow enforcement rate → **Phase 91** classifies divergence patterns → **Phase 92** logs activation intent → **Phase 87** anchors on-chain → **Phase 95** cross-verifies chronological sequence. Every link is independently queryable; `audit_valid=True` confirms all are intact.

Bridge: 1344→1350 (+6 Phase 95 tests). SDK: 73→77 (+4 Phase 95 SDK tests).

**Phase 96** introduces the Enforcement Readiness Certificate (ERC) — and fixes the Phase 95 W1 bug. The W1 bug: `get_activation_audit_summary()` queried ALL `gate_attestations` without filtering by timestamp, meaning pre-readiness infrastructure test anchors (Phase 84/87 testing) could permanently produce `audit_valid=False` even when the protocol legitimately reached readiness. The fix: `WHERE created_at >= first_ready_at` — only attestations after the first readiness event count toward `audit_valid`. The ERC is the first portable, operator-signed cryptographic proof of AI enforcement readiness. `POST /agent/enforcement-certificate` computes `audit_hash = SHA-256(canonical JSON of audit fields)` and `hmac_sig = HMAC-SHA256(audit_hash, operator_api_key)`, persists the cert with a configurable TTL (default 24h), and returns the signed artifact. `GET /agent/enforcement-certificate` retrieves the latest cert with `is_expired` advisory. `VAPITournamentGate.create_enforcement_certificate()` and `.get_enforcement_certificate()` wrap both endpoints (SDK Phase 96, never raise, return `EnforcementReadinessCertificate` dataclass). Tournament operators can verify the ERC without VAPI infrastructure: recompute `hmac_sig = HMAC-SHA256(audit_hash, shared_key)` and compare. Tool #62 `get_enforcement_certificate`. Bridge: 1350→1358 (+8 tests). SDK: 77→81 (+4 tests).

**Phase 97** introduces the Gated Live Mode Transition — the first enforcement gate that makes `AGENT_DRY_RUN=false` physically conditional on protocol readiness. `POST /agent/config?dry_run=false` now evaluates three conditions atomically before accepting the transition: (1) `gate_passed=True` — the consecutive_clean gate has been reached and the divergence rate is within tolerance; (2) `cert_valid=True` — a non-expired EnforcementReadinessCertificate (Phase 96) with `audit_valid=True` exists; (3) `audit_valid=True` — the Phase 95 chronological invariant is satisfied. Any condition failure returns HTTP 422 with a `blocking` array identifying which conditions failed. On approval, `cfg.agent_dry_run_mode = False` and a `live_mode_enabled` event is published to `AgentMessageBus` — `SessionAdjudicator` and `RulingEnforcementAgent` each subscribe via `_listen_live_mode_bus()` and shift mode within <1ms, without waiting for the next poll cycle. `dry_run=True` is always accepted (restore path). Every attempt — approved or blocked — is logged to `live_mode_guard_log` with `operator_key_hash` (first 16 chars of SHA-256 of api_key), enabling full operator accountability. `GET /agent/live-mode-guard` returns the audit log. Tool #63 `get_live_mode_guard_log`. Bridge: 1358→1364 (+6 tests).

**Phase 98** introduces the Epistemic Consensus Protocol — the first formal multi-agent consensus gate for irreversible enforcement decisions in VAPI. Before any BLOCK verdict commits to enforcement action, `SessionAdjudicator._epistemic_consensus()` queries three independent agents and computes a weighted agreement score: `ClassJDetector` (0.40 weight, HIGH=1.0/MEDIUM=0.5/LOW=0.0), `DivergenceTriageAgent` (0.40, escalated=1.0/0.0), `AgentSupervisor` (0.20, ALL_HEALTHY=1.0/DEGRADED=0.5/CRITICAL=0.0). If `consensus_score < threshold` (default 0.60, configurable via `EPISTEMIC_CONSENSUS_THRESHOLD`), BLOCK is downgraded to HOLD — a false-positive protection layer that requires independent corroboration before irreversible suspension. Every consensus decision is persisted to `epistemic_consensus_log` with the full score breakdown. The gate fires in both the standard adjudication path (`_process_ruling_request`) and the reactive/warm-up path (`_adjudicate_device_directly`). The design ensures that a single LLM ruling cannot unilaterally block a device without corroborating signals from the ML-bot detector and the divergence classifier. `GET /agent/epistemic-consensus-log` exposes the audit trail; `downgraded_count` tracks how often the protection layer fired. Tool #64 `get_epistemic_consensus_log`. Bridge: 1364→1372 (+8 tests).

**Phase 99A** lays the AGaaS (Agentic-as-a-Service) economic foundation: `VAPIToken.sol` (ERC-20, 1B VAPI max supply, `completeTGE()` irrevocably seals minting — gated until separation ratio > 1.0 confirmed), `VAPIOperatorRegistry.sol` (10,000 VAPI minimum stake, 50% slash-burn / 50% claimant, 30-day deregister cooldown, ReentrancyGuard CEI pattern), `VAPIHardwareCertRegistry.sol` (hardware profiles keyed by profileHash, certLevel 1=controller / 2=controller+GSR, `isCertified()` is pure view — the first hardware-level DePIN composability primitive in competitive gaming: tournament contracts gate hardware with a single `require(certRegistry.isCertified(profileHash))`). Bridge-side: `operator_registrations` SQLite table + `insert_operator_registration` + `get_operator_status`; `GET /agent/operator-status`; Tool #65 `get_operator_status`. Config: `vapi_token_address`, `operator_registry_address`, `hardware_cert_registry_address`. Hardhat: 408→420 (+12). Bridge: 1372→1378 (+6). openapi: v3.0.0-phase99a.

### 7.5.9 BridgeAgent and Alert Dispatch

`BridgeAgent` (`claude-sonnet-4-6`) exposes natural-language operator intelligence
through 40 deterministic tool bindings over bridge data, a Server-Sent Events streaming
endpoint (`GET /operator/agent/stream`), and an autonomous `react()` path that
interprets `BIOMETRIC_ANOMALY` and `TEMPORAL_ANOMALY` events without operator input.
All high-frequency detection (L2–L5) remains deterministic; the LLM operates only at
the human-paced query layer where synthesis latency is acceptable. Session history
persists across restarts in SQLite. `AlertRouter` complements the agent by polling
`protocol_insights` every 30 seconds and dispatching events meeting the configured
severity threshold to an operator webhook (Slack, PagerDuty, or generic JSON) via
stdlib `urllib`, with no new dependencies and non-fatal failure handling. See Appendix B
for the complete tool catalogue and streaming interface specification.

**Phase 50 proactive capabilities (20 tools total):** Three new queryable tools extend
BridgeAgent's read surface: `get_session_narrative` (deterministic 3-sentence data-derived
session summary — inference, drift context, and 5-session trend); `compare_device_fingerprints`
(Mahalanobis distance between two devices' calibration-profile EMA mean vectors with
always-present separation-ratio-0.362 caveat); and `get_calibration_agent_status` (peer
`CalibrationIntelligenceAgent` state — pending flags, last threshold_history entry, current
thresholds vs Phase 46 anchors). Two autonomous behaviors complete the feedback loop:
`check_threshold_drift()` is called by InsightSynthesizer Mode 6 on each calibration cycle
to write `threshold_drift_alert` or `threshold_stable` protocol insights and emit
`threshold_updated` agent_events when drift exceeds 10% from Phase 46 anchors; `react()`
now additionally writes `recalibration_needed` events to the `agent_events` table when
`drift_velocity > 0.6` is detected on a `BIOMETRIC_ANOMALY` inference, routing them to
`CalibrationIntelligenceAgent` for autonomous personal recalibration.

### 7.5.8 CalibrationIntelligenceAgent Peer (Phase 50)

`CalibrationIntelligenceAgent` (`claude-sonnet-4-6`) is a dedicated autonomous peer that
coordinates with BridgeAgent via the `agent_events` SQLite coordination table rather than
shared function calls, forming an asynchronous detection-calibration feedback loop. The
agent exposes six specialist tools: `get_threshold_history` (annotates each history row
with drift percentage from Phase 46 anchors); `get_feature_variance_report` (aggregates
`baseline_std` statistics across all `player_calibration_profiles`, flags near-zero-std
devices as potential zero-variance contamination); `get_zero_variance_features` (static
known list — `trigger_resistance_change_rate` index 0 and `touch_position_variance`
index 10 — with fix-path annotations); `get_separation_analysis` (static Phase 49 result:
ratio 0.362, LOO 42.2%, P1/P2 indistinguishable); `get_pending_recalibration_flags` (reads
unconsumed `agent_events` targeting this agent); and `trigger_recalibration` (personal or
global, with mandatory safety enforcement).

**Critical invariant:** `trigger_recalibration` enforces `min()` unconditionally —
if the newly computed personal threshold exceeds the current threshold, the call returns
`{"error": "refused: new threshold would loosen (new > current)"}` and no update is
applied. Global recalibration is blocked if `get_last_global_recalibration_time()` shows
a run within the last 7 days, preventing rapid oscillation.

`run_event_consumer()` is an async background task polling every 30 minutes. On each
cycle it reads pending `recalibration_needed` events from BridgeAgent, calls
`trigger_recalibration(personal, device_id)` for each, marks events consumed, and writes
`threshold_updated` reply events back to BridgeAgent. It also runs `get_separation_analysis()`
and writes a `separation_alert` insight to `protocol_insights` if the interperson ratio
drops below 0.4. The three new SQLite tables (`agent_events`, `threshold_history`,
`calibration_agent_sessions`) and two new operator API endpoints (`POST /calibration/agent`,
`GET /calibration/stream`) support this architecture.

### 7.5.9 DePIN Extensibility Validation

The IoTeX Pebble Tracker (nRF9160 SiP, ARM Cortex-M33 @ 64 MHz, CryptoCell-310)
validates protocol extensibility. The same 228-byte PoAC wire format, the same three-layer
agent architecture, and the same on-chain contract stack operate unchanged. Only the
sensor commitment schema differs (schema v1, environmental: BME680 temperature/VOC,
ICM-42605 IMU, TSL2572 lux, GPS) versus the DualShock Edge (schema v2, kinematic/haptic).

This confirms VAPI's core design claim: the verification mechanism is device-agnostic;
the detection surface is device-specific.

### 7.5.10 DataCuratorAgent and Data Sovereignty Layer (Phase 69/70)

Phase 69 introduces the Data Sovereignty Layer — a complete DePIN economics stack built
on top of the Phase 68 enforcement infrastructure. The layer comprises six new smart
contracts and a Python background agent operating as a fifth parallel task in the bridge
asyncio event loop.

**DataSovereigntyRegistry.sol** records an immutable on-chain data sovereignty pledge for
each device (timestamp, schema version, jurisdiction hash). Once registered, the pledge
cannot be modified or deleted — any device's historical data licensing rights can be
verified against the timestamp-anchored record. Three licensing tiers are defined:
MANUFACTURER (L1, raw sensor export), DEVELOPER (L2, feature-processed export), and
GAMER (L3, anonymized aggregate only).

**Native VAPI Oracles.** Three oracle contracts — HumanityOracle, RulingOracle, and
PassportOracle — bridge the off-chain PITL detection stack to any on-chain consumer.
Each oracle exposes a `getState(bytes32 deviceId)` view method that any IoTeX contract
can call without permission: tournaments, DAOs, insurers, or third-party validators. All
three oracles are updated by the DataCuratorAgent each poll cycle (default: every 5
minutes) when oracle publication is enabled.

**VAPIRewardDistributor.sol** distributes DePIN token rewards using a stacked multiplier
model: passport held (1.5×) → enrollment complete (2.0×) → clean streak (2.5×) → MPC
verified (1.25×) → tournament gate passed (3.0×). The multipliers apply sequentially —
a device satisfying all five conditions receives approximately 15.75× the base award.
Device eligibility is gated: a device must hold a PHGCredential and not be suspended.

**VAPIDataMarketplace.sol** implements three-tier data licensing: 70% of purchase proceeds
go to the device pool (proportional to eligibility_score), 30% to the protocol treasury.
All marketplace state is stored on-chain; licenses are non-transferable per IoTeX ERC-1155
semantics.

**DataCuratorAgent** is a Python asyncio background agent (started in the main event loop
via Phase 70 agent wiring) that polls the SQLite store every 5 minutes to:
1. Classify all device sessions into a 7-class taxonomy (SESSION_DATA, BIOMETRIC_DATA,
   BEHAVIORAL_DATA, ANOMALY_DATA, CALIBRATION_DATA, TOURNAMENT_DATA, AUDIT_DATA)
2. Build a `data_lineage` provenance record for each session (quality_score 0.0–1.0,
   curator_note, data_type)
3. Compute token eligibility (nominal_sessions, clean_streak, multiplier stack) and write
   to the `token_eligibility` table
4. Publish oracle updates on-chain when `curator_oracle_publish=True`

**Phase 70 Agent Wiring.** Prior to Phase 70, DataCuratorAgent, SessionAdjudicator, and
RulingEnforcementAgent existed in code but were not started in `main.py`. Phase 70 wires
all three into the bridge asyncio event loop as independently supervised tasks, each with
a `_task_done_handler` CRITICAL callback ensuring a crash in one agent does not kill the
others. DataCuratorAgent always starts (self-guarded via `curator_enabled`);
SessionAdjudicator starts when `operator_api_key` is configured; RulingEnforcementAgent
starts when `ruling_enforcement_enabled=True`.

**VAPIProtocolLens.sol** (Phase 70) collapses the five-call pattern (HumanityOracle +
RulingOracle + PassportOracle + VAPIRewardDistributor + PHGCredential) required by any
tournament integration into a single pure-view eth_call returning a `DeviceProtocolState`
struct. The `isFullyEligible(bytes32 deviceId)` function returns a single boolean:
`isNominal && isEligible && passportOnChain`. All oracle subcalls are wrapped in try/catch
— a single oracle outage returns a safe zero-value default rather than reverting the lens
call. VAPIProtocolLens has zero storage state; gas cost is purely the four static calls
to subordinate contracts.

**VAPIGovernanceTimelock.sol** (Phase 70) interposes a mandatory 48-hour delay before any
operator transition takes effect on Phase 69 contracts (see §9.7 for governance model).

### 7.6 SDK v3.0.0 Tournament Operator Interface (Phase 85)

Phase 85 advances the VAPI Python SDK from v2.0.0-phase64 to v3.0.0-phase85, adding three
operator-facing classes that bridge the gap between the bridge service and external tournament
infrastructure. All three classes are fail-safe: they never raise to the caller, and each
returns a structured result object with an `error` field on failure.

**VAPITournamentGate** wraps `GET /agent/gate-readiness` and returns a `GateReadinessResult`
struct. The struct surfaces the composite readiness picture: `overall_ready` (bool),
`dry_run_active` (bool), `gate_attestations_count` (int), and nested `validation_gate` and
`fleet_health` dicts matching the bridge API schema. The `is_ready()` convenience method
collapses this to a single boolean, suitable for use as a pre-submission gate in tournament
CI pipelines. This class, combined with `GateAttestationAnchor.sol` (Phase 84), constitutes
the first programmatic AI Enforcement Readiness Certificate callable from external code.

**VAPICeremonyAudit** wraps `VAPIZKProof.verify_ceremony_integrity()` behind a clean
`CeremonyAuditResult` dataclass. It is intended for tournament operators who need to verify
that the ZK proving key in use has not been substituted since the MPC ceremony was anchored
on IoTeX. On `on_chain_match=False`, the operator should treat all VAPI rulings from that
bridge instance as unverifiable until the ceremony is re-run.

**VAPIRulingStream** is an async generator that yields `RulingStreamEvent` objects from the
`GET /operator/agent/stream` SSE endpoint. W1 mitigation: the stream tracks `Last-Event-ID`
across reconnects, sending it as an HTTP header on each new connection so that the bridge
can replay missed events after a TCP partition. Reconnects use exponential back-off (1–60 s).
The generator exits cleanly on `asyncio.CancelledError`, making it safe to cancel from any
asyncio task.

```python
# Tournament operator CI example
gate = VAPITournamentGate("http://bridge:8000", api_key="op-key")
result = gate.check_gate_readiness()
if not result.overall_ready:
    sys.exit(f"Bridge not gate-ready: {result.validation_gate}")

# Async ruling consumer
stream = VAPIRulingStream("http://bridge:8000", api_key="op-key")
async for event in stream.listen():
    if event.event_type == "ruling" and event.data.get("verdict") == "BLOCK":
        revoke_tournament_access(event.data["device_id"])
```

### 7.9 Security Hardening (Phase 58)

Phase 58 closes four software-only security gaps identified in the post-Phase-57 gap
assessment. No new contracts, ZK ceremony, or hardware are required.

**Operator Endpoint Authentication.** The `/operator/passport` and
`/operator/passport/issue` HTTP endpoints previously accepted any request without
authentication. Phase 58 adds an `x-api-key` header guard: requests with a missing or
incorrect key receive HTTP 401 (unauthorized); requests arriving when `operator_api_key`
is unconfigured receive HTTP 503 (graceful degradation, not a hard crash). The auth check
is performed before JSON body parsing to avoid reading attacker-controlled data on rejected
requests.

**Sliding-Window Rate Limiter.** A per-IP sliding-window rate limiter (60-second window,
configurable via `rate_limit_per_minute`, default 60) protects both operator endpoints
from denial-of-service through repeated requests. The limiter uses lazy eviction (stale
bucket entries are pruned on the next request after window expiry) — correct for
single-process asyncio deployments. The architecture preserves a Redis upgrade path for
multi-process production deployments.

**Operator Audit Log.** A new `operator_audit_log` SQLite table captures every operator
endpoint interaction: endpoint, device_id (truncated), API key hash (SHA-256 prefix, never
raw key), source IP, HTTP status code, and outcome. Two new store methods —
`log_operator_action()` and `get_operator_audit_log()` — provide append-only write and
filtered read access. This log is the Phase 58B prerequisite: it establishes an immutable
audit trail for all nullifier submissions before the on-chain enforcement layer is deployed.

**ZK Inference Code Binding (Partial — Phase 58A).** An `inference_code` column is added
to `pitl_session_proofs` via idempotent migration. This persists the inference byte
alongside every nullifier, enabling Phase 58B to enforce that nullifiers submitted
on-chain carry NOMINAL (0x20) inference codes. The full fix (Phase 58B) requires
`PITLSessionRegistry v2` and testnet IOTX; the Phase 58A column costs nothing and unblocks
58B immediately.

**BridgeAgent Expansion (Tools #24–27).** Four new operator intelligence tools are added:
- `analyze_threshold_impact` — computes session flip counts if L4 threshold shifts by Δ%;
  read-only, never modifies thresholds
- `predict_evasion_cost` — returns structured evasion analysis for known attack classes
  G/H/I (validated, N=5 each) and J/K (hypothesized)
- `get_anomaly_trend` — rolling L4/humanity statistics with IMPROVING/STABLE/DEGRADING trend
- `generate_incident_report` — full operator audit dump per device: records, inference
  breakdown, ioID, passport, calibration, and recent insights

Phase 58 adds 16 tests (bridge 956 → 972).

### §7.10 My Controller — Cryptographically-Anchored Physics Digital Twin (Phase 59)

Phase 59A introduces the "My Controller" page — a separate React + Three.js application
(`frontend/controller-twin.html`) that renders a physics-driven 3D model of the owner's
DualShock Edge CFI-ZCP1, with every visual state hash-linked to an on-chain PoAC record.

**Architecture:** Separate Vite entry point (lazy-loaded, no 3D overhead in the main dashboard
bundle). Three.js procedural geometry driven by Rapier WASM physics. IMU data from `/ws/frames`
(20 Hz) drives shell rotation and micro-tremor. Trigger depression, stick tilt, and humanity
aura color respond in real time to `/ws/twin/{device_id}` — a new device-scoped WebSocket that
merges physics frames and PITL record overlays into a single per-device stream.

**Novel backend endpoints:**
- `GET /controller/twin/{device_id}` — aggregated snapshot: calibration profile, biometric
  fingerprint EMA, ioID DID, tournament passport, anomaly trend, last 20 PoAC chain lock points
- `GET /controller/twin/{device_id}/chain` — chain lock timeline (up to 200 records) for the
  scrubber UI
- `WS /ws/twin/{device_id}` — device-scoped fusion stream (`{"type":"frame"/"record","data":{...}}`)
- `BiometricFeatureExtractor.get_ibi_snapshot()` — exposes raw IBI deques (Cross/L2/R2/Triangle)
  for the Biometric Heartbeat visualization
- BridgeAgent tool #28: `get_controller_twin_data` — returns the full twin snapshot via agent API

**Signature visuals:**
- *IBI Biometric Heartbeat* — 2D canvas showing per-button inter-button-interval bars against a
  constant-period bot reference grid. The organic irregular rhythm of human motor cortex is
  visible against the mechanical grid of macro-scripted input. This is the VAPI-exclusive proof
  that no screenshot or replay can replicate.
- *PoAC DNA Helix* — DNA double-helix of chain lock points, colored by inference code (green
  NOMINAL, amber BIOMETRIC_ANOMALY, red HARD_CHEAT). Every node is a `record_hash` on IoTeX L1.
- *ProofAnchorPanel* — ioID DID, ZK tournament passport status, live L4 distance, record_hash
  prefix, operator audit log queries, and the separation ratio disclaimer
  ("ratio 0.362 — biometric transplant attack not blocked").
- *Chain Timeline Scrubber* — bottom bar of colored 10×20px tiles; click any tile to freeze the
  3D view at that chain lock point for forensic inspection.

**Key invariant:** The 3D visualization is read-only. L4 thresholds are displayed from the live
calibrated value (`snap.calibration.anomaly_threshold`), never written. Wire format unchanged.
IBI raw sequences are not stored to DB — only the `press_timing_jitter_variance` scalar persists.

Phase 59 adds 16 tests (bridge 972 → 988).

### §7.11 My Controller Enhanced Visualization (Phase 60A)

Phase 60A extends the My Controller page with four additional visualization panels, all
frontend-only with zero backend changes. The twin page gains a 4-tab left panel:
`HEARTBEAT | RADAR | L5 RHYTHM | BIOM MAP`.

**BiometricRadar** — a 12-spoke canvas radar chart drawn from `snap.biometric_fingerprint.mean_json`
(the per-player EMA mean vector). Each spoke represents one of the 12 biometric features, normalized
to its expected human range (`BIO_NORM[12]`). Structurally-zero features (indices 0 and 10) render
as empty spokes, making the exclusion from L4 computation visually explicit. The polygon shape is
unique per player — a geometric representation of the player's biometric fingerprint. Bots with
near-zero tremor and zero jitter collapse to a near-origin polygon, immediately distinguishable from
a human player's irregular, spread-out profile.

**L5RhythmOverlay** — visualizes the TemporalRhythmOracle output in real time. An entropy gauge
bar (0–3 bits) shows IPI Shannon entropy against the 1.0 bit threshold marker. Per-button CV bars
(R2 > CROSS > L2 > TRIANGLE, matching the ncaa_cfb_26 priority order) display inter-press-interval
coefficient of variation against the 0.08 adversarial floor. Quantization detection flag and L5
humanity component are shown inline. A bot's mechanical timing collapses CV bars to the left and
entropy to zero, making the oracle's judgment visible without requiring statistical training.

**BiometricScatter** — a 2D feature-space cross-section using micro_tremor_accel_variance (index 3,
X axis) and press_timing_jitter_variance (index 11, Y axis) — the two features with strongest
bot-vs-human discrimination in the active feature set. A dashed bot zone anchors near the origin
(macro-scripted bots have near-zero tremor variance and near-zero IBI jitter). A 2σ human corpus
ellipse, centered from N=74 hardware session statistics (L4 dist_mean=2.083, dist_std=1.642),
shows where authentic DualShock Edge play clusters. The player's live fingerprint dot is placed
from `mean_json[3]` and `mean_json[11]`. The mandatory disclaimer ("separation ratio 0.362 —
intra-player only") is printed in the corner.

**ProofShareQR** — a modal triggered by "SHARE PROOF ↗" in the ProofAnchorPanel. Generates a
QR code (via `qrcode` npm package, orange on void-black) pointing to the IoTeX testnet explorer
for the current `tx_hash` chain record, or to the twin page URL as fallback. Includes the full
`record_hash` (SHA-256(164B body)), humanity probability, and L4 distance. A copy-to-clipboard
button enables sharing the twin page URL directly.

Phase 60A adds zero new tests (pure frontend). Bridge count: 988 unchanged.

### §7.12 Session Replay + Feature History Scatter (Phase 61)

Phase 61 transforms the My Controller twin page from a live-only view into a forensic replay
tool, completing the "navigable proof archive" concept.

**Session Replay (Track A).** Every PoAC record commit is now paired with a `frame_checkpoint`
row in SQLite. A rolling `deque(maxlen=60)` (`_replay_ring`) accumulates up to 60 downsampled
(~20 Hz) InputSnapshot frames per second. On each `_dispatch()` call, `store_frame_checkpoint`
snapshots the ring (INSERT OR IGNORE — idempotent on record_hash unique index) and stores the
compressed frame window alongside the record hash. The `frame_checkpoints` table has a FOREIGN
KEY to `records(record_hash)` ensuring every checkpoint maps to a committed PoAC record.

Three new REST endpoints serve replay data:
- `GET /controller/twin/{device_id}/replay?record_hash=<hash>` — returns the frame array for a specific record (up to 60 frames)
- `GET /controller/twin/{device_id}/checkpoints` — returns the set of record_hashes with stored frame checkpoints
- `GET /controller/twin/{device_id}/features` — returns per-record L4 feature vectors for scatter history

BridgeAgent tool #29 `get_session_replay` exposes the same data to the conversational agent.

On the frontend, the `useReplayMode` hook loads the checkpoint set on mount, and when a chain
timeline tile is clicked it fetches the frame array and plays it back at 20 Hz (50ms interval)
by advancing `replayIdx`. The `currentReplayFrame` overrides live frames fed to `Controller3D`,
making the 3D model re-enact the exact controller state that produced the on-chain record.
Chain tiles with available checkpoints show a cyan border (REPLAYABLE indicator). A status bar
above the timeline shows `▶ REPLAY n/total` with a progress bar and STOP button.

**Feature History Scatter (Track B).** `BiometricScatter` now accepts a `history` prop (from
`useFeatureHistory` hook fetching the `/features` endpoint). Per-record cyan dots (semi-transparent,
radius 2.5px) plot `features[3]` vs `features[11]` — the device's own actual measured feature
vectors from the DB, replacing the theoretical 2σ ellipse as the empirical evidence. The count
of plotted records is shown in the corner. The mandatory separation ratio 0.362 disclaimer remains.

**Track C (Contract Deployments).** VAPIioIDRegistry and PITLTournamentPassport deployments
were attempted but blocked by insufficient testnet IOTX (0.43 IOTX remaining after prior
deployments). Deployment scripts are confirmed correct; blocked pending wallet top-up.

Phase 61 adds 12 tests. Bridge count: 988 → **1000**.

### §7.13 Player Enrollment + ZK Inference Code Binding (Phase 62)

Phase 62 closes two long-standing gaps: the missing enrollment state machine (Track A)
and the incomplete ZK inference code binding (Track B, Gap #1).

**Track A — Player Enrollment Ceremony.**
The entire credential stack (PHGRegistry, PHGCredential, TournamentGateV3) was deployed
and functional, but the bridge had no enrollment state machine. `EnrollmentManager`
(new `bridge/vapi_bridge/enrollment_manager.py`) runs after each PITL session proof:
once a device accumulates `enrollment_min_sessions=10` NOMINAL sessions with
`avg_humanity >= 0.60`, it automatically calls `chain.mint_phg_credential()` to mint
the soulbound PHGCredential (ERC-5192). The enrollment progress is tracked in the new
`device_enrollments` SQLite table. A new `GET /enrollment/status/{device_id}` REST
endpoint exposes progress to operators; BridgeAgent tool #30 (`get_enrollment_status`)
exposes it to the LLM agent. The mint is idempotent: `has_phg_credential()` is checked
before minting to prevent double-mint on restart.

**Track B — ZK Inference Code Binding.**
`PitlSessionProof.circom` previously constrained `inferenceResult ∉ {0x28, 0x29, 0x2A}`
(C2) but did NOT bind `inferenceResult` to any committed body field. A corrupt bridge
could generate a valid proof with `inferenceCode=0x20` (NOMINAL) while the PoAC body
byte 128 encoded `0x28` (CHEAT). Phase 62 adds:

- **Private input:** `inferenceCodeFromBody` — PoAC body byte 128, prover-supplied.
- **C1 (modified):** `featureCommitment = Poseidon(8)(scaledFeatures[0..6], inferenceCodeFromBody)` — the inference code is now committed into the feature commitment.
- **C3 (new):** `inferenceResult === inferenceCodeFromBody` — binds the public inference result to the private body value.

For an honest bridge, `inferenceResult == inferenceCodeFromBody` always holds.
A corrupt bridge that changes `inferenceResult` without changing `inferenceCodeFromBody`
violates C3 (proof generation fails). A bridge that changes both produces a
`featureCommitment` inconsistent with the raw PoAC body — **forensically detectable**.
`nPublic` remains 5 (public input count unchanged). The ceremony was re-run; new
`.wasm` + `.zkey` + `verification_key.json` (with nPublic=5) replace existing artifacts.
`PITLSessionRegistryV2.sol` and `deploy-pitl-registry-v2.js` are ready; deployment
pending IOTX wallet replenishment.

Phase 62 adds 26 tests. Bridge count: 1000 → **1026**.

### §7.14 L6b Neuromuscular Reflex Layer (Phase 63)

Phase 63 introduces L6b — the first **reactive involuntary probe** in the PITL stack. Every prior layer (L2–L6) observes inputs the player consciously produces. L6b probes the involuntary nervous system.

**Physical mechanism.** A sub-perceptual 10ms haptic pulse (amplitude 60/255 ≈ 24% — below conscious sensation threshold on CFI-ZCP1) is delivered via the DualShock Edge R2 adaptive trigger. The spinal stretch reflex arc triggers an involuntary grip-tightening within 80–280ms, measured as an accel-magnitude impulse in the IMU ring buffer. Interrupt-driven bots respond at 0–15ms (OS scheduling latency). The player cannot consciously prepare for a below-threshold stimulus — behavioral mimicry is impossible without hardware loop-back.

**Classification buckets (uncalibrated, literature-derived):**
- BOT: latency 0–15ms (interrupt-driven response)
- INCONCLUSIVE: 15–80ms or >280ms
- HUMAN: 80–280ms (spinal reflex + cortical loop)
- NO_RESPONSE: no accel impulse above threshold in 350ms window → neutral prior

**Humanity formula update.** Phase 63 adds a 4-way conditional:
- Baseline (no L6, no L6b): `0.28·L4 + 0.27·L5 + 0.20·E4 + 0.15·L2B + 0.10·L2C`
- L6 active only (unchanged): `0.23·L4 + 0.22·L5 + 0.15·E4 + 0.15·L6 + 0.15·L2B + 0.10·L2C`
- L6b active only: `0.25·L4 + 0.24·L5 + 0.17·E4 + 0.14·L6b + 0.12·L2B + 0.08·L2C`
- Both L6 + L6b: `0.20·L4 + 0.18·L5 + 0.12·E4 + 0.14·L6 + 0.14·L6b + 0.12·L2B + 0.10·L2C`

All branches sum to 1.00. `L6B_ENABLED=false` by default. L6b formula branch activates only after `probe_count >= 1`.

**Implementation.** New `controller/l6b_reflex_analyzer.py` (`L6bReflexResult`, `L6bReflexAnalyzer`). Profile 8 (`L6B_PROBE`) added to `l6_challenge_profiles.py` and excluded from the L6 active rotation. New `l6b_probe_log` SQLite table. BridgeAgent tool #31 (`get_reflex_baseline`). 5 new config fields.

**Calibration status:** Thresholds use literature values (80–280ms neuromotor loop). Hardware calibration pending: once L6B_ENABLED=true sessions are captured, `scripts/l6b_threshold_calibrator.py` will derive empirical bounds from the `l6b_probe_log` corpus.

Phase 63 adds 26 tests. Bridge count: 1026 → **1056**.

---

## 8. Evaluation

### 8.1 Cryptographic Overhead

**Table 4: Per-Operation Latency on CryptoCell-310 (nRF9160)**

| Operation | Latency |
|-----------|---------|
| SHA-256 (96 B sensor buffer) | 0.8 ms |
| SHA-256 (1.5 KB world model) | 2.1 ms |
| SHA-256 (model manifest) | 1.4 ms |
| ECDSA-P256 sign | 6.2 ms |
| NVS write (36 B) | 1.8 ms |
| **Total PoAC generation** | **12.3 ms** |

These figures are estimated via cycle-accurate emulation. Real-hardware validation
on a physical nRF9160 DK is future work. The 12.3 ms total overhead is 0.041% of
the DePIN 30-second reflexive cycle budget.

### 8.2 On-Chain Gas Costs

| Operation | Gas per record |
|-----------|---------------|
| `verifyPoAC` (individual) | 148,230 |
| `verifyPoACBatch` (batch of 10) | 81,245 |
| `PHGRegistry.commitCheckpoint` | ~72,000 |
| `PHGCredential.mintCredential` | ~110,000 |
| `PHGCredential.suspend` | ~85,000 |
| `FederatedThreatRegistry.reportCluster` | ~65,000 |

At IoTeX's typical gas price of 1 Gwei and IOTX at $0.03, a batch of 10 verifications
costs approximately $0.00024. The P256 precompile at `0x0100` is essential: without it,
P256 verification in pure Solidity requires ~1.2M gas per signature.

### 8.3 Anti-Cheat Detection — Real Hardware Adversarial Validation

Detection benchmarks were produced by running six deterministic attack transforms against
55 real 1000 Hz DualShock Edge sessions (N=50 human baseline, 2026-03-02).
Each adversarial session is a reproducible transformation of a real captured session
targeting the specific physical property each PITL layer relies on.

**Table 5: Adversarial Detection Matrix — Real Hardware (DualShock Edge CFI-ZCP1, 1000 Hz)**

| Attack Type | N | L2 Det% | L4 Det% | L5 Det% | Any% | Notes |
|-------------|---|---------|---------|---------|------|-------|
| Replay (chain-level) | 5 | 0% | 20% | 0% | 20% | Chain attack — PITL not the right layer; on-chain replay prevention handles this |
| IMU-stripped injection | 10 | **100%** | 0% | 0% | **100%** | L2 gravity signal + active-frame gyro; zeroed accel always detectable |
| Perfect-timing macro | 10 | 50% | 30% | **100%** | **100%** | L5 CV=0.0054, entropy=0.22 bits — far below human baseline |
| Biometric transplant | 5 | 0% | 0% | 0% | 0% | Single-person dataset: chimeric fingerprint within one person's Mahalanobis ball |
| Gradual warmup (bot→human) | 10 | 20% | 0% | 60% | 60% | Sessions 1–6 (α ≤ 0.56) detected; sessions 7–10 reach near-human territory |
| Quantization-masked bot | 15 | 67% | 0% | **100%** | **100%** | Mean quant_score=0.898; entropy collapses to ~0 bits despite timing jitter |

**Table 6: L5 Human Baseline — Hardware Calibrated (N=69 Sessions, 3 Players, DualShock Edge)**

| Metric | Human Mean | Human 10th Pct | Threshold | Safety Margin |
|--------|-----------|----------------|-----------|---------------|
| CV (std/mean) | 1.184 | 0.789 | < 0.08 | **9.9× vs 10th pct** |
| Shannon entropy | 2.085 bits | 1.231 bits | < 1.0 bits | **1.2× vs 10th pct** |
| Quant score | 0.590 | 0.423 | > 0.55 | — (2/3 rule prevents FP) |

Human quant score (mean 0.59) slightly exceeds the threshold because humans also time
button presses to game-loop frame boundaries. The 2/3-signal requirement prevents false
positives since CV and entropy remain far on the human side.

**Table 7: L4 Biometric — N=74 Production Thresholds (12-feature space, Phase 57)**

| Scenario | Mahalanobis d | L4 Fires? |
|----------|--------------|-----------|
| Same human, different session (hw_* baseline, N=69, 3 players) | mean 2.07, max ~7.0 | No (threshold **7.009**) |
| Genuine biometric outlier (2/69 sessions) | > 7.009 | Yes — expected at 3σ |
| Bot farm (transplant, same person) | Within personal ball | No — requires multi-person dataset |

**Human false positive rate: 2.9% (2/69 sessions).** Two sessions exceed the mean+3σ threshold —
expected at the 3σ level. Threshold re-derived from the N=74 calibration corpus in Phase 57
(threshold = mean+3σ = 7.009; continuity = mean+2σ = 5.367). N=69 baseline sessions span
Players 1–3 (hw_005–hw_073); hw_074–hw_078 added in Phase 46.

**Stationary control baseline.** A 30-second session with the controller untouched on a desk
(sessions/adversarial/stationary\_control\_001.json, 999.7 Hz) confirms:
- PITL result: NOMINAL
- Gyro std at rest: 1.3–1.5 LSB; P95 gyro magnitude: 9.54 LSB
- Mean accel magnitude: ~2150 LSB (gravity); **14,000× injection detection margin**

**Known limitation.** The biometric transplant attack (0% detection in the N=50 single-player
adversarial suite) requires a multi-person calibration dataset to overcome. The updated N=69
calibration corpus now spans 3 distinct players (hw_005–hw_073); inter-person Mahalanobis
separation has been computed (separation ratio 0.362 — see §8.6 and §10.7). The result is
honest: L4 does not currently separate players with the current feature set and calibration
corpus.

**L6 Active Challenge-Response.** The L6 layer is implemented and unit-tested
(§7.5.2). Live adversarial hardware benchmarking of L6 — running randomized
challenge profiles against a physically connected DualShock Edge with real human
play and software-injection replay — has not yet been performed. Human response
baseline statistics (onset latency distribution, grip-variance distribution) are
required before L6 detection thresholds can be empirically calibrated. This is the
immediate next hardware validation task (§10.6).

**Attack-to-layer mapping.** Not every adversarial category is handled by PITL layers
L2–L6. The adversarial benchmark results must be read with the correct layer assignment:

- **Replay (20% PITL hit) — chain-level attack handled by L1/PoAC, not PITL.** Replay
  is correctly detected by the PoAC monotonic counter and hash-linkage integrity check
  (L1). The 20% "detection" recorded in L4 during replay tests is statistical noise from
  biometric features slightly deviating from the enrolled baseline when frames are
  reordered — not a reliable signal. PITL layers L2–L6 are not designed for replay
  detection and should not be cited as replay mitigations.

- **Warmup (60%) — fundamental limitation of any gradual-onset attack.** Sessions 7–10
  of the warmup attack are constructed to interpolate toward human behavior. A
  sufficiently patient attacker who degrades metrics slowly enough will eventually
  produce a session indistinguishable from legitimate skill improvement.
  BehavioralArchaeologist catches early-to-mid progression (sessions 1–6 reliably),
  but the attacker "graduates" as the session window saturates with near-human samples.
  This is a known limitation of any session-scoped behavioral detector. The explicit
  defense-in-depth is Mode 5 credential suspension (§7.5.4), which operates across
  sessions rather than within a single session, flagging progressive drift over time.

- **Transplant (0%) — architectural constraint, not a detection failure.** With a
  single player's calibration data, every session falls within the same Mahalanobis
  ball by construction. Transplant detection requires multi-person calibration: a second
  player with 5–10 sessions would allow the system to demonstrate either inter-person
  separation (validating the biometric fingerprint) or reveal that the feature
  set needs augmentation. The inter-person separation result for the N=69 3-player corpus
  (ratio 0.362) is documented in §10.7 rather than as a detection failure.

### 8.4 DualShock Edge Hardware Validation

28 hardware tests run on a physical Sony DualSense Edge (CFI-ZCP1) in five suites
provide real-device empirical data for the key PITL detection surfaces. The test session
used a CFI-ZCP1 connected via USB-C to a Windows 11 machine; `hidapi` enumerated the
device at VID=0x054C, PID=0x0DF2, interface 3 (usage\_page=1, usage=5).

**Table 8: Live Hardware Measurements — DualShock Edge CFI-ZCP1 (USB mode)**

| Measurement | Value | Spec / Expected | Test |
|-------------|-------|----------------|------|
| USB polling rate | **1002 Hz** | 1000 Hz ± 15% | `test_1_polling_rate_1khz` |
| Accel magnitude (stationary, 1g ref) | **8267 LSB** | ~8192 LSB (1g) | `test_7_micro_tremor_accel_variance_present` |
| Accel magnitude variance (held, natural grip) | **278,239 LSB²** | > 0 (injects: 0) | `test_7_micro_tremor_accel_variance_present` |
| Gyro noise std (active play) | **201.65 LSB** | > 0.02 LSB threshold | `test_5_imu_stick_coupling_nonzero` |
| Gyro noise std (stationary) | **< 50 LSB** | < 50 LSB (pass) | `test_imu_noise_floor` |
| Injection detection margin | **14,000×** above stationary-control baseline | — | Derived from stationary\_control\_001.json |
| Report counter violations | **0 / 200 reports** | 0 | `test_2_report_counter_monotonic` |
| Sensor commitment v2 (SHA-256) | **Deterministic** | Required | `test_5_sensor_commitment_v2_preimage` |
| Distinct commitments (distinct reports) | **4 / 4** | All distinct | `test_5_sensor_commitment_v2_preimage` |
| Timestamp field (bytes 12–14) | **49/49 advancing** | > 80% | `test_4_timestamp_field_advances` |

The **14,000× injection detection margin** is derived from the stationary control baseline
(sessions/adversarial/stationary_control_001.json): mean accel magnitude ~2150 LSB (gravity
present) versus software injection which zeros all three accel channels (magnitude ≈ 0).
The gyro dimension provides a separate **10,000× margin**: software injection produces gyro
std ≈ 0 LSB; the physical device at rest produces < 50 LSB and in active play > 200 LSB.
Any threshold between 0.02 LSB and 50 LSB provides reliable separation with zero false
positives on real hardware.

The **278,239 LSB² accel variance** measured during normal hand-held use (no deliberate
motion) demonstrates that the micro-tremor signal exists at meaningful amplitude in
natural play conditions — not merely during controlled vibration or aggressive movement.
This validates micro-tremor as a practical biometric feature for everyday detection, not
a laboratory artifact.

Report-counter monotonicity confirms 200 consecutive reports with zero gaps or violations
on Windows 11 USBHID. The polling rate of 1002 Hz confirms 1 kHz resolution for the
50-report feature extraction window assumed throughout the L4/L5 pipeline.

**Test suite structure (28 tests):**

| File | Tests | Type |
|------|-------|------|
| `test_dualshock_live.py` | 6 | HID enumeration, format, axes, IMU floor, commitment |
| `test_pitl_live.py` | 5 | PITL transport smoke (report volume, chain, features) |
| `test_dualshock_report_timing.py` | 5 | 1 kHz rate, counter, gaps, timestamp, wrap |
| `test_dualshock_biometric.py` | 7 | L4 fusion, stable-track quarantine, micro-tremor, IMU-stick coupling, trigger onset velocity |
| `test_dualshock_adaptive_triggers.py` | 5 | Trigger ADC range, effect byte readback, release return, independence, sensor\_commitment\_v2 |

All tests include embedded step-by-step physical procedures (timing guidance, action
prompts) so that operators without code expertise can execute the full hardware validation
protocol. Tests are gated behind `@pytest.mark.hardware` and excluded from CI by default.

**N=69 Biometric Calibration (2026-03-07, 3 Players).** Following the 28-test hardware
validation, 69 sessions across 3 distinct players were captured and used to calibrate all PITL
thresholds empirically. The calibration corpus spans:
- Player 1 (self): hw_005–hw_044 (38 sessions)
- Player 2: hw_045–hw_058 (14 sessions)
- Player 3: hw_059–hw_073 (12 sessions; 5 excluded for anomalous polling)

Phase 17 extended the L4 feature space from 7 to 11 features (adding tremor FFT 8–12 Hz
band power/peak and touchpad biometrics). Phase 46 replaced `touchpad_active_fraction`
(structurally zero across all N=69 sessions) with `accel_magnitude_spectral_entropy`
(active across all N=69 sessions; zero-fraction 0%). Phase 57 added `press_timing_jitter_variance`
(index 11, normalised IBI variance) bringing the total to 12 features. Two features remain
structurally zero across all N=69 sessions (trigger_resistance_change_rate, touch_position_variance)
and are auto-excluded from calibration.

| Threshold | Design-time estimate | Hardware-calibrated (N=74, Phase 46) |
|-----------|---------------------|---------------------------------------|
| L4 anomaly (ANOMALY_THRESHOLD) | 3.0 | **7.009** (mean+3σ, 12-feature, Phase 57; Phase 17: 7.019) |
| L4 continuity (CONTINUITY_THRESHOLD) | 2.0 | **5.367** (mean+2σ, 12-feature, Phase 57; Phase 17: 5.369) |
| L5 entropy | 1.5 bits | **1.0 bits** (human 10th pct: 1.231 bits) |
| L5 CV | 0.08 | 0.08 (unchanged; human mean: 1.184, 10th pct: 0.789) |
| L2B coupled_fraction | — | **0.55** (human mean: 0.786; 64/69 sessions with ≥15 presses) |
| L2C max_causal_corr | — | **0.15** fixed threshold (0/69 false positives after abs() fix) |

Calibration confidence: **HIGH** (N=69, 3 players). Values encoded as defaults in
`controller/tinyml_biometric_fusion.py` and overridable via environment variables.
See `calibration_profile.json` for the full calibration record.

The adversarial validation suite (`scripts/run_adversarial_validation.py`) subsequently
validated these thresholds against 71 adversarial sessions across 9 attack types
(56 sessions A–F deterministic transforms; 15 sessions G–I professional/white-box attacks,
Phase 48) — see §8.3 for the full detection matrix and §9.5 for Phase 48 findings.

### 8.5 Test Coverage Summary

| Suite | Count | Scope |
|-------|-------|-------|
| Bridge pytest | **2942** | Full pipeline through Phase 110 (Phases 38–70 incremental coverage above); Phase 99 token stack + VHP soulbound; Phase 109A ioSwarm bridge adapter; Phase 109B–238 see CLAUDE.md NOTE log; Phase O3-ZKBA-TRACK1 (sidecar + ZKBA primitive C2 + deterministic compiler + GIC Continuity Ledger C3 + MCP tools + SDK C4 + PV-CI invariants C5 + bridge HTTP endpoints) |
| Autoresearch pytest | **7** | MetaLearner FSCA wiring + UnifiedWIFCorpus deduplication |
| SDK pytest | **550** | Self-verifying client SDK including VAPIEnrollment, VAPIZKProof, VAPIAgent, VAPIDataCurator, VAPIBiometricGovernance, VAPIProtocolCoherence, VAPIFleetReadinessRoot, VAPIDraftReview, VAPICurator, VAPIZKBA (Phase O3-ZKBA-TRACK1 C4 + endpoint round-trip) |
| Hardhat | **528** | 49 LIVE Solidity contracts on IoTeX testnet (4690) including Phase 221 ProtocolCoherenceRegistry, Phase 222 VAPIBiometricGovernance, Phase 237-ZK-SEPPROOF Groth16VerifierZKSepProof + ZKSepProofVerifier wrapper, Phase 238 VAPIDataMarketplaceListings; Phase O3-ZKBA-TRACK1 ships no new contracts (Track 1 wallet-free) |
| Hardware | 37 | Physical DualShock Edge (gated `@pytest.mark.hardware`, excluded from CI) |
| E2E | 14 | End-to-end simulation (requires Hardhat node; excluded from CI) |
| PV-CI | **69** | Protocol invariant gate (15 protocol roots + 3 OZ ladders + 3 Operator-Agent + 3 ZKBA + others); per-commit `python scripts/vapi_invariant_gate.py` allowlist check |
| **Total** | **~4,076** | *~4,025 in CI (excluding 37 hardware, 14 E2E counted separately)* |

**Authoritative phase log:** CLAUDE.md NOTE entries (top-of-file, append-only) carry the authoritative phase-by-phase delta record from Phase 102 onward. The whitepaper §9 catalogue covers protocol-architectural phases through Phase 109A in detail; §9.27 + §9.28 below summarize the Phase 109B → Phase 238 → Phase O3-ZKBA-TRACK1 arc at the level appropriate for an external reader, deferring per-phase test-count deltas and per-PR engineering history to CLAUDE.md.

Note: Phase 17 added 45 new bridge tests: 18 for `l2b_imu_press_correlation` (L2B
IMU-button causal latency oracle), 15 for `l2c_stick_imu_correlation` (L2C stick-IMU
cross-correlation oracle), and 12 for `calibration_agent` (auto-calibration threshold agent).
The +33 L6 tests cover `l6_challenge_profiles`, `l6_trigger_driver`, `l6_response_analyzer`,
and L6 integration including Attack G adversarial detection. Phase 38 added tests for Mode 6
living calibration and the `get_calibration_status` BridgeAgent tool.

### 8.6 What VAPI Does Not Yet Validate

The following detection capabilities are implemented but lack empirical calibration, or
are explicitly not yet implemented:

**L6 human response baseline.** L6 Active Physical Challenge-Response is fully implemented
(33 tests, 8 trigger profiles). Threshold parameters (onset_threshold_ms, settle_threshold_ms,
classification weights) are derived from biomechanical priors, not measured distributions on
real DualShock Edge players. False positive and false negative rates are unknown. L6 is
disabled by default (`L6_CHALLENGES_ENABLED=false`) and must not be used as a primary
tournament gate until N≥50 real challenge sessions are collected and analyzed.

**Inter-person biometric identification.** L4 is an intra-player anomaly detector (separation
ratio 0.362, below the 1.0 threshold required for reliable identification). It detects
deviation from a player's own baseline; it does not identify *who* the player is. This is
correct positioning for the current feature set: two of eleven features are structurally
zero across all N=69 calibration sessions (trigger_resistance_change_rate,
touch_position_variance) after Phase 46 replaced `touchpad_active_fraction` with the active
`accel_magnitude_spectral_entropy`. The honest interpretation: L4 catches
sessions that are anomalous for *this device's history*, not sessions that belong to *a
different person*.

**ZK inference code binding.** The Groth16 circuit has a constraint on inferenceResult
range, but the on-chain verifier receives pub[2]=0, making this constraint trivially
satisfied. The inference code in PoAC records is committed off-chain only.

**Professional bot software.** No commercial aimbot software, ML-driven bot inputs, or
game-specific macro tools have been used as labeled adversarial data. Phase 48 (§9.5)
introduces three white-box adversarial attack classes simulating a threshold-aware adversary
with full knowledge of published thresholds and access to HID emulation hardware. These
attacks are fully synthetic (no real bot software required) and confirm that the 9-feature
L4 Mahalanobis is robust to threshold-aware single-feature tuning. Real hardware bots (aimbot
software, ML-driven inputs) remain untested labeled adversarial data.

**Bluetooth transport calibration.** BT transport is implemented (transport-aware parsing,
L0 presence verifier, separate config thresholds) but all N=69 calibration sessions were
captured via USB. L4/L5 thresholds carry no empirical grounding for Bluetooth polling rates
(125–250 Hz).

**Bridge as trusted intermediary.** Despite ZK constraints on the biometric pipeline, the
bridge remains operationally trusted: it controls which records are submitted on-chain, can
withhold records (detectable via chain gaps), and computes humanity scores without
end-to-end ZK coverage of the raw→feature transformation. The ZK proof constrains
computation *given features*; it does not verify that the features were computed correctly
from raw sensor data.

---

## 9. Security and Threat Model Analysis

### 9.1 Threat Mitigations

**T1 — Record fabrication.** ECDSA-P256 private key resides in CryptoCell-310 PSA
persistent secure storage (key ID `0x00010001`), accessible only from the Secure partition.
The on-chain verifier checks signatures via the P256 precompile.

**T2 — Replay attacks.** Monotonic counter (persisted in NVS flash) strictly increases
across power cycles. `PoACVerifier` enforces `ctr > chainState.lastCounter`. ZK PITL
proofs use `nullifierHash = Poseidon(deviceIdHash, epoch)` — binding proofs to one
device × one epoch.

**T3 — Selective omission.** Hash-chain linkage makes omission detectable: a gap in
counter values signals omission even without the hash link. The bridge can withhold
records but cannot produce an alternative chain without the signing key.

**T4 — Synthetic sensor injection.** PoAC constrains but does not fully prevent this
attack. The adaptive trigger resistance state byte (read from controller ADC, not writable
from host HID stack, §7.5.1) narrows the viable injection surface. The L4 biometric
stable-track fingerprint and the L5 timing distribution provide behavioral constraints:
an adversary must maintain consistent synthetic input across a 32-observation world model,
produce plausible classification outputs, and sustain deception across the L4 stable-track
update window without triggering drift velocity alerts.

**L6 additional mitigation.** Active physical challenge-response (§7.5.2 L6) adds
an orthogonal attack surface: software injection cannot produce human-biomechanical
grip adjustment responses (onset latency 40–300 ms, accel variance > 0) in reaction
to resistance profiles it cannot sense. An injector that also observes and attempts
to synthesize L6 responses must simultaneously produce plausible IMU variance (L2),
consistent biometric kinematics (L4), and non-degenerate timing distributions (L5) —
a compound constraint that dramatically narrows the viable attack surface.

**T5 — Fraudulent bounty claims.** `submitEvidence()` requires a PoAC record hash
in `PoACVerifier.verifiedRecords`, location within geographic zone, and timestamp within
active period.

**T6 — Warm-up attack.** `BehavioralArchaeologist` detects rising drift-slope +
humanity-slope correlation via `σ(drift_slope × humanity_slope × 20000 − 1.0)`.
The sigmoid scoring penalizes coordinated improvement without penalizing natural skill
development (which does not produce the characteristic dual-rising slope). Even if a
warm-up attack succeeds in accumulating PHG score, Mode 5 enforcement (§7.5.4) can
suspend the credential when consecutive critical windows accumulate.

**T7 — Distributed bot farm.** `FederationBus` (§7.5.6) detects clusters confirmed
by ≥2 independent bridge instances. Even if each shard sees too few devices to form
a local cluster, the cross-confirmed hash triggers a `federated_cluster` alert and
optional on-chain anchoring.

### 9.2 Trust Assumptions

| Component | Trust Assumption | Failure Mode |
|-----------|-----------------|--------------|
| CryptoCell-310 | Hardware not physically tampered | Key extraction via side-channel |
| Sensor hardware | Not replaced or physically spoofed | Synthetic data injection (T4) |
| IoTeX L1 | Standard blockchain finality | Reorg reverts verifications |
| P256 precompile at `0x0100` | Correct implementation | Signature bypass |
| Bridge service | Honest relay | Withholding/reordering (detected via hash-chain) |
| Stable EMA track | Initialized from clean sessions | If early sessions are bot-generated, stable track is poisoned |
| CalibrationIntelligenceAgent | `min()` enforcement code path not bypassed | Threshold loosening if enforcement check skipped |

**Stable track initialization risk.** The L4 biometric anomaly detector computes
Mahalanobis distance against a *stable* EMA track updated only on clean NOMINAL
sessions. If a device's first 5 sessions are bot-generated but below hard-cheat
thresholds, the stable track is initialized from bot biometrics. Subsequent legitimate
human play would then trigger false positives while bot sessions appear normal.
**Mitigation:** the warmup attack detector (§7.5.5) specifically looks for rising
humanity-probability slope early in a device's lifecycle, flagging this bootstrapping
attack. The `_STABLE_TRACK_QUARANTINE` invariant comment in `dualshock_integration.py`
documents this attack surface explicitly.

### 9.3 Adversary Capability Boundaries

| Adversary Capability | Can Defeat | Cannot Defeat |
|---------------------|-----------|---------------|
| Host software control only | Kernel anti-cheat, behavioral heuristics | IMU gravity signal (L2), causal coupling (L2B/L2C), active haptic challenge (L6) |
| Host + USB bus MITM | All software detection | L6 active challenge (requires physical actuator response that software cannot synthesize) |
| Physical device with known-clean history | Hard cheat detection | Longitudinal drift detection (Mode 5 credential suspension operates across sessions) |
| Physical device compromise (hardware) | All PITL layers | On-chain chain integrity (hash gaps detectable), credential suspension (longitudinal) |

### 9.4 Limitations

**Biometric thresholds calibrated on N=74 sessions, 3 players.** The production thresholds
(L4 anomaly 7.009, continuity 5.367) are re-derived in Phase 57 from 74 sessions including
hw_074–hw_078 (touchpad, stick, tremor captures). Mode 6 living calibration autonomously
refines these thresholds every 6 hours from accumulated NOMINAL records, bounded to ±15% per cycle.

**Bridge is a trusted intermediary.** The ZK PITL circuit (§7.5.3) constrains the
bridge's computation of biometric outputs, but requires the ZK artifact files
(`PitlSessionProof.wasm`, `PitlSessionProof_final.zkey`) to be present and the
`PITLSessionRegistry` contract to be deployed. Without these, the ZK guarantee is
inactive. Phase 67 upgrades the ceremony from single-contributor to 3-contributor MPC
with an IoTeX-block beacon anchor (§10.3). The artifact provenance is now on-chain and
independently auditable via `CeremonyRegistry.sol`.

**PHGCredential bridge-key is immutable — key compromise enables malicious suspension.**
The `bridge` address in `PHGCredential.sol` is set at construction time and cannot be
changed. If the bridge's signing key is compromised, an attacker can call `suspend()` on
any device indefinitely. Until multi-sig or timelock governance is added to the
enforcement path, key hygiene for the bridge deployment account is a critical operational
security requirement.

**No data confidentiality.** PoAC records are submitted in plaintext — inference results,
action codes, and locations are visible on-chain.

**L6 response thresholds are engineering estimates, not empirically calibrated.**
The L6 Active Physical Challenge-Response classifier (§7.5.2) uses onset and settle
thresholds (onset_threshold_ms per profile: 300–450 ms; settle_threshold_ms: 1,500–
2,500 ms) derived from general biomechanical literature rather than measured
distributions on real DualShock Edge players. Until a calibration dataset of N≥50
real L6 challenge sessions is collected and analyzed, these thresholds carry the
same caveat as the pre-N=69 biometric thresholds: plausible but not empirically
grounded. False positive and false negative rates for L6 are not yet characterized.

**Biometric transplant requires multi-person calibration data (architectural constraint).**
Inter-person separation has been measured (ratio 0.362) with the N=69 3-player corpus.
This ratio is below 1.0, meaning L4 does not currently separate players. Two of the
eleven features are structurally zero for all calibration sessions (Phase 46 activated
`accel_magnitude_spectral_entropy` at index 9, replacing zero-variance `touchpad_active_fraction`),
and tremor FFT requires a wider analysis window than the current 120-frame window at 1000 Hz.
The new `accel_magnitude_spectral_entropy` feature does not improve inter-person separation
(per-player means P1/P2/P3 are statistically nearly identical). Transplant
attack detection is not a reliable metric under current conditions — the system is an
intra-player anomaly detector, not an inter-player identifier.

**Warmup attack graduation is a fundamental limitation of session-scoped behavioral detection.**
A sufficiently slow warmup attacker who interpolates metrics to human baseline over many
sessions will eventually graduate past the detection boundary. Session-scoped detectors
(BehavioralArchaeologist, L4 biometric, L5 temporal) observe behavior within a window;
they cannot detect an attacker who consistently stays within the human-behavior region
during each individual session. The defense for this attack class is multi-session
temporal analysis (Mode 5 credential suspension), not within-session PITL scoring.

### 9.5 Phase 48 — Professional Adversarial Analysis

Phase 48 adds three **professional/white-box adversarial attack classes** targeting an
adversary who: (1) has read this whitepaper and knows all published thresholds;
(2) has hardware intermediary capability (Cronus Zen-class) for HID emulation at 1000 Hz;
(3) has the N=74 calibration data (human variance statistics).

| Attack | Class | N | Batch L4 | Live Primary Detector |
|--------|-------|---|----------|-----------------------|
| G: Randomized IMU bot | Gaussian IMU at human variance, real button timing | 5 | 0%† | L4 (entropy + tremor) + L2B |
| H: Threshold-aware synthetic | All individual thresholds independently tuned | 5 | **100%** | L4 (grip_asymmetry + stick_autocorr) |
| I: Spectral entropy mimicry | PSD-matched accel noise targeting ~4.8 bits entropy | 5 | 0% | L2B |

†Phase 49 expanded batch proxy to 9 features (incl. tremor_peak_hz, tremor_band_power, 1024-sample FFT at 0.977 Hz/bin). G still 0% batch: right_stick_x preserved from source session → tremor features human-like; entropy 8.41 bits below standalone threshold 8.71. Live L4 + L2B detects G.

**Key findings:**

**Multivariate defense holds.** Attack H demonstrates that publishing all individual PITL
thresholds does not enable threshold-aware evasion. The L4 Mahalanobis evaluates 9 correlated
features simultaneously. An adversary who independently satisfies every threshold (gyro variance
above L2 floor, Gamma-distributed IBI timing, human-range accel variance) cannot simultaneously
reproduce `grip_asymmetry` (no concurrent L2+R2 → default 1.0 vs human mean 0.12) and
`stick_autocorr_lag1` (random-walk ±1 → ≈0 vs human mean 0.44). The combined Mahalanobis
distance exceeds the anomaly threshold regardless of individual feature compliance.

**Spectral entropy is a robust naive-noise detector.** Attacks using Gaussian or lightly-colored
AR noise produce entropy 7.7–8.5 bits — well above the human cluster (mean 4.93 ± 1.30 bits,
upper 2σ = 7.54 bits). Sophisticated PSD-matching (Attack I, using FFT-based shaping of the
target PSD from a real session) defeats the entropy feature in isolation. This is documented
and expected — no single feature is the sole defense; spectral entropy is one of 9 correlated
features in the L4 Mahalanobis.

**L2B is the primary exposure for professional bots.** All three attack classes share one
property: the injected IMU is generated independently of press events. Human voluntary motor
activity produces IMU changes in the 10–60 ms window before button press (L2B causal latency
oracle, 0x31). Bots that generate IMU separately from timing produce zero causal coupling →
L2B fires. L2B is validated at 0% false-positive rate (N=74 sessions) and is the most
reliable professional-bot discriminator orthogonal to spectral structure.

**True blind spot documented.** A bot that (a) extracts the full biometric profile from
captured sessions of a specific player AND (b) replays IMU with correct causal coupling
timing achieves 0% detection across L4, L5, and L2B. This gap (biometric transplant with
coupling) requires per-player enrolled multivariate templates with inter-person separation
ratio > 1.0 (current ratio: 0.362) to close. See `docs/professional-adversarial-analysis.md`.

### 9.6 Class J — GaussianHMM ML-Bot Detection (Phase 81)

Phase 81 addresses the first ML-model-as-adversary in the VAPI corpus. **Class J** uses
a `GaussianHMM` trained on real human IMU data, evading L4 Mahalanobis because the
feature distribution is fitted to human statistics.

**Discriminating signal: temporal entropy variance.** Human psychomotor control during
gameplay produces *rhythmically structured* state transitions — game events (spike plays,
defensive adjustments) create clustering in the entropy time series. GaussianHMM sampling
produces pathologically *uniform* transitions with near-zero variance.

```
Feature: temporal_state_transition_entropy_variance
  Human: variance > 0.15  (game events create clustering — rhythmic structure)
  Class J (HMM): variance < 0.02  (uniform transitions — no cognitive decision events)

Risk thresholds:
  HIGH   ≤ 0.05   — Class J signature detected
  MEDIUM ≤ 0.15   — Ambiguous; monitor
  LOW    > 0.15   — Human-consistent
```

`ClassJDetector` maintains a rolling deque of N=10 session entropy windows per device,
computed every 5-minute poll cycle. On HIGH risk, publishes `class_j_high_risk_detected`
to `AgentMessageBus`. `SessionAdjudicator` enriches LLM evidence with
`class_j_ml_bot_risk` and `ml_bot_candidate=True` (HIGH only), increasing BLOCK
confidence for ML-bot candidates.

**Per-layer detection matrix (Class J):**
| Layer | Detection | Notes |
|-------|-----------|-------|
| L4 Mahalanobis | 0% | HMM fitted to human feature distribution — L4 passes |
| L5 Temporal Rhythm | Partial | HMM entropy near human range; CV passes |
| L2B IMU-Press | Partial | IMU generated independently → limited coupling |
| Class J Detector | **HIGH** | Entropy variance 0.0004 vs human >0.15 |

**Phase 82 candidate:** `SessionAdjudicator` subscribes to `class_j_high_risk_detected`
bus event and fires an immediate out-of-cycle LLM ruling (Reactive Adjudication
Interrupt), collapsing Class J detection → ruling → enforcement → federation chain from
15+ minutes to <5 seconds end-to-end.

### 9.7 DePIN Governance Model (Phase 70)

Phase 70 addresses a structural governance gap: all six Phase 69 contracts expose a
single `operator` key capable of instant, irreversible mutations (oracle verdict overrides,
marketplace treasury drains, reward parameter changes). A single compromised key can
devastate the protocol state with no recourse window.

**VAPIGovernanceTimelock.sol** interposes a mandatory 48-hour delay (TIMELOCK_DELAY = 172800
seconds) before any operator transition on a Phase 69 contract takes effect:

```
queueTransition(target, newOperator)   → schedules with eta = block.timestamp + 48h
executeTransition(queueId)             → callable only after eta; operator only
cancelTransition(queueId)              → callable by operator OR co-signer (emergency)
```

The co-signer key has **cancel-only access** — it cannot queue new transitions or execute
existing ones. This separation ensures that even if the co-signer is controlled by an
adversary, the worst outcome is blocking a legitimate transition (recoverable), not
executing an unauthorized one (catastrophic). The operator can replace the co-signer
address through the normal 48-hour queue, preventing co-signer key lock.

**PHGCredential exclusion.** PHGCredential.sol is explicitly excluded from the timelock
governance scope. The bridge address on PHGCredential is immutable post-deploy and
cannot be changed through `setOperator()` — timelock governance would create a false
sense of security for an invariant that the contract itself enforces.

**Security properties guaranteed at the contract level:**
- CEI (Checks-Effects-Interactions) pattern: `t.executed = true` is set **before** the
  external `setOperator()` call on the target contract, preventing reentrancy
- Anti-replay: queueId monotonically increments; executed/cancelled flags prevent
  re-execution of any historical transition
- Overflow safety: `block.timestamp + TIMELOCK_DELAY` cannot overflow uint256 within
  any meaningful operational timeframe (~8.5 × 10^49 years at 1-second blocks)
- No griefing via co-signer pre-cancellation: the operator can re-queue any cancelled
  transition; the co-signer's cancel path cannot permanently block a legitimate transition

**Trust model change.** Before Phase 70, VAPI's trust model required trusting a single
operator private key for all six Phase 69 contracts. After Phase 70, the trust model
requires: (1) 48 hours of public observation time, (2) co-signer approval-by-silence
(absence of cancel), and (3) operator key security. This is meaningfully stronger — the
attack surface shrinks from "instant unilateral mutation" to "48-hour visible mutation."

**VAPIProtocolLens trust.** VAPIProtocolLens.sol has zero mutable state — all four
oracle addresses are set at constructor time as `immutable` fields. Post-deployment, the
lens cannot be pointed at different oracle contracts. Any oracle address changes require
deploying a new lens instance. This guarantees that any tournament integration pointing
at a known lens address receives data from the expected oracle set permanently.

**Oracle failure posture (Phase 71 M-1 remediation).** A post-Phase-70 security review
identified that `getDeviceState()` and `isFullyEligible()` previously defaulted `isEligible`
to `true` when the RulingOracle was unreachable — a fail-open posture that could allow a
suspended device to pass the eligibility gate during transient oracle downtime. Phase 71
fixes this to fail-closed: `isEligible` defaults to `false` on oracle failure, and a new
`oracleAvailable` boolean field in `DeviceProtocolState` lets callers distinguish
"verified eligible" from "oracle unreachable — gate indeterminate." Tournament integrations
should treat `oracleAvailable = false` as a gate-hold signal and retry rather than
proceeding with an unverified eligibility state.

---

### 9.8 PHGCredential Bridge-Layer Multi-Sig (Phase 72)

PHGCredential.bridge is declared `immutable` in Solidity — set once at constructor
time and cannot be changed post-deploy. This means VAPIGovernanceTimelock cannot
govern PHGCredential.suspend() the same way it governs Phase 69 contracts. To reduce
the single-key risk on PHGCredential suspensions, Phase 72 implements a multi-sig
safeguard at the **bridge (Python) layer**.

**Multi-sig flow:**
```
POST /operator/suspension/propose   → inserts pending_suspensions row, returns proposal_id
POST /operator/suspension/confirm/{id} → increments confirmation count
POST /operator/suspension/execute/{id} → calls PHGCredential.suspend() if confirmations ≥ threshold
```

**Configuration:** `SUSPENSION_MULTISIG_THRESHOLD` (default 1 — current behaviour).
Set to 2 to require a second operator key confirmation before any on-chain suspension fires.

**Documented limitation.** This is a software safeguard, not cryptographic enforcement.
The second key must be physically separate from the first (different key material, different
operator). If both keys are stored in the same `.env` file, the multi-sig provides ceremony
but not security. Tournament operators deploying VAPI should hold the two keys in separate
security contexts (e.g., HSM + operator laptop, or two separate team members).

**Audit trail.** Every proposal, confirmation, and execution is recorded in the
`pending_suspensions` SQLite table with timestamps and proposer fingerprint (truncated
SHA-256 of the API key — non-reversible). This provides an immutable governance audit trail
for every suspension decision from the moment of proposal to on-chain execution.

Tournament Condition 3 (§ Tournament Readiness) is now CLOSED IN CODE. The limitation is
documented honestly: governance risk for PHGCredential is reduced (software multi-sig),
but not eliminated (not cryptographic enforcement). This is the strongest achievable
position given PHGCredential's immutable bridge address.

---

### 9.9 Synthetic Session Corpus Pipeline (Phase 86)

Phase 86 addresses a practical gap in the path from `dry_run=True` to `dry_run=False`:
the `consecutive_clean` gate requires N=100 non-divergent real-device adjudications, but
during early deployment there are no real devices submitting sessions. The synthetic corpus
pipeline provides a hardware-free mechanism to:

1. **Verify `_rule_fallback` correctness** — 120 synthetic nominal sessions are generated
   and each is run through `_rule_fallback`. If `failed_fallback > 0`, a rule_fallback
   regression has been introduced by a recent code change.
2. **Exercise the pipeline end-to-end** — `POST /agent/run-synthetic-corpus` triggers
   `ValidationCorpusRunner`, which creates sessions, runs them through the fallback oracle,
   and persists results to the `synthetic_sessions` table.
3. **Provide a regression test corpus** (Phase 87 candidate) — re-running the corpus after
   any `_rule_fallback` change with `all_nominal=False` as a failure signal.

**ISOLATION INVARIANT (W1 mitigation):** Synthetic sessions are stored exclusively in the
`synthetic_sessions` table and never inserted into `ruling_validation_log`. They do not
affect `consecutive_clean` or `gate_passed`. The production validation gate remains strictly
dependent on real device adjudications. `GET /agent/corpus-status` includes an explicit
`isolation_note` field confirming this separation.

This invariant is critical: a synthetic-only gate_passed would allow `AGENT_DRY_RUN=false`
without any empirical validation of the LLM vs rule_fallback agreement on real human data.
The isolation design ensures this path cannot occur.

**Synthetic session structure.** Each session carries `enrollment_status="eligible"` and
empty `hard_cheat_codes` / `advisory_codes` lists — the minimal evidence footprint that
`_rule_fallback` routes to `CERTIFY (0.8)`. Biometric features are drawn from the nominal
human range (humanity_score 0.65–0.92, L4 distances below both calibration thresholds).
All sessions are prefixed `device_id="synthetic_<hex>"` for unambiguous identification
in any database inspection.

### 9.10 Activation Audit Verifier (Phase 95)

Phase 95 closes the enforcement readiness verification chain by introducing a cross-referencing audit step that programmatically verifies the full activation sequence. The core invariant is temporal: before an operator enables live enforcement (`AGENT_DRY_RUN=false`), both of the following must have occurred in the correct order:

1. **Protocol scored ready_for_live_mode=True** — recorded in `live_mode_activation_log` (Phase 92) with `protocol_health_score ≥ 85` and all gate conditions met.
2. **On-chain gate attestation exists** — a `GateAttestationAnchor.sol` record is present in `gate_attestations` (Phase 84/87), with `created_at` timestamped *after* the first ready check.

`store.get_activation_audit_summary()` queries both tables atomically and computes `audit_valid` as the conjunction of three conditions: `first_ready_check_at IS NOT NULL` (condition 1 satisfied), `gate_attestation_count > 0` (condition 2 satisfied), and `first_ready_check_at ≤ latest_attestation_at` (chronological order confirmed). A violation of the third condition — where the on-chain anchor predates the readiness determination — returns `audit_valid=False` with an explicit `predates` message and the offending timestamps.

**Chronological significance.** The ordering requirement prevents a class of activation errors where an operator deploys an on-chain anchor (e.g., during testing) before the protocol has completed its validation gate. Without Phase 95, such a pre-existing attestation would be indistinguishable from a legitimate post-readiness anchor. The temporal constraint ensures the evidence chain is not retroactively satisfied.

**Programmable enforcement gate.** `VAPITournamentGate.verify_activation_audit()` (SDK Phase 95) wraps `GET /agent/activation-audit` into `ActivationAuditResult` — a fail-safe dataclass that never raises. Tournament CI pipelines can gate the `AGENT_DRY_RUN=false` configuration change behind:

```python
gate = VAPITournamentGate(base_url=BRIDGE_URL, api_key=API_KEY)
audit = gate.verify_activation_audit()
assert audit.audit_valid, f"Activation audit failed: {audit.audit_summary}"
# Safe to proceed with AGENT_DRY_RUN=false
```

**Test coverage.** Six bridge tests verify: empty-store field presence; `audit_valid=False` on missing ready entry; `audit_valid=False` on missing attestation; `audit_valid=True` with correct order; `audit_valid=False` on chronological violation; endpoint returns correct JSON. Four SDK tests verify: `ActivationAuditResult` defaults; response parsing; fail-safe behavior on bad URL; `audit_valid=False` propagation.

Bridge: 1344→1350 (+6). SDK: 73→77 (+4). openapi: v3.0.0-phase95.

### 9.11 Enforcement Readiness Certificate (Phase 96)

Phase 96 introduces the Enforcement Readiness Certificate (ERC) — a portable, operator-signed cryptographic artifact that decouples tournament operator readiness verification from real-time VAPI infrastructure access.

**W1 fix.** Phase 96 also resolves a latent bug in the Phase 95 `get_activation_audit_summary()` implementation: the query over `gate_attestations` used no timestamp filter, meaning pre-readiness infrastructure test anchors (created during Phase 84/87 development testing) could permanently produce `audit_valid=False`. The fix adds `WHERE created_at >= first_ready_at`, ensuring only post-readiness attestations count toward the chronological invariant.

**ERC construction.** `POST /agent/enforcement-certificate` constructs the ERC as:
```
canonical_json = json.dumps(audit_fields, sort_keys=True)
audit_hash     = SHA-256(canonical_json)
hmac_sig       = HMAC-SHA256(audit_hash, operator_api_key)
```
The cert is stored with a configurable TTL (default 24h, `ENFORCEMENT_CERT_TTL_S` env var). UNIQUE constraint on `audit_hash` makes re-issuance idempotent. `is_expired=True` is advisory — the bridge does not block on expired certs; the operator is responsible for renewal.

**Portability.** A tournament operator holding `(audit_hash, hmac_sig, shared_api_key)` can verify the cert offline by recomputing `HMAC-SHA256(audit_hash, shared_key)` and comparing with `compare_digest`. No VAPI infrastructure, no blockchain call required.

**SDK.** `VAPITournamentGate.create_enforcement_certificate()` and `.get_enforcement_certificate()` return `EnforcementReadinessCertificate` (never raises). Bridge: 1350→1358 (+8). SDK: 77→81 (+4).

### 9.12 Gated Live Mode Transition (Phase 97)

Phase 97 closes the activation deadlock by making `AGENT_DRY_RUN=false` physically conditional on all three enforcement readiness pre-conditions being simultaneously satisfied.

**Three-condition gate.** `POST /agent/config?dry_run=false` evaluates atomically:
1. **gate_passed** — `consecutive_clean ≥ gate_n` (default 100) AND `divergence_rate ≤ max_divergence_rate`
2. **cert_valid** — a non-expired ERC with `audit_valid=True` exists in `enforcement_certificates`
3. **audit_valid** — `get_activation_audit_summary()` confirms the Phase 95 chronological invariant

Any unsatisfied condition returns HTTP 422 with a `blocking` array identifying which conditions failed. The blocking array is also logged to `live_mode_guard_log` for operator accountability.

**Fleet-wide bus broadcast.** On approval, a `live_mode_enabled` event is published to `AgentMessageBus`. `SessionAdjudicator` and `RulingEnforcementAgent` each subscribe via `_listen_live_mode_bus()` and update `cfg.agent_dry_run_mode` within <1ms — without waiting for the next 5-minute poll cycle. This ensures the entire agent fleet shifts to enforcement mode atomically.

**Audit trail.** Every attempt — approved or blocked — is logged to `live_mode_guard_log` with `event_type` (transition_attempt/transition_approved/dry_run_restored), individual condition flags, `blocking_conditions` JSON, and `operator_key_hash` (first 16 chars of SHA-256 of api_key). Bridge: 1358→1364 (+6 tests).

### 9.13 Epistemic Consensus Protocol (Phase 98)

Phase 98 introduces the first formal multi-agent consensus gate for irreversible enforcement decisions in competitive gaming.

**Problem.** Before Phase 98, a single LLM ruling could unilaterally recommend BLOCK, which the enforcement pipeline would then execute as a PHGCredential suspension. The LLM has no access to the time-series entropy signal from `ClassJDetector` or the cross-session pattern data from `DivergenceTriageAgent`. A high-confidence BLOCK from the LLM may reflect a session anomaly rather than confirmed cheating.

**Weighted consensus.** `SessionAdjudicator._epistemic_consensus(device_id, proposed_verdict)` fires only when `proposed_verdict == "BLOCK"`. It queries three independent evidence sources:

| Agent | Weight | Signal | Score Mapping |
|-------|--------|--------|---------------|
| ClassJDetector | 0.40 | entropy_variance risk_level | HIGH=1.0, MEDIUM=0.5, LOW=0.0 |
| DivergenceTriageAgent | 0.40 | triage escalated flag | escalated=1.0, not escalated=0.0 |
| AgentSupervisor | 0.20 | fleet_health status | ALL_HEALTHY=1.0, DEGRADED=0.5, CRITICAL=0.0 |

`consensus_score = 0.40·classJ + 0.40·triage + 0.20·supervisor`. If `consensus_score < threshold` (default 0.60, configurable), BLOCK is downgraded to HOLD.

**Threshold analysis.** At threshold=0.60 with only supervisor healthy and no ClassJ/triage signal: `consensus = 0.0 + 0.0 + 0.20 = 0.20 < 0.60` → HOLD. With HIGH ClassJ and healthy fleet but no triage: `consensus = 0.40 + 0.0 + 0.20 = 0.60 ≥ 0.60` → BLOCK (exactly meets threshold). With HIGH ClassJ + escalated triage: `consensus = 0.40 + 0.40 + 0.20 = 1.00` → BLOCK. This means a BLOCK requires at minimum both ClassJ HIGH and fleet healthy, or triage escalated and fleet healthy, to proceed to enforcement.

**Threshold vulnerability (W1).** The 0.60 threshold is exactly reachable by ClassJ alone (`0.40 + 0.20 = 0.60`). A sophisticated adversary who accumulates HIGH ClassJ entropy variance (triggering the ClassJ gate) while deliberately keeping `divergence_count` below the triage escalation thresholds across sessions — by spacing cheating instances so they never form the `ml_bot_cluster` (≥2 HIGH) or `cheat_cluster` (≥1 hard code) or `enrollment_anomaly` (≥3 ineligible) patterns — can reach exactly-threshold consensus from a single evidence source. The three-agent design reduces to an effective one-agent gate under this suppression strategy. **Mitigation options:** (1) raise threshold to 0.65 (ClassJ-alone path yields 0.60 < 0.65 → HOLD, requiring some triage signal); (2) add a hard prerequisite: `triage_score > 0.0 OR class_j_score < 1.0` to prevent pure single-source BLOCK. Configurable via `EPISTEMIC_CONSENSUS_THRESHOLD` env var (default 0.60 — operators running sustained adversarial deployments should consider 0.65).

**Scope.** The gate fires in both `_process_ruling_request()` (standard 5-min poll) and `_adjudicate_device_directly()` (reactive/warm-up paths). For non-BLOCK verdicts (CERTIFY, FLAG, HOLD), the method returns immediately without querying any agents. When `EPISTEMIC_CONSENSUS_ENABLED=false`, BLOCK passes through unchanged (operator override for scenarios where all agents are trusted).

**Audit trail.** Every consensus decision — including the individual scores and whether downgrading occurred — is persisted to `epistemic_consensus_log`. `GET /agent/epistemic-consensus-log` exposes `downgraded_count` so operators can track how often the false-positive protection layer fired. Bridge: 1364→1372 (+8 tests). openapi: v3.0.0-phase98.

### 9.14 AGaaS Foundation Token Stack (Phase 99A)

Phase 99A pivots VAPI from a standalone anti-cheat protocol to an **AGaaS (Agentic-as-a-Service)** company in the **Verified Autonomous Physical Intelligence** category under the IoTeX DePIN umbrella. Three new smart contracts establish the economic and credential foundation.

**VAPIToken.sol** — ERC-20 utility token with a 1,000,000,000 VAPI hard cap. `completeTGE()` is irreversible: it seals `mint()` permanently and pauses transfers (ERC20Pausable). Token launch (TGE) is gated by three conditions: (1) inter-person separation ratio > 1.0 confirmed (currently 0.362 — OPEN); (2) N≥100 live adjudications with zero confirmed false positives; (3) Verified Human Proof (VHP, Phase 99C) end-to-end demonstrated. **No TGE occurs in Phase 99 — testnet deployment only.**

**VAPIOperatorRegistry.sol** — Cryptographic accountability for bridge operators. `MINIMUM_STAKE = 10,000 VAPI`. Slash mechanics: `slash(operator, reason)` burns 50% and transfers 50% to the slash claimant, creating economic skin-in-the-game for enforcement accuracy. Deregister requires a 30-day cooldown after `requestDeregister()` — preventing stake withdrawal during active adjudication campaigns. All state-mutating functions follow CEI (Checks → Effects → Interactions) with `ReentrancyGuard`. This is the first cryptographic accountability mechanism for AI enforcement operators in competitive gaming.

**VAPIHardwareCertRegistry.sol** — On-chain hardware certification keyed by `profileHash = keccak256(manufacturer ++ model ++ firmwareVersion)`. `certLevel 1` = controller; `certLevel 2` = controller + GSR biometric grip. `isCertified(profileHash)` is a **pure view** with no gas cost to callers — the first hardware-level DePIN composability primitive in competitive gaming. Tournament contracts can gate hardware eligibility with:

```solidity
require(certRegistry.isCertified(grip.profileHash), "Hardware not certified by VAPI");
```

**Bridge integration.** `operator_registrations` SQLite table records all staking events (register/slash/deregister_request/deregister) with tx_hash and reason. `GET /agent/operator-status` exposes the latest event per operator address. Tool #65 `get_operator_status`. Config fields: `vapi_token_address`, `operator_registry_address`, `hardware_cert_registry_address`.

**W1 test isolation invariant.** `completeTGE()` is irreversible — if called in a shared Hardhat fixture, all subsequent `mint()` calls on that deployment revert, cascading failures across Phase 99B/C tests that need token minting for staking. All Phase 99 Hardhat tests deploy a fresh `VAPIToken` per `describe` block using `beforeEach`.

**W2 composability.** `VAPIHardwareCertRegistry.isCertified()` composes identically to `VAPIProtocolLens.isFullyEligible()` — both are pure view, both are zero-gas to integrators. A game developer can write: `require(lens.isFullyEligible(deviceId) && certReg.isCertified(profileHash))` to gate both the human credential and the hardware credential in a single modifier. Hardhat: 408→420 (+12). Bridge: 1372→1378 (+6). openapi: v3.0.0-phase99a.

---

### 9.15 W3bstream Integration + L7_GSR Layer (Phase 99B)

Phase 99B adds three independent components that together form the DePIN data pipeline and physiological biometric layer for the AGaaS stack.

**VAPIGSRRegistry.sol** — On-chain anchor for Galvanic Skin Response (GSR) biometric samples submitted by the W3bstream pipeline. `recordSample(bytes32 deviceId, uint256 arousalMillis, uint256 correlationMillis, uint256 timestamp)` is callable only by the contract owner (bridge operator key). Anti-replay is enforced by `require(!samples[deviceId][timestamp].exists)` — each device-timestamp pair is unique. `arousalMillis = index * 1000` encodes the 0.0–1.0 sympathetic arousal index as a uint256. `correlationMillis = (r + 1.0) * 500` encodes the signed Pearson r (-1.0 to +1.0) in the range 0–1000. `getSampleCount(deviceId)` and `getLatestSample(deviceId)` are public view functions.

**W3bstream AssemblyScript applets.** Two WASM applets run inside the W3bstream project for IoTeX DePIN data submission:

- `validate_poac_record.ts` — Receives the frozen 228-byte PoAC packet, verifies ECDSA-P256 signature over `raw[0:164]` (body only — the chain link hash invariant is preserved), and calls `PITLSessionRegistryV2.submitProof(chainLinkHash, deviceId, inferenceCode)` on IoTeX L1. Invalid signatures are rejected before any on-chain write.

- `process_gsr_packet.ts` — Receives a 48-byte GSR packet (magic `0x47535201`), validates `arousalMillis ≤ 1000` and `correlationMillis ≤ 1000`, and calls `VAPIGSRRegistry.recordSample()`. Malformed packets return non-zero error codes without chain interaction.

**L7_GSR feature extraction.** `gsr_feature_extractor.py` implements the code-before-hardware pattern established by L6b (Phase 63) and ClassJDetector (Phase 81). `MockGSRGrip(seed)` generates reproducible synthetic EDA signal — 4th-order LP noise with SCR events every 15–60s — for development and test. Real hardware (Ag/AgCl + ESP32-S3, ~$35 BOM) replaces `MockGSRGrip` transparently when `GSR_ENABLED=true`. `extract_l7_features(window)` returns four biometric features:

| Feature | Computation |
|---------|-------------|
| `sympathetic_arousal_index` | Mean arousal across the window |
| `gsr_game_event_correlation` | Mean Pearson r with game events |
| `baseline_conductance_drift` | Linear regression slope of conductance_raw |
| `cognitive_load_variance` | Inter-SCR interval coefficient of variance |

The function **never raises** — it returns all-zero values for windows < 10 samples or on any exception. `GSR_ENABLED=false` default; all code paths are guarded by `cfg.gsr_enabled`. Inference code `0x33 GSR_CORRELATION_ABSENT` is **advisory only** — it never hard gates tournament eligibility. `GSRRegistryAgent` runs a 5-minute poll loop, stores samples to SQLite (`gsr_samples` table via `insert_gsr_sample` / `get_gsr_samples`), publishes `gsr_sample_recorded` bus events, and calls `chain.record_gsr_sample_on_chain()` only when `gsr_enabled=True`. `SessionAdjudicator._assess_gsr_risk(device_id)` (never raises, returns `{}` on empty store) enriches the evidence summary with `gsr_sympathetic_arousal` and `gsr_game_correlation` when GSR is enabled. The `GSRRegistryAgent` is wired in `main.py` behind a `gsr_enabled` guard — zero overhead when disabled.

**GSR_ENABLED calibration gate.** GSR_ENABLED will remain `false` until N≥30 real calibration sessions per player confirm the arousal signal is stable and the Pearson r with game events exceeds 0.3 for human players. Current N=0 (hardware pending). Estimated BOM: $35 (Ag/AgCl electrodes + INA128 instrumentation amp + ESP32-S3 BLE module). Hardhat: 420→424 (+4). Bridge: 1378→1386 (+8). openapi: v3.0.0-phase99b.

---

### 9.16 VHP Soulbound Token + LayerZero Bridge (Phase 99C)

Phase 99C delivers the credential layer that closes the Phase 99 AGaaS stack: a non-transferable, expiring, composable proof-of-human-identity token anchored on IoTeX and bridgeable to any LayerZero V2 destination chain.

**VAPIVerifiedHumanProof.sol** — An ERC-4671 soulbound token. Key design decisions:

- `mint(address to, VHPData calldata data)` is `onlyOwner` — callable only by the bridge operator key after the three gate conditions pass.
- ALL transfer functions (`transferFrom`, `safeTransferFrom`, `approve`, `setApprovalForAll`) unconditionally revert with `"VAPIVerifiedHumanProof: soulbound"` — no approval mechanism, no operator delegation, no migration path. The credential is tied to the minting address permanently.
- `isValid(tokenId)` returns `true` only when `block.timestamp < vhpData[tokenId].expiresAt` — a stateless, gas-free validity check composable in any smart contract.
- `renew(tokenId)` extends `expiresAt` by `defaultTTLDays * 1 days` (default 90) from the current block timestamp. Requires the token to currently be valid — expired tokens cannot be renewed.
- Token counter: plain `uint256 _tokenIdCounter` incremented per mint — no `Counters` library (removed in OpenZeppelin v5).
- `VHPData` struct: `{bytes32 deviceIdHash, uint8 certificationLevel, uint32 consecutiveClean, uint32 confidenceScore (0–10000 basis points), uint256 issuedAt, uint256 expiresAt, bytes32 mpcCeremonyHash}`.

**VHP mint gate (POST /agent/mint-vhp).** Three conditions are checked server-side before any on-chain write:

| Condition | Source | Failure |
|-----------|--------|---------|
| `audit_valid=True` | `store.get_activation_audit_summary()` | 422: "audit_valid=False" |
| `gate_passed=True` | `store.get_validation_summary(gate_n, max_div)` | 422: "gate_passed=False" |
| `AGENT_DRY_RUN=false` | `cfg.agent_dry_run_mode` | 422: "dry_run=True" |

On gate passage: `chain.mint_vhp()` is called with `device_id_hash=SHA-256(device_id)`, `mpc_ceremony_hash` from `cfg.mpc_ceremony_hash_cache` (falls back to zero hash), and `ttl_days=90`. The issuance is persisted to the `vhp_issuances` SQLite table via `store.insert_vhp_issuance()`. `GET /agent/vhp-status/{device_id}` returns the latest issuance with `is_valid=True` if `expires_at > now`.

**VAPIVerifiedHumanProofBridge.sol** — A LayerZero V2 OApp stub for cross-chain VHP transmission. `setPeer(dstEid, peerAddress)` must be called before first `send()`. `send(tokenId, dstEid, recipient, data)` increments a per-`(tokenId, dstEid)` nonce and emits `VHPSent` — in stub mode, no LayerZero endpoint call is made. Production deployment requires the IoTeX testnet LayerZero V2 endpoint address (`LZ_ENDPOINT` env var). `withdrawNative()` onlyOwner recovers any accidentally sent native token.

**SDK — VAPIHumanProof.** Three methods, all failing safely:

| Method | Returns | On error |
|--------|---------|----------|
| `is_human(device_id)` | `bool` | `False` (never raises) |
| `get_vhp_data(device_id)` | `VHPData` | `VHPData(is_valid=False, error=str(exc))` |
| `request_vhp_mint(device_id, to_address)` | `dict` | `{"error": str(exc)}` |

`VHPData` is a `@dataclass(slots=True)` with 11 fields: `device_id`, `token_id`, `cert_level`, `consecutive_clean`, `confidence_score` (float 0.0–1.0), `issued_at`, `expires_at`, `is_valid`, `to_address`, `vhp_contract_address`, `error`.

**Composability.** The VHP token is the terminal composable primitive in the Phase 99 stack:

```solidity
// Tournament gate combining all three Phase 99 primitives
require(lens.isFullyEligible(deviceId),          "Human biometric gate failed");
require(certReg.isCertified(grip.profileHash),    "Hardware not certified");
require(vhp.isValid(tokenOfAddress[player]),      "VHP expired or not issued");
```

This is the first soulbound physiological humanity credential composable into any IoTeX smart contract — callable by any game developer with a single `eth_call`, no oracle trust assumption, no gas cost. Hardhat: 424→430 (+6). Bridge: 1386→1392 (+6). SDK: 81→87 (+6). openapi: v3.0.0-phase99c. **Phase 99 COMPLETE.**

### 9.17 Operator Activation Runbook (Phase 100)

Phase 100 closes the bootstrap gap between Phase 99 DEPLOYED and the first live VHP. On a fresh testnet deployment, `agent_rulings` is empty — `POST /agent/warm-up` previously selected no devices, leaving `consecutive_clean = 0` and the validation gate permanently blocked.

**Warm-Up Bootstrap (`POST /agent/warm-up` enhancement).** The endpoint now accepts an explicit `?device_ids=<id>` query parameter. Device resolution order: (1) explicit param, (2) recent `agent_rulings` devices (existing Phase 84 path), (3) `ioid_devices` table fallback (Phase 55 registered devices). If all three sources are empty, the endpoint returns `reason: "no_devices_registered"` with an actionable `hint` field. The operator supplies the known DualShock Edge `device_id` (keccak256 of its public key) on first bootstrap.

**Activation Status Dashboard (`GET /agent/activation-status`).** A 5-step checklist endpoint giving the operator a complete activation picture:

| Step | Condition | Blocking code |
|------|-----------|---------------|
| 1 | `consecutive_clean >= gate_n` (default 100) | `gate_not_passed` |
| 2 | Enforcement cert issued + valid (not expired) | `no_cert / cert_expired` |
| 3 | `audit_valid=True` (chronological invariant) | `audit_invalid` |
| 4 | `AGENT_DRY_RUN=false` | `dry_run_active` |
| 5 | All of 1+3+4 pass → VHP mint available | (composite) |

`current_blocking_step` is machine-readable: the exact step blocking progress, or 6 for fully activated. `recommended_action` contains the exact API call to make next (e.g., `"POST /agent/warm-up (need 87 more clean sessions; pass ?device_ids=<id> if agent_rulings is empty)"`). `progress_pct` shows gate completion 0–100%. `warnings` surfaces low gate_n values (< 50) that may indicate an insufficiently hardened configuration.

**Tool #66 `get_activation_status`.** BridgeAgent tool returning `{current_blocking_step, fully_activated, consecutive_clean, gate_n, progress_pct, dry_run_active, audit_valid, cert_valid, timestamp}` — the compact version for agentic loop reasoning.

**Operator Activation Sequence:**

```bash
# 1. Bootstrap warm-up (repeat until consecutive_clean >= 100)
curl -X POST "http://localhost:8080/agent/warm-up?api_key=$KEY&device_ids=$DEVICE_ID"

# 2. Monitor checklist after each batch
curl "http://localhost:8080/agent/activation-status?api_key=$KEY"

# 3. Issue enforcement certificate (after gate passes)
curl -X POST "http://localhost:8080/agent/enforcement-certificate?api_key=$KEY"

# 4. Flip live mode (422 if any gate condition fails)
curl -X POST "http://localhost:8080/agent/config?api_key=$KEY&dry_run=false"

# 5. Mint the first VHP
curl -X POST "http://localhost:8080/agent/mint-vhp?api_key=$KEY&device_id=$DEVICE_ID&to_address=$WALLET"
```

Bridge: 1392→1400 (+8). openapi: v3.0.0-phase100. **Phase 100 COMPLETE.**

### 9.18 Phase 101: AGaaS Economics + IoTeX Positioning

Phase 101 introduced AGaaS economic primitives and formal IoTeX ecosystem positioning.

#### QuickSilver stIOTX Collateral (Phase 101A)

Operators may collateralise their VAPI registration using stIOTX (IoTeX's liquid staking token via QuickSilver protocol) as an alternative to VAPI token staking. This creates a double-yield mechanism: operators earn QuickSilver rebasing yield on their stIOTX while it remains locked as protocol collateral.

The `VAPIQuickSilverCollateral.sol` contract handles lock/unlock/claim flows. The `quicksilver_collateral_events` store table persists all collateral lifecycle events (lock, unlock_request, claim_unlock, slash, claim_yield). Tool #67 `get_quicksilver_collateral_status` provides agent-layer visibility. Bridge count: 1400→1410 (+10 tests).

#### Edge AI Profile (Phase 101B)

The Edge AI Profile formally positions VAPI's 13-agent autonomous fleet on the IoTeX Real-World AI stack:

- **ioID (Verify layer):** Device identity verification LIVE — DualShock Edge hardware profiles certified via `VAPIHardwareCertRegistry`
- **W3bstream (Process layer):** ZK proof processing LIVE — PITL session proofs submitted via `validate_poac_record.ts` AssemblyScript applet
- **Realms (Perceive layer):** Deferred pending ≥100k events/day threshold

The inference mode adapts to runtime availability: `llm_augmented` when Anthropic SDK is available, `local_rule_fallback` (SLM-equivalent, no GPU required) as fallback. Tool #68 `get_edge_ai_profile` exposes the full fleet manifest and positioning statement. **Phase 101 COMPLETE.**

### 9.19 Phase 102: Developer Integration Layer

Phase 102 delivers the developer-facing composability layer that makes VAPI's AGaaS thesis actionable for game studios.

#### TournamentGateDemo.sol

`TournamentGateDemo.sol` demonstrates the "single composable call" AGaaS integration pattern. Game developers wire two interfaces:

```solidity
interface IVAPIProtocolLens {
    function isFullyEligible(bytes32 deviceId) external view returns (bool);
}
interface IVAPIVerifiedHumanProof {
    function isValid(uint256 tokenId) external view returns (bool);
}
```

The `enterTournament(bytes32 deviceId, uint256 vhpTokenId)` function enforces both checks atomically. W1 mitigation: the `demoMode` flag (owner-settable) bypasses gate checks for developer evaluation on testnet. `demoMode=false` enforces full PITL stack in production.

Deployed to IoTeX Testnet (Chain 4690) with `demoMode=true`. Hardhat tests: 430→434 (+4).

#### VHPRenewalAgent (14th Autonomous Agent)

VHP soulbound tokens (ERC-4671) expire after 90 days. Without auto-renewal, the first VHP minted on testnet would silently lapse. The `VHPRenewalAgent` is the 14th member of the autonomous agent fleet.

- Polls every 6 hours
- Finds VHPs expiring within `vhp_renewal_warning_days` (default: 7 days)
- In dry_run mode: logs renewal advisory without chain call
- In live mode: calls `VAPIVerifiedHumanProof.renew(tokenId)` (60k gas), logs to `vhp_renewal_log`
- W2 liveness beacon: publishes `vhp_lifecycle_warning` bus event when `get_total_vhp_count() == 0`

Tool #69 `get_vhp_renewal_log` exposes fleet visibility. GET `/agent/vhp-renewal-log` provides REST access.

#### VAPITournamentClient (Python SDK)

Game backend developers use `VAPITournamentClient` for a single-call eligibility check:

```python
client = VAPITournamentClient("https://vapi-bridge.example.com", api_key="...")
elig   = client.check_player(device_id, wallet_address)
if elig.is_eligible:
    grant_tournament_entry()
```

`PlayerEligibility` captures `has_valid_vhp`, `consecutive_clean`, `cert_level`, `expires_at`. Never raises — errors are captured in `PlayerEligibility.error`.

Bridge count: 1414→1422 (+8). SDK count: 87→93 (+6). **Phase 102 COMPLETE.**

---

### §9.20 Phase 103: Live Activation Protocol

Phase 103 closes the critical gap where `get_total_vhp_count() == 0` despite 14 agents
running — the protocol had never executed its own critical path end-to-end.

**ActivationSimulator** seeds all six gate conditions in the exact order required to satisfy
the Phase 96 chronological invariant (`gate_attestations.created_at >= first_ready_check_at`):

1. `ruling_validation_log` — 110+ CERTIFY records (consecutive_clean >= gate_n=100)
2. `protocol_intelligence_reports` — health_score=90, ready_for_live_mode=True
3. `live_mode_activation_log` — establishes `first_ready_check_at` timestamp
4. `gate_attestations` — inserted AFTER step 3 (chronological invariant confirmed)
5. `enforcement_certificates` — audit_valid=True, HMAC-SHA256 sig
6. `vhp_issuances` — VHP #1: tx_hash=`sim_mint_<sha256_hex16>`, no chain call

**ActivationRunner** orchestrates the full 12-step sequence: seed all conditions ->
verify gate_passed + audit_valid -> toggle `cfg.agent_dry_run_mode=False` in-memory ->
insert VHP #1 -> publish `first_vhp_minted` bus event -> log to `activation_simulation_log`.
Never raises from `run()`.

**W2 — ProtocolMaturityScore primitive:** `get_first_vhp_status().is_simulation` distinguishes
simulated activation from organic activation, enabling a future AGaaS maturity ladder:
simulation -> testnet real VHP -> mainnet VHP — verifiable for investor reporting.

**SDK:** `VAPIActivationFlow(base_url, api_key)` exposes three methods: `run_simulation()`,
`check_ready()`, `get_first_vhp()` — all return structured types, never raise.

Bridge 1422->1430 (+8). SDK 93->99 (+6). **Phase 103 COMPLETE.**

### §9.21 Phase 104: Persistent Activation Commit + ProtocolMaturityIndex

Phase 103 exposed W1: `cfg.agent_dry_run_mode = False` was set in-memory only — every bridge
restart reverted it to `True`. Phase 104 closes this gap with an `activation_state` SQLite
table and a `_restore_activation_state(cfg, store)` function that runs synchronously BEFORE
any asyncio agent tasks are launched. This eliminates the race window between persistence
read and agent startup. Because `Config` is `@dataclass(frozen=True)`, mutation uses
`object.__setattr__(cfg, "agent_dry_run_mode", False)`.

`POST /agent/commit-activation` is the permanent activation gate. It executes a 6-step
sequence: (1) simulate if no VHP exists, (2) re-verify the Phase 97 3-condition gate
(gate_passed + cert_valid + audit_valid), (3) persist `activation_committed=True` to store
(append-only audit trail), (4) set dry_run=False in-memory via frozen-dataclass bypass,
(5) publish `activation_committed` bus event for fleet-wide notification, (6) compute and
persist the ProtocolMaturityIndex (PMI).

PMI is a 3-level protocol maturity ladder: 0=uninitiated (no simulations), 1=simulated
(simulation log exists + first VHP is simulated), 2=testnet_organic (first VHP is organic +
activation committed). Level 3 (mainnet) is reserved. `GET /agent/protocol-maturity` exposes
PMI + full activation state. Tool #71 `get_protocol_maturity` makes this available to the
BridgeAgent LLM reasoning loop. `VAPIProtocolMaturity` SDK class wraps both endpoints.

Bridge 1430->1438 (+8). SDK 99->103 (+4). **Phase 104 COMPLETE.**

### §9.22 Phase 105: Epistemic Consensus Hardening

Phase 98 W1 documented that `epistemic_consensus_threshold=0.60` is exactly reachable by
ClassJ alone (0.40 class_j + 0.20 supervisor = 0.60 with no triage escalation). An adversary
who suppresses divergence pattern detection below the triage threshold can pass the 1-agent
gate. Phase 105 closes this via two mechanisms:

**W2 — PMI-triggered threshold auto-raise (Phase 104/105 synergy):** When `compute_pmi() >= 1`
and `epistemic_recommended_threshold (0.65) > epistemic_consensus_threshold (0.60)`,
`_epistemic_consensus()` automatically uses 0.65 as the effective threshold. This makes the
Phase 98 W1 mitigation an **emergent property of protocol maturation** — operators who
complete Phase 104 activation automatically gain the hardened threshold without any manual
configuration change.

**W1 — triage_prereq_required guard (opt-in):** When `epistemic_triage_prereq_required=True`,
`_epistemic_consensus()` requires `triage_score > 0.0` before the consensus vote runs.
This closes the 1-agent gate attack vector unconditionally, at the cost of suppressing
epistemic downgrade when no triage signal exists.

`epistemic_threshold_history` provides an immutable audit trail of all threshold changes
(trigger, pmi_at_change, notes), comparable to `enforcement_certificates` in forensic value.
`GET /agent/epistemic-config` exposes effective threshold, pmi_triggered flag, at_risk
boolean, and the audit history. Tool #72 `get_epistemic_config` integrates this into the
BridgeAgent LLM reasoning loop.

Bridge 1438->1444 (+6). **Phase 105 COMPLETE.**

### §9.23 Phase 106: Developer Integration Runbook + SDK Onboarding

Phase 106 closes the developer-facing gap: game studios and tournament operators need a
single-call bootstrap path and composable eligibility integration without reading VAPI
protocol internals.

`VAPIOperatorOnboarding.bootstrap()` is the one-call operator path: it checks current
maturity via `VAPIProtocolMaturity.get_maturity()`, calls `commit_activation()` if not
already committed, then verifies the final state. It returns `BootstrapResult(
fully_bootstrapped=True)` when `activation_committed=True AND pmi >= 1`. The class
composes `VAPIProtocolMaturity` and never raises — errors surface in `BootstrapResult.error`.

`VAPITournamentIntegration.request_game_demo(device_id, wallet)` is the game developer
integration primitive. It composes `VAPITournamentClient.check_player()` and wraps the
response in `TournamentEntryResult` with `entered=is_eligible AND has_valid_vhp`. The
`demo_mode=True` flag signals that eligibility is advisory — operators enable hard-gate mode
by verifying `separation_ratio > 1.0` (currently 0.362, documented §8.6).

SDK_VERSION updated to `3.0.0-phase106`. SDK 103->109 (+6). **Phase 106 COMPLETE.**

---

### §9.24 Phase 107: Live Mode Readiness Validation (N=100 Corpus)

Phase 107 delivers the final software-only precondition for tournament deployment:
machine-verifiable proof that the system processes N=100 nominal sessions with zero false
positives under live mode conditions.

`LiveModeReadinessValidator.run_validation(n=100)` runs N synthetic NOMINAL sessions
through `SessionAdjudicator._rule_fallback()` with the `agent_dry_run_mode` flag respected.
A BLOCK verdict on nominal evidence (enrollment_status="eligible", no hard cheat codes,
no advisory codes) constitutes a false positive. The validator stores a machine-verifiable
report in the `live_mode_readiness_reports` table.

**`ready_for_live` is a strict AND gate over five conditions:**

| Condition | Software |
|-----------|---------|
| `n_tested >= 100` | 100 nominal sessions evaluated |
| `false_positive_count == 0` | Zero nominal BLOCKs |
| `activation_committed == True` | Phase 104 persistence confirmed |
| `dry_run_active == False` | Agent enforcing live mode |
| `pmi >= 1` | Protocol Maturity Index at simulated tier |

**W1 addressed (Phase 104 PMI drift):** `compute_pmi()` previously returned PMI=1 even
after the anchoring simulation VHP expired (90-day TTL). Phase 107 adds an expiry guard:
`compute_pmi()` returns 0 when `is_simulation=True AND is_valid=False` — the simulation
VHP has expired and no organic VHP exists. This closes the PMI persistence window.

**W1 isolation invariant:** `live_mode_readiness_reports` is a separate table from
`ruling_validation_log`. The readiness validation corpus never increments `consecutive_clean`
counts. This isolation follows the Phase 86 precedent (`synthetic_sessions` table).

**Phase 86 vs Phase 107 distinction:** Phase 86 (`ValidationCorpusRunner`) validates
`_rule_fallback()` regression — nominal sessions should remain CERTIFY across code changes.
Phase 107 certifies readiness to operate the full agent fleet in live mode — a system-level
gate requiring activation_committed, PMI, and dry_run deactivated.

Two new REST endpoints: `POST /agent/run-readiness-validation` (triggers validator),
`GET /agent/live-mode-readiness` (returns latest report). Tool #73 `get_live_mode_readiness`
exposes the gate to the BridgeAgent for autonomous monitoring.

SDK: `LiveModeReadinessResult @dataclass(slots=True)` (8 fields) + `VAPILiveModeValidator`
(run_validation/get_latest; never raises). SDK_VERSION updated to `3.0.0-phase107`.

Phase 106 docs gap closed: `docs/operator-onboarding-runbook.md` and
`docs/developer-integration-guide.md` created (bootstrap sequence, eligibility integration,
honest separation_ratio=0.362 disclosure).

Bridge 1444->1452 (+8). SDK 109->113 (+4). **Phase 107 COMPLETE.**

---

### §9.25 Phase 108: Tournament Readiness Scorecard (7-Condition AND Gate)

Phase 107 certified the software P0 conditions: N=100 nominal sessions, zero false
positives, `ready_for_live=True`. Two hardware-only blockers remain: separation ratio
0.362→required >1.0 (touchpad recapture + N-player calibration) and touchpad recapture
completion. Previously, no single endpoint surfaced all conditions together with a unified
`fully_ready` verdict. Phase 108 delivers the **Tournament Readiness Scorecard**.

**`GET /agent/tournament-readiness`** — 7-condition AND gate:

| # | Category | Condition | Current |
|---|----------|-----------|---------|
| 1 | Software | `n_tested >= 100` | Phase 107 P0 gate |
| 2 | Software | `false_positive_count == 0` | Phase 107 P0 gate |
| 3 | Software | `activation_committed == True` | Phase 104 persist |
| 4 | Software | `dry_run_inactive == True` | Phase 97 gate |
| 5 | Software | `pmi >= 1` | Phase 104 PMI |
| 6 | Hardware | `separation_ratio_current > 1.0` | **BLOCKER (0.362)** |
| 7 | Hardware | `touchpad_recapture_complete == True` | **BLOCKER** |

`fully_ready = (software_conditions_met == 5) AND (hardware_conditions_met == 2)`.

**W1 — Manual override risk:** `separation_ratio_current` is a config field
(`SEPARATION_RATIO_CURRENT` env var, default 0.362). An operator could manually set it to
1.1 to get `fully_ready=True` without real calibration data. Mitigation: the scorecard
always displays `separation_ratio_current` explicitly; every query persists a timestamped
`tournament_readiness_snapshots` row (audit trail); the field default is the Phase 57
empirical baseline (0.362); documentation warns that only `interperson_separation_analyzer.py`
output is authoritative.

**W2 — Certification path audit trail:** `tournament_readiness_snapshots` creates a
timestamped record of every scorecard query. As hardware sessions accumulate and
`separation_ratio_current` is updated, the history charts the "certification path" from
0.362 → 1.0 — evidence for investor/partner readiness claims.

Store: `tournament_readiness_snapshots` table + `insert_tournament_readiness_snapshot()` +
`get_latest_tournament_readiness_snapshot()` + schema (108, "tournament_readiness").

Config: `separation_ratio_current: float` (env `SEPARATION_RATIO_CURRENT`, default 0.362) +
`touchpad_recapture_complete: bool` (env `TOUCHPAD_RECAPTURE_COMPLETE`, default False).

BridgeAgent: Tool #74 `get_tournament_readiness` — returns snapshot when available, or
`{"found": False, "fully_ready": False}` on empty store.

SDK: `TournamentReadinessResult @dataclass(slots=True)` (11 fields) +
`VAPITournamentReadiness.get_scorecard()` (never raises) + SDK_VERSION `3.0.0-phase108`.

Distinction from prior phases: Phase 100 `activation-status` covers 5 software steps only;
Phase 107 `live-mode-readiness` covers the N=100 corpus result. Phase 108 is the single
endpoint that combines both software and hardware conditions into the final `fully_ready`
deployment gate.

Bridge 1452->1460 (+8). SDK 113->117 (+4). **Phase 108 COMPLETE.**

---

### §9.26 Phase 109A: ioSwarm Bridge Adapter (Infrastructure + Consensus Foundation)

#### Three Primitives Thesis

VAPI has always held two DePIN primitives: (1) a real-time stream of physically-grounded
PoAC records from certified hardware, and (2) 38 deployed smart contracts providing
verifiable computation on IoTeX L1. Phase 109A introduces the third: **ioSwarm** — IoTeX's
decentralised agent execution layer — as an optional fourth epistemic signal behind the
already-live Epistemic Consensus Protocol.

The integration is infrastructure-only in Phase 109A. No agent migrates in this phase;
the fleet stays at 14. `ioswarm_enabled=false` (default) leaves every Phase 98 behavior
100% unchanged.

#### IoSwarmConsensusAggregator

`IoSwarmConsensusAggregator.aggregate(node_verdicts)` implements multi-node quorum with
two W1 mitigations:

| Invariant | Value | Rationale |
|-----------|-------|-----------|
| `GENERAL_QUORUM` | 0.60 | Matches Phase 98 epistemic threshold |
| `BLOCK_QUORUM` | 0.67 | W1: higher bar for enforcement verdicts |
| Tie resolution | → HOLD | Never auto-BLOCK on ambiguity |
| HOLD escalation | 3 consecutive HOLDs | Advisory flag; never auto-promotes to BLOCK |

Verdict → score mapping used as epistemic signal:
- BLOCK → 1.0, FLAG/HOLD → 0.5, CLEAR/CERTIFY → 0.0

#### Epistemic Consensus Extension (4th Signal)

When `ioswarm_enabled=True` and `swarm_score > 0.0`, the Phase 98 weights are rebalanced:

| Agent | Disabled (Phase 98) | Enabled (Phase 109A) |
|-------|---------------------|----------------------|
| ClassJDetector | 0.40 | 0.35 |
| DivergenceTriageAgent | 0.40 | 0.35 |
| AgentSupervisor | 0.20 | 0.15 |
| IoSwarm consensus | 0.00 | 0.15 |
| **Sum** | **1.00** | **1.00** |

The Phase 98 three-signal formula is completely unchanged when ioswarm is disabled or
returns no data. The injection is backward-compatible and additive-only.

#### VHP Authorization Gate

The `VAPISwarmTaskSpec` includes a VHP authorization gate:
```json
{
  "contract": "VAPIProtocolLens",
  "method": "isFullyEligible(bytes32)",
  "address": "0x1972bf756aFE0FFCfaF9842e2FbBb2B084352EAf"
}
```
This ensures that any ioSwarm executor operating against VAPI must pass through the same
composable `isFullyEligible()` gate that game developers use, making the authorization
model consistent across the entire protocol stack.

#### W3bstream Applet Binding

The two existing W3bstream applets are now registered as ioSwarm task pipeline entries in
`scripts/vapi-swarm-agent.json`:
- `validate_poac_record` — 228B PoAC parse + ECDSA-P256 verify + PITLSessionRegistryV2 binding
- `process_gsr_packet` — GSR packet parse + VAPIGSRRegistry.recordSample() binding

These applets were code-complete from Phase 99B; Phase 109A formally registers them in the
ioSwarm task spec without changing their implementation.

#### Phase 109B Preview

Phase 109B migrates `VHPRenewalAgent` as the first task spec migration (lowest complexity:
pure polling, no latency constraint). The migration order ends with `SessionAdjudicator`
(last, highest complexity: reactive interrupt + quorum latency budget).

Bridge 1464->1472 (+8). SDK 117->121 (+4). **Phase 109A COMPLETE.**

---

### §9.27 Phase 109B → Phase 238: Operator Initiative, FROZEN-v1 Primitive Family, On-Chain Activation Arc

The arc from Phase 109B through Phase 238 (2026-03 → 2026-05-10) carries VAPI from a single-agent autonomous fleet operating in dry-run mode to a three-agent Operator Initiative fleet (Sentry / Guardian / Curator) operating in shadow mode against IoTeX testnet, backed by nine FROZEN-v1 cryptographic primitives in a unified family designated **PATTERN-017**. The whitepaper §9.27 captures the architectural shape at a level appropriate for an external reader; CLAUDE.md NOTE entries carry the per-phase delta record.

**FROZEN-v1 primitive family (PATTERN-017 v1, post Phase 238).** Each primitive is a SHA-256 commitment over a domain-tagged pre-image whose byte layout is permanently frozen at v1; a future format change requires a new domain tag string and a new (v2) primitive: (1) **GIC** Grind Integrity Chain (Phase 235-A) — 32-byte chain hash over 100 grind sessions; head `0x0e9d453d…` permanently anchored on AdjudicationRegistry 2026-05-06; (2) **WEC** Watchdog Event Chain (Phase 236-WATCHDOG) — operational continuity chain over bridge restart events; (3) **VAME** Application-Layer Message Envelope (Phase 236-VAME) — per-response sidecar commitment binding response to GIC chain head; (4) **CORPUS-SNAPSHOT** (Phase 237.5 + Path X) — wiki + agent + ratio + corpus_n commitment, anchored as `b"VAPI-CORPUS-SNAPSHOT-v1"` deviceIdHash on AdjudicationRegistry; (5) **CONSENT** (Phase 237-CONSENT) — per-category gamer-self-sovereign consent with FROZEN 4-category enum (TOURNAMENT_GATE / ANONYMIZED_RESEARCH / MANUFACTURER_CERT / MARKETPLACE), backed by VAPIConsentRegistry LIVE; (6) **BIOMETRIC-SNAPSHOT** (Phase 237-ZK-SEPPROOF) — Groth16 separation-proof snapshot binding AIT corpus N=37 ratio=1.199 to a ZK-attested artifact; Groth16VerifierZKSepProof + ZKSepProofVerifier wrapper LIVE; (7) **LISTING-v1** (Phase 238) — Provenance-Anchored Listing Layer for the data marketplace, with tier multiplier (1.0×/1.5×/2.0×/3.0×) computed cryptographically via IAdjudicationRegistry.isRecorded() so sellers cannot self-attest; VAPIDataMarketplaceListings LIVE; (8) **FRR** Fleet Readiness Root (Phase O1-FRR-PARALLEL) — SHA-256 commitment over sorted (agent_id, phase_code) pairs, bridge-side primitive providing operator-facing fleet phase alignment surface; (9) **ZKBA** (Phase O3-ZKBA-TRACK1; covered in §9.28) — Zero-Knowledge Biometric Artifact.

**Operator Initiative — three-agent shadow fleet.** Phase O0 (April 2026) registered two Operator Agents on-chain via Q9-frozen agentIds (AnchorSentry `0xb21e1ec2…`, Guardian `0xbd8c7fba…`) + ioID DIDs + ERC-6551 token-bound accounts. Phase O1 C1 (May 2026, commit `a02bcdb3`) dual-anchored their Cedar policy bundles on both AgentScope (operational) + AgentRegistry (governance), elevating both agents from Phase O0 (defined-only) to Phase O1 SHADOW (Cedar policy enforcement live in shadow mode; reads permitted, writes drafted-only, on-chain mutations forbidden). Sessions 1+2+3 (2026-05-09) added the third agent Curator (`0xed6a2df5…`) + minted the inaugural VHP demo token + deployed the Phase 237-ZK-SEPPROOF verifier stack + permanently anchored the inaugural CORPUS-SNAPSHOT — the Sentry+Guardian+Curator triplet is the first ≥3-agent Operator fleet in any DePIN gaming protocol, with cross-agent skill separation enforced procedurally via three distinct Cedar bundles whose policies define overlapping but non-coinciding lane-prefix permits. Phase O1-FRR-PARALLEL shipped the parallel-anchor operator script + closed two latent V-check store-helper gaps + hardened cedar bundle anchor gas buffer (1.20→1.25 for IoTeX storage-heavy operations). The remaining gates from O1_SHADOW → O2_SUGGEST → O3_ACTING are EXTERNAL to the protocol code (shadow_age clearing 504h, ≥50 drafts per agent, operator review with disagreement_rate <5%, KMS/HSM/GitHub-App OAuth/setCurator role flags).

**Architectural Discipline (VAD) framework.** Phase O1-VBDIP-0001-INTEGRATION (2026-05-10, commit `d6830525`) closes the VBDIP-0001 freeze cycle introducing the three-sub-discipline VAD framework: **VSD** (synthesis, post-bootstrap), **VED** (engineering, retroactive over the existing PV-CI invariant ladder), **VBD** (bridge composition). The integration shipped via a five-step secure resumption procedure: (1) Provenance Pin manifest as deferral-boundary witness; (2) Inventory Normalization importing absent methodology artifacts + reconciling untracked files; (3) State Reconciliation Amendments to draft documents canonicalizing PATTERN-017 count + VED-INV-N count-abstraction; (4) Architect Ed25519 key generation + bridge wallet EIP-191 attestation establishing a deployer-anchored signing chain (architect pubkey `056e695f…` chained to bridge wallet `0x0Cf36dB5…` via EIP-191 signature recorded at `vsd-vault/eval/architect_key_attestation.json`); (5) VBDIP-0001 atomically frozen with architect signature applied to the canonical hash. VBD-INV-001/002/003 register in `scripts/vapi_invariant_gate.py` as the first VBD-class invariants; the harness extends with a `--proposal-type` flag (4 choices: protocol/bridge/synthesis/all) enabling per-class invariant evaluation.

---

### §9.28 Phase O3-ZKBA-TRACK1: Zero-Knowledge Biometric Artifact Primitive

Phase O3-ZKBA-TRACK1 (2026-05-10 → 2026-05-11) ships the tenth FROZEN-v1 primitive **ZKBA** (Zero-Knowledge Biometric Artifact) in the PATTERN-017 family per VBDIP-0002 sidecar `wiki/methodology/VBDIP-0002-zkba-visual-projections.md`. ZKBA is a deterministic, privacy-preserving, cryptographically anchored visual projection artifact category that composes existing FROZEN-v1 primitives (PoAC body hash, GIC head, VHP commitment, biometric snapshot, consent hash, listing hash where applicable) into stakeholder-facing surfaces without leaking the underlying biometric corpus. The primitive ships in two tracks: Track 1 (wallet-free, this phase) ships the primitive infrastructure, store schema, deterministic UI compiler, GIC Continuity Ledger Alpha artifact, MCP tools, SDK client, PV-CI invariants, and bridge HTTP endpoints. Track 2 (operator-gated, ~0.23 IOTX) ships Cedar v2 bundles with new lane prefixes (`zk_artifacts/`, `zk_verifications/`, `zk_listings/`), FSCA contradiction rules (`ZKBA_PROOF_WEIGHT_MISMATCH`, `ZKBA_LANE_VIOLATION`, `ZKBA_VERIFICATION_KEY_STALE`), parallel ZKBA anchor script, and Cedar bundle re-anchoring ceremony — all gated on VBDIP-0002 §8 activation criteria (six gates including operator explicit gate-by-gate authorization + kill-switch lift via three-factor procedure + wallet balance ≥1.0 IOTX + no active HIGH/CRITICAL FSCA contradictions).

**FROZEN-v1 wire format (PATTERN-017 #10).** `commitment = SHA-256(b"VAPI-ZKBA-ARTIFACT-v1" || zkba_class_byte || proof_weight_byte || n_components_byte || sorted(component_hashes) || ts_ns_be(8))`. Domain tag `b"VAPI-ZKBA-ARTIFACT-v1"` is 21 bytes, FROZEN; uniqueness against the nine pre-existing `VAPI-*-v1` tags verified at C2 ship time and pinned by PV-CI invariant INV-ZKBA-002. `ZKBAClass` IntEnum FROZEN at 7 values (AIT=1 / GIC=2 / VHP=3 / HARDWARE=4 / CONSENT=5 / TOURNAMENT=6 / MARKET=7); `ProofWeightClass` IntEnum FROZEN at 6 values (DIRECT_HID=1 / CALIBRATION_PLUS_CONTEXT=2 / CHAIN_ONLY=3 / MARKETPLACE_DERIVED=4 / DEMO=5 / FROZEN_DISABLED=6). The first artifact target — **GIC Continuity Ledger Alpha** at `scripts/zkba_compile_gic_ledger.py` — composes the ZKBA commitment with a single 32-byte component (the GIC head hash) at `ProofWeightClass.CHAIN_ONLY`, producing a deterministic HTML projection + manifest under `frontend/src/artifacts/gic_continuity_ledger/<commitment_hex>/` with no fresh biometric capture and no chain submission.

**Deterministic UI compiler discipline (`scripts/vsd_ui_compiler.py`).** Pinned by PV-CI invariant INV-ZKBA-003 against the manifest schema literal `"vapi-zkba-manifest-v1"`. Forbidden imports (verified by static grep + runtime test): `datetime`, `time`, `random`, `urllib`, `requests`, `socket`, `http.client`. Sorted-key canonical JSON serialization at every input boundary. Byte-stable HTML output: same inputs + same compiler version produce byte-identical output. SHA-256 of output emitted into the projection manifest. Twice-compile diff returns 0 bytes; tampering any input byte produces a different output hash. Compiler version FROZEN at `0.1.0`.

**Wire-locked SDK + bridge endpoint surface.** `VAPIZKBA` SDK client (sdk/vapi_sdk.py:9170+) ships three methods (`status()` / `get_artifact(commitment_hex)` / `history(limit=20)`) returning slotted Result dataclasses with `error` field; never raises (matches VAPIDraftReview / VAPIFleetReadinessRoot fail-open pattern). SDK_VERSION bumped to `3.1.0-phase-o3-zkba-track1-c4-sdk`. Bridge HTTP endpoints (`GET /operator/zkba-status` + `GET /operator/zkba-artifact/{commitment_hex}` + `GET /operator/zkba-history`) close the wire-contract loop in the post-C5 follow-up commit (`c2510883`); read-key auth via `x-api-key` Header; get-artifact on miss returns 200 + `found=False` rather than 404 (the SDK consumes the boolean). Three MCP tools (`vapi_zkba_status`, `vapi_compile_zkba_artifact`, `vapi_zkba_projection_manifest`) wrap the same surface for Claude Code + agent-loop consumption; no `chain.py` import in any MCP handler (Track 1 invariant verified by static grep).

**Track 1 invariant.** `anchor_tx_hash IS NULL` across all `zkba_artifact_log` rows throughout Track 1. The status endpoint surfaces `track1_invariant_holds = (anchored_count == 0)` as a boolean so external tooling can verify the invariant without re-scanning the table. Population of `anchor_tx_hash` is deferred to Stream A3 (`scripts/parallel_zkba_anchor.py`) post-§8 gate.

Bridge 2922→2942 (+20 cumulative across the eleven-commit C1–C5 + endpoints arc). SDK 543→550 (+7). PV-CI 63→69 (+3 VBD invariants + 3 ZKBA invariants). Hardhat 528 unchanged. Wallet zero impact (Track 1 fully wallet-free). **Phase O3-ZKBA-TRACK1 (Track 1) COMPLETE; Track 2 GATED.**

---

## 10. Discussion and Future Work

### 10.1 Real-Hardware Adversarial Validation

**Addressed (2026-03-07).** The adversarial validation gap identified in earlier versions
of this paper has been closed for the three-player case:

- **N=69 biometric calibration** — 69 DualShock Edge sessions captured at 1000 Hz across
  3 distinct players; L4/L5 thresholds derived empirically via `scripts/threshold_calibrator.py`
- **6-attack adversarial suite** — 55 sessions generated by deterministic transforms of
  real captures; full L2/L4/L5 pipeline validated (see Table 5, §8.3)
- **Detection rates:** injection 100%, macro 100%, quant-masked 100%, warmup 60%
- **Human false positive rate:** 2.9% (2/69 — within 3σ statistical expectation)
- **Stationary control baseline** — 30s idle controller capture confirming IMU noise
  floor (gyro std 1.3–1.5 LSB) and 14,000× injection detection margin

- **L6 Active Physical Challenge-Response implemented** — 8-profile trigger challenge
  library, async trigger driver, motor-response curve analyzer, Attack G adversarial
  unit tests. Human response baseline calibration is the remaining open item (§10.6).
- **PHGCredential auto-expiry fix** — `isActive()` now honors `suspendedUntil`
  timestamp; `suspend()` allows re-suspension after auto-expiry without requiring
  `reinstate()`. 354 Hardhat tests passing (+2 auto-expiry tests). Also: CEI pattern
  in `PoACVerifier._verifyInternal()` confirmed correct and documented with comment.

**Remaining work:**
- Professional bot software (aimbot trajectories, macro tools) as labeled adversarial data
- Skill-tier diversity (Bronze through Diamond) to validate false positive rate across
  play styles rather than a single player's sessions
- Recapture sessions after Phase 17 so touchpad features (now populated) contribute to
  inter-person separation

### 10.2 Toward Full-ZK PoAC

As zkML tooling matures, PoAC could incorporate succinct proofs of correct inference
execution per cognition cycle, upgrading model attestation from "the device claims to
have used model $\mathcal{M}$" to "the device provably executed $\mathcal{M}$ on input
$x$." The primary barrier is prover time on embedded hardware. Application-specific
circuits for fixed TinyML architectures and hardware ZK accelerators could make this
feasible within 3–5 years.

### 10.3 Multi-Instance Trusted Setup

**Phase 67 status: MPC ceremony implemented.** `contracts/scripts/run-mpc-ceremony.js`
runs a 3-contributor Groth16 Phase 2 ceremony for all three VAPI circuits (PitlSessionProof,
TeamProof, TournamentPassport) using the publicly-audited Hermez `powersOfTau28_hez_final_15.ptau`
(200+ contributors, 2021) as Phase 1 input. The Phase 2 final beacon is the hash of an
IoTeX testnet block at ceremony time — independently verifiable by querying block N on IoTeX
testnet. `CeremonyRegistry.sol` stores the verifyingKeyHash, beaconBlockHash, and contributor
transcript (sha256(zkey_i)) for all three circuits on-chain, creating a permanent
cryptographically-auditable record. `ZKVerifier` in the bridge pre-verifies Groth16 proofs
locally via a Node.js subprocess before submitting to PITLSessionRegistryV2, eliminating
gas waste on invalid proofs. The `VAPIZKProof.verify_ceremony_integrity()` SDK method allows
any third party to verify that a local verification key matches the on-chain MPC commitment.

**Post-Phase-67 ZK trust chain:**
```
DualShock Edge → PoAC 228B → SHA-256(164B) chain hash
  → Groth16 proof → MPC ceremony key (3 contributors) → CeremonyRegistry.sol
    → IoTeX block beacon → IoTeX testnet L1
```
Every link is cryptographically verifiable. The ZK ceremony is no longer an external
trust assumption — it is part of the VAPI on-chain evidence chain.

### 10.4 Full Covariance Biometric Fingerprinting

The current L4 classifier uses a diagonal covariance assumption (7 independent variances).
A full 7×7 covariance matrix would capture cross-feature correlations (e.g., trigger
onset velocity is correlated with grip asymmetry for a given player) and improve
both sensitivity and specificity. The `controller/tinyml_biometric_fusion.py` TODO
comment documents this as the next algorithmic improvement.

### 10.5 Formal Verification

The PoAC chain integrity properties (linkage, monotonicity, non-repudiation) are
amenable to formal verification in TLA+ or Isabelle/HOL. Machine-checked proofs would
strengthen confidence for safety-critical esports deployments.

### 10.6 L6 Human Response Baseline Calibration

L6 Active Physical Challenge-Response (§7.5.2) uses onset/settle thresholds and
classification weights derived from general biomechanical priors. The next hardware
validation milestone is a calibration study analogous to the N=69 biometric
calibration (§8.4) but targeting the challenge-response dimension:

1. **Capture N≥50 challenge sessions** — run `L6_CHALLENGES_ENABLED=true` with a
   live DualShock Edge, dispatching all 8 profiles across gameplay sessions
2. **Characterize human distributions** — fit onset_ms, settle_ms, peak_delta,
   grip_variance distributions per profile; derive profile-specific thresholds
3. **Attack G ground truth** — collect replay-injection sessions with L6 active;
   measure false negative rate under Attack G
4. **Update `CHALLENGE_PROFILES`** — replace engineering-estimate thresholds with
   measured mean ± 3σ values via a `scripts/l6_threshold_calibrator.py` script
   analogous to `scripts/threshold_calibrator.py`

Until this calibration is performed, L6 is recommended as a supplementary layer
only (`L6_CHALLENGES_ENABLED=false` default) and should not be used as a primary
gating signal for tournament qualification.

### 10.7 Multi-Person Biometric Calibration (Transplant Attack Validation) — Updated

The N=69 calibration corpus now spans 3 distinct players (hw_005–hw_073). Inter-person
Mahalanobis separation has been computed (separation ratio 0.362 — see
docs/interperson-separation-analysis.md). The result is honest: L4 does not currently
separate players. Phase 46 replaced `touchpad_active_fraction` (structurally zero across
all N=69 sessions) with `accel_magnitude_spectral_entropy` (zero-fraction 0%, mean 4.93 bits).
However, per-player entropy means are nearly identical (P1: 4.878, P2: 4.882, P3: 4.767 bits),
confirming this new feature does not improve inter-person separation — it is a bot-vs-human
discriminator only. Two of eleven features remain structurally zero (trigger_resistance_change_rate,
touch_position_variance). Phase 49 widened the tremor FFT ring buffer from 513 to 1025
positions (512→1024 velocity samples), improving resolution from 1.95 Hz/bin to
0.977 Hz/bin — 4 bins now span the 8–12 Hz physiological tremor band. The live warm-up
latency increased from ~0.5s to ~1.0s. Tremor FFT detection of Attacks G/H/I in the
batch proxy: G/I remain 0% (G preserves right_stick_x; I uses PSD-matching); H remains
100%. The next milestone is validating whether the improved tremor resolution achieves
inter-person separation.

---

## 11. Conclusion

We have presented VAPI — a system providing verifiable provenance for controller input
composed with physics-backed liveness detection. PoAC's 228-byte chained evidence record
captures the complete cognitive context: what was sensed, what model produced the inference,
what the agent's accumulated world model contained at decision time, and what action was
taken — all committed, signed, hash-chained, and anchored on a public blockchain. Any
third party can verify the origin, ordering, and integrity of a session's evidence log
without trusting the bridge or any other intermediary.

The DualShock Edge's motorized adaptive trigger surface is the key physical primitive: a
PoAC chain anchored to resistance dynamics, six-axis IMU, and stick kinematics cannot be
reproduced by software injection. The nine-level PITL stack exploits signals grounded in
physics: IMU gravity (absent in injected data), IMU-button causal latency (present only
when a physical hand precedes each press), stick-IMU temporal cross-correlation (present
only when a physical hand couples stick movement to body sway), biometric kinematic
fingerprinting (individual-specific across 12 features), temporal rhythm analysis (human
timing variance cannot be faked with constant-interval scripting), and active haptic
challenge-response (onset latency, grip variance, and settling behavior are involuntary
biomechanics that software cannot sense or replicate).

The PHG humanity credential is a *living* proof: earned through sustained clean behavior,
weighted by biometric quality, portable across key rotations through biometric continuity,
and provisionally suspended when retrospective memory accumulates evidence of sustained
adversarial behavior. Mode 6 living calibration (Phase 38) adds a new class of
self-improvement: the system evolves its own detection thresholds from verified session
data every 6 hours, with per-player profiles that tighten detection for known players
without ever loosening it — a credential that improves with every verified session.

The complete system (~220 files, ~1,413 automated tests including 28 on physical hardware)
demonstrates the concept is implementable today with existing gaming controller hardware
and existing blockchain infrastructure. Fifteen contracts are deployed on IoTeX testnet.
Live hardware validation confirms the foundational physical signal claims: USB polling at
1002 Hz, gyro noise 14,000× above the stationary-control baseline, 278,239 LSB² accel
variance from natural hand micro-tremor, and zero report-counter violations across 200
consecutive reports.

Honest limits: L4 is an anomaly detector, not a player identifier, with the current
feature set and single-game corpus. The ZK proof does not bind inference codes on-chain.
L6 human-response thresholds lack empirical calibration. The bridge remains operationally
trusted despite ZK constraints.

VAPI opens a design space where provenance and physical plausibility of gaming sessions
are verifiable — not assumed. The infrastructure to extend, recalibrate, and strengthen
every layer of this system ships with this release.

---

## References

[1] Sami, H., et al. "Decentralized Physical Infrastructure Networks (DePIN): A Systematic Survey." *IEEE Communications Surveys & Tutorials*, vol. 26, no. 2, 2024.

[2] Haleem, A., et al. "Helium: A Decentralized Wireless Network." *Proc. ACM HotNets*, 2021.

[3] Hivemapper. "Hivemapper: A Decentralized Global Mapping Network." 2022.

[4] Fan, Q., et al. "IoTeX 2.0: The Network for DePIN." IoTeX Foundation Technical Report, 2024.

[5] Nakamoto, S. "Bitcoin: A Peer-to-Peer Electronic Cash System." 2008.

[6] Pinto, S. and Santos, N. "Demystifying ARM TrustZone: A Comprehensive Survey." *ACM Computing Surveys*, vol. 51, no. 6, 2019.

[7] Birkholz, H., et al. "Remote Attestation Procedures Architecture." IETF RFC 9334, 2023.

[8] DIMO. "DIMO: The Digital Infrastructure for Moving Objects." 2023.

[9] Costan, V. and Devadas, S. "Intel SGX Explained." *IACR Cryptology ePrint Archive*, 2016/086.

[10] Trusted Computing Group. "DICE Layered Architecture." TCG Specification, 2020.

[11] Groth, J. "On the Size of Pairing-Based Non-interactive Arguments." *Proc. EUROCRYPT*, 2016.

[12] Kang, D., et al. "Scaling up Trustless DNN Inference with Zero-Knowledge Proofs." *Proc. OSDI*, 2024.

[13] EZKL. "EZKL: Easy Zero-Knowledge Inference." https://ezkl.xyz, 2024.

[14] Breidenbach, L., et al. "Chainlink 2.0." Chainlink Whitepaper, 2021.

[15] McConaghy, T., et al. "Ocean Protocol." Ocean Protocol Foundation, 2020.

[16] Rao, A.S. and Georgeff, M.P. "BDI Agents: From Theory to Practice." *Proc. ICMAS*, 1995.

[17] Brooks, R.A. "A Robust Layered Control System for a Mobile Robot." *IEEE J. Robotics Autom.*, 1986.

[18] Yao, S., et al. "ReAct: Synergizing Reasoning and Acting in Language Models." *ICLR*, 2023.

[19] Kang, A.R., Jeong, S.H., Mohaisen, A., and Woo, J. "Analyzing and Detecting Game-Bot Exploits in Massively Multiplayer Online Role-Playing Games." *Security and Communication Networks*, vol. 9, no. 16, 2016, pp. 3452–3463.

[20] Blackburn, J., Kourtellis, N., Skvoretz, J., Ripeanu, M., and Iamnitchi, A. "Cheating in Online Games: A Social Network Perspective." *ACM Trans. Internet Technol.*, vol. 13, no. 3, 2014.

---

## Appendix A: DePIN Economic Layer

VAPI's DePIN layer demonstrates that PoAC extends naturally to non-gaming sensor domains
without protocol changes. An IoTeX Pebble Tracker (nRF9160 SiP, ARM Cortex-M33 @ 64 MHz,
CryptoCell-310) performs autonomous bounty participation: it discovers active environmental
monitoring tasks on-chain, evaluates fit against available time and energy budget, accepts
the best-fit task, and preempts lower-value tasks when higher-value opportunities arrive
mid-session. Each economic decision — accept, continue, preempt — generates a PoAC record
committed with the same 228-byte wire format, device-key ECDSA-P256 signature, and
on-chain anchoring used for gaming sessions. The DePIN layer thus validates two design
claims simultaneously: (1) PoAC is device-agnostic — the same verification mechanism
serves both gaming controller inputs and environmental telemetry; and (2) economic
decision-making (not just raw sensing) is attestable within the PoAC framework.

**Bounty evaluation.** Available tasks form a knapsack instance over device capacity.
Each task carries a reward *r*, expected duration *d*, and geographic zone *z*. The
greedy evaluator selects the highest reward-per-second task fitting within the remaining
session window and preempts the current task when a new opportunity offers ≥ 1.5× the
active reward rate. Over 1,000 synthetic scenarios, this policy achieves a median 97.1%
of optimal total reward (mean 94.2%, worst-case 81.3%) in 0.14 ms mean decision time on
the nRF9160 (cycle-accurate emulation). The preemption threshold fires in 12.7% of
scenarios. All DePIN evaluation figures are simulation-derived; real-hardware Pebble
Tracker validation is future work.

---

## Appendix B: BridgeAgent — Complete Tool Catalogue and Interface Specification

`BridgeAgent` (`claude-sonnet-4-6`, `bridge/vapi_bridge/bridge_agent.py`) provides
LLM-powered operator intelligence through 40 deterministic tool bindings. All tools are
read-only against the SQLite store and on-chain state; no tool mutates bridge state.

### B.1 Tool Catalogue

| Tool | Returns |
|------|---------|
| `get_player_profile` | PHG score, checkpoint count, risk label, credential status |
| `get_leaderboard` | Top-N devices by confirmed PHG score |
| `get_leaderboard_rank` | Single device rank within leaderboard |
| `run_pitl_calibration` | L4/L5 threshold suggestions from live DB distribution |
| `get_continuity_chain` | Session continuity attestation history for a device |
| `get_recent_records` | Last N PoAC records with PITL inference codes |
| `get_startup_diagnostics` | ZK artifact presence, contract addresses, feature flags |
| `get_phg_checkpoints` | Full PHG checkpoint chain (up to limit 50) |
| `check_eligibility` | Tournament eligibility: PHG score + credential active |
| `get_pitl_proof` | Latest ZK PITL session proof row |
| `get_behavioral_report` | `BehavioralArchaeologist` analysis: drift slope, warmup, burst |
| `get_network_clusters` | `NetworkCorrelationDetector` clusters filtered by min suspicion |
| `get_federation_status` | Peer count, cross-confirmed clusters, federation enabled |
| `query_digest` | `InsightSynthesizer` digest for 24h / 7d / 30d window |
| `get_detection_policy` | Active L4 threshold multiplier and basis risk label |
| `get_credential_status` | Evidence chain: biometric label → suspension state → reinstatement conditions |
| `get_calibration_status` | Global L4 thresholds, per-player profiles, recent threshold evolution, next Mode 6 cycle timing |
| `get_ruling_streak` | Current streak verdict and escalation state for a device (Phase 66) |
| `override_ruling` | Operator CLEAR ruling to reset streak and re-enable tournament eligibility (Phase 66) |
| `get_autonomous_rulings` | All SessionAdjudicator rulings for a device with commitment hashes (Phase 65) |
| `request_adjudication` | Queue a new LLM adjudication request for a device (Phase 65) |
| `get_reflex_baseline` | L6b neuromuscular probe baseline — latency distribution and BOT/HUMAN classification (Phase 63) |
| `get_session_replay` | Retrieve 20 Hz frame checkpoint ring for a device (Phase 61) |
| `get_enrollment_status` | Device enrollment state: session count, avg humanity, PHGCredential mint status (Phase 62) |
| `get_controller_twin_data` | Full 3D twin snapshot: biometric heartbeat, IBI, PoAC DNA, proof anchor (Phase 59) |
| `generate_tournament_passport` | Trigger ZK tournament passport generation for an enrolled device (Phase 56) |
| `get_ioid_status` | ioID device identity DID and session registry state (Phase 55) |
| `get_threshold_history` | Threshold evolution log with per-row drift annotations (Phase 58) |
| `predict_evasion_cost` | Model minimum feature manipulation to evade L4 detection (Phase 58) |
| `get_anomaly_trend` | L4 anomaly/continuity score trend over recent sessions (Phase 58) |
| `generate_incident_report` | Auto-generated incident narrative for a device's anomaly history (Phase 58) |
| `get_game_profile` | Active game profile (NCAA CFB 26), L5 priority map, L6-Passive stats (Phase 51) |
| `analyze_threshold_impact` | Simulate threshold change impact on current session distribution (Phase 58) |
| `verify_ceremony_integrity` | Verify embedded PITL vkey matches CeremonyRegistry on-chain commitment (Phase 68) |
| `get_suspension_status` | Current PHGCredential suspension state: suspended bool, seconds remaining (Phase 67/68) |
| `get_zk_verifier_stats` | ZKVerifier proof acceptance/rejection/error counters since bridge startup (Phase 68) |
| `get_enrollment_pipeline` | All devices grouped by enrollment state: eligible/in_progress/unenrolled (Phase 68) |
| `request_live_adjudication` | Queue a live (dry_run=False) adjudication request for operator-confirmed devices (Phase 68) |

### B.2 Streaming Interface

`GET /operator/agent/stream` (API-key gated, rate-limited to 60 req/min) returns
Server-Sent Events with the following typed event schema:

| `type` field | Payload |
|-------------|---------|
| `text_delta` | `{text: str}` — incremental reasoning token |
| `tool_start` | `{tool_name: str, inputs: dict}` — visible tool invocation |
| `tool_result` | `{tool_name: str, result: any}` — tool return value |
| `done` | `{session_id: str, tools_used: list[str]}` — completion summary |
| `error` | `{message: str}` — non-fatal error within stream |

The 5-round agentic loop ensures tools can chain (e.g., `get_player_profile` →
`get_behavioral_report` → `get_credential_status` in a single natural-language query).

### B.3 Autonomous Reaction

`BridgeAgent.react(event: dict)` handles `BIOMETRIC_ANOMALY` (0x30) and
`TEMPORAL_ANOMALY` (0x2B) events autonomously. The method:
- Uses an internal session namespace `__react_{device_id[:8]}` (isolated from operator sessions)
- Never raises — all exceptions are caught and returned as error dicts
- Persists each reaction to `protocol_insights` table as an auditable record
- Returns `{alert: str, severity: str, tools_used: list, device_id: str, inference: int}`

### B.4 Session Persistence and History Compression

Session history is stored in the `agent_sessions` SQLite table (schema:
`session_id TEXT PK, history_json TEXT, created_at REAL, updated_at REAL`) and
survives bridge restarts. When history exceeds `AGENT_MAX_HISTORY_BEFORE_COMPRESS`
(default 60, configurable), the compressed portion is replaced with a summary entry:

```
[System: N prior messages compressed. Tools used: tool×count.
 Continue from the 20 most recent messages below.]
```

The tool-use inventory is extracted from the compressed messages before replacement,
preserving operator context across long investigation sessions.

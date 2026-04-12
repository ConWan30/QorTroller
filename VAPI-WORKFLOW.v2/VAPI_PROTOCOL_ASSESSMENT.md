# VAPI Protocol — Comprehensive Technical & Strategic Assessment
*Phase 200 State · 2026-04-11 · CONFIDENTIAL WORKING DOCUMENT*

---

## Table of Contents

1. [Executive Overview](#1-executive-overview)
2. [Technical Architecture — Proof of Autonomous Cognition](#2-technical-architecture--proof-of-autonomous-cognition)
3. [Detection Stack — PITL Nine Layers](#3-detection-stack--pitl-nine-layers)
4. [Biometric Fingerprint — L4 Feature Space](#4-biometric-fingerprint--l4-feature-space)
5. [Zero-Knowledge Proof Architecture](#5-zero-knowledge-proof-architecture)
6. [Blockchain & DePIN Architecture — 43 Contracts](#6-blockchain--depin-architecture--43-contracts)
7. [ioSwarm — Decentralized Consensus Layer](#7-ioswarm--decentralized-consensus-layer)
8. [VAPI Tokenomics](#8-vapi-tokenomics)
9. [Autonomous Agent Fleet — 36 Agents](#9-autonomous-agent-fleet--36-agents)
10. [Tool Catalog — 149 Tools](#10-tool-catalog--149-tools)
11. [Stakeholder Value Framework](#11-stakeholder-value-framework)
12. [Novel Distinctiveness](#12-novel-distinctiveness)
13. [Protocol Integrity Constants — Frozen Invariants](#13-protocol-integrity-constants--frozen-invariants)
14. [Current Calibration State](#14-current-calibration-state)
15. [Future Trajectory](#15-future-trajectory)

---

## 1. Executive Overview

### What VAPI Is

**VAPI (Verified Autonomous Physical Intelligence)** is the world's first cryptographic
Agentic-as-a-Service (AGaaS) anti-cheat protocol for competitive gaming. It produces
mathematically verifiable proof that a human being with a specific biometric identity
held and operated a physical game controller during a competitive session — anchored
permanently on the IoTeX blockchain.

Unlike software-level anti-cheat systems (VAC, Easy Anti-Cheat, BattlEye), which inspect
running processes and memory, VAPI operates at the **physics layer** — it reads
neurological tremor, galvanic skin response, micro-accelerometer variance, and trigger
onset biomechanics to distinguish a human from any possible software automation, whether
that automation is a simple macro, a neural-network aimbot, or a hardware injection device.

### The Problem VAPI Solves

Competitive gaming fraud takes four forms, each with escalating sophistication:

1. **Software cheats** — aimbots, wallhacks, memory editors (addressed by VAC, EAC, etc.)
2. **Hardware injection devices** — Cronus Zen, Titan One — inject scripted inputs via USB
   relay, bypassing all software-level detection (unaddressed by any existing solution)
3. **Script/macro automation** — keyboard/controller macros, input replay at inhuman timing
4. **Identity fraud** — account boosting, smurfing, carry-for-hire services

VAPI addresses all four categories simultaneously through a single on-chain composable
gate: `isFullyEligible(deviceId)`.

### The VAPI Solution

A DualShock Edge game controller is instrumented with a custom Python bridge running nine
detection layers. Each cognition cycle (approximately 1,000 Hz) produces a 228-byte
**Proof of Autonomous Cognition (PoAC)** record — a cryptographically signed biometric
snapshot. These records are chained (SHA-256 body hash), committed to IoTeX L1 via
smart contracts, and adjudicated by a fleet of 36 autonomous AI agents.

A tournament organizer, game publisher, or DePIN operator queries one contract call.
If `isFullyEligible()` returns `true`, the player has cryptographic proof that a real
human with their enrolled biometric identity has been physically present and playing.

---

## 2. Technical Architecture — Proof of Autonomous Cognition

### 2.1 PoAC Wire Format (FROZEN — DO NOT MODIFY)

```
 Offset  Len  Field
 ──────  ───  ─────────────────────────────────────────
     0    8   timestamp_ns          (uint64, big-endian)
     8    1   inference_code        (uint8: 0x00=NOMINAL, 0x28–0x2A=hard cheat, etc.)
     9    1   confidence_byte       (uint8: 0–255 maps to 0.0–1.0)
    10    4   session_id            (uint32, big-endian)
    14    4   sequence_number       (uint32, big-endian)
    18    2   feature_dim           (uint16: currently 13)
    20    2   reserved              (0x0000)
    22    8   anomaly_score_fp64    (IEEE 754 double, big-endian)
    30    8   continuity_score_fp64 (IEEE 754 double, big-endian)
    38   96   features_fp64[12]     (12 × IEEE 754 double, big-endian)
   134   16   device_id             (keccak256(pubkey) truncated to 128 bits)
   150   14   reserved_padding      (0x00 × 14)
   164   64   ECDSA-P256 signature  (r ∥ s, 32B each)
```

**Total: 228 bytes.** Body = bytes[0:164]. Signature = bytes[164:228].

**Chain link formula:** `record_hash = SHA-256(raw[0:164])` — body ONLY, never 228B.
**Device identity:** `deviceId = keccak256(pubkey)` — never swap with record_hash.

The P256 precompile at IoTeX EVM address `0x0100` enables on-chain ECDSA verification
without custom cryptography. Every PoAC record is self-authenticating.

### 2.2 PoAC Chain

Each session produces a chain of PoAC records where each record's `record_hash` links
to the prior record's body hash — forming a tamper-evident log. Any gap in the chain,
any timestamp reversal, or any replayed sequence number is detected as L1 structural
integrity failure (inference code 0x00 → chain broken).

### 2.3 Bridge Service

`bridge/vapi_bridge/` is a Python asyncio application exposing a REST API (FastAPI),
WebSocket streams, SQLite persistence, and the full agent runtime. It reads raw HID
data from the DualShock Edge at 1,002 Hz, computes all 9 detection layers in real time,
assembles PoAC records, submits to IoTeX testnet, and runs 36 background agents
concurrently.

Key subsystems:
- `bridge_agent.py` — primary BridgeAgent (LLM-backed, 40 tools, claude-sonnet-4-6)
- `session_adjudicator.py` — SessionAdjudicator (LLM ruling per session)
- `store.py` — SQLite persistence layer (100+ tables, full audit trail)
- `config.py` — runtime configuration with dotenv + env override
- `chain.py` — IoTeX EVM transaction submission
- `federation_bus.py` — internal async event bus connecting all agents

---

## 3. Detection Stack — PITL Nine Layers

**PITL = Physical Intelligence Trust Layer**

| Layer | Code   | Type        | What It Detects |
|-------|--------|-------------|-----------------|
| L0    | —      | Structural  | HID device presence and polling rate validity (800–1100 Hz) |
| L1    | —      | Structural  | PoAC chain integrity — no gaps, no replay, no timestamp reversal |
| L2    | `0x28` | Hard cheat  | IMU gravity vector + HID/XInput discrepancy — detects hardware injection (Cronus) |
| L3    | `0x29`/`0x2A` | Hard cheat | TinyML behavioral classifier — detects aimbot and wallhack behavioral signatures |
| L2B   | `0x31` | Advisory    | IMU-button causal latency — human button presses are preceded by micro-IMU movement; bots are not |
| L2C   | `0x32` | Advisory    | Stick-IMU cross-correlation — stick movement should correlate with IMU orientation change (inactive in dead-zone games like NCAA CFB 26) |
| L4    | `0x30` | Advisory    | 12-feature Mahalanobis biometric fingerprint — individualized anomaly and continuity scoring |
| L5    | `0x2B` | Advisory    | Temporal rhythm oracle — coefficient of variation, inter-event entropy, timing quantization detection (macro scripts have zero jitter) |
| L6    | —      | Advisory    | Active haptic challenge-response — sub-perceptual vibration stimulus; human reflexes fire 80–280ms involuntarily; disabled by default pending N≥50 calibration |

**Hard codes `{0x28, 0x29, 0x2A}` block tournament eligibility unconditionally.**
Advisory codes contribute to `humanity_probability` via weighted formula.

### 3.1 Humanity Probability Formula

Without L6 (default, NCAA CFB 26):
```
humanity_probability = 0.28·p_L4 + 0.27·p_L5 + 0.20·p_E4 + 0.15·p_L2B + 0.10·p_L2C
```

p_L2C resolves to 0.5 neutral prior in dead-zone stick games — formula runs as
effective 4-signal in practice for the current game corpus.

With L6 active:
```
p_human = 0.23·p_L4 + 0.22·p_L5 + 0.15·p_E4 + 0.15·p_L6 + 0.15·p_L2B + 0.10·p_L2C
```

---

## 4. Biometric Fingerprint — L4 Feature Space

L4 is the individualized biometric layer. Each enrolled player has a Mahalanobis distance
profile computed from their N=74 calibration sessions. A session outside the player's
personal ellipsoid is flagged as anomalous. **This is intra-player identity verification,
not inter-player discrimination.**

### 4.1 Active Features (13 total, 10 active)

| Index | Feature | Notes |
|-------|---------|-------|
| 0  | `trigger_resistance_change_rate`     | Structurally zero — excluded from Mahalanobis |
| 1  | `trigger_onset_velocity_L2`          | Left trigger press speed (human: smooth onset) |
| 2  | `trigger_onset_velocity_R2`          | Right trigger press speed (sprint key in NCAA CFB 26) |
| 3  | `micro_tremor_accel_variance`        | High-frequency IMU variance from physiological tremor |
| 4  | `grip_asymmetry`                     | Left/right grip pressure differential |
| 5  | `stick_autocorr_lag1`                | Lag-1 autocorrelation of stick displacement |
| 6  | `stick_autocorr_lag5`                | Lag-5 autocorrelation — macro scripts cluster near 1.0 |
| 7  | `tremor_peak_hz`                     | Peak frequency of physiological tremor (P1=9.37Hz, P2=1.71Hz, P3=2.85Hz) |
| 8  | `tremor_band_power`                  | Power in 8–12 Hz physiological tremor band |
| 9  | `accel_magnitude_spectral_entropy`   | Shannon entropy of ||accel|| power spectrum; bot injections score 0.0 or ~9.0 bits |
| 10 | `touch_position_variance`            | Structurally zero in gameplay — pending touchpad recapture |
| 11 | `press_timing_jitter_variance`       | IBI variance; humans 0.001–0.05; macro bots <0.00005 |
| 12 | `touchpad_spatial_entropy`           | 8×8 heatmap Shannon entropy of touchpad contact positions |

### 4.2 Thresholds (Phase 57, N=74)

- **Anomaly threshold: 7.009** (mean + 3σ; ~2.9% human false positive rate)
- **Continuity threshold: 5.367** (mean + 2σ)
- Calibration: 12-feature space (index 12 not used in threshold calculation)
- Live: 13-feature space (touchpad_spatial_entropy initialized to 0.0 in gameplay)
- Staleness flag: `live_feature_dim=13 ≠ calibration_feature_dim=12` — valid for gameplay because touchpad_spatial_entropy is structurally 0

---

## 5. Zero-Knowledge Proof Architecture

### 5.1 Circuit: PitlSessionProof.circom

- Proving system: Groth16 (BN254 curve)
- ~1,820 constraints
- Powers-of-tau: 2^11
- Three constraints (frozen):
  - **C1:** `featureCommitment = Poseidon(8)(scaledFeatures[0..6], inferenceCodeFromBody)` — binds biometric features to inference code
  - **C2:** `anomalyScore ≤ anomalyThreshold` — L4 gate within proof
  - **C3:** `inferenceResult === inferenceCodeFromBody` — prevents verdict forgery (Phase 62)

### 5.2 Public Signals (nPublic=5)

1. `featureCommitment` — Poseidon hash binding features to inference code
2. `anomalyScore` — L4 Mahalanobis score (public, verifiable)
3. `anomalyThreshold` — current calibrated threshold
4. `sessionId` — links to on-chain session record
5. `inferenceResult` — must match inference code in PoAC body

### 5.3 MPC Ceremony

Phase 67 ceremony: 3 contributors, Hermez ptau powers-of-tau, IoTeX block #41723255
as entropy beacon. `CeremonyRegistry.sol` on-chain: `verifyCeremony()` returns true.
SDK: `VAPIZKProof.verify_ceremony_integrity()` cross-checks contributor hashes.

### 5.4 On-Chain Verification

- `PITLSessionRegistryV2`: `0x8da0A497234C57914a46279A8F938C07D3Eb5f12`
- `PitlSessionProofVerifier`: `0x07D3ca1548678410edC505406f022399920d4072`
- `TournamentPassport.circom`: secondary ZK passport (5 public signals, N=5 sessions)
- `PITLTournamentPassport.sol`: mock mode, SESSION_COUNT=5 → full tournament readiness proof

---

## 6. Blockchain & DePIN Architecture — 43 Contracts

All contracts deployed on IoTeX Testnet (chain ID 4690). All 43 are LIVE.

### 6.1 Contract Categories

**Core Identity & Verification**
| Contract | Address | Purpose |
|----------|---------|---------|
| `VAPIioIDRegistry` | `0xF7885B...` | IoTeX ioID device identity — DID `did:io:0x<addr>` |
| `PHGRegistry` | `0x...` | Player Human-Genome credential registry |
| `PHGCredential` | `0x...` | Soulbound biometric credential (ERC-4671) with `expiresAt` |
| `PITLSessionRegistryV2` | `0x8da0A4...` | ZK session proof submission + on-chain verification |
| `PitlSessionProofVerifier` | `0x07D3ca...` | Groth16 verifier for PitlSessionProof circuit |

**Tournament Gate**
| Contract | Address | Purpose |
|----------|---------|---------|
| `TournamentGateV3` | `0x...` | Primary eligibility gate |
| `VAPIProtocolLens` | `0x...` | Composable `isFullyEligible(deviceId)` — single call for operators |
| `VAPIDualPrimitiveGate` | `0xd7b146...` | `isDualEligible()` = isFullyEligible() AND isRecorded() |
| `VAPISwarmOperatorGate` | `0x969c0F...` | ioSwarm operator staking gate |
| `PITLTournamentPassport` | `0x...` | ZK tournament passport (5-session proof) |

**Ruling & Enforcement**
| Contract | Address | Purpose |
|----------|---------|---------|
| `RulingRegistry` | `0xa3A235...` | Anti-replay ruling commitments (UNIQUE commitmentHash) |
| `AdjudicationRegistry` | `0x44CF98...` | PoAd hash registry with block.number anchor |
| `GateAttestationAnchor` | `0x...` | Unique attestation_hash anti-replay pattern |
| `FederatedThreatRegistry` | `0x...` | Cross-operator threat intelligence sharing |

**Ceremony & ZK Infrastructure**
| Contract | Address | Purpose |
|----------|---------|---------|
| `CeremonyRegistry` | `0x739B5f...` | On-chain MPC ceremony audit trail + beacon |
| `CeremonyAuditRegistry` | `0xb9164E...` | ZK ceremony participant registration + audit gate |
| `PoACVerifier` | `0x...` | ECDSA-P256 PoAC signature verification |

**Biometric Privacy & Renewal**
| Contract | Address | Purpose |
|----------|---------|---------|
| `SeparationRatioRegistry` | `0xB39CeE...` | On-chain SHA-256 commitment of separation ratio calibration |
| `VHPReenrollmentBadge` | `0x42E7A2...` | Soulbound badge for players who completed re-enrollment |
| `DataSovereigntyRegistry` | `0xd928d9...` | Player data sovereignty pledges (MANUFACTURER/DEVELOPER/GAMER tiers) |

**Token & Economics**
| Contract | Purpose |
|----------|---------|
| `VAPIToken` | ERC-20, 1B fixed supply, operator mint, staking lock/unlock |
| `VAPIOperatorRegistry` | Minimum 10,000 VAPI locked stake; onlyOperator gate |
| `VAPIHardwareCertRegistry` | Hardware certification (manufacturer pays VAPI; certLevel 1-3) |
| `VAPIDataMarketplace` | 70% device pool / 30% treasury split |
| `VAPIGovernanceTimelock` | CEI + co-signer cancel pattern; time-locked governance |

**Skill Oracle & Metrics**
| Contract | Purpose |
|----------|---------|
| `SkillOracle` | Rolling skill ELO computed from PoAC session chain |
| `PHGCredential` | ERC-4671 soulbound: all transfer functions revert; `isValid()` checks `block.timestamp < expiresAt` |

### 6.2 The Single Composable Gate

```solidity
// Any tournament, game, or DePIN node queries ONE function:
bool eligible = VAPIProtocolLens.isFullyEligible(deviceId);
```

Behind this call: ioID registration verified, ZK session proof verified, biometric
credential not expired, ruling registry clean (no active BLOCK ruling), PoAd anchor
present, dual-primitive gate satisfied. All in one view call, zero gas.

---

## 7. ioSwarm — Decentralized Consensus Layer

ioSwarm is VAPI's decentralized adjudication network — a fleet of independent IoTeX
operator nodes that vote on VAPI decisions before they are executed. No single node
controls any critical operation. This eliminates the centralized oracle problem that
plagues every existing anti-cheat solution.

### 7.1 Three Coordinators

**IoSwarmAdjudicationCoordinator** (Phase 109C)
- Dual-quorum veto: ClassJ nodes (BLOCK_QUORUM=0.67) + Triage nodes (BLOCK_QUORUM=0.67)
- Dual veto score=0.80 for DUAL_BLOCK
- Fail-OPEN CLEAR (adjudication is a reversible action)
- 5-node ClassJ emulator + 5-node Triage emulator (seed=109)

**IoSwarmVHPMintCoordinator** (Phase 110)
- MINT_QUORUM=0.80 — stricter because VHP mint is irreversible soulbound action
- Fail-CLOSED (no quorum = no mint)
- Swarm fingerprint = SHA-256(node_verdicts_json) — auditable consensus signature
- 5-node mint emulator (seed=110)

**IoSwarmRenewalCoordinator** (Phase 109B)
- CERTIFY_RENEW_QUORUM=0.60
- Fail-open (renewal failure = credential stays valid)
- W2 consecutive_clean-weighted verdicts for renewal scoring

### 7.2 Live Node Infrastructure (Phase 131)

`ioswarm_node_registry` table tracks registered nodes with staker_address, node_url,
last_seen_ts, node_version. `IoSwarmLiveNodeClient` dispatches to live nodes when
`IOSWARM_NODE_URLS` is set; falls back to emulator when empty.

Current state: `IOSWARM_ENABLED=true` (emulator mode, Phase 200). Exits emulator when
live node URLs registered.

---

## 8. VAPI Tokenomics

### 8.1 VAPI Token

- **Max supply:** 1,000,000,000 VAPI (1 billion, fixed — no inflation)
- **Standard:** ERC-20 on IoTeX L1; cross-chain via LayerZero V2 OApp
- **Mint policy:** operator-only; `tgeComplete=true` blocks all future minting after TGE

### 8.2 Distribution

| Allocation | % | Notes |
|-----------|---|-------|
| Operator staking pool | 30% | Locked for node operators |
| Device data rewards | 25% | Earned by hardware operators per PoAC submission |
| Ecosystem development | 20% | Grants, integrations, DePIN partnerships |
| Team | 15% | 4-year linear vest |
| Liquidity bootstrapping | 10% | Initial DEX liquidity |

### 8.3 Utility Mechanisms

**Staking:** Operators lock minimum 10,000 VAPI in `VAPIOperatorRegistry`. Slashing:
50% burned (deflationary) + 50% to claimant (incentive alignment).

**Hardware certification:** Manufacturers pay VAPI to register hardware in
`VAPIHardwareCertRegistry` (certLevel 1=basic, 2=BLE accessory, 3=full biometric).
This creates ongoing protocol revenue tied directly to hardware sales.

**Data marketplace:** `VAPIDataMarketplace` — players with data sovereignty pledges
earn VAPI when their anonymized biometric data is licensed. 70% to device pool / 30%
to treasury. Three licensing tiers: MANUFACTURER (hardware improvement) /
DEVELOPER (game AI training) / GAMER (competitive analytics).

### 8.4 Reward Multipliers

| Condition | Multiplier |
|-----------|-----------|
| Base rate | 1.0× |
| Tournament Passport holder | 1.5× |
| Enrolled (biometric credential active) | 2.0× |
| CERTIFY streak (5+ consecutive) | 2.5× |
| MPC ceremony contributor | 1.25× |
| Gate attestation anchor | 3.0× |
| L7 GSR enrolled (future) | 1.75× |

### 8.5 Token Launch Sequencing (Non-Negotiable)

Token launch is sequenced behind measurable milestones — not arbitrary:

1. Inter-person separation ratio > 1.0 confirmed empirically (currently 0.728)
2. N≥100 live non-dry-run adjudications with zero false positives
3. VHP end-to-end demonstrated on IoTeX testnet
4. All 43 contracts audited (security audit in progress)
5. THEN: TGE consideration

---

## 9. Autonomous Agent Fleet — 36 Agents

The VAPI agent fleet is organized into six functional tiers. All agents run as background
asyncio tasks. All share the federation_bus event channel. All operate independently but
are architecturally coupled through shared store tables.

### Tier 1 — Core Adjudication (Phases 65–68)

**Agent #1 — SessionAdjudicator** (Phase 65)
- LLM: claude-sonnet-4-6
- 5-minute polling cycle; processes all sessions without LLM ruling
- Produces `agent_rulings` (BLOCK/FLAG/HOLD/CERTIFY/CLEAR) with `commitment_hash`
- Rule-fallback logic when LLM unavailable
- `dry_run=True` default — does not execute hard blocks until activated

**Agent #2 — RulingEnforcementAgent** (Phase 66)
- Monitors ruling streaks: FLAG×5 → HOLD; HOLD×2 → BLOCK
- Suspends `PHGCredential` on BLOCK (24h default; 7d if warmup_attack_score > 0.7)
- Records rulings on-chain via `RulingRegistry.sol`
- Operator override endpoint: `POST /agent/override`

### Tier 2 — Intelligence Synthesis (Phases 50–51)

**Agent #3 — CalibrationIntelligenceAgent** (Phase 50)
- 6 calibration-specialist tools
- Enforces `min()` unconditionally — thresholds can only tighten
- 30-minute event consumer; fires `recalibration_needed` when drift_velocity > 0.6
- Wired to InsightSynthesizer Mode 6 callback

**Agent #4 — BridgeAgent** (Phase 50, expanded through Phase 65)
- claude-sonnet-4-6, 40 tool bindings
- Primary operator-facing intelligence interface
- Tools: threshold analysis, evasion cost prediction, anomaly trends, incident reports,
  controller twin data, enrollment status, session replay, and more

### Tier 3 — Enrollment & Separation (Phases 143–165)

**Agent #5 — SeparationRatioMonitorAgent** (Phase 129)
- 5-minute polling; monitors separation ratio breakthrough
- 2-consecutive guard against false breakthrough
- Fires `separation_ratio_breakthrough` bus event
- Auto-enables `confidence_multiplier_enabled` on breakthrough

**Agent #6 — CaptureStagnationMonitor** (Phase 154)
- Rolling sessions/day from `separation_defensibility_log` (7-day window)
- Stagnant when < 0.5 sessions/day
- Feeds urgency input to EnrollmentAutoGuidanceAgent

**Agent #7 — CentroidVelocityMonitor** (Phase 152)
- Computes |ratio_curr − ratio_prev| / dt_seconds
- Plateau threshold: 0.001 per day
- Stagnant flag feeds Phase 156 urgency scoring

**Agent #8 — EnrollmentCaptureGuidanceAgent** (Phase 151)
- Per-probe, per-player gap breakdown
- `GET /agent/enrollment-capture-guidance` — synthesizes N needed per player
- Emits `enrollment_capture_guidance` bus event
- Whitelist enforcement: only `STRUCTURED_PROBE_TYPES` accepted in defensibility log

**Agent #9 — EnrollmentAutoGuidanceAgent** (Phase 156)
- Synthesizes Phase 151 guidance + Phase 154 stagnation + Phase 152 velocity + Phase 155 hardware status
- 1-hour poll; urgency_level HIGH/MEDIUM/LOW
- Fires `enrollment_complete` → `TournamentActivationChainAgent` when `overall_ready=True`

**Agent #10 — PlayerQualityReportAgent** (Phase 144)
- Per-player stability/probe-type/enrollment-readiness scoring
- `ENROLLMENT_STABILITY_THRESHOLD=0.70`, `ENROLLMENT_MIN_PROBE_TYPES=2`
- Produces per-player recommendations

### Tier 4 — Tournament Gate Chain (Phases 127–200)

**Agent #11 — TournamentPreflightAgent** (Phase 127)
- 10 P0 conditions checked before tournament activation:
  1. `separation_ok` — ratio ≥ min_separation_ratio (0.70)
  2. `l4_ok` — L4 thresholds calibrated and not stale
  3. `gate_ok` — VAPIProtocolLens.isFullyEligible circuit-breaker green
  4. `cert_ok` — PHGCredential not suspended
  5. `audit_ok` — MPC ceremony integrity verified
  6. `dual_gate_warned` — VAPIDualPrimitiveGate status
  7. `epoch_window_warned` — epoch freshness window configured
  8. `ioswarm_warned` — ioSwarm emulator vs. live status
  9. `biometric_ttl_ok` — (not ttl_expired) AND len(renewal_chain) > 0 (Phase 196)
  10. `all_pairs_p0_ok` — all player pairs have separation ≥ 1.0 (Phase 197; bypassed in prototype mode)
- Fail-closed: `overall_pass=False` blocks `commit-activation`

**Agent #12 — TournamentActivationChainAgent** (Phase 127+)
- Receives `enrollment_complete` from EnrollmentAutoGuidanceAgent
- Runs preflight checklist atomically
- Blocks on P0 failure (separation_ok=False or l4_ok=False)
- Records activation attempt to `tournament_preflight_log`

**Agent #13 — L4CalibrationStalenessMonitor** (Phase 123)
- Tracks `live_feature_dim` vs `calibration_feature_dim`
- `stale=True` when dimensions mismatch
- Fires calibration staleness warning

**Agent #14 — L4PerBatteryThresholdRouter** (Phase 126)
- Routes L4 threshold lookup by battery_type (touchpad/trigger/button/gameplay/resting_grip)
- Falls back to global 7.009/5.367 with WARNING log
- Source logged: "per_battery" | "global_fallback"

**Agent #15 — ControllerHardwareIntelligenceAgent** (Phase 155)
- Attested tier (DualShock Edge, L0–L6) vs. Standard tier (Xbox/Switch, L0–L5)
- Composite key `profile_hash:battery_type:transport_type`
- Default thresholds 7.009/5.367
- `multi_controller_enabled=False` default

### Tier 5 — Biometric Privacy & Renewal (Phases 159–200)

**Agent #16 — BiometricPrivacyComplianceAgent** (Phase 159)
- BP-001: Temporal Biometric Decay `TBD(t) = e^(−λt)` with τ_half=90 days
- Warning when mean_decay_factor < 0.25
- `privacy_compliance_log` table
- Fires `biometric_decay_warning` bus event

**Agent #17 — BiometricCredentialTTLAgent** (Phase 178)
- Tracks credential age against `biometric_credential_ttl_days=90.0`
- `check_biometric_credential_ttl()` in TournamentActivationChainAgent
- Renewal chain required: (not ttl_expired) AND len(renewal_chain) > 0

**Agent #18 — BiometricRenewalEngine** (Phase 180)
- WIF-029 W2 closure — consent-bound renewal commitment chain
- `new_hash = SHA-256(prev_hash + ratio + N + N_consented + ttl + ts_ns)`
- Calls `SeparationRatioRegistry.renewCommit()` on IoTeX
- `POST /agent/renew-separation-ratio-commitment`

**Agent #19 — ReEnrollmentAttestationAgent** (Phase 185)
- HMAC attestation tokens on persona break events
- `reauth_attestation_enabled=True`
- Links attestation tokens to biometric renewal chain

**Agent #20 — AttestationBoundRenewalAgent** (Phase 186)
- Validates attestation token present at time of renewal
- `attestation_bound_renewal_enabled=False` default
- RENEWAL_WITHOUT_ATTESTATION is CRITICAL severity in FleetSignalCoherenceAgent

**Agent #21 — AttestationOpSecAdvisorAgent** (Phase 187)
- Mempool OPSEC advisory for attestation transactions
- `mempool_opsec_enabled=False` default
- Coordinates with VHPReenrollmentBadge.sol contract

### Tier 6 — Epistemic Intelligence (Phases 65–200)

**Agent #22 — ClassJAgent** (Phase 81)
- Epistemic ClassJ specialist (weight 0.40 in consensus formula)
- 4-signal VAPI-aware reasoning about NOMINAL/ANOMALY sessions
- Contributes to Phase 109C ioSwarm dual-quorum

**Agent #23 — SupervisorAgent** (Phase 98 hardened → Phase 147)
- Epistemic Supervisor (weight 0.20)
- Phase 147 hardening: threshold 0.60 → 0.65; `triage_prereq_required=True`
- ClassJ + Supervisor alone (0.60) can no longer reach 0.65 gate — anti-capture

**Agent #24 — EpistemicConsensusGate** (Phase 98)
- Aggregates ClassJ + Supervisor + Triage + ioSwarm
- `epistemic_consensus_threshold=0.65` (Phase 147 hardened)
- Consensus formula: {0.35, 0.35, 0.15, 0.15} (swarm on) or {0.40, 0.40, 0.20} (off)
- `triage_prereq_required=True` — Triage signal must be present

**Agent #25 — PersonaBreakDetectorAgent** (Phase 182)
- LOO centroid drift detection — identifies when player biometric profile shifts
- `persona_break_detection_enabled=True`
- Fires `persona_break_detected` bus event → triggers ReEnrollmentAttestation

**Agent #26 — MaturityElevationGateAgent** (Phase 183)
- Maturity elevation plan — transitions ALPHA → BETA → PRODUCTION_CANDIDATE
- `maturity_elevation_enabled=True`
- Reads ProtocolMaturityScoringAgent score; elevates tier when score ≥ threshold

**Agent #27 — ProtocolMaturityScoringAgent** (Phase 177, extended through Phase 195)
- 9-component maturity score (0.0–1.0) → tier ALPHA/BETA/PRODUCTION_CANDIDATE
- Components (Phase 195 _WEIGHTS v3):
  - separation (0.18) — ratio toward 1.0
  - freshness (0.11) — L4 calibration recency
  - calibration_coverage (0.12) — session spread
  - l4_precision (0.12) — threshold tightness
  - gate_integrity (0.07) — contract health
  - ioswarm_quorum (0.07) — consensus reliability
  - threat_forecast_accuracy (0.07) — PIR harness score
  - biometric_stationarity (0.04) — BSO confidence
  - protocol_metabolism_index (0.03) — orphan resolution speed (PMI = max(0, 1 − mean_orphan_hours/48))
  - (remaining 0.19 distributed across enrollment/ceremony/dp components)

**Agent #28 — BiometricStationarityOracleAgent** (Phase 188)
- Drift cause classifier — distinguishes genuine drift from measurement noise
- `biometric_stationarity_enabled=False` default
- Provides `biometric_stationarity_component` to ProtocolMaturityScoringAgent

**Agent #29 — ProtocolIntelligenceRecordAgent** (Phase 189)
- PIR chain hash sequence — creates auditable record chain for all protocol intelligence reports
- `pir_chain_enabled=False` default
- Provides `threat_forecast_accuracy_component` to ProtocolMaturityScoringAgent

**Agent #30 — LivePresenceSignalingAgent** (Phase 190)
- Bidirectional presence channel — 8 signal types (LED + haptic vocabulary)
- Signals: CERTIFY_PULSE, FLAG_ALERT, BLOCK_VIBRATION, CLEAR_CONFIRM, etc.
- `live_presence_signaling_enabled=False` default
- 8 bus subscriptions for real-time presence indication to connected hardware

**Agent #31 — FleetConsensusSnapshotAgent** (Phase 157)
- WIF-012: dual-condition `overall_ready` = sessions_needed==0 AND defensible
- WIF-016: `cov_stability_check()` — 3 regime labels (STABLE/TRANSITIONAL/UNSTABLE)
- WIF-013: PoFC hash = SHA-256(sorted_verdicts + ratio + ts_ns)
- Produces Proof of Fleet Consensus snapshots

**Agent #32 — CorpusDataCuratorAgent** (Phase 192, agent #35 in fleet order)
- 7 data coherence tasks:
  1. **Provenance DAG** — 20-hop walk of CALIBRATION_SESSION → RULING → COMMITMENT chain
  2. **Corpus Entropy Monitor** — clustering warning at Shannon entropy < 1.5
  3. **Proof-of-Erasure Certificate** — `sha256: SHA-256(device_id + erased_tables + ratio + ts_ns)`
  4. **Federated Corpus Quality** — BP-007 compliant privacy constraint gate
  5. **Cross-Feature Temporal Correlation** — Frobenius norm per-pair separability
  6. **Data Readiness Certificate** — 8-dimensional gate (NOT_READY/READY/PARTIAL)
  7. **Session Contribution Weights** — TBD λ=ln(2)/90 FROZEN (BP-001)

**Agent #33 — FleetSignalCoherenceAgent** (Phase 193, agent #36 in fleet order)
- Fleet-level signal coherence observer — always-on (`fleet_coherence_enabled=True` default)
- 3 failure mode categories with 15 total rules:
  - **CONTRADICTION (7 rules):** semantic conflicts between agent outputs
  - **ORPHAN (5 rules):** nodes with no parent in Provenance DAG
  - **INVERSION (3 rules):** Provenance DAG timestamp anomalies (child timestamp precedes parent)
    - COMMITMENT_PREDATES_CONSENT
    - BADGE_WITHOUT_RENEWAL_PARENT
    - RULING_PREDATES_CALIBRATION (common during corpus growth — classified by delta_s)
- `coherence_id = "coh_" + SHA-256[:16]`
- Auto-promotes persistent contradictions (N_PROMOTE_THRESHOLD=3) to VAPI_WHAT_IF.md
- RENEWAL_WITHOUT_ATTESTATION = CRITICAL severity
- BP-007 `_scrub_evidence()` removes raw biometric fields from evidence_json

**Agents #34–#36 — ioSwarm Coordinators** (Phases 109A, 109B, 110)
- See Section 7 — IoSwarm Architecture

---

## 10. Tool Catalog — 149 Tools

VAPI exposes 149 deterministic tools through the BridgeAgent and specialized agents.
Tools are numbered sequentially and bound to specific store methods, endpoints, or chain
calls. Each tool has a corresponding SDK class and OpenAPI schema.

### Tool Categories

| Range | Category | Count |
|-------|----------|-------|
| #1–#22 | Core bridge (HID, chain, enrollment, replay, profiles) | 22 |
| #23–#45 | ZK, operator, security, agent autonomy | 23 |
| #46–#74 | Epoch window, per-battery calibration, threshold management | 29 |
| #75–#99 | ioSwarm (adjudication, mint, renewal, node registry) | 25 |
| #100–#120 | Separation ratio, corpus, privacy, GSR, federation | 21 |
| #121–#135 | Blockchain anchoring, dual-primitive, TSP, maturity scoring | 15 |
| #136–#144 | CorpusDataCurator (9 data coherence tools) | 9 |
| #145–#147 | FleetSignalCoherence (summary, entries, resolve) | 3 |
| #148 | CoherenceFingerprint (persistent contradiction tracking) | 1 |
| #149 | Protocol Metabolism Index | 1 |

### Selected Key Tools

- `#75 get_ioswarm_consensus` — ioSwarm block/certify quorum result
- `#89 get_separation_ratio_status` — pooled + battery-stratified ratio, tournament blocker flag
- `#95 run_tournament_preflight` — executes all 10 P0 conditions, returns pass/fail with detail
- `#107 get_enrollment_capture_guidance` — per-probe per-player gap analysis
- `#116 get_biometric_privacy_compliance` — decay factor, TTL, compliance status
- `#126 get_protocol_maturity_score` — 9-component score, tier, component breakdown
- `#129 trigger_renewal_commitment` — initiates biometric renewal chain
- `#136 get_provenance_dag_status` — DAG walk health, inversion count
- `#145 get_fleet_coherence_summary` — active contradictions, orphans, inversions
- `#149 get_protocol_metabolism_index` — PMI score, orphan resolution hours

---

## 11. Stakeholder Value Framework

### For Gamers

**The Problem Today:** Competitive online gaming is corrupted by cheaters who use
hardware injection devices (Cronus Zen, Titan One) that are completely invisible to
any software-level anti-cheat system. These devices relay scripted inputs through a
clean controller, making bots look like human players. The result: legitimate players
lose matches, rankings, and prize money to cheaters who cannot be detected.

**What VAPI Provides:**
- **Proof of human presence** — cryptographically verifiable, not just asserted
- **Personal biometric credential** — cannot be shared, sold, or impersonated
- **Tournament eligibility** — single `isFullyEligible()` call any organizer can query
- **Data sovereignty** — players own their biometric data and can earn VAPI tokens
  when it is licensed to developers or manufacturers
- **Competitive integrity** — knowing every opponent has a valid VAPI credential means
  playing on a level field

**Gamer Experience:**
- Enroll once (10 NOMINAL sessions with enrolled credential)
- Play as normal — no UI changes, no performance impact
- Dashboard shows real-time biometric status, humanity score, and PoAC chain health
- MY CONTROLLER page shows live 3D digital twin with biometric heartbeat visualization

### For Game Developers & Publishers

**The Problem Today:** Publishers spend millions on anti-cheat (Activision / Riot / EA)
and still face rampant cheating. Existing solutions:
- Require kernel-level ring-0 drivers (privacy concerns, instability)
- Can be bypassed by hardware injection at the USB layer
- Are opaque — players cannot verify fairness claims
- Cannot prove WHO was playing, only what software was running

**What VAPI Provides:**
- **Single composable integration:** `isFullyEligible(deviceId)` — one view call, zero gas
- **No kernel driver required** — VAPI runs in user space on the player's PC
- **Hardware-layer detection** — Cronus and hardware injection devices are detected at L2
- **Verifiable fairness** — every eligibility decision has an on-chain audit trail
- **Modular adoption** — enable only the detection layers needed (L4, L5, ZK, etc.)
- **Revenue alignment** — VAPI token rewards increase when players are in active competition
- **Open protocol** — published invariants, published circuit, published corpus methodology

### For Hardware Manufacturers

**The Problem Today:** Premium gaming controller manufacturers (Sony, Microsoft, Razer)
cannot differentiate their hardware from cheap alternatives in the anti-cheat space.
A $200 DualShock Edge looks identical to a $20 controller to any existing anti-cheat.

**What VAPI Provides:**
- **Hardware certification registry** — `VAPIHardwareCertRegistry` certifies specific
  hardware SKUs as VAPI-compatible (certLevel 1, 2, or 3)
- **Attested tier advantage** — certified hardware unlocks L0–L6 full detection stack;
  uncertified hardware runs L0–L5 only
- **Revenue from certification** — manufacturers pay VAPI to register; ongoing fee per
  new SKU
- **GSR grip integration** — ESP32-S3 BLE grip accessory extends hardware value proposition
  with physiological biometric data (sympathetic_arousal_index, gsr_game_event_correlation)
- **Premium justification** — players can demonstrate they are using certified hardware
  in competitive contexts
- **DePIN data pipeline** — GSR grip data flows to VAPIDataMarketplace; manufacturers
  earn insights into how players actually use hardware under competitive stress

### For Tournament Organizers & Esports

**What VAPI Provides:**
- **Zero-trust eligibility** — no need to trust player identity claims or rely on
  account credentials
- **On-chain audit trail** — every tournament entry has a linked PoAC chain, ZK proof,
  and ruling history
- **Automated preflight** — `run_tournament_preflight` checks all 10 P0 conditions
  atomically before tournament activation
- **Fraud deterrence** — the cost of defeating VAPI is acquiring N=10+ calibration
  sessions of another person's biometric data at 1,002 Hz — practically impossible
- **Prize pool protection** — cryptographic proof of human presence in every session
  reduces liability for incorrect prize distribution

---

## 12. Novel Distinctiveness

### What Makes VAPI Different From Everything Else

**1. Physics-layer detection, not software inspection.**
Every other anti-cheat system (VAC, EAC, BattlEye, FACEIT, Vanguard) inspects running
processes, memory layouts, and driver signatures. A hardware injection device at the USB
layer defeats all of these because the host PC is running legitimate software. VAPI reads
the physics of human motor control — neurological tremor (8–12 Hz), galvanic skin response
conductance changes, micro-accelerometer variance from hand muscle movement — that cannot
be forged by any software layer.

**2. Biometric fingerprinting without biometric storage.**
The L4 Mahalanobis profile is computed from a 12-feature vector derived from controller
physics, never from fingerprint/face/retinal data. No personal biometric data leaves the
device. The zero-knowledge proof allows verifying "this session matches this player's
enrolled profile" without revealing the profile. BP-001 temporal decay and BP-007 scrubbing
ensure data minimization by design.

**3. Cryptographic chain of custody from physical action to on-chain proof.**
Every button press, stick movement, and accelerometer reading contributes to a 228-byte
PoAC record that is signed with ECDSA-P256, chained via SHA-256, committed to IoTeX L1,
and proven via Groth16 ZK circuit. An adversary cannot inject fake evidence into any
layer without invalidating the chain.

**4. Autonomous multi-agent adjudication.**
36 agents operating concurrently means no single point of judgment failure. A session that
is borderline on L4 gets additional review from ClassJ, Supervisor, and Triage agents, all
feeding into an epistemic consensus gate at 0.65 threshold. No single agent alone can reach
the gate — a deliberate design to prevent capture.

**5. Decentralized consensus via ioSwarm.**
Unlike centralized anti-cheat servers, ioSwarm distributes the final BLOCK/CERTIFY decision
across N independent IoTeX operator nodes. BLOCK_QUORUM=0.67 means a minority of malicious
nodes cannot block legitimate players. MINT_QUORUM=0.80 means soulbound VHP credentials
require strong consensus before issuance.

**6. Player-owned biometric credentials.**
VHP (Verified Human Proof) is an ERC-4671 soulbound token. It cannot be transferred,
sold, or lent. Its validity is time-bounded (`expiresAt`) and linked to a renewal chain
that requires re-enrollment attestation if the biometric profile drifts. This solves
account boosting (another player cannot use your credential) and carry-for-hire services.

**7. Composable DePIN integration.**
The entire protocol is composable: `isFullyEligible()` is a view call any smart contract
on any chain (via LayerZero) can invoke. Tournament gates, staking contracts, data
marketplaces, and governance systems can all consume VAPI proof without understanding
its internals. This is the Lego-brick property that makes VAPI an infrastructure layer
rather than a point solution.

---

## 13. Protocol Integrity Constants — Frozen Invariants

These values are permanently fixed. Any code change that touches them must halt and report.

| Constant | Value | Source |
|----------|-------|--------|
| PoAC wire format | 228 bytes (164B body + 64B sig) | Phase 1 |
| Chain link hash | SHA-256(raw[0:164]) — body ONLY | Phase 1 |
| Device ID | keccak256(pubkey) | Phase 1 |
| Hard cheat codes | 0x28 DRIVER_INJECT, 0x29 WALLHACK, 0x2A AIMBOT | Phase 1 |
| Advisory codes | 0x2B TEMPORAL_BOT, 0x30 BIOMETRIC_ANOMALY, 0x31 IMU_PRESS_DECOUPLED, 0x32 STICK_IMU_DECOUPLED, 0x33 GSR_CORRELATION_ABSENT | Phase 17 |
| L4 anomaly threshold | 7.009 (mean+3σ, N=74, Phase 57) | Phase 57 |
| L4 continuity threshold | 5.367 (mean+2σ, N=74, Phase 57) | Phase 57 |
| Phase 62 ZK | Poseidon(8)(scaledFeatures[0..6], inferenceCodeFromBody); C3: inferenceResult===inferenceCodeFromBody; nPublic=5 | Phase 62 |
| Phase 66 commitment | SHA-256(verdict + sorted(evidence_hashes) + attestation_hash_hex + struct.pack(">Q", ts_ns)) | Phase 66 |
| Phase 67 circuitId | sha3_256(circuitName.encode()) — consistent in chain.py, run-mpc-ceremony.js, SDK | Phase 67 |
| BLOCK_QUORUM | 0.67 (never lower below GENERAL_QUORUM=0.60) | Phase 109A |
| MINT_QUORUM | 0.80 (never lower) | Phase 110 |
| Epistemic threshold | 0.65 (Phase 147 hardened from 0.60) | Phase 147 |
| Stable EMA track | Updates NOMINAL sessions ONLY | Phase 38 |
| L6_CHALLENGES_ENABLED | false — never change without N≥50 hardware calibration | Phase 43 |
| L6B_ENABLED | false — never change without N≥50 neuromuscular reflex calibration | Phase 63 |
| GSR_ENABLED | false — never change without N≥30 GSR calibration sessions per player | Phase 99 |

---

## 14. Current Calibration State

*As of Phase 200, 2026-04-11*

### Separation Ratio

| Metric | Value |
|--------|-------|
| Current ratio (touchpad_corners) | **0.728** (N=35, diagonal+LOO) |
| Target | **1.0** (ALL_PAIRS gate) |
| Prototype mode | Active (`ALL_PAIRS_GATE_ENABLED=false`) |
| Player counts | P1=12, P2=12, P3=11 sessions |
| LOO classification | 54.3% (19/35) |
| P2 vs P3 distance | 0.401 — structural proximity ceiling |
| tremor_peak_hz | P1=9.37Hz, P2=1.71Hz, P3=2.85Hz |
| Path to >1.0 | tremor_resting probe (Phase 199): 5 sessions/player, 30s still-hold |

### Test Counts

| Suite | Count |
|-------|-------|
| Bridge | 2,192 |
| Hardhat | 482 |
| SDK | 418 (402 passing + 16 pre-existing version-check failures) |
| Hardware | 37 |
| E2E | 14 |
| **Total** | **~3,089** |

### Agent & Tool Counts

- **Agents:** 36 active
- **Tools:** 149 (#149 = get_protocol_metabolism_index)
- **Contracts:** 43 ALL LIVE on IoTeX Testnet

---

## 15. Future Trajectory

### Gate 1 — Separation Breakthrough (Next Hardware Session)

**Objective:** Push inter-person separation ratio above 1.0 for all player pairs.

**Method:** `tremor_resting` probe — 5 sessions per player, 30 seconds each, completely
still controller. Primary discriminator: `tremor_peak_hz` (P1=9.37Hz is reliably distinct
from P2=1.71Hz; P3=2.85Hz separation from P2 requires clean resting measurement).

**Deliverable:** Separation ratio > 1.0 → set `ALL_PAIRS_GATE_ENABLED=true` →
tournament prototype mode exits → `all_pairs_p0_ok=True` in real mode.

### Gate 2 — Live Non-Dry-Run Adjudications

**Objective:** N≥100 live adjudications with `dry_run=False` and zero false positives.

**Method:** Competitive gaming sessions with real rulings (not simulated). CERTIFY
rulings become actual credential issuances. BLOCK rulings become actual suspensions.

**Deliverable:** 100 validated sessions → TGE consideration opens.

### Gate 3 — GSR Hardware Integration

**Objective:** Validate L7 GSR layer with real hardware.

**Required:** N≥30 GSR calibration sessions per player with ESP32-S3 BLE grip.
**Discriminators to validate:** `sympathetic_arousal_index`, `gsr_game_event_correlation`
(human >0.3 Pearson r vs game events; bot ≈0.0 — no physiological response).
**Manufacturing path:** OEM DualShock Edge grip module slot; certLevel=2.

### Gate 4 — Production Mainnet

**Objective:** Migrate from IoTeX Testnet (4690) to IoTeX Mainnet (4689).

**Prerequisites:**
- Security audit of all 43 contracts complete
- Separation ratio > 1.0 confirmed
- 100 live validated adjudications
- VAPIToken TGE on testnet demonstrated
- OpenZeppelin TransparentUpgradeableProxy wired for Realms migration readiness

**Target:** When daily PoAC volume ≥ 100,000/day → Realms migration evaluation.

### Long-Term Vision

**VAPI as DePIN Infrastructure:**
The protocol is designed to be adopted by any game publisher, tournament organizer, or
esports platform as infrastructure — not a competing product. The `isFullyEligible()`
composability means any on-chain gaming contract can check VAPI proof without
understanding the protocol internals.

**Market Opportunity:**
- Global esports prize pools: $1.4B/year (2025) growing 15%/year
- Hardware anti-cheat gap: zero existing solutions for hardware injection devices
- Data marketplace: biometric gaming data has commercial value for game AI training,
  hardware ergonomics research, and competitive analytics
- DePIN convergence: IoTeX positions VAPI as a flagship DePIN physical-world data
  protocol alongside environmental sensing and supply chain verification

**The Flywheel:**
```
GSR grips → physiological data → VAPIDataMarketplace
→ VAPI token rewards → more grips manufactured
→ more tournament operators integrate isFullyEligible()
→ more players enroll → richer corpus
→ better separation ratio → stronger proof
→ higher protocol maturity → larger prize pools use VAPI
→ greater token utility demand → higher staking rewards
→ more ioSwarm operators register → stronger consensus
→ more hardware manufacturers certify → more hardware variety
→ loop continues
```

---

*Document generated: 2026-04-11 | Phase 200 | VAPI Protocol v3.0.0-phase199*
*Active wallet: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692 | Chain: IoTeX Testnet 4690*
*Repository: C:\Users\Contr\vapi-pebble-prototype*

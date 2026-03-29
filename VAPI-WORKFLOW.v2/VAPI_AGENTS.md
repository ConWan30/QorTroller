# VAPI AGENTS — For Claude Code Context

## Agent Identity: VAPI Master Expert

**You are Claude Code, the Architectural Infrastructure Creator of VAPI and an Expert across all domains comprising the VAPI ecosystem.**

**Your Expertise Profile**:
- **DePIN/Blockchain Architect**: IoTeX L1 integration, Solidity smart contract design, ZK proof systems (Groth16), on-chain verification, token economics, distributed consensus (ioSwarm), wallet management, MPC ceremonies
- **AI/ML/FL/AGI Engineer**: PITL stack (L0-L6) classification, behavioral ML for anti-cheat, federated learning threat correlation, Mahalanobis biometric analysis, temporal rhythm detection, humanoid bot classification, epistemic consensus protocols
- **IoT-Sensors-Electronics Engineer**: HID protocol implementation, sensor fusion (accelerometer/gyroscope), embedded firmware (C/Zephyr RTOS), real-time data acquisition, hardware calibration, BLE transport, power management, ATECC608A secure elements
- **Cryptographic Systems Engineer**: SHA-256/Poseidon hashing, ECDSA-P256 signatures, zero-knowledge circuits, Merkle proofs, device identity (ioID), credential lifecycle (VHP soulbound tokens)
- **Distributed Systems Architect**: Asyncio agent orchestration, SQLite WAL concurrency, MQTT/Mosquitto messaging, FastAPI bridge services, cross-bridge threat correlation, event-driven architectures
- **Anti-Cheat Systems Specialist**: Gaming anti-cheat protocols, wallhack/aimbot detection, injection detection (HID-XInput Oracle), tournament integrity, competitive gaming ecosystems
- **Firmware Engineer**: nRF9160 embedded development, Zephyr RTOS, sensor polling optimization, 228-byte PoAC record generation, power-efficient cryptography
- **Full-Stack Integration Engineer**: Python SDK design, OpenAPI client generation, dataclass/slot optimization, pytest automation, Hardhat contract testing

**Your Role**: When reading this file, you are the agent fleet commander. You can spawn parallel expert contexts for any of these 16+ agents. You know their fail modes, epistemic weights, and tool inventories. Orchestrate them for complex cross-domain tasks.

> **INSTRUCTION TO CLAUDE CODE**: This file defines the VAPI agent fleet as callable expert subsystems.
> When reading this file, you must:
> 1. Reference specific agents when proposing changes to their domains
> 2. Spawn parallel expert contexts for complex cross-domain work
> 3. Respect each agent's fail mode (fail-open vs fail-closed)
> 4. Use agent-specific tools from the 104 available

---

## Agent Overview

VAPI operates 16+ specialized agents in the bridge service. Each agent is a background asyncio task with specific expertise, tools, and decision logic. This document maps them for Claude Code expert spawning.

### Agent Table

| # | Agent | LLM | Cycle | Expertise | Fail Mode | Tools |
|---|-------|-----|-------|-----------|-----------|-------|
| 1 | SessionAdjudicator | claude-opus-4-6 | 5 min | PITL L0-L6 pipeline, PoAd anchoring | Fail-open | 15 |
| 2 | CalibrationIntelligenceAgent | claude-sonnet-4-6 | 30 min | L4 thresholds, per-battery tracks | Fail-closed | 6 |
| 3 | SeparationRatioMonitorAgent | — | 300 sec | Tikhonov correction, breakthrough | Fail-open | 3 |
| 4 | PoAdAnchorAgent | — | 60 sec | ioSwarm consensus, dual-quorum | Non-blocking | 2 |
| 5 | ClassJDetector | claude-opus-4-6 | 60 sec | Humanoid bot classification | Fail-open | 8 |
| 6 | RulingEnforcementAgent | — | 5 min | Streak escalation, on-chain commit | Fail-closed | 4 |
| 7 | VHPRenewalAgent | claude-opus-4-6 | 5 min | VHP credential renewal | Fail-closed | 6 |
| 8 | CalibrationWatcher | — | Real-time | Threshold drift detection | Advisory | 3 |
| 9 | ProactiveMonitor | — | 60 sec | Real-time cluster detection | Advisory | 5 |
| 10 | InsightSynthesizer | claude-opus-4-6 | 6 hrs | Retrospective digests, policy | Advisory | 6 |
| 11 | FederationBus | — | 120 sec | Cross-bridge threat correlation | Privacy-preserving | 4 |
| 12 | TournamentActivationChainAgent | claude-opus-4-6 | Manual | Tournament readiness orchestration | Manual | 10 |
| 13 | EnrollmentManager | — | Event | PHGCredential mint after enrollment | Fail-closed | 4 |
| 14 | IoSwarmRenewalCoordinator | — | Event | ioSwarm consensus for VHP renewal | Fail-open | 5 |
| 15 | IoSwarmAdjudicationCoordinator | — | Event | Dual-quorum veto for adjudication | Fail-open | 5 |
| 16 | IoSwarmVHPMintCoordinator | — | Event | ioSwarm quorum for VHP minting | Fail-closed | 6 |
| 17 | ControllerHardwareIntelligenceAgent | claude-opus-4-6 | Event-driven | Multi-controller capability mapping, PITL layer availability, tier eligibility, transport negotiation | Fail-open | 8 |

---

## Agent 1: SessionAdjudicator

**Trigger**: `/vapi expert adjudicate <session_id>`

**Role**: Real-time PITL L0-L6 classification and PoAd on-chain anchoring

**Expertise**:
- L0: Physical presence (controller connection, battery level)
- L1: PoAC chain integrity (hash linkage, signature verification)
- L2: HID-XInput Oracle (driver injection detection)
- L3: Behavioral ML (wallhack, aimbot detection)
- L4: Mahalanobis biometric (anomaly scoring)
- L5: Temporal rhythm oracle (temporal bot detection)
- L6: Active challenge-response (trigger-based)

**Decision Output**:
- HUMAN: humanity_prob > 0.7, all layers nominal
- BOT: Any hard cheat code (0x28, 0x29, 0x2A)
- UNCLEAR: Advisory codes only (0x2B, 0x30), humanity_prob 0.3-0.7

**Tools** (15 available):
- get_pitl_status: Current L0-L6 layer status
- get_l4_biometric_score: Mahalanobis distance
- get_l5_rhythm_analysis: CV and entropy
- get_l6_response_baseline: Trigger latency
- request_adjudication: Full PITL pipeline
- get_autonomous_rulings: AIL history
- [Additional 9 tools]

**Fail Mode**: Fail-open (CLEAR on uncertainty)
- No false positives (no innocent banned)
- Trade-off: Some bots may slip through as UNCLEAR
- Mitigation: PoAd anchoring for retrospective analysis

**Epistemic Weight**: 0.35 (highest, real-time authority)

**Invariant Requirements**:
- Must preserve 228B PoAC format
- Must not hard-gate on GSR (advisory only)
- Must log all decisions to pitl_records
- Must compute PoAd_hash for on-chain anchoring

---

## Agent 2: CalibrationIntelligenceAgent

**Trigger**: `/vapi expert calibrate <battery_type>`

**Role**: L4 threshold management and per-battery track registry

**Expertise**:
- Mahalanobis distance computation
- Threshold calibration (anomaly, continuity)
- Per-battery routing (USB vs BT vs touchpad vs trigger)
- Staleness detection (live_feature_dim vs calibration_feature_dim)
- EMA track updates (NOMINAL sessions only)

**Decision Output**:
- New threshold pair (anomaly, continuity)
- Source: per_battery or global_fallback
- Staleness: True/False

**Tools** (6 available):
- get_l4_calibration_status: Current staleness
- apply_l4_battery_calibration: Update thresholds
- get_l4_router_status: Per-battery routing
- check_threshold_drift: Drift detection
- [Additional 2 tools]

**Fail Mode**: Fail-closed (thresholds only tighten)
- min() enforcement: new_threshold = min(old, proposed)
- Never loosens thresholds (prevents baseline poisoning)
- Trade-off: May over-detect during drift periods

**Epistemic Weight**: 0.25 (specialist authority)

**Invariant Requirements**:
- Per-player thresholds only tighten (min())
- Stable EMA updates on NOMINAL sessions only
- Bounds enforcement: anomaly [5.0-15.0], continuity [3.0-10.0]

---

## Agent 3: SeparationRatioMonitorAgent

**Trigger**: `/vapi expert measure --full-covariance`

**Role**: Inter-person separation ratio analysis with Tikhonov correction

**Expertise**:
- Full covariance Mahalanobis estimation
- Tikhonov regularization (numerical stability)
- Battery-stratified analysis (touchpad, trigger, grip)
- Resting-grip normalization
- Breakthrough detection (ratio > 1.0)

**Decision Output**:
- Pooled ratio (all sessions combined)
- Battery-stratified ratio (per-battery-group)
- Tikhonov-corrected estimate (N>150 only)
- Tournament ready: True/False

**Tools** (3 available):
- get_separation_ratio_status: Current ratios
- analyze_interperson_separation: Full analysis
- get_separation_ratio_breakthrough: Breakthrough monitoring

**Fail Mode**: Fail-open (2-consecutive guard)
- Single outlier ignored (ratio spike)
- Requires 2 consecutive crossings to fire breakthrough
- Prevents false alarms from measurement noise

**Epistemic Weight**: 0.30 (critical path authority)

**Invariant Requirements**:
- Full covariance only when N>150 (mathematical stability)
- Honest disclosure of measured ratio (not target)
- Per-battery stratification for VHP confidence

---

## Agent 4: PoAdAnchorAgent

**Trigger**: `/vapi expert poad <device_id>`

**Role**: Proof of Adjudication on-chain anchoring for ioSwarm consensus

**Expertise**:
- PoAd_hash computation: SHA-256(sorted(node_verdicts) + quorum + ts_ns)
- ioSwarm node verdict aggregation
- Dual-quorum veto (ClassJ + Triage both needed)
- AdjudicationRegistry.sol interaction

**Decision Output**:
- PoAd_hash (32 bytes)
- Node verdicts JSON (sorted)
- On-chain transaction hash

**Tools** (2 available):
- get_poad_anchor_status: Current anchor state
- record_adjudication_on_chain: Submit to registry

**Fail Mode**: Non-blocking (async)
- Session classification proceeds regardless
- PoAd anchoring happens in background
- Failure does not block gameplay

**Epistemic Weight**: 0.15 (supporting authority)

**Invariant Requirements**:
- PoAd_hash includes sorted node_verdicts (deterministic)
- Quorum string includes actual vote counts
- Timestamp in nanoseconds (precision)

---

## Agent 5: ClassJDetector

**Trigger**: `/vapi expert class-j <session_trace>`

**Role**: Humanoid bot classification (no injection, but non-human patterns)

**Expertise**:
- Humanoid bot signatures (perfect consistency, no micro-tremor)
- Gyro/accel correlation analysis (L2C coupling)
- Press timing distribution (too uniform = bot)
- Session-to-session variance (too consistent = bot)

**Decision Output**:
- ClassJ: Humanoid bot detected (advisory 0x31)
- NOT ClassJ: Normal variance patterns
- Confidence: 0.0-1.0

**Tools** (8 available):
- get_class_j_status: Classification result
- analyze_session_variance: Variance patterns
- compare_session_similarity: Cross-session analysis
- [Additional 5 tools]

**Fail Mode**: Fail-open (advisory only)
- ClassJ never hard-blocks (may be human with unusual consistency)
- Advisory code 0x31 (not 0x28/0x29/0x2A hard cheats)
- AIL may escalate to BLOCK if pattern persists

**Epistemic Weight**: 0.20 (specialist authority)

---

## Agent 6: RulingEnforcementAgent

**Trigger**: `/vapi expert enforce <device_id>`

**Role**: Ruling streak escalation and on-chain credential enforcement

**Expertise**:
- Ruling streak tracking (FLAG×5 → HOLD, HOLD×2 → BLOCK)
- PHGCredential suspension/reinstatement
- On-chain ruling registry (RulingRegistry.sol)
- Suspension expiration (24h default, 7d for high warmup_attack_score)

**Decision Output**:
- FLAG: Advisory (first detection)
- HOLD: Temporary suspension (investigation)
- BLOCK: Credential suspended (enforcement)
- Reinstate: Credential reactivated (expiration)

**Tools** (4 available):
- get_ruling_streak: Current streak status
- get_on_chain_rulings: Registry history
- override_ruling: Operator override
- [Additional 1 tool]

**Fail Mode**: Fail-closed (escalatory)
- Conservative escalation: needs 5 FLAGs for HOLD, 2 HOLDs for BLOCK
- Reinstatement requires expiration or operator override
- On-chain record immutable (audit trail)

**Epistemic Weight**: 0.30 (enforcement authority)

**Invariant Requirements**:
- BLOCK requires all_layers_active=True
- Reinstatement automatic on expiration (auto_reinstate loop)
- On-chain commitment hash (anti-replay)

---

## Agent 7: VHPRenewalAgent

**Trigger**: `/vapi expert renew-vhp <device_id>`

**Role**: VHP credential renewal with ioSwarm consensus

**Expertise**:
- PHGCredential renewal conditions (clean_weighted threshold)
- IoSwarm consensus for renewal (CERTIFY_RENEW_QUORUM=0.60)
- W2 consecutive clean-weighted verdicts requirement
- VAPISwarmOperatorGate validation

**Decision Output**:
- Renew: Credential reactivated with ioSwarm consensus
- Hold: Insufficient clean history
- Block: Revoke eligibility

**Tools** (6 available):
- get_vhp_renewal_status: Current eligibility
- request_vhp_renewal: Initiate renewal
- get_ioswarm_renewal_status: Consensus status
- [Additional 3 tools]

**Fail Mode**: Fail-closed (quorum required)
- Requires 0.60 quorum from ioSwarm nodes
- W2 consecutive clean-weighted (not just any clean)
- No renewal without consensus

**Epistemic Weight**: 0.25 (consensus authority)

---

## Agent 8-11: Supporting Agents

### Agent 8: CalibrationWatcher
**Role**: Real-time threshold drift detection
**Trigger**: Event-driven (on drift_velocity > 0.6)
**Output**: recalibration_needed event to agent_events table

### Agent 9: ProactiveMonitor
**Role**: 60-second real-time cluster detection
**Expertise**: Trajectory checks, eligibility horizon alerts, 3 detection checks
**Cycle**: 60 seconds

### Agent 10: InsightSynthesizer
**Role**: 6-hour retrospective analysis
**Modes**: 5 modes including Credential Enforcement (Mode 6)
**Output**: 24h/7d/30d digests, risk labels, policy updates

### Agent 11: FederationBus
**Role**: 120-second cross-bridge threat correlation
**Privacy**: Privacy-preserving cluster fingerprints (no raw data sharing)
**Output**: Cross-bridge threat registry updates

---

## Agent 12: TournamentActivationChainAgent (Phase 135)

**Trigger**: `/vapi expert tournament-activate`

**Role**: Tournament readiness orchestration and activation chain management

**Expertise**:
- 6-signal readiness scoring (separation, l4, dual_gate, epoch, ioswarm, dry_run)
- 8-condition preflight validation
- Activation chain commit (persistent state)
- Auto-activation on breakthrough (currently disabled)

**Decision Output**:
- Ready: All 6 signals pass, activation chain committed
- Not Ready: Specific blocker identified
- Breakthrough Detected: Separation ratio > 1.0 (auto-activation pending manual enable)

**Tools** (10 available):
- get_tournament_readiness_score: 6-signal calculation
- run_tournament_preflight: 8-condition check
- commit_activation: Persist activation state
- get_tournament_activation_chain: Chain status
- [Additional 6 tools]

**Fail Mode**: Manual (auto_activate_on_breakthrough=False)
- Phase 135: Hardcoded safety, requires operator to activate even after breakthrough
- Future Phase: May enable auto-activation after 10+ verified breakthroughs

**Epistemic Weight**: 0.40 (highest, tournament authority)

---

## Agent 13-16: IoSwarm Coordinators

### Agent 13: EnrollmentManager
- PHGCredential mint after enrollment_min_sessions=10 NOMINAL
- Auto-mint on eligibility

### Agent 14: IoSwarmRenewalCoordinator
- CERTIFY_RENEW_QUORUM=0.60 for VHP renewal
- Fail-open if no live nodes (emulator mode)

### Agent 15: IoSwarmAdjudicationCoordinator
- DUAL_VETO_SCORE=0.80 (ClassJ + Triage both needed)
- ClassJ_BLOCK_QUORUM=0.67
- TRIAGE_BLOCK_QUORUM=0.67

### Agent 16: IoSwarmVHPMintCoordinator
- MINT_QUORUM=0.80 (fail-CLOSED)
- Swarm fingerprint: SHA-256(sorted(node_verdicts))
- VAPISwarmOperatorGate: min 3 distinct staker addresses

---

## Agent 17: ControllerHardwareIntelligenceAgent (Phase 136)

**Trigger**: `/vapi expert controller <detect|profile|validate|negotiate>`

**Role**: Multi-controller hardware abstraction and capability intelligence layer

**Expertise**:
- Controller auto-detection (USB HID enumeration, BLE scanning)
- Capability matrix mapping (PITL layer availability per controller)
- Tier eligibility determination (Attested vs Standard)
- Transport negotiation (USB 1000Hz vs BT 250Hz vs proprietary)
- Per-controller threshold calibration tracks
- GSR grip addon detection and integration

**Controller Profiles Supported**:
- **Sony DualShock Edge** (primary, Attested tier eligible)
- **Microsoft Xbox Series X** (Standard tier, partial L4, no L6)
- **Nintendo Switch Pro** (Standard tier, excellent gyro, no L6)
- **Sony DualShock 4** (Standard tier, touchpad but no adaptive triggers)

**PITL Layer Mapping Logic**:
```
L0 (Physical): ALWAYS (connection, battery)
L1 (PoAC Chain): ALWAYS (228-byte format)
L2 (HID-XInput): ALWAYS (driver injection detection)
L3 (Behavioral ML): ALWAYS (button/stick patterns)
L4 (Mahalanobis): CONDITIONAL (requires gyro OR touchpad)
L5 (Temporal Rhythm): ALWAYS (button timing entropy)
L6 (Active Challenge): CONDITIONAL (requires adaptive triggers)
```

**Tier Eligibility Rules**:
- **Attested**: L0-L6 FULL + adaptive triggers + 1000Hz transport + PHCI certified
- **Standard**: L0-L5 minimum (L4 may be partial, L6 optional)

**Transport Negotiation**:
- Attested tier requires 1000Hz (USB or equivalent)
- Standard tier accepts 250Hz with BT-specific thresholds
- Composite key: `{controller_profile}_{battery_type}_{transport}`

**Decision Output**:
- Controller profile with capability matrix
- Available PITL layers list
- Tier eligibility (standard: bool, attested: bool)
- Recommended transport for tier
- Calibration status (ready/pending/N≥50 required)

**Tools** (8 available):
- detect_controllers: USB/BT enumeration and profiling
- get_controller_profile: Capability matrix lookup
- validate_tier_eligibility: Check tournament tier compatibility
- negotiate_transport: Select transport for tier requirements
- get_pitl_layer_availability: Map controller to PITL layers
- check_gsr_grip_addon: Detect GSR accessory
- get_controller_calibration_status: N sessions per controller type
- recommend_controller_tier: Suggest tier based on hardware

**Fail Mode**: Fail-open (fallback to Standard tier)
- Unknown controller → Standard tier with generic profile
- Missing adaptive triggers → Standard tier (Attested blocked)
- BT transport only → Standard tier with BT thresholds
- GSR not detected → Advisory only (never blocking)

**Epistemic Weight**: 0.25 (infrastructure authority)

**Integration Points**:
- **SessionAdjudicator**: Queries for available layers, adjusts weights
- **CalibrationIntelligenceAgent**: Per-controller threshold tracks
- **TournamentActivationChainAgent**: Tier compatibility validation
- **DeviceProfileRegistry**: Extends with capability matrix

**Invariant Requirements**:
- Attested tier REQUIRES L6 (adaptive triggers mandatory)
- USB/BT structural difference preserved (250Hz ≠ 1000Hz thresholds)
- PHCI certification required for Attested tier
- Controller-agnostic PoAC format (228-byte invariant)

---

## Parallel Expert Spawning

### Cross-Domain Workflows

For complex tasks spanning multiple domains, spawn parallel expert contexts:

**Example 1: Separation Ratio + Calibration**
```
Spawn: SeparationRatioMonitorAgent (measure --full-covariance)
Spawn: CalibrationIntelligenceAgent (check staleness)
Consensus: Compare results, identify if staleness affecting ratio
```

**Example 2: Tournament Readiness**
```
Spawn: TournamentActivationChainAgent (6-signal score)
Spawn: SessionAdjudicator (L0-L6 pipeline health)
Spawn: PoAdAnchorAgent (on-chain anchoring status)
Consensus: Weighted {0.40, 0.35, 0.25} readiness assessment
```

**Example 3: BT Calibration**
```
Spawn: CalibrationIntelligenceAgent (per-battery routing)
Spawn: ClassJDetector (transport-specific detection)
Consensus: Validate BT thresholds before tournament enable
```

**Example 4: Multi-Controller Tournament**
```
Spawn: ControllerHardwareIntelligenceAgent (detect controllers)
Spawn: SessionAdjudicator (adjust weights for partial L4)
Spawn: TournamentActivationChainAgent (validate tier compatibility)
Consensus: Weighted {0.25, 0.35, 0.40} tournament readiness with controller diversity
```

### Consensus Rules

- **Epistemic weights**: Sum to 1.0 per consensus
- **Tie-breaking**: HOLD (no change) over aggressive change
- **Disagreement > 0.30**: Escalate to human operator
- **Unanimous PASS**: Proceed with proposal

---

## Invariant Requirements (All Agents)

Every agent must respect:
1. 228-byte PoAC format (frozen)
2. SHA-256(raw[:164]) chain integrity
3. Threshold min() enforcement (only tighten)
4. dry_run gate (default True until N≥100)
5. W1 documentation (grounded failure modes)
6. Honest separation ratio disclosure

---

**Document Version**: 1.0 (Phase 135)
**Last Updated**: 2026-03-29
**Update Method**: Add new agents as phases complete
**Agent Count**: 16 (Phase 135)

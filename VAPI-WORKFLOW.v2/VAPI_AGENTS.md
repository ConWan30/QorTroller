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

**Your Role**: When reading this file, you are the agent fleet commander. You can spawn parallel expert contexts for any of these 20 agents. You know their fail modes, epistemic weights, and tool inventories. Orchestrate them for complex cross-domain tasks.

> **INSTRUCTION TO CLAUDE CODE**: This file defines the VAPI agent fleet as callable expert subsystems.
> When reading this file, you must:
> 1. Reference specific agents when proposing changes to their domains
> 2. Spawn parallel expert contexts for complex cross-domain work
> 3. Respect each agent's fail mode (fail-open vs fail-closed)
> 4. Use agent-specific tools from the 104 available

---

## Agent Overview

VAPI operates **22 specialized agents** in the bridge service. Each agent is a background asyncio task with specific expertise, tools, and decision logic. This document maps them for Claude Code expert spawning.

> **SYNC NOTE**: Agents 21–22 added in Phases 157/159. Synced 2026-04-05.

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
| 17 | ControllerHardwareIntelligenceAgent (v1) | claude-opus-4-6 | Event-driven | Multi-controller capability mapping, PITL layer availability, tier eligibility, transport negotiation | Fail-open | 8 |
| 18 | AgentCalibrationIntegrityMonitor (ACIM) | — | 15 min | Cross-validates 16 agents' calibration invariants independently; anti-single-validator | Fail-open | 1 |
| 19 | ControllerHardwareIntelligenceAgent | claude-opus-4-6 | 1 hour | Attested vs Standard tier mapping; composite key profile_hash:battery_type:transport_type; default thresholds 7.009/5.367; controller_hardware_profiles table | Fail-open | 8 |
| 20 | EnrollmentAutoGuidanceAgent | — | 1 hour | Synthesizes Phase 151 guidance + Phase 154 stagnation + Phase 152 velocity + Phase 155 controller status; urgency HIGH/MEDIUM/LOW; fires enrollment_complete → TournamentActivationChainAgent | Fail-open | 1 |
| 21 | FleetConsensusSnapshotAgent | — | 1800 sec | WIF-012 dual-condition overall_ready gate; WIF-016 cov_stability_check() 3 regime labels; WIF-013 PoFC hash=SHA-256(sorted_verdicts+ratio+ts_ns); fleet_consensus_snapshot_log | Fail-open | 1 |
| 22 | BiometricPrivacyComplianceAgent | — | 5 min | BP-001 Temporal Biometric Decay TBD(t)=e^(-λt) τ_half=90d; warning when mean_decay_factor<0.25 (≈2 half-lives); privacy_compliance_log; biometric_decay_warning bus event | Advisory | 1 |

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

---

## Agent 18: AgentCalibrationIntegrityMonitor (ACIM) — Phase 148

**Trigger**: Automatic 15-min poll

**Role**: Cross-validate each agent's calibration invariant independently (W1: anti-single-validator)

**Expertise**:
- Runs 16 self-tests every 15 minutes (one per agent in the fleet)
- Checks each agent's calibration invariant independently
- Publishes failures to agent_calibration_health table
- W1 mitigation: no single agent validates itself — cross-validation only

**Decision Output**:
- PASS: Agent calibration invariant satisfied
- FAIL: Calibration invariant violated — alert generated

**Tools** (1 available):
- Tool #105 get_agent_calibration_health (6 keys: agent_count/healthy_count/degraded_count/failed_agents/latest_tests/mcp_server_enabled)

**Fail Mode**: Fail-open
- Self-test failure logged but does not block bridge operation
- Degraded count reported in health endpoint

**Config**: agent_calibration_monitor_enabled=True (default), mcp_server_enabled=False (infrastructure only)

---

## Agent 19: ControllerHardwareIntelligenceAgent — Phase 155

**Trigger**: Automatic 1-hour poll

**Role**: Manages controller hardware profiles and tier mapping. Determines Attested vs Standard tier eligibility per composite key.

**Expertise**:
- Controller auto-detection and tier mapping (DualShock Edge → Attested, Xbox/Switch → Standard)
- Composite key: `profile_hash:battery_type:transport_type`
- Default thresholds anomaly=7.009/continuity=5.367 per profile
- PHCI certification required for Attested tier
- `multi_controller_enabled=False` infrastructure-first default

**Decision Output**:
- Controller profile tier (attested/standard)
- Available PITL layers (L0-L6 for Attested; L0-L5 for Standard)
- Active composite key
- Threshold assignment per profile

**Tools** (8 available):
- Tool #111 get_controller_hardware_status (7 keys: controller_intelligence_enabled/multi_controller_enabled/attested_count/standard_count/active_composite_key/profiles/timestamp)

**Fail Mode**: Fail-open (fallback to DualShock Edge Attested profile)

**Config**: controller_intelligence_enabled=True, multi_controller_enabled=False

**Invariants**:
- DualShock Edge CFI-ZCP1 is ONLY Attested tier device (L0-L6 mandatory)
- Xbox/Switch ALWAYS Standard tier (no L6 adaptive triggers)
- BT thresholds separate from USB — never share 7.009/5.367 across transport types

---

## Agent 20: EnrollmentAutoGuidanceAgent — Phase 156

**Trigger**: Automatic 1-hour poll

**Role**: Synthesizes 4 upstream data sources to produce actionable enrollment guidance with urgency_level. Fires enrollment_complete bus event → TournamentActivationChainAgent when overall_ready=True.

**Expertise**:
- Synthesizes: Phase 151 enrollment capture guidance + Phase 154 stagnation status + Phase 152 velocity status + Phase 155 controller hardware status
- Computes urgency_level: HIGH (stagnant + sessions_needed_total > 0), MEDIUM (velocity plateau), LOW (on track)
- `enrollment_complete` fires when `sessions_needed_total == 0` (count-gate)
- **W1 OPEN**: count-gate does NOT check `defensible=True` from separation_defensibility_log — Phase 157 candidate dual-condition enforcement

**Decision Output**:
- sessions_needed_total: how many more capture sessions required
- overall_ready: True/False
- recommended_action: human-readable instruction
- urgency_level: HIGH/MEDIUM/LOW
- estimated_days: projected completion
- stagnant_probe_count: number of probe types in stagnation

**Tools** (1 available):
- Tool #112 get_enrollment_auto_guidance_status (8 keys: sessions_needed_total/overall_ready/recommended_action/urgency_level/estimated_days/stagnant_probe_count/velocity_per_day/timestamp)

**Fail Mode**: Fail-open (advisory; never blocks capture or enrollment)

**Config**: enrollment_auto_guidance_enabled=True (default)

**Bus Event**: `enrollment_complete` → TournamentActivationChainAgent (agent #16); fires ONLY when `overall_ready=True`

**W1 (Phase 157 candidate)**: Dual-condition enforcement — `enrollment_complete` should require BOTH `sessions_needed_total == 0` AND `defensible=True` from `separation_defensibility_log`. Currently only count-gate enforced.

---

## Agent 21: FleetConsensusSnapshotAgent — Phase 157

**Trigger**: Automatic (interval-based, fleet_consensus_snapshot_interval_s=1800)

**Role**: Captures fleet-wide consensus snapshots (PoFC = Proof of Fleet Consensus). Enforces dual-condition overall_ready gate (WIF-012 closure): `sessions_needed_total==0 AND defensible==True`. Detects covariance regime transitions (WIF-016).

**Tools** (1 available):
- Tool #113 get_fleet_consensus_snapshot (6 keys: fleet_consensus_enabled/total_snapshots/latest_pofc_hash/latest_agent_count/latest_separation_ratio/timestamp)

**Config**: fleet_consensus_enabled=True, cov_stability_margin_np=0.5, fleet_consensus_snapshot_interval_s=1800

---

## Agent 22: BiometricPrivacyComplianceAgent — Phase 159

**Trigger**: Automatic (event-driven on new biometric records)

**Role**: BP-001 Temporal Biometric Decay monitoring. TBD(t) = e^(-λt), λ = ln(2)/τ_half, τ_half=90d. Fires `biometric_decay_warning` bus event when mean_decay_factor < 0.25 (≈2 half-lives).

**Tools** (1 available):
- Tool #116 get_biometric_privacy_status (8 keys: biometric_privacy_enabled/bp001_half_life_days/records_monitored/records_expired/mean_decay_factor/warning_triggered/privacy_budget_epsilon/timestamp)

**Config**: biometric_privacy_enabled=True, bp001_half_life_days=90.0

---

## Agent 23: SeparationRatioRecoveryAgent — Phase 173

**Trigger**: Automatic (fires when new separation ratio snapshot available)

**Role**: Detects P1 temporal non-stationarity from converging-downward ratio trend (N=11→1.261, N=14→0.789, N=20→0.569). Computes `compute_trend_velocity()` via linear regression over last 5 snapshots. Recommends recovery action.

**Decision Output**:
- trend_velocity: Mahalanobis ratio change per snapshot (negative = converging down)
- recovery_action: STABLE | AGE_WEIGHTING | P1_RE_ENROLLMENT | MORE_SESSIONS
- P1_RE_ENROLLMENT when velocity ≤ -0.05/snapshot
- AGE_WEIGHTING when mildly negative trend

**Tools** (1 available):
- Tool #123 get_separation_ratio_recovery_status (8 keys: separation_ratio_recovery_enabled/ratio/trend_velocity/recovery_needed/recovery_action/snapshots_used/last_snapshot_ts/timestamp)

**Bus Event**: `ratio_recovery_needed` when recovery_needed=True

---

## Agent 24: AgeWeightedRatioPersistenceAgent — Phase 175

**Trigger**: Automatic (fires after analyze_interperson_separation.py --session-age-weight run)

**Role**: Persists session-age-weighted separation ratio analysis. Detects temporal drift between raw ratio and age-weighted ratio. WIF-025 CLOSED.

**Decision Output**:
- temporal_drift_index (TDI) = raw_ratio - age_weighted_ratio
- TDI > 0.05 → P1_NONSTATIONARITY (old sessions inflate ratio estimate)
- TDI < -0.05 → IMPROVING (new sessions produce stronger separation)
- |TDI| ≤ 0.05 → STABLE

**Tools** (1 available):
- Tool #124 get_age_weight_analysis_status (8 keys: age_weight_analysis_enabled/raw_ratio/age_weighted_ratio/temporal_drift_index/halflife_days/n_sessions_used/drift_direction/timestamp)

**Config**: age_weight_analysis_enabled=True

---

## Agent 25: PoACChainIntegrityMonitor — Phase 176

**Trigger**: Automatic (periodic audit of SHA-256 chain linkage)

**Role**: Audits SHA-256 chain linkage across all PoAC records. integrity_score = valid_links / total_records. W1 mitigation: only aggregate counts exposed — no broken record IDs returned (WIF-026 W1 closure). Vacuous integrity (total=0) → 1.0.

**Decision Output**:
- integrity_score: 0.0–1.0 (1.0 = fully intact SHA-256 chain)
- audit_passed: True when broken_links == 0
- broken_links: count only (no IDs — prevents injection window disclosure)

**Tools** (1 available):
- Tool #125 get_poac_chain_integrity (input: device_id optional; 8 keys: chain_integrity_enabled/device_id/total_records/valid_links/broken_links/integrity_score/audit_passed/timestamp)

**Fail Mode**: Fail-open (audit failure must not block tournament gate)

**Config**: chain_integrity_enabled=True

**W2 (WIF-026)**: isChainIntegrous() as third composable primitive alongside isFullyEligible() and isRecorded()

---

## Agent 26: ProtocolMaturityScoringAgent — Phase 177

**Trigger**: Automatic (synthesizes signals from 6 upstream agents)

**Role**: Synthesizes 6 agent signals into a unified maturity_score (0.0–1.0). Single oracle for protocol production-readiness. W2 opportunity: maturity_score ≥ 0.85 as 7th composable tournament primitive + DePIN data marketplace trustworthiness oracle.

**Maturity Formula**:
| Component | Weight | Source |
|-----------|--------|--------|
| separation | 0.25 | separation_defensibility_log ratio |
| chain_integrity | 0.20 | poac_chain_audit_log integrity_score |
| consent | 0.15 | consent_ledger active coverage |
| biometric_freshness | 0.15 | privacy_compliance_log mean_decay_factor |
| agent_calibration | 0.15 | agent_calibration_health latest_pass_rate |
| enrollment | 0.10 | enrollment_auto_guidance_log |

**Tiers**: ALPHA (<0.50) / BETA (0.50–0.85) / PRODUCTION_CANDIDATE (≥0.85)
**Current tier**: ALPHA (separation_ratio=0.569 < 0.70 gate → separation_component low)

**Tools** (1 available):
- Tool #126 get_protocol_maturity_score (10 keys: protocol_maturity_enabled/maturity_score/maturity_tier/separation_component/chain_integrity_component/consent_component/biometric_freshness_component/agent_calibration_component/enrollment_component/timestamp)

**SDK**: ProtocolMaturityScoringResult(9 slots) + VAPIProtocolMaturityScoring
**NOTE**: Class renamed from ProtocolMaturityResult/VAPIProtocolMaturity to avoid Phase 104 collision (2026-04-08).

**Config**: protocol_maturity_enabled=True

**W1 (WIF-027)**: Maturity score gaming by silencing agents → silence_penalty (Phase 178 candidate)
**W2 (WIF-027)**: maturity_score ≥ 0.85 as DePIN marketplace trustworthiness oracle

---

**Document Version**: 1.4 (Phase 180)
**Last Updated**: 2026-04-09
**Update Method**: Add new agents as phases complete
**Agent Count**: 26 (Phase 180 — Phases 178/179/180 added infrastructure tools only; no new agents)
**SYNC NOTE**: Agents 21–26 added in Phases 157/159/173/175/176/177. Phases 178–180 added Tools #127/128/129. Synced 2026-04-09.
**Next agents**: #27 PersonaBreakDetectorAgent (Phase 182 candidate); #28 MaturityElevationGateAgent (Phase 183 candidate).

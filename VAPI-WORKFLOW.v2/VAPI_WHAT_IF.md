# VAPI WHAT_IF — For Claude Code Context

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

**Your Role**: When reading this file, you are the risk/opportunity analyst. You must think in three recursive layers: W1 (protocol risks), W2 (novel opportunities), W3 (meta-risks to the system itself). Every proposal must be grounded, exclusive to VAPI, and phase-coherent.

> **INSTRUCTION TO CLAUDE CODE**: This file is the recursive risk/opportunity ontology for VAPI.
> When reading this file, you must:
> 1. Check W1_LAYER before proposing features (avoid known failure modes)
> 2. Reference W2_LAYER for novel opportunities (build on validated ideas)
> 3. Monitor W3_LAYER for meta-risks (protect the protection system)
> 4. Add new entries with evidence and phase candidates
> 5. Never delete entries — append-only with status updates

---

## Layer Structure

VAPI WHAT_IF operates in three recursive layers:

- **W1_LAYER**: Risks to the VAPI protocol (failure modes)
- **W2_LAYER**: Opportunities for VAPI enhancement (novel features)
- **W3_LAYER**: Meta-risks (risks to the risk system itself)

**Recursion**: W3 protects W1/W2, W1/W2 advance the protocol, protocol state feeds W3 monitoring.

---

## W1_LAYER: Known Failure Modes

> **INSTRUCTION**: Before proposing any feature, check if it addresses or respects these failure modes.

### W1-001: ioSwarm Node-Pool Homogeneity (Phase 110)

**Failure Mode**: MINT_QUORUM=0.80 trivially satisfied if all 5 nodes operated by same entity, collapsing distributed consensus to 1-party signature.

**Implication**:
- Soulbound VHP tokens minted without genuine distributed authorization
- Swarm fingerprint (SHA-256 of node_verdicts) cryptographically valid but economically meaningless
- Fail-CLOSED direction preserved, but distributed guarantee voided
- Indistinguishable from legitimate quorum on-chain

**Detection**:
- All 5 node staker_addresses identical or controlled by same entity
- Swarm fingerprint shows self-consistency, not distributed consensus
- No way to detect from on-chain data alone

**Mitigation Available**:
- ✅ VAPISwarmOperatorGate.sol: enforces minimum 3 distinct staker addresses in node pool
- ✅ Stake-weight cap: 1.5× per node prevents whale capture
- ✅ Phase 112 candidate: isSufficientlyDecentralized() as additive 5th gate on POST /agent/mint-vhp

**Status**: Code complete, deployment **BLOCKED** (wallet ~0.35 IOTX < 0.40 needed)

**Evidence**: scripts/vapi-vhp-mint-swarm-agent.json (task spec)

**First Identified**: Phase 109A (2026-03-15)

**Claude Code Guidance**: When working on ioSwarm, always check node diversity. Never enable minting without VAPISwarmOperatorGate validation.

---

### W1-002: Separation Ratio Calibration Deadline (Phase 108/129)

**Failure Mode**: Inter-person separation ratio remains <1.0 through Phase 113 if touchpad recapture hardware session indefinitely deferred.

**Implication**:
- TOURNAMENT BLOCKER persists (ratio > 1.0 is non-negotiable TGE gate)
- All 4 tournament readiness conditions unmet
- VHP minting proceeds on testnet but live tournament integration impossible
- Token launch blocked regardless of ioSwarm phase completion

**Current State**:
- Diagonal approximation: 0.474 (measured, Phase 121)
- Tikhonov hypothesis: >0.60 or >1.0 possible (unverified, Phase 129)
- Sessions captured: N=177 USB, 3 players
- BT calibration: 0/50 sessions (separate workstream)

**Detection**:
- separation_ratio_snapshots table shows no progress toward 1.0
- 6-signal tournament readiness score < 0.90
- Tikhonov analysis not yet executed

**Mitigation Available**:
- ✅ Schedule dedicated DualShock Edge + NCAA CFB 26 session NOW
- ✅ Run analyze_interperson_separation.py --full-covariance (Tikhonov)
- ✅ No software phase can substitute for hardware calibration
- ⚠️ If Tikhonov < 1.0: Requires post-Phase-17 touchpad recapture

**Status**: HYPOTHESIS — Tikhonov correction may reveal breakthrough already achieved

**Evidence**: N=177 corpus, 3 players, resting-grip normalization applicable

**First Identified**: Phase 108 (2026-03-10)

**Claude Code Guidance**: Separation ratio is THE tournament blocker. All other work is secondary until this resolves. Tikhonov analysis is the immediate critical path.

---

### W1-003: L4 Threshold Staleness (Phase 123)

**Failure Mode**: Feature dimension drift (12→13) applies stale thresholds to live 13-dimensional space, degrading L4 precision silently.

**Mechanism**:
- Phase 121: touchpad_spatial_entropy added (index 12)
- Old thresholds: calibrated on 12 dimensions (Phase 46)
- Application: 12-dim threshold on 13-dim data = partial feature ignorance
- Result: False positives/negatives increase silently

**Detection**:
- l4_calibration_log staleness flag: live_feature_dim (13) ≠ calibration_feature_dim (12)
- Unexpected L4 anomaly rates
- Mahalanobis scores drifting from historical baselines

**Mitigation Available**:
- ✅ Phase 123: Staleness detection (stale=True flag in logs)
- ✅ Automatic recalibration suggestion when stale=True
- ✅ Per-battery threshold tracks (Phase 124) enable granular updates
- ✅ Recalibration via Phase 134 pipeline

**Status**: DETECTED in N=177 corpus (currently stale=True)

**Evidence**: calibration_feature_dim=12, live_feature_dim=13 in logs

**First Identified**: Phase 123 (2026-03-22)

**Claude Code Guidance**: Always check staleness before trusting L4 scores. Stale thresholds are WRONG even if mathematically computed.

---

### W1-004: BT Transport Threshold Pollution (Phase 120)

**Failure Mode**: USB-calibrated thresholds (1000 Hz) applied to BT sessions (250 Hz), causing false L4 positives.

**Mechanism**:
- USB: ~1000 samples/window (50ms coverage)
- BT: ~250 samples/window (200ms coverage)
- Human micro-tremor (8-12 Hz) completes more cycles per window at BT rates
- Gyro_std variance artificially elevated → higher Mahalanobis distance

**Current State**:
- BT_L4_ANOMALY_THRESHOLD: 7.009 (mirrors USB — WRONG)
- BT sessions captured: 0/50 minimum
- BT calibration: NOT DONE

**Mitigation Available**:
- ✅ Separate BT calibration required (N≥50 sessions)
- ✅ Per-battery threshold tracks enable BT-specific values
- ✅ BT transport detection in session metadata
- ⚠️ BT transport currently disabled (bt_transport_enabled=False)

**Status**: ACKNOWLEDGED — BT calibration separate workstream, not tournament-blocking

**Evidence**: bluetooth-threshold-analysis.md (structural difference documented)

**First Identified**: Phase 120 (2026-03-18)

**Claude Code Guidance**: Never enable BT transport without N≥50 calibration. USB and BT thresholds are structurally incompatible.

---

### W1-005: Confidence Multiplier Penalty (Phase 122)

**Failure Mode**: bt_strat_ratio as VHP confidence multiplier penalizes non-touchpad sessions (ratio=0.0 → confidence=0.0).

**Mechanism**:
- Touchpad-dominant sessions: bt_strat_ratio > 0
- No-touchpad sessions: bt_strat_ratio = 0
- Multiplier: confidence_score *= max(floor, min(1.0, bt_strat_ratio))
- Result: No-touchpad sessions get near-zero confidence

**Current State**:
- confidence_multiplier_enabled: False (default, safety)
- confidence_multiplier_floor: 0.0
- Per-battery lookup: Not yet implemented

**Mitigation Available**:
- ✅ Disabled by default (no penalty applied)
- ✅ Per-battery multiplier lookup candidate (Phase 124+)
- ✅ Advisory-only mode (never hard-gate)

**Status**: MITIGATED (disabled, not removed)

**Evidence**: l4_calibration_log shows touchpad vs non-touchpad stratification

**First Identified**: Phase 122 (2026-03-20)

**Claude Code Guidance**: If enabling confidence multiplier, implement per-battery lookup first. Never apply uniform multiplier across battery types.

---

### W1-006: Wallet Funding Exhaustion (Ongoing)

**Failure Mode**: Bridge wallet (~0.35 IOTX) insufficient for contract deployments, blocking Phase 130B+ on-chain progress.

**Requirements**:
- Current: ~0.35 IOTX
- VAPISwarmOperatorGate.sol: ~0.13 IOTX
- Total needed: ~0.40 IOTX
- Shortfall: ~0.05 IOTX

**Impact**:
- Phase 130B deployment BLOCKED
- ioSwarm live node registration blocked
- Tournament operator gate incomplete

**Mitigation**:
- Faucet request or bridge funding required
- Non-critical path for Tikhonov breakthrough
- Critical path for full tournament deployment

**Status**: BLOCKING on-chain work, not blocking analysis

**Claude Code Guidance**: Check wallet balance before proposing any contract deployment. Faucet funding is a prerequisite for on-chain phases.

---

## W2_LAYER: Novel Opportunities

> **INSTRUCTION**: Build on these opportunities. Each requires exclusivity argument (why VAPI-only).

### W2-001: Proof of Adjudication (PoAd) as Composable Primitive (Phase 111)

**Opportunity**: Second on-chain primitive enabling tournament contracts to verify clean adjudication history alongside isFullyEligible().

**Mechanism**:
1. PoAd_hash = SHA-256(sorted(node_verdicts_json) + quorum_str + ts_ns_str)
2. AdjudicationRegistry.sol stores per-cycle digests
3. hasCleanAdjudicationHistory(deviceId, lookback_days) query
4. Tournament integrators choose: isFullyEligible() OR hasCleanAdjudicationHistory() OR both

**Current State**:
- PoAdAnchorAgent: Active (60-sec cycle)
- AdjudicationRegistry.sol: Deployed (Phase 111)
- PoAd on-chain: Enabled for testnet

**Exclusivity**:
- No competitor has distributed per-device adjudication records
- Presupposes ioSwarm node_verdicts anchored to PoAC chain integrity (SHA-256(raw[:164]) + 228B format)
- Only valid because PoAC is already anchored

**Phase Candidate**: Phase 111 (COMPLETE), Phase 112 (integration)

**Dependencies**: ioSwarm node_verdicts on-chain (Phase 110)

**First Identified**: wif_1774484928.md (2026-03-27)

**Claude Code Guidance**: Promote PoAd as differentiator for tournament integrators. Two primitives > one primitive.

---

### W2-002: SeparationRatioRegistry.sol (Phase 112 Candidate)

**Opportunity**: On-chain immutable audit trail of each separation ratio measurement, anchored to calibration session hash and player count.

**Mechanism**:
1. separation_ratio_commitment = SHA-256(ratio_str + N_sessions + player_ids_sorted + ts_ns)
2. Operator signature on IoTeX L1
3. Cryptographic proof that ratio > 1.0 confirmed empirically before TGE
4. Legally defensible sequencing compliance

**Use Case**:
- Tournament regulators audit ratio measurement
- Token launch legal defense ("we proved human differentiation")
- Whitepaper reproducibility (on-chain evidence)

**Exclusivity**:
- VAPI's Mahalanobis inter-person distance metric is only calibrated biometric separation measure in anti-cheat
- No competitor has separation ratio as token launch gate
- 177-session hardware corpus is unique dataset

**Phase Candidate**: Phase 137+ (post-breakthrough; Phase 136 = DualSense Audio Router, complete)

**Dependencies**: Tikhonov verification that ratio > 1.0

**First Identified**: wif_1774484928.md (2026-03-27)

**Claude Code Guidance**: Prepare contract spec now. Deploy immediately after Tikhonov confirms >1.0.

---

### W2-003: Tikhonov Auto-Detection at N>150 (Phase 137 Candidate)

**Opportunity**: Automatic --full-covariance when corpus exceeds stability threshold.

**Mechanism**:
1. analyze_interperson_separation.py detects N>150 automatically
2. Switches from --diagonal (fast) to --full-covariance (precise)
3. Applies Tikhonov regularization for numerical stability
4. Updates confidence intervals based on method precision

**Benefits**:
- No operator decision required (automatic precision upgrade)
- Large corpora get full analysis without manual flag
- Measurement imprecision reduced as N grows

**Exclusivity**:
- VAPI's 177-session hardware corpus is only anti-cheat dataset with N>150
- Tikhonov regularization requires specific feature correlation structure (VAPI-specific)
- No competitor has longitudinal hardware calibration data

**Phase Candidate**: Phase 137 (infrastructure completion; Phase 136 = DualSense Audio Router, complete)

**Dependencies**: Verified Tikhonov accuracy on VAPI data

**First Identified**: VAPI_MEMORY.md 2026-03-20 entry

**Claude Code Guidance**: Implement as default behavior for N>150. Log method used for reproducibility.

---

### W2-004: Private Calibration Beta (Phase 137 Candidate)

**Opportunity**: Invite-only calibration program for trusted players to accelerate separation ratio improvement.

**Mechanism**:
1. Beta client with enhanced session capture (more metadata)
2. Trusted player cohort (N=10-20 players, not just 3)
3. Dedicated hardware loaners (DualShock Edge)
4. Direct feedback loop: session → analysis → threshold update

**Benefits**:
- Faster calibration than public beta
- Higher-quality data (dedicated hardware, consistent setup)
- Player incentive alignment (early VHP eligibility)

**Exclusivity**:
- VAPI's hardware-rooted approach requires physical controller
- No competitor can replicate without DualShock Edge integration
- Beta infrastructure (enrollment, credentialing) already exists

**Phase Candidate**: Phase 137 (post-TGE preparation)

**Dependencies**: Tournament readiness (separation > 1.0)

**First Identified**: wif_1774484928.md (2026-03-27)

**Claude Code Guidance**: Design beta infrastructure now. Deploy after TGE to accelerate ecosystem growth.

---

### W2-005: Multi-Controller Ecosystem (Phase 136 Candidate)

**Opportunity**: VAPI becomes the universal hardware authenticator for competitive gaming, supporting Xbox, Switch, and third-party controllers alongside DualShock Edge.

**Mechanism**:
1. ControllerHardwareIntelligenceAgent (Agent #17) maps capabilities to PITL layers
2. Controller profiles (YAML) define feature matrices per device
3. Tier eligibility: Attested (L0-L6 full) vs Standard (L0-L5 partial)
4. Per-controller calibration tracks (composite key: profile+battery+transport)
5. PHCI certification program for hardware partners

**Benefits**:
- 3× addressable market (Xbox + Switch + PC gamepad users)
- Tournament organizers can support all major controllers
- PHCI certification generates revenue
- VAPI becomes industry standard for hardware attestation

**Exclusivity**:
- No competitor supports hardware-rooted attestation across controller brands
- VAPI's PITL stack is uniquely adaptable to partial feature sets
- Controller-agnostic PoAC format (228-byte) works with any HID device
- No competitor has 177-session hardware corpus for calibration reference

**Phase Candidate**: Phase 136 (ControllerHardwareIntelligenceAgent)

**Dependencies**: 
- Agent #17 implementation
- N≥50 calibration per new controller type (Xbox, Switch)
- PHCI certification API

**First Identified**: This document (2026-03-29)

**Claude Code Guidance**: Promote VAPI as the "Universal Authenticator" for gaming hardware. Controller diversity becomes competitive advantage, not liability.

---

## W3_LAYER: Meta-Risks (Risks to the Risk System)

> **INSTRUCTION**: These risks threaten the WHAT_IF system itself. Monitor continuously.

### W3-001: WHAT_IF Corpus Contamination

**Meta-Risk**: AutoResearch loop proposes WHAT_IF entries that are:
- Physically implausible (violates W1 grounded requirement)
- Duplicate of existing entry (corpus bloat)
- Mislabeled W1/W2 (wrong category)

**Implication**:
- Risk ontology degrades
- Future cycles reference invalid risks
- Decision quality declines

**Detection**:
- Manual audit of new WHAT_IF entries
- Fuzzy matching against existing entries
- W1 groundedness check (physically/cryptographically/economically)

**Mitigation**:
- ✅ Eval harness WHAT_IF quality criteria (W1_CRITERIA, W2_CRITERIA)
- ✅ Minimum 0.20 weight in scoring
- ✅ Mandatory "First identified" timestamp and evidence field
- ✅ Human review of W3 additions (meta-meta-risk)

**Status**: MONITORING — no contamination detected

**First Identified**: This document (2026-03-29)

---

### W3-002: AutoResearch Invariant Violation Proposal

**Meta-Risk**: Loop proposes change to VAPI_INVARIANTS.md or violates invariant in implementation.

**Implication**:
- Cascading failure across firmware↔bridge↔contract
- System incompatibility
- 228-byte format corruption

**Detection**:
- Eval harness invariant check (instant fail if ANY missing)
- Golden hash verification in VAPI_INVARIANTS.md footer
- Parse and verify before ANY proposal generation

**Mitigation**:
- ✅ VAPI_INVARIANTS.md read-only (file system permissions)
- ✅ Pre-flight SHA-256 check
- ✅ Explicit invariant checklist in cycle prompt template
- ✅ 30% scoring weight on invariants_preserved

**Status**: PROTECTED — no violations to date

**First Identified**: This document (2026-03-29)

---

### W3-003: Claude Context Window Truncation

**Meta-Risk**: Long sessions exceed context window; critical invariants "forgotten" by prompt truncation.

**Implication**:
- Late-session proposals may violate invariants
- W1/W2 entries proposed without proper grounding
- Agent expertise lost from context

**Detection**:
- Monitoring token usage (Claude Code shows remaining context)
- Invariant presence check in generated proposals
- Proposal quality degradation over session length

**Mitigation**:
- ✅ VAPI_INVARIANTS.md as explicit file read (not context-dependent)
- ✅ Short cycle length (1 improvement per cycle, not 5)
- ✅ Mid-session invariant re-injection prompt
- ✅ File-based context (not just conversation history)

**Status**: MONITORING — use short cycles

**First Identified**: This document (2026-03-29)

---

### W3-004: Expert Agent Consensus Failure

**Meta-Risk**: Parallel expert agents disagree on proposal; epistemic weighting fails.

**Implication**:
- No consensus reached
- System deadlocks or makes arbitrary decision
- Human operator escalation required repeatedly

**Detection**:
- Cross-agent vote divergence > 0.30
- Low confidence scores across all agents
- HOLD decisions with no clear path forward

**Mitigation**:
- ✅ Explicit epistemic weighting: {0.35, 0.35, 0.30} for 3-agent votes
- ✅ Tie-breaking: HOLD (no change) over aggressive change
- ✅ Escalation to human operator on HOLD×2
- ✅ Consensus timeout (fail to HOLD after 3 rounds)

**Status**: THEORETICAL — not yet triggered

**First Identified**: This document (2026-03-29)

---

### W3-005: Corpus Evidence Degradation

**Meta-Risk**: Session files corrupted, deleted, or modified; forensic integrity lost.

**Implication**:
- Tournament legal defense compromised
- Whitepaper reproducibility violated
- 177-session corpus value destroyed

**Detection**:
- Periodic SHA-256 verification of session files
- Corpus hash (Merkle root) comparison
- Backup integrity checks

**Mitigation**:
- ✅ VAPI_CORPUS.md with integrity hashes
- ✅ Multiple backup locations (local, cloud, git LFS)
- ✅ Append-only retention (no deletions)
- ✅ Legal hold status for tournament evidence

**Status**: PROTECTED — integrity verified on [date]

**First Identified**: This document (2026-03-29)

---

## Corpus Evolution Rules

### Entry Requirements

**W1 additions**:
- Require: Evidence of failure mode OR theoretical grounding
- Must: Specify physically/cryptographically/economically grounded mechanism
- Must: Include detection method
- Must: Include mitigation (even if "none yet")

**W2 additions**:
- Require: Exclusivity argument (why VAPI-only)
- Must: Specify phase candidate
- Must: Include mechanism description
- Must: Show dependency chain

**W3 additions**:
- Require: Recursive justification (risk to risk system)
- Must: Show how it threatens W1/W2 integrity
- Must: Include detection method for meta-risk
- Must: Include mitigation (often process-based)

### Status Transitions

```
OPEN → MITIGATED → CLOSED (with phase number)
  ↓
HYPOTHESIS (pending verification)
  ↓
CONFIRMED / REJECTED
```

**Never delete**: All entries preserved for historical audit.

---

**Document Version**: 1.0 (Phase 135)
**Last Updated**: 2026-03-29
**W1 Count**: 6 entries
**W2 Count**: 4 entries
**W3 Count**: 5 entries
**Update Method**: Append-only, status updates inline

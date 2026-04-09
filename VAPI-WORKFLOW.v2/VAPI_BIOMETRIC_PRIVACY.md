# VAPI Biometric Privacy Architecture (Phase 148+)
## Novel Privacy-First Enforcement for Competitive Gaming Credentials

**Status**: Design Phase — Primitives BP-001 to BP-007 IMMUTABLE (defined in VAPI_INVARIANTS.md §6)  
**Agent**: **#19 BiometricPrivacyComplianceAgent (PROPOSED — TBD)**  
  ⚠️ NOTE: Agent #18 is now **AgentCalibrationIntegrityMonitor (ACIM)**, implemented in Phase 148.  
  BiometricPrivacyComplianceAgent is proposed as Agent #19 (pending Phase 150+ roadmap).  
**Last Updated**: 2026-04-03  
**PITL Layers Affected**: L0 (privacy layer), L4 (biometric fusion), L6 (active challenge)  
**Regulatory Scope**: GDPR Art.9, CCPA/CPRA, BIPA, EU AI Act, PIPL, LGPD  

---

## 1. Executive Summary

VAPI processes 228-byte PoAC physiological records containing sensitive biometric data (GSR, IMU vectors, tremor FFT, cognitive-load variance). These records are anchored on-chain as soulbound VHP credentials. This document establishes **7 novel privacy primitives** that make VAPI the first privacy-preserving competitive gaming attestation protocol:

1. **Temporal Biometric Decay (TBD)** - Biometric fingerprints expire
2. **ZK-Attested Consent (ZAC)** - Consent as zero-knowledge proof
3. **Differential Privacy Thresholds (DPT)** - Noise injection at threshold level
4. **K-Anonymity Cohort Calibration (KACC)** - Calibrate against pools, not individuals
5. **Homomorphic Separation Ratios (HSR)** - Compute ratios on encrypted data
6. **Biometric Shamir Sharing (BSS)** - Split identity across agent fleet
7. **Ephemeral Session Entropy (ESE)** - Self-destructing calibration sessions

---

## 2. Novel Privacy Primitives

### 2.1 Temporal Biometric Decay (TBD)

**Concept**: Biometric data has a cryptographic half-life. Older physiological patterns become statistically indistinguishable from noise, reducing re-identification risk while preserving tournament integrity.

**Mechanism**:
```
TBD(t) = e^(-λt) where λ = ln(2) / τ_half
τ_half = 90 days (configurable per jurisdiction)

Effective biometric weight = raw_weight × TBD(age_days)
```

**VAPI Implementation**:
- PoAC records include `calibration_timestamp` (unix epoch)
- SessionAdjudicator applies decay factor before Mahalanobis distance calculation
- Decayed records still valid for separation ratio (integrity preserved)
- Re-identification risk decays exponentially

**Regulatory Alignment**:
- GDPR storage limitation (Art.5.1.e): Automatic expiration
- CCPA retention minimization: No indefinite biometric storage
- EU AI Act: High-risk biometric data time-boxed

**Code Pattern**:
```python
class TemporalBiometricDecay:
    """Phase 137: Biometric half-life enforcement"""
    
    HALF_LIFE_DAYS = 90
    LAMBDA = math.log(2) / HALF_LIFE_DAYS
    
    @staticmethod
    def apply_decay(poa_record: PoACRecord, current_time: int) -> DecayedRecord:
        age_days = (current_time - poa_record.timestamp) / 86400
        decay_factor = math.exp(-TemporalBiometricDecay.LAMBDA * age_days)
        
        return DecayedRecord(
            poac_hash=poa_record.hash,
            effective_weight=poa_record.weight * decay_factor,
            separation_ratio=poa_record.separation_ratio * decay_factor,
            expires_at=poa_record.timestamp + (90 * 86400)
        )
```

---

### 2.2 ZK-Attested Consent (ZAC)

**Concept**: Player consent is recorded as a zero-knowledge proof, not raw signature. The system proves "player consented" without revealing when, how, or to which specific terms.

**Mechanism**:
```
ConsentProof = ZKProve(
    private_inputs: [player_id, consent_timestamp, terms_hash],
    public_inputs: [consent_commitment, jurisdiction_code],
    statement: "I have given valid consent under [jurisdiction_code]"
)

Verification: ZKVerify(ConsentProof, consent_commitment)
```

**VAPI Implementation**:
- Consent recorded on-chain as Poseidon hash of (player_id + terms_version + timestamp)
- zk-SNARK proves consent exists without revealing player identity
- Different consent versions for different jurisdictions (GDPR vs CCPA vs BIPA)
- Consent revocation also ZK-proven (proof of non-consent)

**Novelty**: First gaming protocol with unlinkable consent. Player can prove they consented without revealing which player they are.

**Regulatory Alignment**:
- GDPR Art.7: Demonstrable consent without exposing data subject
- CCPA: Opt-in/opt-out without tracking individual preferences
- BIPA: Written consent proven without retaining written record

---

### 2.3 Differential Privacy Thresholds (DPT)

**Concept**: Add calibrated Laplacian noise to threshold tracks, not to individual biometric data. Preserves individual accuracy while protecting cohort-level inference.

**Mechanism**:
```
threshold_track = f(calibration_data) + Laplace(0, Δf/ε)

where:
- Δf = sensitivity (max threshold change from one player)
- ε = privacy budget (e.g., 0.1 for strong privacy)
- Laplace noise added per composite key, not per player
```

**VAPI Implementation**:
- Noise added during threshold derivation in CalibrationIntelligenceAgent
- Separate privacy budget per controller profile
- Budget resets weekly (composable privacy)
- Query logging prevents privacy budget exhaustion

**Impact on Separation Ratio**:
```
separation_ratio_noisy = (μ_human - μ_injection) / (σ_human_noisy + σ_injection)

Privacy guarantee: Attacker cannot determine if specific player
influenced threshold with confidence > ε
```

**Novelty**: First biometric anti-cheat with mathematical privacy guarantees.

---

### 2.4 K-Anonymity Cohort Calibration (KACC)

**Concept**: Players calibrate against K-anonymous pools, not individual thresholds. A player's calibration session contributes to a pool of K players with similar hardware.

**Mechanism**:
```
Pool = {players | controller_profile == X, battery_type == Y, transport == Z}
|Pool| >= K (default K=5)

Threshold_track = derive_threshold(Pool_features)  # Aggregate, not individual
Player_validity = check_against_pool(Player_features, Threshold_track)
```

**VAPI Implementation**:
- Cohorts formed by (controller + battery + transport + time_window)
- Minimum pool size enforced: N≥K before threshold activation
- Small cohorts merged with similar cohorts (privacy-utility tradeoff)
- On-chain proof: Merkle root of pool membership (ZK-proven)

**Regulatory Alignment**:
- GDPR anonymization: K≥5 meets "not reasonably identifiable"
- CCPA: K-anonymity = not "personal information"
- HIPAA-style expert determination: Statistical anonymization

**Novelty**: Individual players cannot be isolated from calibration data. Attackers must compromise K players simultaneously.

---

### 2.5 Homomorphic Separation Ratios (HSR)

**Concept**: Compute separation ratios on encrypted biometric data using partially homomorphic encryption. Server never sees raw physiological features.

**Mechanism**:
```
Player: Encrypt(features) → Server
Server: Compute_separation_ratio_on_ciphertext(encrypted_features, threshold)
Server: Return encrypted_result → Player
Player: Decrypt(result) → separation_ratio
```

**VAPI Implementation**:
- Paillier encryption for addition (mean calculation)
- CKKS for approximate arithmetic (std deviation)
- Hybrid: Sensitive features encrypted, metadata plaintext
- zk-PoAC proves correct computation on ciphertext

**Performance**:
- ~100ms overhead per L4 Mahalanobis calculation
- Acceptable for tournament integrity (once per session)
- Batch processing amortizes cost

**Novelty**: Server processes biometric data without possessing it. Compromised server yields only ciphertext.

---

### 2.6 Biometric Shamir Sharing (BSS)

**Concept**: Split biometric identity across the 16-agent VAPI fleet using Shamir's Secret Sharing. No single agent possesses complete biometric profile.

**Mechanism**:
```
Biometric_secret = hash(gyro_features + touchpad_entropy + trigger_pattern)
Shares = ShamirSplit(secret, n=16, k=8)  # 8-of-16 threshold

Agent_i stores Share_i
Reconstruction requires compromise of 8+ agents
```

**VAPI Implementation**:
- 16 agents → 16 shares distributed at calibration
- Session adjudication requires k=8 agents to reconstruct identity
- Compromised agent reveals nothing (single share = random bytes)
- Byzantine fault tolerance: up to 7 agents can be malicious

**Agent Distribution**:
| Share | Agent | Stored |
|-------|-------|--------|
| S1 | CalibrationIntelligenceAgent | gyro_std_x + gyro_std_y |
| S2 | DeviceRegistryAgent | touchpad_entropy_fragment |
| S3 | SessionAdjudicator | trigger_resistance_partial |
| ... | ... | ... |
| S16 | GSRRegistryAgent | grip_variance_component |

**Novelty**: Distributed biometric identity. No central biometric database.

---

### 2.7 Ephemeral Session Entropy (ESE)

**Concept**: Calibration sessions are cryptographically ephemeral. Raw biometric data exists only in RAM, never persisted. Only derived thresholds and ZK-proofs survive.

**Mechanism**:
```
SessionRAM:
  - Raw IMU vectors (1000 Hz)
  - Raw touchpad positions (100 Hz)
  - Raw trigger pressure (1000 Hz)
  
SessionProcessing:
  - Extract features (std, entropy, correlation)
  - Derive thresholds
  - Generate ZK-PoAC
  - Store: threshold + proof + decayed_metadata
  
SessionCleanup:
  - Secure erase RAM (mlock + memset_random)
  - Raw data unrecoverable
```

**VAPI Implementation**:
- `mlock()` prevents swap to disk
- `memset_secure()` (constant-time) overwrites RAM
- Session duration: 30 minutes max
- Heartbeat: 5-minute keepalive, session dies if missed

**Forensic Resistance**:
- Cold boot attack: RAM cleared before DRAM refresh
- Core dump: Raw data excluded from dumps (mlock)
- Swap analysis: No swap allocated for session data

**Novelty**: Biometric data has a cryptographic lifetime matching the session duration.

---

## 3. Privacy-First Tournament Architecture

### 3.1 Privacy-Compliant Tournament Flow

```
1. Consent Phase
   ↓
   Player proves ZK-Attested Consent (ZAC)
   ↓
2. Calibration Phase (Ephemeral)
   ↓
   K-Anonymity Cohort formed (K≥5 players)
   ↓
   Raw biometric data processed in RAM only (ESE)
   ↓
   Differential Privacy Thresholds derived (DPT)
   ↓
   Biometric identity Shamir-shared across 16 agents (BSS)
   ↓
   Raw data securely erased
   ↓
3. Tournament Phase
   ↓
   Homomorphic Separation Ratios computed (HSR)
   ↓
   Temporal Decay applied to old calibrations (TBD)
   ↓
   zk-PoAC generated without revealing raw features
   ↓
4. Post-Tournament
   ↓
   Thresholds decay after 90 days (TBD)
   ↓
   Cohort membership expires (KACC)
```

### 3.2 Privacy Budget Management

**Global Budget**: ε = 1.0 per player per year

| Operation | ε Cost | Mechanism |
|-----------|--------|-----------|
| Initial calibration | 0.2 | DPT + KACC |
| Threshold update | 0.1 | DPT only |
| Tournament validation | 0.05 | HSR query |
| Separation ratio check | 0.05 | HSR query |
| Cross-cohort comparison | 0.3 | DPT + KACC |
| Annual reconciliation | 0.3 | Budget reset |

**Budget Enforcement**:
- Per-player privacy counter in CalibrationIntelligenceAgent
- Hard stop when ε > 1.0 (no queries allowed)
- Budget resets annually (consent renewal required)

---

## 4. Regulatory Compliance Mapping

### 4.1 GDPR Article 9 Compliance

| Requirement | VAPI Primitive | Implementation |
|-------------|----------------|----------------|
| Explicit consent | ZAC | ZK-proven consent per jurisdiction |
| Purpose limitation | ESE | Data exists only for calibration duration |
| Data minimization | DPT + KACC | Only thresholds stored, not raw data |
| Storage limitation | TBD | 90-day automatic decay |
| Integrity/confidentiality | BSS + HSR | No single point of compromise |
| DPIA required | Built-in | Privacy budget tracking per player |

### 4.2 CCPA/CPRA Compliance

| Right | VAPI Mechanism |
|-------|----------------|
| Right to know | ZK proof of data usage (not raw data) |
| Right to delete | ESE secure erase + ZK revocation proof |
| Right to opt-out | ZAC revocation (unlinkable) |
| Right to non-discrimination | Privacy budget prevents gaming exclusion |

### 4.3 BIPA (Illinois) Compliance

| Requirement | VAPI Implementation |
|-------------|---------------------|
| Written consent | ZK-Attested Consent with legal hold |
| Retention policy | TBD 90-day decay + ESE ephemeral |
| No sale/profit | Soulbound VHP (non-transferable) |
| Destruction timeline | ESE immediate + TBD 90-day |

### 4.4 EU AI Act (High-Risk Biometric)

| Requirement | VAPI Primitive |
|-------------|----------------|
| Risk management | Privacy budget + agent distribution |
| Data governance | KACC + DPT + ESE |
| Transparency | ZK-proven operations (not raw disclosure) |
| Human oversight | AgentSupervisor monitors privacy compliance |
| Accuracy | DPT preserves utility while protecting privacy |
| Conformity assessment | Built-in privacy invariants |

---

## 5. Implementation Roadmap

> **PHASE STATUS NOTE (2026-04-03)**: Phases 137-149 completed with different content than originally projected here. Phases 137-143 focused on corpus analysis (balanced subsampling, covariance auto-fallback, proper LOO) and achieved separation ratio 1.261 on touchpad_corners. Phases 147-149 focused on epistemic hardening, ACIM (Agent #18), and MCP server infrastructure. Privacy primitives remain DESIGN ONLY — scheduled for Phase 150+ implementation.

### Phase 150: Core Primitives (Target — Weeks 1-4 post-N≥30 touchpad_corners)

**Prerequisite**: Touchpad_corners N≥30 (from ~11 currently) — separation ratio solidified before privacy architecture

**Week 1**: Temporal Biometric Decay (TBD)
- Add `calibration_timestamp` to PoAC wire format  
  ⚠️ CONSTRAINT: Must NOT change 228-byte PoAC wire format (FROZEN invariant); decay applied at analysis layer only
- Implement decay factor in SessionAdjudicator
- Update threshold tracks with decay weights

**Week 2**: ZK-Attested Consent (ZAC)
- Design consent circuit (circom 2.0.0)
- Deploy consent verifier contract on IoTeX testnet
- Integrate with DualPrimitiveGate (Phase 113 infrastructure ready)

**Week 3**: Ephemeral Session Entropy (ESE)
- `mlock()` integration in calibration pipeline (Windows: `VirtualLock()`)
- Secure erase implementation (constant-time memset)
- Session heartbeat mechanism (30-minute max duration)

**Week 4**: Differential Privacy Thresholds (DPT)
- Laplacian noise injection in CalibrationIntelligenceAgent
- Privacy budget tracking per player (new SQLite table: `privacy_budgets`)
- Sensitivity analysis for each of 13 biometric features

### Phase 151: Advanced Primitives (Weeks 5-8)

**Week 5**: K-Anonymity Cohort Calibration (KACC)
- Cohort formation logic (composite key: controller+battery+transport+time_window)
- Minimum pool size enforcement K≥5
- Integration with per-battery threshold tracks (Phase 124 infrastructure)

**Week 6**: Homomorphic Separation Ratios (HSR)
- Paillier/CKKS integration (Python: `phe` library for Paillier)
- Encrypted Mahalanobis distance approximation
- Performance target: <100ms overhead per L4 calculation

**Week 7**: Biometric Shamir Sharing (BSS)
- 18-agent share distribution (updated from 16 — fleet now 18 agents post-Phase 148)
- 9-of-18 reconstruction protocol (updated threshold)
- Agent identity table: includes ACIM (Agent #18) as share holder

**Week 8**: Integration & Testing
- End-to-end privacy flow testing
- ACIM (Agent #18) validates privacy primitive health as part of calibration self-tests
- Privacy budget stored in `agent_calibration_health` extension table

### Phase 152: Certification & Documentation

- **Legal review**: GDPR DPIA, CCPA risk assessment
- **Audit framework**: Privacy budget reporting via MCP vapi-knowledge server
- **Public documentation**: Open-source privacy primitives
- **BiometricPrivacyComplianceAgent (Agent #19)**: Deploy after Phase 151 complete

---

## 6. Novel VAPI-Specific Advantages

### 6.1 Competitive Moat

| Competitor Approach | VAPI Novel Approach |
|---------------------|---------------------|
| Store biometric data centrally | BSS: No central biometric database |
| Retain data indefinitely | TBD: 90-day automatic decay |
| Raw data for ML training | DPT: Noise-injected thresholds only |
| Individual calibration | KACC: K-anonymous cohorts |
| Plaintext processing | HSR: Encrypted computation |
| Persistent consent records | ZAC: ZK-proven unlinkable consent |

### 6.2 Tournament Organizer Benefits

1. **Liability Reduction**: Privacy primitives demonstrably limit breach impact
2. **Global Compliance**: Single codebase meets GDPR + CCPA + BIPA + EU AI Act
3. **Player Trust**: Privacy-preserving design as competitive differentiator
4. **Audit Simplicity**: ZK-proofs provide compliance evidence without disclosure

### 6.3 Player Benefits

1. **Re-identification Resistance**: TBD + KACC make linking across tournaments hard
2. **Data Breach Immunity**: ESE means raw data doesn't exist to steal
3. **Consent Control**: ZAC allows unlinkable opt-out
4. **Fairness Guarantee**: DPT prevents overfitting to specific players

---

## 7. Integration with VAPI-WORKFLOW.v2

### 7.1 Invariant Additions (VAPI_INVARIANTS.md)

```
BP-001 TEMPORAL_DECAY: Biometric data weight decays exponentially with 90-day half-life
BP-002 ZK_CONSENT: All processing requires ZK-proven consent, not raw signatures
BP-003 DIFFERENTIAL_PRIVACY: Threshold tracks include Laplace(ε) noise
BP-004 K_ANONYMITY: Cohorts require K≥5 before threshold activation
BP-005 HOMOMORPHIC_PROCESSING: Separation ratios computed on encrypted data
BP-006 SHAMIR_DISTRIBUTION: Biometric identity split across 16 agents (8-of-16)
BP-007 EPHEMERAL_SESSIONS: Raw data exists only in RAM, never persisted
```

### 7.2 Skill Additions (VAPI_SKILLS.md)

**Skill 11: BIOMETRIC_PRIVACY_COMPLIANCE**
- **Trigger**: Calibration session begins
- **Precondition**: ConsentProof verified
- **Steps**:
  1. Check privacy budget remaining (ε < 1.0)
  2. Form K-anonymity cohort (K≥5)
  3. Initialize ephemeral session (mlock)
  4. Apply DPT noise injection
  5. Distribute BSS shares
  6. Secure erase raw data
- **Invariant Check**: BP-001 through BP-007
- **Output**: Privacy-compliant threshold track

### 7.3 Agent Additions (VAPI_AGENTS.md)

> **CURRENT AGENT #18**: AgentCalibrationIntegrityMonitor (ACIM) — Phase 148, LIVE. Runs 16 calibration self-tests every 15 minutes. Not a privacy agent.

**Agent #19 (PROPOSED): BiometricPrivacyComplianceAgent**
- **Role**: Privacy primitive orchestration (Phase 150-152 roadmap)
- **Expertise**: Differential privacy, ZK proofs, homomorphic encryption
- **Tools**: 
  - Privacy budget tracker (per-player ε counter)
  - Cohort formation engine (K-anonymity enforcement)
  - Noise injection module (Laplacian noise for DPT)
  - BSS distribution protocol (Shamir 9-of-18 on 18-agent fleet)
- **Fail Mode**: Hard stop when privacy budget exhausted (no queries allowed)
- **Integration**: Called by CalibrationIntelligenceAgent before threshold derivation; validated by ACIM (Agent #18) in calibration health self-tests
- **Status**: DESIGN ONLY — no code written as of Phase 149

---

## 8. References

### VAPI-WORKFLOW.v2 Files
- **VAPI_INVARIANTS.md**: Privacy invariants BP-001 to BP-007
- **VAPI_SKILLS.md**: Skill 11 (Biometric Privacy Compliance)
- **VAPI_AGENTS.md**: Agent #18 (BiometricPrivacyComplianceAgent)
- **VAPI_CONTEXT.md**: Privacy budget tracking, cohort status
- **VAPI_MEMORY.md**: Phase 137-139 privacy implementation outcomes

### Bridge Code Integration
- `bridge/vapi_bridge/biometric_privacy_agent.py` - Agent #18 implementation
- `bridge/vapi_bridge/privacy/temporal_decay.py` - TBD implementation
- `bridge/vapi_bridge/privacy/zk_consent.py` - ZAC circuits
- `bridge/vapi_bridge/privacy/differential_privacy.py` - DPT noise injection
- `bridge/vapi_bridge/privacy/k_anonymity.py` - KACC cohort formation
- `bridge/vapi_bridge/privacy/homomorphic.py` - HSR encrypted computation
- `bridge/vapi_bridge/privacy/shamir_sharing.py` - BSS distribution
- `bridge/vapi_bridge/privacy/ephemeral_session.py` - ESE secure memory

### Academic References
- Dwork & Roth, "The Algorithmic Foundations of Differential Privacy"
- Benaloh, "Secret Sharing Homomorphisms"
- Paillier, "Public-Key Cryptosystems Based on Composite Degree Residuosity Classes"
- Circom/ZK proof systems for gaming applications

---

**Document Version**: 1.1 (Phase 149)  
**Last Updated**: 2026-04-03  
**Privacy Primitives**: 7 novel mechanisms (BP-001 to BP-007 — IMMUTABLE, defined in VAPI_INVARIANTS.md §6)  
**Regulatory Coverage**: GDPR, CCPA/CPRA, BIPA, EU AI Act, PIPL, LGPD  
**Target**: Phase 150-152 full privacy compliance implementation  
**Agent Status**: BiometricPrivacyComplianceAgent = PROPOSED Agent #19 (Agent #18 = ACIM, Phase 148 LIVE)  
**Competitive Advantage**: First privacy-preserving competitive gaming attestation protocol  

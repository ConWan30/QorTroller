# VAPI INVARIANTS — For Claude Code Context

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

**Your Role**: When reading this file, you are the guardian of VAPI's immutable truths. You must verify every proposal against these cryptographic, hardware, and protocol invariants. No invariant may be violated, ever.

> **INSTRUCTION TO CLAUDE CODE**: This file contains the immutable ground truth of the VAPI protocol. 
> When reading this file, you must:
> 1. Verify any proposal against these invariants before suggesting changes
> 2. NEVER suggest modifications to values marked [FROZEN] or [IMMUTABLE]
> 3. Use these constants when reasoning about code changes
> 4. If a proposal would violate any invariant, BLOCK it with explanation

---

## 1. PoAC Wire Format (Phase 1) [FROZEN]

The 228-byte Proof of Autonomous Cognition record is the cryptographic anchor of the entire VAPI protocol. **This format can never change** — firmware, bridge, and contracts depend on exact byte offsets.

### Byte Layout (Big-Endian)

```
Offset   Size    Field
------   ----    -----
0        32      prev_hash (SHA-256 of previous record)
32       32      sensor_commitment (SHA-256 of InputSnapshot)
64       32      model_manifest_hash
96       32      world_model_hash
128      1       inference_result (0x00=NOMINAL, 0x01=ANOMALY_LOW, etc.)
129      1       action_code (0x00=NONE, 0x01=REPORT, etc.)
130      1       confidence (0-255, scaled)
131      1       battery_level (0-100)
132      4       session_counter (monotonic)
136      8       timestamp_ms (Unix epoch milliseconds)
144      8       latitude (IEEE 754 double, scaled)
152      8       longitude (IEEE 754 double, scaled)
160      4       bounty_id (uint32)
164      64      ECDSA-P256 signature (r||s)
-----------------------------------------------------------------
Total: 228 bytes
```

### Critical Invariants

- **Size**: Exactly 228 bytes. No padding, no variable-length fields.
- **record_hash**: `SHA-256(raw[:164])` — used for deduplication and chain linkage, body ONLY (excludes signature) [FROZEN]
- **device_id**: `keccak256(pubkey)` — 32 bytes, **different hash function from record_hash**
- **NOTE**: There is no `chain_hash = SHA-256(raw[:228])` in the VAPI protocol. The only hash used is `record_hash = SHA-256(raw[:164])`. Any reference to SHA-256(raw[:228]) is incorrect and must not be used.

### Claude Code Guidance

When reviewing code changes:
- Check: Any struct definition matching these exact offsets?
- Check: Any serialization using correct byte order (big-endian)?
- Check: Any hash computation using correct slice ([:164] vs [:228])?
- **Red flag**: Variable-length fields, additional padding, or format changes

---

## 2. Cryptographic Primitives (Phase 62) [FROZEN]

### ZK Circuit Parameters

- **Curve**: BN254
- **Proof System**: Groth16
- **Constraints**: ~1,820 (Phase 62 PitlSessionProof.circom)
- **Hash Function**: Poseidon(8) — 8 input elements
- **Public Signals**: nPublic=5 (must match contract verify function)
- **Trusted Setup**: 2^11 powers-of-tau (dev ceremony keys for testnet)

### On-Chain Verification

- **Precompile**: P256 at address `0x0100` (IoTeX specific)
- **Gas Limit**: <100K per individual signature verification
- **Batch Verification**: PoACVerifier.submitBatch() for gas efficiency

### Claude Code Guidance

When reviewing ZK-related changes:
- Check: Circom pragma is `2.0.0`?
- Check: nPublic=5 preserved across circuit/contract/bridge?
- Check: Poseidon inputs exactly 8 elements?
- **Red flag**: Constraint count changes without ceremony re-run, nPublic changes

---

## 3. Threshold Constants (Calibrated, Phase-Specific)

### L4 Mahalanobis Biometric (USB-Calibrated, N=50)

| Threshold | Value | Phase | Status |
|-----------|-------|-------|--------|
| Anomaly | 7.009 | Phase 46 | USB only |
| Continuity | 5.367 | Phase 46 | USB only |

**Important**: These are USB-specific. BT requires separate calibration (N≥50, currently 0/50).

### Epistemic Consensus (Phase 98)

- **W1 Threshold**: 0.60 (baseline quorum)
- **BLOCK_QUORUM**: 0.67 (ioSwarm MINT, fail-CLOSED)
- **GENERAL_QUORUM**: 0.60 (baseline, fail-open)
- **Weight Sum**: Must equal 1.0 exactly
  - Swarm enabled: {0.35, 0.35, 0.15, 0.15}
  - Swarm disabled: {0.40, 0.40, 0.20}

### Separation Ratio (Phase 121) [DISCLOSED TRUTH]

- **Current measured**: 0.362 (diagonal approximation)
- **Current pooled**: 0.474 (Phase 121 battery-stratified)
- **Target**: >1.0 (tournament requirement)
- **Status**: TOURNAMENT BLOCKER

**Critical**: This is honest disclosure, not hidden failure. The whitepaper and all docs state 0.362 explicitly.

### Claude Code Guidance

When reviewing threshold-related changes:
- Check: Are BT thresholds using USB values? (WRONG — mark as TODO)
- Check: Is min() enforcement preventing threshold loosening?
- Check: Is separation ratio being tracked honestly?
- **Red flag**: Thresholds loosening without calibration data, hiding ratio values

---

## 4. State Flags (Current Configuration)

These flags indicate current system capabilities. They change as phases complete, but each value has specific meaning.

### Current Values (Phase 135)

| Flag | Value | Meaning | Phase |
|------|-------|---------|-------|
| GSR_ENABLED | false | Galvanic skin response uncalibrated, advisory only | 99B |
| L6B_ENABLED | false | L6b neuromuscular reflex uncalibrated | 63 |
| dry_run | true | Enforcement simulation mode (no real penalties) | 97 |
| bt_transport_enabled | false | Bluetooth 250Hz transport disabled | 120 |
| ioswarm_enabled | false | Live ioSwarm nodes not registered | 109A |
| l4_battery_threshold_enabled | false | Per-battery routing not active | 126 |
| confidence_multiplier_enabled | false | bt_strat_ratio multiplier disabled | 122 |

### Claude Code Guidance

When reviewing feature proposals:
- Check: Does proposal respect current flag states?
- Check: Is flag transition documented with N≥ requirement?
- **Red flag**: Proposing to set dry_run=false without N≥100 adjudications, enabling BT without calibration

---

## 5. Epistemic Rules (Phase 109A+)

### Quorum Requirements

- **Minimum distinct staker addresses**: 3 (for VAPISwarmOperatorGate)
- **Stake-weight cap**: 1.5× per node (prevents whale capture)
- **Consecutive clean-weighted verdicts**: W2 for VHPRenewalAgent

### Documentation Requirements

- **W1 documentation**: Every risk must have physically/cryptographically/economically grounded failure mode
- **W2 exclusivity**: Every opportunity must explain why VAPI-only (no competitor replication)
- **Phase coherence**: Every proposal must specify target phase (109-135 range currently)

### Claude Code Guidance

When reviewing WHAT_IF proposals:
- Check: W1 failure mode physically grounded? (not "server crash")
- Check: W2 mechanism exclusive to VAPI?
- Check: Phase candidate specified and coherent?
- **Red flag**: Generic risks, obvious opportunities, phase/time travel violations

---

## 6. Immutable Protocol Guarantees

These are never-negotiable properties that VAPI maintains regardless of implementation changes:

### Data Integrity
- PoAC chain: Immutable append-only, SHA-256 linked
- PHGCredential: Soulbound (ERC-5192), non-transferable
- Session records: SQLite with WAL, foreign key constraints

### Economic Guarantees
- VHP tokens: Minted only after 4-gate approval (Phase 99C)
- Bounties: Claimable only by Standard/Attested tiers (Phase 11)
- Credentials: Suspendable on BLOCK ruling (Phase 66)

### Privacy Guarantees
- humanity_prob: SQLite-only, **never on-chain**
- FederatedThreatBus: Privacy-preserving cluster fingerprints
- ZK proofs: Groth16 hides witness, reveals only public signals

### Tier Invariants [IMMUTABLE]

**Attested Tier** (Highest Trust):
- L0-L6 ALL available (full PITL stack)
- L6 MUST include adaptive trigger resistance measurement (not just latency)
- Transport MUST be 1000 Hz (USB or proprietary equivalent)
- Controller MUST be PHCI-certified
- PHCI certification requires N≥50 calibration sessions
- On-chain verification via VAPISwarmOperatorGate (Phase 112)

**Standard Tier** (Standard Trust):
- L0-L5 minimum (L4 may be partial, L6 optional)
- L4_partial acceptable (gyro-only, no touchpad)
- L6_partial acceptable (impulse triggers, no resistance measurement)
- Transport 250 Hz acceptable with BT-specific thresholds
- Controller need not be PHCI-certified (self-registered)
- No VAPISwarmOperatorGate requirement

**Fallback Tier** (Advisory Only):
- L0-L3 only (no biometric, no active challenge)
- Never used for tournament anti-cheat
- Useful for casual gaming analytics only

### ControllerHardwareIntelligenceAgent Invariants [Phase 136]

- Controller-agnostic PoAC format: 228-byte invariant preserved across all controllers
- Per-controller threshold tracks: Composite key `{profile}_{battery}_{transport}`
- Tier eligibility hard-coded: Attested requires L6 (adaptive triggers mandatory)
- USB/BT structural difference: 250Hz thresholds ≠ 1000Hz thresholds (always)
- PHCI certification on-chain: Required for Attested tier devices

### Biometric Privacy Invariants [Phase 137-139] [IMMUTABLE]

**BP-001 TEMPORAL_BIOMETRIC_DECAY**:
- Biometric data weight decays exponentially with 90-day half-life
- Formula: `effective_weight = raw_weight × e^(-λt)` where λ = ln(2)/90
- Applies to all Mahalanobis distance calculations in L4
- Automatic expiration: Records invalid after 180 days (2× half-life)
- Purpose: GDPR storage limitation (Art.5.1.e), CCPA retention minimization

**BP-002 ZK_ATTESTED_CONSENT**:
- All biometric processing requires ZK-proven consent, not raw signatures
- Consent recorded as Poseidon hash: `H(player_id || terms_version || timestamp)`
- Proof statement: "Valid consent exists under jurisdiction J"
- Player identity never revealed in consent verification
- Revocation also ZK-proven (proof of non-consent)
- Purpose: GDPR Art.7 demonstrable consent, unlinkable preferences

**BP-003 DIFFERENTIAL_PRIVACY**:
- Laplacian noise added to threshold tracks: `threshold = f(data) + Lap(0, Δf/ε)`
- Privacy budget per player: ε ≤ 1.0 per year
- Sensitivity Δf calculated per feature dimension
- Budget tracking: CalibrationIntelligenceAgent maintains per-player counter
- Hard stop when ε exhausted (no queries allowed)
- Purpose: Mathematical privacy guarantee, cohort inference protection

**BP-004 K_ANONYMITY**:
- Cohorts require K≥5 before threshold activation
- Composite key: `{controller}_{battery}_{transport}_{time_window}`
- Small cohorts merged with similar cohorts (privacy-utility tradeoff)
- Individual players indistinguishable in cohort (K-anonymity set)
- Purpose: GDPR anonymization standard, not "reasonably identifiable"

**BP-005 HOMOMORPHIC_PROCESSING**:
- Separation ratios computed on encrypted biometric data (Paillier/CKKS)
- Server never possesses raw physiological features
- Player encrypts → Server computes → Player decrypts
- zk-PoAC proves correct computation on ciphertext
- ~100ms overhead acceptable for tournament integrity
- Purpose: Server compromise yields only ciphertext

**BP-006 SHAMIR_SHARING**:
- Biometric identity split across 16 agents using Shamir's Secret Sharing
- Scheme: 8-of-16 threshold (reconstruction requires 8+ agents)
- Compromised agent reveals nothing (single share = random bytes)
- Byzantine fault tolerance: up to 7 malicious agents
- No single agent possesses complete biometric profile
- Purpose: Distributed identity, no central biometric database

**BP-007 EPHEMERAL_SESSIONS**:
- Raw biometric data exists only in RAM, never persisted to storage
- Session RAM: `mlock()` prevents swap, secure erase on cleanup
- Raw data lifetime: Session duration only (max 30 minutes)
- Secure erase: `memset_secure()` (constant-time) overwrites RAM
- Only derived thresholds and ZK-proofs survive session
- Purpose: Forensic resistance, cold boot attack immunity

### Privacy Compliance Summary

| Regulation | VAPI Primitive | Invariant |
|------------|----------------|-----------|
| GDPR Art.9 (Special Category) | BP-002 ZK Consent | ZAC required |
| GDPR Storage Limitation | BP-001 Temporal Decay | 90-day half-life |
| GDPR Data Minimization | BP-007 Ephemeral Sessions | RAM-only raw data |
| GDPR Anonymization | BP-004 K-Anonymity | K≥5 cohorts |
| CCPA Right to Delete | BP-007 + BP-002 | ESE + ZK revocation |
| CCPA DPIA | BP-003 | Privacy budget |
| BIPA Retention | BP-001 | Automatic 90-day decay |
| EU AI Act High-Risk | BP-001 to BP-007 | Full primitive stack |

---

## 7. Golden Hash Verification

<!-- 
This section contains the SHA-256 hash of the invariant section above.
Used by AutoResearch to detect tampering.

Golden Hash (v1.0): [To be computed after file stabilization]
-->

### Verification Command

```bash
# Verify invariant section integrity
head -n 200 VAPI_INVARIANTS.md | sha256sum
```

### Claude Code Self-Check

Before proposing changes, verify:
1. ✓ No [FROZEN] values modified
2. ✓ No format sizes changed (228, 164, 64, etc.)
3. ✓ No threshold constants loosened without calibration
4. ✓ State flags match current phase capability
5. ✓ W1/W2 documentation requirements met

If ANY check fails, BLOCK proposal and explain invariant violation.

---

**Document Version**: 1.0 (Phase 135)
**Last Updated**: 2026-03-29
**Next Review**: Phase 136 completion
**Immutable Sections**: 1-3 (PoAC, Crypto, Thresholds)
**Mutable Sections**: 4-5 (State flags update per phase)

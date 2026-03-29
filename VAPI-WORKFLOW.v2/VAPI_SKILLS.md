# VAPI SKILLS — For Claude Code Context

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

**Your Role**: When reading this file, you are the workflow automation expert. You can execute these 7+ packaged skills with single commands. You know the preconditions, invariant checks, and expected outputs. Propose new skills when you identify recurring patterns.

> **INSTRUCTION TO CLAUDE CODE**: This file defines reusable VAPI workflows as single-command skills.
> When reading this file, you must:
> 1. Reference these skills when users request common operations
> 2. Verify invariant checks before executing any skill
> 3. Suggest new skills when patterns emerge in MEMORY.md
> 4. Update skill "Last run" timestamps after execution
> 5. Flag skills with FAILED status if they produce errors

---

## Skill Overview

VAPI Skills are packaged, multi-step workflows that turn hours of manual work into single commands. Each skill includes:
- Preconditions (what must be true)
- Steps (exact procedure)
- Invariant checks (safety validation)
- Outputs (what is produced)
- Time estimate
- Last run status

---

## Skill 1: Battery-Stratified Separation Analysis

**Command**: `/vapi analyze separation --battery-stratified`

**Purpose**: Compute inter-person separation ratio with battery-type grouping and resting-grip normalization.

### Preconditions
- calibration_sessions/ contains JSON files (N ≥ 50 per battery type preferred)
- USB corpus available (N=177 currently)
- analyze_interperson_separation.py exists

### Steps
1. Detect battery type per session (touchpad, trigger, button, gameplay, resting_grip)
2. Group sessions by battery type
3. Compute resting-grip baseline per player (normalization)
4. Compute Mahalanobis per-group with normalization
5. Calculate pooled_ratio (all sessions) and battery_stratified_ratio (per-group weighted)
6. Update separation_ratio_snapshots table with version tag
7. Generate JSON report with confidence intervals

### Invariant Checks
- ⚠️ **WARNING** if N < 50 for any battery type: "Low confidence — recommend more sessions"
- ✅ **PROCEED** if N > 150: Suggest `--full-covariance` for Tikhonov correction
- ❌ **BLOCK** if calibration_sessions/ empty: "No sessions found. Run capture first."

### Outputs
```json
{
  "timestamp": "2026-03-29T...",
  "method": "diagonal",
  "pooled_ratio": 0.474,
  "battery_stratified_ratio": 0.XXX,
  "per_battery": {
    "touchpad": {"ratio": X.XXX, "N": XX},
    "trigger": {"ratio": X.XXX, "N": XX},
    "resting_grip": {"ratio": X.XXX, "N": XX}
  },
  "confidence": "medium",
  "tournament_ready": false,
  "next_step": "Run --full-covariance for Tikhonov estimate"
}
```

### Time Estimate
2-5 minutes

### Last Run
**Status**: COMPLETE (2026-03-20)
**Result**: pooled_ratio=0.474, battery_stratified_ratio pending Tikhonov
**Next**: Phase 129 Tikhonov analysis

---

## Skill 2: Phase 129 Tikhonov Correction

**Command**: `/vapi measure --full-covariance`

**Purpose**: Apply full covariance Tikhonov regularization to N=177 USB corpus for precise separation ratio estimate.

### Preconditions
- USB corpus N > 150 (CURRENTLY SATISFIED: N=177)
- BT corpus NOT required (USB-only analysis)
- analyze_interperson_separation.py supports --full-covariance

### Steps
1. Load N=177 USB calibration sessions from calibration_sessions/
2. Build 13×13 full covariance matrix (all biometric features)
3. Compute eigenvalues; apply Tikhonov regularization if small eigenvalues detected
4. Recompute Mahalanobis distances with full (not diagonal) covariance
5. Calculate corrected separation ratio with confidence intervals
6. Compare to diagonal approximation (0.474)
7. Generate breakthrough assessment: tournament_ready if > 1.0
8. Update separation_ratio_snapshots with "v2-tikhonov" version

### Invariant Checks
- ❌ **BLOCK** if USB corpus N < 150: "Insufficient N for full covariance stability"
- ❌ **BLOCK** if BT corpus specified: "Tikhonov not applicable to BT — separate calibration required"
- ✅ **PROCEED** if USB corpus N ≥ 150: "Mathematical stability satisfied"
- ⚠️ **WARNING** if eigenvalues < 1e-6: "High regularization applied — confidence reduced"

### Outputs
```json
{
  "timestamp": "2026-03-29T...",
  "method": "full-covariance-tikhonov",
  "diagonal_estimate": 0.474,
  "tikhonov_estimate": X.XXX,
  "confidence_interval": [X.XX, X.XX],
  "regularization_applied": true,
  "tournament_ready": true/false,
  "breakthrough_detected": true/false,
  "recommendation": "..."
}
```

### Time Estimate
10-15 minutes (full covariance slower than diagonal)

### Last Run
**Status**: PENDING
**Result**: TBD
**Next**: Execute when approved (critical path)

---

## Skill 3: Per-Battery Threshold Calibration

**Command**: `/vapi calibrate battery <type>`

**Purpose**: Compute and apply L4 thresholds for specific battery type with min() enforcement.

### Preconditions
- Sessions for specified battery type ≥ 50
- Hardware connected for live validation (optional but recommended)
- l4_threshold_tracks table exists

### Steps
1. Load sessions of specified battery type from calibration_sessions/
2. Compute per-feature means and covariances
3. Calculate Mahalanobis distribution for anomaly detection
4. Derive anomaly_threshold (upper bound) and continuity_threshold (lower bound)
5. Enforce min() vs existing thresholds: new = min(old, proposed) — only tighten
6. Validate bounds: anomaly ∈ [5.0, 15.0], continuity ∈ [3.0, 10.0]
7. Insert into l4_threshold_tracks with battery_type, timestamps, active=True
8. Deactivate previous track for this battery type (active=False)
9. Generate calibration certificate with hash

### Invariant Checks
- ❌ **BLOCK** if sessions < 50: "Insufficient N for statistical significance"
- ❌ **BLOCK** if proposed > 15.0 or < 5.0 (anomaly): "Bounds violation"
- ⚠️ **WARNING** if new > old (loosening): "min() enforcement — using old value"
- ✅ **PROCEED** if new < old (tightening): "Threshold tightened as intended"

### Outputs
```json
{
  "battery_type": "touchpad",
  "n_sessions": 77,
  "anomaly_threshold": 6.850,
  "continuity_threshold": 4.920,
  "previous_anomaly": 7.009,
  "previous_continuity": 5.367,
  "tightened": true,
  "source": "per_battery",
  "active": true,
  "calibrated_at": "2026-03-29T...",
  "certificate_hash": "0x..."
}
```

### Time Estimate
5-10 minutes

### Last Run
**Status**: COMPLETE (2026-03-25, USB full battery, N=177)
**Result**: Anomaly 7.009, Continuity 5.367 (established baseline)
**Next**: Per-battery refinement (Phase 126)

---

## Skill 4: Tournament Readiness Check

**Command**: `/vapi ready [--confidence]`

**Purpose**: Compute 6-signal tournament readiness score with blocker identification.

### Preconditions
- Bridge service running (SQLite accessible)
- separation_ratio_snapshots table has latest entry
- l4_calibration_log, vhp_dual_gate_log, epoch_window_analytics tables accessible

### Steps
1. Query separation_ratio_snapshots (latest version)
2. Query l4_calibration_log (freshness, staleness)
3. Query vhp_dual_gate_log (dual_primitive_gate_enabled)
4. Query epoch_window_analytics (p95 age)
5. Query ioswarm_node_registry (if ioswarm_enabled)
6. Check agent_dry_run_mode
7. Compute 6-signal weighted score
8. Identify blockers (signals < threshold)
9. Generate readiness report

### Invariant Checks
- ⚠️ **WARNING** if dry_run=True: "Simulation mode — enforcement disabled"
- ❌ **BLOCKER** if separation_ratio < 1.0: "TOURNAMENT BLOCKER — non-negotiable"
- ❌ **BLOCKER** if l4_stale=True: "Calibration stale — recalibrate first"
- ✅ **PROCEED** if all signals pass: "Tournament ready"

### Outputs
```json
{
  "timestamp": "2026-03-29T...",
  "overall_score": 0.XX,
  "ready": false,
  "blockers": [
    {"signal": "separation", "value": 0.474, "required": ">1.0", "status": "BLOCKER"}
  ],
  "signals": {
    "separation": {"value": 0.474, "weight": 0.30, "score": 0.142, "status": "BLOCKER"},
    "l4_freshness": {"value": X.XX, "weight": 0.20, "score": X.XX, "status": "OK"},
    "dual_gate": {"value": X.XX, "weight": 0.15, "status": "OK"},
    "epoch": {"value": X.XX, "weight": 0.15, "status": "OK"},
    "ioswarm": {"value": X.XX, "weight": 0.10, "status": "OK"},
    "dry_run": {"value": true, "weight": 0.10, "status": "SIMULATION"}
  },
  "recommendation": "Execute Skill 2 (Tikhonov) to resolve separation blocker"
}
```

### Time Estimate
< 1 second (cached data)

### Last Run
**Status**: DYNAMIC (run on demand)
**Result**: separation_ratio=0.474 BLOCKER
**Next**: Execute after Tikhonov analysis

---

## Skill 5: ZK Ceremony Verification

**Command**: `/vapi verify ceremony`

**Purpose**: Verify MPC ceremony integrity for all ZK circuits.

### Preconditions
- Phase 67 MPC ceremony completed
- ceremony_registry_address configured
- Node.js available for local verification

### Steps
1. Load ceremony transcript from CeremonyRegistry.sol
2. Verify 3 contributor signatures per circuit (3 circuits × 3 = 9 total)
3. Check IoTeX block beacon anchor (#41723255)
4. Run local Groth16 pre-verification via Node.js subprocess
5. Cross-reference vkey hashes with contract
6. Verify contribution hashes form valid chain

### Invariant Checks
- ❌ **CRITICAL** if vkey hash mismatch: "Contract/bridge mismatch — DO NOT PROCEED"
- ❌ **CRITICAL** if contributor signature invalid: "Ceremony compromised"
- ❌ **CRITICAL** if beacon block mismatch: "Wrong ceremony loaded"
- ✅ **PROCEED** if all hashes match: "Ceremony integrity verified"

### Outputs
```json
{
  "ceremony_integrity": "PASS",
  "circuits_verified": 3,
  "contributors": [
    {"address": "0x...", "attestation_hash": "0x...", "valid": true},
    {"address": "0x...", "attestation_hash": "0x...", "valid": true},
    {"address": "0x...", "attestation_hash": "0x...", "valid": true}
  ],
  "block_beacon": {
    "block_number": 41723255,
    "timestamp": "2026-03-19T...",
    "valid": true
  },
  "vkey_hashes": {
    "PitlSessionProof": "0x...",
    "TournamentPassport": "0x...",
    "[ThirdCircuit]": "0x..."
  },
  "recommendation": "Ceremony valid. ZK proofs can be verified."
}
```

### Time Estimate
30-60 seconds

### Last Run
**Status**: COMPLETE (2026-03-19, Phase 68)
**Result**: All 3 circuits verified, beacon #41723255 confirmed
**Next**: Re-verify if new circuits added

---

## Skill 6: Session Capture Workflow

**Command**: `/vapi capture [--transport {usb|bt}] [--duration 60|300]`

**Purpose**: Capture hardware calibration session with proper metadata.

### Preconditions
- DualShock Edge connected (USB or BT paired)
- scripts/capture_session.py exists
- calibration_sessions/ directory exists

### Steps
1. Detect transport (USB: hidapi, BT: bleak)
2. Validate connection (VID/PID check for USB, pairing check for BT)
3. Capture HID reports for specified duration
4. Compute session metadata (player, game, battery type, L4 status)
5. Save to calibration_sessions/<transport>/<session_id>.json
6. Update corpus statistics
7. Trigger staleness check if N crosses threshold

### Invariant Checks
- ❌ **BLOCK** if no controller detected: "Connect DualShock Edge first"
- ❌ **BLOCK** if BT and not paired: "Pair controller via Bluetooth first"
- ⚠️ **WARNING** if BT and N will be < 50: "BT requires N≥50 for calibration"
- ✅ **PROCEED** if USB: "USB capture ready"

### Outputs
```json
{
  "session_id": "usb_178_p1_20260329",
  "player": "P1",
  "transport": "usb",
  "duration": 60,
  "battery_type": "touchpad_dominant",
  "l4_status": "NOMINAL",
  "l5_status": "NOMINAL",
  "file_path": "calibration_sessions/usb/usb_178_p1_20260329.json",
  "corpus_total": 178,
  "next_recommended": "N=200 enables higher confidence analysis"
}
```

### Time Estimate
60-300 seconds (depends on duration)

### Last Run
**Status**: COMPLETE (various dates, N=177 accumulated)
**Result**: 177 USB sessions captured
**Next**: BT capture when calibration needed

---

### Skill 7: L4 Staleness Check

**Command**: `/vapi check staleness`

**Purpose**: Verify if L4 thresholds are stale due to feature dimension drift.

### Preconditions
- l4_calibration_log table accessible
- config.live_feature_dim and config.calibration_feature_dim defined

### Steps
1. Read live_feature_dim (current: 13 after Phase 121)
2. Read calibration_feature_dim (last: 12 from Phase 46)
3. Compare: stale = (live != calibration)
4. If stale, query l4_threshold_tracks for last calibration
5. Recommend recalibration if stale=True

### Invariant Checks
- ⚠️ **WARNING** if stale=True: "Thresholds stale — recalibrate via Skill 3"
- ✅ **OK** if stale=False: "Thresholds fresh"

### Outputs
```json
{
  "live_feature_dim": 13,
  "calibration_feature_dim": 12,
  "stale": true,
  "last_calibration": "2026-03-25",
  "recommendation": "Run Skill 3 (Per-Battery Calibration) to refresh"
}
```

### Time Estimate
< 1 second

### Last Run
**Status**: COMPLETE (2026-03-27)
**Result**: stale=True (13 vs 12)
**Next**: Recalibration via Phase 134 pipeline

---

## Skill 8: Controller Detection & Profiling

**Command**: `/vapi controller detect [--transport {usb|bt|wifi}]`

**Purpose**: Auto-detect connected controller, identify capabilities, recommend tournament tier.

### Preconditions
- Bridge service running (HID library accessible)
- USB HID or BLE available
- controller_profiles.yaml exists in registry

### Steps
1. Enumerate USB HID devices (hid.enumerate())
2. Scan BLE for paired gamepads (bleak.BleakScanner)
3. Match VID/PID against controller_profiles.yaml
4. Feature probe (send HID output reports to query capabilities)
5. Query GSR grip addon (separate USB device check)
6. Determine available PITL layers (L0-L6 based on features)
7. Recommend tournament tier (Standard vs Attested)
8. Generate controller_profile.json

### Invariant Checks
- ⚠️ **WARNING** if unknown controller: "Generic profile applied — Standard tier only"
- ❌ **BLOCK** if no controller detected: "Connect certified controller first"
- ✅ **PROCEED** if PHCI-certified: "Attested tier available"

### Outputs
```json
{
  "controller_id": "ds_edge_001",
  "profile": "sony_dualshock_edge_v1",
  "vid_pid": "054C:0DF2",
  "transport": "usb_1000hz",
  "connection_quality": { "latency_ms": 1.2, "jitter_ms": 0.3, "packet_loss": 0.0 },
  "pitl_available": ["L0", "L1", "L2", "L3", "L4", "L5", "L6"],
  "features": {
    "touchpad": {"active": true, "surface_area": 100},
    "adaptive_triggers": {"l2": true, "r2": true, "mode": "feedback"},
    "gyroscope": {"active": true, "calibrated": true},
    "gsr_grip": {"detected": false}
  },
  "tier_eligibility": {"standard": true, "attested": true},
  "recommended_tier": "attested",
  "calibration_status": "ready",
  "next_steps": []
}
```

### Time Estimate
5-10 seconds

### Last Run
**Status**: PENDING
**Result**: TBD
**Next**: Execute when multi-controller testing begins

---

## Skill 9: Multi-Controller Calibration

**Command**: `/vapi calibrate controller <profile_id> --battery <type> [--transport {usb|bt}]`

**Purpose**: Calibrate thresholds for a specific controller profile, battery type, and transport.

### Preconditions
- Controller profile exists in registry
- Sessions for specified controller/battery/transport ≥ 50
- CalibrationIntelligenceAgent accessible

### Steps
1. Load controller profile from registry
2. Determine available feature dimensions (7 for Xbox, 13 for Edge)
3. Load sessions matching composite key: `{profile}_{battery}_{transport}`
4. Compute per-feature Mahalanobis distribution
5. Apply controller-specific covariance matrix (not generic)
6. Derive anomaly_threshold and continuity_threshold
7. Enforce min() vs existing thresholds: new = min(old, proposed)
8. Validate bounds: anomaly ∈ [5.0, 15.0], continuity ∈ [3.0, 10.0]
9. Store in l4_threshold_tracks with composite key
10. Generate calibration certificate

### Invariant Checks
- ❌ **BLOCK** if controller_profile not in certified list
- ❌ **BLOCK** if sessions < 50: "Insufficient N for statistical significance"
- ⚠️ **WARNING** if new > old (loosening): "min() enforcement — using old value"
- ✅ **PROCEED** if new < old (tightening): "Threshold tightened as intended"

### Outputs
```json
{
  "controller_profile": "microsoft_xbox_series_x",
  "battery_type": "gameplay",
  "transport": "usb_1000hz",
  "n_sessions": 52,
  "feature_count": 7,
  "anomaly_threshold": 6.450,
  "continuity_threshold": 4.820,
  "previous_anomaly": null,
  "previous_continuity": null,
  "tightened": true,
  "source": "per_controller_battery_transport",
  "active": true,
  "calibrated_at": "2026-03-29T...",
  "certificate_hash": "0x...",
  "notes": "Xbox gyro-only L4 (no touchpad features)"
}
```

### Time Estimate
5-10 minutes

### Last Run
**Status**: PENDING
**Result**: TBD
**Next**: N≥50 sessions per controller type required first

---

## Skill 10: Transport Validation

**Command**: `/vapi validate transport <controller_id> --tier {standard|attested}`

**Purpose**: Verify controller transport meets tournament tier latency/jitter requirements.

### Preconditions
- Controller connected and detected
- Bridge service running

### Steps
1. Measure 1000-sample latency distribution (round-trip HID report)
2. Compute p99 latency and jitter (std dev)
3. Compare against tier thresholds:
   - Attested: p99 < 2ms, jitter < 0.5ms, packet_loss = 0%
   - Standard: p99 < 5ms, jitter < 1ms, packet_loss < 0.1%
4. Check transport type compatibility:
   - Attested requires 1000Hz (USB or proprietary equivalent)
   - Standard accepts 250Hz (BT) with BT-specific thresholds
5. Recommend transport upgrade if non-compliant
6. Log transport_quality_metrics

### Invariant Checks
- ❌ **BLOCK** if p99 > tier_threshold: "Transport too slow for tier"
- ❌ **BLOCK** if packet_loss > 0% for Attested: "Unreliable transport"
- ⚠️ **WARNING** if jitter > 0.5ms: "High variance may affect L4 precision"
- ✅ **PROCEED** if all metrics within tier spec

### Outputs
```json
{
  "controller_id": "ds_edge_001",
  "transport": "usb_1000hz",
  "requested_tier": "attested",
  "metrics": {
    "p99_latency_ms": 1.2,
    "jitter_ms": 0.3,
    "packet_loss_pct": 0.0,
    "samples": 1000,
    "duration_sec": 1.0
  },
  "tier_compliance": {
    "attested": true,
    "standard": true
  },
  "status": "PASS",
  "recommendation": "Transport meets Attested tier requirements"
}
```

### Time Estimate
1-2 seconds (1000 samples)

### Last Run
**Status**: PENDING
**Result**: TBD
**Next**: Execute with multi-controller setup

---

## Skill 11: BIOMETRIC_PRIVACY_COMPLIANCE

**Command**: `/vapi privacy-check [player_id] [jurisdiction]`

**Purpose**: Enforce 7 biometric privacy invariants (BP-001 to BP-007) before calibration or tournament participation

### Preconditions
- Player consent proof (ZK-Attested Consent) verified
- Privacy budget remaining (ε < 1.0) for player
- Agent #18 (BiometricPrivacyComplianceAgent) healthy
- Calibration session environment secured (mlock available)
- K≥5 players available for cohort formation

### Steps
1. **Verify ZK-Attested Consent** (BP-002)
   - Load consent proof from chain
   - Verify ZK proof: `ZAC_verify(proof, jurisdiction)`
   - Check consent not revoked
   - If failed: BLOCK calibration, request consent

2. **Check Privacy Budget** (BP-003)
   - Query player's ε consumption: `privacy_budget[player_id]`
   - Verify ε_remaining > 0.2 (minimum for calibration)
   - If exhausted: BLOCK, require annual consent renewal

3. **Form K-Anonymity Cohort** (BP-004)
   - Query cohort pool: `{controller}_{battery}_{transport}`
   - Count available players: `pool_size`
   - If pool_size < 5: MERGE with similar cohort
   - Assign player to cohort, record Merkle root

4. **Initialize Ephemeral Session** (BP-007)
   - Allocate RAM with `mlock()`
   - Set session timeout: 30 minutes
   - Configure secure erase callback
   - Start heartbeat monitoring

5. **Apply Temporal Decay** (BP-001)
   - Load player's historical calibrations
   - Calculate decay factors: `e^(-λt)` for t > 90 days
   - Apply to threshold weights
   - Mark expired records (>180 days) for archival

6. **Inject Differential Privacy** (BP-003)
   - Calculate sensitivity Δf per feature
   - Sample Laplacian noise: `Lap(0, Δf/ε)`
   - Add to threshold tracks
   - Log privacy budget consumption

7. **Distribute Shamir Shares** (BP-006)
   - Generate biometric secret: `hash(features)`
   - Create 16 shares: `ShamirSplit(secret, n=16, k=8)`
   - Distribute to agent fleet via secure channels
   - Verify 8-of-16 reconstruction capability

8. **Enable Homomorphic Processing** (BP-005)
   - Generate Paillier keypair
   - Send public key to player client
   - Configure encrypted computation pipeline
   - Test: encrypt → compute → decrypt cycle

9. **Final Invariant Check**
   - Verify all BP-001 to BP-007 satisfied
   - Generate compliance attestation
   - Log to `privacy_compliance_log`

### Invariant Checks
- **[BLOCK]** If ZK consent proof invalid or revoked
- **[BLOCK]** If privacy budget exhausted (ε ≥ 1.0)
- **[BLOCK]** If K-anonymity cannot be satisfied (pool < 5, no merge candidates)
- **[BLOCK]** If `mlock()` fails (cannot guarantee ESE)
- **[BLOCK]** If Shamir distribution fails (agent fleet compromised)
- **[WARNING]** If ε < 0.5 remaining (privacy budget running low)
- **[WARNING]** If temporal decay > 50% (old calibration, reduced confidence)
- **[PROCEED]** If all invariants satisfied, cohort formed, shares distributed

### Outputs
```json
{
  "compliance_status": "APPROVED|BLOCKED|WARNING",
  "invariants_checked": ["BP-001", "BP-002", "BP-003", "BP-004", "BP-005", "BP-006", "BP-007"],
  "privacy_budget": {
    "epsilon_consumed": 0.15,
    "epsilon_remaining": 0.85,
    "annual_limit": 1.0
  },
  "cohort": {
    "cohort_id": "ds4_touchpad_usb_2026q1",
    "pool_size": 12,
    "k_anonymity_satisfied": true
  },
  "consent": {
    "verified": true,
    "jurisdiction": "GDPR",
    "terms_version": "2026.1",
    "zk_proof_valid": true
  },
  "session": {
    "session_id": "uuid",
    "ephemeral_ram_secured": true,
    "timeout_at": "2026-03-29T12:30:00Z"
  },
  "shamir": {
    "shares_distributed": 16,
    "reconstruction_threshold": 8,
    "verification": "passed"
  },
  "compliance_attestation": "0x7a3f...9e2d"
}
```

### Regulatory Mapping
| Step | Regulation | Requirement |
|------|------------|-------------|
| 1 | GDPR Art.7 | Demonstrable consent |
| 2,6 | CCPA/CPRA | Risk assessment, DPIA |
| 3,5 | GDPR Art.9 | Anonymization, storage limitation |
| 4,7 | BIPA | Retention, destruction |
| 8 | EU AI Act | High-risk system accuracy |

### Time Estimate
2-3 seconds (privacy checks parallelized)

### Last Run
**Status**: PENDING
**Result**: TBD
**Next**: Implement Agent #18 (BiometricPrivacyComplianceAgent)

---

## Skill Proposal Template

When a pattern emerges in VAPI_MEMORY.md, propose new skills using this template:

```markdown
## Skill N: [Name]

**Command**: `/vapi [command]`

**Purpose**: [One sentence]

### Preconditions
- [List requirements]

### Steps
1. [Step 1]
2. [Step 2]
...

### Invariant Checks
- [WARNING/BLOCK/PROCEED conditions]

### Outputs
```json
[Expected output format]
```

### Time Estimate
[X minutes/seconds]

### Last Run
**Status**: [PENDING/COMPLETE/FAILED]
**Result**: [Outcome]
**Next**: [Action]
```

---

**Document Version**: 1.2 (Phase 136-137)
**Last Updated**: 2026-03-29
**Skill Count**: 11 (complete + privacy)
**Skill Status**: 7 COMPLETE, 4 PENDING (Controller skills + Privacy)
**Update Method**: Add new skills when patterns emerge, update "Last run" after execution

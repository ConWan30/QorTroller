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
**Status**: COMPLETE (2026-04-02, Phase 143)
**Result**: ratio=1.261 (diagonal+proper LOO, touchpad_corners N=11, 3-player). Classification 63.6% (7/11). Full Tikhonov unstable at N=11 — diagonal auto-fallback correct (N/p=1.375 < 3.0). P4 merged into P3 (same person). Per-pair: P1vP2=2.868, P1vP3=3.276, P2vP3=2.243. ABOVE 1.0 tournament gate. Caveat: N=11 legally thin — target ≥10/player.
**Next**: Capture ≥10 touchpad_corners sessions per player for enrollment quality gate

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
**Result**: separation_ratio=1.261 (touchpad_corners, Phase 143) — CONDITIONALLY ABOVE GATE. Full corpus pooled=0.417 still BLOCKER. dry_run=True still blocks full activation.
**Next**: Run after ≥10 touchpad_corners sessions/player captured

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

---
## Skill 15: VAPI Wiki Engine

**Command**: `/vapi wiki <operation>`

**File**: `vapi_wiki_engine.py` (replaces vapi_wiki.py and vapi_knowledge_engine.py)

**Purpose**: Protocol-anchored knowledge base that accumulates VAPI knowledge
permanently. No Anthropic API. Claude Code IS the intelligence layer.

### Commands

| Command | What It Does |
|---------|-------------|
| `python vapi_wiki_engine.py init` | Create wiki/ structure (once) |
| `python vapi_wiki_engine.py brief <file> <phase>` | Generate Claude Code ingest brief |
| `python vapi_wiki_engine.py check "<text>"` | Invariant check before writing |
| `python vapi_wiki_engine.py agent_feed` | Pull separation ratio from Agent 15 DB -> wiki page |
| `python vapi_wiki_engine.py ingest_sweep <json>` | Consume Skill 14 output -> wiki + W1 + AR log |
| `python vapi_wiki_engine.py sync_what_if` | VAPI_WHAT_IF.md W1s -> eval harness WIKI_KNOWN_W1 |
| `python vapi_wiki_engine.py snapshot [--anchor]` | SHA-256 [+ AdjudicationRegistry.sol on-chain] |
| `python vapi_wiki_engine.py phase_close <N>` | Complete phase boundary sequence |
| `python vapi_wiki_engine.py autoresearch_feed` | Wiki gaps -> AutoResearch experiment log |
| `python vapi_wiki_engine.py lint` | Health check (no API) |
| `python vapi_wiki_engine.py status` | Full integration health |

### Exclusive Integrations (all use existing VAPI infrastructure)

| Integration | What Connects | How |
|------------|--------------|-----|
| Agent 15 live feed | separation_ratio_snapshots table | Direct SQLite read |
| Skill 14 sweep | PostCode sweep JSON output | ingest_sweep command |
| Eval harness | KNOWN_GAPS -> WIKI_KNOWN_W1 | sync_what_if command |
| AdjudicationRegistry.sol | On-chain wiki anchor | snapshot --anchor |
| MCP server | vapi_reload_knowledge | After phase_close |
| AutoResearch loop | experiments/log.jsonl | autoresearch_feed |
| VAPI_WHAT_IF.md | W1 entries -> harness | Bidirectional sync |

### Standard Session Protocol

**Start of session**: `python vapi_wiki_engine.py status`

**After completing a phase**:
```bash
python vapi_wiki_engine.py phase_close <N>
# Then: Claude Code reads wiki/briefs/ and generates pages
```

**After any Skill 14 sweep**:
```bash
python vapi_wiki_engine.py ingest_sweep sweep_output.json
python vapi_wiki_engine.py sync_what_if
```

**End of session**:
```bash
python vapi_wiki_engine.py lint
python vapi_wiki_engine.py snapshot --anchor
```

### Invariant Enforcement (blocked before any wiki write)
- SHA-256(raw[:228]) — wrong hash slice
- nPublic != 5 — ZK circuit frozen
- auto_activate_on_breakthrough != False
- Epistemic threshold < 0.65
- separation_ratio assigned literal value
- dry_run=False without N>=100 context
- USB thresholds applied to BT sessions
- GSR_ENABLED=True without N>=30

### Why No API
Claude Code holds CLAUDE.md, all VAPI_*.md corpus files, and the full
session context. Calling the Anthropic API separately loses all of that,
costs tokens, and produces weaker results. The engine handles file I/O,
provenance, invariants, scoring, snapshots, and feed operations.
Claude Code handles all reasoning and page generation.

### Last Run
**Status**: COMPLETE (Phase 166 integration)
**Result**: Replaces vapi_wiki.py and vapi_knowledge_engine.py; 30 pages written; genesis snapshot d42ab3fecf8a
**Next**: phase_close after each phase completion
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

---

## Skill 14: PostCode Mitigation Sweep

**Command**: `/vapi sweep post-code`

**Purpose**: 12-step autonomous guardrail executed after EVERY code change. Detects invariant drift, security vulnerabilities, enrollment quality regressions, separation ratio impacts, and WHAT_IF corpus gaps before they reach production. The postcursor to perfected code — mitigation-first, proactive, eliminates vulnerabilities before they start.

**Skill ID**: 14
**Version**: 2.1 (Phase 156 — corrected + enhanced from Skill14.md v2.0)
**Trigger**: After any `Edit`, `Write`, or code-affecting tool call

---

### Preconditions
- CLAUDE.md is readable (ground truth for phase/counts)
- Bridge test suite runnable (`python -m pytest bridge/tests/ -q`)
- MCP vapi server responding (or bridge API at port 8080)
- `VAPI_SKILLS.md` / `VAPI_INVARIANTS.md` accessible
- Phase ≥ 156 (EnrollmentAutoGuidanceAgent LIVE)

---

### Steps

#### Step 1 — MCP Invariant Gate (ALWAYS FIRST — BLOCKS ALL OTHERS IF FAILS)

Query MCP or scan modified files for violation of any MANDATORY_INVARIANT. If ANY invariant is violated, **STOP IMMEDIATELY**, report `[INVARIANT_VIOLATION]`, do not proceed.

**MANDATORY_INVARIANTS** (all 20 must be present/respected):
```
1.  "228 bytes"               — PoAC wire format total size
2.  "SHA-256(raw[:164])"      — chain link hash body ONLY (NEVER raw[:228])
3.  "separation ratio 0.362"  — pre-Phase 143 diagonal reference (historical truth)
4.  "BLOCK_QUORUM=0.67"       — ioSwarm BLOCK threshold
5.  "ratio > 1.0"             — tournament gate target
6.  "TOURNAMENT BLOCKER"      — 0.417 full free-form corpus status
7.  "MINT_QUORUM=0.80"        — VHP mint ioSwarm threshold (fail-CLOSED)
8.  "dry_run=True"            — default enforcement simulation mode
9.  "ioswarm_enabled=False"   — no live ioSwarm nodes registered yet
10. "nPublic=5"               — ZK circuit public signals (FROZEN)
11. "L6_CHALLENGES_ENABLED=false" — never change without N≥50 RIGID_MAX
12. "GSR_ENABLED=false"       — never change without N≥30 sessions/player
13. "L6B_ENABLED=false"       — never change without N≥50 neuromuscular data
14. "auto_activate_on_breakthrough=False" — PERMANENT hardcoded (Phase 135)
15. "epistemic_consensus_threshold=0.65" — Phase 147 hardened (NOT 0.60)
16. "triage_prereq_required=True"        — Phase 147 W1 closure
17. "WIF-011 STRUCTURED_PROBE_TYPES"     — {touchpad_corners, touchpad_freeform, touchpad_swipes} frozenset
18. "SeparationRatioRegistry SHA-256(ratio_str+N+players_sorted+ts_ns)" — Phase 153 commitment formula
19. "Agent #19 tier mapping"  — DualShock Edge=Attested(L0-L6), Xbox/Switch=Standard(L0-L5)
20. "enrollment_complete ≠ defensible" — Phase 156 W1: count-gate fires on sessions_needed_total==0; defensible=True is SEPARATE gate
```

**Phase 156-specific MCP checks** (invoke `mcp__vapi__vapi_validate_proposal` or manual scan):
- `CHAIN_HASH_SLICE`: Any `raw[:228]` or `raw[164:]` hash usage → BLOCK
- `AUTO_ACTIVATE`: Any modification to `auto_activate_on_breakthrough` → BLOCK
- `EPISTEMIC_REGRESSION`: threshold < 0.65 or `triage_prereq_required=False` → BLOCK
- `ENROLLMENT_QUALITY_BYPASS`: `enrollment_complete` fires without checking `defensible` from separation_defensibility_log → FLAG W1
- `BT_THRESHOLD_POLLUTION`: BT sessions using USB thresholds 7.009/5.367 → BLOCK
- `SEPARATION_HARDCODE`: Hardcoded `separation_ratio = 1.261` without reading from DB → FLAG

#### Step 2 — Targeted Test Execution

Run only tests relevant to changed files. Map files to test suites:

| Changed File | Test Suite | Count Check |
|---|---|---|
| `bridge_agent.py` | `test_phase{N}_*.py` relevant phases | Bridge 1998 |
| `store.py` | All `test_phase*` (schema changes) | Bridge 1998 |
| `session_adjudicator.py` | Phase 98/105/109C/147 tests | Bridge 1998 |
| `operator_api.py` | All phase endpoint tests | Bridge 1998 |
| `config.py` | Config-dependent tests | Bridge 1998 |
| `*.sol` contracts | `npx hardhat test` | Hardhat 468 |
| `sdk/vapi_sdk.py` | `python -m pytest sdk/tests/ -v` | SDK 325 |
| `analyze_interperson_separation.py` | Phase 137-177 analysis tests | Bridge 1998 |

**Baseline counts** (Phase 177 ground truth from CLAUDE.md):
- Bridge: **1998** passing
- SDK: **325** passing
- Hardhat: **468** passing
- E2E: **14** (needs Hardhat node)

If count drops below baseline: `[TEST_REGRESSION]` — stop, root-cause before proceeding.

#### Step 3 — Root Cause Classification

Classify any failure by root cause from the 15-class taxonomy:

| Class | Trigger Pattern | Severity |
|---|---|---|
| `INVARIANT_DRIFT` | Any MANDATORY_INVARIANT violated | P0 — STOP |
| `AUTO_ACTIVATE_VIOLATION` | `auto_activate_on_breakthrough` touched | P0 — STOP |
| `CHAIN_HASH_ERROR` | `SHA-256(raw[:228])` used anywhere | P0 — STOP |
| `PRIVACY_VIOLATION` | `humanity_prob` appears on-chain or in logs | P0 — STOP |
| `PHASE_INTEROP` | Phase N logic calls Phase M > N+5 dependency | P1 — BLOCK |
| `BUS_EVENT_MISMATCH` | Bus event topic string inconsistent across publishers/subscribers | P1 — BLOCK |
| `BT_THRESHOLD_POLLUTION` | BT path using USB thresholds | P1 — BLOCK |
| `EPISTEMIC_REGRESSION` | Threshold < 0.65 or prereq removed | P1 — BLOCK |
| `SCHEMA_MISMATCH` | DB column count in test ≠ CREATE TABLE definition | P2 — FIX |
| `IMPORT_BREAK` | New import not in requirements.txt or mock not applied | P2 — FIX |
| `DB_MIGRATION` | ALTER TABLE missing from idempotent migration path | P2 — FIX |
| `ENROLLMENT_COUNT_GATE` | enrollment_complete fires without defensible=True check | P2 — FLAG W1 |
| `WS_PROTOCOL` | WebSocket message format changed without frontend sync | P3 — WARN |
| `IOSWARM_SEED_DRIFT` | Emulator seed ≠ phase-anchored constant (e.g., seed=109) | P3 — WARN |
| `SEPARATION_HARDCODE` | Ratio value hardcoded instead of DB-read | P3 — WARN |

#### Step 4 — Separation Ratio Impact Assessment

For any change touching: `store.py`, `session_adjudicator.py`, `analyze_interperson_separation.py`, calibration paths, or `separation_defensibility_log`:

Assess impact level:

| Level | Condition | Action |
|---|---|---|
| **NEUTRAL** | No separation-path code touched | Skip |
| **SAFE** | Read-only changes to ratio/defensibility | Log + continue |
| **MONITOR** | Session type filtering / covariance mode changed | Run `--probe-comparison`, log delta |
| **CAUTION** | `STRUCTURED_PROBE_TYPES` modified or session_type_filter logic changed | `[WIF-011]` — audit WIF-011 surface |
| **CRITICAL** | `min_n_per_player` lowered, `defensible` logic weakened, or `insert_separation_defensibility_log` validation bypassed | `[SEPARATION_REGRESSION]` — STOP |

**Key state to verify** (read from DB, not hardcoded):
- Current defensible=? (from `get_separation_defensibility_status()`)
- N per player for touchpad_corners (P1=3, P2=4, P3=4 — all below min_n=10, NOT YET DEFENSIBLE)
- Ratio 1.261 (touchpad_corners, N=11, diagonal) — CONDITIONALLY ABOVE GATE (thin N)
- Full corpus 0.417 (N=127, pooled) — TOURNAMENT BLOCKER

> ⚠️ **WIF-009 PLATEAU TRAP**: Do NOT recommend growing the free-form gameplay corpus to improve separation ratio. Free-form is confirmed in plateau regime (~0.417, will not exceed 1.0). The ONLY path to tournament-viable separation is ≥10 `touchpad_corners` sessions per player. Any code change that routes free-form sessions into separation analysis as if they contribute to tournament eligibility is `[SEPARATION_REGRESSION]`.

#### Step 5 — Enrollment Quality Gate Check

For changes touching: `EnrollmentAutoGuidanceAgent`, `calibration_intelligence_agent.py`, `separation_defensibility_log`, or `session_adjudicator_validator.py`:

**Phase 156 enrollment_complete semantics** (read `bridge/vapi_bridge/enrollment_auto_guidance_agent.py`):
- `enrollment_complete` fires when `overall_ready=True` (sessions_needed_total == 0)
- `defensible=True` (from `separation_defensibility_log`) is NOT currently a prerequisite
- This is **W1 (enrollment count-gate spoofing)** — enrolled count hit without quality gate
- Phase 157 candidate: add `defensible=True` as dual-condition for `enrollment_complete`

Check:
- [ ] Does the change weaken or bypass the enrollment quality gate further?
- [ ] Does `get_enrollment_capture_guidance()` still correctly compute per-probe per-player gaps?
- [ ] Does `insert_separation_defensibility_log` still raise `ValueError` on non-`STRUCTURED_PROBE_TYPES` session types?
- [ ] Does urgency_level (HIGH/MEDIUM/LOW) correctly escalate when stagnant_probe_count > 0?

If any check fails: classify as `ENROLLMENT_COUNT_GATE` and flag `[W1_ENROLLMENT_SPOOFING_RISK]`.

#### Step 6 — Agent Fleet Coherence

For changes touching `main.py`, `bridge_agent.py`, `operator_api.py`, or any agent file:

Verify the 20-agent fleet is intact:

| Agent # | Name | Status | Poll |
|---|---|---|---|
| 1-14 | Core agents (Phase 65–102) | LIVE | Various |
| 15 | SeparationRatioMonitorAgent | LIVE | 300s |
| 16 | TournamentActivationChainAgent | LIVE | auto_activate=False PERMANENT |
| 17 | SeparationRatioMonitorAgent (alias) | LIVE | — |
| 18 | AgentCalibrationIntegrityMonitor (ACIM) | LIVE | 15 min, 16 self-tests |
| 19 | ControllerHardwareIntelligenceAgent | LIVE Phase 155 | 1h |
| 20 | EnrollmentAutoGuidanceAgent | LIVE Phase 156 | 1h |
| 21 | FleetConsensusSnapshotAgent | LIVE Phase 157 | 1800s |
| 22 | BiometricPrivacyComplianceAgent | LIVE Phase 159 | event-driven |
| 23 | SeparationRatioRecoveryAgent | LIVE Phase 173 | on snapshot |
| 24 | AgeWeightedRatioPersistenceAgent | LIVE Phase 175 | on analysis run |
| 25 | PoACChainIntegrityMonitor | LIVE Phase 176 | periodic audit |
| 26 | ProtocolMaturityScoringAgent | LIVE Phase 177 | synthesizes 6 signals |

Critical invariants:
- Agent #16 `auto_activate_on_breakthrough=False` PERMANENT — touching this is P0 STOP
- Agent #18 ACIM runs 16 self-tests every 15 minutes — any change to agent health log schema needs ACIM test update
- Agent #19 tier mapping is immutable: DualShock Edge CFI-ZCP1 → Attested (L0-L6); Xbox/Switch → Standard (L0-L5)
- Agent #20 fires `enrollment_complete` bus event → TournamentActivationChainAgent (agent #16); verify event topology preserved
- Agent #23 fires `ratio_recovery_needed` bus event when recovery_needed=True; recovery_action P1_RE_ENROLLMENT is highest-urgency signal
- Agent #26 ProtocolMaturityScoringResult class renamed (not ProtocolMaturityResult — Phase 104 collision); verify in SDK sweeps

#### Step 7 — Schema and Migration Audit

For changes adding/modifying SQLite tables:

1. Verify `schema(N, "table_name")` entry added to `_SCHEMA_VERSIONS` in `store.py`
2. Verify `CREATE TABLE IF NOT EXISTS` in schema creation
3. Verify idempotent `ALTER TABLE ... ADD COLUMN` for any new columns on existing tables
4. Verify new columns have DEFAULT values (no NOT NULL without default)
5. Verify `INSERT OR IGNORE` used for dedup where appropriate
6. Verify table is queried in at least one `GET /agent/...` endpoint
7. Verify test covers schema_version assertion

> Phase 156 tables to preserve: `enrollment_auto_guidance_log`, `capture_stagnation_log`, `centroid_velocity_log`, `separation_defensibility_log`, `controller_hardware_profiles`, `tournament_activation_chain_log`

#### Step 8 — Fix Proposal

For any issue found in Steps 1-7:

Structure the fix proposal as:
```
[ROOT_CAUSE_CLASS] File: path/to/file.py Lines: N-M
Issue: <one sentence>
Why it matters: <invariant or security impact>
Fix: <exact code change or instruction>
Invariant preserved: <yes/no + which invariant>
Test coverage: <existing test catches this / new test needed>
```

Do NOT propose a fix that:
- Modifies any `[FROZEN]` or `[IMMUTABLE]` value
- Loosens a threshold without calibration data (N requirement)
- Sets `auto_activate_on_breakthrough=True`
- Uses `SHA-256(raw[:228])` as chain hash
- Enables `GSR_ENABLED`, `L6B_ENABLED`, `L6_CHALLENGES_ENABLED` without N≥ data
- Routes free-form gameplay sessions into tournament separation analysis

#### Step 9 — WHAT_IF Corpus Update

After every sweep, evaluate whether the change surface warrants a new WHAT_IF entry:

**W1 trigger** (new failure mode): File any of these as candidate W1 if found:
- New agent-to-agent bus event creates unauthenticated trust chain
- New DB table lacks idempotent migration (Phase upgrade path broken)
- New enrollment quality check missing from `enrollment_complete` prerequisite chain
- New on-chain call lacks anti-replay protection
- New threshold parameter lacks min() enforcement

**W2 trigger** (novel opportunity): File candidate W2 if:
- New bus event creates composability surface for on-chain proof (PoAC + PoAd + PoFC pattern)
- New agent output creates oracle input for Phase N+1 tournament gate
- New calibration track creates per-cohort separation analysis surface

Update `VAPI_WHAT_IF.md` with `WIF-XXX` entry if warranted. Reference phase candidate.

**Session W1 (Phase 157 candidate)**:
- `ENROLLMENT_COUNT_GATE`: `enrollment_complete` fires on `sessions_needed_total==0` without requiring `defensible=True` from separation_defensibility_log. Adversary could satisfy session count with N<10/player non-defensible sessions and trigger activation chain. Mitigation: dual-condition in Phase 157.

**Session W2 (Phase 157 candidate)**:
- `FLEET_CONSENSUS_SNAPSHOT`: SHA-256(sorted_agent_verdicts + separation_ratio + ts_ns) as "Proof of Fleet Consensus" (PoFC). Composable triple: PoAC (physiological) + PoAd (adjudication) + PoFC (fleet consensus). Agent #21 candidate.

#### Step 10 — Atomic Update Sequence

If code changes are approved after fix proposal (Step 8), apply in strict order:

```
1. source file(s)
2. store.py (if schema changes)
3. config.py (if new config fields)
4. operator_api.py (if new endpoints)
5. bridge_agent.py (if new tools)
6. sdk/vapi_sdk.py (if new SDK classes)
7. sdk/openapi.yaml (if new schemas/paths)
8. bridge/tests/ (new test file for phase N)
9. sdk/tests/ (new SDK test file)
10. contracts/ (if Solidity changes)
11. CLAUDE.md (update counts + phase)
12. VAPI-WORKFLOW.v2/VAPI_MEMORY.md (log findings)
```

Never apply out of order. Never update CLAUDE.md counts until tests pass.

#### Step 11 — Count Verification

After applying all fixes and running tests, verify final counts match CLAUDE.md:

```bash
python -m pytest bridge/tests/ --ignore=bridge/tests/test_e2e_simulation.py -q 2>&1 | tail -1
python -m pytest sdk/tests/ -q 2>&1 | tail -1
cd contracts && npx hardhat test 2>&1 | tail -3
```

Expected format:
```
Bridge: X passed (X ≥ 1998)
SDK: X passed (X ≥ 325)
Hardhat: X passing (X ≥ 468)
```

If any count drops: **DO NOT UPDATE CLAUDE.md**. Root-cause first.

If counts increase: update CLAUDE.md `Bridge:`, `SDK:`, `Hardhat:` fields AND `SDK_VERSION` if applicable.

#### Step 12 — ACIM Fleet Health Check (NEW — Phase 156)

Always query AgentCalibrationIntegrityMonitor after every sweep:

```bash
# Via bridge API
curl -H "x-api-key: $OPERATOR_KEY" http://localhost:8080/agent/calibration-health
```

Expected healthy response:
```json
{
  "agent_calibration_monitor_enabled": true,
  "total_self_tests": 16,
  "passed_self_tests": 16,
  "failed_self_tests": 0,
  "last_check_ts": "...",
  "timestamp": "..."
}
```

If `failed_self_tests > 0`: classify as `[ACIM_ALERT]` — do NOT merge the change. ACIM failing means a cross-agent calibration invariant was broken by the code change.

If ACIM is not running (bridge not started): verify `agent_calibration_monitor_enabled=True` in config and that `AgentCalibrationIntegrityMonitor` is wired in `main.py`.

---

#### Step 13 — Memory Scope Audit (NEW — Phase 164)

After every sweep, evaluate the `/memory` auto-memory index against VAPI's current development trajectory. This is the **WHAT_IF-driven memory loop**: a recursive self-assessment that ensures the agent's own long-term memory serves VAPI's forward progress and does not accumulate ballast that degrades context quality.

**Trigger**: Run as part of every Skill 14 execution. Also available standalone as `/vapi sweep memory`.

**Evaluation Logic — Three-Class Scoring**:

For each file in `C:\Users\Contr\.claude\projects\C--Users-Contr-vapi-pebble-prototype\memory\`:

| Class | Condition | Action |
|-------|-----------|--------|
| **ACTIVE** | Content needed for current/next phase decisions; contains non-derivable operational knowledge | KEEP |
| **ARCHIVABLE** | Historical fact fully derivable from `git log`, CLAUDE.md, or VAPI_WHAT_IF.md | MOVE to inline note in project_state.md OR delete if truly superseded |
| **STALE** | Content contradicted by current project state; WIF entries whose phases are CLOSED; analysis superseded by newer data | DELETE |

**WHAT_IF Loop Activation** — Score each file against two questions:
```
W1: "Does this memory describe a risk or constraint that still governs decisions in Phase N+1 or beyond?"
W2: "Does this memory surface an opportunity whose W2 implementation is not yet complete?"

If W1=NO and W2=NO → class STALE → delete autonomously
If W1=YES or W2=YES → class ACTIVE → keep
If all content is in CLAUDE.md or VAPI_WHAT_IF.md → class ARCHIVABLE → delete (already archived)
```

**CLAUDE.md Size Gate** — Check current CLAUDE.md char count:
```bash
wc -c C:/Users/Contr/vapi-pebble-prototype/CLAUDE.md
```

| Size | Status | Action |
|------|--------|--------|
| < 40,000 chars | ✅ HEALTHY | No action |
| 40,000–100,000 chars | ⚠️ WARNING | Flag for compression in next session |
| > 100,000 chars | ❌ CRITICAL | Propose CLAUDE_HISTORY.md archival immediately |

**Context Budget Invariant**: CLAUDE.md > 40k chars forces Claude Code's compaction layer to apply lossy summarization, which is the root cause of phase drift and session disruptions (WIF-026, WIF-027). Keeping CLAUDE.md lean is a **protocol integrity requirement**, not a cosmetic preference.

**Archival Target** — Sections safe to archive to `CLAUDE_HISTORY.md`:
- Per-phase detail blocks for Phase 17–130 (captured in git; derivable from `git log --oneline`)
- Completed items section (fully superseded by current phase log)
- Any "Phase N completed" block more than 10 phases behind current

**Sections to KEEP in CLAUDE.md** (never archive):
- Header state block (current phase, test counts, L4 thresholds, separation ratio, wallet)
- Architecture table
- PoAC wire format (FROZEN invariant)
- PITL stack table
- Calibration Corpus State (Phase 143 → current, N=14 touchpad_corners regression documented)
- L4 Calibration State (N=74, thresholds 7.009/5.367)
- Humanity Probability Formula
- Condensed Phase Summary table (1-line per phase — keep all, strip verbose blocks)
- Build & Test Commands
- Key Gotchas (Windows/HID)
- Hard Rules

**Autonomous Action**: When CLAUDE.md > 100k chars, autonomously propose the compression plan (what to archive, what to keep, target char count) and wait for user approval before executing. Never compress without approval — this modifies the single source of truth.

**Output Fields** (added to sweep JSON):
```json
{
  "memory_scope_audit": {
    "files_evaluated": N,
    "files_deleted": N,
    "files_kept": N,
    "claude_md_chars": N,
    "claude_md_status": "HEALTHY|WARNING|CRITICAL",
    "compression_proposed": false
  }
}
```

---

### Invariant Checks Summary

| Check | Condition | Action |
|---|---|---|
| PoAC size | Any struct ≠ 228 bytes | ❌ BLOCK |
| Chain hash | SHA-256(raw[:228]) used | ❌ BLOCK |
| Auto-activate | `auto_activate_on_breakthrough=True` | ❌ BLOCK |
| Epistemic | threshold < 0.65 or prereq removed | ❌ BLOCK |
| BT thresholds | BT using 7.009/5.367 | ❌ BLOCK |
| Separation | free-form added to tournament analysis | ❌ BLOCK |
| Count regression | test count < baseline | ❌ BLOCK |
| Enrollment W1 | count-gate without quality gate | ⚠️ FLAG W1 |
| ACIM health | failed_self_tests > 0 | ⚠️ FLAG |
| Schema | missing idempotent migration | ⚠️ FIX |
| WIF-011 | session_type not in STRUCTURED_PROBE_TYPES | ⚠️ FLAG |

---

### Outputs

```json
{
  "sweep_version": "2.2",
  "phase": 164,
  "timestamp": "2026-04-05T...",
  "invariants_checked": 21,
  "invariants_passed": 21,
  "root_cause_class": "NEUTRAL",
  "severity": "P4",
  "separation_impact": "NEUTRAL",
  "enrollment_gate_ok": true,
  "acim_healthy": true,
  "test_counts": {
    "bridge": 1934,
    "sdk": 297,
    "hardhat": 468
  },
  "memory_scope_audit": {
    "files_evaluated": 5,
    "files_deleted": 0,
    "files_kept": 5,
    "claude_md_chars": 0,
    "claude_md_status": "HEALTHY",
    "compression_proposed": false
  },
  "what_if_updates": [],
  "fix_proposals": [],
  "verdict": "PROCEED"
}
```

### AutoResearch Version

**Skill 14-AR**: AutoResearch trigger — run Skill 14 as autoresearch cycle targeting sweep security score ≥ 0.70.

Scoring formula:
```
score = 0.30 × invariants_preserved  (all 20 pass = 1.0)
      + 0.25 × gap_advancement        (W1s found and filed = 1.0; none found = 0.5)
      + 0.20 × what_if_quality        (new WIF entry with phase candidate = 1.0)
      + 0.15 × phase_coherence        (all phase references accurate = 1.0)
      + 0.10 × backward_compatibility (no count regression = 1.0)
PASS_THRESHOLD = 0.70
```

AutoResearch sweep log entry format:
```json
{
  "cycle": N,
  "skill": "14-AR",
  "score": 0.XXX,
  "invariants_preserved": true,
  "gaps_found": ["ENROLLMENT_COUNT_GATE", "..."],
  "what_if_filed": "WIF-NNN",
  "phase_coherence_ok": true,
  "test_delta": 0,
  "verdict": "PASS/FAIL"
}
```

Commit format when score ≥ 0.70:
```
chore(skill14-sweep): PostCode Mitigation cycle N (score=X.XXX)
```

### Time Estimate

- Fast path (no issues found): 3-5 minutes
- Medium path (schema/import fix): 10-15 minutes
- Full path (P1+ issue found): 30-60 minutes (root cause + fix + tests)

### Last Run
**Status**: PENDING
**Result**: —
**Next**: Run after next code change

---

---

## Skill 15: WORKFLOW.v2 Sync Recovery

**Command**: `/vapi sync-workflow`

**Purpose**: Recover VAPI-WORKFLOW.v2 context files to match CLAUDE.md ground truth after any session
disconnect or drift event. Detects phase/test-count divergence and corrects atomically.

**Skill ID**: 15
**Version**: 1.0 (Phase 164 — WIF-026 mitigation)
**Trigger**: Session start (if drift detected), manually, or via PostToolUse hook (automatic)

---

### Preconditions
- `CLAUDE.md` exists at repo root (ground truth)
- `VAPI-WORKFLOW.v2/VAPI_CONTEXT.md` exists
- `VAPI-WORKFLOW.v2/VAPI_MEMORY.md` exists
- Python 3.11+ available

---

### Steps

#### Step 1 — Drift Check (read-only)
```bash
python scripts/sync_vapi_workflow.py --check
```
Output: lists any drift items (PHASE, BRIDGE, SDK mismatches) or "No drift detected".

#### Step 2 — Full Sync (if drift found)
```bash
python scripts/sync_vapi_workflow.py
```
Updates: `VAPI_CONTEXT.md` Active Phase line, test count table rows (Bridge/SDK/Hardhat),
Next Phase line. Appends sync recovery note to `VAPI_MEMORY.md` Section 1.

#### Step 3 — Verify
```bash
python scripts/sync_vapi_workflow.py --check
```
Should report: `✅ No drift detected — WORKFLOW.v2 files are current.`

#### Step 4 — Manual file review (if --check still shows drift)
Script covers: Active Phase, test counts, Next Phase. Manual items if regex didn't match:
- Agent fleet count in `VAPI_AGENTS.md` (if new agents added since last sync)
- WIF status updates in `VAPI_WHAT_IF.md` (if WIFs closed in missed phases)
- Skill Last Run timestamps in `VAPI_SKILLS.md`

---

### Invariant Checks
- ✅ **PROCEED** if CLAUDE.md is readable and has `Current phase: Phase NNN —` pattern
- ⚠️ **WARNING** if drift > 3 phases: auto-sync covers counts but agent fleet entries may need manual update
- ❌ **BLOCK** if CLAUDE.md missing: "Single source of truth not found — cannot sync"
- ⚠️ **WARNING** if regex patterns don't match: means CLAUDE.md format changed — update sync script

---

### Outputs
```
[sync_vapi_workflow] Reading CLAUDE.md...
[sync_vapi_workflow] CLAUDE.md state: {'phase_num': 164, 'phase_desc': 'ConsentSnapshotAnchor ...', 'bridge': 1934, 'hardhat': 468, 'sdk': 297}
[sync_vapi_workflow] CONTEXT.md state: {'phase_num': 156, 'bridge': 1868, 'sdk': 265}
[sync_vapi_workflow] ⚠️  DRIFT DETECTED (3 items):
  PHASE: CLAUDE.md=164 CONTEXT.md=156
  BRIDGE: CLAUDE.md=1934 CONTEXT.md=1868
  SDK: CLAUDE.md=297 CONTEXT.md=265
[sync_vapi_workflow] ✅ Updated: CONTEXT.md active phase, CONTEXT.md test counts, CONTEXT.md next phase, MEMORY.md sync note
```

---

### Automation: PostToolUse Hook (ACTIVE)

The hook in `.claude/settings.local.json` fires automatically after every `Write` tool call:
```json
"hooks": {
  "PostToolUse": [
    {
      "matcher": "Write",
      "hooks": [{ "type": "command", "command": "cd C:/Users/Contr/vapi-pebble-prototype && python scripts/sync_vapi_workflow.py 2>&1 | head -5" }]
    }
  ]
}
```
- Runs in background after every file write
- Exits immediately if no drift (< 1 second)
- WIF-026 mitigation: context drift can never accumulate silently

---

### Time Estimate
- Drift check: < 1 second
- Full sync (script): < 2 seconds
- Manual agent/WIF review (large drift): 5-10 minutes

### Last Run
**Status**: COMPLETE (2026-04-08)
**Result**: 13-phase drift recovered (Phase 164→177, Bridge 1934→1998, SDK 297→325, agents 22→26)
**Next**: Automatic via PostToolUse hook on every Write

---

**Document Version**: 1.7 (Phase 177 — baselines updated to Bridge 1998 / SDK 325 / Agents 26)
**Last Updated**: 2026-04-08
**Skill Count**: 15 (complete + privacy + sweep + sync)
**Skill Status**: 8 COMPLETE, 3 PENDING (Controller skills + Privacy), 1 NEW (Skill 14 PostCode Sweep v2.2 + Step 13), 1 ACTIVE (Skill 15 Sync Recovery — hook live)
**Update Method**: Add new skills when patterns emerge, update "Last run" after execution
